from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app.api.router import api_router
from app.clients.kafka import KafkaProducerManager
from app.core.config import get_settings
from app.core.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    app.state.http_client = httpx.AsyncClient(
        base_url=str(settings.backend_base_url),
        timeout=settings.request_timeout_seconds,
    )
    app.state.kafka_producer = None

    if settings.kafka_enabled:
        kafka_producer = KafkaProducerManager(settings)
        await kafka_producer.start()
        app.state.kafka_producer = kafka_producer

    try:
        yield
    finally:
        if app.state.kafka_producer is not None:
            await app.state.kafka_producer.stop()
        await app.state.http_client.aclose()


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(api_router, prefix="/api/v1")
