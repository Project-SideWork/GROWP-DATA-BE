from fastapi import APIRouter, Request

from app.core.config import get_settings

router = APIRouter()


@router.get("/health", summary="Liveness check")
async def health(request: Request) -> dict[str, str]:
    settings = get_settings()
    kafka_producer = request.app.state.kafka_producer
    if not settings.kafka_enabled:
        kafka_status = "disabled"
    elif kafka_producer is not None and kafka_producer.is_connected:
        kafka_status = "connected"
    else:
        kafka_status = "disconnected"

    return {"status": "ok", "kafka": kafka_status}
