"""
agents/validator.py
Finding Validation Engine — the anti-hallucination layer.

Every finding produced by the LLM passes through here.
Findings that fail validation are rejected and logged,
never silently passed through.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

from models.finding import DesignPrinciple, Finding, SeverityLevel

logger = logging.getLogger("design_audit.validator")

# Fields that MUST be present and non-empty in every finding
REQUIRED_FIELDS = {
    "principle",
    "severity",
    "location",
    "user_impact",
    "recommendation",
    "confidence",
}

# Strings that indicate a hallucinated / generic location
GENERIC_LOCATIONS = {
    "page",
    "screen",
    "ui",
    "interface",
    "image",
    "unknown",
    "the page",
    "the screen",
    "the ui",
    "the interface",
    "n/a",
    "not specified",
    "various",
    "throughout",
    "multiple areas",
    "entire page",
}

# Strings that indicate a too-vague recommendation
VAGUE_REC_PREFIXES = (
    "consider",
    "maybe",
    "perhaps",
    "you could",
    "it might",
    "think about",
)


class ValidationResult:
    """Result of validating a single finding."""

    def __init__(self, finding: Finding | None, rejected: bool, reason: str = ""):
        self.finding = finding
        self.rejected = rejected
        self.reason = reason


class FindingValidator:
    """
    Validates each raw finding dict from the LLM.

    Rules enforced:
    1. All required fields present
    2. Location is specific (not generic)
    3. Recommendation is actionable
    4. Principle is a known value
    5. Severity is a known value
    6. Confidence is in range [0, 100]
    7. Pydantic model validation (type safety)
    """

    def validate_all(
        self, raw_findings: List[Dict[str, Any]]
    ) -> Tuple[List[Finding], List[Dict[str, Any]]]:
        """
        Validate a list of raw finding dicts.

        Returns:
            (accepted_findings, rejected_finding_dicts_with_reasons)
        """
        accepted: List[Finding] = []
        rejected: List[Dict[str, Any]] = []

        logger.info("Validating %d raw findings from LLM", len(raw_findings))

        for i, raw in enumerate(raw_findings):
            result = self._validate_one(raw, index=i)
            if result.rejected:
                logger.warning(
                    "Finding %d REJECTED: %s | Raw: %s",
                    i,
                    result.reason,
                    str(raw)[:200],
                )
                rejected.append({**raw, "_rejection_reason": result.reason})
            else:
                logger.debug(
                    "Finding %d ACCEPTED: principle=%s severity=%s location=%s",
                    i,
                    raw.get("principle"),
                    raw.get("severity"),
                    raw.get("location"),
                )
                accepted.append(result.finding)  # type: ignore[arg-type]

        logger.info(
            "Validation complete: %d accepted, %d rejected",
            len(accepted),
            len(rejected),
        )
        return accepted, rejected

    # ── Private ────────────────────────────────────────────────────────────────

    def _validate_one(self, raw: Dict[str, Any], index: int) -> ValidationResult:
        # 1. Must be a dict
        if not isinstance(raw, dict):
            return ValidationResult(
                None, True, f"Finding {index} is not a dict (got {type(raw).__name__})"
            )

        # 2. Required fields present
        missing = REQUIRED_FIELDS - set(raw.keys())
        if missing:
            return ValidationResult(
                None, True, f"Missing required fields: {missing}"
            )

        # 3. All required fields non-empty
        for field in REQUIRED_FIELDS:
            val = raw.get(field)
            if val is None or (isinstance(val, str) and not val.strip()):
                return ValidationResult(None, True, f"Field '{field}' is empty or null")

        # 4. Location specificity check
        location = str(raw.get("location", "")).strip()
        if location.lower() in GENERIC_LOCATIONS:
            return ValidationResult(
                None, True, f"Location '{location}' is too generic — must reference a specific UI element"
            )
        if len(location) < 5:
            return ValidationResult(
                None, True, f"Location '{location}' is too short to be meaningful"
            )

        # 5. Recommendation actionability check
        rec = str(raw.get("recommendation", "")).strip().lower()
        if len(rec) < 15:
            return ValidationResult(
                None, True, f"Recommendation is too short ({len(rec)} chars)"
            )
        if any(rec.startswith(prefix) for prefix in VAGUE_REC_PREFIXES) and len(rec) < 40:
            return ValidationResult(
                None, True, f"Recommendation is too vague: '{raw.get('recommendation')}'"
            )

        # 6. Confidence range check (pre-Pydantic)
        try:
            confidence = int(raw.get("confidence", -1))
        except (TypeError, ValueError):
            return ValidationResult(
                None, True, f"Confidence must be an integer, got: {raw.get('confidence')}"
            )
        if not (0 <= confidence <= 100):
            return ValidationResult(
                None, True, f"Confidence {confidence} is out of range [0, 100]"
            )

        # 7. Principle normalization
        principle_raw = str(raw.get("principle", "")).strip()
        principle = self._normalize_principle(principle_raw)
        if principle is None:
            return ValidationResult(
                None, True, f"Unknown principle '{principle_raw}'. Must be one of: {[p.value for p in DesignPrinciple]}"
            )

        # 8. Severity normalization
        severity_raw = str(raw.get("severity", "")).strip()
        severity = self._normalize_severity(severity_raw)
        if severity is None:
            return ValidationResult(
                None, True, f"Unknown severity '{severity_raw}'. Must be one of: {[s.value for s in SeverityLevel]}"
            )

        # 9. Full Pydantic model validation
        try:
            finding = Finding(
                principle=principle,
                severity=severity,
                location=raw["location"],
                user_impact=raw["user_impact"],
                recommendation=raw["recommendation"],
                confidence=confidence,
                wcag_criterion=raw.get("wcag_criterion"),
                element_description=raw.get("element_description"),
            )
        except Exception as exc:
            return ValidationResult(
                None, True, f"Pydantic validation failed: {exc}"
            )

        return ValidationResult(finding, False)

    def _normalize_principle(self, raw: str) -> DesignPrinciple | None:
        mapping = {
            "visual hierarchy": DesignPrinciple.VISUAL_HIERARCHY,
            "hierarchy": DesignPrinciple.VISUAL_HIERARCHY,
            "contrast": DesignPrinciple.CONTRAST,
            "wcag": DesignPrinciple.CONTRAST,
            "spacing": DesignPrinciple.SPACING,
            "whitespace": DesignPrinciple.SPACING,
            "alignment": DesignPrinciple.ALIGNMENT,
            "consistency": DesignPrinciple.CONSISTENCY,
            "inconsistency": DesignPrinciple.CONSISTENCY,
        }
        return mapping.get(raw.lower())

    def _normalize_severity(self, raw: str) -> SeverityLevel | None:
        mapping = {
            "critical": SeverityLevel.CRITICAL,
            "high": SeverityLevel.HIGH,
            "medium": SeverityLevel.MEDIUM,
            "moderate": SeverityLevel.MEDIUM,
            "low": SeverityLevel.LOW,
            "minor": SeverityLevel.LOW,
            "info": SeverityLevel.INFO,
            "informational": SeverityLevel.INFO,
        }
        return mapping.get(raw.lower())
