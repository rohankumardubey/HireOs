from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

import app.main as main_module
from app.db.models import EventOutbox, EvaluationRun
from app.db.session import SessionLocal, init_db
from app.services.evaluations import EvaluationService


def signup(client: TestClient, *, role: str = "admin") -> tuple[str, dict[str, str]]:
    email = f"evaluation+{uuid4().hex[:8]}@hireos.ai"
    response = client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "Evaluation Owner",
            "email": email,
            "password": "Demo@123",
            "company_name": f"Evaluation Co {uuid4().hex[:8]}",
            "role": role,
        },
    )
    assert response.status_code == 200
    return response.json()["access_token"], {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_evaluation_service_preserves_current_golden_set_scores() -> None:
    summary = EvaluationService().evaluate_dataset()

    assert summary.total_cases == 5
    assert summary.strong_pass_rate == 40.0
    assert summary.weak_rejection_rate == 100.0
    assert summary.false_negative_count == 3
    assert summary.false_positive_count == 0
    assert summary.regression_count == 0
    assert summary.quality_status == "failed"
    assert summary.cases[0]["strong_score"] == 64.97
    assert summary.cases[0]["weak_score"] == 17.38


def test_evaluation_run_is_persisted_and_repeatable() -> None:
    init_db()
    client = TestClient(main_module.app)
    _, headers = signup(client)

    first = client.post("/api/v1/evaluations/runs", headers=headers)
    assert first.status_code == 200
    first_payload = first.json()
    assert first_payload["status"] == "completed"
    assert first_payload["quality_status"] == "failed"
    assert first_payload["total_cases"] == 5
    assert first_payload["strong_pass_rate"] == 40.0
    assert first_payload["weak_rejection_rate"] == 100.0
    assert len(first_payload["case_results"]) == 5

    second = client.post("/api/v1/evaluations/runs", headers=headers)
    assert second.status_code == 200
    second_payload = second.json()
    assert second_payload["baseline_run_id"] == first_payload["id"]
    assert second_payload["regression_count"] == 0
    assert [case["strong_score"] for case in second_payload["case_results"]] == [
        case["strong_score"] for case in first_payload["case_results"]
    ]

    listing = client.get("/api/v1/evaluations/runs", headers=headers)
    assert listing.status_code == 200
    assert len(listing.json()["runs"]) == 2
    assert listing.json()["latest"]["id"] == second_payload["id"]

    with SessionLocal() as db:
        stored = db.execute(
            select(EvaluationRun).where(EvaluationRun.id == second_payload["id"])
        ).scalar_one()
        assert stored.scoring_policy_version == "interview-heuristic-v1"
        event_types = set(
            db.execute(
                select(EventOutbox.event_type).where(
                    EventOutbox.event_type.in_(
                        ["evaluation.run_started", "evaluation.run_completed"]
                    )
                )
            )
            .scalars()
            .all()
        )
        assert event_types == {"evaluation.run_started", "evaluation.run_completed"}


def test_evaluation_runs_are_company_scoped_and_role_protected() -> None:
    init_db()
    client = TestClient(main_module.app)
    _, owner_headers = signup(client)
    _, other_headers = signup(client)
    _, manager_headers = signup(client, role="hiring_manager")

    created = client.post("/api/v1/evaluations/runs", headers=owner_headers)
    assert created.status_code == 200
    run_id = created.json()["id"]

    hidden = client.get(f"/api/v1/evaluations/runs/{run_id}", headers=other_headers)
    assert hidden.status_code == 404

    forbidden = client.post("/api/v1/evaluations/runs", headers=manager_headers)
    assert forbidden.status_code == 403
