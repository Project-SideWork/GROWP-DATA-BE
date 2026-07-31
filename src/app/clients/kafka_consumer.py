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

from aiokafka import AIOKafkaConsumer

from app.core.config import get_settings
from app.core.logging import configure_logging

LOGGER = logging.getLogger(__name__)
PROJECT_TOPIC = "project.recruit.ends"
STUDY_TOPIC = "study.recruit.ends"

EventHandler = Callable[[dict[str, Any]], Awaitable[None]]


async def handle_project_event(payload: dict[str, Any]) -> None:
    """Handle a project recruitment-finished event.

    Replace this function with the application action required for the event.
    """
    LOGGER.info("project recruitment ended: %s", payload)


async def handle_study_event(payload: dict[str, Any]) -> None:
    """Handle a study recruitment-finished event."""
    LOGGER.info("study recruitment ended: %s", payload)


class RecruitmentEventConsumer:
    def __init__(
        self,
        project_handler: EventHandler = handle_project_event,
        study_handler: EventHandler = handle_study_event,
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
                if not isinstance(message.value, dict):
                    LOGGER.warning("Ignoring non-object payload on %s", message.topic)
                    await self._consumer.commit()
                    continue
                try:
                    await self._handlers[message.topic](message.value)
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
    await RecruitmentEventConsumer().run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
