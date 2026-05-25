from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, get_password_hash, session_cookie_settings, verify_password
from app.db.models import Company, CompanyMembership, UsageEvent, User
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.schemas import GoogleAuthExchangeRequest, GoogleAuthStartRequest, GoogleAuthStartResponse, Token, UserLogin, UserRead, UserSignup
from app.services.events import EventPublisher, log_audit
from app.services.google_auth import GoogleAuthService

router = APIRouter(prefix="/auth", tags=["auth"])
events = EventPublisher()
google_auth = GoogleAuthService()


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(value=token, **session_cookie_settings())


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(session_cookie_settings()["key"], path="/", samesite=settings.session_cookie_samesite)


@router.post("/signup", response_model=Token)
def signup(payload: UserSignup, response: Response, db: Session = Depends(get_db)) -> Token:
    existing = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")
    company = Company(name=payload.company_name, slug=payload.company_name.lower().replace(" ", "-"))
    user = User(full_name=payload.full_name, email=payload.email, hashed_password=get_password_hash(payload.password))
    db.add_all([company, user])
    db.flush()
    membership = CompanyMembership(company_id=company.id, user_id=user.id, role=payload.role)
    usage = UsageEvent(company_id=company.id, event_name="signup", quantity=1, unit="account")
    db.add_all([membership, usage])
    log_audit(db, user.id, "company", company.id, "company.created", {"name": company.name})
    events.publish(
        db,
        event_type="company.created",
        topic_name="hireos.company.created",
        company_id=company.id,
        actor_id=user.id,
        actor_type="admin",
        payload={"company_name": company.name},
    )
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id)
    set_session_cookie(response, token)
    return Token(access_token=token, user=UserRead.model_validate(user))


@router.post("/login", response_model=Token)
def login(payload: UserLogin, response: Response, db: Session = Depends(get_db)) -> Token:
    user = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(user.id)
    set_session_cookie(response, token)
    return Token(access_token=token, user=UserRead.model_validate(user))


@router.post("/google/start", response_model=GoogleAuthStartResponse)
def start_google_auth(payload: GoogleAuthStartRequest) -> GoogleAuthStartResponse:
    if not google_auth.is_configured():
        raise HTTPException(
            status_code=400,
            detail="Google SSO is not configured. Add GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_AUTH_REDIRECT_URI.",
        )
    return GoogleAuthStartResponse(
        authorization_url=google_auth.build_auth_url(
            flow=payload.flow,
            company_name=payload.company_name,
            full_name=payload.full_name,
            role=payload.role,
        )
    )


@router.get("/google/callback")
def google_callback(code: str = Query(...), state: str = Query(...), db: Session = Depends(get_db)) -> RedirectResponse:
    try:
        result = google_auth.complete_oauth(db, code=code, state=state)
        return RedirectResponse(url=google_auth.build_callback_redirect(result))
    except Exception as exc:
        params = urlencode({"auth": "error", "message": str(exc)})
        return RedirectResponse(url=f"{settings.public_app_url}/login?{params}")


@router.post("/google/exchange", response_model=Token)
def exchange_google_auth(
    payload: GoogleAuthExchangeRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> Token:
    result = google_auth.exchange_code(db, code=payload.code)
    set_session_cookie(response, result["access_token"])
    return Token(access_token=result["access_token"], user=UserRead.model_validate(result["user"]))


@router.post("/logout")
def logout(response: Response) -> dict[str, str]:
    clear_session_cookie(response)
    return {"status": "signed_out"}


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)
