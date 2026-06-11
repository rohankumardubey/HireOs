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
    candidate_portal_expires_at: datetime | None = None
    candidate_join_url: str
    meeting_setup_url: str
    email_compose_url: str
    share_message: str
    meeting_note: str
    schedule_type: str
    schedule_label: str
    scheduled_at: datetime | None = None
    email_subject: str | None = None
    email_body: str | None = None


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


class NotificationDeliveryRead(ORMModel):
    id: str
    company_id: str
    interview_id: str | None = None
    candidate_id: str | None = None
    recruiter_id: str | None = None
    channel: str
    notification_type: str
    recipient_email: EmailStr
    subject: str
    body_text: str
    provider: str
    status: str
    error_message: str | None = None
    metadata_json: dict = {}
    created_at: datetime


class InterviewEmailSendResponse(BaseModel):
    status: str
    delivery: NotificationDeliveryRead


class WebhookDeliveryRead(ORMModel):
    id: str
    company_id: str
    interview_id: str | None = None
    candidate_id: str | None = None
    job_id: str | None = None
    recruiter_id: str | None = None
    integration_name: str
    event_name: str
    target_url: str
    provider: str
    status: str
    response_status_code: int | None = None
    error_message: str | None = None
    request_body: str
    response_body: str | None = None
    metadata_json: dict = {}
    created_at: datetime


class ATSWebhookExportResponse(BaseModel):
    status: str
    delivery: WebhookDeliveryRead


class ATSWebhookTriggerResult(BaseModel):
    status: str
    delivery: WebhookDeliveryRead | None = None
    reason: str | None = None


class ReminderCandidatePreview(BaseModel):
    interview_id: str
    candidate_id: str
    candidate_name: str
    candidate_email: EmailStr
    job_id: str
    job_title: str
    reminder_type: str
    reminder_reason: str
    last_activity_at: datetime
    reminder_attempts: int


class ReminderPreviewResponse(BaseModel):
    invited_no_show_count: int
    incomplete_count: int
    candidates: list[ReminderCandidatePreview]
    policy_note: str


class ReminderRunResponse(BaseModel):
    sent_count: int
    fallback_count: int
    failed_count: int
    deliveries: list[NotificationDeliveryRead]


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
    access_token: str | None = None


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
    access_token: str | None = None


class InterviewAccessLinkRead(BaseModel):
    candidate_portal_url: str | None = None
    issued_at: datetime | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    revoked_reason: str | None = None
    is_active: bool
    is_expired: bool
    is_revoked: bool
    note: str


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


class RecruiterDecisionResponse(BaseModel):
    status: str
    ats_export: ATSWebhookTriggerResult


class RecruiterDecisionRead(BaseModel):
    id: str
    decision: str
    notes: str | None = None
    override_ai_recommendation: bool = False
    recruiter_id: str
    recruiter_name: str
    created_at: datetime


class HiringManagerFeedbackRequest(BaseModel):
    recommendation: str
    notes: str | None = None
    recommended_next_round: str | None = None


class HiringManagerFeedbackRead(BaseModel):
    id: str
    recommendation: str
    notes: str | None = None
    recommended_next_round: str | None = None
    hiring_manager_id: str
    hiring_manager_name: str
    created_at: datetime


class HiringManagerFeedbackResponse(BaseModel):
    status: str
    feedback: HiringManagerFeedbackRead


class DecisionConsensusSignalRead(BaseModel):
    source: str
    label: str
    raw_value: str
    normalized_recommendation: str
    rationale: str


class DecisionConsensusRead(BaseModel):
    overall_status: str
    agreement_score: float
    requires_escalation: bool
    summary: str
    conflict_reasons: list[str] = Field(default_factory=list)
    signals: list[DecisionConsensusSignalRead] = Field(default_factory=list)


class CalibrationCaseRead(BaseModel):
    id: str
    status: str
    assigned_to_user_id: str | None = None
    assigned_to_name: str | None = None
    due_at: datetime | None = None
    sla_status: str
    resolution_summary: str | None = None
    resolution_notes: str | None = None
    resolved_by_user_id: str | None = None
    resolved_by_name: str | None = None
    resolved_at: datetime | None = None
    updated_at: datetime


class CalibrationCaseUpdateRequest(BaseModel):
    status: str | None = None
    assigned_to_user_id: str | None = None
    assign_to_me: bool = False
    clear_assignee: bool = False
    due_at: datetime | None = None
    resolution_summary: str | None = None
    resolution_notes: str | None = None


class ReviewTimelineEntry(BaseModel):
    timestamp: datetime
    source: str
    action: str
    actor_label: str
    summary: str
    details: dict = Field(default_factory=dict)


class CandidateReviewWorkspaceRead(BaseModel):
    candidate_id: str
    job_id: str
    job_title: str
    status: str
    latest_match: MatchResultRead | None = None
    latest_interview: InterviewRead | None = None
    latest_report: ReportRead | None = None
    latest_decision: RecruiterDecisionRead | None = None
    decision_history: list[RecruiterDecisionRead] = Field(default_factory=list)
    latest_manager_feedback: HiringManagerFeedbackRead | None = None
    manager_feedback_history: list[HiringManagerFeedbackRead] = Field(default_factory=list)
    decision_consensus: DecisionConsensusRead
    calibration_case: CalibrationCaseRead | None = None
    audit_timeline: list[ReviewTimelineEntry] = Field(default_factory=list)
    can_record_decision: bool
    can_record_manager_feedback: bool
    decision_support_note: str


class CalibrationQueueEntryRead(BaseModel):
    candidate_id: str
    candidate_name: str
    candidate_email: str
    candidate_status: str
    current_role: str | None = None
    job_id: str
    job_title: str
    ai_recommendation: str | None = None
    recruiter_decision: str | None = None
    hiring_manager_recommendation: str | None = None
    consensus_status: str
    agreement_score: float
    requires_escalation: bool
    priority: str
    calibration_case: CalibrationCaseRead | None = None
    recommended_next_step: str | None = None
    conflict_reasons: list[str] = Field(default_factory=list)
    latest_signal_at: datetime


class CalibrationQueueRead(BaseModel):
    total_items: int
    conflicted_count: int
    mixed_count: int
    pending_count: int
    entries: list[CalibrationQueueEntryRead] = Field(default_factory=list)


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


class RankingSimulationRequest(BaseModel):
    resume_weight: float = Field(default=55, ge=0, le=100)
    interview_weight: float = Field(default=45, ge=0, le=100)
    missing_skill_penalty: float = Field(default=6, ge=0, le=25)
    human_review_penalty: float = Field(default=8, ge=0, le=25)
    shortlist_boost: float = Field(default=4, ge=0, le=20)


class RankingSimulationConfigRead(BaseModel):
    resume_weight: float
    interview_weight: float
    missing_skill_penalty: float
    human_review_penalty: float
    shortlist_boost: float


class RankingSimulationCandidate(BaseModel):
    candidate_id: str
    candidate_name: str
    baseline_rank: int
    simulated_rank: int
    rank_change: int
    baseline_score: float
    simulated_score: float
    match_score: float
    interview_score: float
    required_skill_coverage: float
    missing_skills: list[str]
    human_review_required: bool
    ai_recommendation: str
    recruiter_decision: str | None = None
    movement_reason: str


class RankingSimulationResponse(BaseModel):
    job_id: str
    job_title: str
    summary: str
    top_mover_candidate_id: str | None = None
    config: RankingSimulationConfigRead
    candidates: list[RankingSimulationCandidate]
    policy_note: str


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


class ZoomIntegrationStatus(BaseModel):
    configured: bool
    connected: bool
    email: EmailStr | None = None


class ATSWebhookStatus(BaseModel):
    configured: bool
    enabled: bool
    provider_label: str
    endpoint_url: str | None = None
    export_stages: list[str] = Field(default_factory=list)
    has_auth_token: bool = False
    has_signing_secret: bool = False


class ATSWebhookUpdateRequest(BaseModel):
    enabled: bool = False
    provider_label: str = "ATS webhook"
    endpoint_url: AnyUrl | None = None
    auth_token: str | None = None
    signing_secret: str | None = None
    export_stages: list[str] = Field(default_factory=lambda: ["shortlisted", "moved_to_next_round", "hired"])


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
