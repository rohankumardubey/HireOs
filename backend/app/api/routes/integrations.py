from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Company
from app.db.session import get_db
from app.dependencies.auth import get_current_user, get_primary_membership, require_roles
from app.schemas import (
    ATSWebhookExportResponse,
    ATSWebhookStatus,
    ATSWebhookUpdateRequest,
    GoogleConnectResponse,
    GoogleIntegrationStatus,
    WebhookDeliveryRead,
)
from app.services.ats_webhooks import ATSWebhookExportService
from app.services.google_calendar import GoogleCalendarIntegrationService

router = APIRouter(prefix="/integrations", tags=["integrations"])
google = GoogleCalendarIntegrationService()
ats_webhooks = ATSWebhookExportService()


@router.get("/google/status", response_model=GoogleIntegrationStatus)
def google_status(current_user=Depends(get_current_user), db: Session = Depends(get_db)) -> GoogleIntegrationStatus:
    membership = get_primary_membership(current_user, db)
    company = db.get(Company, membership.company_id)
    return GoogleIntegrationStatus(**google.status(company))


@router.post("/google/connect", response_model=GoogleConnectResponse)
def connect_google(
    current_user=Depends(require_roles("admin", "recruiter")),
    db: Session = Depends(get_db),
) -> GoogleConnectResponse:
    if not google.is_configured():
        raise HTTPException(status_code=400, detail="Google OAuth is not configured on this environment")
    membership = get_primary_membership(current_user, db)
    return GoogleConnectResponse(
        authorization_url=google.build_auth_url(company_id=membership.company_id, user_id=current_user.id)
    )


@router.delete("/google")
def disconnect_google(
    current_user=Depends(require_roles("admin", "recruiter")),
    db: Session = Depends(get_db),
) -> dict:
    membership = get_primary_membership(current_user, db)
    company = db.get(Company, membership.company_id)
    google.disconnect(db, company)
    return {"status": "disconnected"}


@router.get("/google/callback")
def google_callback(code: str = Query(...), state: str = Query(...), db: Session = Depends(get_db)) -> RedirectResponse:
    try:
        result = google.complete_oauth(db, code=code, state=state)
        params = urlencode({"google": "connected", "email": result.get("email", "")})
    except Exception as exc:
        params = urlencode({"google": "error", "message": str(exc)})
    return RedirectResponse(url=f"{settings.public_app_url.rstrip('/')}/settings?{params}", status_code=302)


@router.get("/ats-webhook/status", response_model=ATSWebhookStatus)
def ats_webhook_status(
    current_user=Depends(require_roles("admin", "recruiter", "hiring_manager")),
    db: Session = Depends(get_db),
) -> ATSWebhookStatus:
    membership = get_primary_membership(current_user, db)
    company = db.get(Company, membership.company_id)
    return ATSWebhookStatus(**ats_webhooks.status(company))


@router.patch("/ats-webhook", response_model=ATSWebhookStatus)
def update_ats_webhook(
    payload: ATSWebhookUpdateRequest,
    current_user=Depends(require_roles("admin", "recruiter")),
    db: Session = Depends(get_db),
) -> ATSWebhookStatus:
    membership = get_primary_membership(current_user, db)
    company = db.get(Company, membership.company_id)
    endpoint_url = str(payload.endpoint_url) if payload.endpoint_url else None
    if payload.enabled and not endpoint_url:
        raise HTTPException(status_code=400, detail="An endpoint URL is required before enabling ATS webhook export.")
    status = ats_webhooks.update(
        company,
        enabled=payload.enabled,
        endpoint_url=endpoint_url,
        provider_label=payload.provider_label,
        export_stages=payload.export_stages,
        auth_token=payload.auth_token,
        signing_secret=payload.signing_secret,
    )
    db.commit()
    db.refresh(company)
    return ATSWebhookStatus(**status)


@router.post("/ats-webhook/test", response_model=ATSWebhookExportResponse)
def test_ats_webhook(
    current_user=Depends(require_roles("admin", "recruiter")),
    db: Session = Depends(get_db),
) -> ATSWebhookExportResponse:
    membership = get_primary_membership(current_user, db)
    company = db.get(Company, membership.company_id)
    try:
        delivery = ats_webhooks.send_test_event(db, company=company, recruiter_id=current_user.id)
        db.commit()
        db.refresh(delivery)
        return ATSWebhookExportResponse(status=delivery.status, delivery=WebhookDeliveryRead.model_validate(delivery))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
