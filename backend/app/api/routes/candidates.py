from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.db.models import Candidate, CandidateJobMatch, CandidateResume, CandidateSkill, Job
from app.db.session import get_db
from app.dependencies.auth import get_current_user, get_primary_membership, require_roles
from app.schemas import CalibrationQueueRead, CandidateCreate, CandidateRead, CandidateReviewWorkspaceRead, MatchResultRead
from app.services.events import EventPublisher, log_audit
from app.services.fairness_guard import FairnessGuard
from app.services.parsers import extract_text_from_upload, parse_resume_text
from app.services.review_workspace import CandidateReviewWorkspaceService
from app.services.scoring import HiringIntelligenceService

router = APIRouter(prefix="/candidates", tags=["candidates"])
events = EventPublisher()
ai = HiringIntelligenceService()
review_workspace = CandidateReviewWorkspaceService()
fairness_guard = FairnessGuard()


@router.post("", response_model=CandidateRead)
def create_candidate(payload: CandidateCreate, current_user=Depends(require_roles("admin", "recruiter")), db: Session = Depends(get_db)) -> CandidateRead:
    membership = get_primary_membership(current_user, db)
    candidate = Candidate(
        company_id=membership.company_id,
        owner_id=current_user.id,
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        location=payload.location,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return CandidateRead.model_validate(candidate)


@router.post("/upload-resume")
async def upload_resume(
    file: UploadFile = File(...),
    candidate_id: str | None = Form(default=None),
    name: str | None = Form(default=None),
    email: str | None = Form(default=None),
    phone: str | None = Form(default=None),
    location: str | None = Form(default=None),
    current_user=Depends(require_roles("admin", "recruiter")),
    db: Session = Depends(get_db),
) -> dict:
    membership = get_primary_membership(current_user, db)
    content = await file.read()
    if Path(file.filename or "").suffix.lower() not in {".pdf", ".docx", ".txt"}:
        raise HTTPException(status_code=400, detail="Unsupported file type")
    text = extract_text_from_upload(file.filename or "resume.txt", content)
    redaction_summary = fairness_guard.sanitize_text(text)
    parsed = parse_resume_text(redaction_summary.sanitized_text)
    parsed["compliance"] = redaction_summary.to_dict()
    candidate = db.get(Candidate, candidate_id) if candidate_id else None
    if not candidate:
        candidate = Candidate(
            company_id=membership.company_id,
            owner_id=current_user.id,
            name=name or parsed["name"],
            email=email or parsed["email"] or f"candidate-{membership.company_id[:6]}@example.com",
            phone=phone or parsed["phone"],
            location=location,
            years_experience=parsed["total_years_experience"],
            current_role=parsed["role_title"],
            education=parsed["education"],
            profile_summary=parsed["summary"],
            parsed_profile=parsed,
            status="resume_screened",
        )
        db.add(candidate)
        db.flush()
    else:
        candidate.years_experience = parsed["total_years_experience"]
        candidate.current_role = parsed["role_title"]
        candidate.education = parsed["education"]
        candidate.profile_summary = parsed["summary"]
        candidate.parsed_profile = parsed
        candidate.status = "resume_screened"
        for skill in list(candidate.skills):
            db.delete(skill)
    for skill_name in parsed["skills"]:
        db.add(CandidateSkill(candidate_id=candidate.id, name=skill_name))
    save_path = settings.uploads_dir / f"{candidate.id}-{file.filename}"
    save_path.write_bytes(content)
    db.add(
        CandidateResume(
            candidate_id=candidate.id,
            file_name=file.filename or "resume.txt",
            file_path=str(save_path),
            raw_text=text,
            parser_metadata={
                "source": "upload",
                "format": Path(file.filename or "").suffix.lower(),
                "sanitized_text": redaction_summary.sanitized_text,
                "compliance": redaction_summary.to_dict(),
            },
        )
    )
    events.publish(
        db,
        event_type="resume.uploaded",
        topic_name="hireos.resume.uploaded",
        company_id=membership.company_id,
        candidate_id=candidate.id,
        actor_id=current_user.id,
        actor_type="recruiter",
        payload={"file_name": file.filename},
    )
    events.publish(
        db,
        event_type="resume.parsed",
        topic_name="hireos.resume.parsed",
        company_id=membership.company_id,
        candidate_id=candidate.id,
        actor_id=current_user.id,
        actor_type="system",
        payload=parsed,
    )
    if redaction_summary.redaction_count:
        events.publish(
            db,
            event_type="resume.redacted",
            topic_name="hireos.resume.redacted",
            company_id=membership.company_id,
            candidate_id=candidate.id,
            actor_id=current_user.id,
            actor_type="system",
            payload=redaction_summary.to_dict(),
        )
    log_audit(db, current_user.id, "candidate", candidate.id, "resume.uploaded", {"file_name": file.filename})
    db.commit()
    db.refresh(candidate)
    return {"candidate": CandidateRead.model_validate(candidate).model_dump(), "parsed_resume": parsed}


@router.get("", response_model=list[CandidateRead])
def list_candidates(current_user=Depends(get_current_user), db: Session = Depends(get_db)) -> list[CandidateRead]:
    membership = get_primary_membership(current_user, db)
    candidates = db.execute(select(Candidate).where(Candidate.company_id == membership.company_id).order_by(Candidate.created_at.desc())).scalars()
    return [CandidateRead.model_validate(candidate) for candidate in candidates]


@router.get("/calibration-queue", response_model=CalibrationQueueRead)
def get_calibration_queue(
    current_user=Depends(require_roles("admin", "recruiter", "hiring_manager")),
    db: Session = Depends(get_db),
) -> CalibrationQueueRead:
    membership = get_primary_membership(current_user, db)
    return review_workspace.build_calibration_queue(db, company_id=membership.company_id)


@router.get("/{candidate_id}", response_model=CandidateRead)
def get_candidate(candidate_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)) -> CandidateRead:
    candidate = db.execute(
        select(Candidate).options(selectinload(Candidate.skills), selectinload(Candidate.resumes)).where(Candidate.id == candidate_id)
    ).scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return CandidateRead.model_validate(candidate)


@router.get("/{candidate_id}/review-workspace/{job_id}", response_model=CandidateReviewWorkspaceRead)
def get_candidate_review_workspace(
    candidate_id: str,
    job_id: str,
    current_user=Depends(require_roles("admin", "recruiter", "hiring_manager")),
    db: Session = Depends(get_db),
) -> CandidateReviewWorkspaceRead:
    workspace = review_workspace.build(db, candidate_id=candidate_id, job_id=job_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Candidate or job not found")
    return workspace


@router.post("/{candidate_id}/match-job/{job_id}", response_model=MatchResultRead)
def match_candidate_to_job(
    candidate_id: str,
    job_id: str,
    current_user=Depends(require_roles("admin", "recruiter", "hiring_manager")),
    db: Session = Depends(get_db),
) -> MatchResultRead:
    candidate = db.execute(select(Candidate).options(selectinload(Candidate.skills)).where(Candidate.id == candidate_id)).scalar_one_or_none()
    job = db.execute(select(Job).options(selectinload(Job.skills)).where(Job.id == job_id)).scalar_one_or_none()
    if not candidate or not job:
        raise HTTPException(status_code=404, detail="Candidate or job not found")
    result = ai.match_candidate(candidate, job)
    match = db.execute(
        select(CandidateJobMatch).where(CandidateJobMatch.candidate_id == candidate_id, CandidateJobMatch.job_id == job_id)
    ).scalar_one_or_none()
    if not match:
        match = CandidateJobMatch(candidate_id=candidate_id, job_id=job_id, explanation="")
        db.add(match)
    for field, value in result.items():
        setattr(match, field, value)
    candidate.status = "ai_review_completed" if not result["human_review_required"] else "human_review_required"
    events.publish(
        db,
        event_type="candidate.matched",
        topic_name="hireos.candidate.matched",
        company_id=candidate.company_id,
        job_id=job_id,
        candidate_id=candidate.id,
        actor_id=current_user.id,
        actor_type="system",
        payload=result,
    )
    db.commit()
    db.refresh(match)
    return MatchResultRead.model_validate(match)
