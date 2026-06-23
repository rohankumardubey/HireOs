import type {
  AnswerScore,
  AuthToken,
  CalibrationCase,
  CalibrationQueue,
  CalibrationReminderPreviewResponse,
  CalibrationReminderRunResponse,
  Candidate,
  CandidateReviewWorkspace,
  EvaluationRun,
  EvaluationRunList,
  Interview,
  InterviewAccessLink,
  InterviewInviteResponse,
  InterviewQuestion,
  Job,
  MatchResult,
  Report,
  User,
} from "@/lib/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

type RequestOptions = Omit<RequestInit, "body"> & {
  token?: string | null;
  body?: unknown;
};

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { token, body, ...requestInit } = options;
  const headers = new Headers(options.headers);
  const isFormData = body instanceof FormData;
  if (!isFormData && body !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  if (token && token !== "cookie-session") {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const requestBody: BodyInit | undefined =
    body === undefined
      ? undefined
      : isFormData
        ? body
        : JSON.stringify(body);

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...requestInit,
    headers,
    credentials: "include",
    body: requestBody,
  });

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      message = payload.detail || message;
    } catch {
      // Keep the HTTP fallback message when the response is not JSON.
    }
    throw new Error(message);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export const api = {
  signup: (payload: Record<string, string>) =>
    request<AuthToken>("/auth/signup", { method: "POST", body: payload }),
  login: (payload: { email: string; password: string }) =>
    request<AuthToken>("/auth/login", { method: "POST", body: payload }),
  logout: () => request<{ status: string }>("/auth/logout", { method: "POST" }),
  getMe: (token?: string) => request<User>("/auth/me", { token }),
  startGoogleAuth: (payload: Record<string, string>) =>
    request<{ authorization_url: string }>("/auth/google/start", {
      method: "POST",
      body: payload,
    }),
  exchangeGoogleAuth: (payload: { code: string }) =>
    request<AuthToken>("/auth/google/exchange", { method: "POST", body: payload }),

  getCompany: (token: string) =>
    request<Record<string, unknown> & { name: string }>("/companies/me", { token }),
  updateCompany: (token: string, payload: Record<string, string>) =>
    request<Record<string, unknown>>("/companies/me", {
      method: "PATCH",
      token,
      body: payload,
    }),

  getJobs: (token: string) => request<Job[]>("/jobs", { token }),
  getJob: (token: string, jobId: string) => request<Job>(`/jobs/${jobId}`, { token }),
  createJob: (token: string, payload: Record<string, unknown>) =>
    request<Job>("/jobs", { method: "POST", token, body: payload }),
  parseJob: (token: string, jobId: string) =>
    request<Job>(`/jobs/${jobId}/parse`, { method: "POST", token }),
  getJobCandidates: (token: string, jobId: string) =>
    request<Array<{ candidate: Record<string, unknown>; match: Record<string, unknown> }>>(
      `/jobs/${jobId}/candidates`,
      { token },
    ),
  getJobRanking: (token: string, jobId: string) =>
    request<Array<Record<string, unknown> & {
      rank: number;
      candidate_id: string;
      candidate_name: string;
      match_score: number;
      interview_score: number;
      final_score: number;
      missing_skills: string[];
      status: string;
      ai_recommendation: string;
      recruiter_decision?: string | null;
    }>>(`/jobs/${jobId}/ranking`, { token }),
  simulateJobRanking: (
    token: string,
    jobId: string,
    payload: Record<string, number>,
  ) =>
    request<Record<string, unknown> & {
      summary: string;
      policy_note: string;
      top_mover_candidate_id?: string | null;
      candidates: Array<Record<string, unknown> & {
        candidate_id: string;
        candidate_name: string;
        baseline_rank: number;
        simulated_rank: number;
        rank_change: number;
        baseline_score: number;
        simulated_score: number;
        match_score: number;
        interview_score: number;
        required_skill_coverage: number;
        missing_skills: string[];
        human_review_required: boolean;
        ai_recommendation: string;
        recruiter_decision?: string | null;
        movement_reason: string;
      }>;
    }>(`/jobs/${jobId}/ranking/simulate`, { method: "POST", token, body: payload }),

  getCandidates: (token: string) => request<Candidate[]>("/candidates", { token }),
  getCandidate: (token: string, candidateId: string) =>
    request<Candidate>(`/candidates/${candidateId}`, { token }),
  uploadResume: (token: string, formData: FormData) =>
    request<{ candidate: Candidate; parsed_resume: Record<string, unknown> }>(
      "/candidates/upload-resume",
      { method: "POST", token, body: formData },
    ),
  matchCandidate: (token: string, candidateId: string, jobId: string) =>
    request<MatchResult>(`/candidates/${candidateId}/match-job/${jobId}`, {
      method: "POST",
      token,
    }),
  getCandidateReviewWorkspace: (token: string, candidateId: string, jobId: string) =>
    request<CandidateReviewWorkspace>(
      `/candidates/${candidateId}/review-workspace/${jobId}`,
      { token },
    ),
  getCalibrationQueue: (token: string) =>
    request<CalibrationQueue>("/candidates/calibration-queue", { token }),
  updateCalibrationCase: (
    token: string,
    candidateId: string,
    jobId: string,
    payload: Record<string, unknown>,
  ) =>
    request<CalibrationCase>(`/candidates/${candidateId}/calibration-case/${jobId}`, {
      method: "PATCH",
      token,
      body: payload,
    }),
  previewCalibrationReminders: (token: string) =>
    request<CalibrationReminderPreviewResponse>(
      "/candidates/calibration-queue/reminders/preview",
      { token },
    ),
  runCalibrationReminders: (token: string) =>
    request<CalibrationReminderRunResponse>(
      "/candidates/calibration-queue/reminders/run",
      { method: "POST", token },
    ),

  inviteInterview: (token: string, payload: Record<string, unknown>) =>
    request<InterviewInviteResponse>("/interviews/invite", {
      method: "POST",
      token,
      body: payload,
    }),
  startInterview: (interviewId: string, accessToken: string | null) =>
    request<Interview>(`/interviews/${interviewId}/start`, {
      method: "POST",
      body: { consent_given: true, access_token: accessToken },
    }),
  getNextQuestion: (interviewId: string, accessToken: string | null) =>
    request<InterviewQuestion | { done: true }>(
      `/interviews/${interviewId}/next-question?access=${encodeURIComponent(accessToken || "")}`,
    ),
  submitAnswer: (interviewId: string, payload: Record<string, unknown>) =>
    request<{ score: AnswerScore; next_question_index: number }>(
      `/interviews/${interviewId}/answers`,
      { method: "POST", body: payload },
    ),
  completeInterview: (interviewId: string, accessToken: string | null) =>
    request<Report>(
      `/interviews/${interviewId}/complete?access=${encodeURIComponent(accessToken || "")}`,
      { method: "POST" },
    ),
  submitRecruiterDecision: (
    token: string,
    interviewId: string,
    payload: Record<string, unknown>,
  ) =>
    request<Record<string, unknown>>(`/interviews/${interviewId}/decision`, {
      method: "POST",
      token,
      body: payload,
    }),
  submitHiringManagerFeedback: (
    token: string,
    interviewId: string,
    payload: Record<string, unknown>,
  ) =>
    request<Record<string, unknown>>(
      `/interviews/${interviewId}/hiring-manager-feedback`,
      { method: "POST", token, body: payload },
    ),
  sendInterviewEmail: (token: string, interviewId: string) =>
    request<Record<string, unknown>>(`/interviews/${interviewId}/send-email`, {
      method: "POST",
      token,
    }),
  getInterviewEmailDeliveries: (token: string, interviewId: string) =>
    request<Array<Record<string, unknown> & {
      id: string;
      status: string;
      recipient_email: string;
      subject: string;
      provider: string;
      created_at: string;
      error_message?: string | null;
    }>>(`/interviews/${interviewId}/email-deliveries`, { token }),
  previewInterviewReminders: (token: string) =>
    request<Record<string, unknown> & {
      invited_no_show_count: number;
      incomplete_count: number;
      candidates: Array<{
        interview_id: string;
        candidate_id: string;
        candidate_name: string;
        candidate_email: string;
        job_id: string;
        job_title: string;
        reminder_type: string;
        reminder_reason: string;
        last_activity_at: string;
        reminder_attempts: number;
      }>;
      policy_note: string;
    }>("/interviews/reminders/preview", { token }),
  runInterviewReminders: (token: string) =>
    request<CalibrationReminderRunResponse>("/interviews/reminders/run", {
      method: "POST",
      token,
    }),
  getInterviewAccessLink: (token: string, interviewId: string) =>
    request<InterviewAccessLink>(`/interviews/${interviewId}/access-link`, { token }),
  refreshInterviewAccessLink: (token: string, interviewId: string) =>
    request<InterviewAccessLink>(`/interviews/${interviewId}/access-link/refresh`, {
      method: "POST",
      token,
    }),
  revokeInterviewAccessLink: (token: string, interviewId: string) =>
    request<InterviewAccessLink>(`/interviews/${interviewId}/access-link/revoke`, {
      method: "POST",
      token,
    }),
  getInterviewATSExports: (token: string, interviewId: string) =>
    request<Array<Record<string, unknown> & {
      id: string;
      status: string;
      event_name: string;
      provider: string;
      target_url: string;
      response_status_code?: number | null;
      error_message?: string | null;
      created_at: string;
    }>>(`/interviews/${interviewId}/ats-exports`, { token }),
  exportInterviewToATS: (token: string, interviewId: string) =>
    request<Record<string, unknown>>(`/interviews/${interviewId}/export-ats`, {
      method: "POST",
      token,
    }),

  getReports: (token: string) => request<Report[]>("/reports", { token }),
  getReport: (token: string, reportId: string) =>
    request<Report>(`/reports/${reportId}`, { token }),
  getAnalyticsOverview: (token: string) =>
    request<{
      total_candidates: number;
      active_jobs: number;
      interviews_completed: number;
      candidates_shortlisted: number;
      average_match_score: number;
      average_interview_score: number;
      candidates_requiring_human_review: number;
      pipeline_by_stage: Record<string, number>;
    }>("/analytics/overview", { token }),
  getAnalyticsFunnel: (token: string) =>
    request<{ stages: Array<{ stage: string; count: number }> }>("/analytics/funnel", {
      token,
    }),
  getModelQuality: (token: string) =>
    request<{
      average_answer_score: number;
      override_rate: number;
      human_in_loop: boolean;
      compliance_note: string;
    }>("/analytics/model-quality", { token }),

  getEvaluationRuns: (token: string) =>
    request<EvaluationRunList>("/evaluations/runs", { token }),
  createEvaluationRun: (token: string) =>
    request<EvaluationRun>("/evaluations/runs", { method: "POST", token }),
  getEvaluationRun: (token: string, runId: string) =>
    request<EvaluationRun>(`/evaluations/runs/${runId}`, { token }),

  getGoogleIntegrationStatus: (token: string) =>
    request<{ configured: boolean; connected: boolean; email?: string | null }>(
      "/integrations/google/status",
      { token },
    ),
  connectGoogle: (token: string) =>
    request<{ authorization_url: string }>("/integrations/google/connect", {
      method: "POST",
      token,
    }),
  disconnectGoogle: (token: string) =>
    request<{ status: string }>("/integrations/google", { method: "DELETE", token }),
  getZoomIntegrationStatus: (token: string) =>
    request<{ configured: boolean; connected: boolean; email?: string | null }>(
      "/integrations/zoom/status",
      { token },
    ),
  connectZoom: (token: string) =>
    request<{ authorization_url: string }>("/integrations/zoom/connect", {
      method: "POST",
      token,
    }),
  disconnectZoom: (token: string) =>
    request<{ status: string }>("/integrations/zoom", { method: "DELETE", token }),
  getATSWebhookStatus: (token: string) =>
    request<{
      configured: boolean;
      enabled: boolean;
      provider_label: string;
      endpoint_url?: string | null;
      export_stages: string[];
      has_auth_token: boolean;
      has_signing_secret: boolean;
    }>("/integrations/ats-webhook/status", { token }),
  updateATSWebhook: (token: string, payload: Record<string, unknown>) =>
    request<{
      configured: boolean;
      enabled: boolean;
      provider_label: string;
      endpoint_url?: string | null;
      export_stages: string[];
      has_auth_token: boolean;
      has_signing_secret: boolean;
    }>("/integrations/ats-webhook", { method: "PATCH", token, body: payload }),
  testATSWebhook: (token: string) =>
    request<{ status: string }>("/integrations/ats-webhook/test", {
      method: "POST",
      token,
    }),

  copilotQuery: (token: string, payload: Record<string, unknown>) =>
    request<Record<string, unknown> & {
      answer: string;
      recommendation: string;
      follow_up_questions: string[];
      action_items: string[];
      evidence: Array<{
        label: string;
        resume_match?: number | null;
        interview_score?: number | null;
        missing_skills: string[];
        strength_skills: string[];
        ai_recommendation?: string | null;
        match_explanation?: string | null;
        report_excerpt?: string | null;
        human_review_required?: boolean | null;
      }>;
      human_review_note: string;
    }>("/copilot/query", { method: "POST", token, body: payload }),
  compareCandidates: (
    token: string,
    jobId: string,
    payload: { candidate_ids: string[] },
  ) =>
    request<Record<string, unknown> & {
      job_id: string;
      job_title: string;
      summary: string;
      recommendation: string;
      top_candidate_id: string;
      comparison_answer: string;
      human_review_note: string;
      axes: Array<{
        label: string;
        winner_candidate_id: string;
        description: string;
      }>;
      recruiter_questions: string[];
      candidates: Array<Record<string, unknown> & {
        candidate_id: string;
        candidate_name: string;
        status: string;
        current_role?: string | null;
        years_experience: number;
        resume_match_score: number;
        interview_score: number;
        final_score: number;
        must_have_coverage: number;
        confidence_score: number;
        human_review_required: boolean;
        strengths: string[];
        missing_skills: string[];
        matched_skills: string[];
        risk_notes: string[];
        ai_recommendation: string;
        recruiter_decision?: string | null;
        report_excerpt: string;
      }>;
    }>(`/comparison/jobs/${jobId}`, { method: "POST", token, body: payload }),
};
