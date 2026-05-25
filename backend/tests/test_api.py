from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from fastapi.testclient import TestClient

import app.main as main_module
from app.api.routes import auth as auth_route
from app.api.routes import interviews as interviews_route
import app.services.ats_webhooks as ats_webhooks_service
from app.db.models import Interview
from app.db.session import SessionLocal, engine, init_db


def test_health() -> None:
    init_db()
    client = TestClient(main_module.app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_signup_and_login() -> None:
    client = TestClient(main_module.app)
    unique_email = f"test+{uuid4().hex[:8]}@hireos.ai"
    unique_company = f"Test Co {uuid4().hex[:6]}"
    signup = client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "Test Recruiter",
            "email": unique_email,
            "password": "Demo@123",
            "company_name": unique_company,
            "role": "admin",
        },
    )
    assert signup.status_code == 200
    assert "hireos_session=" in signup.headers.get("set-cookie", "")
    token = signup.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == unique_email


def test_google_auth_start_returns_authorization_url(monkeypatch) -> None:
    client = TestClient(main_module.app)
    monkeypatch.setattr(auth_route.google_auth, "is_configured", lambda: True)
    monkeypatch.setattr(
        auth_route.google_auth,
        "build_auth_url",
        lambda **kwargs: "https://accounts.google.com/o/oauth2/v2/auth?demo=1",
    )

    response = client.post(
        "/api/v1/auth/google/start",
        json={"flow": "signup", "company_name": "Acme Talent", "full_name": "Avery Recruiter", "role": "admin"},
    )
    assert response.status_code == 200
    assert response.json()["authorization_url"].startswith("https://accounts.google.com/")


def test_google_auth_callback_creates_session_for_new_user(monkeypatch) -> None:
    client = TestClient(main_module.app)
    monkeypatch.setattr(auth_route.google_auth, "is_configured", lambda: True)
    monkeypatch.setattr(
        auth_route.google_auth,
        "_exchange_code_for_tokens",
        lambda code: {"access_token": "google-access-token"},
    )
    monkeypatch.setattr(
        auth_route.google_auth,
        "_fetch_profile",
        lambda access_token: {"email": f"google+{uuid4().hex[:8]}@example.com", "name": "Google Recruiter"},
    )
    state = auth_route.google_auth._sign_state(
        {
            "flow": "signup",
            "company_name": f"Google Co {uuid4().hex[:6]}",
            "full_name": "Google Recruiter",
            "role": "admin",
            "ts": datetime.now(UTC).timestamp(),
        }
    )

    response = client.get(f"/api/v1/auth/google/callback?code=demo-code&state={state}", follow_redirects=False)
    assert response.status_code == 307
    location = response.headers["location"]
    assert "/auth/callback?" in location
    params = parse_qs(urlparse(location).query)
    assert params["code"][0]

    exchange = client.post("/api/v1/auth/google/exchange", json={"code": params["code"][0]})
    assert exchange.status_code == 200
    assert "hireos_session=" in exchange.headers.get("set-cookie", "")
    assert "google+" in exchange.json()["user"]["email"]


def test_google_auth_callback_logs_in_existing_user(monkeypatch) -> None:
    client = TestClient(main_module.app)
    existing_email = f"existing+{uuid4().hex[:8]}@hireos.ai"
    company_name = f"Existing Co {uuid4().hex[:6]}"
    signup = client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "Existing Recruiter",
            "email": existing_email,
            "password": "Demo@123",
            "company_name": company_name,
            "role": "admin",
        },
    )
    assert signup.status_code == 200

    monkeypatch.setattr(auth_route.google_auth, "is_configured", lambda: True)
    monkeypatch.setattr(
        auth_route.google_auth,
        "_exchange_code_for_tokens",
        lambda code: {"access_token": "google-access-token"},
    )
    monkeypatch.setattr(
        auth_route.google_auth,
        "_fetch_profile",
        lambda access_token: {"email": existing_email, "name": "Existing Recruiter"},
    )
    state = auth_route.google_auth._sign_state(
        {
            "flow": "login",
            "company_name": "",
            "full_name": "",
            "role": "admin",
            "ts": datetime.now(UTC).timestamp(),
        }
    )

    response = client.get(f"/api/v1/auth/google/callback?code=demo-code&state={state}", follow_redirects=False)
    assert response.status_code == 307
    params = parse_qs(urlparse(response.headers["location"]).query)
    assert params["workspace"][0] == "joined"
    exchange = client.post("/api/v1/auth/google/exchange", json={"code": params["code"][0]})
    assert exchange.status_code == 200
    assert exchange.json()["user"]["email"] == existing_email


def test_copilot_query_returns_evidence() -> None:
    client = TestClient(main_module.app)
    email = f"copilot+{uuid4().hex[:8]}@hireos.ai"
    company = f"Copilot Co {uuid4().hex[:6]}"
    signup = client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "Copilot Recruiter",
            "email": email,
            "password": "Demo@123",
            "company_name": company,
            "role": "admin",
        },
    )
    assert signup.status_code == 200
    token = signup.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    job = client.post(
        "/api/v1/jobs",
        headers=headers,
        json={
            "title": "Backend Engineer",
            "department": "Engineering",
            "location": "Remote",
            "work_mode": "remote",
            "experience_range": "3-6 years",
            "employment_type": "full-time",
            "salary_range": "$120k-$150k",
            "status": "open",
            "job_description": "Build FastAPI services with PostgreSQL, Docker, Redis, and Python.",
            "required_skills": ["python", "fastapi", "postgresql", "docker", "redis"],
            "preferred_skills": ["aws"],
        },
    )
    assert job.status_code == 200
    job_id = job.json()["id"]

    resume_text = b"""Taylor Backend\n+taylor@example.com\n+Senior Backend Engineer\n+\n+5 years building Python, FastAPI, PostgreSQL, Docker, and Redis services in production.\n+"""
    upload = client.post(
        "/api/v1/candidates/upload-resume",
        headers=headers,
        files={"file": ("resume.txt", resume_text, "text/plain")},
        data={"name": "Taylor Backend", "email": "taylor@example.com", "location": "Remote"},
    )
    assert upload.status_code == 200
    candidate_id = upload.json()["candidate"]["id"]

    match = client.post(f"/api/v1/candidates/{candidate_id}/match-job/{job_id}", headers=headers)
    assert match.status_code == 200

    copilot = client.post(
        "/api/v1/copilot/query",
        headers=headers,
        json={"query": "What should I review next before moving candidates forward?", "job_id": job_id},
    )
    assert copilot.status_code == 200
    payload = copilot.json()
    assert payload["answer"]
    assert payload["recommendation"]
    assert payload["action_items"]
    assert payload["human_review_note"]


def test_candidate_comparison_returns_ranked_snapshot() -> None:
    client = TestClient(main_module.app)
    email = f"compare+{uuid4().hex[:8]}@hireos.ai"
    company = f"Compare Co {uuid4().hex[:6]}"
    signup = client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "Compare Recruiter",
            "email": email,
            "password": "Demo@123",
            "company_name": company,
            "role": "admin",
        },
    )
    assert signup.status_code == 200
    token = signup.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    job = client.post(
        "/api/v1/jobs",
        headers=headers,
        json={
            "title": "Data Engineer",
            "department": "Data",
            "location": "Remote",
            "work_mode": "remote",
            "experience_range": "4-7 years",
            "employment_type": "full-time",
            "salary_range": "$130k-$160k",
            "status": "open",
            "job_description": "Build data pipelines with Python, SQL, Kafka, Airflow, and PostgreSQL.",
            "required_skills": ["python", "sql", "kafka", "airflow", "postgresql"],
            "preferred_skills": ["spark", "dbt"],
        },
    )
    assert job.status_code == 200
    job_id = job.json()["id"]

    candidate_payloads = [
        (
            "Riya Streams",
            "riya@example.com",
            b"Riya Streams\nSenior Data Engineer\n6 years with Python, SQL, Kafka, Airflow, PostgreSQL, Spark.\n",
        ),
        (
            "Noah Pipelines",
            "noah@example.com",
            b"Noah Pipelines\nData Platform Engineer\n5 years with Python, SQL, Airflow, PostgreSQL and warehouse design.\n",
        ),
    ]

    candidate_ids: list[str] = []
    for name, candidate_email, resume_text in candidate_payloads:
        upload = client.post(
            "/api/v1/candidates/upload-resume",
            headers=headers,
            files={"file": ("resume.txt", resume_text, "text/plain")},
            data={"name": name, "email": candidate_email, "location": "Remote"},
        )
        assert upload.status_code == 200
        candidate_id = upload.json()["candidate"]["id"]
        candidate_ids.append(candidate_id)

        match = client.post(f"/api/v1/candidates/{candidate_id}/match-job/{job_id}", headers=headers)
        assert match.status_code == 200

    comparison = client.post(
        f"/api/v1/comparison/jobs/{job_id}",
        headers=headers,
        json={"candidate_ids": candidate_ids},
    )
    assert comparison.status_code == 200
    payload = comparison.json()
    assert payload["comparison_answer"]
    assert len(payload["candidates"]) == 2
    assert payload["axes"]
    assert payload["human_review_note"]


def test_candidate_review_workspace_includes_decision_history_and_timeline() -> None:
    client = TestClient(main_module.app)
    email = f"review+{uuid4().hex[:8]}@hireos.ai"
    company = f"Review Co {uuid4().hex[:6]}"
    signup = client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "Review Recruiter",
            "email": email,
            "password": "Demo@123",
            "company_name": company,
            "role": "admin",
        },
    )
    assert signup.status_code == 200
    token = signup.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    job = client.post(
        "/api/v1/jobs",
        headers=headers,
        json={
            "title": "Platform Engineer",
            "department": "Infrastructure",
            "location": "Remote",
            "work_mode": "remote",
            "experience_range": "4-8 years",
            "employment_type": "full-time",
            "salary_range": "$140k-$180k",
            "status": "open",
            "job_description": "Build Python platforms with PostgreSQL, Kafka, and observability tooling.",
            "required_skills": ["python", "postgresql", "kafka"],
            "preferred_skills": ["observability"],
        },
    )
    assert job.status_code == 200
    job_id = job.json()["id"]

    upload = client.post(
        "/api/v1/candidates/upload-resume",
        headers=headers,
        files={"file": ("resume.txt", b"Casey Platform\ncasey@example.com\nPlatform Engineer\nPython PostgreSQL Kafka observability\n", "text/plain")},
        data={"name": "Casey Platform", "email": "casey@example.com", "location": "Remote"},
    )
    assert upload.status_code == 200
    candidate_id = upload.json()["candidate"]["id"]

    match = client.post(f"/api/v1/candidates/{candidate_id}/match-job/{job_id}", headers=headers)
    assert match.status_code == 200

    invite = client.post(
        "/api/v1/interviews/invite",
        headers=headers,
        json={
            "candidate_id": candidate_id,
            "job_id": job_id,
            "interview_type": "Technical screening",
            "mode": "text",
        },
    )
    assert invite.status_code == 200
    interview_id = invite.json()["id"]

    start = client.post(f"/api/v1/interviews/{interview_id}/start", json={"consent_given": True})
    assert start.status_code == 200

    question = client.get(f"/api/v1/interviews/{interview_id}/next-question")
    assert question.status_code == 200
    question_id = question.json()["id"]

    answer = client.post(
        f"/api/v1/interviews/{interview_id}/answers",
        json={
            "question_id": question_id,
            "answer_text": "I have led Python and Kafka platform work with strong production instrumentation.",
            "answer_mode": "text",
            "latency_ms": 18000,
        },
    )
    assert answer.status_code == 200

    report = client.post(f"/api/v1/interviews/{interview_id}/complete")
    assert report.status_code == 200

    decision = client.post(
        f"/api/v1/interviews/{interview_id}/decision",
        headers=headers,
        json={
            "decision": "shortlisted",
            "notes": "Strong systems depth, good fit for the next manager round.",
            "override_ai_recommendation": True,
        },
    )
    assert decision.status_code == 200

    workspace = client.get(f"/api/v1/candidates/{candidate_id}/review-workspace/{job_id}", headers=headers)
    assert workspace.status_code == 200
    payload = workspace.json()
    assert payload["latest_match"]["overall_score"] >= 0
    assert payload["latest_interview"]["id"] == interview_id
    assert payload["latest_report"]["recommended_next_step"]
    assert payload["latest_decision"]["decision"] == "shortlisted"
    assert payload["latest_decision"]["override_ai_recommendation"] is True
    assert payload["decision_history"]
    assert any(entry["action"] == "recruiter.decision_made" for entry in payload["audit_timeline"])


def test_voice_interview_answer_accepts_transcript() -> None:
    client = TestClient(main_module.app)
    email = f"voice+{uuid4().hex[:8]}@hireos.ai"
    company = f"Voice Co {uuid4().hex[:6]}"
    signup = client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "Voice Recruiter",
            "email": email,
            "password": "Demo@123",
            "company_name": company,
            "role": "admin",
        },
    )
    assert signup.status_code == 200
    token = signup.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    job = client.post(
        "/api/v1/jobs",
        headers=headers,
        json={
            "title": "ML Engineer",
            "department": "AI",
            "location": "Remote",
            "work_mode": "remote",
            "experience_range": "3-6 years",
            "employment_type": "full-time",
            "salary_range": "$140k-$175k",
            "status": "open",
            "job_description": "Build ML systems with Python, model serving, feature pipelines, and experimentation.",
            "required_skills": ["python", "ml", "serving"],
            "preferred_skills": ["feature stores"],
        },
    )
    assert job.status_code == 200
    job_id = job.json()["id"]

    upload = client.post(
        "/api/v1/candidates/upload-resume",
        headers=headers,
        files={"file": ("resume.txt", b"Jamie Voice\nML Engineer\nPython ML serving experimentation.\n", "text/plain")},
        data={"name": "Jamie Voice", "email": "jamie.voice@example.com", "location": "Remote"},
    )
    assert upload.status_code == 200
    candidate_id = upload.json()["candidate"]["id"]

    invite = client.post(
        "/api/v1/interviews/invite",
        headers=headers,
        json={
            "candidate_id": candidate_id,
            "job_id": job_id,
            "interview_type": "Technical screening",
            "mode": "voice",
        },
    )
    assert invite.status_code == 200
    interview_id = invite.json()["id"]

    start = client.post(f"/api/v1/interviews/{interview_id}/start", json={"consent_given": True})
    assert start.status_code == 200
    assert start.json()["mode"] == "voice"

    question = client.get(f"/api/v1/interviews/{interview_id}/next-question")
    assert question.status_code == 200
    question_id = question.json()["id"]

    answer = client.post(
        f"/api/v1/interviews/{interview_id}/answers",
        json={
            "question_id": question_id,
            "answer_text": "I have built Python ML services with measurable production impact.",
            "transcript_text": "I have built Python ML services with measurable production impact and collaborated closely with stakeholders.",
            "answer_mode": "voice",
            "latency_ms": 42000,
        },
    )
    assert answer.status_code == 200
    payload = answer.json()
    assert payload["score"]["total_score"] >= 0


def test_interview_invite_returns_shareable_links() -> None:
    client = TestClient(main_module.app)
    email = f"invite+{uuid4().hex[:8]}@hireos.ai"
    company = f"Invite Co {uuid4().hex[:6]}"
    signup = client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "Invite Recruiter",
            "email": email,
            "password": "Demo@123",
            "company_name": company,
            "role": "admin",
        },
    )
    assert signup.status_code == 200
    token = signup.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    job = client.post(
        "/api/v1/jobs",
        headers=headers,
        json={
            "title": "Backend Engineer",
            "department": "Engineering",
            "location": "Remote",
            "work_mode": "remote",
            "experience_range": "3-6 years",
            "employment_type": "full-time",
            "salary_range": "$120k-$145k",
            "status": "open",
            "job_description": "Build APIs with Python, FastAPI, and PostgreSQL.",
            "required_skills": ["python", "fastapi", "postgresql"],
            "preferred_skills": ["redis"],
        },
    )
    assert job.status_code == 200
    job_id = job.json()["id"]

    upload = client.post(
        "/api/v1/candidates/upload-resume",
        headers=headers,
        files={"file": ("resume.txt", b"Rhea API\nrhea@example.com\nBackend Engineer\nPython FastAPI PostgreSQL\n", "text/plain")},
        data={"name": "Rhea API", "email": "rhea@example.com", "location": "Remote"},
    )
    assert upload.status_code == 200
    candidate_id = upload.json()["candidate"]["id"]

    invite = client.post(
        "/api/v1/interviews/invite",
        headers=headers,
        json={
            "candidate_id": candidate_id,
            "job_id": job_id,
            "interview_type": "Technical screening",
            "mode": "voice",
            "meeting_provider": "google_meet",
        },
    )
    assert invite.status_code == 200
    payload = invite.json()
    assert payload["share_links"]["candidate_email"] == "rhea@example.com"
    assert payload["share_links"]["candidate_portal_url"].endswith(f"/interview/{payload['id']}")
    assert payload["share_links"]["candidate_join_url"].endswith(f"/interview/{payload['id']}")
    assert "calendar.google.com" in payload["share_links"]["meeting_setup_url"]
    assert payload["share_links"]["email_compose_url"].startswith("mailto:rhea%40example.com")


def test_send_interview_email_creates_delivery_history() -> None:
    client = TestClient(main_module.app)
    email = f"notify+{uuid4().hex[:8]}@hireos.ai"
    company = f"Notify Co {uuid4().hex[:6]}"
    signup = client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "Notify Recruiter",
            "email": email,
            "password": "Demo@123",
            "company_name": company,
            "role": "admin",
        },
    )
    assert signup.status_code == 200
    token = signup.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    job = client.post(
        "/api/v1/jobs",
        headers=headers,
        json={
            "title": "Backend Engineer",
            "department": "Engineering",
            "location": "Remote",
            "work_mode": "remote",
            "experience_range": "3-6 years",
            "employment_type": "full-time",
            "salary_range": "$120k-$145k",
            "status": "open",
            "job_description": "Build APIs with Python, FastAPI, and PostgreSQL.",
            "required_skills": ["python", "fastapi", "postgresql"],
            "preferred_skills": ["redis"],
        },
    )
    assert job.status_code == 200
    job_id = job.json()["id"]

    upload = client.post(
        "/api/v1/candidates/upload-resume",
        headers=headers,
        files={"file": ("resume.txt", b"Rhea Notify\nrhea@example.com\nBackend Engineer\nPython FastAPI PostgreSQL\n", "text/plain")},
        data={"name": "Rhea Notify", "email": "rhea@example.com", "location": "Remote"},
    )
    assert upload.status_code == 200
    candidate_id = upload.json()["candidate"]["id"]

    invite = client.post(
        "/api/v1/interviews/invite",
        headers=headers,
        json={
            "candidate_id": candidate_id,
            "job_id": job_id,
            "interview_type": "Technical screening",
            "mode": "text",
            "meeting_provider": "google_meet",
        },
    )
    assert invite.status_code == 200
    interview_id = invite.json()["id"]

    send = client.post(f"/api/v1/interviews/{interview_id}/send-email", headers=headers)
    assert send.status_code == 200
    payload = send.json()
    assert payload["delivery"]["recipient_email"] == "rhea@example.com"
    assert payload["delivery"]["status"] in {"fallback", "delivered"}

    history = client.get(f"/api/v1/interviews/{interview_id}/email-deliveries", headers=headers)
    assert history.status_code == 200
    history_payload = history.json()
    assert len(history_payload) == 1
    assert history_payload[0]["subject"]


def test_live_video_invite_uses_real_join_url() -> None:
    client = TestClient(main_module.app)
    email = f"live+{uuid4().hex[:8]}@hireos.ai"
    company = f"Live Co {uuid4().hex[:6]}"
    signup = client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "Live Recruiter",
            "email": email,
            "password": "Demo@123",
            "company_name": company,
            "role": "admin",
        },
    )
    assert signup.status_code == 200
    token = signup.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    job = client.post(
        "/api/v1/jobs",
        headers=headers,
        json={
            "title": "Data Engineer",
            "department": "Data",
            "location": "Remote",
            "work_mode": "remote",
            "experience_range": "4-7 years",
            "employment_type": "full-time",
            "salary_range": "$130k-$160k",
            "status": "open",
            "job_description": "Build pipelines with Python, Kafka, SQL, and Airflow.",
            "required_skills": ["python", "sql", "kafka"],
            "preferred_skills": ["airflow"],
        },
    )
    assert job.status_code == 200
    job_id = job.json()["id"]

    upload = client.post(
        "/api/v1/candidates/upload-resume",
        headers=headers,
        files={"file": ("resume.txt", b"Priya Streams\npriya@example.com\nData Engineer\nPython Kafka SQL\n", "text/plain")},
        data={"name": "Priya Streams", "email": "priya@example.com", "location": "Remote"},
    )
    assert upload.status_code == 200
    candidate_id = upload.json()["candidate"]["id"]

    invite = client.post(
        "/api/v1/interviews/invite",
        headers=headers,
        json={
            "candidate_id": candidate_id,
            "job_id": job_id,
            "interview_type": "Technical screening",
            "mode": "video",
            "meeting_provider": "google_meet",
            "schedule_type": "scheduled",
            "scheduled_at": "2026-06-01T14:30:00",
            "meeting_join_url": "https://meet.google.com/abc-defg-hij",
        },
    )
    assert invite.status_code == 200
    payload = invite.json()
    assert payload["share_links"]["candidate_join_url"] == "https://meet.google.com/abc-defg-hij"
    assert payload["share_links"]["meeting_setup_url"] == "https://meet.google.com/abc-defg-hij"
    assert payload["share_links"]["schedule_type"] == "scheduled"


def test_live_video_invite_auto_generates_google_meet_when_connected(monkeypatch) -> None:
    client = TestClient(main_module.app)
    email = f"automeet+{uuid4().hex[:8]}@hireos.ai"
    company = f"Auto Meet Co {uuid4().hex[:6]}"
    signup = client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "Auto Meet Recruiter",
            "email": email,
            "password": "Demo@123",
            "company_name": company,
            "role": "admin",
        },
    )
    assert signup.status_code == 200
    token = signup.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    monkeypatch.setattr(interviews_route.google_calendar, "is_configured", lambda: True)
    monkeypatch.setattr(
        interviews_route.google_calendar,
        "create_meet_event",
        lambda *args, **kwargs: {
            "meeting_join_url": "https://meet.google.com/generated-demo-link",
            "calendar_event_id": "calendar-event-123",
            "scheduled_at": "2026-06-02T10:00:00+00:00",
            "schedule_type": "scheduled",
        },
    )

    job = client.post(
        "/api/v1/jobs",
        headers=headers,
        json={
            "title": "Platform Engineer",
            "department": "Platform",
            "location": "Remote",
            "work_mode": "remote",
            "experience_range": "5-8 years",
            "employment_type": "full-time",
            "salary_range": "$150k-$180k",
            "status": "open",
            "job_description": "Own infrastructure, Python services, observability, and developer tooling.",
            "required_skills": ["python", "kubernetes", "observability"],
            "preferred_skills": ["terraform"],
        },
    )
    assert job.status_code == 200
    job_id = job.json()["id"]

    upload = client.post(
        "/api/v1/candidates/upload-resume",
        headers=headers,
        files={"file": ("resume.txt", b"Arjun Infra\narjun@example.com\nPlatform Engineer\nPython Kubernetes observability\n", "text/plain")},
        data={"name": "Arjun Infra", "email": "arjun@example.com", "location": "Remote"},
    )
    assert upload.status_code == 200
    candidate_id = upload.json()["candidate"]["id"]

    invite = client.post(
        "/api/v1/interviews/invite",
        headers=headers,
        json={
            "candidate_id": candidate_id,
            "job_id": job_id,
            "interview_type": "Technical screening",
            "mode": "video",
            "meeting_provider": "google_meet",
            "schedule_type": "scheduled",
            "scheduled_at": "2026-06-02T10:00:00Z",
        },
    )
    assert invite.status_code == 200
    payload = invite.json()
    assert payload["share_links"]["candidate_join_url"] == "https://meet.google.com/generated-demo-link"
    assert payload["share_links"]["meeting_setup_url"] == "https://meet.google.com/generated-demo-link"
    assert payload["share_links"]["schedule_type"] == "scheduled"


def test_ranking_simulator_reorders_candidates_when_weights_change() -> None:
    client = TestClient(main_module.app)
    email = f"simrank+{uuid4().hex[:8]}@hireos.ai"
    company = f"Sim Rank Co {uuid4().hex[:6]}"
    signup = client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "Simulator Recruiter",
            "email": email,
            "password": "Demo@123",
            "company_name": company,
            "role": "admin",
        },
    )
    assert signup.status_code == 200
    token = signup.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    job = client.post(
        "/api/v1/jobs",
        headers=headers,
        json={
            "title": "Data Platform Engineer",
            "department": "Data",
            "location": "Remote",
            "work_mode": "remote",
            "experience_range": "4-8 years",
            "employment_type": "full-time",
            "salary_range": "$135k-$170k",
            "status": "open",
            "job_description": "Build Python, SQL, Kafka, Airflow, and PostgreSQL data systems.",
            "required_skills": ["python", "sql", "kafka", "airflow", "postgresql"],
            "preferred_skills": ["spark"],
        },
    )
    assert job.status_code == 200
    job_id = job.json()["id"]

    candidates = [
        (
            "Morgan Match",
            "morgan@example.com",
            b"Morgan Match\nData Engineer\nPython SQL Kafka Airflow PostgreSQL Spark.\n",
            "I have built reliable data pipelines and can explain schema evolution clearly.",
        ),
        (
            "Ivy Interview",
            "ivy@example.com",
            b"Ivy Interview\nAnalytics Engineer\nPython SQL PostgreSQL.\n",
            "I design systems end to end, explain trade-offs well, mentor engineers, and reason deeply about latency, retries, and stakeholder communication.",
        ),
    ]

    interview_ids: dict[str, str] = {}

    for name, candidate_email, resume_text, answer_text in candidates:
        upload = client.post(
            "/api/v1/candidates/upload-resume",
            headers=headers,
            files={"file": ("resume.txt", resume_text, "text/plain")},
            data={"name": name, "email": candidate_email, "location": "Remote"},
        )
        assert upload.status_code == 200
        candidate_id = upload.json()["candidate"]["id"]

        match = client.post(f"/api/v1/candidates/{candidate_id}/match-job/{job_id}", headers=headers)
        assert match.status_code == 200

        invite = client.post(
            "/api/v1/interviews/invite",
            headers=headers,
            json={
                "candidate_id": candidate_id,
                "job_id": job_id,
                "interview_type": "Technical screening",
                "mode": "text",
            },
        )
        assert invite.status_code == 200
        interview_id = invite.json()["id"]
        interview_ids[name] = interview_id

        start = client.post(f"/api/v1/interviews/{interview_id}/start", json={"consent_given": True})
        assert start.status_code == 200

        question = client.get(f"/api/v1/interviews/{interview_id}/next-question")
        assert question.status_code == 200
        question_id = question.json()["id"]

        answer = client.post(
            f"/api/v1/interviews/{interview_id}/answers",
            json={
                "question_id": question_id,
                "answer_text": answer_text,
                "answer_mode": "text",
                "latency_ms": 15000,
            },
        )
        assert answer.status_code == 200

    baseline = client.get(f"/api/v1/jobs/{job_id}/ranking", headers=headers)
    assert baseline.status_code == 200
    baseline_payload = baseline.json()
    assert baseline_payload[0]["candidate_name"] == "Morgan Match"

    decision = client.post(
        f"/api/v1/interviews/{interview_ids['Ivy Interview']}/decision",
        headers=headers,
        json={
            "decision": "shortlisted",
            "notes": "Promising communicator worth advancing despite missing skills.",
            "override_ai_recommendation": True,
        },
    )
    assert decision.status_code == 200

    simulation = client.post(
        f"/api/v1/jobs/{job_id}/ranking/simulate",
        headers=headers,
        json={
            "resume_weight": 15,
            "interview_weight": 85,
            "missing_skill_penalty": 1,
            "human_review_penalty": 0,
            "shortlist_boost": 20,
        },
    )
    assert simulation.status_code == 200
    payload = simulation.json()
    assert payload["candidates"][0]["candidate_name"] == "Ivy Interview"
    assert payload["candidates"][0]["rank_change"] > 0
    assert payload["summary"]


def test_interview_reminder_preview_and_run() -> None:
    client = TestClient(main_module.app)
    email = f"reminders+{uuid4().hex[:8]}@hireos.ai"
    company = f"Reminder Co {uuid4().hex[:6]}"
    signup = client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "Reminder Recruiter",
            "email": email,
            "password": "Demo@123",
            "company_name": company,
            "role": "admin",
        },
    )
    assert signup.status_code == 200
    token = signup.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    job = client.post(
        "/api/v1/jobs",
        headers=headers,
        json={
            "title": "Analytics Engineer",
            "department": "Data",
            "location": "Remote",
            "work_mode": "remote",
            "experience_range": "3-6 years",
            "employment_type": "full-time",
            "salary_range": "$120k-$145k",
            "status": "open",
            "job_description": "Own analytics models with SQL, Python, and stakeholder communication.",
            "required_skills": ["sql", "python"],
            "preferred_skills": ["dbt"],
        },
    )
    assert job.status_code == 200
    job_id = job.json()["id"]

    candidate_payloads = [
        ("Nina NoShow", "nina@example.com", b"Nina NoShow\nSQL Python\n"),
        ("Omar Partial", "omar@example.com", b"Omar Partial\nSQL Python DBT\n"),
    ]
    interview_ids: list[str] = []
    for name, candidate_email, resume_text in candidate_payloads:
        upload = client.post(
            "/api/v1/candidates/upload-resume",
            headers=headers,
            files={"file": ("resume.txt", resume_text, "text/plain")},
            data={"name": name, "email": candidate_email, "location": "Remote"},
        )
        assert upload.status_code == 200
        candidate_id = upload.json()["candidate"]["id"]

        invite = client.post(
            "/api/v1/interviews/invite",
            headers=headers,
            json={
                "candidate_id": candidate_id,
                "job_id": job_id,
                "interview_type": "Technical screening",
                "mode": "text",
            },
        )
        assert invite.status_code == 200
        interview_ids.append(invite.json()["id"])

    started = client.post(f"/api/v1/interviews/{interview_ids[1]}/start", json={"consent_given": True})
    assert started.status_code == 200

    stale_time = datetime.now(UTC).replace(tzinfo=None)
    with SessionLocal() as db:
        invited = db.get(Interview, interview_ids[0])
        partial = db.get(Interview, interview_ids[1])
        assert invited and partial
        invited.created_at = stale_time - timedelta(hours=25)
        partial.started_at = stale_time - timedelta(hours=8)
        db.commit()

    preview = client.get("/api/v1/interviews/reminders/preview", headers=headers)
    assert preview.status_code == 200
    payload = preview.json()
    assert payload["invited_no_show_count"] == 1
    assert payload["incomplete_count"] == 1
    assert len(payload["candidates"]) == 2

    run = client.post("/api/v1/interviews/reminders/run", headers=headers)
    assert run.status_code == 200
    run_payload = run.json()
    assert run_payload["fallback_count"] + run_payload["sent_count"] == 2
    assert len(run_payload["deliveries"]) == 2


def test_ats_webhook_export_flows_from_recruiter_decision(monkeypatch) -> None:
    client = TestClient(main_module.app)
    email = f"ats+{uuid4().hex[:8]}@hireos.ai"
    company = f"ATS Co {uuid4().hex[:6]}"
    signup = client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "ATS Recruiter",
            "email": email,
            "password": "Demo@123",
            "company_name": company,
            "role": "admin",
        },
    )
    assert signup.status_code == 200
    token = signup.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    status_before = client.get("/api/v1/integrations/ats-webhook/status", headers=headers)
    assert status_before.status_code == 200
    assert status_before.json()["configured"] is False

    class DummyResponse:
        status_code = 202
        text = "accepted"

    class DummyClient:
        def __init__(self, timeout: int) -> None:
            self.timeout = timeout

        def __enter__(self) -> "DummyClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def post(self, url: str, content: str, headers: dict[str, str]) -> DummyResponse:
            payload = json.loads(content)
            assert url == "https://ats.example.com/webhooks/hireos"
            assert headers["Authorization"] == "Bearer ats-token"
            assert headers["X-HireOS-Signature"].startswith("sha256=")
            assert payload["compliance"]["human_in_the_loop"] is True
            return DummyResponse()

    monkeypatch.setattr(ats_webhooks_service.httpx, "Client", DummyClient)

    config = client.patch(
        "/api/v1/integrations/ats-webhook",
        headers=headers,
        json={
            "enabled": True,
            "provider_label": "Greenhouse",
            "endpoint_url": "https://ats.example.com/webhooks/hireos",
            "auth_token": "ats-token",
            "signing_secret": "signing-secret",
            "export_stages": ["shortlisted", "moved_to_next_round", "hired"],
        },
    )
    assert config.status_code == 200
    assert config.json()["enabled"] is True
    assert config.json()["has_auth_token"] is True

    company_response = client.get("/api/v1/companies/me", headers=headers)
    assert company_response.status_code == 200
    assert "auth_token" not in json.dumps(company_response.json()["settings_json"])

    test_delivery = client.post("/api/v1/integrations/ats-webhook/test", headers=headers)
    assert test_delivery.status_code == 200
    assert test_delivery.json()["status"] == "delivered"

    job = client.post(
        "/api/v1/jobs",
        headers=headers,
        json={
            "title": "Integration Engineer",
            "department": "Platform",
            "location": "Remote",
            "work_mode": "remote",
            "experience_range": "4-7 years",
            "employment_type": "full-time",
            "salary_range": "$135k-$165k",
            "status": "open",
            "job_description": "Build integrations, APIs, and webhook workflows with Python and SQL.",
            "required_skills": ["python", "sql", "webhooks"],
            "preferred_skills": ["fastapi"],
        },
    )
    assert job.status_code == 200
    job_id = job.json()["id"]

    upload = client.post(
        "/api/v1/candidates/upload-resume",
        headers=headers,
        files={"file": ("resume.txt", b"Jordan Integrations\njordan@example.com\nPython SQL webhooks FastAPI.\n", "text/plain")},
        data={"name": "Jordan Integrations", "email": "jordan@example.com", "location": "Remote"},
    )
    assert upload.status_code == 200
    candidate_id = upload.json()["candidate"]["id"]

    match = client.post(f"/api/v1/candidates/{candidate_id}/match-job/{job_id}", headers=headers)
    assert match.status_code == 200

    invite = client.post(
        "/api/v1/interviews/invite",
        headers=headers,
        json={
            "candidate_id": candidate_id,
            "job_id": job_id,
            "interview_type": "Technical screening",
            "mode": "text",
        },
    )
    assert invite.status_code == 200
    interview_id = invite.json()["id"]

    start = client.post(f"/api/v1/interviews/{interview_id}/start", json={"consent_given": True})
    assert start.status_code == 200

    question = client.get(f"/api/v1/interviews/{interview_id}/next-question")
    assert question.status_code == 200
    question_id = question.json()["id"]

    answer = client.post(
        f"/api/v1/interviews/{interview_id}/answers",
        json={
            "question_id": question_id,
            "answer_text": "I have shipped integration pipelines and webhook delivery tooling in production.",
            "answer_mode": "text",
            "latency_ms": 14000,
        },
    )
    assert answer.status_code == 200

    report = client.post(f"/api/v1/interviews/{interview_id}/complete")
    assert report.status_code == 200

    decision = client.post(
        f"/api/v1/interviews/{interview_id}/decision",
        headers=headers,
        json={
            "decision": "shortlisted",
            "notes": "Approved by recruiter for downstream ATS handoff.",
            "override_ai_recommendation": False,
        },
    )
    assert decision.status_code == 200
    assert decision.json()["ats_export"]["status"] == "delivered"

    exports = client.get(f"/api/v1/interviews/{interview_id}/ats-exports", headers=headers)
    assert exports.status_code == 200
    assert len(exports.json()) == 1
    assert exports.json()[0]["target_url"] == "https://ats.example.com/webhooks/hireos"

    manual_retry = client.post(f"/api/v1/interviews/{interview_id}/export-ats", headers=headers)
    assert manual_retry.status_code == 200
    assert manual_retry.json()["status"] == "delivered"

    exports_after_retry = client.get(f"/api/v1/interviews/{interview_id}/ats-exports", headers=headers)
    assert exports_after_retry.status_code == 200
    assert len(exports_after_retry.json()) == 2
