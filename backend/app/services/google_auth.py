from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.db.models import AuthExchangeCode, Company, CompanyMembership, UsageEvent, User
from app.schemas import UserRead
from app.services.events import EventPublisher, log_audit


class GoogleAuthService:
    auth_endpoint = "https://accounts.google.com/o/oauth2/v2/auth"
    token_endpoint = "https://oauth2.googleapis.com/token"
    userinfo_endpoint = "https://www.googleapis.com/oauth2/v2/userinfo"
    scopes = ["openid", "email", "profile"]

    def __init__(self) -> None:
        self.events = EventPublisher()

    def is_configured(self) -> bool:
        return bool(settings.google_client_id and settings.google_client_secret and settings.google_auth_redirect_uri)

    def build_auth_url(
        self,
        *,
        flow: str,
        company_name: str | None = None,
        full_name: str | None = None,
        role: str = "admin",
    ) -> str:
        state = self._sign_state(
            {
                "flow": flow,
                "company_name": (company_name or "").strip(),
                "full_name": (full_name or "").strip(),
                "role": role or "admin",
                "ts": datetime.now(UTC).timestamp(),
            }
        )
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.google_auth_redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "select_account",
            "state": state,
        }
        return f"{self.auth_endpoint}?{httpx.QueryParams(params)}"

    def complete_oauth(self, db: Session, *, code: str, state: str) -> dict:
        if not self.is_configured():
            raise ValueError("Google SSO is not configured")

        payload = self._verify_state(state)
        token_data = self._exchange_code_for_tokens(code)
        profile = self._fetch_profile(token_data["access_token"])
        email = (profile.get("email") or "").strip().lower()
        if not email:
            raise ValueError("Google did not return an email address")

        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        created_workspace = False
        company_name = payload.get("company_name") or self._default_company_name(email)
        full_name = payload.get("full_name") or profile.get("name") or email.split("@", 1)[0].replace(".", " ").title()
        role = payload.get("role") or "admin"

        if not user:
            company = self._create_company(db, company_name)
            user = User(
                full_name=full_name,
                email=email,
                hashed_password=get_password_hash(secrets.token_urlsafe(32)),
            )
            db.add(user)
            db.flush()
            db.add_all(
                [
                    CompanyMembership(company_id=company.id, user_id=user.id, role=role),
                    UsageEvent(company_id=company.id, event_name="google_signup", quantity=1, unit="account"),
                ]
            )
            created_workspace = True
            log_audit(db, user.id, "company", company.id, "company.created", {"name": company.name, "source": "google_sso"})
            self.events.publish(
                db,
                event_type="company.created",
                topic_name="hireos.company.created",
                company_id=company.id,
                actor_id=user.id,
                actor_type="admin",
                payload={"company_name": company.name, "source": "google_sso"},
            )
        else:
            if not user.full_name and full_name:
                user.full_name = full_name

            membership = db.execute(select(CompanyMembership).where(CompanyMembership.user_id == user.id)).scalar_one_or_none()
            if not membership:
                company = self._create_company(db, company_name)
                db.add_all(
                    [
                        CompanyMembership(company_id=company.id, user_id=user.id, role=role),
                        UsageEvent(company_id=company.id, event_name="google_signup", quantity=1, unit="account"),
                    ]
                )
                created_workspace = True
                log_audit(db, user.id, "company", company.id, "company.created", {"name": company.name, "source": "google_sso"})
                self.events.publish(
                    db,
                    event_type="company.created",
                    topic_name="hireos.company.created",
                    company_id=company.id,
                    actor_id=user.id,
                    actor_type="admin",
                    payload={"company_name": company.name, "source": "google_sso"},
                )

        db.commit()
        db.refresh(user)

        return {
            "user": UserRead.model_validate(user).model_dump(mode="json"),
            "flow": payload.get("flow", "login"),
            "created_workspace": created_workspace,
            "db": db,
        }

    def issue_exchange_code(self, db: Session, *, user_id: str, flow: str) -> str:
        raw_code = secrets.token_urlsafe(32)
        db.add(
            AuthExchangeCode(
                user_id=user_id,
                code_hash=self._hash_exchange_code(raw_code),
                expires_at=datetime.utcnow() + timedelta(minutes=5),
                flow=flow,
            )
        )
        db.commit()
        return raw_code

    def exchange_code(self, db: Session, *, code: str) -> dict:
        record = db.execute(
            select(AuthExchangeCode).where(AuthExchangeCode.code_hash == self._hash_exchange_code(code))
        ).scalar_one_or_none()
        if not record or record.used_at is not None or record.expires_at < datetime.utcnow():
            raise ValueError("Google sign-in code is invalid or expired")

        user = db.get(User, record.user_id)
        if not user:
            raise ValueError("User not found for sign-in exchange")

        record.used_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        return {
            "access_token": create_access_token(user.id),
            "token_type": "bearer",
            "user": UserRead.model_validate(user).model_dump(mode="json"),
            "flow": record.flow or "login",
        }

    def _exchange_code_for_tokens(self, code: str) -> dict:
        with httpx.Client(timeout=30) as client:
            response = client.post(
                self.token_endpoint,
                data={
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": settings.google_auth_redirect_uri,
                },
            )
            response.raise_for_status()
            return response.json()

    def _fetch_profile(self, access_token: str) -> dict:
        with httpx.Client(timeout=30) as client:
            response = client.get(
                self.userinfo_endpoint,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            return response.json()

    def _create_company(self, db: Session, company_name: str) -> Company:
        slug = self._unique_slug(db, company_name)
        company = Company(name=company_name, slug=slug)
        db.add(company)
        db.flush()
        return company

    def _unique_slug(self, db: Session, company_name: str) -> str:
        base = re.sub(r"[^a-z0-9]+", "-", company_name.lower()).strip("-") or "hireos-company"
        slug = base
        index = 2
        while db.execute(select(Company).where(Company.slug == slug)).scalar_one_or_none():
            slug = f"{base}-{index}"
            index += 1
        return slug

    def _default_company_name(self, email: str) -> str:
        domain = email.split("@", 1)[-1].split(".", 1)[0]
        label = domain.replace("-", " ").replace("_", " ").title() or "New Company"
        return f"{label} Hiring"

    def _sign_state(self, payload: dict) -> str:
        encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
        signature = hmac.new(settings.jwt_secret.encode("utf-8"), encoded.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{encoded}.{signature}"

    def _verify_state(self, state: str) -> dict:
        try:
            encoded, signature = state.rsplit(".", 1)
        except ValueError as exc:
            raise ValueError("Invalid OAuth state") from exc

        expected = hmac.new(settings.jwt_secret.encode("utf-8"), encoded.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid OAuth state signature")

        payload = json.loads(base64.urlsafe_b64decode(encoded.encode("utf-8")).decode("utf-8"))
        issued_at = datetime.fromtimestamp(payload["ts"], tz=UTC)
        if datetime.now(UTC) - issued_at > timedelta(minutes=15):
            raise ValueError("Google OAuth state has expired")
        return payload

    def build_callback_redirect(self, result: dict) -> str:
        exchange_code = self.issue_exchange_code(
            result["db"],
            user_id=result["user"]["id"],
            flow=result.get("flow", "login"),
        )
        params = urlencode(
            {
                "code": exchange_code,
                "flow": result.get("flow", "login"),
                "workspace": "created" if result.get("created_workspace") else "joined",
            }
        )
        return f"{settings.public_app_url}/auth/callback?{params}"

    def _hash_exchange_code(self, code: str) -> str:
        return hmac.new(settings.jwt_secret.encode("utf-8"), code.encode("utf-8"), hashlib.sha256).hexdigest()
