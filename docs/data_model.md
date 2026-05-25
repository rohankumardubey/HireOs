# Data Model

## Core entities

- `companies`
- `users`
- `company_memberships`
- `jobs`
- `job_skills`
- `candidates`
- `candidate_skills`
- `candidate_resumes`
- `candidate_job_matches`
- `interviews`
- `interview_questions`
- `interview_answers`
- `answer_scores`
- `interview_reports`
- `recruiter_decisions`
- `audit_logs`
- `events_outbox`
- `usage_events`
- `analytics_daily_metrics`

## Design notes

- UUID strings are used as primary keys for portability across SQLite local demos and PostgreSQL deployments.
- Audit and event tables are first-class, not auxiliary.
- Candidate and job skills are normalized into dedicated tables for explainability and ranking logic.
- Match results and answer scores store explanations so the UI can show evidence instead of opaque numbers.

