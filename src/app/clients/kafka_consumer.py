"""Consumers for project/study recruitment-finished events.

Run with ``python -m app.clients.kafka_consumer``.  Event-specific business
logic can be supplied by replacing ``handle_project_event`` and
``handle_study_event`` (or by composing :class:`RecruitmentEventConsumer`).
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

import httpx
from aiokafka import AIOKafkaConsumer
from pydantic import BaseModel, Field, PositiveInt, ValidationError

from app.clients.recruitment import RecruitmentDataClient
from app.core.config import get_settings
from app.core.logging import configure_logging

LOGGER = logging.getLogger(__name__)
PROJECT_TOPIC = "project.recruit.ends"
STUDY_TOPIC = "study.recruit.ends"

EventHandler = Callable[[list[int]], Awaitable[None]]


class RecruitmentEndedEvent(BaseModel):
    event_id: UUID = Field(alias="eventId")
    targets: list[PositiveInt]


def parse_recruitment_event(payload: Any) -> RecruitmentEndedEvent:
    return RecruitmentEndedEvent.model_validate(payload)


def build_event_handlers(client: RecruitmentDataClient) -> tuple[EventHandler, EventHandler]:
    async def handle_project_event(entity_ids: list[int]) -> None:
        results = await client.fetch_projects(entity_ids)
        LOGGER.info("Fetched %d project analysis payloads", len(results))

    async def handle_study_event(entity_ids: list[int]) -> None:
        results = await client.fetch_studies(entity_ids)
        LOGGER.info("Fetched %d study analysis payloads", len(results))

    return handle_project_event, handle_study_event


class RecruitmentEventConsumer:
    def __init__(
        self,
        project_handler: EventHandler,
        study_handler: EventHandler,
    ) -> None:
        settings = get_settings()
        self._consumer = AIOKafkaConsumer(
            PROJECT_TOPIC,
            STUDY_TOPIC,
            bootstrap_servers=settings.kafka_bootstrap_servers,
            group_id=settings.kafka_consumer_group_id,
            client_id=f"{settings.kafka_client_id}-consumer",
            enable_auto_commit=False,
            value_deserializer=lambda value: json.loads(value.decode("utf-8")),
            auto_offset_reset="earliest",
        )
        self._handlers: dict[str, EventHandler] = {
            PROJECT_TOPIC: project_handler,
            STUDY_TOPIC: study_handler,
        }

    async def run(self) -> None:
        await self._consumer.start()
        LOGGER.info("Kafka consumer started for %s, %s", PROJECT_TOPIC, STUDY_TOPIC)
        try:
            async for message in self._consumer:
                try:
                    event = parse_recruitment_event(message.value)
                except ValidationError as exc:
                    LOGGER.warning(
                        "Ignoring invalid recruitment event topic=%s partition=%s "
                        "offset=%s error=%s",
                        message.topic,
                        message.partition,
                        message.offset,
                        exc,
                    )
                    await self._consumer.commit()
                    continue
                LOGGER.info(
                    "Kafka event received topic=%s partition=%s offset=%s "
                    "event_id=%s target_count=%s",
                    message.topic,
                    message.partition,
                    message.offset,
                    event.event_id,
                    len(event.targets),
                )
                try:
                    await self._handlers[message.topic](event.targets)
                except Exception:
                    LOGGER.exception(
                        "Kafka event handling failed topic=%s partition=%s offset=%s",
                        message.topic,
                        message.partition,
                        message.offset,
                    )
                    raise
                await self._consumer.commit()
                LOGGER.info(
                    "Kafka event handled and committed topic=%s partition=%s offset=%s",
                    message.topic,
                    message.partition,
                    message.offset,
                )
        finally:
            await self._consumer.stop()


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    headers = {}
    if settings.backend_api_key:
        headers["Authorization"] = f"Bearer {settings.backend_api_key}"

    async with httpx.AsyncClient(
        base_url=str(settings.backend_base_url),
        timeout=settings.request_timeout_seconds,
        headers=headers,
    ) as http_client:
        data_client = RecruitmentDataClient(http_client, settings)
        project_handler, study_handler = build_event_handlers(data_client)
        await RecruitmentEventConsumer(project_handler, study_handler).run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
