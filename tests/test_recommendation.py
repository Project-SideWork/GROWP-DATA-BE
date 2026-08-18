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


def test_analyzes_anonymous_club_applicant_without_user_profile() -> None:
    dataset = ApplicantDataset.model_validate(
        {
            "target": {"targetId": 1, "targetType": "CLUB", "title": "동아리 모집"},
            "applicants": [
                {
                    "applicationId": 10,
                    "userId": None,
                    "profileId": None,
                    "nickname": "비회원 지원자",
                    "status": "UNREAD",
                    "answers": [
                        {
                            "questionId": 1,
                            "question": "지원 동기는?",
                            "answer": "동아리 활동을 통해 협업 경험을 쌓고 함께 성장하고 싶습니다.",
                        }
                    ],
                }
            ],
        }
    )

    recommendation = analyze_applicants(dataset).recommendations[0]

    assert recommendation.application_id == 10
    assert recommendation.user_id is None
    assert recommendation.profile_id is None
    assert recommendation.recommendation == "INSUFFICIENT_DATA"


def test_study_answer_is_evaluated_with_study_specific_weights() -> None:
    dataset = ApplicantDataset.model_validate(
        {
            "target": {"targetId": 2, "targetType": "STUDY", "title": "알고리즘"},
            "applicants": [
                {
                    "applicationId": 20,
                    "nickname": "학습자",
                    "status": "ACCEPTED",
                    "answers": [
                        {
                            "questionId": 1,
                            "question": "학습 목표는?",
                            "answer": (
                                "매주 문제 풀이 과정을 공유하고 서로의 접근법을 비교하며 "
                                "성장하고 싶습니다."
                            ),
                        }
                    ],
                }
            ],
        }
    )

    recommendation = analyze_applicants(dataset).recommendations[0]

    assert recommendation.confidence == 0.55
    assert recommendation.recommendation != "INSUFFICIENT_DATA"
    assert recommendation.recommendation != "NOT_ELIGIBLE"


def test_club_uses_motivation_and_answers_instead_of_project_criteria() -> None:
    dataset = ApplicantDataset.model_validate(
        {
            "target": {"targetId": 3, "targetType": "CLUB", "title": "개발 동아리"},
            "applicants": [
                {
                    "applicationId": 30,
                    "nickname": "지원자",
                    "status": "REJECTED",
                    "motivation": (
                        "팀원들과 꾸준히 프로젝트를 만들며 협업 역량과 개발 역량을 "
                        "함께 키우고 싶습니다."
                    ),
                    "answers": [
                        {
                            "questionId": 1,
                            "question": "하고 싶은 활동은?",
                            "answer": (
                                "사용자 문제를 탐색하고 작은 기능부터 함께 구현해 배포까지 "
                                "경험하고 싶습니다."
                            ),
                        }
                    ],
                }
            ],
        }
    )

    recommendation = analyze_applicants(dataset).recommendations[0]

    assert recommendation.confidence == 0.8
    assert recommendation.recommendation != "INSUFFICIENT_DATA"
    assert recommendation.recommendation != "NOT_ELIGIBLE"
    assert set(recommendation.score_details) == {"motivationScore", "interviewScore"}
