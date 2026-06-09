from datetime import datetime
from enum import Enum
from typing import Optional, List

from pydantic import BaseModel, Field, field_validator, model_validator


class SeverityLevel(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    INFO = "Info"


class DesignPrinciple(str, Enum):
    VISUAL_HIERARCHY = "Visual Hierarchy"
    CONTRAST = "Contrast"
    SPACING = "Spacing"
    ALIGNMENT = "Alignment"
    CONSISTENCY = "Consistency"


class Finding(BaseModel):
    principle: DesignPrinciple
    severity: SeverityLevel
    location: str
    user_impact: str
    recommendation: str
    confidence: int = Field(..., ge=0, le=100)

    wcag_criterion: Optional[str] = None
    element_description: Optional[str] = None

    @field_validator("location")
    @classmethod
    def validate_location(cls, v):
        generic = {"page", "screen", "ui", "interface", "image", "unknown"}
        if v.strip().lower() in generic:
            raise ValueError("Location is too generic")
        return v

    @model_validator(mode="after")
    def validate_high_severity(self):
        if self.severity in (
            SeverityLevel.CRITICAL,
            SeverityLevel.HIGH
        ):
            if len(self.recommendation) < 20:
                raise ValueError(
                    "High severity findings require detailed recommendations"
                )
        return self


class ImageMetadata(BaseModel):
    filename: str
    format: str
    width: int
    height: int
    size_bytes: int
    file_size: int
    color_mode: str


class AuditReport(BaseModel):
    resource: str

    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z"
    )

    agent_version: str = "1.0.0"

    image_metadata: Optional[ImageMetadata] = None

    total_findings: int
    findings: List[Finding]

    summary: str
    overall_severity: SeverityLevel
    analysis_confidence: int = Field(..., ge=0, le=100)

    principles_checked: List[DesignPrinciple] = []
    principles_with_issues: List[DesignPrinciple] = []

    @model_validator(mode="after")
    def validate_counts(self):
        if self.total_findings != len(self.findings):
            raise ValueError(
                f"Expected {self.total_findings} findings but got {len(self.findings)}"
            )
        return self


class AgentException(Exception):
    def __init__(
        self,
        error_code: str,
        message: str,
        detail: str | None = None,
        recoverable: bool = False,
        suggested_action: str | None = None,
    ):
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.detail = detail
        self.recoverable = recoverable
        self.suggested_action = suggested_action

class AgentError(BaseModel): 
    """Structured error returned when the agent fails.""" 
    error_code: str 
    message: str 
    detail: Optional[str] = None 
    timestamp: str = Field( default_factory=lambda: datetime.utcnow().isoformat() + "Z" ) 
    recoverable: bool = True 
    suggested_action: Optional[str] = None

class AgentError(Exception): 
    def __init__( self, error_code: str, message: str, detail: str | None = None, recoverable: bool = False, suggested_action: str | None = None, ): 
        super().__init__(message) 
        self.error_code = error_code 
        self.message = message 
        self.detail = detail 
        self.recoverable = recoverable 
        self.suggested_action = suggested_action