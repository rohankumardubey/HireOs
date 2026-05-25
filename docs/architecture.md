# Architecture

## Product shape

HireOS AI is intentionally split into:

- a recruiter-facing Next.js application
- a FastAPI domain backend
- a data/event layer that can run lightly in MVP mode and grow into streaming analytics later

## Request flow

1. Recruiters authenticate and operate inside a company workspace.
2. Jobs are created with structured metadata plus free-text descriptions.
3. Resume uploads are parsed into raw text, extracted fields, and candidate skill records.
4. The matching layer compares candidate capabilities against job requirements and produces explainable outputs.
5. Interviews are generated from role focus areas and candidate context.
6. Answer scoring stores question-level evidence, missing concepts, strengths, weaknesses, and follow-up suggestions.
7. Reports are generated for recruiter review.
8. Lifecycle events are emitted to Kafka or local JSONL for analytics processing.

## Service boundaries

- `frontend`: SaaS UI, recruiter workflow, candidate interview screen
- `backend/app/api/routes`: REST surface
- `backend/app/services/parsers.py`: job and resume parsing
- `backend/app/services/ai.py`: provider abstraction for OpenAI-compatible or Ollama flows
- `backend/app/services/scoring.py`: match logic, interview generation, answer scoring, report building
- `backend/app/services/events.py`: event outbox + fallback publisher
- `backend/app/services/analytics.py`: overview and model-quality queries

## Why this architecture works for MVP

- The system stays runnable with mock heuristics when no external AI key is present.
- Recruiter-critical paths are synchronous and easy to demo.
- Events, lakehouse assets, and Flink are scaffolded without blocking core product usage.
- Human review remains a first-class product concept instead of an afterthought.

