from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from kafka import KafkaProducer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import AuditLog, EventOutbox, EventStatus


class EventPublisher:
    def __init__(self) -> None:
        self.events_file = Path(settings.events_dir) / "hireos-events.jsonl"

    def publish(
        self,
        db: Session,
        *,
        event_type: str,
        topic_name: str,
        company_id: str | None = None,
        job_id: str | None = None,
        candidate_id: str | None = None,
        interview_id: str | None = None,
        actor_id: str | None = None,
        actor_type: str = "system",
        payload: dict | None = None,
    ) -> dict:
        envelope = {
            "event_id": str(uuid4()),
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "company_id": company_id,
            "job_id": job_id,
            "candidate_id": candidate_id,
            "interview_id": interview_id,
            "actor_id": actor_id,
            "actor_type": actor_type,
            "source": "hireos-ai",
            "schema_version": "1.0",
            "payload": payload or {},
        }
        outbox = EventOutbox(event_type=event_type, topic_name=topic_name, envelope=envelope)
        db.add(outbox)
        status = EventStatus.fallback.value
        error_message = None
        if settings.enable_kafka:
            try:
                producer = KafkaProducer(
                    bootstrap_servers=settings.kafka_bootstrap_servers,
                    value_serializer=lambda value: json.dumps(value).encode("utf-8"),
                )
                producer.send(topic_name, envelope)
                producer.flush(5)
                status = EventStatus.delivered.value
            except Exception as exc:
                error_message = str(exc)
                status = EventStatus.fallback.value
        self.events_file.parent.mkdir(parents=True, exist_ok=True)
        with self.events_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(envelope) + "\n")
        outbox.status = status
        outbox.error_message = error_message
        return envelope


def log_audit(db: Session, actor_id: str | None, entity_type: str, entity_id: str, action: str, after_json: dict) -> None:
    db.add(
        AuditLog(
            actor_id=actor_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            after_json=after_json,
        )
    )

