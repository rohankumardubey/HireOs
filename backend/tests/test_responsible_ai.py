from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

import app.main as main_module
from app.db.session import init_db


def _signup(client: TestClient, *, role: str = "admin") -> tuple[str, str]:
    init_db()
    email = f"responsible-ai+{uuid4().hex[:8]}@hireos.ai"
    company = f"Responsible AI Co {uuid4().hex[:6]}"
    response = client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "Responsible AI Admin",
            "email": email,
            "password": "Demo@123",
            "company_name": company,
            "role": role,
        },
    )
    assert response.status_code == 200
    return response.json()["access_token"], response.json()["user"]["memberships"][0]["company_id"]


def test_responsible_ai_dashboard_summarizes_bias_shield_and_human_review_controls() -> None:
    client = TestClient(main_module.app)
    token, _company_id = _signup(client)
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
            "salary_range": "$140k-$180k",
            "status": "open",
            "job_description": "Build Kafka, Spark, Airflow, Python, and lakehouse platforms for hiring analytics.",
            "required_skills": ["kafka", "spark", "airflow", "python"],
            "preferred_skills": ["lakehouse"],
        },
    )
    assert job.status_code == 200
    job_id = job.json()["id"]

    upload = client.post(
        "/api/v1/candidates/upload-resume",
        headers=headers,
        files={
            "file": (
                "resume.txt",
                (
                    b"Taylor Governance\n"
                    b"taylor.governance@example.com\n"
                    b"DOB: 12/05/1995\n"
                    b"Married\n"
                    b"She/Her\n"
                    b"Senior Data Engineer\n"
                    b"Python SQL Kafka Airflow PostgreSQL\n"
                ),
                "text/plain",
            )
        },
        data={
            "name": "Taylor Governance",
            "email": "taylor.governance@example.com",
            "location": "Remote",
        },
    )
    assert upload.status_code == 200
    candidate_id = upload.json()["candidate"]["id"]

    match = client.post(f"/api/v1/candidates/{candidate_id}/match-job/{job_id}", headers=headers)
    assert match.status_code == 200
    assert match.json()["human_review_required"] is True

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

    decision = client.post(
        f"/api/v1/interviews/{interview_id}/decision",
        headers=headers,
        json={
            "decision": "shortlisted",
            "notes": "Proceeding after human review despite missing one preferred platform signal.",
            "override_ai_recommendation": True,
        },
    )
    assert decision.status_code == 200

    calibration = client.patch(
        f"/api/v1/candidates/{candidate_id}/calibration-case/{job_id}",
        headers=headers,
        json={
            "status": "in_progress",
            "assign_to_me": True,
            "due_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            "resolution_summary": "Reviewing override rationale",
        },
    )
    assert calibration.status_code == 200

    dashboard = client.get("/api/v1/analytics/responsible-ai", headers=headers)
    assert dashboard.status_code == 200
    payload = dashboard.json()

    assert payload["summary"]["total_candidates"] == 1
    assert payload["summary"]["resumes_processed"] == 1
    assert payload["summary"]["redacted_resumes"] == 1
    assert payload["summary"]["protected_signal_rate"] == 100.0
    assert payload["summary"]["human_review_candidates"] == 1
    assert payload["summary"]["override_count"] == 1
    assert payload["summary"]["open_calibration_cases"] == 1
    assert payload["summary"]["overdue_calibration_cases"] == 1
    assert payload["summary"]["governance_event_count"] >= 3
    assert {item["category"] for item in payload["redaction_categories"]} >= {
        "age_or_date_of_birth",
        "gender_or_pronouns",
        "marital_status",
    }
    assert any(item["event_type"] == "resume.redacted" for item in payload["governance_events"])
    assert any(item["event_type"] == "candidate.matched" for item in payload["governance_events"])
    assert any(item["event_type"] == "recruiter.decision_made" for item in payload["governance_events"])

    signal = payload["recent_candidate_signals"][0]
    assert signal["candidate_id"] == candidate_id
    assert signal["human_review_required"] is True
    assert signal["override_ai_recommendation"] is True
    assert "Protected-attribute signals redacted from resume" in signal["reasons"]
    assert "Open calibration case" in signal["reasons"]
    assert payload["policy_note"]


def test_responsible_ai_dashboard_is_company_scoped() -> None:
    client = TestClient(main_module.app)
    first_token, _first_company_id = _signup(client)
    second_token, _second_company_id = _signup(client)

    first_headers = {"Authorization": f"Bearer {first_token}"}
    second_headers = {"Authorization": f"Bearer {second_token}"}

    upload = client.post(
        "/api/v1/candidates/upload-resume",
        headers=first_headers,
        files={
            "file": (
                "resume.txt",
                b"Scoped Candidate\nscoped@example.com\nDOB: 12/05/1995\nPython SQL Kafka\n",
                "text/plain",
            )
        },
        data={"name": "Scoped Candidate", "email": "scoped@example.com"},
    )
    assert upload.status_code == 200

    first_dashboard = client.get("/api/v1/analytics/responsible-ai", headers=first_headers)
    assert first_dashboard.status_code == 200
    assert first_dashboard.json()["summary"]["redacted_resumes"] == 1

    second_dashboard = client.get("/api/v1/analytics/responsible-ai", headers=second_headers)
    assert second_dashboard.status_code == 200
    assert second_dashboard.json()["summary"]["total_candidates"] == 0
    assert second_dashboard.json()["summary"]["redacted_resumes"] == 0
    assert second_dashboard.json()["recent_candidate_signals"] == []
