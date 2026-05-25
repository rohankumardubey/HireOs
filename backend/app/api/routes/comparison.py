from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user, get_primary_membership
from app.schemas import CandidateComparisonRequest, CandidateComparisonResponse
from app.services.comparison import CandidateComparisonService

router = APIRouter(prefix="/comparison", tags=["comparison"])
service = CandidateComparisonService()


@router.post("/jobs/{job_id}", response_model=CandidateComparisonResponse)
def compare_candidates_for_job(
    job_id: str,
    payload: CandidateComparisonRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CandidateComparisonResponse:
    membership = get_primary_membership(current_user, db)
    try:
        result = service.compare(
            db,
            company_id=membership.company_id,
            job_id=job_id,
            candidate_ids=payload.candidate_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CandidateComparisonResponse(**result)

