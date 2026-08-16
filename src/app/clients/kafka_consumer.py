"""Consumers for project/study/club recruitment-finished events.

Run with ``python -m app.clients.kafka_consumer``.  Event-specific business
logic can be supplied by composing :class:`RecruitmentEventConsumer`.
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
from app.schemas.recommendation import ApplicantDataset
from app.services.recommendation import analyze_applicants

LOGGER = logging.getLogger(__name__)
PROJECT_TOPIC = "project.recruit.ends"
STUDY_TOPIC = "study.recruit.ends"
CLUB_TOPIC = "club.recruit.ends"

EventHandler = Callable[[list[int]], Awaitable[None]]


class RecruitmentEndedEvent(BaseModel):
    event_id: UUID = Field(alias="eventId")
    targets: list[PositiveInt]


def parse_recruitment_event(payload: Any) -> RecruitmentEndedEvent:
    return RecruitmentEndedEvent.model_validate(payload)


def build_event_handlers(
    client: RecruitmentDataClient,
) -> tuple[EventHandler, EventHandler, EventHandler]:
    async def handle_project_event(entity_ids: list[int]) -> None:
        payloads = await client.fetch_projects(entity_ids)
        _analyze_payloads(payloads, "project")

    async def handle_study_event(entity_ids: list[int]) -> None:
        payloads = await client.fetch_studies(entity_ids)
        _analyze_payloads(payloads, "study")

    async def handle_club_event(entity_ids: list[int]) -> None:
        payloads = await client.fetch_clubs(entity_ids)
        _analyze_payloads(payloads, "club")

    return handle_project_event, handle_study_event, handle_club_event


def _analyze_payloads(payloads: list[Any], entity_type: str) -> None:
    for payload in payloads:
        # Spring ApiResponse의 result와 본문 직접 응답을 모두 지원한다.
        raw_dataset = payload.get("result", payload) if isinstance(payload, dict) else payload
        raw_dataset = _normalize_dataset(raw_dataset, entity_type)
        dataset = ApplicantDataset.model_validate(raw_dataset)
        result = analyze_applicants(dataset)
        LOGGER.info(
            "Applicant analysis completed type=%s target_id=%s applicant_count=%s "
            "top_application_id=%s top_score=%s",
            entity_type,
            result.target_id,
            len(result.recommendations),
            result.recommendations[0].application_id if result.recommendations else None,
            result.recommendations[0].final_score if result.recommendations else None,
        )
        for rank, recommendation in enumerate(result.recommendations, start=1):
            LOGGER.info(
                "Applicant ranking type=%s target_id=%s rank=%s application_id=%s "
                "score=%s recommendation=%s confidence=%s human_review=%s",
                entity_type,
                result.target_id,
                rank,
                recommendation.application_id,
                recommendation.final_score,
                recommendation.recommendation,
                recommendation.confidence,
                recommendation.requires_human_review,
            )


def _normalize_dataset(payload: Any, entity_type: str) -> Any:
    """Convert the current legacy Spring DTO into the expanded analysis contract."""
    if not isinstance(payload, dict) or "target" in payload:
        return payload

    id_field = f"{entity_type}Id"
    title_field = f"{entity_type}Title"
    if id_field not in payload or "applicants" not in payload:
        return payload

    applicants: list[dict[str, Any]] = []
    for raw_applicant in payload["applicants"]:
        applicant = dict(raw_applicant)
        # 현재 DTO에는 applicationId가 없다. userId로 대체하면 다른 지원 건을
        # 갱신할 위험이 있으므로 누락 상태를 그대로 유지한다.
        applicant.setdefault("applicationId", None)
        if entity_type == "study" and applicant.get("answerSummary"):
            applicant["answers"] = [
                {
                    "questionId": 0,
                    "question": "지원서 답변 요약",
                    "evaluationCriterion": "APPLICATION_SUMMARY",
                    "answer": applicant["answerSummary"],
                }
            ]
        applicants.append(applicant)

    return {
        "target": {
            "targetId": payload[id_field],
            "targetType": entity_type.upper(),
            "clubId": payload.get("clubId"),
            "title": payload.get(title_field, ""),
        },
        "applicants": applicants,
    }


class RecruitmentEventConsumer:
    def __init__(
        self,
        project_handler: EventHandler,
        study_handler: EventHandler,
        club_handler: EventHandler,
    ) -> None:
        settings = get_settings()
        self._consumer = AIOKafkaConsumer(
            PROJECT_TOPIC,
            STUDY_TOPIC,
            CLUB_TOPIC,
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
            CLUB_TOPIC: club_handler,
        }

    async def run(self) -> None:
        await self._consumer.start()
        LOGGER.info(
            "Kafka consumer started for %s, %s, %s",
            PROJECT_TOPIC,
            STUDY_TOPIC,
            CLUB_TOPIC,
        )
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
        project_handler, study_handler, club_handler = build_event_handlers(data_client)
        await RecruitmentEventConsumer(project_handler, study_handler, club_handler).run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
