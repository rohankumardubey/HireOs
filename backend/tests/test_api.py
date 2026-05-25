from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from fastapi.testclient import TestClient

import app.main as main_module
from app.api.routes import auth as auth_route
from app.api.routes import interviews as interviews_route
from app.db.session import engine, init_db


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
