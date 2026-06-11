"""Pydantic models shared across the API."""

from enum import Enum

from pydantic import BaseModel


class ApplicationRecord(BaseModel):
    """A label application as it would come from COLA (mocked for the prototype)."""

    application_number: str
    brand_name: str
    class_type: str
    alcohol_content: str
    net_contents: str
    applicant: str


class FieldStatus(str, Enum):
    MATCH = "match"
    MISMATCH = "mismatch"
    NEEDS_REVIEW = "needs_review"


class FieldResult(BaseModel):
    """Comparison result for a single label field."""

    field: str
    label: str  # human-readable field name for the UI
    status: FieldStatus
    application_value: str
    extracted_value: str | None
    note: str | None = None


class VerificationResponse(BaseModel):
    application_number: str
    results: list[FieldResult]
    summary: str
    elapsed_seconds: float


class ExtractedLabel(BaseModel):
    """Fields the AI extracted from the label image. None = not found / unreadable."""

    brand_name: str | None = None
    class_type: str | None = None
    alcohol_content: str | None = None
    net_contents: str | None = None
    government_warning: str | None = None
    readable: bool = True
    notes: str | None = None
