from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=lambda value: _to_camel(value), populate_by_name=True)


def _to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class TargetType(StrEnum):
    PROJECT = "PROJECT"
    STUDY = "STUDY"
    CLUB = "CLUB"


class Experience(CamelModel):
    title: str = ""
    role: str = ""
    description: str = ""
    skills: list[str] = Field(default_factory=list)
    duration_months: int | None = Field(default=None, ge=0)


class Portfolio(CamelModel):
    title: str = ""
    description: str = ""
    url: str | None = None
    skills: list[str] = Field(default_factory=list)


class QuestionAnswer(CamelModel):
    question_id: int
    question: str
    evaluation_criterion: str | None = None
    answer: str = ""
    # AI 평가기가 먼저 평가한 경우 0~100 점과 신뢰도를 함께 전달한다.
    evaluation_score: float | None = Field(default=None, ge=0, le=100)
    evaluation_confidence: float | None = Field(default=None, ge=0, le=1)


class Applicant(CamelModel):
    application_id: int | None = None
    user_id: int | None = None
    profile_id: int | None = None
    nickname: str
    applied_position_id: int | None = None
    applied_role: str | None = None
    status: str
    applied_at: datetime | None = None
    introduction: str | None = None
    skills: list[str] = Field(default_factory=list)
    experiences: list[Experience] = Field(default_factory=list)
    portfolios: list[Portfolio] = Field(default_factory=list)
    available_weekly_hours: int | None = Field(default=None, ge=0)
    preferred_activity_method: str | None = None
    activity_region: str | None = None
    motivation: str | None = None
    answers: list[QuestionAnswer] = Field(default_factory=list)


class RecruitmentPosition(CamelModel):
    position_id: int
    role: str
    recruitment_count: int | None = Field(default=None, ge=0)
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    responsibilities: str | None = None
    required_experience: str | None = None


class RecommendationTarget(CamelModel):
    target_id: int
    target_type: TargetType
    club_id: int | None = None
    title: str
    description: str = ""
    positions: list[RecruitmentPosition] = Field(default_factory=list)
    expected_weekly_hours: int | None = Field(default=None, ge=0)
    activity_method: str | None = None
    activity_region: str | None = None
    activity_start_at: datetime | None = None
    activity_end_at: datetime | None = None


class ApplicantDataset(CamelModel):
    target: RecommendationTarget
    applicants: list[Applicant]


class ScoreDetail(CamelModel):
    score: float = Field(ge=0, le=100)
    weight: float = Field(gt=0, le=1)
    evidence: list[str]


class ApplicantRecommendation(CamelModel):
    application_id: int | None = None
    user_id: int | None = None
    profile_id: int | None = None
    nickname: str
    final_score: float = Field(ge=0, le=100)
    recommendation: str
    confidence: float = Field(ge=0, le=1)
    score_details: dict[str, ScoreDetail]
    strengths: list[str]
    concerns: list[str]
    requires_human_review: bool


class RecommendationResult(CamelModel):
    target_id: int
    target_type: TargetType
    recommendations: list[ApplicantRecommendation]
    analysis_version: str = "rule-v1"
    analyzed_at: datetime
