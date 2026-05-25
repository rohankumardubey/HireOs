from __future__ import annotations

import json
from pathlib import Path

from app.core.config import settings


def read_local_event_log() -> list[dict]:
    events_file = Path(settings.events_dir) / "hireos-events.jsonl"
    if not events_file.exists():
        return []

    with events_file.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def summarize_events() -> dict:
    events = read_local_event_log()
    interviews_started = sum(1 for event in events if event["event_type"] == "interview.started")
    interviews_completed = sum(1 for event in events if event["event_type"] == "interview.completed")
    answer_scored = sum(1 for event in events if event["event_type"] == "answer.scored")
    return {
        "events_seen": len(events),
        "interviews_started": interviews_started,
        "interviews_completed": interviews_completed,
        "answer_scored": answer_scored,
    }


if __name__ == "__main__":
    print(json.dumps(summarize_events(), indent=2))
