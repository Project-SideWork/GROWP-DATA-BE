from __future__ import annotations

from dataclasses import dataclass

from app.schemas.recommendation import ApplicantDataset, RecommendationResult
from app.services.recommendation import analyze_applicants


class CrewEvaluationError(ValueError):
    """Raised when an agent finds an invalid evaluation input or output."""


@dataclass(frozen=True)
class DataQualityReport:
    target_id: int
    applicant_count: int
    missing_application_ids: int
    duplicate_application_ids: tuple[int, ...]


class DataQualityAgent:
    """Checks whether the backend dataset is safe to evaluate."""

    role = "recruitment-data-quality-analyst"

    def inspect(self, dataset: ApplicantDataset) -> DataQualityReport:
        application_ids = [
            applicant.application_id
            for applicant in dataset.applicants
            if applicant.application_id is not None
        ]
        duplicates = tuple(
            sorted(
                application_id
                for application_id in set(application_ids)
                if application_ids.count(application_id) > 1
            )
        )
        if duplicates:
            raise CrewEvaluationError(
                f"Duplicate application IDs for target {dataset.target.target_id}: {duplicates}"
            )

        return DataQualityReport(
            target_id=dataset.target.target_id,
            applicant_count=len(dataset.applicants),
            missing_application_ids=sum(
                applicant.application_id is None for applicant in dataset.applicants
            ),
            duplicate_application_ids=duplicates,
        )


class ApplicantEvaluationAgent:
    """Scores applicants with the project's deterministic recommendation engine."""

    role = "applicant-fit-evaluator"

    def evaluate(self, dataset: ApplicantDataset) -> RecommendationResult:
        return analyze_applicants(dataset)


class EvaluationReviewAgent:
    """Reviews scoring output before it can be delivered to the backend."""

    role = "evaluation-quality-reviewer"

    @staticmethod
    def _summary(result: RecommendationResult, index: int) -> str:
        recommendation = result.recommendations[index]
        parts = [
            f"판정: {recommendation.recommendation}",
            f"최종 점수: {recommendation.final_score:.2f}",
            f"신뢰도: {recommendation.confidence:.2f}",
            "사람 검토: 필요" if recommendation.requires_human_review else "사람 검토: 불필요",
        ]
        if recommendation.strengths:
            parts.append(f"강점: {', '.join(recommendation.strengths)}")
        if recommendation.concerns:
            parts.append(f"검토사항: {', '.join(recommendation.concerns)}")
        return " | ".join(parts)[:2000]

    def review(
        self,
        dataset: ApplicantDataset,
        quality: DataQualityReport,
        result: RecommendationResult,
    ) -> RecommendationResult:
        if result.target_id != dataset.target.target_id:
            raise CrewEvaluationError("Evaluation target ID does not match the input dataset")
        if result.target_type != dataset.target.target_type:
            raise CrewEvaluationError("Evaluation target type does not match the input dataset")
        if len(result.recommendations) != quality.applicant_count:
            raise CrewEvaluationError("Evaluation result does not contain every applicant")

        scores = [recommendation.final_score for recommendation in result.recommendations]
        if scores != sorted(scores, reverse=True):
            raise CrewEvaluationError("Applicant recommendations are not sorted by score")

        reviewed_recommendations = [
            recommendation.model_copy(update={"review_summary": self._summary(result, index)})
            for index, recommendation in enumerate(result.recommendations)
        ]
        return result.model_copy(update={"recommendations": reviewed_recommendations})
