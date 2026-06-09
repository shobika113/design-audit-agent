"""
services/regression_report_generator.py
Regression Report Generator — assembles and serializes RegressionReport.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List

from models.finding import ImageMetadata
from models.regression import (
    ChangeDirection,
    RegressionReport,
    RegressionVerdict,
    VisualDiff,
)

logger = logging.getLogger("design_audit.regression_report_generator")

REPORTS_DIR = Path(__file__).parent.parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

VERDICT_MAP = {
    "net_improvement": RegressionVerdict.NET_IMPROVEMENT,
    "improvement": RegressionVerdict.NET_IMPROVEMENT,
    "net_regression": RegressionVerdict.NET_REGRESSION,
    "regression": RegressionVerdict.NET_REGRESSION,
    "mixed": RegressionVerdict.MIXED,
    "no_change": RegressionVerdict.NO_CHANGE,
    "no change": RegressionVerdict.NO_CHANGE,
}


class RegressionReportGenerator:
    """
    Assembles the final RegressionReport from pipeline outputs.
    Also handles JSON serialization and file persistence.
    """

    def build(
        self,
        baseline_name: str,
        current_name: str,
        baseline_meta: ImageMetadata,
        current_meta: ImageMetadata,
        diffs: List[VisualDiff],
        verdict_summary: str,
        verdict_raw: str,
        analysis_confidence: int,
    ) -> RegressionReport:
        improvements = [d for d in diffs if d.direction == ChangeDirection.IMPROVEMENT]
        regressions = [d for d in diffs if d.direction == ChangeDirection.REGRESSION]
        neutrals = [d for d in diffs if d.direction == ChangeDirection.NEUTRAL]

        # Derive verdict from counts if LLM verdict is unreliable
        verdict = VERDICT_MAP.get(verdict_raw.lower(), RegressionVerdict.MIXED)

        # Override verdict based on actual counts for consistency
        if not diffs:
            verdict = RegressionVerdict.NO_CHANGE
        elif not regressions and improvements:
            verdict = RegressionVerdict.NET_IMPROVEMENT
        elif not improvements and regressions:
            verdict = RegressionVerdict.NET_REGRESSION
        elif improvements and regressions:
            verdict = RegressionVerdict.MIXED
        elif not improvements and not regressions:
            verdict = RegressionVerdict.NO_CHANGE

        # Compute weighted confidence
        if diffs:
            confidence = round(sum(d.confidence for d in diffs) / len(diffs))
        else:
            confidence = analysis_confidence

        # Clamp confidence
        confidence = max(0, min(100, confidence))

        report = RegressionReport(
            resource_baseline=baseline_name,
            resource_current=current_name,
            baseline_width=baseline_meta.width,
            baseline_height=baseline_meta.height,
            current_width=current_meta.width,
            current_height=current_meta.height,
            total_diffs=len(diffs),
            diffs=diffs,
            improvements_count=len(improvements),
            regressions_count=len(regressions),
            neutral_count=len(neutrals),
            verdict=verdict,
            verdict_summary=verdict_summary,
            analysis_confidence=confidence,
        )

        logger.info(
            "Regression report built: %d diffs | improvements=%d regressions=%d neutral=%d | verdict=%s",
            report.total_diffs,
            report.improvements_count,
            report.regressions_count,
            report.neutral_count,
            report.verdict.value,
        )
        return report

    def to_json(self, report: RegressionReport, indent: int = 2) -> str:
        """Serialize the regression report to a formatted JSON string."""
        return json.dumps(report.model_dump(), indent=indent, default=str)

    def save(self, report: RegressionReport) -> Path:
        """Save the report to the reports/ directory."""
        safe_baseline = report.resource_baseline.replace(" ", "_").replace("/", "_")
        safe_current = report.resource_current.replace(" ", "_").replace("/", "_")
        ts = report.timestamp.replace(":", "-").replace(".", "-")
        out_path = REPORTS_DIR / f"regression_{safe_baseline}_vs_{safe_current}_{ts}.json"
        out_path.write_text(self.to_json(report), encoding="utf-8")
        logger.info("Regression report saved to %s", out_path)
        return out_path
