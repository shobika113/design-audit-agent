"""
models/regression.py
Pydantic models for Level 2 — Before/After Regression Analysis.

All data structures for visual diffs, change classification,
accessibility regressions, and the final RegressionReport.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class ChangeDirection(str, Enum):
    IMPROVEMENT = "improvement"
    REGRESSION = "regression"
    NEUTRAL = "neutral"


class AccessibilityRegressionType(str, Enum):
    CONTRAST_DROP = "contrast_ratio_drop"
    FONT_SIZE_REDUCTION = "font_size_reduction"
    SPACING_COMPRESSION = "spacing_compression"
    COLOR_REMOVAL = "color_removal"
    ELEMENT_HIDDEN = "element_hidden"


class VisualDiff(BaseModel):
    """
    A single detected visual difference between baseline and current.
    Every field is required — no partial diffs are accepted.
    """

    diff_id: int = Field(..., description="Sequential 1-based identifier for this diff")

    category: str = Field(
        ...,
        description="Category of change: color, typography, spacing, layout, component, contrast, etc.",
    )

    location: str = Field(
        ...,
        min_length=5,
        description="Specific UI location where the change was detected",
    )

    what_changed: str = Field(
        ...,
        min_length=10,
        description="Clear description of what specifically changed",
    )

    direction: ChangeDirection = Field(
        ..., description="Whether the change is an improvement, regression, or neutral"
    )

    direction_reasoning: str = Field(
        ...,
        min_length=10,
        description="Written reasoning explaining why this direction was assigned",
    )

    ux_impact: str = Field(
        ...,
        min_length=10,
        description="How this change affects the user experience",
    )

    confidence: int = Field(
        ..., ge=0, le=100, description="Confidence score for this diff (0–100)"
    )

    # Measurable values — populated when detectable
    baseline_hex: Optional[str] = Field(
        None, description="Hex color in baseline image (e.g. #1A2B3C)"
    )
    current_hex: Optional[str] = Field(
        None, description="Hex color in current image (e.g. #FFFFFF)"
    )
    baseline_px: Optional[int] = Field(
        None, description="Pixel measurement in baseline (e.g. padding 16px)"
    )
    current_px: Optional[int] = Field(
        None, description="Pixel measurement in current (e.g. padding 8px)"
    )
    baseline_value: Optional[str] = Field(
        None, description="Any other baseline measurement (font size, ratio, etc.)"
    )
    current_value: Optional[str] = Field(
        None, description="Any other current measurement"
    )

    # Accessibility regression flag
    is_accessibility_regression: bool = Field(
        default=False,
        description="True if this change introduces an accessibility regression",
    )
    accessibility_regression_type: Optional[AccessibilityRegressionType] = Field(
        None,
        description="Type of accessibility regression if applicable",
    )
    accessibility_detail: Optional[str] = Field(
        None,
        description="Specific accessibility detail (e.g. 'contrast ratio dropped from 4.8:1 to 2.1:1')",
    )


class RegressionVerdict(str, Enum):
    NET_IMPROVEMENT = "net_improvement"
    NET_REGRESSION = "net_regression"
    MIXED = "mixed"
    NO_CHANGE = "no_change"


class RegressionReport(BaseModel):
    """
    Top-level Level 2 regression analysis report.
    Machine-readable JSON output comparing baseline vs current.
    """

    resource_baseline: str = Field(..., description="Baseline image filename")
    resource_current: str = Field(..., description="Current image filename")
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z"
    )
    agent_version: str = "2.0.0"

    # Image metadata
    baseline_width: int
    baseline_height: int
    current_width: int
    current_height: int

    # Core diff results
    total_diffs: int = Field(..., ge=0)
    diffs: List[VisualDiff]

    # Summary counts
    improvements_count: int = Field(..., ge=0)
    regressions_count: int = Field(..., ge=0)
    neutral_count: int = Field(..., ge=0)

    # Accessibility
    accessibility_regressions: List[VisualDiff] = Field(
        default_factory=list,
        description="Subset of diffs that are accessibility regressions",
    )
    has_accessibility_regressions: bool = False

    # Overall verdict
    verdict: RegressionVerdict
    verdict_summary: str = Field(
        ...,
        min_length=20,
        description="Executive summary of net improvement vs net regression",
    )

    # Analysis metadata
    analysis_confidence: int = Field(..., ge=0, le=100)

    @model_validator(mode="after")
    def validate_counts(self) -> "RegressionReport":
        if self.total_diffs != len(self.diffs):
            raise ValueError(
                f"total_diffs ({self.total_diffs}) does not match actual diff count ({len(self.diffs)})"
            )
        actual_improvements = sum(1 for d in self.diffs if d.direction == ChangeDirection.IMPROVEMENT)
        actual_regressions = sum(1 for d in self.diffs if d.direction == ChangeDirection.REGRESSION)
        actual_neutral = sum(1 for d in self.diffs if d.direction == ChangeDirection.NEUTRAL)
        if self.improvements_count != actual_improvements:
            raise ValueError(f"improvements_count mismatch: declared {self.improvements_count}, actual {actual_improvements}")
        if self.regressions_count != actual_regressions:
            raise ValueError(f"regressions_count mismatch: declared {self.regressions_count}, actual {actual_regressions}")
        if self.neutral_count != actual_neutral:
            raise ValueError(f"neutral_count mismatch: declared {self.neutral_count}, actual {actual_neutral}")
        return self

    @model_validator(mode="after")
    def sync_accessibility_fields(self) -> "RegressionReport":
        a11y = [d for d in self.diffs if d.is_accessibility_regression]
        self.accessibility_regressions = a11y
        self.has_accessibility_regressions = len(a11y) > 0
        return self
