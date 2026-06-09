"""
agents/scorer.py
Severity and Confidence Scoring Engine.

Post-processes validated findings to:
1. Cross-check and potentially adjust confidence scores
2. Derive the overall severity for the report
3. Calculate an aggregate analysis confidence
"""

from __future__ import annotations

import logging
from typing import List, Tuple

from models.finding import DesignPrinciple, Finding, SeverityLevel

logger = logging.getLogger("design_audit.scorer")

# Severity → numeric weight for comparison
SEVERITY_WEIGHT: dict[SeverityLevel, int] = {
    SeverityLevel.CRITICAL: 5,
    SeverityLevel.HIGH: 4,
    SeverityLevel.MEDIUM: 3,
    SeverityLevel.LOW: 2,
    SeverityLevel.INFO: 1,
}

# Principles that carry higher stakes for accessibility/legal compliance
HIGH_STAKES_PRINCIPLES = {DesignPrinciple.CONTRAST}


class ScoringEngine:
    """
    Applies scoring logic to a list of validated findings.

    Business rules:
    - Contrast findings are accessibility-critical → minimum severity enforced
    - Low-confidence findings (< 50) are downgraded one severity step
    - Overall analysis confidence is the weighted average of individual scores
    """

    def score(
        self, findings: List[Finding]
    ) -> Tuple[List[Finding], SeverityLevel, int]:
        """
        Score and adjust findings.

        Returns:
            (adjusted_findings, overall_severity, overall_confidence)
        """
        if not findings:
            logger.info("No findings to score — returning clean bill of health")
            return [], SeverityLevel.INFO, 100

        adjusted = [self._adjust_finding(f) for f in findings]
        overall_severity = self._compute_overall_severity(adjusted)
        overall_confidence = self._compute_overall_confidence(adjusted)

        logger.info(
            "Scoring complete: %d findings | overall_severity=%s | overall_confidence=%d",
            len(adjusted),
            overall_severity.value,
            overall_confidence,
        )
        return adjusted, overall_severity, overall_confidence

    # ── Private ────────────────────────────────────────────────────────────────

    def _adjust_finding(self, f: Finding) -> Finding:
        """Apply business rules to a single finding."""
        severity = f.severity
        confidence = f.confidence

        # Rule 1: Contrast issues are accessibility-critical.
        # If LLM scored them as Low/Info but they involve contrast,
        # escalate to at least Medium.
        if f.principle == DesignPrinciple.CONTRAST:
            if SEVERITY_WEIGHT[severity] < SEVERITY_WEIGHT[SeverityLevel.MEDIUM]:
                logger.info(
                    "Escalating contrast finding at '%s' from %s → Medium (accessibility rule)",
                    f.location,
                    severity.value,
                )
                severity = SeverityLevel.MEDIUM

        # Rule 2: If confidence < 50, downgrade severity by one step.
        # We can't be certain enough to call something High or Critical
        # without enough confidence.
        if confidence < 50 and SEVERITY_WEIGHT[severity] >= SEVERITY_WEIGHT[SeverityLevel.HIGH]:
            downgraded = self._downgrade(severity)
            logger.info(
                "Downgrading low-confidence finding at '%s': %s → %s (confidence=%d)",
                f.location,
                severity.value,
                downgraded.value,
                confidence,
            )
            severity = downgraded

        # Return a new Finding with adjusted values (Pydantic models are immutable by default)
        return f.model_copy(update={"severity": severity})

    def _compute_overall_severity(self, findings: List[Finding]) -> SeverityLevel:
        worst = max(findings, key=lambda f: SEVERITY_WEIGHT[f.severity])
        return worst.severity

    def _compute_overall_confidence(self, findings: List[Finding]) -> int:
        """
        Weighted average confidence — Critical/High findings carry more weight
        because they impact the report's credibility more.
        """
        total_weight = 0
        weighted_sum = 0
        for f in findings:
            w = SEVERITY_WEIGHT[f.severity]
            weighted_sum += f.confidence * w
            total_weight += w
        if total_weight == 0:
            return 0
        return round(weighted_sum / total_weight)

    def _downgrade(self, severity: SeverityLevel) -> SeverityLevel:
        order = [
            SeverityLevel.INFO,
            SeverityLevel.LOW,
            SeverityLevel.MEDIUM,
            SeverityLevel.HIGH,
            SeverityLevel.CRITICAL,
        ]
        idx = order.index(severity)
        return order[max(0, idx - 1)]
