from app.schemas.recommendation import ApplicantDataset
from app.services.recommendation import analyze_applicants


def test_analyze_applicants_scores_and_orders_candidates() -> None:
    dataset = ApplicantDataset.model_validate(
        {
            "target": {
                "targetId": 10,
                "targetType": "PROJECT",
                "title": "백엔드 프로젝트",
                "expectedWeeklyHours": 10,
                "activityMethod": "ONLINE",
                "positions": [
                    {
                        "positionId": 1,
                        "role": "BACKEND",
                        "requiredSkills": ["Java", "Spring"],
                        "preferredSkills": ["Kafka"],
                        "responsibilities": None,
                    }
                ],
            },
            "applicants": [
                {
                    "applicationId": 100,
                    "userId": 1,
                    "profileId": 11,
                    "nickname": "적합",
                    "appliedPositionId": 1,
                    "appliedRole": "BACKEND",
                    "status": "UNREAD",
                    "introduction": None,
                    "motivation": None,
                    "skills": ["java", "Spring", "Kafka"],
                    "availableWeeklyHours": 12,
                    "preferredActivityMethod": "ONLINE",
                    "experiences": [
                        {"title": "API 서버", "skills": ["Spring"], "durationMonths": 12}
                    ],
                    "answers": [
                        {
                            "questionId": 1,
                            "question": "협업 경험은?",
                            "answer": "충돌 원인을 문서화하고 팀과 대안을 비교해 합의했습니다.",
                            "evaluationScore": 90,
                            "evaluationConfidence": 0.9,
                        }
                    ],
                },
                {
                    "applicationId": 200,
                    "userId": 2,
                    "profileId": 22,
                    "nickname": "검토",
                    "appliedPositionId": 1,
                    "appliedRole": "BACKEND",
                    "status": "READ",
                    "skills": ["Java"],
                    "availableWeeklyHours": 5,
                    "preferredActivityMethod": "OFFLINE",
                    "answers": [],
                },
            ],
        }
    )

    result = analyze_applicants(dataset)

    assert [item.application_id for item in result.recommendations] == [100, 200]
    assert result.recommendations[0].final_score > result.recommendations[1].final_score
    assert result.recommendations[0].score_details["requiredSkillMatch"].score == 100
    assert result.recommendations[1].score_details["requiredSkillMatch"].score == 50


def test_missing_categories_are_excluded_instead_of_scored_zero() -> None:
    dataset = ApplicantDataset.model_validate(
        {
            "target": {"targetId": 1, "targetType": "STUDY", "title": "알고리즘"},
            "applicants": [
                {
                    "applicationId": 1,
                    "userId": 1,
                    "profileId": 1,
                    "nickname": "지원자",
                    "status": "UNREAD",
                }
            ],
        }
    )

    recommendation = analyze_applicants(dataset).recommendations[0]

    assert recommendation.final_score == 0
    assert recommendation.confidence == 0
    assert recommendation.recommendation == "INSUFFICIENT_DATA"
    assert recommendation.requires_human_review is True
