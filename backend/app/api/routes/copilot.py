from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user, get_primary_membership
from app.schemas import CopilotQueryRequest, CopilotResponse
from app.services.copilot import RecruiterCopilotService

router = APIRouter(prefix="/copilot", tags=["copilot"])
copilot = RecruiterCopilotService()


@router.post("/query", response_model=CopilotResponse)
def recruiter_copilot_query(
    payload: CopilotQueryRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CopilotResponse:
    membership = get_primary_membership(current_user, db)
    result = copilot.answer_query(
        db,
        company_id=membership.company_id,
        query=payload.query,
        job_id=payload.job_id,
        candidate_ids=payload.candidate_ids,
    )
    return CopilotResponse(**result)

