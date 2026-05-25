from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.models import Company
from app.db.session import get_db
from app.dependencies.auth import get_current_user, get_primary_membership
from app.schemas import CompanyRead, CompanyUpdate
from app.services.company_settings import sanitize_company_settings

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("/me", response_model=CompanyRead)
def get_my_company(current_user=Depends(get_current_user), db: Session = Depends(get_db)) -> CompanyRead:
    membership = get_primary_membership(current_user, db)
    company = db.get(Company, membership.company_id)
    payload = CompanyRead.model_validate(company)
    return payload.model_copy(update={"settings_json": sanitize_company_settings(company.settings_json)})


@router.patch("/me", response_model=CompanyRead)
def update_my_company(payload: CompanyUpdate, current_user=Depends(get_current_user), db: Session = Depends(get_db)) -> CompanyRead:
    membership = get_primary_membership(current_user, db)
    company = db.get(Company, membership.company_id)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(company, field, value)
    db.commit()
    db.refresh(company)
    response = CompanyRead.model_validate(company)
    return response.model_copy(update={"settings_json": sanitize_company_settings(company.settings_json)})
