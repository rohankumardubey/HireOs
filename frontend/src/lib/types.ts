export interface CompanyMembership {
  id: string;
  company_id: string;
  role: string;
}

export interface User {
  id: string;
  full_name: string;
  email: string;
  memberships: CompanyMembership[];
}

export interface AuthToken {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Job {
  id: string;
  company_id: string;
  title: string;
  department?: string | null;
  location?: string | null;
  work_mode: string;
  experience_range?: string | null;
  employment_type?: string | null;
  salary_range?: string | null;
  status: string;
  job_description: string;
  jd_analysis: {
    required_skills?: string[];
    preferred_skills?: string[];
    responsibilities?: string[];
    seniority_level?: string;
    interview_focus_areas?: string[];
  };
  created_at: string;
}

export interface Candidate {
  id: string;
  company_id: string;
  name: string;
  email: string;
  phone?: string | null;
  location?: string | null;
  years_experience: number;
  current_role?: string | null;
  current_company?: string | null;
  education?: string | null;
  profile_summary?: string | null;
  parsed_profile: {
    skills?: string[];
    compliance?: {
      redaction_applied: boolean;
      redaction_count: number;
      categories_detected: string[];
      policy_note: string;
    };
    [key: string]: unknown;
  };
  status: string;
  created_at: string;
}

export interface MatchResult {
  id: string;
  candidate_id: string;
  job_id: string;
  overall_score: number;
  match_recommendation: string;
  matched_required_skills: string[];
  missing_required_skills: string[];
  matched_preferred_skills: string[];
  red_flags: string[];
  explanation: string;
  confidence_score: number;
  human_review_required: boolean;
}

export interface Interview {
  id: string;
  company_id: string;
  job_id: string;
  candidate_id: string;
  interview_type: string;
  mode: string;
  status: string;
  current_question_index: number;
  consent_given: boolean;
  created_at: string;
}

export interface InterviewQuestion {
  id: string;
  question_order: number;
  question_text: string;
  skill_category: string;
  difficulty: string;
  expected_concepts: string[];
  scoring_rubric: Record<string, number>;
  follow_up_strategy?: string | null;
  is_follow_up: boolean;
}

export interface AnswerScore {
  id?: string;
  total_score: number;
  skill_score: number;
  clarity_score: number;
  communication_score: number;
  confidence_score: number;
  matched_concepts: string[];
  missing_concepts: string[];
  strengths: string[];
  weaknesses: string[];
  suggested_follow_up?: string | null;
  human_review_required: boolean;
  explanation: string;
}

export interface Report {
  id: string;
  interview_id: string;
  report_markdown: string;
  report_html: string;
  recommended_next_step: string;
  human_review_required: boolean;
  audit_trail: Array<Record<string, unknown>>;
}

export interface InterviewInviteResponse extends Interview {
  share_links: {
    meeting_provider: string;
    meeting_provider_label: string;
    candidate_email: string;
    candidate_portal_url: string;
    candidate_portal_expires_at?: string | null;
    candidate_join_url: string;
    meeting_setup_url: string;
    email_compose_url: string;
    share_message: string;
    meeting_note: string;
    schedule_type: string;
    schedule_label: string;
    scheduled_at?: string | null;
    email_subject?: string | null;
    email_body?: string | null;
  };
}

export interface InterviewAccessLink {
  candidate_portal_url?: string | null;
  issued_at?: string | null;
  expires_at?: string | null;
  revoked_at?: string | null;
  revoked_reason?: string | null;
  is_active: boolean;
  is_expired: boolean;
  is_revoked: boolean;
  note: string;
}

export interface RecruiterDecision {
  id: string;
  decision: string;
  notes?: string | null;
  override_ai_recommendation: boolean;
  recruiter_id: string;
  recruiter_name: string;
  created_at: string;
}

export interface HiringManagerFeedback {
  id: string;
  recommendation: string;
  notes?: string | null;
  recommended_next_round?: string | null;
  hiring_manager_id: string;
  hiring_manager_name: string;
  created_at: string;
}

export interface CalibrationCase {
  id: string;
  status: string;
  assigned_to_user_id?: string | null;
  assigned_to_name?: string | null;
  due_at?: string | null;
  sla_status: string;
  resolution_summary?: string | null;
  resolution_notes?: string | null;
  resolved_by_user_id?: string | null;
  resolved_by_name?: string | null;
  resolved_at?: string | null;
  updated_at: string;
}

export interface CandidateReviewWorkspace {
  candidate_id: string;
  job_id: string;
  job_title: string;
  status: string;
  latest_match?: MatchResult | null;
  latest_interview?: Interview | null;
  latest_report?: Report | null;
  latest_decision?: RecruiterDecision | null;
  decision_history: RecruiterDecision[];
  latest_manager_feedback?: HiringManagerFeedback | null;
  manager_feedback_history: HiringManagerFeedback[];
  decision_consensus: {
    overall_status: string;
    agreement_score: number;
    requires_escalation: boolean;
    summary: string;
    conflict_reasons: string[];
    signals: Array<{
      source: string;
      label: string;
      raw_value: string;
      normalized_recommendation: string;
      rationale: string;
    }>;
  };
  calibration_case?: CalibrationCase | null;
  audit_timeline: Array<{
    timestamp: string;
    source: string;
    action: string;
    actor_label: string;
    summary: string;
    details: Record<string, unknown>;
  }>;
  can_record_decision: boolean;
  can_record_manager_feedback: boolean;
  decision_support_note: string;
}

export interface CalibrationQueueEntry {
  candidate_id: string;
  candidate_name: string;
  candidate_email: string;
  candidate_status: string;
  current_role?: string | null;
  job_id: string;
  job_title: string;
  ai_recommendation?: string | null;
  recruiter_decision?: string | null;
  hiring_manager_recommendation?: string | null;
  consensus_status: string;
  agreement_score: number;
  requires_escalation: boolean;
  priority: string;
  calibration_case?: CalibrationCase | null;
  recommended_next_step?: string | null;
  conflict_reasons: string[];
  latest_signal_at: string;
}

export interface CalibrationQueue {
  total_items: number;
  conflicted_count: number;
  mixed_count: number;
  pending_count: number;
  entries: CalibrationQueueEntry[];
}

export interface CalibrationReminderPreview {
  calibration_case_id: string;
  candidate_id: string;
  candidate_name: string;
  job_id: string;
  job_title: string;
  recipient_user_id: string;
  recipient_name: string;
  recipient_email: string;
  priority: string;
  consensus_status: string;
  reminder_reason: string;
  due_at: string;
  sla_status: string;
  reminder_attempts: number;
}

export interface CalibrationReminderPreviewResponse {
  overdue_count: number;
  due_today_count: number;
  cases: CalibrationReminderPreview[];
  policy_note: string;
}

export interface NotificationDelivery {
  id: string;
  status: string;
  recipient_email: string;
  subject: string;
  provider: string;
  notification_type: string;
  created_at: string;
  error_message?: string | null;
}

export interface CalibrationReminderRunResponse {
  sent_count: number;
  fallback_count: number;
  failed_count: number;
  deliveries: NotificationDelivery[];
}

export interface EvaluationCaseResult {
  id: string;
  case_key: string;
  role: string;
  skill_category: string;
  question: string;
  min_passing_score: number;
  strong_score: number;
  weak_score: number;
  strong_passes: boolean;
  weak_passes: boolean;
  score_separation: number;
  regression_detected: boolean;
  regression_reason?: string | null;
  details_json: {
    expected_concepts?: string[];
    strong?: AnswerScore;
    weak?: AnswerScore;
  };
}

export interface EvaluationRun {
  id: string;
  company_id: string;
  triggered_by_id?: string | null;
  dataset_name: string;
  dataset_version: string;
  scoring_policy_version: string;
  provider: string;
  status: string;
  quality_status?: string | null;
  total_cases: number;
  strong_pass_rate: number;
  weak_rejection_rate: number;
  average_score_separation: number;
  minimum_score_separation: number;
  false_negative_count: number;
  false_positive_count: number;
  regression_count: number;
  baseline_run_id?: string | null;
  error_message?: string | null;
  started_at: string;
  completed_at?: string | null;
  created_at: string;
  case_results: EvaluationCaseResult[];
}

export interface EvaluationRunList {
  runs: EvaluationRun[];
  latest?: EvaluationRun | null;
  policy_note: string;
}

export interface ResponsibleAISummary {
  total_candidates: number;
  resumes_processed: number;
  redacted_resumes: number;
  protected_signal_rate: number;
  total_redactions: number;
  human_review_candidates: number;
  human_review_rate: number;
  total_matches: number;
  human_review_matches: number;
  total_reports: number;
  human_review_reports: number;
  total_decisions: number;
  override_count: number;
  override_rate: number;
  open_calibration_cases: number;
  overdue_calibration_cases: number;
  audit_log_count: number;
  governance_event_count: number;
}

export interface ResponsibleAIRedactionCategory {
  category: string;
  count: number;
}

export interface ResponsibleAIHumanReviewBreakdown {
  label: string;
  total: number;
  requires_review: number;
  rate: number;
}

export interface ResponsibleAIGovernanceEvent {
  event_type: string;
  count: number;
}

export interface ResponsibleAICandidateSignal {
  candidate_id: string;
  candidate_name: string;
  candidate_email: string;
  status: string;
  job_id?: string | null;
  job_title?: string | null;
  match_score?: number | null;
  ai_recommendation?: string | null;
  human_review_required: boolean;
  override_ai_recommendation: boolean;
  redaction_count: number;
  redaction_categories: string[];
  open_calibration_case_count: number;
  reasons: string[];
  latest_signal_at: string;
}

export interface ResponsibleAIControl {
  name: string;
  status: string;
  evidence_count: number;
  description: string;
}

export interface ResponsibleAIDashboard {
  summary: ResponsibleAISummary;
  redaction_categories: ResponsibleAIRedactionCategory[];
  human_review_breakdown: ResponsibleAIHumanReviewBreakdown[];
  governance_events: ResponsibleAIGovernanceEvent[];
  recent_candidate_signals: ResponsibleAICandidateSignal[];
  controls: ResponsibleAIControl[];
  risk_flags: string[];
  policy_note: string;
}
