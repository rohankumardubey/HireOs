from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    Candidate,
    CandidateJobMatch,
    Company,
    Interview,
    InterviewReport,
    Job,
    RecruiterDecision,
    WebhookDelivery,
    WebhookDeliveryStatus,
)
from app.services.secret_crypto import SecretCryptoService


class ATSWebhookExportService:
    DEFAULT_EXPORT_STAGES = ["shortlisted", "moved_to_next_round", "hired"]

    def __init__(self) -> None:
        self.secret_crypto = SecretCryptoService()

    def status(self, company: Company) -> dict[str, Any]:
        config = self._settings(company)
        endpoint_url = config.get("endpoint_url") or None
        export_stages = self._normalize_export_stages(config.get("export_stages"))
        return {
            "configured": bool(endpoint_url),
            "enabled": bool(config.get("enabled") and endpoint_url),
            "provider_label": config.get("provider_label") or "ATS webhook",
            "endpoint_url": endpoint_url,
            "export_stages": export_stages,
            "has_auth_token": bool(config.get("auth_token")),
            "has_signing_secret": bool(config.get("signing_secret")),
        }

    def update(
        self,
        company: Company,
        *,
        enabled: bool,
        endpoint_url: str | None,
        provider_label: str | None,
        export_stages: list[str] | None,
        auth_token: str | None,
        signing_secret: str | None,
    ) -> dict[str, Any]:
        config = self._settings(company)
        config["enabled"] = enabled
        config["endpoint_url"] = endpoint_url
        config["provider_label"] = (provider_label or "ATS webhook").strip() or "ATS webhook"
        config["export_stages"] = self._normalize_export_stages(export_stages)

        if auth_token is not None:
            token = auth_token.strip()
            if token:
                config["auth_token"] = self.secret_crypto.encrypt(token)
            else:
                config.pop("auth_token", None)

        if signing_secret is not None:
            secret = signing_secret.strip()
            if secret:
                config["signing_secret"] = self.secret_crypto.encrypt(secret)
            else:
                config.pop("signing_secret", None)

        company.settings_json = self._with_settings(company, config)
        return self.status(company)

    def send_test_event(self, db: Session, *, company: Company, recruiter_id: str | None) -> WebhookDelivery:
        config = self._settings(company)
        endpoint_url = config.get("endpoint_url")
        if not endpoint_url:
            raise ValueError("Configure an ATS webhook endpoint URL before sending a test export.")

        payload = {
            "event_id": str(uuid4()),
            "event_type": "candidate.shortlisted",
            "source": "hireos-ai",
            "exported_at": datetime.now(UTC).isoformat(),
            "company": {"id": company.id, "name": company.name, "slug": company.slug},
            "job": {"id": "demo-job", "title": "Demo role"},
            "candidate": {"id": "demo-candidate", "name": "Demo Candidate", "email": "candidate@example.com"},
            "decision": {
                "decision": "shortlisted",
                "notes": "This is a connectivity check from HireOS AI.",
                "override_ai_recommendation": False,
                "recorded_at": datetime.now(UTC).isoformat(),
            },
            "ai_assessment": {
                "match_score": 86,
                "ai_recommendation": "strong_match",
                "human_review_required": True,
                "explanation": "AI scores are decision-support signals and should be reviewed by a human recruiter.",
            },
            "compliance": {
                "human_in_the_loop": True,
                "disclaimer": "This export reflects a recruiter-approved pipeline step and should not be treated as an automated rejection or hiring decision.",
            },
        }
        return self._dispatch_delivery(
            db,
            company_id=company.id,
            interview_id=None,
            candidate_id=None,
            job_id=None,
            recruiter_id=recruiter_id,
            event_name="candidate.shortlisted",
            config=config,
            payload=payload,
            metadata={"trigger": "test"},
        )

    def maybe_export_for_decision(
        self,
        db: Session,
        *,
        company: Company,
        interview: Interview,
        decision: RecruiterDecision,
        recruiter_id: str | None,
    ) -> tuple[str, WebhookDelivery | None]:
        status = self.status(company)
        if decision.decision not in status["export_stages"]:
            return ("not_enabled_for_stage", None)
        if not status["enabled"]:
            return ("not_configured", None)
        delivery = self.send_candidate_export(
            db,
            company=company,
            interview=interview,
            decision=decision,
            recruiter_id=recruiter_id,
            trigger="automatic",
        )
        return ("attempted", delivery)

    def send_candidate_export(
        self,
        db: Session,
        *,
        company: Company,
        interview: Interview,
        decision: RecruiterDecision,
        recruiter_id: str | None,
        trigger: str,
    ) -> WebhookDelivery:
        config = self._settings(company)
        endpoint_url = config.get("endpoint_url")
        if not endpoint_url:
            raise ValueError("Configure an ATS webhook endpoint URL before exporting candidates.")

        payload = self._build_candidate_payload(db, company=company, interview=interview, decision=decision)
        return self._dispatch_delivery(
            db,
            company_id=company.id,
            interview_id=interview.id,
            candidate_id=interview.candidate_id,
            job_id=interview.job_id,
            recruiter_id=recruiter_id,
            event_name=f"candidate.{decision.decision}",
            config=config,
            payload=payload,
            metadata={"trigger": trigger, "decision": decision.decision},
        )

    def list_deliveries(self, db: Session, *, interview_id: str) -> list[WebhookDelivery]:
        return (
            db.execute(
                select(WebhookDelivery)
                .where(WebhookDelivery.interview_id == interview_id, WebhookDelivery.integration_name == "ats_webhook")
                .order_by(WebhookDelivery.created_at.desc())
            )
            .scalars()
            .all()
        )

    def _dispatch_delivery(
        self,
        db: Session,
        *,
        company_id: str,
        interview_id: str | None,
        candidate_id: str | None,
        job_id: str | None,
        recruiter_id: str | None,
        event_name: str,
        config: dict[str, Any],
        payload: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> WebhookDelivery:
        request_body = json.dumps(payload)
        delivery = WebhookDelivery(
            company_id=company_id,
            interview_id=interview_id,
            candidate_id=candidate_id,
            job_id=job_id,
            recruiter_id=recruiter_id,
            event_name=event_name,
            target_url=config["endpoint_url"],
            provider=config.get("provider_label") or "ATS webhook",
            request_body=request_body,
            metadata_json=metadata or {},
        )
        db.add(delivery)
        db.flush()

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "HireOS-AI/1.0",
            "X-HireOS-Event": event_name,
            "X-HireOS-Delivery-Id": delivery.id,
        }
        auth_token = self.secret_crypto.decrypt(config.get("auth_token"))
        signing_secret = self.secret_crypto.decrypt(config.get("signing_secret"))
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        if signing_secret:
            signature = hmac.new(signing_secret.encode("utf-8"), request_body.encode("utf-8"), hashlib.sha256).hexdigest()
            headers["X-HireOS-Signature"] = f"sha256={signature}"

        try:
            with httpx.Client(timeout=settings.ats_webhook_timeout_seconds) as client:
                response = client.post(config["endpoint_url"], content=request_body, headers=headers)
            delivery.response_status_code = response.status_code
            delivery.response_body = response.text[:4000]
            if 200 <= response.status_code < 300:
                delivery.status = WebhookDeliveryStatus.delivered.value
            else:
                delivery.status = WebhookDeliveryStatus.failed.value
                delivery.error_message = f"Webhook returned status {response.status_code}"
        except Exception as exc:
            delivery.status = WebhookDeliveryStatus.failed.value
            delivery.error_message = str(exc)
        return delivery

    def _build_candidate_payload(
        self,
        db: Session,
        *,
        company: Company,
        interview: Interview,
        decision: RecruiterDecision,
    ) -> dict[str, Any]:
        candidate = db.get(Candidate, interview.candidate_id)
        job = db.get(Job, interview.job_id)
        match = db.execute(
            select(CandidateJobMatch).where(
                CandidateJobMatch.candidate_id == interview.candidate_id,
                CandidateJobMatch.job_id == interview.job_id,
            )
        ).scalar_one_or_none()
        report = db.execute(select(InterviewReport).where(InterviewReport.interview_id == interview.id)).scalar_one_or_none()

        return {
            "event_id": str(uuid4()),
            "event_type": f"candidate.{decision.decision}",
            "source": "hireos-ai",
            "exported_at": datetime.now(UTC).isoformat(),
            "company": {
                "id": company.id,
                "name": company.name,
                "slug": company.slug,
            },
            "job": {
                "id": interview.job_id,
                "title": getattr(job, "title", "Unknown role"),
                "department": getattr(job, "department", None),
                "location": getattr(job, "location", None),
                "status": getattr(job, "status", None),
            },
            "candidate": {
                "id": interview.candidate_id,
                "name": candidate.name if candidate else "Unknown candidate",
                "email": candidate.email if candidate else None,
                "phone": candidate.phone if candidate else None,
                "location": candidate.location if candidate else None,
                "current_role": candidate.current_role if candidate else None,
                "current_company": candidate.current_company if candidate else None,
                "years_experience": candidate.years_experience if candidate else None,
                "skills": list((candidate.parsed_profile or {}).get("skills", [])) if candidate else [],
                "profile_summary": candidate.profile_summary if candidate else None,
                "status": candidate.status if candidate else decision.decision,
            },
            "decision": {
                "decision": decision.decision,
                "notes": decision.notes,
                "override_ai_recommendation": decision.override_ai_recommendation,
                "recorded_at": decision.created_at.isoformat(),
            },
            "ai_assessment": {
                "match_score": match.overall_score if match else None,
                "ai_recommendation": match.match_recommendation if match else None,
                "matched_required_skills": match.matched_required_skills if match else [],
                "missing_required_skills": match.missing_required_skills if match else [],
                "matched_preferred_skills": match.matched_preferred_skills if match else [],
                "human_review_required": (
                    report.human_review_required
                    if report
                    else (match.human_review_required if match else True)
                ),
                "confidence_score": match.confidence_score if match else None,
                "explanation": match.explanation if match else None,
            },
            "interview": {
                "id": interview.id,
                "type": interview.interview_type,
                "mode": interview.mode,
                "status": interview.status,
                "started_at": interview.started_at.isoformat() if interview.started_at else None,
                "completed_at": interview.completed_at.isoformat() if interview.completed_at else None,
                "average_score": (interview.summary_json or {}).get("average_score"),
                "questions_answered": (interview.summary_json or {}).get("questions_answered"),
            },
            "report": {
                "recommended_next_step": report.recommended_next_step if report else None,
                "human_review_required": report.human_review_required if report else True,
                "audit_trail_length": len(report.audit_trail) if report else 0,
                "summary_excerpt": (report.report_markdown[:400] if report and report.report_markdown else None),
            },
            "compliance": {
                "human_in_the_loop": True,
                "disclaimer": "AI-generated scores are decision-support signals and should be reviewed by a human recruiter.",
            },
        }

    def _normalize_export_stages(self, export_stages: list[str] | None) -> list[str]:
        stages = [stage for stage in (export_stages or self.DEFAULT_EXPORT_STAGES) if stage]
        deduped: list[str] = []
        for stage in stages:
            if stage not in deduped:
                deduped.append(stage)
        return deduped or list(self.DEFAULT_EXPORT_STAGES)

    def _settings(self, company: Company) -> dict[str, Any]:
        return dict((company.settings_json or {}).get("integrations", {}).get("ats_webhook") or {})

    def _with_settings(self, company: Company, ats_settings: dict[str, Any]) -> dict[str, Any]:
        settings_json = dict(company.settings_json or {})
        integrations = dict(settings_json.get("integrations") or {})
        integrations["ats_webhook"] = ats_settings
        settings_json["integrations"] = integrations
        return settings_json
