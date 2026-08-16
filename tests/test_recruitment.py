import logging

import httpx
import respx
from _pytest.logging import LogCaptureFixture

from app.clients.kafka_consumer import _analyze_payloads, _normalize_dataset, build_event_handlers
from app.clients.recruitment import RecruitmentDataClient
from app.core.config import Settings


def dataset(target_id: int, target_type: str) -> dict[str, object]:
    return {
        "result": {
            "target": {
                "targetId": target_id,
                "targetType": target_type,
                "title": "모집",
            },
            "applicants": [],
        }
    }


@respx.mock
async def test_project_handler_fetches_each_id() -> None:
    first = respx.get(
        "http://localhost:8080/api/v1/analytics/projects/10/evaluation-dataset"
    ).mock(
        return_value=httpx.Response(200, json=dataset(10, "PROJECT"))
    )
    second = respx.get(
        "http://localhost:8080/api/v1/analytics/projects/20/evaluation-dataset"
    ).mock(
        return_value=httpx.Response(200, json=dataset(20, "PROJECT"))
    )
    settings = Settings(delivery_max_attempts=1)

    async with httpx.AsyncClient(base_url=str(settings.backend_base_url)) as http_client:
        client = RecruitmentDataClient(http_client, settings)
        project_handler, _, _ = build_event_handlers(client)
        await project_handler([10, 20])

    assert first.call_count == 1
    assert second.call_count == 1


@respx.mock
async def test_study_handler_fetches_each_id() -> None:
    first = respx.get(
        "http://localhost:8080/api/v1/analytics/studies/1/evaluation-dataset"
    ).mock(
        return_value=httpx.Response(200, json=dataset(1, "STUDY"))
    )
    second = respx.get(
        "http://localhost:8080/api/v1/analytics/studies/2/evaluation-dataset"
    ).mock(
        return_value=httpx.Response(200, json=dataset(2, "STUDY"))
    )
    settings = Settings(delivery_max_attempts=1)

    async with httpx.AsyncClient(base_url=str(settings.backend_base_url)) as http_client:
        client = RecruitmentDataClient(http_client, settings)
        _, study_handler, _ = build_event_handlers(client)
        await study_handler([1, 2])

    assert first.call_count == 1
    assert second.call_count == 1


@respx.mock
async def test_club_handler_fetches_each_id() -> None:
    first = respx.get(
        "http://localhost:8080/api/v1/analytics/clubs/3/evaluation-dataset"
    ).mock(return_value=httpx.Response(200, json=dataset(3, "CLUB")))
    second = respx.get(
        "http://localhost:8080/api/v1/analytics/clubs/4/evaluation-dataset"
    ).mock(return_value=httpx.Response(200, json=dataset(4, "CLUB")))
    settings = Settings(delivery_max_attempts=1)

    async with httpx.AsyncClient(base_url=str(settings.backend_base_url)) as http_client:
        client = RecruitmentDataClient(http_client, settings)
        _, _, club_handler = build_event_handlers(client)
        await club_handler([3, 4])

    assert first.call_count == 1
    assert second.call_count == 1


def test_normalizes_current_study_backend_response() -> None:
    normalized = _normalize_dataset(
        {
            "studyId": 7,
            "clubId": 3,
            "studyTitle": "알고리즘 스터디",
            "applicants": [
                {
                    "userId": 10,
                    "nickname": "지원자",
                    "profileId": 20,
                    "status": "UNREAD",
                    "answerSummary": "문제 풀이 과정을 함께 설명하고 학습하고 싶습니다.",
                }
            ],
        },
        "study",
    )

    assert normalized["target"]["targetId"] == 7
    assert normalized["target"]["targetType"] == "STUDY"
    assert normalized["applicants"][0]["applicationId"] is None
    assert normalized["applicants"][0]["answers"][0]["answer"]


def test_logs_all_applicants_in_score_order(caplog: LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        _analyze_payloads(
            [
                {
                    "target": {
                        "targetId": 1,
                        "targetType": "CLUB",
                        "title": "동아리 모집",
                    },
                    "applicants": [
                        {
                            "applicationId": 1,
                            "userId": None,
                            "profileId": None,
                            "nickname": "첫째",
                            "status": "UNREAD",
                        },
                        {
                            "applicationId": 2,
                            "userId": None,
                            "profileId": None,
                            "nickname": "둘째",
                            "status": "UNREAD",
                        },
                    ],
                }
            ],
            "club",
        )

    ranking_messages = [
        record.message
        for record in caplog.records
        if record.message.startswith("Applicant ranking")
    ]
    assert len(ranking_messages) == 2
    assert "rank=1 application_id=1" in ranking_messages[0]
    assert "rank=2 application_id=2" in ranking_messages[1]
