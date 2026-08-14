from uuid import UUID

import pytest
from pydantic import ValidationError

from app.clients.kafka_consumer import parse_recruitment_event


def test_parse_recruitment_event_extracts_targets() -> None:
    event = parse_recruitment_event(
        {
            "eventId": "a654194d-c1a0-4adc-b1f1-b840b3a4ba11",
            "targets": [1, 2, 3],
        }
    )

    assert event.event_id == UUID("a654194d-c1a0-4adc-b1f1-b840b3a4ba11")
    assert event.targets == [1, 2, 3]


def test_parse_recruitment_event_rejects_invalid_targets() -> None:
    with pytest.raises(ValidationError):
        parse_recruitment_event(
            {
                "eventId": "a654194d-c1a0-4adc-b1f1-b840b3a4ba11",
                "targets": [0, -1],
            }
        )
