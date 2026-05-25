from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import AuditLog, Candidate, CandidateJobMatch, EventOutbox, Interview, Job, RecruiterDecision, User
from app.schemas import (
    CandidateReviewWorkspaceRead,
    InterviewRead,
    MatchResultRead,
    RecruiterDecisionRead,
    ReportRead,
    ReviewTimelineEntry,
)


class CandidateReviewWorkspaceService:
    def build(self, db: Session, *, candidate_id: str, job_id: str) -> CandidateReviewWorkspaceRead | None:
        candidate = db.get(Candidate, candidate_id)
        job = db.get(Job, job_id)
        if not candidate or not job:
            return None

        match = db.execute(
            select(CandidateJobMatch)
            .where(CandidateJobMatch.candidate_id == candidate_id, CandidateJobMatch.job_id == job_id)
            .order_by(CandidateJobMatch.created_at.desc())
        ).scalar_one_or_none()

        interview = db.execute(
            select(Interview)
            .options(selectinload(Interview.report))
            .where(Interview.candidate_id == candidate_id, Interview.job_id == job_id)
            .order_by(Interview.created_at.desc())
        ).scalar_one_or_none()

        decision_rows = db.execute(
            select(RecruiterDecision, User.full_name)
            .join(User, User.id == RecruiterDecision.recruiter_id)
            .where(RecruiterDecision.candidate_id == candidate_id, RecruiterDecision.job_id == job_id)
            .order_by(RecruiterDecision.created_at.desc())
        ).all()
        decisions = [
            RecruiterDecisionRead(
                id=decision.id,
                decision=decision.decision,
                notes=decision.notes,
                override_ai_recommendation=decision.override_ai_recommendation,
                recruiter_id=decision.recruiter_id,
                recruiter_name=recruiter_name,
                created_at=decision.created_at,
            )
            for decision, recruiter_name in decision_rows
        ]

        audit_ids = {candidate.id, job.id}
        if match:
            audit_ids.add(match.id)
        if interview:
            audit_ids.add(interview.id)
            if interview.report:
                audit_ids.add(interview.report.id)
        audit_ids.update(decision.id for decision, _ in decision_rows)

        actor_ids = {actor_id for actor_id in [candidate.owner_id, *(decision.recruiter_id for decision, _ in decision_rows)] if actor_id}
        audit_logs = db.execute(
            select(AuditLog).where(AuditLog.entity_id.in_(audit_ids)).order_by(AuditLog.created_at.desc())
        ).scalars().all()
        actor_ids.update(log.actor_id for log in audit_logs if log.actor_id)

        users = db.execute(select(User).where(User.id.in_(actor_ids))).scalars().all() if actor_ids else []
        user_labels = {user.id: user.full_name for user in users}

        timeline: list[ReviewTimelineEntry] = []

        for log in audit_logs:
            timeline.append(
                ReviewTimelineEntry(
                    timestamp=self._ensure_utc(log.created_at),
                    source="audit",
                    action=log.action,
                    actor_label=user_labels.get(log.actor_id, "HireOS AI"),
                    summary=self._summarize_audit(log.action, log.after_json),
                    details=log.after_json or {},
                )
            )

        event_rows = db.execute(select(EventOutbox).order_by(EventOutbox.created_at.desc())).scalars().all()
        for event in event_rows:
            envelope = event.envelope or {}
            if envelope.get("candidate_id") != candidate_id or envelope.get("job_id") != job_id:
                continue
            if interview and envelope.get("interview_id") not in {None, interview.id}:
                continue
            timestamp = self._parse_timestamp(envelope.get("timestamp")) or event.created_at
            timeline.append(
                ReviewTimelineEntry(
                    timestamp=timestamp,
                    source="event",
                    action=envelope.get("event_type", event.event_type),
                    actor_label=self._actor_label(
                        actor_type=envelope.get("actor_type"),
                        actor_id=envelope.get("actor_id"),
                        candidate_name=candidate.name,
                        user_labels=user_labels,
                    ),
                    summary=self._summarize_event(envelope.get("event_type", event.event_type), envelope.get("payload") or {}),
                    details=envelope.get("payload") or {},
                )
            )

        report = interview.report if interview else None
        if report and report.audit_trail:
            for step in report.audit_trail:
                timeline.append(
                    ReviewTimelineEntry(
                        timestamp=self._ensure_utc(report.created_at),
                        source="report",
                        action=str(step.get("step", "report.step")),
                        actor_label="HireOS AI",
                        summary=self._summarize_report_step(step),
                        details=step,
                    )
                )

        timeline.sort(key=lambda item: item.timestamp, reverse=True)

        return CandidateReviewWorkspaceRead(
            candidate_id=candidate.id,
            job_id=job.id,
            job_title=job.title,
            status=candidate.status,
            latest_match=MatchResultRead.model_validate(match) if match else None,
            latest_interview=InterviewRead.model_validate(interview) if interview else None,
            latest_report=ReportRead.model_validate(report) if report else None,
            latest_decision=decisions[0] if decisions else None,
            decision_history=decisions,
            audit_timeline=timeline[:16],
            can_record_decision=interview is not None,
            decision_support_note=(
                "Recruiter decisions are the final workflow action. AI outputs remain decision-support signals, "
                "and every override should be documented with human reasoning."
            ),
        )

    def _actor_label(self, *, actor_type: str | None, actor_id: str | None, candidate_name: str, user_labels: dict[str, str]) -> str:
        if actor_type == "candidate":
            return candidate_name
        if actor_type == "recruiter" and actor_id:
            return user_labels.get(actor_id, "Recruiter")
        return "HireOS AI"

    def _summarize_event(self, event_type: str, payload: dict) -> str:
        summaries = {
            "resume.uploaded": "Resume uploaded for parsing.",
            "resume.parsed": "Resume was parsed into a structured candidate profile.",
            "candidate.matched": "AI resume-to-job match was recalculated.",
            "interview.invited": "Interview invitation was created and shared.",
            "interview.started": "Candidate started the interview session.",
            "question.generated": "Interview question set was generated.",
            "answer.submitted": "Candidate submitted an interview answer.",
            "answer.transcribed": "Voice response was transcribed into text.",
            "answer.scored": "A candidate answer was scored against the rubric.",
            "followup.generated": "Adaptive follow-up question was generated.",
            "interview.completed": "Interview was completed and locked for reporting.",
            "report.generated": "Recruiter report was generated from the interview.",
            "recruiter.decision_made": "Recruiter recorded a final pipeline decision.",
        }
        if event_type in summaries:
            return summaries[event_type]
        if payload.get("recommended_next_step"):
            return f"Report recommended next step: {payload['recommended_next_step']}."
        return event_type.replace(".", " ").replace("_", " ").title()

    def _summarize_audit(self, action: str, details: dict) -> str:
        if action == "resume.uploaded":
            return f"Resume file {details.get('file_name', 'upload')} was attached to the candidate profile."
        if action == "recruiter.decision_made":
            decision = str(details.get("decision", "review")).replace("_", " ")
            return f"Recruiter marked the candidate as {decision}."
        return action.replace(".", " ").replace("_", " ").title()

    def _summarize_report_step(self, step: dict) -> str:
        name = str(step.get("step", "review")).replace("_", " ")
        value = step.get("value")
        if value is None:
            return name.title()
        return f"{name.title()}: {value}"

    def _parse_timestamp(self, value: str | None) -> datetime | None:
        if not value:
            return None
        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed

    def _ensure_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
