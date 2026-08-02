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

import httpx
from aiokafka import AIOKafkaConsumer
from pydantic import PositiveInt, TypeAdapter, ValidationError

from app.clients.recruitment import RecruitmentDataClient
from app.core.config import get_settings
from app.core.logging import configure_logging

LOGGER = logging.getLogger(__name__)
PROJECT_TOPIC = "project.recruit.ends"
STUDY_TOPIC = "study.recruit.ends"

EventHandler = Callable[[list[int]], Awaitable[None]]
ID_LIST_ADAPTER = TypeAdapter(list[PositiveInt])


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
                LOGGER.info(
                    "Kafka event received topic=%s partition=%s offset=%s key=%r payload=%s",
                    message.topic,
                    message.partition,
                    message.offset,
                    message.key,
                    message.value,
                )
                try:
                    entity_ids = ID_LIST_ADAPTER.validate_python(message.value)
                except ValidationError:
                    LOGGER.exception("Ignoring invalid ID array on %s", message.topic)
                    await self._consumer.commit()
                    continue
                try:
                    await self._handlers[message.topic](entity_ids)
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
