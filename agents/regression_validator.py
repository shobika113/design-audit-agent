"""
agents/regression_validator.py
Diff Validation Engine — anti-hallucination layer for Level 2.

Every visual diff produced by the LLM passes through here.
Diffs that fail validation are rejected and logged, never silently passed through.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Tuple

from models.regression import (
    AccessibilityRegressionType,
    ChangeDirection,
    VisualDiff,
)

logger = logging.getLogger("design_audit.regression_validator")

REQUIRED_FIELDS = {
    "diff_id",
    "category",
    "location",
    "what_changed",
    "direction",
    "direction_reasoning",
    "ux_impact",
    "confidence",
}

GENERIC_LOCATIONS = {
    "page", "screen", "ui", "interface", "image", "unknown",
    "the page", "the screen", "n/a", "not specified", "various",
    "throughout", "multiple areas", "entire page",
}

VALID_CATEGORIES = {
    "color", "typography", "spacing", "layout", "component",
    "contrast", "iconography", "other",
}

HEX_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")


class RegressionValidator:
    """
    Validates each raw diff dict from the LLM.

    Rules enforced:
    1. All required fields present and non-empty
    2. Location is specific (not generic)
    3. direction is a valid ChangeDirection value
    4. confidence is in [0, 100]
    5. hex values are valid #RRGGBB format when present
    6. Pydantic model validation (type safety)
    """

    def validate_all(
        self, raw_diffs: List[Dict[str, Any]]
    ) -> Tuple[List[VisualDiff], List[Dict[str, Any]]]:
        """
        Validate a list of raw diff dicts.

        Returns:
            (accepted_diffs, rejected_diff_dicts_with_reasons)
        """
        accepted: List[VisualDiff] = []
        rejected: List[Dict[str, Any]] = []

        logger.info("Validating %d raw diffs from LLM", len(raw_diffs))

        for i, raw in enumerate(raw_diffs):
            diff, reason = self._validate_one(raw, index=i)
            if diff is None:
                logger.warning(
                    "Diff %d REJECTED: %s | Raw: %s",
                    i,
                    reason,
                    str(raw)[:200],
                )
                rejected.append({**raw, "_rejection_reason": reason})
            else:
                logger.debug(
                    "Diff %d ACCEPTED: category=%s direction=%s location=%s",
                    i,
                    raw.get("category"),
                    raw.get("direction"),
                    raw.get("location"),
                )
                accepted.append(diff)

        logger.info(
            "Validation complete: %d accepted, %d rejected",
            len(accepted),
            len(rejected),
        )
        return accepted, rejected

    # ── Private ────────────────────────────────────────────────────────────────

    def _validate_one(self, raw: Dict[str, Any], index: int) -> Tuple[VisualDiff | None, str]:
        if not isinstance(raw, dict):
            return None, f"Diff {index} is not a dict (got {type(raw).__name__})"

        missing = REQUIRED_FIELDS - set(raw.keys())
        if missing:
            return None, f"Missing required fields: {missing}"

        for field in REQUIRED_FIELDS:
            val = raw.get(field)
            if val is None or (isinstance(val, str) and not val.strip()):
                return None, f"Field '{field}' is empty or null"

        location = str(raw.get("location", "")).strip()
        if location.lower() in GENERIC_LOCATIONS:
            return None, f"Location '{location}' is too generic"
        if len(location) < 5:
            return None, f"Location '{location}' is too short to be meaningful"

        try:
            confidence = int(raw.get("confidence", -1))
        except (TypeError, ValueError):
            return None, f"Confidence must be an integer, got: {raw.get('confidence')}"
        if not (0 <= confidence <= 100):
            return None, f"Confidence {confidence} is out of range [0, 100]"

        direction_raw = str(raw.get("direction", "")).strip().lower()
        direction = self._normalize_direction(direction_raw)
        if direction is None:
            return None, f"Unknown direction '{direction_raw}'. Must be one of: improvement, regression, neutral"

        # Validate hex values if present
        for hex_field in ("baseline_hex", "current_hex"):
            val = raw.get(hex_field)
            if val and val not in (None, "null", ""):
                if not HEX_PATTERN.match(str(val)):
                    # Don't reject — just clear the invalid value
                    raw[hex_field] = None
                    logger.debug("Cleared invalid hex value '%s' in field '%s'", val, hex_field)

        # Normalize pixel values
        for px_field in ("baseline_px", "current_px"):
            val = raw.get(px_field)
            if val in (None, "null", ""):
                raw[px_field] = None
            else:
                try:
                    raw[px_field] = int(val)
                except (TypeError, ValueError):
                    raw[px_field] = None

        # Normalize accessibility type
        a11y_type_raw = raw.get("accessibility_regression_type")
        a11y_type = None
        if a11y_type_raw and a11y_type_raw not in (None, "null", ""):
            a11y_type = self._normalize_a11y_type(str(a11y_type_raw))

        # Normalize booleans
        is_a11y = raw.get("is_accessibility_regression", False)
        if isinstance(is_a11y, str):
            is_a11y = is_a11y.lower() in ("true", "1", "yes")

        # Assign sequential diff_id (use index+1 if LLM gave a bad value)
        try:
            diff_id = int(raw.get("diff_id", index + 1))
        except (TypeError, ValueError):
            diff_id = index + 1

        try:
            diff = VisualDiff(
                diff_id=diff_id,
                category=str(raw.get("category", "other")).lower(),
                location=raw["location"],
                what_changed=raw["what_changed"],
                direction=direction,
                direction_reasoning=raw["direction_reasoning"],
                ux_impact=raw["ux_impact"],
                confidence=confidence,
                baseline_hex=raw.get("baseline_hex") or None,
                current_hex=raw.get("current_hex") or None,
                baseline_px=raw.get("baseline_px"),
                current_px=raw.get("current_px"),
                baseline_value=raw.get("baseline_value") or None,
                current_value=raw.get("current_value") or None,
                is_accessibility_regression=is_a11y,
                accessibility_regression_type=a11y_type,
                accessibility_detail=raw.get("accessibility_detail") or None,
            )
        except Exception as exc:
            return None, f"Pydantic validation failed: {exc}"

        return diff, ""

    def _normalize_direction(self, raw: str) -> ChangeDirection | None:
        mapping = {
            "improvement": ChangeDirection.IMPROVEMENT,
            "improved": ChangeDirection.IMPROVEMENT,
            "better": ChangeDirection.IMPROVEMENT,
            "regression": ChangeDirection.REGRESSION,
            "regressed": ChangeDirection.REGRESSION,
            "worse": ChangeDirection.REGRESSION,
            "degradation": ChangeDirection.REGRESSION,
            "neutral": ChangeDirection.NEUTRAL,
            "no change": ChangeDirection.NEUTRAL,
            "unchanged": ChangeDirection.NEUTRAL,
        }
        return mapping.get(raw)

    def _normalize_a11y_type(self, raw: str) -> AccessibilityRegressionType | None:
        mapping = {
            "contrast_ratio_drop": AccessibilityRegressionType.CONTRAST_DROP,
            "contrast ratio drop": AccessibilityRegressionType.CONTRAST_DROP,
            "contrast drop": AccessibilityRegressionType.CONTRAST_DROP,
            "font_size_reduction": AccessibilityRegressionType.FONT_SIZE_REDUCTION,
            "font size reduction": AccessibilityRegressionType.FONT_SIZE_REDUCTION,
            "font reduction": AccessibilityRegressionType.FONT_SIZE_REDUCTION,
            "spacing_compression": AccessibilityRegressionType.SPACING_COMPRESSION,
            "spacing compression": AccessibilityRegressionType.SPACING_COMPRESSION,
            "color_removal": AccessibilityRegressionType.COLOR_REMOVAL,
            "color removal": AccessibilityRegressionType.COLOR_REMOVAL,
            "element_hidden": AccessibilityRegressionType.ELEMENT_HIDDEN,
            "element hidden": AccessibilityRegressionType.ELEMENT_HIDDEN,
        }
        return mapping.get(raw.lower())
