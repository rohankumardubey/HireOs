from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    AuditLog,
    Candidate,
    CandidateJobMatch,
    EventOutbox,
    HiringManagerFeedback,
    Interview,
    Job,
    RecruiterDecision,
    User,
)
from app.schemas import (
    CalibrationQueueEntryRead,
    CalibrationQueueRead,
    CandidateReviewWorkspaceRead,
    DecisionConsensusRead,
    DecisionConsensusSignalRead,
    HiringManagerFeedbackRead,
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
        ).scalars().first()

        interview = db.execute(
            select(Interview)
            .options(selectinload(Interview.report))
            .where(Interview.candidate_id == candidate_id, Interview.job_id == job_id)
            .order_by(Interview.created_at.desc())
        ).scalars().first()

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
        manager_feedback_rows = db.execute(
            select(HiringManagerFeedback, User.full_name)
            .join(User, User.id == HiringManagerFeedback.hiring_manager_id)
            .where(HiringManagerFeedback.candidate_id == candidate_id, HiringManagerFeedback.job_id == job_id)
            .order_by(HiringManagerFeedback.created_at.desc())
        ).all()
        manager_feedback = [
            HiringManagerFeedbackRead(
                id=feedback.id,
                recommendation=feedback.recommendation,
                notes=feedback.notes,
                recommended_next_round=feedback.recommended_next_round,
                hiring_manager_id=feedback.hiring_manager_id,
                hiring_manager_name=manager_name,
                created_at=feedback.created_at,
            )
            for feedback, manager_name in manager_feedback_rows
        ]

        audit_ids = {candidate.id, job.id}
        if match:
            audit_ids.add(match.id)
        if interview:
            audit_ids.add(interview.id)
            if interview.report:
                audit_ids.add(interview.report.id)
        audit_ids.update(decision.id for decision, _ in decision_rows)
        audit_ids.update(feedback.id for feedback, _ in manager_feedback_rows)

        actor_ids = {
            actor_id
            for actor_id in [
                candidate.owner_id,
                *(decision.recruiter_id for decision, _ in decision_rows),
                *(feedback.hiring_manager_id for feedback, _ in manager_feedback_rows),
            ]
            if actor_id
        }
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
        decision_consensus = self._build_decision_consensus(
            match=match,
            report=report,
            latest_manager_feedback=manager_feedback[0] if manager_feedback else None,
            latest_decision=decisions[0] if decisions else None,
        )

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
            latest_manager_feedback=manager_feedback[0] if manager_feedback else None,
            manager_feedback_history=manager_feedback,
            decision_consensus=decision_consensus,
            audit_timeline=timeline[:16],
            can_record_decision=interview is not None,
            can_record_manager_feedback=interview is not None,
            decision_support_note=(
                "Recruiter decisions are the final workflow action. Hiring managers can add recommendation notes, "
                "but AI outputs remain decision-support signals and every override should be documented with human reasoning."
            ),
        )

    def build_calibration_queue(self, db: Session, *, company_id: str) -> CalibrationQueueRead:
        pair_keys: set[tuple[str, str]] = set()

        match_pairs = db.execute(
            select(CandidateJobMatch.candidate_id, CandidateJobMatch.job_id)
            .join(Candidate, Candidate.id == CandidateJobMatch.candidate_id)
            .where(Candidate.company_id == company_id)
        ).all()
        interview_pairs = db.execute(
            select(Interview.candidate_id, Interview.job_id).where(Interview.company_id == company_id)
        ).all()

        pair_keys.update((candidate_id, job_id) for candidate_id, job_id in match_pairs)
        pair_keys.update((candidate_id, job_id) for candidate_id, job_id in interview_pairs)

        entries: list[CalibrationQueueEntryRead] = []
        for candidate_id, job_id in pair_keys:
            workspace = self.build(db, candidate_id=candidate_id, job_id=job_id)
            if not workspace:
                continue

            candidate = db.get(Candidate, candidate_id)
            if not candidate:
                continue

            priority = self._calibration_priority(workspace)
            if not priority:
                continue

            latest_signal_at = (
                workspace.audit_timeline[0].timestamp
                if workspace.audit_timeline
                else self._ensure_utc(candidate.updated_at)
            )

            entries.append(
                CalibrationQueueEntryRead(
                    candidate_id=candidate.id,
                    candidate_name=candidate.name,
                    candidate_email=candidate.email,
                    candidate_status=workspace.status,
                    current_role=candidate.current_role,
                    job_id=workspace.job_id,
                    job_title=workspace.job_title,
                    ai_recommendation=workspace.latest_match.match_recommendation if workspace.latest_match else None,
                    recruiter_decision=workspace.latest_decision.decision if workspace.latest_decision else None,
                    hiring_manager_recommendation=(
                        workspace.latest_manager_feedback.recommendation if workspace.latest_manager_feedback else None
                    ),
                    consensus_status=workspace.decision_consensus.overall_status,
                    agreement_score=workspace.decision_consensus.agreement_score,
                    requires_escalation=workspace.decision_consensus.requires_escalation,
                    priority=priority,
                    recommended_next_step=workspace.latest_report.recommended_next_step if workspace.latest_report else None,
                    conflict_reasons=workspace.decision_consensus.conflict_reasons,
                    latest_signal_at=latest_signal_at,
                )
            )

        priority_rank = {"critical": 0, "high": 1, "medium": 2}
        entries.sort(
            key=lambda item: (
                priority_rank.get(item.priority, 99),
                item.agreement_score,
                -item.latest_signal_at.timestamp(),
            )
        )

        return CalibrationQueueRead(
            total_items=len(entries),
            conflicted_count=sum(1 for entry in entries if entry.consensus_status == "conflicted"),
            mixed_count=sum(1 for entry in entries if entry.consensus_status == "mixed"),
            pending_count=sum(1 for entry in entries if entry.consensus_status == "pending"),
            entries=entries,
        )

    def _build_decision_consensus(
        self,
        *,
        match: CandidateJobMatch | None,
        report,
        latest_manager_feedback: HiringManagerFeedbackRead | None,
        latest_decision: RecruiterDecisionRead | None,
    ) -> DecisionConsensusRead:
        signals: list[DecisionConsensusSignalRead] = []
        if match:
            ai_recommendation = self._normalize_ai_recommendation(match.match_recommendation)
            rationale = match.explanation
            if report and report.recommended_next_step:
                rationale = f"{rationale} Next step: {report.recommended_next_step}"
            signals.append(
                DecisionConsensusSignalRead(
                    source="ai",
                    label="HireOS AI",
                    raw_value=match.match_recommendation,
                    normalized_recommendation=ai_recommendation,
                    rationale=rationale,
                )
            )
        if latest_manager_feedback:
            signals.append(
                DecisionConsensusSignalRead(
                    source="hiring_manager",
                    label=latest_manager_feedback.hiring_manager_name,
                    raw_value=latest_manager_feedback.recommendation,
                    normalized_recommendation=self._normalize_manager_recommendation(latest_manager_feedback.recommendation),
                    rationale=latest_manager_feedback.notes
                    or latest_manager_feedback.recommended_next_round
                    or "Hiring manager recommendation recorded without additional context.",
                )
            )
        if latest_decision:
            signals.append(
                DecisionConsensusSignalRead(
                    source="recruiter",
                    label=latest_decision.recruiter_name,
                    raw_value=latest_decision.decision,
                    normalized_recommendation=self._normalize_recruiter_decision(latest_decision.decision),
                    rationale=latest_decision.notes
                    or (
                        "Recruiter explicitly overrode the AI recommendation."
                        if latest_decision.override_ai_recommendation
                        else "Recruiter recorded the current pipeline action."
                    ),
                )
            )

        if len(signals) < 2:
            return DecisionConsensusRead(
                overall_status="pending",
                agreement_score=0,
                requires_escalation=False,
                summary="Capture at least two decision-support signals before calibrating alignment.",
                conflict_reasons=[],
                signals=signals,
            )

        normalized_values = [signal.normalized_recommendation for signal in signals]
        distinct_values = set(normalized_values)
        dominant_count = max(normalized_values.count(value) for value in distinct_values)
        agreement_score = round((dominant_count / len(signals)) * 100, 2)
        conflict_reasons = self._build_conflict_reasons(signals, latest_decision)

        if len(distinct_values) == 1:
            normalized = next(iter(distinct_values))
            return DecisionConsensusRead(
                overall_status="aligned",
                agreement_score=agreement_score,
                requires_escalation=False,
                summary=f"AI and human reviewers are aligned to {normalized} this candidate.",
                conflict_reasons=[],
                signals=signals,
            )

        has_advance = "advance" in distinct_values
        has_reject = "reject" in distinct_values
        overall_status = "conflicted" if has_advance and has_reject else "mixed"
        summary = (
            "Signals are split between advancing and rejecting the candidate. Run a calibration review before changing the pipeline."
            if overall_status == "conflicted"
            else "Signals are partially aligned but still need a human calibration pass before the final recruiter action."
        )
        return DecisionConsensusRead(
            overall_status=overall_status,
            agreement_score=agreement_score,
            requires_escalation=True,
            summary=summary,
            conflict_reasons=conflict_reasons,
            signals=signals,
        )

    def _build_conflict_reasons(
        self,
        signals: list[DecisionConsensusSignalRead],
        latest_decision: RecruiterDecisionRead | None,
    ) -> list[str]:
        reasons: list[str] = []
        signal_map = {signal.source: signal for signal in signals}
        ai_signal = signal_map.get("ai")
        manager_signal = signal_map.get("hiring_manager")
        recruiter_signal = signal_map.get("recruiter")

        if ai_signal and recruiter_signal and ai_signal.normalized_recommendation != recruiter_signal.normalized_recommendation:
            reasons.append("Recruiter decision differs from the current HireOS AI recommendation.")
        if manager_signal and recruiter_signal and manager_signal.normalized_recommendation != recruiter_signal.normalized_recommendation:
            reasons.append("Hiring manager feedback differs from the recruiter decision.")
        if ai_signal and manager_signal and ai_signal.normalized_recommendation != manager_signal.normalized_recommendation:
            reasons.append("Hiring manager feedback differs from the current HireOS AI recommendation.")
        if latest_decision and latest_decision.override_ai_recommendation:
            reasons.append("Recruiter marked this decision as an explicit AI override.")

        deduped: list[str] = []
        for reason in reasons:
            if reason not in deduped:
                deduped.append(reason)
        return deduped

    def _normalize_ai_recommendation(self, value: str) -> str:
        mapping = {
            "strong_match": "advance",
            "potential_match": "advance",
            "needs_human_review": "review",
            "weak_match": "reject",
        }
        return mapping.get(value, "review")

    def _normalize_manager_recommendation(self, value: str) -> str:
        mapping = {
            "strong_yes": "advance",
            "yes": "advance",
            "hold": "review",
            "no": "reject",
        }
        return mapping.get(value, "review")

    def _normalize_recruiter_decision(self, value: str) -> str:
        mapping = {
            "shortlisted": "advance",
            "moved_to_next_round": "advance",
            "hired": "advance",
            "human_review_required": "review",
            "rejected": "reject",
            "archived": "reject",
        }
        return mapping.get(value, "review")

    def _calibration_priority(self, workspace: CandidateReviewWorkspaceRead) -> str | None:
        consensus = workspace.decision_consensus
        if consensus.overall_status == "conflicted":
            return "critical"
        if consensus.overall_status == "mixed":
            return "high"
        if workspace.latest_decision and workspace.latest_decision.override_ai_recommendation:
            return "high"
        if consensus.overall_status == "pending" and (
            (workspace.latest_match and workspace.latest_match.human_review_required)
            or (workspace.latest_report and workspace.latest_report.human_review_required)
            or not workspace.latest_decision
        ):
            return "medium"
        return None

    def _actor_label(self, *, actor_type: str | None, actor_id: str | None, candidate_name: str, user_labels: dict[str, str]) -> str:
        if actor_type == "candidate":
            return candidate_name
        if actor_type in {"recruiter", "hiring_manager", "admin"} and actor_id:
            return user_labels.get(actor_id, "Team member")
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
            "hiring_manager.feedback_recorded": "Hiring manager feedback was captured for the review loop.",
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
        if action == "hiring_manager.feedback_recorded":
            recommendation = str(details.get("recommendation", "hold")).replace("_", " ")
            return f"Hiring manager recommended {recommendation}."
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
