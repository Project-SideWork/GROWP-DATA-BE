import httpx
import respx

from app.clients.kafka_consumer import build_event_handlers
from app.clients.recruitment import RecruitmentDataClient
from app.core.config import Settings


@respx.mock
async def test_project_handler_fetches_each_id() -> None:
    first = respx.get("http://localhost:8080/api/v1/analytics/projects/10/applicants").mock(
        return_value=httpx.Response(200, json={"id": 10})
    )
    second = respx.get("http://localhost:8080/api/v1/analytics/projects/20/applicants").mock(
        return_value=httpx.Response(200, json={"id": 20})
    )
    settings = Settings(delivery_max_attempts=1)

    async with httpx.AsyncClient(base_url=str(settings.backend_base_url)) as http_client:
        client = RecruitmentDataClient(http_client, settings)
        project_handler, _ = build_event_handlers(client)
        await project_handler([10, 20])

    assert first.call_count == 1
    assert second.call_count == 1


@respx.mock
async def test_study_handler_fetches_each_id() -> None:
    first = respx.get("http://localhost:8080/api/v1/analytics/studies/1/applicants").mock(
        return_value=httpx.Response(200, json={"id": 1})
    )
    second = respx.get("http://localhost:8080/api/v1/analytics/studies/2/applicants").mock(
        return_value=httpx.Response(200, json={"id": 2})
    )
    settings = Settings(delivery_max_attempts=1)

    async with httpx.AsyncClient(base_url=str(settings.backend_base_url)) as http_client:
        client = RecruitmentDataClient(http_client, settings)
        _, study_handler = build_event_handlers(client)
        await study_handler([1, 2])

    assert first.call_count == 1
    assert second.call_count == 1
