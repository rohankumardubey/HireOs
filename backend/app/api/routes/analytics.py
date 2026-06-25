from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user, get_primary_membership
from app.schemas import AnalyticsOverview, ResponsibleAIDashboard
from app.services.analytics import get_funnel, get_job_metrics, get_model_quality, get_overview
from app.services.responsible_ai import build_responsible_ai_dashboard

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", response_model=AnalyticsOverview)
def overview(current_user=Depends(get_current_user), db: Session = Depends(get_db)) -> AnalyticsOverview:
    membership = get_primary_membership(current_user, db)
    return AnalyticsOverview(**get_overview(db, membership.company_id))


@router.get("/jobs/{job_id}")
def job_analytics(job_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    membership = get_primary_membership(current_user, db)
    return get_job_metrics(db, membership.company_id, job_id)


@router.get("/model-quality")
def model_quality(current_user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    membership = get_primary_membership(current_user, db)
    return get_model_quality(db, membership.company_id)


@router.get("/funnel")
def funnel(current_user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    membership = get_primary_membership(current_user, db)
    return get_funnel(db, membership.company_id)


@router.get("/responsible-ai", response_model=ResponsibleAIDashboard)
def responsible_ai(current_user=Depends(get_current_user), db: Session = Depends(get_db)) -> ResponsibleAIDashboard:
    membership = get_primary_membership(current_user, db)
    return ResponsibleAIDashboard(**build_responsible_ai_dashboard(db, membership.company_id))
