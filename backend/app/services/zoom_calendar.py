from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Company
from app.services.secret_crypto import SecretCryptoService


class ZoomCalendarIntegrationService:
    auth_endpoint = "https://zoom.us/oauth/authorize"
    token_endpoint = "https://zoom.us/oauth/token"
    user_endpoint = "https://api.zoom.us/v2/users/me"
    meeting_create_endpoint = "https://api.zoom.us/v2/users/me/meetings"

    def __init__(self) -> None:
        self.secret_crypto = SecretCryptoService()

    def is_configured(self) -> bool:
        return bool(settings.zoom_client_id and settings.zoom_client_secret and settings.zoom_oauth_redirect_uri)

    def build_auth_url(self, *, company_id: str, user_id: str) -> str:
        state = self._sign_state({"company_id": company_id, "user_id": user_id, "ts": datetime.now(UTC).timestamp()})
        params = {
            "response_type": "code",
            "client_id": settings.zoom_client_id,
            "redirect_uri": settings.zoom_oauth_redirect_uri,
            "state": state,
        }
        return f"{self.auth_endpoint}?{httpx.QueryParams(params)}"

    def complete_oauth(self, db: Session, *, code: str, state: str) -> dict:
        payload = self._verify_state(state)
        token_data = self._exchange_code_for_tokens(code)
        profile = self._fetch_profile(token_data["access_token"])
        company = db.get(Company, payload["company_id"])
        if not company:
            raise ValueError("Company not found for Zoom connection")

        zoom_settings = self._zoom_settings(company)
        zoom_settings.update(
            {
                "connected": True,
                "email": profile.get("email"),
                "user_id": profile.get("id"),
                "account_id": profile.get("account_id"),
                "access_token": self.secret_crypto.encrypt(token_data["access_token"]),
                "refresh_token": self.secret_crypto.encrypt(token_data.get("refresh_token"))
                or zoom_settings.get("refresh_token"),
                "token_type": token_data.get("token_type", "Bearer"),
                "scope": token_data.get("scope"),
                "expires_at": (
                    datetime.now(UTC) + timedelta(seconds=int(token_data.get("expires_in", 3600)))
                ).isoformat(),
            }
        )
        company.settings_json = self._with_zoom_settings(company, zoom_settings)
        db.commit()
        return {"company_id": company.id, "email": profile.get("email")}

    def disconnect(self, db: Session, company: Company) -> None:
        settings_json = dict(company.settings_json or {})
        integrations = dict(settings_json.get("integrations") or {})
        integrations.pop("zoom", None)
        settings_json["integrations"] = integrations
        company.settings_json = settings_json
        db.commit()

    def status(self, company: Company) -> dict:
        zoom_settings = self._zoom_settings(company)
        return {
            "configured": self.is_configured(),
            "connected": bool(zoom_settings.get("connected")),
            "email": zoom_settings.get("email"),
        }

    def create_meeting(
        self,
        db: Session,
        *,
        company: Company,
        candidate_email: str,
        candidate_name: str,
        recruiter_email: str,
        job_title: str,
        schedule_type: str,
        scheduled_at: datetime | None,
        candidate_portal_url: str,
    ) -> dict:
        access_token = self._valid_access_token(db, company)
        schedule = schedule_type.lower()
        start_at = scheduled_at.astimezone(UTC) if scheduled_at else datetime.now(UTC)
        payload = {
            "topic": f"HireOS live interview - {job_title}",
            "agenda": (
                f"Candidate: {candidate_name} ({candidate_email})\n"
                f"Recruiter: {recruiter_email}\n"
                f"HireOS workflow reference: {candidate_portal_url}\n\n"
                "AI-generated interview signals are decision-support only and should be reviewed by a human recruiter."
            ),
            "type": 2 if schedule == "scheduled" else 1,
            "duration": 45,
            "timezone": "UTC",
            "settings": {
                "join_before_host": False,
                "waiting_room": True,
                "participant_video": True,
                "host_video": True,
            },
        }
        if schedule == "scheduled":
            payload["start_time"] = start_at.isoformat()

        with httpx.Client(timeout=30) as client:
            response = client.post(
                self.meeting_create_endpoint,
                headers={"Authorization": f"Bearer {access_token}"},
                json=payload,
            )
            response.raise_for_status()
            meeting = response.json()

        join_url = meeting.get("join_url")
        if not join_url:
            raise ValueError("Zoom meeting was created but no join URL was returned")

        return {
            "meeting_join_url": join_url,
            "meeting_start_url": meeting.get("start_url"),
            "meeting_id": meeting.get("id"),
            "scheduled_at": (start_at.isoformat() if schedule == "scheduled" else None),
            "schedule_type": schedule,
        }

    def _exchange_code_for_tokens(self, code: str) -> dict:
        basic = base64.b64encode(f"{settings.zoom_client_id}:{settings.zoom_client_secret}".encode("utf-8")).decode("utf-8")
        with httpx.Client(timeout=30) as client:
            response = client.post(
                self.token_endpoint,
                params={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": settings.zoom_oauth_redirect_uri,
                },
                headers={"Authorization": f"Basic {basic}"},
            )
            response.raise_for_status()
            return response.json()

    def _refresh_access_token(self, refresh_token: str) -> dict:
        basic = base64.b64encode(f"{settings.zoom_client_id}:{settings.zoom_client_secret}".encode("utf-8")).decode("utf-8")
        with httpx.Client(timeout=30) as client:
            response = client.post(
                self.token_endpoint,
                params={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
                headers={"Authorization": f"Basic {basic}"},
            )
            response.raise_for_status()
            return response.json()

    def _fetch_profile(self, access_token: str) -> dict:
        with httpx.Client(timeout=30) as client:
            response = client.get(
                self.user_endpoint,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            return response.json()

    def _valid_access_token(self, db: Session, company: Company) -> str:
        zoom_settings = self._zoom_settings(company)
        access_token = self.secret_crypto.decrypt(zoom_settings.get("access_token"))
        expires_at = zoom_settings.get("expires_at")
        refresh_token = self.secret_crypto.decrypt(zoom_settings.get("refresh_token"))

        if access_token and expires_at:
            expires_dt = datetime.fromisoformat(expires_at)
            if expires_dt - timedelta(minutes=5) > datetime.now(UTC):
                return access_token

        if not refresh_token:
            raise ValueError("Zoom connection expired. Reconnect Zoom to auto-create meetings.")

        refreshed = self._refresh_access_token(refresh_token)
        zoom_settings.update(
            {
                "access_token": self.secret_crypto.encrypt(refreshed["access_token"]),
                "refresh_token": self.secret_crypto.encrypt(refreshed.get("refresh_token"))
                or zoom_settings.get("refresh_token"),
                "token_type": refreshed.get("token_type", "Bearer"),
                "scope": refreshed.get("scope"),
                "expires_at": (
                    datetime.now(UTC) + timedelta(seconds=int(refreshed.get("expires_in", 3600)))
                ).isoformat(),
                "connected": True,
            }
        )
        company.settings_json = self._with_zoom_settings(company, zoom_settings)
        db.commit()
        return refreshed["access_token"]

    def _zoom_settings(self, company: Company) -> dict:
        return dict((company.settings_json or {}).get("integrations", {}).get("zoom") or {})

    def _with_zoom_settings(self, company: Company, zoom_settings: dict) -> dict:
        settings_json = dict(company.settings_json or {})
        integrations = dict(settings_json.get("integrations") or {})
        integrations["zoom"] = zoom_settings
        settings_json["integrations"] = integrations
        return settings_json

    def _sign_state(self, payload: dict) -> str:
        encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
        signature = hmac.new(settings.jwt_secret.encode("utf-8"), encoded.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{encoded}.{signature}"

    def _verify_state(self, state: str) -> dict:
        try:
            encoded, signature = state.rsplit(".", 1)
        except ValueError as exc:
            raise ValueError("Invalid Zoom OAuth state") from exc

        expected = hmac.new(settings.jwt_secret.encode("utf-8"), encoded.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid Zoom OAuth state signature")

        payload = json.loads(base64.urlsafe_b64decode(encoded.encode("utf-8")).decode("utf-8"))
        issued_at = datetime.fromtimestamp(payload["ts"], tz=UTC)
        if datetime.now(UTC) - issued_at > timedelta(minutes=15):
            raise ValueError("Zoom OAuth state has expired")
        return payload
