"""
agents/regression_pipeline.py
Level 2 Regression Analysis Pipeline.

Coordinates all layers:
  Input Validation → Image Loading → LLM Diff Analysis
  → Diff Validation → Report Assembly → Output
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

from PIL import Image

from agents.regression_analyzer import RegressionAnalysisError, RegressionAnalyzer
from agents.regression_validator import RegressionValidator
from models.finding import AgentError
from models.regression import ChangeDirection, RegressionReport, RegressionVerdict, VisualDiff
from services.image_processor import ImageProcessor, ImageValidationError
from services.regression_report_generator import RegressionReportGenerator

logger = logging.getLogger("design_audit.regression_pipeline")


# ─────────────────────────────────────────────
# Result Wrapper
# ─────────────────────────────────────────────
@dataclass
class RegressionPipelineResult:
    success: bool
    report: Optional[RegressionReport] = None
    error: Optional[AgentError] = None
    duration_seconds: float = 0.0


# ─────────────────────────────────────────────
# Main Pipeline
# ─────────────────────────────────────────────
class RegressionPipeline:
    """
    Level 2 Design Regression Analysis Agent.
    """

    def __init__(self, gemini_api_key: str | None = None):
        self._image_processor = ImageProcessor()
        self._analyzer = RegressionAnalyzer(api_key=gemini_api_key)
        self._validator = RegressionValidator()
        self._report_gen = RegressionReportGenerator()

        logger.info("RegressionPipeline initialized — all components ready")

    def run(
        self,
        baseline_bytes: bytes,
        baseline_name: str,
        current_bytes: bytes,
        current_name: str,
    ) -> RegressionPipelineResult:
        """
        Execute full regression pipeline (safe: never raises exceptions).
        """
        start = time.time()

        logger.info("=" * 60)
        logger.info("REGRESSION PIPELINE START: '%s' vs '%s'", baseline_name, current_name)
        logger.info("=" * 60)

        try:
            # ── Stage 1: Image Validation ─────────────────────────────
            logger.info("[Stage 1/5] Image Validation — Baseline")
            baseline_img, baseline_meta = self._image_processor.validate_and_load(
                baseline_bytes, baseline_name
            )

            logger.info(
                "[Stage 1/5] ✓ Baseline valid: %dx%d %s",
                baseline_meta.width,
                baseline_meta.height,
                baseline_meta.format,
            )

            logger.info("[Stage 1/5] Image Validation — Current")
            current_img, current_meta = self._image_processor.validate_and_load(
                current_bytes, current_name
            )

            logger.info(
                "[Stage 1/5] ✓ Current valid: %dx%d %s",
                current_meta.width,
                current_meta.height,
                current_meta.format,
            )

            # ── Stage 2: LLM Analysis ────────────────────────────────
            logger.info("[Stage 2/5] Regression Analysis (LLM)")

            raw_result = self._analyzer.analyze(
                baseline_image=baseline_img,
                current_image=current_img,
                baseline_name=baseline_name,
                current_name=current_name,
            )

            raw_diffs = raw_result.get("diffs", [])
            logger.info("[Stage 2/5] ✓ LLM returned %d diffs", len(raw_diffs))

            # ── Stage 3: Validation ──────────────────────────────────
            logger.info("[Stage 3/5] Diff Validation")

            accepted, rejected = self._validator.validate_all(raw_diffs)

            logger.info(
                "[Stage 3/5] ✓ %d accepted, %d rejected",
                len(accepted),
                len(rejected),
            )

            if raw_diffs and not accepted:
                return RegressionPipelineResult(
                    success=False,
                    error=AgentError(
                        error_code="ALL_DIFFS_REJECTED",
                        message="All diffs were rejected by validation",
                        detail=str(rejected),
                        recoverable=True,
                        suggested_action="Improve screenshot clarity or UI contrast.",
                    ),
                    duration_seconds=time.time() - start,
                )

            # ── Stage 4: Renumber Diffs ──────────────────────────────
            logger.info("[Stage 4/5] Renumbering diffs")

            accepted = self._renumber(accepted)

            # ── Stage 5: Report Generation ───────────────────────────
            logger.info("[Stage 5/5] Report Generation")

            report = self._report_gen.build(
                baseline_name=baseline_name,
                current_name=current_name,
                baseline_meta=baseline_meta,
                current_meta=current_meta,
                diffs=accepted,
                verdict_summary=raw_result.get(
                    "verdict_summary", "Regression analysis complete."
                ),
                verdict_raw=raw_result.get("verdict", "mixed"),
                analysis_confidence=int(raw_result.get("analysis_confidence", 70)),
            )

            self._report_gen.save(report)

            duration = time.time() - start

            logger.info("=" * 60)
            logger.info(
                "REGRESSION COMPLETE: %d diffs | verdict=%s | %.2fs",
                report.total_diffs,
                report.verdict.value,
                duration,
            )
            logger.info("=" * 60)

            return RegressionPipelineResult(
                success=True,
                report=report,
                duration_seconds=duration,
            )

        # ── Error Handling ───────────────────────────────────────────
        except ImageValidationError as exc:
            return RegressionPipelineResult(
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

        except RegressionAnalysisError as exc:
            return RegressionPipelineResult(
                success=False,
                error=AgentError(
                    error_code=exc.code,
                    message=exc.message,
                    detail=exc.detail,
                    recoverable=True,
                    suggested_action="Check API key or retry request.",
                ),
                duration_seconds=time.time() - start,
            )

        except Exception as exc:
            logger.exception("Unexpected pipeline error: %s", exc)

            return RegressionPipelineResult(
                success=False,
                error=AgentError(
                    error_code="INTERNAL_ERROR",
                    message=str(exc),
                    recoverable=False,
                    suggested_action="Check logs for debugging.",
                ),
                duration_seconds=time.time() - start,
            )

    # ─────────────────────────────────────────────
    # Helper
    # ─────────────────────────────────────────────
    def _renumber(self, diffs: list[VisualDiff]) -> list[VisualDiff]:
        """Ensure diff IDs are sequential."""
        return [
            d.model_copy(update={"diff_id": i + 1})
            for i, d in enumerate(diffs)
        ]