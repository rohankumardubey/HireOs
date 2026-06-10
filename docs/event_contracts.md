# Event Contracts

## Topics

- `hireos.company.created`
- `hireos.job.created`
- `hireos.resume.uploaded`
- `hireos.resume.parsed`
- `hireos.resume.redacted`
- `hireos.jd.parsed`
- `hireos.candidate.matched`
- `hireos.interview.invited`
- `hireos.interview.started`
- `hireos.question.generated`
- `hireos.answer.submitted`
- `hireos.answer.transcribed`
- `hireos.answer.scored`
- `hireos.followup.generated`
- `hireos.interview.completed`
- `hireos.report.generated`
- `hireos.recruiter.decision_made`
- `hireos.error.events`

## Envelope

```json
{
  "event_id": "uuid",
  "event_type": "answer_scored",
  "timestamp": "ISO-8601 UTC",
  "company_id": "uuid",
  "job_id": "uuid",
  "candidate_id": "uuid",
  "interview_id": "uuid",
  "actor_id": "uuid",
  "actor_type": "candidate|recruiter|system",
  "source": "hireos-ai",
  "schema_version": "1.0",
  "payload": {}
}
```

## Delivery model

- Preferred: Kafka/Redpanda
- Fallback: append JSON lines to `data/events/hireos-events.jsonl`
- Stored outbox metadata: `events_outbox`

## MVP metrics path

- Local consumer skeleton: [backend/app/workers/analytics_consumer.py](/Users/dubeyroh/Library/CloudStorage/OneDrive-TheStarsGroup/Desktop/HireOs/backend/app/workers/analytics_consumer.py)
- Kafka topic bootstrap: [infra/kafka/create-topics.sh](/Users/dubeyroh/Library/CloudStorage/OneDrive-TheStarsGroup/Desktop/HireOs/infra/kafka/create-topics.sh)
- Flink skeleton: [infra/flink/HireOsMetricsJob.java](/Users/dubeyroh/Library/CloudStorage/OneDrive-TheStarsGroup/Desktop/HireOs/infra/flink/HireOsMetricsJob.java)
