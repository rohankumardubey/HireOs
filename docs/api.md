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
- `GET /candidates/{candidate_id}`
- `POST /candidates/{candidate_id}/match-job/{job_id}`

## Interviews

- `POST /interviews/invite`
- `POST /interviews/{interview_id}/start`
- `GET /interviews/{interview_id}/next-question`
- `POST /interviews/{interview_id}/answers`
- `POST /interviews/{interview_id}/complete`
- `GET /interviews/{interview_id}/report`
- `POST /interviews/{interview_id}/decision`

## Reports

- `GET /reports`
- `GET /reports/{report_id}`
- `GET /reports/{report_id}/download`

## Analytics

- `GET /analytics/overview`
- `GET /analytics/jobs/{job_id}`
- `GET /analytics/model-quality`
- `GET /analytics/funnel`

## Health

- `GET /health`
- `GET /metrics`

