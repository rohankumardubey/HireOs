from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Candidate, Interview, InterviewStatus, Job, NotificationDelivery, NotificationStatus
from app.schemas import ReminderCandidatePreview
from app.services.email_delivery import InterviewEmailDeliveryService


@dataclass
class DueReminder:
    interview: Interview
    candidate: Candidate
    job: Job
    reminder_type: str
    reminder_reason: str
    last_activity_at: datetime
    reminder_attempts: int


class InterviewReminderAutomationService:
    def __init__(self) -> None:
        self.email_delivery = InterviewEmailDeliveryService()

    def preview_due_reminders(self, db: Session, *, company_id: str) -> list[DueReminder]:
        interviews = db.execute(
            select(Interview, Candidate, Job)
            .join(Candidate, Candidate.id == Interview.candidate_id)
            .join(Job, Job.id == Interview.job_id)
            .where(Interview.company_id == company_id)
            .order_by(Interview.created_at.asc())
        ).all()

        due: list[DueReminder] = []
        now = datetime.now(UTC)
        for interview, candidate, job in interviews:
            summary = interview.summary_json or {}
            schedule_type = str(summary.get("schedule_type", "adhoc"))
            is_due, reminder_type, reminder_reason, last_activity_at, attempts = self._evaluate_due(
                db=db,
                interview=interview,
                candidate=candidate,
                schedule_type=schedule_type,
                now=now,
            )
            if not is_due or not reminder_type or not reminder_reason or not last_activity_at:
                continue
            due.append(
                DueReminder(
                    interview=interview,
                    candidate=candidate,
                    job=job,
                    reminder_type=reminder_type,
                    reminder_reason=reminder_reason,
                    last_activity_at=last_activity_at,
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
                interview_id=item.interview.id,
                candidate_id=item.candidate.id,
                recruiter_id=recruiter_id,
                recipient_email=item.candidate.email,
                subject=subject,
                body_text=body,
                notification_type=item.reminder_type,
                metadata={
                    "reminder_reason": item.reminder_reason,
                    "job_title": item.job.title,
                    "last_activity_at": self._ensure_utc(item.last_activity_at).isoformat(),
                },
            )
            deliveries.append(delivery)
        return deliveries

    def to_preview_schema(self, item: DueReminder) -> ReminderCandidatePreview:
        return ReminderCandidatePreview(
            interview_id=item.interview.id,
            candidate_id=item.candidate.id,
            candidate_name=item.candidate.name,
            candidate_email=item.candidate.email,
            job_id=item.job.id,
            job_title=item.job.title,
            reminder_type=item.reminder_type,
            reminder_reason=item.reminder_reason,
            last_activity_at=self._ensure_utc(item.last_activity_at),
            reminder_attempts=item.reminder_attempts,
        )

    def _evaluate_due(
        self,
        *,
        db: Session,
        interview: Interview,
        candidate: Candidate,
        schedule_type: str,
        now: datetime,
    ) -> tuple[bool, str | None, str | None, datetime | None, int]:
        created_at = self._ensure_utc(interview.created_at)
        started_at = self._ensure_utc(interview.started_at) if interview.started_at else None
        last_activity_at = started_at or created_at

        if interview.status == InterviewStatus.completed.value:
            return False, None, None, None, 0

        reminder_type = None
        reminder_reason = None
        threshold_hours = 0

        if interview.status == InterviewStatus.invited.value:
            reminder_type = "interview_no_show_reminder"
            reminder_reason = (
                "Candidate has not started the interview after the invite window elapsed."
                if schedule_type != "scheduled"
                else "Candidate has not joined or started the scheduled interview workflow."
            )
            threshold_hours = settings.interview_invite_reminder_after_hours
        elif interview.status == InterviewStatus.started.value:
            reminder_type = "interview_completion_reminder"
            reminder_reason = "Candidate started the interview but has not completed it."
            threshold_hours = settings.interview_incomplete_reminder_after_hours
        else:
            return False, None, None, None, 0

        if now < (last_activity_at + timedelta(hours=threshold_hours)):
            return False, None, None, last_activity_at, 0

        attempts, last_sent_at = self._reminder_history(db, interview.id, reminder_type)
        if attempts >= settings.interview_reminder_max_attempts:
            return False, None, None, last_activity_at, attempts
        if last_sent_at and now < (last_sent_at + timedelta(hours=settings.interview_reminder_cooldown_hours)):
            return False, None, None, last_activity_at, attempts

        return True, reminder_type, reminder_reason, last_activity_at, attempts

    def _reminder_history(self, db: Session, interview_id: str, reminder_type: str) -> tuple[int, datetime | None]:
        rows = db.execute(
            select(NotificationDelivery)
            .where(
                NotificationDelivery.interview_id == interview_id,
                NotificationDelivery.notification_type == reminder_type,
                NotificationDelivery.status.in_([NotificationStatus.delivered.value, NotificationStatus.fallback.value]),
            )
            .order_by(NotificationDelivery.created_at.desc())
        ).scalars().all()
        if not rows:
            return 0, None
        return len(rows), self._ensure_utc(rows[0].created_at)

    def _build_message(self, item: DueReminder) -> tuple[str, str]:
        portal_url = f"{settings.public_app_url.rstrip('/')}/interview/{item.interview.id}"
        if item.reminder_type == "interview_no_show_reminder":
            subject = f"Reminder: complete your HireOS interview for {item.job.title}"
            body = (
                f"Hi {item.candidate.name},\n\n"
                f"This is a reminder to start your HireOS interview for the {item.job.title} role.\n\n"
                f"Interview link: {portal_url}\n\n"
                "If you need more time or an accommodation, please reply to the recruiter.\n\n"
                "Best,\nHireOS AI Recruiting"
            )
            return subject, body

        subject = f"Reminder: finish your HireOS interview for {item.job.title}"
        body = (
            f"Hi {item.candidate.name},\n\n"
            f"You started your HireOS interview for the {item.job.title} role but have not completed it yet.\n\n"
            f"Resume where you left off: {portal_url}\n\n"
            "Please finish the interview when you can, or reply to the recruiter if you need help.\n\n"
            "Best,\nHireOS AI Recruiting"
        )
        return subject, body

    def _ensure_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
