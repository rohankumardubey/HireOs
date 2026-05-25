from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def uuid_str() -> str:
    return str(uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RoleEnum(str, Enum):
    admin = "admin"
    recruiter = "recruiter"
    candidate = "candidate"
    hiring_manager = "hiring_manager"


class JobStatus(str, Enum):
    draft = "draft"
    open = "open"
    closed = "closed"


class CandidateStatus(str, Enum):
    applied = "applied"
    resume_screened = "resume_screened"
    interview_invited = "interview_invited"
    interview_completed = "interview_completed"
    ai_review_completed = "ai_review_completed"
    human_review_required = "human_review_required"
    shortlisted = "shortlisted"
    rejected = "rejected"
    moved_to_next_round = "moved_to_next_round"
    hired = "hired"
    archived = "archived"


class MatchRecommendation(str, Enum):
    strong_match = "strong_match"
    potential_match = "potential_match"
    needs_human_review = "needs_human_review"
    weak_match = "weak_match"


class InterviewMode(str, Enum):
    text = "text"
    voice = "voice"
    video = "video"


class InterviewStatus(str, Enum):
    invited = "invited"
    started = "started"
    completed = "completed"


class EventStatus(str, Enum):
    pending = "pending"
    delivered = "delivered"
    fallback = "fallback"
    failed = "failed"


class NotificationStatus(str, Enum):
    pending = "pending"
    delivered = "delivered"
    fallback = "fallback"
    failed = "failed"


class Company(Base, TimestampMixin):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    industry: Mapped[str | None] = mapped_column(String(255))
    size_band: Mapped[str | None] = mapped_column(String(50))
    settings_json: Mapped[dict] = mapped_column(JSON, default=dict)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    memberships: Mapped[list["CompanyMembership"]] = relationship(back_populates="company")
    jobs: Mapped[list["Job"]] = relationship(back_populates="company")
    candidates: Mapped[list["Candidate"]] = relationship(back_populates="company")


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    full_name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    memberships: Mapped[list["CompanyMembership"]] = relationship(back_populates="user")
    auth_exchange_codes: Mapped[list["AuthExchangeCode"]] = relationship(back_populates="user")


class CompanyMembership(Base, TimestampMixin):
    __tablename__ = "company_memberships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(50), index=True)

    company: Mapped[Company] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="memberships")


class AuthExchangeCode(Base):
    __tablename__ = "auth_exchange_codes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    code_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    flow: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[User] = relationship(back_populates="auth_exchange_codes")


class Job(Base, TimestampMixin):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    department: Mapped[str | None] = mapped_column(String(255))
    location: Mapped[str | None] = mapped_column(String(255))
    work_mode: Mapped[str] = mapped_column(String(50), default="remote")
    experience_range: Mapped[str | None] = mapped_column(String(100))
    employment_type: Mapped[str | None] = mapped_column(String(50))
    salary_range: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), default=JobStatus.draft.value, index=True)
    job_description: Mapped[str] = mapped_column(Text)
    jd_analysis: Mapped[dict] = mapped_column(JSON, default=dict)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    company: Mapped[Company] = relationship(back_populates="jobs")
    skills: Mapped[list["JobSkill"]] = relationship(back_populates="job", cascade="all, delete-orphan")
    matches: Mapped[list["CandidateJobMatch"]] = relationship(back_populates="job")
    interviews: Mapped[list["Interview"]] = relationship(back_populates="job")


class JobSkill(Base, TimestampMixin):
    __tablename__ = "job_skills"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    category: Mapped[str] = mapped_column(String(50), default="required")
    weight: Mapped[float] = mapped_column(Float, default=1.0)

    job: Mapped[Job] = relationship(back_populates="skills")


class Candidate(Base, TimestampMixin):
    __tablename__ = "candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    phone: Mapped[str | None] = mapped_column(String(50))
    location: Mapped[str | None] = mapped_column(String(255))
    years_experience: Mapped[float] = mapped_column(Float, default=0)
    current_role: Mapped[str | None] = mapped_column(String(255))
    current_company: Mapped[str | None] = mapped_column(String(255))
    education: Mapped[str | None] = mapped_column(Text)
    profile_summary: Mapped[str | None] = mapped_column(Text)
    parsed_profile: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(50), default=CandidateStatus.applied.value, index=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    company: Mapped[Company] = relationship(back_populates="candidates")
    skills: Mapped[list["CandidateSkill"]] = relationship(back_populates="candidate", cascade="all, delete-orphan")
    resumes: Mapped[list["CandidateResume"]] = relationship(back_populates="candidate", cascade="all, delete-orphan")
    matches: Mapped[list["CandidateJobMatch"]] = relationship(back_populates="candidate")
    interviews: Mapped[list["Interview"]] = relationship(back_populates="candidate")


class CandidateSkill(Base, TimestampMixin):
    __tablename__ = "candidate_skills"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id"), index=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    source: Mapped[str] = mapped_column(String(50), default="resume")
    confidence: Mapped[float] = mapped_column(Float, default=0.75)

    candidate: Mapped[Candidate] = relationship(back_populates="skills")


class CandidateResume(Base, TimestampMixin):
    __tablename__ = "candidate_resumes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id"), index=True)
    file_name: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(500))
    raw_text: Mapped[str] = mapped_column(Text)
    parser_metadata: Mapped[dict] = mapped_column(JSON, default=dict)

    candidate: Mapped[Candidate] = relationship(back_populates="resumes")


class CandidateJobMatch(Base, TimestampMixin):
    __tablename__ = "candidate_job_matches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id"), index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    overall_score: Mapped[float] = mapped_column(Float, default=0)
    match_recommendation: Mapped[str] = mapped_column(String(50), default=MatchRecommendation.needs_human_review.value)
    matched_required_skills: Mapped[list] = mapped_column(JSON, default=list)
    missing_required_skills: Mapped[list] = mapped_column(JSON, default=list)
    matched_preferred_skills: Mapped[list] = mapped_column(JSON, default=list)
    red_flags: Mapped[list] = mapped_column(JSON, default=list)
    explanation: Mapped[str] = mapped_column(Text)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.5)
    human_review_required: Mapped[bool] = mapped_column(Boolean, default=True)

    candidate: Mapped[Candidate] = relationship(back_populates="matches")
    job: Mapped[Job] = relationship(back_populates="matches")


class Interview(Base, TimestampMixin):
    __tablename__ = "interviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id"), index=True)
    invited_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    interview_type: Mapped[str] = mapped_column(String(100), default="Technical screening")
    mode: Mapped[str] = mapped_column(String(50), default=InterviewMode.text.value)
    status: Mapped[str] = mapped_column(String(50), default=InterviewStatus.invited.value, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    consent_given: Mapped[bool] = mapped_column(Boolean, default=False)
    current_question_index: Mapped[int] = mapped_column(Integer, default=0)
    summary_json: Mapped[dict] = mapped_column(JSON, default=dict)

    job: Mapped[Job] = relationship(back_populates="interviews")
    candidate: Mapped[Candidate] = relationship(back_populates="interviews")
    questions: Mapped[list["InterviewQuestion"]] = relationship(back_populates="interview", cascade="all, delete-orphan")
    answers: Mapped[list["InterviewAnswer"]] = relationship(back_populates="interview", cascade="all, delete-orphan")
    report: Mapped["InterviewReport | None"] = relationship(back_populates="interview", uselist=False)


class InterviewQuestion(Base, TimestampMixin):
    __tablename__ = "interview_questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    interview_id: Mapped[str] = mapped_column(ForeignKey("interviews.id"), index=True)
    question_order: Mapped[int] = mapped_column(Integer, default=0)
    question_text: Mapped[str] = mapped_column(Text)
    skill_category: Mapped[str] = mapped_column(String(100))
    difficulty: Mapped[str] = mapped_column(String(50), default="medium")
    expected_concepts: Mapped[list] = mapped_column(JSON, default=list)
    scoring_rubric: Mapped[dict] = mapped_column(JSON, default=dict)
    follow_up_strategy: Mapped[str | None] = mapped_column(Text)
    is_follow_up: Mapped[bool] = mapped_column(Boolean, default=False)

    interview: Mapped[Interview] = relationship(back_populates="questions")
    answers: Mapped[list["InterviewAnswer"]] = relationship(back_populates="question")


class InterviewAnswer(Base, TimestampMixin):
    __tablename__ = "interview_answers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    interview_id: Mapped[str] = mapped_column(ForeignKey("interviews.id"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("interview_questions.id"), index=True)
    answer_text: Mapped[str] = mapped_column(Text)
    transcript_text: Mapped[str | None] = mapped_column(Text)
    answer_mode: Mapped[str] = mapped_column(String(50), default=InterviewMode.text.value)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)

    interview: Mapped[Interview] = relationship(back_populates="answers")
    question: Mapped[InterviewQuestion] = relationship(back_populates="answers")
    score: Mapped["AnswerScore | None"] = relationship(back_populates="answer", uselist=False)


class AnswerScore(Base, TimestampMixin):
    __tablename__ = "answer_scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    answer_id: Mapped[str] = mapped_column(ForeignKey("interview_answers.id"), index=True)
    total_score: Mapped[float] = mapped_column(Float, default=0)
    skill_score: Mapped[float] = mapped_column(Float, default=0)
    clarity_score: Mapped[float] = mapped_column(Float, default=0)
    communication_score: Mapped[float] = mapped_column(Float, default=0)
    confidence_score: Mapped[float] = mapped_column(Float, default=0)
    matched_concepts: Mapped[list] = mapped_column(JSON, default=list)
    missing_concepts: Mapped[list] = mapped_column(JSON, default=list)
    strengths: Mapped[list] = mapped_column(JSON, default=list)
    weaknesses: Mapped[list] = mapped_column(JSON, default=list)
    suggested_follow_up: Mapped[str | None] = mapped_column(Text)
    human_review_required: Mapped[bool] = mapped_column(Boolean, default=False)
    explanation: Mapped[str] = mapped_column(Text)

    answer: Mapped[InterviewAnswer] = relationship(back_populates="score")


class InterviewReport(Base, TimestampMixin):
    __tablename__ = "interview_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    interview_id: Mapped[str] = mapped_column(ForeignKey("interviews.id"), unique=True, index=True)
    report_markdown: Mapped[str] = mapped_column(Text)
    report_html: Mapped[str] = mapped_column(Text)
    recommended_next_step: Mapped[str] = mapped_column(String(255))
    human_review_required: Mapped[bool] = mapped_column(Boolean, default=True)
    audit_trail: Mapped[list] = mapped_column(JSON, default=list)

    interview: Mapped[Interview] = relationship(back_populates="report")


class RecruiterDecision(Base, TimestampMixin):
    __tablename__ = "recruiter_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    interview_id: Mapped[str] = mapped_column(ForeignKey("interviews.id"), index=True)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id"), index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    recruiter_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    decision: Mapped[str] = mapped_column(String(50))
    notes: Mapped[str | None] = mapped_column(Text)
    override_ai_recommendation: Mapped[bool] = mapped_column(Boolean, default=False)


class NotificationDelivery(Base, TimestampMixin):
    __tablename__ = "notification_deliveries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    interview_id: Mapped[str | None] = mapped_column(ForeignKey("interviews.id"), index=True)
    candidate_id: Mapped[str | None] = mapped_column(ForeignKey("candidates.id"), index=True)
    recruiter_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    channel: Mapped[str] = mapped_column(String(50), default="email")
    notification_type: Mapped[str] = mapped_column(String(100), default="interview_invite")
    recipient_email: Mapped[str] = mapped_column(String(255), index=True)
    subject: Mapped[str] = mapped_column(String(255))
    body_text: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(50), default="file")
    status: Mapped[str] = mapped_column(String(50), default=NotificationStatus.pending.value, index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    actor_id: Mapped[str | None] = mapped_column(String(36), index=True)
    entity_type: Mapped[str] = mapped_column(String(100), index=True)
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    action: Mapped[str] = mapped_column(String(100))
    before_json: Mapped[dict] = mapped_column(JSON, default=dict)
    after_json: Mapped[dict] = mapped_column(JSON, default=dict)


class EventOutbox(Base, TimestampMixin):
    __tablename__ = "events_outbox"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    topic_name: Mapped[str] = mapped_column(String(255))
    envelope: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(50), default=EventStatus.pending.value)
    error_message: Mapped[str | None] = mapped_column(Text)


class UsageEvent(Base, TimestampMixin):
    __tablename__ = "usage_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    company_id: Mapped[str] = mapped_column(String(36), index=True)
    event_name: Mapped[str] = mapped_column(String(100), index=True)
    quantity: Mapped[float] = mapped_column(Float, default=1.0)
    unit: Mapped[str] = mapped_column(String(50), default="count")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class AnalyticsDailyMetric(Base, TimestampMixin):
    __tablename__ = "analytics_daily_metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    company_id: Mapped[str] = mapped_column(String(36), index=True)
    metric_date: Mapped[str] = mapped_column(String(20), index=True)
    metric_name: Mapped[str] = mapped_column(String(100), index=True)
    metric_value: Mapped[float] = mapped_column(Float, default=0)
    dimension: Mapped[str | None] = mapped_column(String(100))
