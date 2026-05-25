from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import AnswerScore, Candidate, CandidateJobMatch, CandidateStatus, Interview, InterviewReport, InterviewStatus, Job, RecruiterDecision


def get_overview(db: Session, company_id: str) -> dict:
    total_candidates = db.scalar(select(func.count(Candidate.id)).where(Candidate.company_id == company_id)) or 0
    active_jobs = db.scalar(select(func.count(Job.id)).where(Job.company_id == company_id, Job.status == "open")) or 0
    interviews_completed = (
        db.scalar(select(func.count(Interview.id)).where(Interview.company_id == company_id, Interview.status == InterviewStatus.completed.value))
        or 0
    )
    candidates_shortlisted = (
        db.scalar(select(func.count(Candidate.id)).where(Candidate.company_id == company_id, Candidate.status == CandidateStatus.shortlisted.value))
        or 0
    )
    avg_match = db.scalar(
        select(func.avg(CandidateJobMatch.overall_score)).join(Candidate).where(Candidate.company_id == company_id)
    ) or 0
    avg_interview = db.scalar(
        select(func.avg(AnswerScore.total_score))
        .join(AnswerScore.answer)
        .join(Interview)
        .where(Interview.company_id == company_id)
    ) or 0
    human_review = (
        db.scalar(select(func.count(InterviewReport.id)).join(Interview).where(Interview.company_id == company_id, InterviewReport.human_review_required))
        or 0
    )
    pipeline_rows = db.execute(
        select(Candidate.status, func.count(Candidate.id)).where(Candidate.company_id == company_id).group_by(Candidate.status)
    ).all()
    return {
        "total_candidates": total_candidates,
        "active_jobs": active_jobs,
        "interviews_completed": interviews_completed,
        "candidates_shortlisted": candidates_shortlisted,
        "average_match_score": round(float(avg_match), 2),
        "average_interview_score": round(float(avg_interview), 2),
        "candidates_requiring_human_review": human_review,
        "pipeline_by_stage": {status: count for status, count in pipeline_rows},
    }


def get_job_metrics(db: Session, company_id: str, job_id: str) -> dict:
    ranking = db.execute(
        select(Candidate.name, CandidateJobMatch.overall_score)
        .join(Candidate, Candidate.id == CandidateJobMatch.candidate_id)
        .where(Candidate.company_id == company_id, CandidateJobMatch.job_id == job_id)
        .order_by(CandidateJobMatch.overall_score.desc())
    ).all()
    return {"job_id": job_id, "ranking_snapshot": [{"candidate": name, "match_score": score} for name, score in ranking]}


def get_funnel(db: Session, company_id: str) -> dict:
    rows = db.execute(
        select(Candidate.status, func.count(Candidate.id)).where(Candidate.company_id == company_id).group_by(Candidate.status)
    ).all()
    return {"stages": [{"stage": status, "count": count} for status, count in rows]}


def get_model_quality(db: Session, company_id: str) -> dict:
    avg_score = db.scalar(
        select(func.avg(AnswerScore.total_score))
        .join(AnswerScore.answer)
        .join(Interview)
        .where(Interview.company_id == company_id)
    ) or 0
    overrides = db.scalar(
        select(func.count(RecruiterDecision.id)).where(RecruiterDecision.override_ai_recommendation.is_(True))
    ) or 0
    return {
        "average_answer_score": round(float(avg_score), 2),
        "override_rate": overrides,
        "human_in_loop": True,
        "compliance_note": "Protected attributes are excluded from scoring logic. Final decisions remain with humans.",
    }

