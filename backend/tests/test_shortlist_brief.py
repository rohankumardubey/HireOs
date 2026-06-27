from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

import app.main as main_module
from app.db.session import init_db


def _signup(client: TestClient, *, role: str = "admin") -> tuple[str, dict[str, str]]:
    init_db()
    email = f"shortlist+{uuid4().hex[:8]}@hireos.ai"
    company = f"Shortlist Co {uuid4().hex[:6]}"
    response = client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "Shortlist Recruiter",
            "email": email,
            "password": "Demo@123",
            "company_name": company,
            "role": role,
        },
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return token, {"Authorization": f"Bearer {token}"}


def _create_job(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post(
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
    assert response.status_code == 200
    return response.json()["id"]


def _upload_and_match(
    client: TestClient,
    headers: dict[str, str],
    *,
    job_id: str,
    name: str,
    email: str,
    resume: bytes,
) -> str:
    upload = client.post(
        "/api/v1/candidates/upload-resume",
        headers=headers,
        files={"file": ("resume.txt", resume, "text/plain")},
        data={"name": name, "email": email, "location": "Remote"},
    )
    assert upload.status_code == 200
    candidate_id = upload.json()["candidate"]["id"]
    match = client.post(f"/api/v1/candidates/{candidate_id}/match-job/{job_id}", headers=headers)
    assert match.status_code == 200
    return candidate_id


def test_shortlist_brief_builds_hiring_manager_ready_evidence() -> None:
    client = TestClient(main_module.app)
    _token, headers = _signup(client)
    job_id = _create_job(client, headers)

    leader_id = _upload_and_match(
        client,
        headers,
        job_id=job_id,
        name="Morgan Match",
        email="morgan.shortlist@example.com",
        resume=b"Morgan Match\nData Engineer\nPython SQL Kafka Airflow PostgreSQL Spark.\n",
    )
    backup_id = _upload_and_match(
        client,
        headers,
        job_id=job_id,
        name="Ivy Interview",
        email="ivy.shortlist@example.com",
        resume=b"Ivy Interview\nAnalytics Engineer\nPython SQL PostgreSQL stakeholder communication.\n",
    )

    invite = client.post(
        "/api/v1/interviews/invite",
        headers=headers,
        json={
            "candidate_id": leader_id,
            "job_id": job_id,
            "interview_type": "Technical screening",
            "mode": "text",
        },
    )
    assert invite.status_code == 200
    interview_id = invite.json()["id"]

    decision = client.post(
        f"/api/v1/interviews/{interview_id}/decision",
        headers=headers,
        json={
            "decision": "shortlisted",
            "notes": "Strong must-have coverage for hiring-manager review.",
            "override_ai_recommendation": False,
        },
    )
    assert decision.status_code == 200

    brief = client.get(f"/api/v1/jobs/{job_id}/shortlist-brief", headers=headers)
    assert brief.status_code == 200
    payload = brief.json()

    assert payload["job_id"] == job_id
    assert payload["summary"]["total_matched_candidates"] == 2
    assert payload["summary"]["recommended_shortlist_count"] == 2
    assert payload["summary"]["advanced_decision_count"] == 1
    assert payload["summary"]["human_review_required_count"] >= 1
    assert payload["summary"]["top_candidate_id"] == leader_id
    assert "Morgan Match" in payload["hiring_manager_summary"]
    assert len(payload["discussion_questions"]) >= 3
    assert payload["policy_note"]

    leader = payload["candidates"][0]
    assert leader["candidate_id"] == leader_id
    assert leader["rank"] == 1
    assert leader["recruiter_decision"] == "shortlisted"
    assert leader["must_have_coverage"] == 100.0
    assert "python" in leader["matched_required_skills"]
    assert leader["suggested_next_step"] == "Align with the hiring manager on next-round focus areas."
    assert leader["evidence_summary"]

    backup = next(candidate for candidate in payload["candidates"] if candidate["candidate_id"] == backup_id)
    assert backup["missing_required_skills"]
    assert any("Missing must-have skills" in risk for risk in backup["risks"])


def test_shortlist_brief_is_company_scoped() -> None:
    client = TestClient(main_module.app)
    _first_token, first_headers = _signup(client)
    _second_token, second_headers = _signup(client)
    job_id = _create_job(client, first_headers)

    _upload_and_match(
        client,
        first_headers,
        job_id=job_id,
        name="Scoped Shortlist",
        email="scoped.shortlist@example.com",
        resume=b"Scoped Shortlist\nData Engineer\nPython SQL Kafka Airflow PostgreSQL.\n",
    )

    allowed = client.get(f"/api/v1/jobs/{job_id}/shortlist-brief", headers=first_headers)
    assert allowed.status_code == 200
    assert allowed.json()["summary"]["total_matched_candidates"] == 1

    blocked = client.get(f"/api/v1/jobs/{job_id}/shortlist-brief", headers=second_headers)
    assert blocked.status_code == 404
