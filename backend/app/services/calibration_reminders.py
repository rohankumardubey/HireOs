from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CalibrationCase, Candidate, Job, NotificationDelivery, NotificationStatus, User
from app.schemas import CalibrationReminderPreviewRead
from app.services.email_delivery import InterviewEmailDeliveryService
from app.services.review_workspace import CandidateReviewWorkspaceService


@dataclass
class DueCalibrationReminder:
    calibration_case: CalibrationCase
    candidate: Candidate
    job: Job
    recipient: User
    priority: str
    consensus_status: str
    reminder_reason: str
    due_at: datetime
    sla_status: str
    reminder_attempts: int


class CalibrationReminderService:
    def __init__(self) -> None:
        self.email_delivery = InterviewEmailDeliveryService()
        self.review_workspace = CandidateReviewWorkspaceService()

    def preview_due_reminders(self, db: Session, *, company_id: str) -> list[DueCalibrationReminder]:
        rows = db.execute(
            select(CalibrationCase, Candidate, Job)
            .join(Candidate, Candidate.id == CalibrationCase.candidate_id)
            .join(Job, Job.id == CalibrationCase.job_id)
            .where(CalibrationCase.company_id == company_id)
            .order_by(CalibrationCase.updated_at.asc())
        ).all()

        due: list[DueCalibrationReminder] = []
        now = datetime.now(UTC)
        for calibration_case, candidate, job in rows:
            if calibration_case.status == "resolved":
                continue

            workspace = self.review_workspace.build(db, candidate_id=candidate.id, job_id=job.id)
            if not workspace or not workspace.calibration_case:
                continue

            case = workspace.calibration_case
            if case.sla_status not in {"overdue", "due_today"}:
                continue

            recipient = self._resolve_recipient(
                db,
                assigned_to_user_id=calibration_case.assigned_to_user_id,
                fallback_user_id=candidate.owner_id,
            )
            if not recipient:
                continue

            reminder_type = self._notification_type(calibration_case.id)
            attempts, last_sent_at = self._reminder_history(db, reminder_type)
            if attempts >= 2:
                continue
            if last_sent_at and now < (last_sent_at + timedelta(hours=12)):
                continue

            reminder_reason = (
                "Calibration case is overdue and still unresolved."
                if case.sla_status == "overdue"
                else "Calibration case is due today and still needs recruiter action."
            )
            due.append(
                DueCalibrationReminder(
                    calibration_case=calibration_case,
                    candidate=candidate,
                    job=job,
                    recipient=recipient,
                    priority=self._priority_label_from_consensus(workspace.decision_consensus.overall_status),
                    consensus_status=workspace.decision_consensus.overall_status,
                    reminder_reason=reminder_reason,
                    due_at=case.due_at or self._ensure_utc(calibration_case.updated_at),
                    sla_status=case.sla_status,
                    reminder_attempts=attempts,
                )
            )
        return due

    def send_due_reminders(self, db: Session, *, company_id: str, recruiter_id: str) -> list[NotificationDelivery]:
        deliveries: list[NotificationDelivery] = []
        for item in self.preview_due_reminders(db, company_id=company_id):
            subject, body = self._build_message(item)
            delivery = self.email_delivery.send_notification(
                db,
                company_id=company_id,
                interview_id=None,
                candidate_id=item.candidate.id,
                recruiter_id=recruiter_id,
                recipient_email=item.recipient.email,
                subject=subject,
                body_text=body,
                notification_type=self._notification_type(item.calibration_case.id),
                metadata={
                    "calibration_case_id": item.calibration_case.id,
                    "job_id": item.job.id,
                    "candidate_name": item.candidate.name,
                    "job_title": item.job.title,
                    "sla_status": item.sla_status,
                    "due_at": item.due_at.isoformat(),
                },
            )
            deliveries.append(delivery)
        return deliveries

    def to_preview_schema(self, item: DueCalibrationReminder) -> CalibrationReminderPreviewRead:
        return CalibrationReminderPreviewRead(
            calibration_case_id=item.calibration_case.id,
            candidate_id=item.candidate.id,
            candidate_name=item.candidate.name,
            job_id=item.job.id,
            job_title=item.job.title,
            recipient_user_id=item.recipient.id,
            recipient_name=item.recipient.full_name,
            recipient_email=item.recipient.email,
            priority=self._priority_label(item),
            consensus_status=item.consensus_status,
            reminder_reason=item.reminder_reason,
            due_at=item.due_at,
            sla_status=item.sla_status,
            reminder_attempts=item.reminder_attempts,
        )

    def _resolve_recipient(self, db: Session, *, assigned_to_user_id: str | None, fallback_user_id: str | None) -> User | None:
        if assigned_to_user_id:
            assigned = db.get(User, assigned_to_user_id)
            if assigned:
                return assigned
        if fallback_user_id:
            fallback = db.get(User, fallback_user_id)
            if fallback:
                return fallback
        return None

    def _build_message(self, item: DueCalibrationReminder) -> tuple[str, str]:
        subject = f"Calibration reminder: {item.candidate.name} for {item.job.title}"
        body = (
            f"Hi {item.recipient.full_name},\n\n"
            f"The calibration case for {item.candidate.name} ({item.job.title}) still needs recruiter action.\n\n"
            f"SLA status: {item.sla_status.replace('_', ' ')}\n"
            f"Due at: {item.due_at.isoformat()}\n"
            f"Consensus status: {item.consensus_status.replace('_', ' ')}\n"
            f"Reason: {item.reminder_reason}\n\n"
            "Open the HireOS calibration queue to review the case, update ownership, and capture the final resolution.\n\n"
            "Best,\nHireOS AI"
        )
        return subject, body

    def _notification_type(self, calibration_case_id: str) -> str:
        return f"calibration_case_reminder:{calibration_case_id}"

    def _reminder_history(self, db: Session, notification_type: str) -> tuple[int, datetime | None]:
        rows = db.execute(
            select(NotificationDelivery)
            .where(
                NotificationDelivery.notification_type == notification_type,
                NotificationDelivery.status.in_([NotificationStatus.delivered.value, NotificationStatus.fallback.value]),
            )
            .order_by(NotificationDelivery.created_at.desc())
        ).scalars().all()
        if not rows:
            return 0, None
        return len(rows), self._ensure_utc(rows[0].created_at)

    def _priority_label(self, item: DueCalibrationReminder) -> str:
        return self._priority_label_from_consensus(item.consensus_status)

    def _priority_label_from_consensus(self, consensus_status: str) -> str:
        if consensus_status == "conflicted":
            return "critical"
        if consensus_status == "mixed":
            return "high"
        return "medium"

    def _ensure_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
