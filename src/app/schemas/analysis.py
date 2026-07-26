from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AnalysisRequest(BaseModel):
    job_id: UUID = Field(default_factory=uuid4)
    records: list[dict[str, Any]] = Field(min_length=1, max_length=100_000)


class NumericSummary(BaseModel):
    count: int
    mean: float
    minimum: float
    maximum: float


class AnalysisResult(BaseModel):
    job_id: UUID
    row_count: int
    numeric_columns: dict[str, NumericSummary]
    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PipelineResponse(BaseModel):
    status: Literal["delivered"]
    result: AnalysisResult

