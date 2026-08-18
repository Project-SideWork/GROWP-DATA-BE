import pytest

from app.crew import RecruitmentEvaluationCrew
from app.crew.agents import CrewEvaluationError
from app.schemas.recommendation import ApplicantDataset


def dataset(*, duplicate_ids: bool = False) -> ApplicantDataset:
    return ApplicantDataset.model_validate(
        {
            "target": {
                "targetId": 10,
                "targetType": "PROJECT",
                "title": "백엔드 프로젝트",
                "positions": [
                    {
                        "positionId": 1,
                        "role": "BACKEND",
                        "requiredSkills": ["Java", "Spring"],
                    }
                ],
            },
            "applicants": [
                {
                    "applicationId": 100,
                    "nickname": "적합",
                    "status": "UNREAD",
                    "appliedPositionId": 1,
                    "appliedRole": "BACKEND",
                    "skills": ["Java", "Spring"],
                },
                {
                    "applicationId": 100 if duplicate_ids else 200,
                    "nickname": "검토",
                    "status": "READ",
                    "appliedPositionId": 1,
                    "appliedRole": "BACKEND",
                    "skills": ["Java"],
                },
            ],
        }
    )


def test_crew_inspects_evaluates_and_reviews_applicants() -> None:
    result = RecruitmentEvaluationCrew().kickoff(dataset())

    assert result.target_id == 10
    assert [item.application_id for item in result.recommendations] == [100, 200]
    assert result.recommendations[0].final_score >= result.recommendations[1].final_score
    assert "판정:" in result.recommendations[0].review_summary
    assert "최종 점수:" in result.recommendations[0].review_summary
    assert "신뢰도:" in result.recommendations[0].review_summary
    assert result.recommendations[0].model_dump(by_alias=True)["reviewSummary"]


def test_crew_rejects_duplicate_application_ids() -> None:
    with pytest.raises(CrewEvaluationError, match="Duplicate application IDs"):
        RecruitmentEvaluationCrew().kickoff(dataset(duplicate_ids=True))
