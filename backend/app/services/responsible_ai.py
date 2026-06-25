from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    AuditLog,
    CalibrationCase,
    Candidate,
    CandidateJobMatch,
    CandidateResume,
    EventOutbox,
    Interview,
    InterviewReport,
    Job,
    RecruiterDecision,
)


RESOLVED_CALIBRATION_STATUSES = {"resolved", "closed"}


def _percentage(numerator: int | float, denominator: int | float) -> float:
    if not denominator:
        return 0.0
    return round((float(numerator) / float(denominator)) * 100, 2)


def _compliance_from_resume(resume: CandidateResume) -> dict[str, Any]:
    metadata = resume.parser_metadata or {}
    compliance = metadata.get("compliance")
    return compliance if isinstance(compliance, dict) else {}


def _latest_datetime(*values: datetime | None) -> datetime | None:
    return max((value for value in values if value is not None), default=None)


def build_responsible_ai_dashboard(db: Session, company_id: str) -> dict:
    candidates = (
        db.execute(
            select(Candidate)
            .options(selectinload(Candidate.resumes))
            .where(Candidate.company_id == company_id, Candidate.is_deleted.is_(False))
            .order_by(Candidate.created_at.desc())
        )
        .scalars()
        .all()
    )
    candidate_ids = {candidate.id for candidate in candidates}
    candidate_by_id = {candidate.id: candidate for candidate in candidates}

    resumes = (
        db.execute(
            select(CandidateResume)
            .join(Candidate, Candidate.id == CandidateResume.candidate_id)
            .where(Candidate.company_id == company_id, Candidate.is_deleted.is_(False))
            .order_by(CandidateResume.created_at.desc())
        )
        .scalars()
        .all()
    )
    matches = (
        db.execute(
            select(CandidateJobMatch)
            .join(Candidate, Candidate.id == CandidateJobMatch.candidate_id)
            .where(Candidate.company_id == company_id, Candidate.is_deleted.is_(False))
            .order_by(CandidateJobMatch.updated_at.desc())
        )
        .scalars()
        .all()
    )
    interviews = (
        db.execute(
            select(Interview)
            .where(Interview.company_id == company_id)
            .order_by(Interview.updated_at.desc())
        )
        .scalars()
        .all()
    )
    reports = (
        db.execute(
            select(InterviewReport)
            .join(Interview, Interview.id == InterviewReport.interview_id)
            .where(Interview.company_id == company_id)
            .order_by(InterviewReport.updated_at.desc())
        )
        .scalars()
        .all()
    )
    decisions = (
        db.execute(
            select(RecruiterDecision)
            .join(Candidate, Candidate.id == RecruiterDecision.candidate_id)
            .where(Candidate.company_id == company_id, Candidate.is_deleted.is_(False))
            .order_by(RecruiterDecision.created_at.desc())
        )
        .scalars()
        .all()
    )
    calibration_cases = (
        db.execute(
            select(CalibrationCase)
            .where(CalibrationCase.company_id == company_id)
            .order_by(CalibrationCase.updated_at.desc())
        )
        .scalars()
        .all()
    )
    jobs = db.execute(select(Job).where(Job.company_id == company_id)).scalars().all()
    job_titles = {job.id: job.title for job in jobs}

    redacted_resume_count = 0
    total_redactions = 0
    category_counts: Counter[str] = Counter()
    redaction_by_candidate: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"redaction_count": 0, "categories": set(), "latest_at": None}
    )
    for resume in resumes:
        compliance = _compliance_from_resume(resume)
        redaction_count = int(compliance.get("redaction_count") or 0)
        categories = [str(category) for category in compliance.get("categories_detected") or []]
        if compliance.get("redaction_applied") or redaction_count:
            redacted_resume_count += 1
            total_redactions += redaction_count
            category_counts.update(categories)
            candidate_summary = redaction_by_candidate[resume.candidate_id]
            candidate_summary["redaction_count"] += redaction_count
            candidate_summary["categories"].update(categories)
            candidate_summary["latest_at"] = _latest_datetime(candidate_summary["latest_at"], resume.updated_at)

    matches_by_candidate: dict[str, list[CandidateJobMatch]] = defaultdict(list)
    for match in matches:
        matches_by_candidate[match.candidate_id].append(match)

    interviews_by_id = {interview.id: interview for interview in interviews}
    reports_by_candidate: dict[str, list[InterviewReport]] = defaultdict(list)
    for report in reports:
        interview = interviews_by_id.get(report.interview_id)
        if interview:
            reports_by_candidate[interview.candidate_id].append(report)

    decisions_by_candidate: dict[str, list[RecruiterDecision]] = defaultdict(list)
    for decision in decisions:
        decisions_by_candidate[decision.candidate_id].append(decision)

    calibration_by_candidate: dict[str, list[CalibrationCase]] = defaultdict(list)
    for calibration_case in calibration_cases:
        calibration_by_candidate[calibration_case.candidate_id].append(calibration_case)

    now = datetime.now(UTC).replace(tzinfo=None)
    open_calibration_cases = [
        item for item in calibration_cases if item.status not in RESOLVED_CALIBRATION_STATUSES
    ]
    overdue_calibration_cases = [
        item
        for item in open_calibration_cases
        if item.due_at is not None and item.due_at < now
    ]

    human_review_candidate_ids: set[str] = set()
    for match in matches:
        if match.human_review_required:
            human_review_candidate_ids.add(match.candidate_id)
    for report in reports:
        interview = interviews_by_id.get(report.interview_id)
        if report.human_review_required and interview:
            human_review_candidate_ids.add(interview.candidate_id)
    for calibration_case in open_calibration_cases:
        human_review_candidate_ids.add(calibration_case.candidate_id)
    for candidate in candidates:
        if candidate.status == "human_review_required":
            human_review_candidate_ids.add(candidate.id)

    event_rows = db.execute(select(EventOutbox).order_by(EventOutbox.created_at.desc())).scalars().all()
    company_events = [
        event
        for event in event_rows
        if isinstance(event.envelope, dict) and event.envelope.get("company_id") == company_id
    ]
    event_counts = Counter(event.event_type for event in company_events)
    governance_event_types = {
        "resume.redacted",
        "candidate.matched",
        "answer.scored",
        "recruiter.decision_made",
        "hiring_manager.feedback_recorded",
        "calibration.case_updated",
        "evaluation.run_completed",
        "evaluation.regression_detected",
    }
    governance_events = [
        {"event_type": event_type, "count": count}
        for event_type, count in sorted(event_counts.items())
        if event_type in governance_event_types
    ]

    audit_logs = db.execute(select(AuditLog).order_by(AuditLog.created_at.desc())).scalars().all()
    relevant_entity_ids = candidate_ids | {interview.id for interview in interviews} | {decision.id for decision in decisions}
    audit_log_count = sum(1 for log in audit_logs if log.entity_id in relevant_entity_ids)

    candidate_signals = []
    for candidate in candidates:
        reasons: list[str] = []
        latest_at = candidate.updated_at

        redaction_summary = redaction_by_candidate.get(candidate.id)
        if redaction_summary and redaction_summary["redaction_count"]:
            reasons.append("Protected-attribute signals redacted from resume")
            latest_at = _latest_datetime(latest_at, redaction_summary["latest_at"]) or latest_at

        candidate_matches = matches_by_candidate.get(candidate.id, [])
        latest_match = candidate_matches[0] if candidate_matches else None
        if any(match.human_review_required for match in candidate_matches):
            reasons.append("Resume match requires human review")
        if latest_match:
            latest_at = _latest_datetime(latest_at, latest_match.updated_at) or latest_at

        candidate_reports = reports_by_candidate.get(candidate.id, [])
        latest_report = candidate_reports[0] if candidate_reports else None
        if any(report.human_review_required for report in candidate_reports):
            reasons.append("Interview report requires human review")
        if latest_report:
            latest_at = _latest_datetime(latest_at, latest_report.updated_at) or latest_at

        candidate_decisions = decisions_by_candidate.get(candidate.id, [])
        latest_decision = candidate_decisions[0] if candidate_decisions else None
        if latest_decision and latest_decision.override_ai_recommendation:
            reasons.append("Recruiter overrode AI recommendation")
            latest_at = _latest_datetime(latest_at, latest_decision.created_at) or latest_at

        candidate_calibration_cases = calibration_by_candidate.get(candidate.id, [])
        open_cases = [
            item for item in candidate_calibration_cases if item.status not in RESOLVED_CALIBRATION_STATUSES
        ]
        if open_cases:
            reasons.append("Open calibration case")
            latest_at = _latest_datetime(latest_at, open_cases[0].updated_at) or latest_at

        if not reasons:
            continue

        candidate_signals.append(
            {
                "candidate_id": candidate.id,
                "candidate_name": candidate.name,
                "candidate_email": candidate.email,
                "status": candidate.status,
                "job_id": latest_match.job_id if latest_match else (latest_decision.job_id if latest_decision else None),
                "job_title": job_titles.get(latest_match.job_id) if latest_match else (
                    job_titles.get(latest_decision.job_id) if latest_decision else None
                ),
                "match_score": round(float(latest_match.overall_score), 2) if latest_match else None,
                "ai_recommendation": latest_match.match_recommendation if latest_match else None,
                "human_review_required": candidate.id in human_review_candidate_ids,
                "override_ai_recommendation": bool(latest_decision and latest_decision.override_ai_recommendation),
                "redaction_count": int(redaction_summary["redaction_count"]) if redaction_summary else 0,
                "redaction_categories": sorted(redaction_summary["categories"]) if redaction_summary else [],
                "open_calibration_case_count": len(open_cases),
                "reasons": reasons,
                "latest_signal_at": latest_at or candidate.created_at,
            }
        )

    candidate_signals.sort(
        key=lambda item: (
            item["open_calibration_case_count"],
            int(item["override_ai_recommendation"]),
            int(item["human_review_required"]),
            len(item["reasons"]),
            item["latest_signal_at"],
        ),
        reverse=True,
    )

    risk_flags = []
    if not resumes:
        risk_flags.append("No resumes have been processed yet, so bias-shield coverage is not measurable.")
    if human_review_candidate_ids and not open_calibration_cases:
        risk_flags.append("Some candidates require human review, but no open calibration cases are currently tracking them.")
    override_rate = _percentage(sum(1 for decision in decisions if decision.override_ai_recommendation), len(decisions))
    if override_rate >= 25:
        risk_flags.append("Recruiter override rate is elevated; review whether model recommendations need calibration.")
    if overdue_calibration_cases:
        risk_flags.append("One or more calibration cases are overdue.")
    if not risk_flags:
        risk_flags.append("No immediate governance gaps detected from the current workspace data.")

    return {
        "summary": {
            "total_candidates": len(candidates),
            "resumes_processed": len(resumes),
            "redacted_resumes": redacted_resume_count,
            "protected_signal_rate": _percentage(redacted_resume_count, len(resumes)),
            "total_redactions": total_redactions,
            "human_review_candidates": len(human_review_candidate_ids),
            "human_review_rate": _percentage(len(human_review_candidate_ids), len(candidates)),
            "total_matches": len(matches),
            "human_review_matches": sum(1 for match in matches if match.human_review_required),
            "total_reports": len(reports),
            "human_review_reports": sum(1 for report in reports if report.human_review_required),
            "total_decisions": len(decisions),
            "override_count": sum(1 for decision in decisions if decision.override_ai_recommendation),
            "override_rate": override_rate,
            "open_calibration_cases": len(open_calibration_cases),
            "overdue_calibration_cases": len(overdue_calibration_cases),
            "audit_log_count": audit_log_count,
            "governance_event_count": sum(item["count"] for item in governance_events),
        },
        "redaction_categories": [
            {"category": category, "count": count}
            for category, count in category_counts.most_common()
        ],
        "human_review_breakdown": [
            {
                "label": "Resume matches",
                "total": len(matches),
                "requires_review": sum(1 for match in matches if match.human_review_required),
                "rate": _percentage(sum(1 for match in matches if match.human_review_required), len(matches)),
            },
            {
                "label": "Interview reports",
                "total": len(reports),
                "requires_review": sum(1 for report in reports if report.human_review_required),
                "rate": _percentage(sum(1 for report in reports if report.human_review_required), len(reports)),
            },
            {
                "label": "Calibration cases",
                "total": len(calibration_cases),
                "requires_review": len(open_calibration_cases),
                "rate": _percentage(len(open_calibration_cases), len(calibration_cases)),
            },
        ],
        "governance_events": governance_events,
        "recent_candidate_signals": candidate_signals[:10],
        "controls": [
            {
                "name": "Protected-attribute redaction",
                "status": "active",
                "evidence_count": redacted_resume_count,
                "description": "Resume text is sanitized before AI parsing and matching.",
            },
            {
                "name": "Human-in-the-loop decisions",
                "status": "active",
                "evidence_count": len(decisions),
                "description": "Recruiter decisions and explicit AI overrides are recorded.",
            },
            {
                "name": "Calibration workflow",
                "status": "attention" if open_calibration_cases else "monitored",
                "evidence_count": len(open_calibration_cases),
                "description": "Conflicted or ambiguous candidates can be tracked through calibration review.",
            },
            {
                "name": "Audit and event trail",
                "status": "active" if company_events or audit_log_count else "monitored",
                "evidence_count": len(company_events) + audit_log_count,
                "description": "Governance activity is written to audit logs and the event outbox/JSONL fallback.",
            },
        ],
        "risk_flags": risk_flags,
        "policy_note": (
            "Responsible-AI metrics are decision-support telemetry. They show where protected-attribute redaction, "
            "human review, overrides, and calibration controls are operating; they do not make hiring decisions."
        ),
    }
