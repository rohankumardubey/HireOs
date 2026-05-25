from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import AnswerScore, Candidate, CandidateJobMatch, Interview, InterviewAnswer, Job, JobSkill, RecruiterDecision
from app.db.session import get_db
from app.dependencies.auth import get_current_user, get_primary_membership, require_roles
from app.schemas import JobCreate, JobRead, JobUpdate, RankingEntry
from app.services.events import EventPublisher, log_audit
from app.services.scoring import HiringIntelligenceService

router = APIRouter(prefix="/jobs", tags=["jobs"])
events = EventPublisher()
ai = HiringIntelligenceService()


def serialize_job(job: Job) -> JobRead:
    return JobRead.model_validate(job)


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
    rows = db.execute(
        select(
            Candidate.id,
            Candidate.name,
            Candidate.status,
            CandidateJobMatch.overall_score,
            CandidateJobMatch.missing_required_skills,
            CandidateJobMatch.match_recommendation,
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
        )
        .order_by(CandidateJobMatch.overall_score.desc())
    ).all()
    ranking: list[RankingEntry] = []
    for index, row in enumerate(rows, start=1):
        interview_score = round(float(row[6] or 0), 2)
        final_score = round((float(row[3]) * 0.55) + (interview_score * 0.45), 2)
        ranking.append(
            RankingEntry(
                rank=index,
                candidate_id=row[0],
                candidate_name=row[1],
                match_score=round(float(row[3] or 0), 2),
                interview_score=interview_score,
                final_score=final_score,
                strengths=[f"High alignment for rank #{index}."] if final_score > 70 else ["Needs more evidence."],
                missing_skills=row[4] or [],
                status=row[2],
                ai_recommendation=row[5],
                recruiter_decision=row[7],
            )
        )
    return sorted(ranking, key=lambda item: item.final_score, reverse=True)

