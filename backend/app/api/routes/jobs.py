from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import AnswerScore, Candidate, CandidateJobMatch, Interview, InterviewAnswer, Job, JobSkill, RecruiterDecision
from app.db.session import get_db
from app.dependencies.auth import get_current_user, get_primary_membership, require_roles
from app.schemas import (
    JobCreate,
    JobRead,
    JobUpdate,
    RankingEntry,
    RankingSimulationCandidate,
    RankingSimulationConfigRead,
    RankingSimulationRequest,
    RankingSimulationResponse,
)
from app.services.events import EventPublisher, log_audit
from app.services.scoring import HiringIntelligenceService

router = APIRouter(prefix="/jobs", tags=["jobs"])
events = EventPublisher()
ai = HiringIntelligenceService()


@dataclass
class RankingSnapshot:
    candidate_id: str
    candidate_name: str
    status: str
    match_score: float
    interview_score: float
    missing_skills: list[str]
    ai_recommendation: str
    recruiter_decision: str | None
    human_review_required: bool
    matched_skills_count: int
    total_required_skills: int


def serialize_job(job: Job) -> JobRead:
    return JobRead.model_validate(job)


def fetch_ranking_snapshots(db: Session, job_id: str) -> list[RankingSnapshot]:
    rows = db.execute(
        select(
            Candidate.id,
            Candidate.name,
            Candidate.status,
            CandidateJobMatch.overall_score,
            CandidateJobMatch.missing_required_skills,
            CandidateJobMatch.match_recommendation,
            CandidateJobMatch.human_review_required,
            CandidateJobMatch.matched_required_skills,
            func.avg(AnswerScore.total_score),
            func.max(RecruiterDecision.decision),
        )
        .join(CandidateJobMatch, CandidateJobMatch.candidate_id == Candidate.id)
        .outerjoin(Interview, Interview.candidate_id == Candidate.id)
        .outerjoin(InterviewAnswer, InterviewAnswer.interview_id == Interview.id)
        .outerjoin(AnswerScore, AnswerScore.answer_id == InterviewAnswer.id)
        .outerjoin(RecruiterDecision, RecruiterDecision.candidate_id == Candidate.id)
        .where(CandidateJobMatch.job_id == job_id)
        .group_by(
            Candidate.id,
            Candidate.name,
            Candidate.status,
            CandidateJobMatch.overall_score,
            CandidateJobMatch.missing_required_skills,
            CandidateJobMatch.match_recommendation,
            CandidateJobMatch.human_review_required,
            CandidateJobMatch.matched_required_skills,
        )
    ).all()

    job = db.get(Job, job_id)
    total_required_skills = len((job.jd_analysis or {}).get("required_skills", [])) if job else 0

    return [
        RankingSnapshot(
            candidate_id=row[0],
            candidate_name=row[1],
            status=row[2],
            match_score=round(float(row[3] or 0), 2),
            interview_score=round(float(row[8] or 0), 2),
            missing_skills=row[4] or [],
            ai_recommendation=row[5],
            recruiter_decision=row[9],
            human_review_required=bool(row[6]),
            matched_skills_count=len(row[7] or []),
            total_required_skills=total_required_skills,
        )
        for row in rows
    ]


def calculate_baseline_score(snapshot: RankingSnapshot) -> float:
    return round((snapshot.match_score * 0.55) + (snapshot.interview_score * 0.45), 2)


def calculate_simulated_score(snapshot: RankingSnapshot, config: RankingSimulationRequest) -> float:
    total_weight = max(config.resume_weight + config.interview_weight, 1)
    resume_weight = config.resume_weight / total_weight
    interview_weight = config.interview_weight / total_weight
    score = (snapshot.match_score * resume_weight) + (snapshot.interview_score * interview_weight)
    score -= len(snapshot.missing_skills) * config.missing_skill_penalty
    if snapshot.human_review_required:
        score -= config.human_review_penalty
    if snapshot.recruiter_decision in {"shortlisted", "moved_to_next_round", "hired"}:
        score += config.shortlist_boost
    if snapshot.recruiter_decision in {"rejected", "archived"}:
        score -= config.shortlist_boost
    return round(max(score, 0), 2)


def coverage_percent(snapshot: RankingSnapshot) -> float:
    return round((snapshot.matched_skills_count / max(snapshot.total_required_skills, 1)) * 100, 2)


def movement_reason(snapshot: RankingSnapshot, rank_change: int, config: RankingSimulationRequest) -> str:
    if rank_change > 0:
        if snapshot.interview_score > snapshot.match_score and config.interview_weight > config.resume_weight:
            return "Moved up because interview performance is weighted more heavily in this scenario."
        if snapshot.recruiter_decision in {"shortlisted", "moved_to_next_round", "hired"}:
            return "Moved up because recruiter-approved candidates receive a shortlist boost."
        return "Moved up because this candidate carries fewer penalties under the simulated scorecard."
    if rank_change < 0:
        if snapshot.missing_skills:
            return "Moved down because missing required skills carry more penalty in this scenario."
        if snapshot.human_review_required:
            return "Moved down because human-review-required candidates are penalized more heavily."
        return "Moved down because other candidates gain more from the simulated weighting mix."
    return "Held position because the simulated policy does not materially change this candidate's evidence profile."


def build_ranking_entries(snapshots: list[RankingSnapshot]) -> list[RankingEntry]:
    ordered = sorted(snapshots, key=lambda item: (calculate_baseline_score(item), item.match_score), reverse=True)
    ranking: list[RankingEntry] = []
    for index, snapshot in enumerate(ordered, start=1):
        final_score = calculate_baseline_score(snapshot)
        ranking.append(
            RankingEntry(
                rank=index,
                candidate_id=snapshot.candidate_id,
                candidate_name=snapshot.candidate_name,
                match_score=snapshot.match_score,
                interview_score=snapshot.interview_score,
                final_score=final_score,
                strengths=[f"High alignment for rank #{index}."] if final_score > 70 else ["Needs more evidence."],
                missing_skills=snapshot.missing_skills,
                status=snapshot.status,
                ai_recommendation=snapshot.ai_recommendation,
                recruiter_decision=snapshot.recruiter_decision,
            )
        )
    return ranking


@router.post("", response_model=JobRead)
def create_job(payload: JobCreate, current_user=Depends(require_roles("admin", "recruiter")), db: Session = Depends(get_db)) -> JobRead:
    membership = get_primary_membership(current_user, db)
    job = Job(
        company_id=membership.company_id,
        created_by_id=current_user.id,
        title=payload.title,
        department=payload.department,
        location=payload.location,
        work_mode=payload.work_mode,
        experience_range=payload.experience_range,
        employment_type=payload.employment_type,
        salary_range=payload.salary_range,
        status=payload.status,
        job_description=payload.job_description,
    )
    db.add(job)
    db.flush()
    for name in payload.required_skills:
        db.add(JobSkill(job_id=job.id, name=name, category="required", weight=1.0))
    for name in payload.preferred_skills:
        db.add(JobSkill(job_id=job.id, name=name, category="preferred", weight=0.6))
    job.jd_analysis = ai.analyze_job(job)
    events.publish(
        db,
        event_type="job.created",
        topic_name="hireos.job.created",
        company_id=membership.company_id,
        job_id=job.id,
        actor_id=current_user.id,
        actor_type="recruiter",
        payload={"title": job.title},
    )
    log_audit(db, current_user.id, "job", job.id, "job.created", {"title": job.title})
    db.commit()
    db.refresh(job)
    return serialize_job(job)


@router.get("", response_model=list[JobRead])
def list_jobs(current_user=Depends(get_current_user), db: Session = Depends(get_db)) -> list[JobRead]:
    membership = get_primary_membership(current_user, db)
    jobs = db.execute(select(Job).where(Job.company_id == membership.company_id, Job.is_deleted.is_(False)).order_by(Job.created_at.desc())).scalars()
    return [serialize_job(job) for job in jobs]


@router.get("/{job_id}", response_model=JobRead)
def get_job(job_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)) -> JobRead:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return serialize_job(job)


@router.patch("/{job_id}", response_model=JobRead)
def update_job(job_id: str, payload: JobUpdate, current_user=Depends(require_roles("admin", "recruiter")), db: Session = Depends(get_db)) -> JobRead:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    data = payload.model_dump(exclude_none=True)
    required = data.pop("required_skills", None)
    preferred = data.pop("preferred_skills", None)
    for field, value in data.items():
        setattr(job, field, value)
    if required is not None or preferred is not None:
        for skill in list(job.skills):
            db.delete(skill)
        for name in required or []:
            db.add(JobSkill(job_id=job.id, name=name, category="required", weight=1.0))
        for name in preferred or []:
            db.add(JobSkill(job_id=job.id, name=name, category="preferred", weight=0.6))
    if "job_description" in data:
        job.jd_analysis = ai.analyze_job(job)
    db.commit()
    db.refresh(job)
    return serialize_job(job)


@router.post("/{job_id}/parse", response_model=JobRead)
def parse_job(job_id: str, current_user=Depends(require_roles("admin", "recruiter")), db: Session = Depends(get_db)) -> JobRead:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.jd_analysis = ai.analyze_job(job)
    events.publish(
        db,
        event_type="jd.parsed",
        topic_name="hireos.jd.parsed",
        company_id=job.company_id,
        job_id=job.id,
        actor_id=current_user.id,
        actor_type="recruiter",
        payload=job.jd_analysis,
    )
    db.commit()
    db.refresh(job)
    return serialize_job(job)


@router.get("/{job_id}/candidates")
def job_candidates(job_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(
        select(Candidate, CandidateJobMatch)
        .join(CandidateJobMatch, CandidateJobMatch.candidate_id == Candidate.id)
        .where(CandidateJobMatch.job_id == job_id)
    ).all()
    return [
        {
            "candidate": {"id": candidate.id, "name": candidate.name, "email": candidate.email, "status": candidate.status},
            "match": {
                "score": match.overall_score,
                "recommendation": match.match_recommendation,
                "human_review_required": match.human_review_required,
            },
        }
        for candidate, match in rows
    ]


@router.get("/{job_id}/ranking", response_model=list[RankingEntry])
def job_ranking(job_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)) -> list[RankingEntry]:
    snapshots = fetch_ranking_snapshots(db, job_id)
    return build_ranking_entries(snapshots)


@router.post("/{job_id}/ranking/simulate", response_model=RankingSimulationResponse)
def simulate_job_ranking(
    job_id: str,
    payload: RankingSimulationRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RankingSimulationResponse:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    snapshots = fetch_ranking_snapshots(db, job_id)
    baseline = build_ranking_entries(snapshots)
    baseline_ranks = {entry.candidate_id: entry.rank for entry in baseline}
    baseline_scores = {entry.candidate_id: entry.final_score for entry in baseline}

    simulated_order = sorted(
        snapshots,
        key=lambda item: (calculate_simulated_score(item, payload), item.match_score, item.interview_score),
        reverse=True,
    )

    candidates: list[RankingSimulationCandidate] = []
    for simulated_rank, snapshot in enumerate(simulated_order, start=1):
        base_rank = baseline_ranks.get(snapshot.candidate_id, simulated_rank)
        rank_change = base_rank - simulated_rank
        candidates.append(
            RankingSimulationCandidate(
                candidate_id=snapshot.candidate_id,
                candidate_name=snapshot.candidate_name,
                baseline_rank=base_rank,
                simulated_rank=simulated_rank,
                rank_change=rank_change,
                baseline_score=baseline_scores.get(snapshot.candidate_id, calculate_baseline_score(snapshot)),
                simulated_score=calculate_simulated_score(snapshot, payload),
                match_score=snapshot.match_score,
                interview_score=snapshot.interview_score,
                required_skill_coverage=coverage_percent(snapshot),
                missing_skills=snapshot.missing_skills,
                human_review_required=snapshot.human_review_required,
                ai_recommendation=snapshot.ai_recommendation,
                recruiter_decision=snapshot.recruiter_decision,
                movement_reason=movement_reason(snapshot, rank_change, payload),
            )
        )

    top_mover = max(candidates, key=lambda item: abs(item.rank_change), default=None)
    summary = (
        f"This scenario favors {'interview evidence' if payload.interview_weight > payload.resume_weight else 'resume alignment'} "
        f"and applies a {payload.missing_skill_penalty:.0f}-point penalty per missing required skill. "
        f"{candidates[0].candidate_name if candidates else 'No candidates'} leads the simulated shortlist."
    )

    return RankingSimulationResponse(
        job_id=job.id,
        job_title=job.title,
        summary=summary,
        top_mover_candidate_id=top_mover.candidate_id if top_mover and top_mover.rank_change else None,
        config=RankingSimulationConfigRead(
            resume_weight=payload.resume_weight,
            interview_weight=payload.interview_weight,
            missing_skill_penalty=payload.missing_skill_penalty,
            human_review_penalty=payload.human_review_penalty,
            shortlist_boost=payload.shortlist_boost,
        ),
        candidates=candidates,
        policy_note=(
            "Use simulated rankings to stress-test your shortlist criteria, then let a recruiter confirm whether any weight changes are fair and role-appropriate."
        ),
    )
