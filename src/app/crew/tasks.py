from __future__ import annotations

from dataclasses import dataclass

from app.crew.agents import (
    ApplicantEvaluationAgent,
    DataQualityAgent,
    DataQualityReport,
    EvaluationReviewAgent,
)
from app.schemas.recommendation import ApplicantDataset, RecommendationResult


@dataclass(frozen=True)
class InspectDatasetTask:
    agent: DataQualityAgent

    def execute(self, dataset: ApplicantDataset) -> DataQualityReport:
        return self.agent.inspect(dataset)


@dataclass(frozen=True)
class EvaluateApplicantsTask:
    agent: ApplicantEvaluationAgent

    def execute(self, dataset: ApplicantDataset) -> RecommendationResult:
        return self.agent.evaluate(dataset)


@dataclass(frozen=True)
class ReviewEvaluationTask:
    agent: EvaluationReviewAgent

    def execute(
        self,
        dataset: ApplicantDataset,
        quality: DataQualityReport,
        result: RecommendationResult,
    ) -> RecommendationResult:
        return self.agent.review(dataset, quality, result)
