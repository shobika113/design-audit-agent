"""
services/report_generator.py
JSON Report Generator — assembles the final AuditReport
from validated, scored findings and metadata.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from models.finding import (
    AuditReport,
    DesignPrinciple,
    Finding,
    ImageMetadata,
    SeverityLevel,
)

logger = logging.getLogger("design_audit.report_generator")

REPORTS_DIR = Path(__file__).parent.parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)


class ReportGenerator:
    """
    Assembles the final AuditReport from all pipeline outputs.
    Also handles JSON serialization and optional file persistence.
    """

    def build(
        self,
        filename: str,
        metadata: ImageMetadata,
        findings: List[Finding],
        overall_severity: SeverityLevel,
        overall_confidence: int,
        raw_summary: str,
        principles_checked: List[str],
        principles_with_issues: List[str],
        rejected_count: int = 0,
    ) -> AuditReport:
        """
        Build and validate the final AuditReport.
        Raises ValueError if the report itself is invalid (internal error).
        """
        logger.info(
            "Building report: %d findings, %d rejected, severity=%s",
            len(findings),
            rejected_count,
            overall_severity.value,
        )

        # Enrich the summary if findings were rejected
        summary = raw_summary
        if rejected_count > 0:
            summary += (
                f" [Note: {rejected_count} finding(s) from the LLM were rejected "
                f"during validation due to insufficient specificity or missing fields.]"
            )

        # Normalize principle enums
        p_checked = self._normalize_principles(principles_checked)
        p_issues = self._normalize_principles(principles_with_issues)
        print("DEBUG IMAGE_METADATA:", metadata)
        print("DEBUG TYPE:", type(metadata))
        report = AuditReport(
            resource=filename,
            image_metadata=metadata,
            total_findings=len(findings),
            findings=findings,
            summary=summary,
            overall_severity=overall_severity,
            analysis_confidence=overall_confidence,
            principles_checked=p_checked,
            principles_with_issues=p_issues,
        )

        logger.info(
            "Report built successfully: resource='%s' total_findings=%d",
            report.resource,
            report.total_findings,
        )
        return report

    def to_json(self, report: AuditReport, indent: int = 2) -> str:
        """Serialize the report to a formatted JSON string."""
        return json.dumps(report.model_dump(), indent=indent, default=str)

    def save(self, report: AuditReport) -> Path:
        """Save the report to the reports/ directory. Returns the file path."""
        safe_name = report.resource.replace(" ", "_").replace("/", "_")
        ts = report.timestamp.replace(":", "-").replace(".", "-")
        out_path = REPORTS_DIR / f"audit_{safe_name}_{ts}.json"
        out_path.write_text(self.to_json(report), encoding="utf-8")
        logger.info("Report saved to %s", out_path)
        return out_path

    # ── Private ────────────────────────────────────────────────────────────────

    def _normalize_principles(self, raw: List[str]) -> List[DesignPrinciple]:
        mapping = {
            "visual hierarchy": DesignPrinciple.VISUAL_HIERARCHY,
            "hierarchy": DesignPrinciple.VISUAL_HIERARCHY,
            "contrast": DesignPrinciple.CONTRAST,
            "spacing": DesignPrinciple.SPACING,
            "alignment": DesignPrinciple.ALIGNMENT,
            "consistency": DesignPrinciple.CONSISTENCY,
        }
        result = []
        seen = set()
        for item in raw:
            normalized = item.strip().lower()
            principle = mapping.get(normalized)
            if principle and principle not in seen:
                result.append(principle)
                seen.add(principle)
        return result
