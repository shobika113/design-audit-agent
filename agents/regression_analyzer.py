"""
agents/regression_analyzer.py
Regression Analysis Engine — Level 2 core LLM agent.

Sends two images (baseline + current) to Gemini Vision and
returns a structured visual diff with change classification.
"""

from __future__ import annotations

from email.mime import text
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict

import google.generativeai as genai
from PIL import Image

logger = logging.getLogger("design_audit.regression_analyzer")

REGRESSION_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "regression_prompt.txt"
MAX_RETRIES = 3
RETRY_DELAY = 2


class RegressionAnalysisError(Exception):
    """Raised when the regression analysis engine fails."""

    def __init__(self, code: str, message: str, detail: str = ""):
        self.code = code
        self.message = message
        self.detail = detail
        super().__init__(message)


class RegressionAnalyzer:
    """
    LLM-powered regression analysis engine for Level 2.

    Compares two images (baseline vs current) and returns
    a structured diff with change direction, hex values,
    pixel measurements, and accessibility regression flags.
    """

    def __init__(self, api_key: str | None = None):
        key = api_key or os.getenv("GEMINI_API_KEY", "")
        if not key:
            raise RegressionAnalysisError(
                code="NO_API_KEY",
                message="GEMINI_API_KEY is not set.",
                detail="Set the GEMINI_API_KEY environment variable or pass it directly.",
            )
        genai.configure(api_key=key)
        self._model = genai.GenerativeModel(
            "gemini-2.5-flash",
            generation_config={"response_mime_type": "application/json"},
        )
        self._prompt = self._load_prompt()
        logger.info("RegressionAnalyzer initialized with Gemini 2.5 Flash")

    # ── Public API ─────────────────────────────────────────────────────────────

    def analyze(
        self,
        baseline_image: Image.Image,
        current_image: Image.Image,
        baseline_name: str,
        current_name: str,
    ) -> Dict[str, Any]:
        """
        Run regression analysis comparing two PIL images.
        Returns the raw parsed JSON dict from the LLM.
        Raises RegressionAnalysisError on unrecoverable failure.
        """
        logger.info(
            "Regression analysis started: baseline='%s' current='%s'",
            baseline_name,
            current_name,
        )
        start = time.time()

        raw_response = self._call_with_retry(baseline_image, current_image, baseline_name, current_name)
        parsed = self._extract_json(raw_response, baseline_name, current_name)

        elapsed = time.time() - start
        logger.info(
            "Regression analysis completed in %.2fs — %d diffs returned",
            elapsed,
            len(parsed.get("diffs", [])),
        )
        return parsed

    # ── Private helpers ────────────────────────────────────────────────────────

    def _load_prompt(self) -> str:
        if not REGRESSION_PROMPT_PATH.exists():
            raise RegressionAnalysisError(
                code="PROMPT_MISSING",
                message=f"Regression prompt not found at {REGRESSION_PROMPT_PATH}",
                detail="Ensure prompts/regression_prompt.txt exists in the project root.",
            )
        text = REGRESSION_PROMPT_PATH.read_text(encoding="utf-8").strip()
        logger.debug("Loaded regression prompt (%d chars)", len(text))
        return text

    def _call_with_retry(
        self,
        baseline_image: Image.Image,
        current_image: Image.Image,
        baseline_name: str,
        current_name: str,
    ) -> str:
        """Call Gemini API with exponential back-off retry."""
        last_error: Exception | None = None

        # Build the prompt with explicit labels for the two images
        labeled_prompt = (
            f"{self._prompt}\n\n"
            f"Image 1 (BASELINE — before): {baseline_name}\n"
            f"Image 2 (CURRENT — after): {current_name}"
        )

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(
                    "Calling Gemini API — attempt %d/%d for regression '%s' vs '%s'",
                    attempt,
                    MAX_RETRIES,
                    baseline_name,
                    current_name,
                )
                response = self._model.generate_content(
                    [labeled_prompt, baseline_image, current_image],
                    generation_config=genai.types.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=8192,
                    response_mime_type="application/json",),
                )
                text = response.text
                logger.info("RAW RESPONSE:")
                logger.info(text)

                if not text or not text.strip():
                    raise RegressionAnalysisError(
                        code="EMPTY_RESPONSE",
                        message="Gemini returned an empty response.",
                        detail=f"Attempt {attempt} returned no content.",
                    )
                logger.info("Gemini API responded on attempt %d", attempt)
                return text

            except RegressionAnalysisError:
                raise
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Gemini API attempt %d failed: %s", attempt, exc
                )
                if attempt < MAX_RETRIES:
                    sleep_time = RETRY_DELAY * (2 ** (attempt - 1))
                    logger.info("Retrying in %.1f seconds…", sleep_time)
                    time.sleep(sleep_time)

        raise RegressionAnalysisError(
            code="API_FAILURE",
            message=f"Gemini API failed after {MAX_RETRIES} attempts.",
            detail=str(last_error),
        )

    def _extract_json(self, raw: str, baseline_name: str, current_name: str) -> Dict[str, Any]:
        """Extract and parse JSON from the LLM response."""
        cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip()
        cleaned = cleaned.rstrip("`").strip()

        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        logger.error("FULL RESPONSE:\n%s", cleaned)

        if start == -1 or end == 0:
            logger.error(
                "No JSON object found in response for '%s' vs '%s'. Snippet: %s…",
                baseline_name,
                current_name,
                raw[:200],
            )
            raise RegressionAnalysisError(
                code="MALFORMED_JSON",
                message="LLM response did not contain a valid JSON object.",
                detail=f"Response started with: {raw[:300]}",
            )

        json_str = cleaned[start:end]

        try:
            parsed = json.loads(json_str)
        except Exception:

            logger.error("RAW RESPONSE:\n%s", raw)

            raise RegressionAnalysisError(
                code="JSON_PARSE_ERROR",
                message="Failed to parse LLM JSON response",
                detail=raw[:1000],
            )   
        except json.JSONDecodeError as exc:
            logger.error("JSON parse error: %s\nSnippet: %s…", exc, json_str[:300])
            raise RegressionAnalysisError(
                code="JSON_PARSE_ERROR",
                message=f"Failed to parse LLM JSON response: {exc}",
                detail=json_str[:500],
            )

        if not isinstance(parsed, dict):
            raise RegressionAnalysisError(
                code="UNEXPECTED_JSON_SHAPE",
                message="LLM returned JSON but it is not an object.",
                detail=f"Got type: {type(parsed).__name__}",
            )

        if "diffs" not in parsed:
            raise RegressionAnalysisError(
                code="MISSING_DIFFS_KEY",
                message="LLM JSON response is missing the 'diffs' key.",
                detail=f"Keys present: {list(parsed.keys())}",
            )

        logger.debug("Extracted %d raw diffs from LLM response", len(parsed.get("diffs", [])))
        return parsed
