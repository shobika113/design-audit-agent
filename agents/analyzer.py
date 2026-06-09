"""
agents/analyzer.py
Design Analysis Engine — the core LLM-powered agent.
Sends the image + prompt to Gemini, parses the response,
and returns raw (unvalidated) findings.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict

import google.generativeai as genai
from PIL import Image

logger = logging.getLogger("design_audit.analyzer")

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "audit_prompt.txt"
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds


class AnalysisError(Exception):
    """Raised when the analysis engine fails."""

    def __init__(self, code: str, message: str, detail: str = ""):
        self.code = code
        self.message = message
        self.detail = detail
        super().__init__(message)


class DesignAnalyzer:
    """
    LLM-powered design analysis engine.

    Responsibilities:
    - Load and manage the audit prompt
    - Send image + prompt to Gemini Vision
    - Parse and extract JSON from the response
    - Retry on transient failures
    - Detect and handle malformed responses
    """

    def __init__(self, api_key: str | None = None):
        key = api_key or os.getenv("GEMINI_API_KEY", "")
        if not key:
            raise AnalysisError(
                code="NO_API_KEY",
                message="GEMINI_API_KEY is not set.",
                detail="Set the GEMINI_API_KEY environment variable or pass it directly.",
            )
        genai.configure(api_key=key)
        self._model = genai.GenerativeModel("gemini-2.5-flash",generation_config={"response_mime_type": "application/json"})
        self._prompt = self._load_prompt()
        logger.info("DesignAnalyzer initialized with Gemini 2.5 Flash")

    # ── Public API ─────────────────────────────────────────────────────────────

    def analyze(self, image: Image.Image, filename: str) -> Dict[str, Any]:
        """
        Run full design analysis on a PIL image.
        Returns the raw parsed JSON dict from the LLM.
        Raises AnalysisError on unrecoverable failure.
        """
        logger.info("Analysis started for '%s'", filename)
        start = time.time()

        raw_response = self._call_with_retry(image, filename)
        parsed = self._extract_json(raw_response, filename)

        elapsed = time.time() - start
        logger.info(
            "Analysis completed for '%s' in %.2fs — %d findings returned",
            filename,
            elapsed,
            len(parsed.get("findings", [])),
        )
        return parsed

    # ── Private helpers ────────────────────────────────────────────────────────

    def _load_prompt(self) -> str:
        if not PROMPT_PATH.exists():
            raise AnalysisError(
                code="PROMPT_MISSING",
                message=f"Audit prompt not found at {PROMPT_PATH}",
                detail="Ensure prompts/audit_prompt.txt exists in the project root.",
            )
        text = PROMPT_PATH.read_text(encoding="utf-8").strip()
        logger.debug("Loaded audit prompt (%d chars)", len(text))
        return text

    def _call_with_retry(self, image: Image.Image, filename: str) -> str:
        """Call Gemini API with exponential back-off retry."""
        last_error: Exception | None = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(
                    "Calling Gemini API — attempt %d/%d for '%s'",
                    attempt,
                    MAX_RETRIES,
                    filename,
                )
                response = self._model.generate_content(
                    [self._prompt, image],
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.1,        # Low temperature = consistent, factual output
                        response_mime_type="application/json",
                        max_output_tokens=8192,  # Allow for very long responses    
                    ),
                )
                text = response.text
                if not text or not text.strip():
                    raise AnalysisError(
                        code="EMPTY_RESPONSE",
                        message="Gemini returned an empty response.",
                        detail=f"Attempt {attempt} returned no content.",
                    )
                logger.info("Gemini API responded on attempt %d", attempt)
                return text

            except AnalysisError:
                raise
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Gemini API attempt %d failed for '%s': %s",
                    attempt,
                    filename,
                    exc,
                )
                if attempt < MAX_RETRIES:
                    sleep_time = RETRY_DELAY * (2 ** (attempt - 1))
                    logger.info("Retrying in %.1f seconds…", sleep_time)
                    time.sleep(sleep_time)

        raise AnalysisError(
            code="API_FAILURE",
            message=f"Gemini API failed after {MAX_RETRIES} attempts.",
            detail=str(last_error),
        )

    def _extract_json(self, raw: str, filename: str) -> Dict[str, Any]:
        """
        Extract and parse JSON from the LLM response.
        Handles markdown code fences and stray text.
        """
        # Strip markdown code fences if present
        cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip()
        cleaned = cleaned.rstrip("`").strip()

        # Find the JSON object boundaries
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start == -1 or end == 0:
            logger.error(
                "No JSON object found in response for '%s'. Raw snippet: %s…",
                filename,
                raw[:200],
            )
            raise AnalysisError(
                code="MALFORMED_JSON",
                message="LLM response did not contain a valid JSON object.",
                detail=f"Response started with: {raw[:300]}",
            )

        json_str = cleaned[start:end]

        try:
            parsed = json.loads(json_str)
        except json.JSONDecodeError as exc:
            logger.error(
                "JSON parse error for '%s': %s\nJSON snippet: %s…",
                filename,
                exc,
                json_str[:300],
            )
            raise AnalysisError(
                code="JSON_PARSE_ERROR",
                message=f"Failed to parse LLM JSON response: {exc}",
                detail=json_str[:500],
            )

        if not isinstance(parsed, dict):
            raise AnalysisError(
                code="UNEXPECTED_JSON_SHAPE",
                message="LLM returned JSON but it is not an object.",
                detail=f"Got type: {type(parsed).__name__}",
            )

        if "findings" not in parsed:
            raise AnalysisError(
                code="MISSING_FINDINGS_KEY",
                message="LLM JSON response is missing the 'findings' key.",
                detail=f"Keys present: {list(parsed.keys())}",
            )

        logger.debug("Extracted %d raw findings from LLM response", len(parsed.get("findings", [])))
        return parsed
