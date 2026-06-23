#!/usr/bin/env bash

set -euo pipefail

TOPICS=(
  "hireos.company.created"
  "hireos.job.created"
  "hireos.resume.uploaded"
  "hireos.resume.parsed"
  "hireos.jd.parsed"
  "hireos.candidate.matched"
  "hireos.interview.invited"
  "hireos.interview.started"
  "hireos.question.generated"
  "hireos.answer.submitted"
  "hireos.answer.transcribed"
  "hireos.answer.scored"
  "hireos.followup.generated"
  "hireos.interview.completed"
  "hireos.report.generated"
  "hireos.recruiter.decision_made"
  "hireos.hiring_manager.feedback_recorded"
  "hireos.calibration.case_updated"
  "hireos.calibration.reminder_sent"
  "hireos.evaluation.run_started"
  "hireos.evaluation.run_completed"
  "hireos.evaluation.regression_detected"
  "hireos.error.events"
)

for topic in "${TOPICS[@]}"; do
  docker compose exec redpanda rpk topic create "$topic" --brokers redpanda:9092 || true
done

echo "HireOS topics created or already present."
