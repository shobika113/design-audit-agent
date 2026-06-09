"""
agents/pipeline.py
Master orchestration pipeline for the Design Audit Agent.

Coordinates all layers in order:
  Input → Image Validation → Analysis → Finding Validation
  → Scoring → Report Generation → Output

This is the single entry point that Streamlit (or any other
caller) should use. It is fully observable through structured logging.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

from PIL import Image

from agents.analyzer import AnalysisError, DesignAnalyzer
from agents.scorer import ScoringEngine
from agents.validator import FindingValidator
from models.finding import AgentError, AuditReport,ImageMetadata
from services.image_processor import ImageProcessor, ImageValidationError
from services.report_generator import ReportGenerator

logger = logging.getLogger("design_audit.pipeline")


@dataclass
class PipelineResult:
    """Outcome of running the full audit pipeline."""

    success: bool
    report: Optional[AuditReport] = None
    error: Optional[AgentError] = None
    duration_seconds: float = 0.0


class AuditPipeline:
    """
    The top-level Design Audit Agent.

    Usage:
        pipeline = AuditPipeline(gemini_api_key="...")
        result = pipeline.run(file_bytes=..., filename="screen.png")
        if result.success:
            print(result.report)
        else:
            print(result.error)
    """

    def __init__(self, gemini_api_key: str | None = None):
        self._image_processor = ImageProcessor()
        self._analyzer = DesignAnalyzer(api_key=gemini_api_key)
        self._validator = FindingValidator()
        self._scorer = ScoringEngine()
        self._report_gen = ReportGenerator()
        logger.info("AuditPipeline initialized — all components ready")

    def run(self, file_bytes: bytes, filename: str) -> PipelineResult:
        """
        Execute the full audit pipeline for a single image.

        Returns a PipelineResult — never raises an exception.
        All errors are captured and returned as structured AgentError objects.
        """
        start = time.time()
        logger.info("=" * 60)
        logger.info("PIPELINE START: '%s'", filename)
        logger.info("=" * 60)

        try:
            # ── Stage 1: Image Validation ──────────────────────────────────
            logger.info("[Stage 1/5] Image Validation")
            pil_image, metadata = self._image_processor.validate_and_load(
                file_bytes, filename
            )
            logger.info(
                "[Stage 1/5] ✓ Image valid: %dx%d %s",
                metadata.width,
                metadata.height,
                metadata.format,
            )

            # ── Stage 2: LLM Analysis ──────────────────────────────────────
            logger.info("[Stage 2/5] Design Analysis (LLM)")
            raw_result = self._analyzer.analyze(pil_image, filename)
            raw_findings = raw_result.get("findings", [])
            logger.info(
                "[Stage 2/5] ✓ LLM returned %d raw findings", len(raw_findings)
            )

            # ── Stage 3: Finding Validation ────────────────────────────────
            logger.info("[Stage 3/5] Finding Validation")
            accepted, rejected = self._validator.validate_all(raw_findings)
            logger.info(
                "[Stage 3/5] ✓ %d accepted, %d rejected", len(accepted), len(rejected)
            )

            # Guard: If ALL findings were rejected, something went wrong
            if raw_findings and not accepted:
                return PipelineResult(
                    success=False,
                    error=AgentError(
                        error_code="ALL_FINDINGS_REJECTED",
                        message=(
                            f"All {len(raw_findings)} findings from the LLM were rejected "
                            f"during validation. The LLM output was too vague or malformed."
                        ),
                        detail=f"Rejected reasons: {[r.get('_rejection_reason') for r in rejected]}",
                        recoverable=True,
                        suggested_action="Try uploading a higher-resolution screenshot or a different image.",
                    ),
                    duration_seconds=time.time() - start,
                )

            # ── Stage 4: Scoring ───────────────────────────────────────────
            logger.info("[Stage 4/5] Severity & Confidence Scoring")
            scored_findings, overall_severity, overall_confidence = self._scorer.score(accepted)
            logger.info(
                "[Stage 4/5] ✓ overall_severity=%s confidence=%d%%",
                overall_severity.value,
                overall_confidence,
            )

            # ── Stage 5: Report Generation ─────────────────────────────────
            logger.info("[Stage 5/5] Report Generation")
            report = self._report_gen.build(
                filename=filename,
                metadata=metadata,
                findings=scored_findings,
                overall_severity=overall_severity,
                overall_confidence=overall_confidence,
                raw_summary=raw_result.get("summary", "Analysis complete."),
                principles_checked=raw_result.get(
                    "principles_checked",
                    ["Visual Hierarchy", "Contrast", "Spacing", "Alignment", "Consistency"],
                ),
                principles_with_issues=raw_result.get("principles_with_issues", []),
                rejected_count=len(rejected),
            )

            # Persist to disk
            self._report_gen.save(report)

            duration = time.time() - start
            logger.info("=" * 60)
            logger.info(
                "PIPELINE COMPLETE: '%s' | %d findings | %.2fs",
                filename,
                report.total_findings,
                duration,
            )
            logger.info("=" * 60)

            return PipelineResult(success=True, report=report, duration_seconds=duration)

        # ── Error handling ─────────────────────────────────────────────────────

        except ImageValidationError as exc:
            logger.error("Image validation failed: [%s] %s", exc.code, exc.message)
            return PipelineResult(
                success=False,
                error=AgentError(
                    error_code=exc.code,
                    message=exc.message,
                    detail=exc.suggestion,
                    recoverable=True,
                    suggested_action=exc.suggestion,
                ),
                duration_seconds=time.time() - start,
            )

        except AnalysisError as exc:
            logger.error("Analysis failed: [%s] %s", exc.code, exc.message)
            return PipelineResult(
                success=False,
                error=AgentError(
                    error_code=exc.code,
                    message=exc.message,
                    detail=exc.detail,
                    recoverable=exc.code
                    not in ("NO_API_KEY", "PROMPT_MISSING"),
                    suggested_action=(
                        "Check your GEMINI_API_KEY and internet connection, then retry."
                        if exc.code == "API_FAILURE"
                        else "Contact the administrator."
                    ),
                ),
                duration_seconds=time.time() - start,
            )

        except Exception as exc:
            logger.exception("Unexpected pipeline error: %s", exc)
            return PipelineResult(
                success=False,
                error=AgentError(
                    error_code="INTERNAL_ERROR",
                    message=f"An unexpected error occurred: {type(exc).__name__}: {exc}",
                    recoverable=False,
                    suggested_action="Please report this error with the log output.",
                ),
                duration_seconds=time.time() - start,
            )
