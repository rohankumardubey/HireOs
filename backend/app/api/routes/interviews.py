from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.db.models import (
    AnswerScore,
    Candidate,
    CandidateJobMatch,
    Company,
    Interview,
    InterviewAnswer,
    NotificationDelivery,
    InterviewQuestion,
    InterviewReport,
    InterviewStatus,
    Job,
    RecruiterDecision,
)
from app.db.session import get_db
from app.dependencies.auth import get_current_user, get_primary_membership, require_roles
from app.schemas import (
    AnswerSubmitRequest,
    DecisionRequest,
    InterviewEmailSendResponse,
    InterviewInviteRequest,
    InterviewInviteResponse,
    InterviewQuestionRead,
    InterviewRead,
    InterviewStartRequest,
    NotificationDeliveryRead,
    ReminderPreviewResponse,
    ReminderRunResponse,
    ReportRead,
)
from app.services.email_delivery import InterviewEmailDeliveryService
from app.services.events import EventPublisher, log_audit
from app.services.google_calendar import GoogleCalendarIntegrationService
from app.services.interview_invites import InterviewInviteLinkBuilder
from app.services.interview_reminders import InterviewReminderAutomationService
from app.services.scoring import HiringIntelligenceService

router = APIRouter(prefix="/interviews", tags=["interviews"])
events = EventPublisher()
ai = HiringIntelligenceService()
invite_links = InterviewInviteLinkBuilder()
google_calendar = GoogleCalendarIntegrationService()
email_delivery = InterviewEmailDeliveryService()
reminder_automation = InterviewReminderAutomationService()


@router.post("/invite", response_model=InterviewInviteResponse)
def invite_candidate(
    payload: InterviewInviteRequest,
    current_user=Depends(require_roles("admin", "recruiter")),
    db: Session = Depends(get_db),
) -> InterviewInviteResponse:
    if payload.mode == "video" and payload.schedule_type == "scheduled" and not payload.scheduled_at:
        raise HTTPException(status_code=400, detail="Scheduled live interviews require a scheduled time")
    if payload.mode == "video" and payload.meeting_provider == "zoom" and not payload.meeting_join_url:
        raise HTTPException(status_code=400, detail="Live video interviews require a valid meeting join URL")
    candidate = db.execute(select(Candidate).options(selectinload(Candidate.skills)).where(Candidate.id == payload.candidate_id)).scalar_one_or_none()
    job = db.execute(select(Job).options(selectinload(Job.skills)).where(Job.id == payload.job_id)).scalar_one_or_none()
    if not candidate or not job:
        raise HTTPException(status_code=404, detail="Candidate or job not found")
    company = db.get(Company, job.company_id)
    interview = Interview(
        company_id=job.company_id,
        candidate_id=candidate.id,
        job_id=job.id,
        invited_by_id=current_user.id,
        interview_type=payload.interview_type,
        mode=payload.mode,
        status=InterviewStatus.invited.value,
        summary_json={
            "meeting_provider": payload.meeting_provider,
            "schedule_type": payload.schedule_type,
            "scheduled_at": payload.scheduled_at.isoformat() if payload.scheduled_at else None,
            "meeting_join_url": str(payload.meeting_join_url) if payload.meeting_join_url else None,
        },
    )
    db.add(interview)
    db.flush()
    candidate_portal_url = f"{settings.public_app_url.rstrip('/')}/interview/{interview.id}"
    meeting_join_url = str(payload.meeting_join_url) if payload.meeting_join_url else None
    if payload.mode == "video" and payload.meeting_provider == "google_meet" and not meeting_join_url:
        if not google_calendar.is_configured():
            raise HTTPException(status_code=400, detail="Google Meet auto-generation is not configured. Connect Google or paste a join URL.")
        try:
            event = google_calendar.create_meet_event(
                db,
                company=company,
                candidate_email=candidate.email,
                candidate_name=candidate.name,
                recruiter_email=current_user.email,
                job_title=job.title,
                schedule_type=payload.schedule_type,
                scheduled_at=payload.scheduled_at,
                candidate_portal_url=candidate_portal_url,
            )
            meeting_join_url = event["meeting_join_url"]
            interview.summary_json = {
                **(interview.summary_json or {}),
                "calendar_event_id": event["calendar_event_id"],
                "meeting_join_url": event["meeting_join_url"],
                "scheduled_at": event["scheduled_at"],
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    questions = ai.generate_interview_plan(candidate, job, payload.interview_type)
    for question in questions:
        db.add(InterviewQuestion(interview_id=interview.id, **question))
    candidate.status = "interview_invited"
    events.publish(
        db,
        event_type="interview.invited",
        topic_name="hireos.interview.invited",
        company_id=job.company_id,
        job_id=job.id,
        candidate_id=candidate.id,
        interview_id=interview.id,
        actor_id=current_user.id,
        actor_type="recruiter",
        payload={"interview_type": payload.interview_type, "mode": payload.mode},
    )
    events.publish(
        db,
        event_type="question.generated",
        topic_name="hireos.question.generated",
        company_id=job.company_id,
        job_id=job.id,
        candidate_id=candidate.id,
        interview_id=interview.id,
        actor_id=current_user.id,
        actor_type="system",
        payload={"count": len(questions)},
    )
    db.commit()
    db.refresh(interview)
    share_links = invite_links.build(
        mode=payload.mode,
        meeting_provider=payload.meeting_provider,
        schedule_type=payload.schedule_type,
        scheduled_at=payload.scheduled_at,
        meeting_join_url=meeting_join_url,
        candidate_name=candidate.name,
        candidate_email=candidate.email,
        job_title=job.title,
        candidate_portal_url=candidate_portal_url,
    )
    return InterviewInviteResponse(
        **InterviewRead.model_validate(interview).model_dump(),
        share_links=share_links,
    )


@router.post("/{interview_id}/send-email", response_model=InterviewEmailSendResponse)
def send_interview_email(
    interview_id: str,
    current_user=Depends(require_roles("admin", "recruiter", "hiring_manager")),
    db: Session = Depends(get_db),
) -> InterviewEmailSendResponse:
    interview = db.get(Interview, interview_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    candidate = db.get(Candidate, interview.candidate_id)
    job = db.get(Job, interview.job_id)
    if not candidate or not job:
        raise HTTPException(status_code=404, detail="Candidate or job not found")

    summary = interview.summary_json or {}
    scheduled_at = datetime.fromisoformat(summary["scheduled_at"]) if summary.get("scheduled_at") else None
    candidate_portal_url = f"{settings.public_app_url.rstrip('/')}/interview/{interview.id}"
    share_links = invite_links.build(
        mode=interview.mode,
        meeting_provider=summary.get("meeting_provider", "google_meet"),
        schedule_type=summary.get("schedule_type", "adhoc"),
        scheduled_at=scheduled_at,
        meeting_join_url=summary.get("meeting_join_url"),
        candidate_name=candidate.name,
        candidate_email=candidate.email,
        job_title=job.title,
        candidate_portal_url=candidate_portal_url,
    )

    delivery = email_delivery.send_interview_invite(
        db,
        company_id=interview.company_id,
        interview_id=interview.id,
        candidate_id=candidate.id,
        recruiter_id=current_user.id,
        recipient_email=candidate.email,
        subject=share_links["email_subject"],
        body_text=share_links["email_body"],
        metadata={
            "job_title": job.title,
            "candidate_portal_url": candidate_portal_url,
            "mode": interview.mode,
            "meeting_provider": share_links["meeting_provider"],
        },
    )
    if delivery.status == "failed":
        db.commit()
        raise HTTPException(status_code=502, detail=f"Invite email could not be delivered: {delivery.error_message}")
    try:
        events.publish(
            db,
            event_type="notification.sent",
            topic_name="hireos.notification.sent",
            company_id=interview.company_id,
            job_id=interview.job_id,
            candidate_id=interview.candidate_id,
            interview_id=interview.id,
            actor_id=current_user.id,
            actor_type="recruiter",
            payload={"channel": "email", "status": delivery.status, "provider": delivery.provider},
        )
        log_audit(
            db,
            current_user.id,
            "notification_delivery",
            delivery.id,
            "interview.email_sent",
            {"recipient_email": candidate.email, "status": delivery.status, "provider": delivery.provider},
        )
        db.commit()
        db.refresh(delivery)
        return InterviewEmailSendResponse(status=delivery.status, delivery=NotificationDeliveryRead.model_validate(delivery))
    except Exception as exc:
        db.commit()
        raise HTTPException(status_code=502, detail=f"Invite email could not be delivered: {exc}") from exc


@router.get("/reminders/preview", response_model=ReminderPreviewResponse)
def preview_interview_reminders(
    current_user=Depends(require_roles("admin", "recruiter", "hiring_manager")),
    db: Session = Depends(get_db),
) -> ReminderPreviewResponse:
    membership = get_primary_membership(current_user, db)
    due = reminder_automation.preview_due_reminders(db, company_id=membership.company_id)
    previews = [reminder_automation.to_preview_schema(item) for item in due]
    invited_no_show_count = sum(1 for item in previews if item.reminder_type == "interview_no_show_reminder")
    incomplete_count = sum(1 for item in previews if item.reminder_type == "interview_completion_reminder")
    return ReminderPreviewResponse(
        invited_no_show_count=invited_no_show_count,
        incomplete_count=incomplete_count,
        candidates=previews,
        policy_note=(
            "Reminder automation only nudges candidates who are overdue, respects cooldown windows, and stops after the configured max attempt count."
        ),
    )


@router.post("/reminders/run", response_model=ReminderRunResponse)
def run_interview_reminders(
    current_user=Depends(require_roles("admin", "recruiter", "hiring_manager")),
    db: Session = Depends(get_db),
) -> ReminderRunResponse:
    membership = get_primary_membership(current_user, db)
    deliveries = reminder_automation.send_due_reminders(db, company_id=membership.company_id, recruiter_id=current_user.id)
    for delivery in deliveries:
        events.publish(
            db,
            event_type="notification.sent",
            topic_name="hireos.notification.sent",
            company_id=delivery.company_id,
            candidate_id=delivery.candidate_id,
            interview_id=delivery.interview_id,
            actor_id=current_user.id,
            actor_type="recruiter",
            payload={"channel": delivery.channel, "status": delivery.status, "notification_type": delivery.notification_type},
        )
        log_audit(
            db,
            current_user.id,
            "notification_delivery",
            delivery.id,
            "interview.reminder_sent",
            {"recipient_email": delivery.recipient_email, "status": delivery.status, "notification_type": delivery.notification_type},
        )
    db.commit()
    return ReminderRunResponse(
        sent_count=sum(1 for delivery in deliveries if delivery.status == "delivered"),
        fallback_count=sum(1 for delivery in deliveries if delivery.status == "fallback"),
        failed_count=sum(1 for delivery in deliveries if delivery.status == "failed"),
        deliveries=[NotificationDeliveryRead.model_validate(delivery) for delivery in deliveries],
    )


@router.get("/{interview_id}/email-deliveries", response_model=list[NotificationDeliveryRead])
def list_interview_email_deliveries(
    interview_id: str,
    current_user=Depends(require_roles("admin", "recruiter", "hiring_manager")),
    db: Session = Depends(get_db),
) -> list[NotificationDeliveryRead]:
    rows = db.execute(
        select(NotificationDelivery)
        .where(NotificationDelivery.interview_id == interview_id)
        .order_by(NotificationDelivery.created_at.desc())
    ).scalars().all()
    return [NotificationDeliveryRead.model_validate(row) for row in rows]


@router.post("/{interview_id}/start", response_model=InterviewRead)
def start_interview(interview_id: str, payload: InterviewStartRequest, db: Session = Depends(get_db)) -> InterviewRead:
    interview = db.get(Interview, interview_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    interview.status = InterviewStatus.started.value
    interview.started_at = datetime.utcnow()
    interview.consent_given = payload.consent_given
    events.publish(
        db,
        event_type="interview.started",
        topic_name="hireos.interview.started",
        company_id=interview.company_id,
        job_id=interview.job_id,
        candidate_id=interview.candidate_id,
        interview_id=interview.id,
        actor_id=interview.candidate_id,
        actor_type="candidate",
        payload={"mode": interview.mode},
    )
    db.commit()
    db.refresh(interview)
    return InterviewRead.model_validate(interview)


@router.get("/{interview_id}/next-question", response_model=InterviewQuestionRead | dict)
def next_question(interview_id: str, db: Session = Depends(get_db)) -> InterviewQuestionRead | dict:
    interview = db.execute(select(Interview).options(selectinload(Interview.questions)).where(Interview.id == interview_id)).scalar_one_or_none()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    ordered_questions = sorted(interview.questions, key=lambda item: item.question_order)
    if interview.current_question_index >= len(ordered_questions):
        return {"done": True}
    question = ordered_questions[interview.current_question_index]
    return InterviewQuestionRead.model_validate(question)


@router.post("/{interview_id}/answers")
def submit_answer(interview_id: str, payload: AnswerSubmitRequest, db: Session = Depends(get_db)) -> dict:
    interview = db.execute(select(Interview).options(selectinload(Interview.questions)).where(Interview.id == interview_id)).scalar_one_or_none()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    question = db.get(InterviewQuestion, payload.question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    if payload.answer_mode == "voice" and not (payload.transcript_text or payload.answer_text):
        raise HTTPException(status_code=400, detail="Voice answers require a transcript or answer text")
    answer = InterviewAnswer(
        interview_id=interview.id,
        question_id=question.id,
        answer_text=payload.answer_text,
        transcript_text=payload.transcript_text,
        answer_mode=payload.answer_mode,
        latency_ms=payload.latency_ms,
    )
    db.add(answer)
    db.flush()
    score_result = ai.score_answer(question, payload.transcript_text or payload.answer_text)
    score = AnswerScore(answer_id=answer.id, **score_result)
    db.add(score)
    interview.current_question_index += 1
    candidate = db.get(Candidate, interview.candidate_id)
    if candidate:
        candidate.status = "human_review_required" if score.human_review_required else "ai_review_completed"
    events.publish(
        db,
        event_type="answer.submitted",
        topic_name="hireos.answer.submitted",
        company_id=interview.company_id,
        job_id=interview.job_id,
        candidate_id=interview.candidate_id,
        interview_id=interview.id,
        actor_id=interview.candidate_id,
        actor_type="candidate",
        payload={"question_id": question.id},
    )
    if payload.answer_mode == "voice" and payload.transcript_text:
        events.publish(
            db,
            event_type="answer.transcribed",
            topic_name="hireos.answer.transcribed",
            company_id=interview.company_id,
            job_id=interview.job_id,
            candidate_id=interview.candidate_id,
            interview_id=interview.id,
            actor_id=interview.id,
            actor_type="system",
            payload={
                "question_id": question.id,
                "transcript_length": len(payload.transcript_text.split()),
            },
        )
    events.publish(
        db,
        event_type="answer.scored",
        topic_name="hireos.answer.scored",
        company_id=interview.company_id,
        job_id=interview.job_id,
        candidate_id=interview.candidate_id,
        interview_id=interview.id,
        actor_id=interview.id,
        actor_type="system",
        payload=score_result,
    )
    if score.suggested_follow_up:
        events.publish(
            db,
            event_type="followup.generated",
            topic_name="hireos.followup.generated",
            company_id=interview.company_id,
            job_id=interview.job_id,
            candidate_id=interview.candidate_id,
            interview_id=interview.id,
            actor_id=interview.id,
            actor_type="system",
            payload={"question_id": question.id, "suggested_follow_up": score.suggested_follow_up},
        )
    db.commit()
    db.refresh(score)
    return {"score": score_result, "next_question_index": interview.current_question_index}


@router.post("/{interview_id}/complete", response_model=ReportRead)
def complete_interview(interview_id: str, db: Session = Depends(get_db)) -> ReportRead:
    interview = db.execute(
        select(Interview)
        .options(selectinload(Interview.answers).selectinload(InterviewAnswer.score), selectinload(Interview.questions))
        .where(Interview.id == interview_id)
    ).scalar_one_or_none()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    candidate = db.get(Candidate, interview.candidate_id)
    job = db.get(Job, interview.job_id)
    match_result = db.execute(
        select(CandidateJobMatch).where(CandidateJobMatch.candidate_id == interview.candidate_id, CandidateJobMatch.job_id == interview.job_id)
    ).scalar_one_or_none()
    scores = [answer.score for answer in interview.answers if answer.score]
    report_payload = ai.build_report(interview, candidate, job, match_result, scores)
    report = interview.report or InterviewReport(interview_id=interview.id, **report_payload)
    if interview.report:
        for field, value in report_payload.items():
            setattr(report, field, value)
    else:
        db.add(report)
    interview.status = InterviewStatus.completed.value
    interview.completed_at = datetime.utcnow()
    interview.summary_json = {
        "average_score": round(sum(score.total_score for score in scores) / max(len(scores), 1), 2) if scores else 0,
        "questions_answered": len(interview.answers),
    }
    if candidate:
        candidate.status = "interview_completed"
    events.publish(
        db,
        event_type="interview.completed",
        topic_name="hireos.interview.completed",
        company_id=interview.company_id,
        job_id=interview.job_id,
        candidate_id=interview.candidate_id,
        interview_id=interview.id,
        actor_id=interview.candidate_id,
        actor_type="candidate",
        payload=interview.summary_json,
    )
    events.publish(
        db,
        event_type="report.generated",
        topic_name="hireos.report.generated",
        company_id=interview.company_id,
        job_id=interview.job_id,
        candidate_id=interview.candidate_id,
        interview_id=interview.id,
        actor_id=interview.id,
        actor_type="system",
        payload={"recommended_next_step": report_payload["recommended_next_step"]},
    )
    db.commit()
    db.refresh(report)
    return ReportRead.model_validate(report)


@router.get("/{interview_id}/report", response_model=ReportRead)
def get_interview_report(interview_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)) -> ReportRead:
    report = db.execute(select(InterviewReport).where(InterviewReport.interview_id == interview_id)).scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return ReportRead.model_validate(report)


@router.post("/{interview_id}/decision")
def recruiter_decision(
    interview_id: str,
    payload: DecisionRequest,
    current_user=Depends(require_roles("admin", "recruiter", "hiring_manager")),
    db: Session = Depends(get_db),
) -> dict:
    interview = db.get(Interview, interview_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    decision = RecruiterDecision(
        interview_id=interview.id,
        candidate_id=interview.candidate_id,
        job_id=interview.job_id,
        recruiter_id=current_user.id,
        decision=payload.decision,
        notes=payload.notes,
        override_ai_recommendation=payload.override_ai_recommendation,
    )
    db.add(decision)
    db.flush()
    candidate = db.get(Candidate, interview.candidate_id)
    if candidate:
        candidate.status = payload.decision
    log_audit(db, current_user.id, "recruiter_decision", decision.id, "recruiter.decision_made", payload.model_dump())
    events.publish(
        db,
        event_type="recruiter.decision_made",
        topic_name="hireos.recruiter.decision_made",
        company_id=interview.company_id,
        job_id=interview.job_id,
        candidate_id=interview.candidate_id,
        interview_id=interview.id,
        actor_id=current_user.id,
        actor_type="recruiter",
        payload=payload.model_dump(),
    )
    db.commit()
    return {"status": "ok"}
