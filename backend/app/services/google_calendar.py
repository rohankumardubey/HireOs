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


class GoogleCalendarIntegrationService:
    auth_endpoint = "https://accounts.google.com/o/oauth2/v2/auth"
    token_endpoint = "https://oauth2.googleapis.com/token"
    userinfo_endpoint = "https://www.googleapis.com/oauth2/v2/userinfo"
    events_endpoint = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
    scopes = [
      "openid",
      "email",
      "https://www.googleapis.com/auth/calendar.events",
    ]

    def __init__(self) -> None:
        self.secret_crypto = SecretCryptoService()

    def is_configured(self) -> bool:
        return bool(settings.google_client_id and settings.google_client_secret and settings.google_oauth_redirect_uri)

    def build_auth_url(self, *, company_id: str, user_id: str) -> str:
        state = self._sign_state({"company_id": company_id, "user_id": user_id, "ts": datetime.now(UTC).timestamp()})
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.google_oauth_redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "consent",
            "state": state,
        }
        return f"{self.auth_endpoint}?{httpx.QueryParams(params)}"

    def complete_oauth(self, db: Session, *, code: str, state: str) -> dict:
        payload = self._verify_state(state)
        token_data = self._exchange_code_for_tokens(code)
        profile = self._fetch_profile(token_data["access_token"])
        company = db.get(Company, payload["company_id"])
        if not company:
            raise ValueError("Company not found for Google connection")

        google_settings = self._google_settings(company)
        google_settings.update(
            {
                "connected": True,
                "email": profile.get("email"),
                "access_token": self.secret_crypto.encrypt(token_data["access_token"]),
                "refresh_token": self.secret_crypto.encrypt(token_data.get("refresh_token"))
                or google_settings.get("refresh_token"),
                "token_type": token_data.get("token_type", "Bearer"),
                "scope": token_data.get("scope"),
                "expires_at": (
                    datetime.now(UTC) + timedelta(seconds=int(token_data.get("expires_in", 3600)))
                ).isoformat(),
            }
        )
        company.settings_json = self._with_google_settings(company, google_settings)
        db.commit()
        return {"company_id": company.id, "email": profile.get("email")}

    def disconnect(self, db: Session, company: Company) -> None:
        settings_json = dict(company.settings_json or {})
        integrations = dict(settings_json.get("integrations") or {})
        integrations.pop("google", None)
        settings_json["integrations"] = integrations
        company.settings_json = settings_json
        db.commit()

    def status(self, company: Company) -> dict:
        google_settings = self._google_settings(company)
        return {
            "configured": self.is_configured(),
            "connected": bool(google_settings.get("connected")),
            "email": google_settings.get("email"),
        }

    def create_meet_event(
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
        start_at = scheduled_at.astimezone(UTC) if scheduled_at else datetime.now(UTC)
        end_at = start_at + timedelta(minutes=45)

        payload = {
            "summary": f"HireOS live interview - {job_title}",
            "description": (
                f"Candidate: {candidate_name}\n"
                f"Candidate email: {candidate_email}\n"
                f"Recruiter: {recruiter_email}\n"
                f"HireOS workflow reference: {candidate_portal_url}\n\n"
                "AI-generated signals are decision-support only and should be reviewed by a human recruiter."
            ),
            "start": {"dateTime": start_at.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": end_at.isoformat(), "timeZone": "UTC"},
            "attendees": [{"email": candidate_email}],
            "conferenceData": {
                "createRequest": {
                    "requestId": str(uuid4()),
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            },
        }

        with httpx.Client(timeout=30) as client:
            response = client.post(
                f"{self.events_endpoint}?conferenceDataVersion=1&sendUpdates=all",
                headers={"Authorization": f"Bearer {access_token}"},
                json=payload,
            )
            response.raise_for_status()
            event = response.json()

        join_url = event.get("hangoutLink")
        if not join_url:
            for entry in event.get("conferenceData", {}).get("entryPoints", []):
                if entry.get("entryPointType") == "video" and entry.get("uri"):
                    join_url = entry["uri"]
                    break
        if not join_url:
            raise ValueError("Google event was created but no Meet join URL was returned")

        return {
            "meeting_join_url": join_url,
            "calendar_event_id": event.get("id"),
            "scheduled_at": start_at.isoformat(),
            "schedule_type": schedule_type,
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
                    "redirect_uri": settings.google_oauth_redirect_uri,
                },
            )
            response.raise_for_status()
            return response.json()

    def _refresh_access_token(self, refresh_token: str) -> dict:
        with httpx.Client(timeout=30) as client:
            response = client.post(
                self.token_endpoint,
                data={
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
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

    def _valid_access_token(self, db: Session, company: Company) -> str:
        google_settings = self._google_settings(company)
        access_token = self.secret_crypto.decrypt(google_settings.get("access_token"))
        expires_at = google_settings.get("expires_at")
        refresh_token = self.secret_crypto.decrypt(google_settings.get("refresh_token"))

        if access_token and expires_at:
            expires_dt = datetime.fromisoformat(expires_at)
            if expires_dt - timedelta(minutes=5) > datetime.now(UTC):
                return access_token

        if not refresh_token:
            raise ValueError("Google Calendar connection expired. Reconnect Google to generate Meet links.")

        refreshed = self._refresh_access_token(refresh_token)
        google_settings.update(
            {
                "access_token": self.secret_crypto.encrypt(refreshed["access_token"]),
                "token_type": refreshed.get("token_type", "Bearer"),
                "scope": refreshed.get("scope"),
                "expires_at": (
                    datetime.now(UTC) + timedelta(seconds=int(refreshed.get("expires_in", 3600)))
                ).isoformat(),
                "connected": True,
            }
        )
        company.settings_json = self._with_google_settings(company, google_settings)
        db.commit()
        return refreshed["access_token"]

    def _google_settings(self, company: Company) -> dict:
        return dict((company.settings_json or {}).get("integrations", {}).get("google") or {})

    def _with_google_settings(self, company: Company, google_settings: dict) -> dict:
        settings_json = dict(company.settings_json or {})
        integrations = dict(settings_json.get("integrations") or {})
        integrations["google"] = google_settings
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
            raise ValueError("Invalid OAuth state") from exc

        expected = hmac.new(settings.jwt_secret.encode("utf-8"), encoded.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid OAuth state signature")

        payload = json.loads(base64.urlsafe_b64decode(encoded.encode("utf-8")).decode("utf-8"))
        issued_at = datetime.fromtimestamp(payload["ts"], tz=UTC)
        if datetime.now(UTC) - issued_at > timedelta(minutes=15):
            raise ValueError("Google OAuth state has expired")
        return payload
