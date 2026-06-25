# API

Base path: `/api/v1`

## Auth

- `POST /auth/signup`
- `POST /auth/login`
- `GET /auth/me`

## Companies

- `GET /companies/me`
- `PATCH /companies/me`

## Jobs

- `POST /jobs`
- `GET /jobs`
- `GET /jobs/{job_id}`
- `PATCH /jobs/{job_id}`
- `POST /jobs/{job_id}/parse`
- `GET /jobs/{job_id}/candidates`
- `GET /jobs/{job_id}/ranking`

## Candidates

- `POST /candidates`
- `POST /candidates/upload-resume`
- `GET /candidates`
- `GET /candidates/calibration-queue`
- `GET /candidates/calibration-queue/reminders/preview`
- `POST /candidates/calibration-queue/reminders/run`
- `GET /candidates/{candidate_id}`
- `PATCH /candidates/{candidate_id}/calibration-case/{job_id}`
- `POST /candidates/{candidate_id}/match-job/{job_id}`

## Interviews

- `POST /interviews/invite`
- `POST /interviews/{interview_id}/send-email`
- `GET /interviews/{interview_id}/email-deliveries`
- `GET /interviews/reminders/preview`
- `POST /interviews/reminders/run`
- `POST /interviews/{interview_id}/start`
- `GET /interviews/{interview_id}/next-question`
- `POST /interviews/{interview_id}/answers`
- `POST /interviews/{interview_id}/complete`
- `GET /interviews/{interview_id}/report`
- `POST /interviews/{interview_id}/decision`
- `GET /interviews/{interview_id}/hiring-manager-feedback`
- `POST /interviews/{interview_id}/hiring-manager-feedback`
- `GET /interviews/{interview_id}/ats-exports`
- `POST /interviews/{interview_id}/export-ats`

## Integrations

- `GET /integrations/google/status`
- `POST /integrations/google/connect`
- `DELETE /integrations/google`
- `GET /integrations/zoom/status`
- `POST /integrations/zoom/connect`
- `DELETE /integrations/zoom`
- `GET /integrations/ats-webhook/status`
- `PATCH /integrations/ats-webhook`
- `POST /integrations/ats-webhook/test`

## Reports

- `GET /reports`
- `GET /reports/{report_id}`
- `GET /reports/{report_id}/download`

## Analytics

- `GET /analytics/overview`
- `GET /analytics/jobs/{job_id}`
- `GET /analytics/model-quality`
- `GET /analytics/funnel`
- `GET /analytics/responsible-ai`

## Model quality evaluations

- `POST /evaluations/runs`
- `GET /evaluations/runs`
- `GET /evaluations/runs/{run_id}`

## Health

- `GET /health`
- `GET /metrics`
