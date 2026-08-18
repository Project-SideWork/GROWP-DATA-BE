from __future__ import annotations

import logging

from app.crew.agents import ApplicantEvaluationAgent, DataQualityAgent, EvaluationReviewAgent
from app.crew.tasks import EvaluateApplicantsTask, InspectDatasetTask, ReviewEvaluationTask
from app.schemas.recommendation import ApplicantDataset, RecommendationResult

LOGGER = logging.getLogger(__name__)


class RecruitmentEvaluationCrew:
    """Runs recruitment evaluation agents in a controlled sequential workflow."""

    def __init__(self) -> None:
        self._inspect_task = InspectDatasetTask(DataQualityAgent())
        self._evaluate_task = EvaluateApplicantsTask(ApplicantEvaluationAgent())
        self._review_task = ReviewEvaluationTask(EvaluationReviewAgent())

    def kickoff(self, dataset: ApplicantDataset) -> RecommendationResult:
        LOGGER.info(
            "Evaluation crew started target_type=%s target_id=%s applicants=%s",
            dataset.target.target_type,
            dataset.target.target_id,
            len(dataset.applicants),
        )
        quality = self._inspect_task.execute(dataset)
        result = self._evaluate_task.execute(dataset)
        reviewed = self._review_task.execute(dataset, quality, result)
        LOGGER.info(
            "Evaluation crew completed target_type=%s target_id=%s "
            "recommendations=%s missing_application_ids=%s",
            reviewed.target_type,
            reviewed.target_id,
            len(reviewed.recommendations),
            quality.missing_application_ids,
        )
        return reviewed
