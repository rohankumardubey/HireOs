from __future__ import annotations

from datetime import datetime

from pydantic import AnyUrl, BaseModel, ConfigDict, EmailStr, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Token(ORMModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserRead"


class UserSignup(BaseModel):
    full_name: str
    email: EmailStr
    password: str = Field(min_length=8)
    company_name: str
    role: str = "admin"


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthStartRequest(BaseModel):
    flow: str = "login"
    company_name: str | None = None
    full_name: str | None = None
    role: str = "admin"


class GoogleAuthStartResponse(BaseModel):
    authorization_url: str


class GoogleAuthExchangeRequest(BaseModel):
    code: str


class UserRead(ORMModel):
    id: str
    full_name: str
    email: EmailStr
    memberships: list["CompanyMembershipRead"] = []


class CompanyMembershipRead(ORMModel):
    id: str
    company_id: str
    role: str


class CompanyRead(ORMModel):
    id: str
    name: str
    slug: str
    industry: str | None = None
    size_band: str | None = None
    settings_json: dict = {}


class CompanyUpdate(BaseModel):
    industry: str | None = None
    size_band: str | None = None
    settings_json: dict | None = None


class JobCreate(BaseModel):
    title: str
    department: str | None = None
    location: str | None = None
    work_mode: str = "remote"
    experience_range: str | None = None
    employment_type: str | None = None
    salary_range: str | None = None
    status: str = "draft"
    job_description: str
    required_skills: list[str] = []
    preferred_skills: list[str] = []


class JobUpdate(BaseModel):
    title: str | None = None
    department: str | None = None
    location: str | None = None
    work_mode: str | None = None
    experience_range: str | None = None
    employment_type: str | None = None
    salary_range: str | None = None
    status: str | None = None
    job_description: str | None = None
    required_skills: list[str] | None = None
    preferred_skills: list[str] | None = None


class JobRead(ORMModel):
    id: str
    company_id: str
    title: str
    department: str | None = None
    location: str | None = None
    work_mode: str
    experience_range: str | None = None
    employment_type: str | None = None
    salary_range: str | None = None
    status: str
    job_description: str
    jd_analysis: dict = {}
    created_at: datetime


class CandidateCreate(BaseModel):
    name: str
    email: EmailStr
    phone: str | None = None
    location: str | None = None


class CandidateRead(ORMModel):
    id: str
    company_id: str
    name: str
    email: EmailStr
    phone: str | None = None
    location: str | None = None
    years_experience: float
    current_role: str | None = None
    current_company: str | None = None
    education: str | None = None
    profile_summary: str | None = None
    parsed_profile: dict = {}
    status: str
    created_at: datetime


class MatchResultRead(ORMModel):
    id: str
    candidate_id: str
    job_id: str
    overall_score: float
    match_recommendation: str
    matched_required_skills: list = []
    missing_required_skills: list = []
    matched_preferred_skills: list = []
    red_flags: list = []
    explanation: str
    confidence_score: float
    human_review_required: bool


class InterviewInviteRequest(BaseModel):
    candidate_id: str
    job_id: str
    interview_type: str = "Technical screening"
    mode: str = "text"
    meeting_provider: str = "google_meet"
    schedule_type: str = "adhoc"
    scheduled_at: datetime | None = None
    meeting_join_url: AnyUrl | None = None


class InterviewShareLinks(BaseModel):
    meeting_provider: str
    meeting_provider_label: str
    candidate_email: EmailStr
    candidate_portal_url: str
    candidate_join_url: str
    meeting_setup_url: str
    email_compose_url: str
    share_message: str
    meeting_note: str
    schedule_type: str
    schedule_label: str
    scheduled_at: datetime | None = None


class InterviewInviteResponse(ORMModel):
    id: str
    company_id: str
    job_id: str
    candidate_id: str
    interview_type: str
    mode: str
    status: str
    current_question_index: int
    consent_given: bool
    created_at: datetime
    share_links: InterviewShareLinks


class InterviewRead(ORMModel):
    id: str
    company_id: str
    job_id: str
    candidate_id: str
    interview_type: str
    mode: str
    status: str
    current_question_index: int
    consent_given: bool
    created_at: datetime


class InterviewStartRequest(BaseModel):
    consent_given: bool = True


class InterviewQuestionRead(ORMModel):
    id: str
    question_order: int
    question_text: str
    skill_category: str
    difficulty: str
    expected_concepts: list = []
    scoring_rubric: dict = {}
    follow_up_strategy: str | None = None
    is_follow_up: bool = False


class AnswerSubmitRequest(BaseModel):
    question_id: str
    answer_text: str
    answer_mode: str = "text"
    transcript_text: str | None = None
    latency_ms: int = 0


class AnswerScoreRead(ORMModel):
    id: str
    total_score: float
    skill_score: float
    clarity_score: float
    communication_score: float
    confidence_score: float
    matched_concepts: list = []
    missing_concepts: list = []
    strengths: list = []
    weaknesses: list = []
    suggested_follow_up: str | None = None
    human_review_required: bool
    explanation: str


class ReportRead(ORMModel):
    id: str
    interview_id: str
    report_markdown: str
    report_html: str
    recommended_next_step: str
    human_review_required: bool
    audit_trail: list = []


class DecisionRequest(BaseModel):
    decision: str
    notes: str | None = None
    override_ai_recommendation: bool = False


class RankingEntry(BaseModel):
    rank: int
    candidate_id: str
    candidate_name: str
    match_score: float
    interview_score: float
    final_score: float
    strengths: list[str]
    missing_skills: list[str]
    status: str
    ai_recommendation: str
    recruiter_decision: str | None = None


class AnalyticsOverview(BaseModel):
    total_candidates: int
    active_jobs: int
    interviews_completed: int
    candidates_shortlisted: int
    average_match_score: float
    average_interview_score: float
    candidates_requiring_human_review: int
    pipeline_by_stage: dict[str, int]


class GoogleIntegrationStatus(BaseModel):
    configured: bool
    connected: bool
    email: EmailStr | None = None


class GoogleConnectResponse(BaseModel):
    authorization_url: str


class CopilotQueryRequest(BaseModel):
    query: str = Field(min_length=4)
    job_id: str | None = None
    candidate_ids: list[str] = []


class CopilotEvidenceItem(BaseModel):
    label: str
    resume_match: float | None = None
    interview_score: float | None = None
    missing_skills: list[str] = []
    strength_skills: list[str] = []
    ai_recommendation: str | None = None
    match_explanation: str | None = None
    report_excerpt: str | None = None
    human_review_required: bool | None = None


class CopilotResponse(BaseModel):
    answer: str
    recommendation: str
    follow_up_questions: list[str]
    action_items: list[str]
    evidence: list[CopilotEvidenceItem]
    human_review_note: str


class CandidateComparisonRequest(BaseModel):
    candidate_ids: list[str] = Field(min_length=2, max_length=3)


class CandidateComparisonAxis(BaseModel):
    label: str
    winner_candidate_id: str
    description: str


class CandidateComparisonCandidate(BaseModel):
    candidate_id: str
    candidate_name: str
    status: str
    current_role: str | None = None
    years_experience: float
    resume_match_score: float
    interview_score: float
    final_score: float
    must_have_coverage: float
    confidence_score: float
    human_review_required: bool
    strengths: list[str]
    missing_skills: list[str]
    matched_skills: list[str]
    risk_notes: list[str]
    ai_recommendation: str
    recruiter_decision: str | None = None
    report_excerpt: str


class CandidateComparisonResponse(BaseModel):
    job_id: str
    job_title: str
    summary: str
    recommendation: str
    top_candidate_id: str
    comparison_answer: str
    axes: list[CandidateComparisonAxis]
    candidates: list[CandidateComparisonCandidate]
    recruiter_questions: list[str]
    human_review_note: str


UserRead.model_rebuild()
Token.model_rebuild()
