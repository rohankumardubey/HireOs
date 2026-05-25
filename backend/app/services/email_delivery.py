from __future__ import annotations

import json
import smtplib
from email.message import EmailMessage
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import NotificationDelivery, NotificationStatus


class InterviewEmailDeliveryService:
    def is_configured(self) -> bool:
        return bool(settings.smtp_host and settings.smtp_from_email)

    def send_notification(
        self,
        db: Session,
        *,
        company_id: str,
        interview_id: str | None,
        candidate_id: str | None,
        recruiter_id: str | None,
        recipient_email: str,
        subject: str,
        body_text: str,
        notification_type: str = "interview_invite",
        metadata: dict | None = None,
    ) -> NotificationDelivery:
        delivery = NotificationDelivery(
            company_id=company_id,
            interview_id=interview_id,
            candidate_id=candidate_id,
            recruiter_id=recruiter_id,
            recipient_email=recipient_email,
            subject=subject,
            body_text=body_text,
            notification_type=notification_type,
            metadata_json=metadata or {},
        )
        db.add(delivery)
        db.flush()

        if self.is_configured():
            try:
                self._send_via_smtp(recipient_email=recipient_email, subject=subject, body_text=body_text)
                delivery.provider = "smtp"
                delivery.status = NotificationStatus.delivered.value
                return delivery
            except Exception as exc:
                delivery.provider = "smtp"
                delivery.status = NotificationStatus.failed.value
                delivery.error_message = str(exc)
                return delivery

        self._write_fallback_file(delivery)
        delivery.provider = "file"
        delivery.status = NotificationStatus.fallback.value
        return delivery

    def send_interview_invite(
        self,
        db: Session,
        *,
        company_id: str,
        interview_id: str,
        candidate_id: str,
        recruiter_id: str,
        recipient_email: str,
        subject: str,
        body_text: str,
        metadata: dict | None = None,
    ) -> NotificationDelivery:
        return self.send_notification(
            db,
            company_id=company_id,
            interview_id=interview_id,
            candidate_id=candidate_id,
            recruiter_id=recruiter_id,
            recipient_email=recipient_email,
            subject=subject,
            body_text=body_text,
            notification_type="interview_invite",
            metadata=metadata,
        )

    def _send_via_smtp(self, *, recipient_email: str, subject: str, body_text: str) -> None:
        message = EmailMessage()
        sender = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
        message["From"] = sender
        message["To"] = recipient_email
        message["Subject"] = subject
        message.set_content(body_text)

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_username and settings.smtp_password:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)

    def _write_fallback_file(self, delivery: NotificationDelivery) -> Path:
        path = Path(settings.email_outbox_dir) / f"{delivery.id or uuid4()}.json"
        payload = {
            "delivery_id": delivery.id,
            "recipient_email": delivery.recipient_email,
            "subject": delivery.subject,
            "body_text": delivery.body_text,
            "metadata": delivery.metadata_json,
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path
