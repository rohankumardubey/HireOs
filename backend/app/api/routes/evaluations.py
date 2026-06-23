from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import EvaluationRun
from app.db.session import get_db
from app.dependencies.auth import get_current_user, get_primary_membership, require_roles
from app.schemas import EvaluationRunListRead, EvaluationRunRead
from app.services.evaluations import EvaluationService
from app.services.events import EventPublisher, log_audit
from app.services.scoring import SCORING_POLICY_VERSION

router = APIRouter(prefix="/evaluations", tags=["evaluations"])
evaluation_service = EvaluationService()
events = EventPublisher()


def serialize_run(evaluation_run: EvaluationRun) -> EvaluationRunRead:
    return EvaluationRunRead.model_validate(evaluation_run)


@router.post("/runs", response_model=EvaluationRunRead)
def create_evaluation_run(
    current_user=Depends(require_roles("admin", "recruiter")),
    db: Session = Depends(get_db),
) -> EvaluationRunRead:
    membership = get_primary_membership(current_user, db)
    baseline = evaluation_service.latest_completed_run(db, membership.company_id)
    evaluation_run = EvaluationRun(
        company_id=membership.company_id,
        triggered_by_id=current_user.id,
        dataset_name=evaluation_service.dataset_path.name,
        dataset_version="pending",
        scoring_policy_version=SCORING_POLICY_VERSION,
        provider=evaluation_service.scorer.llm.provider,
        status="running",
        baseline_run_id=baseline.id if baseline else None,
    )
    db.add(evaluation_run)
    db.flush()
    events.publish(
        db,
        event_type="evaluation.run_started",
        topic_name="hireos.evaluation.run_started",
        company_id=membership.company_id,
        actor_id=current_user.id,
        actor_type="recruiter",
        payload={
            "evaluation_run_id": evaluation_run.id,
            "dataset_name": evaluation_run.dataset_name,
            "scoring_policy_version": evaluation_run.scoring_policy_version,
        },
    )
    db.commit()

    try:
        summary = evaluation_service.evaluate_dataset(baseline)
        evaluation_service.persist_results(
            db,
            evaluation_run=evaluation_run,
            summary=summary,
        )
        evaluation_run.status = "completed"
        evaluation_run.completed_at = datetime.now(UTC).replace(tzinfo=None)
        events.publish(
            db,
            event_type="evaluation.run_completed",
            topic_name="hireos.evaluation.run_completed",
            company_id=membership.company_id,
            actor_id=current_user.id,
            actor_type="recruiter",
            payload={
                "evaluation_run_id": evaluation_run.id,
                "quality_status": summary.quality_status,
                "total_cases": summary.total_cases,
                "strong_pass_rate": summary.strong_pass_rate,
                "weak_rejection_rate": summary.weak_rejection_rate,
                "regression_count": summary.regression_count,
            },
        )
        if summary.regression_count:
            events.publish(
                db,
                event_type="evaluation.regression_detected",
                topic_name="hireos.evaluation.regression_detected",
                company_id=membership.company_id,
                actor_id=current_user.id,
                actor_type="system",
                payload={
                    "evaluation_run_id": evaluation_run.id,
                    "baseline_run_id": evaluation_run.baseline_run_id,
                    "regression_count": summary.regression_count,
                },
            )
        log_audit(
            db,
            current_user.id,
            "evaluation_run",
            evaluation_run.id,
            "evaluation.run_completed",
            {
                "quality_status": summary.quality_status,
                "total_cases": summary.total_cases,
                "regression_count": summary.regression_count,
            },
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        evaluation_run = db.get(EvaluationRun, evaluation_run.id)
        if evaluation_run:
            evaluation_run.status = "failed"
            evaluation_run.quality_status = "failed"
            evaluation_run.error_message = str(exc)
            evaluation_run.completed_at = datetime.now(UTC).replace(tzinfo=None)
            db.commit()
        raise HTTPException(status_code=422, detail=f"Evaluation run failed: {exc}") from exc

    completed = db.execute(
        select(EvaluationRun)
        .options(selectinload(EvaluationRun.case_results))
        .where(EvaluationRun.id == evaluation_run.id)
    ).scalar_one()
    return serialize_run(completed)


@router.get("/runs", response_model=EvaluationRunListRead)
def list_evaluation_runs(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EvaluationRunListRead:
    membership = get_primary_membership(current_user, db)
    runs = (
        db.execute(
            select(EvaluationRun)
            .options(selectinload(EvaluationRun.case_results))
            .where(EvaluationRun.company_id == membership.company_id)
            .order_by(EvaluationRun.created_at.desc())
        )
        .scalars()
        .all()
    )
    serialized = [serialize_run(run) for run in runs]
    return EvaluationRunListRead(
        runs=serialized,
        latest=serialized[0] if serialized else None,
        policy_note=(
            "Golden-set results are regression signals, not proof of model fairness or production readiness. "
            "Review failed cases and expand the dataset before changing scoring policy."
        ),
    )


@router.get("/runs/{run_id}", response_model=EvaluationRunRead)
def get_evaluation_run(
    run_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EvaluationRunRead:
    membership = get_primary_membership(current_user, db)
    evaluation_run = db.execute(
        select(EvaluationRun)
        .options(selectinload(EvaluationRun.case_results))
        .where(
            EvaluationRun.id == run_id,
            EvaluationRun.company_id == membership.company_id,
        )
    ).scalar_one_or_none()
    if not evaluation_run:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    return serialize_run(evaluation_run)
