from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status

from app.core.config import settings
from app.db.models import Interview


@dataclass
class CandidateAccessStatus:
    candidate_portal_url: str | None
    issued_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None
    revoked_reason: str | None
    is_active: bool
    is_expired: bool
    is_revoked: bool
    note: str


class InterviewAccessService:
    summary_key = "candidate_access"

    def issue_link(
        self,
        interview: Interview,
        *,
        ttl_hours: int | None = None,
    ) -> CandidateAccessStatus:
        now = datetime.now(UTC)
        expires_at = now + timedelta(hours=ttl_hours or settings.interview_magic_link_ttl_hours)
        payload = {
            "nonce": secrets.token_urlsafe(24),
            "issued_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "revoked_at": None,
            "revoked_by_id": None,
            "revoked_reason": None,
        }
        self._write_access_payload(interview, payload)
        return self.status(interview)

    def refresh_link(self, interview: Interview) -> CandidateAccessStatus:
        return self.issue_link(interview)

    def revoke_link(
        self,
        interview: Interview,
        *,
        actor_id: str | None,
        reason: str | None = None,
    ) -> CandidateAccessStatus:
        payload = self._access_payload(interview)
        if not payload:
            raise ValueError("No candidate access link has been issued for this interview yet.")

        payload["revoked_at"] = datetime.now(UTC).isoformat()
        payload["revoked_by_id"] = actor_id
        payload["revoked_reason"] = reason or "Revoked by recruiter"
        self._write_access_payload(interview, payload)
        return self.status(interview)

    def get_or_create_candidate_portal_url(
        self,
        interview: Interview,
        *,
        renew_if_missing: bool = True,
        renew_if_expired: bool = False,
    ) -> str:
        payload = self._access_payload(interview)
        if not payload:
            if not renew_if_missing:
                raise ValueError("Candidate access link is missing.")
            return self.issue_link(interview).candidate_portal_url or ""

        if payload.get("revoked_at"):
            raise ValueError("Candidate access link has been revoked. Refresh it before sharing again.")

        expires_at = self._parse_datetime(payload.get("expires_at"))
        if expires_at and expires_at <= datetime.now(UTC):
            if not renew_if_expired:
                raise ValueError("Candidate access link has expired. Refresh it before sharing again.")
            return self.refresh_link(interview).candidate_portal_url or ""

        token = self._build_token(interview.id, payload)
        return self._build_url(interview.id, token)

    def status(self, interview: Interview) -> CandidateAccessStatus:
        payload = self._access_payload(interview)
        if not payload:
            return CandidateAccessStatus(
                candidate_portal_url=None,
                issued_at=None,
                expires_at=None,
                revoked_at=None,
                revoked_reason=None,
                is_active=False,
                is_expired=False,
                is_revoked=False,
                note="Candidate access link has not been generated yet.",
            )

        issued_at = self._parse_datetime(payload.get("issued_at"))
        expires_at = self._parse_datetime(payload.get("expires_at"))
        revoked_at = self._parse_datetime(payload.get("revoked_at"))
        is_expired = bool(expires_at and expires_at <= datetime.now(UTC))
        is_revoked = revoked_at is not None
        is_active = not is_expired and not is_revoked

        if is_revoked:
            note = "Candidate access link was revoked and can no longer be used."
            candidate_portal_url = None
        elif is_expired:
            note = "Candidate access link expired and should be refreshed before sharing again."
            candidate_portal_url = None
        else:
            note = "Candidate access link is active."
            candidate_portal_url = self._build_url(interview.id, self._build_token(interview.id, payload))

        return CandidateAccessStatus(
            candidate_portal_url=candidate_portal_url,
            issued_at=issued_at,
            expires_at=expires_at,
            revoked_at=revoked_at,
            revoked_reason=payload.get("revoked_reason"),
            is_active=is_active,
            is_expired=is_expired,
            is_revoked=is_revoked,
            note=note,
        )

    def require_valid_access(self, interview: Interview, token: str | None) -> None:
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="A valid candidate access link is required for this interview.",
            )

        payload = self._verify_token(token)
        if payload.get("interview_id") != interview.id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid candidate access link.")

        current = self._access_payload(interview)
        if not current or current.get("nonce") != payload.get("nonce"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="This interview link has been replaced. Please use the latest invitation.",
            )

        if current.get("revoked_at"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="This interview link has been revoked. Please contact the recruiter for a fresh invitation.",
            )

        expires_at = self._parse_datetime(current.get("expires_at"))
        if not expires_at or expires_at <= datetime.now(UTC):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="This interview link has expired. Please request a refreshed invitation from the recruiter.",
            )

    def _verify_token(self, token: str) -> dict[str, Any]:
        try:
            encoded_payload, encoded_sig = token.split(".", 1)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid candidate access link.") from exc

        expected_sig = self._sign(encoded_payload)
        if not hmac.compare_digest(expected_sig, encoded_sig):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid candidate access link.")

        try:
            payload_raw = self._b64decode(encoded_payload)
            payload = json.loads(payload_raw)
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid candidate access link.") from exc

        expires_at = self._parse_datetime(payload.get("expires_at"))
        if not expires_at or expires_at <= datetime.now(UTC):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="This interview link has expired. Please request a refreshed invitation from the recruiter.",
            )
        return payload

    def _build_token(self, interview_id: str, payload: dict[str, Any]) -> str:
        token_payload = {
            "interview_id": interview_id,
            "nonce": payload["nonce"],
            "issued_at": payload["issued_at"],
            "expires_at": payload["expires_at"],
        }
        encoded_payload = self._b64encode(json.dumps(token_payload, separators=(",", ":")).encode("utf-8"))
        signature = self._sign(encoded_payload)
        return f"{encoded_payload}.{signature}"

    def _build_url(self, interview_id: str, token: str) -> str:
        return f"{settings.public_app_url.rstrip('/')}/interview/{interview_id}?access={token}"

    def _access_payload(self, interview: Interview) -> dict[str, Any] | None:
        summary = interview.summary_json or {}
        payload = summary.get(self.summary_key)
        return deepcopy(payload) if isinstance(payload, dict) else None

    def _write_access_payload(self, interview: Interview, payload: dict[str, Any]) -> None:
        interview.summary_json = {
            **(interview.summary_json or {}),
            self.summary_key: payload,
        }

    def _parse_datetime(self, value: Any) -> datetime | None:
        if not value or not isinstance(value, str):
            return None
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    def _sign(self, encoded_payload: str) -> str:
        return hmac.new(
            settings.jwt_secret.encode("utf-8"),
            encoded_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _b64encode(self, value: bytes) -> str:
        return base64.urlsafe_b64encode(value).decode("utf-8").rstrip("=")

    def _b64decode(self, value: str) -> bytes:
        padding = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode(f"{value}{padding}")
