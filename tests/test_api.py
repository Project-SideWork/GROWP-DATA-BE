import httpx
import respx
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


@respx.mock
def test_analysis_endpoint_delivers_result() -> None:
    delivery = respx.post("http://localhost:8080/api/v1/analysis-results").mock(
        return_value=httpx.Response(200)
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/analysis",
            json={"records": [{"amount": 100}, {"amount": 200}]},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "delivered"
    assert response.json()["result"]["numeric_columns"]["amount"]["mean"] == 150
    assert delivery.called


def test_health_reports_kafka_disabled_by_default() -> None:
    get_settings.cache_clear()

    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "kafka": "disabled"}
