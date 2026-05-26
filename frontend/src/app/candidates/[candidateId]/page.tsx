"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useState } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { useAuth } from "@/hooks/use-auth";
import { api } from "@/lib/api";
import type { InterviewInviteResponse, MatchResult } from "@/lib/types";
import { formatScore, titleCase } from "@/lib/utils";

const decisionOptions = [
  { value: "human_review_required", label: "Mark for human review" },
  { value: "shortlisted", label: "Shortlist" },
  { value: "moved_to_next_round", label: "Move to next round" },
  { value: "rejected", label: "Reject" },
  { value: "hired", label: "Mark as hired" },
  { value: "archived", label: "Archive" },
];

type BadgeTone = "success" | "warning" | "danger" | "brand" | "neutral";

function statusTone(status?: string): BadgeTone {
  if (!status) {
    return "neutral";
  }
  if (status.includes("reject") || status.includes("archived")) {
    return "danger";
  }
  if (status.includes("review")) {
    return "warning";
  }
  if (status.includes("shortlist") || status.includes("hired") || status.includes("next_round")) {
    return "success";
  }
  return "brand";
}

export default function CandidateDetailPage() {
  const auth = useAuth();
  const params = useParams<{ candidateId: string }>();
  const candidateId = params.candidateId;
  const [selectedJobId, setSelectedJobId] = useState("");
  const [interviewMode, setInterviewMode] = useState("text");
  const [scheduleType, setScheduleType] = useState("adhoc");
  const [scheduledAt, setScheduledAt] = useState("");
  const [meetingProvider, setMeetingProvider] = useState("google_meet");
  const [meetingJoinUrl, setMeetingJoinUrl] = useState("");
  const [matchResult, setMatchResult] = useState<MatchResult | null>(null);
  const [inviteResult, setInviteResult] = useState<InterviewInviteResponse | null>(null);
  const [decision, setDecision] = useState("human_review_required");
  const [decisionNotes, setDecisionNotes] = useState("");
  const [overrideRecommendation, setOverrideRecommendation] = useState(false);

  const candidate = useQuery({
    queryKey: ["candidate", auth.token, candidateId],
    queryFn: () => api.getCandidate(auth.token as string, candidateId),
    enabled: Boolean(auth.token && candidateId),
  });
  const jobs = useQuery({
    queryKey: ["jobs", auth.token],
    queryFn: () => api.getJobs(auth.token as string),
    enabled: Boolean(auth.token),
  });
  const googleStatus = useQuery({
    queryKey: ["google-status", auth.token],
    queryFn: () => api.getGoogleIntegrationStatus(auth.token as string),
    enabled: Boolean(auth.token),
  });
  const zoomStatus = useQuery({
    queryKey: ["zoom-status", auth.token],
    queryFn: () => api.getZoomIntegrationStatus(auth.token as string),
    enabled: Boolean(auth.token),
  });
  const reviewWorkspace = useQuery({
    queryKey: ["candidate-review-workspace", auth.token, candidateId, selectedJobId],
    queryFn: () => api.getCandidateReviewWorkspace(auth.token as string, candidateId, selectedJobId),
    enabled: Boolean(auth.token && candidateId && selectedJobId),
  });
  const activeInterviewId = inviteResult?.id || reviewWorkspace.data?.latest_interview?.id || null;
  const emailDeliveries = useQuery({
    queryKey: ["interview-email-deliveries", auth.token, activeInterviewId],
    queryFn: () => api.getInterviewEmailDeliveries(auth.token as string, activeInterviewId as string),
    enabled: Boolean(auth.token && activeInterviewId),
  });
  const atsExports = useQuery({
    queryKey: ["interview-ats-exports", auth.token, activeInterviewId],
    queryFn: () => api.getInterviewATSExports(auth.token as string, activeInterviewId as string),
    enabled: Boolean(auth.token && activeInterviewId),
  });

  const matchMutation = useMutation({
    mutationFn: () => api.matchCandidate(auth.token as string, candidateId, selectedJobId),
    onSuccess: async (result) => {
      setMatchResult(result);
      await Promise.all([candidate.refetch(), reviewWorkspace.refetch()]);
    },
  });

  const inviteMutation = useMutation({
    mutationFn: () =>
      api.inviteInterview(auth.token as string, {
        candidate_id: candidateId,
        job_id: selectedJobId,
        interview_type: "Technical screening",
        mode: interviewMode,
        meeting_provider: meetingProvider,
        schedule_type: scheduleType,
        scheduled_at: scheduledAt ? new Date(scheduledAt).toISOString() : null,
        meeting_join_url: meetingJoinUrl || null,
      }),
    onSuccess: async (interview) => {
      setInviteResult(interview);
      await Promise.all([candidate.refetch(), reviewWorkspace.refetch(), emailDeliveries.refetch(), atsExports.refetch()]);
    },
  });

  const recruiterDecisionMutation = useMutation({
    mutationFn: () =>
      api.submitRecruiterDecision(auth.token as string, reviewWorkspace.data?.latest_interview?.id as string, {
        decision,
        notes: decisionNotes || null,
        override_ai_recommendation: overrideRecommendation,
      }),
    onSuccess: async () => {
      setDecisionNotes("");
      setOverrideRecommendation(false);
      await Promise.all([candidate.refetch(), reviewWorkspace.refetch(), atsExports.refetch()]);
    },
  });

  const sendEmailMutation = useMutation({
    mutationFn: () => api.sendInterviewEmail(auth.token as string, activeInterviewId as string),
    onSuccess: async () => {
      await emailDeliveries.refetch();
    },
  });
  const exportToATSMutation = useMutation({
    mutationFn: () => api.exportInterviewToATS(auth.token as string, activeInterviewId as string),
    onSuccess: async () => {
      await atsExports.refetch();
    },
  });

  const inviteDisabled =
    !selectedJobId ||
    inviteMutation.isPending ||
    (interviewMode === "video" &&
      meetingProvider === "zoom" &&
      !zoomStatus.data?.connected &&
      !meetingJoinUrl.trim()) ||
    (interviewMode === "video" &&
      meetingProvider === "google_meet" &&
      !googleStatus.data?.connected &&
      !meetingJoinUrl.trim()) ||
    (interviewMode === "video" && scheduleType === "scheduled" && !scheduledAt);

  const reviewDecisionDisabled =
    recruiterDecisionMutation.isPending ||
    !reviewWorkspace.data?.can_record_decision ||
    !reviewWorkspace.data?.latest_interview?.id;

  return (
    <AppShell
      title={candidate.data?.name || "Candidate detail"}
      subtitle="Inspect the parsed resume profile, run role matching, launch an AI interview, send branded invites, and record the final recruiter-controlled decision with auditability."
    >
      <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
        <Card>
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-display text-3xl font-semibold text-text">
                {candidate.data?.name}
              </h3>
              <p className="mt-2 text-sm text-muted">{candidate.data?.email}</p>
            </div>
            <Badge tone={statusTone(candidate.data?.status)}>
              {titleCase(candidate.data?.status || "applied")}
            </Badge>
          </div>
          <div className="mt-6 grid gap-3 md:grid-cols-2">
            <div className="rounded-[20px] bg-white/70 px-4 py-3">
              <p className="text-xs uppercase tracking-[0.2em] text-muted-soft">Experience</p>
              <p className="mt-2 font-semibold text-text">{candidate.data?.years_experience} years</p>
            </div>
            <div className="rounded-[20px] bg-white/70 px-4 py-3">
              <p className="text-xs uppercase tracking-[0.2em] text-muted-soft">Current role</p>
              <p className="mt-2 font-semibold text-text">
                {candidate.data?.current_role || "Not provided"}
              </p>
            </div>
          </div>
          <p className="mt-6 text-sm leading-7 text-muted">
            {candidate.data?.profile_summary || "Parsed resume summary unavailable."}
          </p>
          <div className="mt-6 flex flex-wrap gap-2">
            {((candidate.data?.parsed_profile.skills as string[]) || []).map((skill) => (
              <Badge key={skill} tone="brand">
                {skill}
              </Badge>
            ))}
          </div>
        </Card>

        <Card>
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">
            Next actions
          </p>
          <div className="mt-4 space-y-4">
            <label className="block">
              <span className="text-sm font-medium text-muted">Select a job</span>
              <select
                className="mt-2 w-full rounded-2xl border border-border bg-white/80 px-4 py-3 outline-none"
                value={selectedJobId}
                onChange={(event) => setSelectedJobId(event.target.value)}
              >
                <option value="">Choose a role...</option>
                {jobs.data?.map((job) => (
                  <option key={job.id} value={job.id}>
                    {job.title}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="text-sm font-medium text-muted">Interview mode</span>
              <select
                className="mt-2 w-full rounded-2xl border border-border bg-white/80 px-4 py-3 outline-none"
                value={interviewMode}
                onChange={(event) => {
                  const nextMode = event.target.value;
                  setInterviewMode(nextMode);
                  setInviteResult(null);
                }}
              >
                <option value="text">Text interview</option>
                <option value="voice">Voice interview</option>
                <option value="video">Video interview</option>
              </select>
            </label>
            {interviewMode === "video" ? (
              <>
                <label className="block">
                  <span className="text-sm font-medium text-muted">Session timing</span>
                  <select
                    className="mt-2 w-full rounded-2xl border border-border bg-white/80 px-4 py-3 outline-none"
                    value={scheduleType}
                    onChange={(event) => setScheduleType(event.target.value)}
                  >
                    <option value="adhoc">Ad hoc now</option>
                    <option value="scheduled">Scheduled for later</option>
                  </select>
                </label>
                {scheduleType === "scheduled" ? (
                  <label className="block">
                    <span className="text-sm font-medium text-muted">Scheduled time</span>
                    <input
                      type="datetime-local"
                      className="mt-2 w-full rounded-2xl border border-border bg-white/80 px-4 py-3 outline-none"
                      value={scheduledAt}
                      onChange={(event) => setScheduledAt(event.target.value)}
                    />
                  </label>
                ) : null}
              </>
            ) : null}
            <label className="block">
              <span className="text-sm font-medium text-muted">Meeting provider</span>
              <select
                className="mt-2 w-full rounded-2xl border border-border bg-white/80 px-4 py-3 outline-none"
                value={meetingProvider}
                onChange={(event) => {
                  setMeetingProvider(event.target.value);
                  setInviteResult(null);
                }}
              >
                <option value="google_meet">Google Meet</option>
                <option value="zoom">Zoom</option>
              </select>
            </label>
            {interviewMode === "video" ? (
              <label className="block">
                <span className="text-sm font-medium text-muted">Live meeting join URL</span>
                <input
                  type="url"
                  className="mt-2 w-full rounded-2xl border border-border bg-white/80 px-4 py-3 outline-none"
                  placeholder={
                    meetingProvider === "zoom"
                      ? zoomStatus.data?.connected
                        ? "Auto-generated from connected Zoom account if left empty"
                        : "https://zoom.us/j/..."
                      : googleStatus.data?.connected
                        ? "Auto-generated from connected Google account if left empty"
                        : "https://meet.google.com/..."
                  }
                  value={meetingJoinUrl}
                  onChange={(event) => setMeetingJoinUrl(event.target.value)}
                />
                <p className="mt-2 text-xs leading-6 text-muted">
                  {meetingProvider === "google_meet"
                    ? googleStatus.data?.connected
                      ? "Because Google is connected, HireOS can auto-create a Meet link if you leave this blank. You can still paste an existing Meet URL if you already have one."
                      : "Connect Google in Settings to auto-generate a Meet link. Without that connection, paste an existing Meet URL here."
                    : zoomStatus.data?.connected
                      ? "Because Zoom is connected, HireOS can auto-create a real Zoom meeting if you leave this blank. You can still paste an existing Zoom join link if you already have one."
                      : "Connect Zoom in Settings to auto-generate a Zoom meeting. Without that connection, paste an existing Zoom join link here."}
                </p>
              </label>
            ) : null}
            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                disabled={!selectedJobId || matchMutation.isPending}
                onClick={() => matchMutation.mutate()}
                className="rounded-full bg-brand px-5 py-3 text-sm font-semibold text-white disabled:opacity-60"
              >
                Run resume match
              </button>
              <button
                type="button"
                disabled={inviteDisabled}
                onClick={() => inviteMutation.mutate()}
                className="rounded-full border border-border bg-white/70 px-5 py-3 text-sm font-semibold text-text disabled:opacity-60"
              >
                Invite to interview
              </button>
            </div>
            {inviteResult ? (
              <div className="rounded-[24px] bg-success-soft px-4 py-4 text-sm text-text">
                <p className="font-semibold text-text">
                  {interviewMode === "video" ? "Live video" : interviewMode === "voice" ? "Voice" : "Text"}{" "}
                  interview created for {inviteResult.share_links.candidate_email}.
                </p>
                <p className="mt-2 text-sm leading-7 text-muted">
                  {inviteResult.share_links.meeting_note}
                </p>
                {inviteResult.share_links.scheduled_at ? (
                  <p className="mt-2 text-sm font-medium text-text">
                    {inviteResult.share_links.schedule_label}:{" "}
                    {new Date(inviteResult.share_links.scheduled_at).toLocaleString()}
                  </p>
                ) : (
                  <p className="mt-2 text-sm font-medium text-text">
                    {inviteResult.share_links.schedule_label}
                  </p>
                )}
                <div className="mt-4 flex flex-wrap gap-3">
                  <a
                    href={inviteResult.share_links.meeting_setup_url}
                    target="_blank"
                    rel="noreferrer"
                    className="rounded-full bg-brand px-4 py-2 text-sm font-semibold text-white"
                  >
                    {interviewMode === "video"
                      ? "Open live meeting link"
                      : `Open ${inviteResult.share_links.meeting_provider_label} setup`}
                  </a>
                  <a
                    href={inviteResult.share_links.email_compose_url}
                    className="rounded-full border border-border bg-white/70 px-4 py-2 text-sm font-semibold text-text"
                  >
                    Email candidate
                  </a>
                  <button
                    type="button"
                    disabled={sendEmailMutation.isPending}
                    onClick={() => sendEmailMutation.mutate()}
                    className="rounded-full border border-border bg-white/70 px-4 py-2 text-sm font-semibold text-text disabled:opacity-60"
                  >
                    {sendEmailMutation.isPending ? "Sending..." : "Send with HireOS"}
                  </button>
                  <a
                    href={
                      interviewMode === "video"
                        ? inviteResult.share_links.candidate_join_url
                        : inviteResult.share_links.candidate_portal_url
                    }
                    target="_blank"
                    rel="noreferrer"
                    className="rounded-full border border-border bg-white/70 px-4 py-2 text-sm font-semibold text-text"
                  >
                    {interviewMode === "video" ? "Open candidate join link" : "Open candidate interview"}
                  </a>
                </div>
                <div className="mt-4 rounded-[20px] bg-white/80 px-4 py-4">
                  <p className="text-xs uppercase tracking-[0.2em] text-muted-soft">
                    {interviewMode === "video" ? "Candidate video join link" : "Candidate interview link"}
                  </p>
                  <a
                    href={
                      interviewMode === "video"
                        ? inviteResult.share_links.candidate_join_url
                        : inviteResult.share_links.candidate_portal_url
                    }
                    target="_blank"
                    rel="noreferrer"
                    className="mt-2 block font-semibold text-brand"
                  >
                    {interviewMode === "video"
                      ? inviteResult.share_links.candidate_join_url
                      : inviteResult.share_links.candidate_portal_url}
                  </a>
                </div>
                {interviewMode === "video" ? (
                  <div className="mt-4 rounded-[20px] bg-white/80 px-4 py-4">
                    <p className="text-xs uppercase tracking-[0.2em] text-muted-soft">
                      HireOS workflow reference
                    </p>
                    <a
                      href={inviteResult.share_links.candidate_portal_url}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-2 block font-semibold text-brand"
                    >
                      {inviteResult.share_links.candidate_portal_url}
                    </a>
                  </div>
                ) : null}
                <div className="mt-4 rounded-[20px] border border-border bg-white/80 px-4 py-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-xs uppercase tracking-[0.2em] text-muted-soft">
                      Invite delivery history
                    </p>
                    <Badge tone={emailDeliveries.data?.[0]?.status === "delivered" ? "success" : "neutral"}>
                      {emailDeliveries.data?.length ? titleCase(emailDeliveries.data[0].status) : "Not sent"}
                    </Badge>
                  </div>
                  {sendEmailMutation.error ? (
                    <p className="mt-3 text-sm text-rose-700">{sendEmailMutation.error.message}</p>
                  ) : null}
                  <div className="mt-3 space-y-3">
                    {emailDeliveries.data?.length ? (
                      emailDeliveries.data.map((delivery) => (
                        <div
                          key={delivery.id}
                          className="rounded-[16px] border border-border bg-surface-elevated px-3 py-3"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-3">
                            <p className="text-sm font-semibold text-text">
                              {titleCase(delivery.status)} via {titleCase(delivery.provider)}
                            </p>
                            <p className="text-xs uppercase tracking-[0.16em] text-muted-soft">
                              {new Date(delivery.created_at).toLocaleString()}
                            </p>
                          </div>
                          <p className="mt-2 text-sm text-muted">{delivery.recipient_email}</p>
                          {delivery.error_message ? (
                            <p className="mt-2 text-sm text-rose-700">{delivery.error_message}</p>
                          ) : null}
                        </div>
                      ))
                    ) : (
                      <p className="text-sm leading-7 text-muted">
                        No HireOS email has been sent yet. Use `Send with HireOS` to deliver a branded invite and keep the delivery log attached to this interview.
                      </p>
                    )}
                  </div>
                </div>
              </div>
            ) : null}
            {matchResult ? (
              <div className="rounded-[24px] border border-border bg-white/70 px-4 py-4">
                <div className="flex items-center justify-between">
                  <p className="font-semibold text-text">AI recommendation</p>
                  <Badge tone={matchResult.overall_score >= 75 ? "success" : "warning"}>
                    {formatScore(matchResult.overall_score)}%
                  </Badge>
                </div>
                <p className="mt-3 text-sm leading-7 text-muted">{matchResult.explanation}</p>
                <div className="mt-4 flex flex-wrap gap-2">
                  {matchResult.missing_required_skills.map((skill) => (
                    <Badge key={skill} tone="danger">
                      Missing: {skill}
                    </Badge>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        </Card>
      </div>

      {selectedJobId ? (
        <div className="mt-4 grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
          <Card>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">
                  Recruiter decision workspace
                </p>
                <h3 className="mt-3 font-display text-3xl font-semibold text-text">
                  {reviewWorkspace.data?.job_title || "Loading role context"}
                </h3>
                <p className="mt-2 max-w-2xl text-sm leading-7 text-muted">
                  {reviewWorkspace.data?.decision_support_note ||
                    "Keep the recruiter in control by documenting the final decision and any AI override."}
                </p>
              </div>
              {reviewWorkspace.data?.latest_decision ? (
                <Badge tone={statusTone(reviewWorkspace.data.latest_decision.decision)}>
                  Final call: {titleCase(reviewWorkspace.data.latest_decision.decision)}
                </Badge>
              ) : (
                <Badge tone="warning">Awaiting recruiter decision</Badge>
              )}
            </div>

            <div className="mt-6 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <div className="rounded-[22px] bg-white/75 px-4 py-4">
                <p className="text-xs uppercase tracking-[0.2em] text-muted-soft">Resume match</p>
                <p className="mt-2 font-display text-3xl font-semibold text-text">
                  {reviewWorkspace.data?.latest_match
                    ? `${formatScore(reviewWorkspace.data.latest_match.overall_score)}%`
                    : "Pending"}
                </p>
                <p className="mt-2 text-sm text-muted">
                  {reviewWorkspace.data?.latest_match
                    ? titleCase(reviewWorkspace.data.latest_match.match_recommendation)
                    : "Run the resume match to create AI evidence."}
                </p>
              </div>
              <div className="rounded-[22px] bg-white/75 px-4 py-4">
                <p className="text-xs uppercase tracking-[0.2em] text-muted-soft">Interview status</p>
                <p className="mt-2 font-display text-3xl font-semibold text-text">
                  {reviewWorkspace.data?.latest_interview
                    ? titleCase(reviewWorkspace.data.latest_interview.status)
                    : "Not invited"}
                </p>
                <p className="mt-2 text-sm text-muted">
                  {reviewWorkspace.data?.latest_interview
                    ? `${titleCase(reviewWorkspace.data.latest_interview.mode)} mode`
                    : "Create an invite to unlock decision logging."}
                </p>
              </div>
              <div className="rounded-[22px] bg-white/75 px-4 py-4">
                <p className="text-xs uppercase tracking-[0.2em] text-muted-soft">Human review</p>
                <p className="mt-2 font-display text-3xl font-semibold text-text">
                  {reviewWorkspace.data?.latest_report?.human_review_required ||
                  reviewWorkspace.data?.latest_match?.human_review_required
                    ? "Required"
                    : "Ready"}
                </p>
                <p className="mt-2 text-sm text-muted">
                  {reviewWorkspace.data?.latest_report?.recommended_next_step ||
                    "AI evidence should still be reviewed by a recruiter before moving the candidate."}
                </p>
              </div>
              <div className="rounded-[22px] bg-white/75 px-4 py-4">
                <p className="text-xs uppercase tracking-[0.2em] text-muted-soft">Latest override</p>
                <p className="mt-2 font-display text-3xl font-semibold text-text">
                  {reviewWorkspace.data?.latest_decision?.override_ai_recommendation ? "Yes" : "No"}
                </p>
                <p className="mt-2 text-sm text-muted">
                  {reviewWorkspace.data?.latest_decision
                    ? `Logged by ${reviewWorkspace.data.latest_decision.recruiter_name}`
                    : "No recruiter override recorded yet."}
                </p>
              </div>
            </div>

            <div className="mt-6 grid gap-4 lg:grid-cols-[1fr_0.9fr]">
              <div className="rounded-[24px] border border-border bg-white/70 px-4 py-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="font-semibold text-text">Decision capture</p>
                  {reviewWorkspace.data?.latest_match ? (
                    <Badge tone={reviewWorkspace.data.latest_match.human_review_required ? "warning" : "success"}>
                      AI says {titleCase(reviewWorkspace.data.latest_match.match_recommendation)}
                    </Badge>
                  ) : null}
                </div>
                {!reviewWorkspace.data?.can_record_decision ? (
                  <p className="mt-3 text-sm leading-7 text-muted">
                    Invite the candidate to an interview first so HireOS can attach the recruiter decision to a specific review workflow.
                  </p>
                ) : (
                  <>
                    <label className="mt-4 block">
                      <span className="text-sm font-medium text-muted">Final recruiter decision</span>
                      <select
                        className="mt-2 w-full rounded-2xl border border-border bg-white/80 px-4 py-3 outline-none"
                        value={decision}
                        onChange={(event) => setDecision(event.target.value)}
                      >
                        {decisionOptions.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="mt-4 block">
                      <span className="text-sm font-medium text-muted">Recruiter notes</span>
                      <textarea
                        className="mt-2 min-h-[130px] w-full rounded-2xl border border-border bg-white/80 px-4 py-3 outline-none"
                        placeholder="Capture why you are advancing, holding, or rejecting this candidate."
                        value={decisionNotes}
                        onChange={(event) => setDecisionNotes(event.target.value)}
                      />
                    </label>
                    <label className="mt-4 flex items-start gap-3 rounded-[20px] border border-border bg-surface-elevated px-4 py-3 text-sm text-muted">
                      <input
                        type="checkbox"
                        className="mt-1 h-4 w-4"
                        checked={overrideRecommendation}
                        onChange={(event) => setOverrideRecommendation(event.target.checked)}
                      />
                      <span>
                        I am overriding the AI recommendation and want the audit trail to explicitly capture that this was a human judgment call.
                      </span>
                    </label>
                    <div className="mt-4 flex flex-wrap gap-3">
                      <button
                        type="button"
                        disabled={reviewDecisionDisabled}
                        onClick={() => recruiterDecisionMutation.mutate()}
                        className="rounded-full bg-brand px-5 py-3 text-sm font-semibold text-white disabled:opacity-60"
                      >
                        Record recruiter decision
                      </button>
                      {reviewWorkspace.data?.latest_report ? (
                        <a
                          href={`/reports/${reviewWorkspace.data.latest_report.id}`}
                          className="rounded-full border border-border bg-white/70 px-5 py-3 text-sm font-semibold text-text"
                        >
                          Open report
                        </a>
                      ) : null}
                    </div>
                  </>
                )}
              </div>

              <div className="rounded-[24px] border border-border bg-white/70 px-4 py-4">
                <p className="font-semibold text-text">Decision history</p>
                <div className="mt-4 space-y-3">
                  {reviewWorkspace.data?.decision_history?.length ? (
                    reviewWorkspace.data.decision_history.map((entry) => (
                      <div
                        key={entry.id}
                        className="rounded-[20px] border border-border bg-surface-elevated px-4 py-4"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <Badge tone={statusTone(entry.decision)}>{titleCase(entry.decision)}</Badge>
                          <p className="text-xs uppercase tracking-[0.18em] text-muted-soft">
                            {new Date(entry.created_at).toLocaleString()}
                          </p>
                        </div>
                        <p className="mt-3 text-sm font-medium text-text">{entry.recruiter_name}</p>
                        <p className="mt-2 text-sm leading-7 text-muted">
                          {entry.notes || "No recruiter note added for this decision."}
                        </p>
                        {entry.override_ai_recommendation ? (
                          <p className="mt-3 text-xs font-semibold uppercase tracking-[0.18em] text-brand">
                            AI override captured
                          </p>
                        ) : null}
                      </div>
                    ))
                  ) : (
                    <p className="text-sm leading-7 text-muted">
                      No recruiter decision has been recorded yet. Once you log one, it will appear here with notes and override context.
                    </p>
                  )}
                </div>
              </div>
            </div>

            <div className="mt-4 rounded-[24px] border border-border bg-white/70 px-4 py-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="font-semibold text-text">ATS export</p>
                  <p className="mt-2 text-sm leading-7 text-muted">
                    Push recruiter-approved candidate movement into an external ATS webhook without blocking the recruiter if the downstream system is temporarily unavailable.
                  </p>
                </div>
                <Badge tone={atsExports.data?.[0]?.status === "delivered" ? "success" : atsExports.data?.[0]?.status === "failed" ? "danger" : "neutral"}>
                  {atsExports.data?.length ? titleCase(atsExports.data[0].status) : "Not exported"}
                </Badge>
              </div>
              <div className="mt-4 flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={() => exportToATSMutation.mutate()}
                  disabled={!reviewWorkspace.data?.latest_decision || !activeInterviewId || exportToATSMutation.isPending}
                  className="rounded-full bg-brand px-5 py-3 text-sm font-semibold text-white disabled:opacity-60"
                >
                  {exportToATSMutation.isPending
                    ? "Exporting..."
                    : atsExports.data?.length
                      ? "Resend to ATS"
                      : "Send to ATS"}
                </button>
                <p className="self-center text-sm text-muted">
                  Automatic export runs for configured shortlist stages. This action lets recruiters retry a failed handoff manually.
                </p>
              </div>
              <div className="mt-4 space-y-3">
                {atsExports.data?.length ? (
                  atsExports.data.map((delivery) => (
                    <div key={delivery.id} className="rounded-[20px] border border-border bg-surface-elevated px-4 py-4">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <Badge tone={delivery.status === "delivered" ? "success" : delivery.status === "failed" ? "danger" : "neutral"}>
                          {titleCase(delivery.status)}
                        </Badge>
                        <p className="text-xs uppercase tracking-[0.18em] text-muted-soft">
                          {new Date(delivery.created_at).toLocaleString()}
                        </p>
                      </div>
                      <p className="mt-3 text-sm font-medium text-text">
                        {titleCase(delivery.event_name.replace("candidate.", "").replaceAll("_", " "))} via {delivery.provider}
                      </p>
                      <p className="mt-2 text-sm leading-7 text-muted break-all">
                        {delivery.target_url}
                      </p>
                      <p className="mt-2 text-sm text-muted">
                        HTTP status: {delivery.response_status_code || "n/a"}
                      </p>
                      {delivery.error_message ? (
                        <p className="mt-2 text-sm leading-7 text-danger">
                          {delivery.error_message}
                        </p>
                      ) : null}
                    </div>
                  ))
                ) : (
                  <p className="text-sm leading-7 text-muted">
                    No ATS export has been recorded yet. Save webhook settings first, then record a shortlist-stage decision or trigger a manual export here.
                  </p>
                )}
              </div>
            </div>
          </Card>

          <Card>
            <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">
              Audit timeline
            </p>
            <p className="mt-3 text-sm leading-7 text-muted">
              Every meaningful hiring action stays visible here so recruiters, hiring managers, and admins can understand what happened before a final decision.
            </p>
            <div className="mt-6 space-y-3">
              {reviewWorkspace.data?.audit_timeline?.length ? (
                reviewWorkspace.data.audit_timeline.map((entry, index) => (
                  <div
                    key={`${entry.source}-${entry.action}-${index}`}
                    className="relative rounded-[22px] border border-border bg-white/70 px-4 py-4"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <Badge tone={entry.source === "audit" ? "brand" : entry.source === "report" ? "warning" : "neutral"}>
                        {titleCase(entry.source)}
                      </Badge>
                      <p className="text-xs uppercase tracking-[0.18em] text-muted-soft">
                        {new Date(entry.timestamp).toLocaleString()}
                      </p>
                    </div>
                    <p className="mt-3 text-sm font-semibold text-text">{entry.summary}</p>
                    <p className="mt-2 text-xs uppercase tracking-[0.18em] text-muted-soft">
                      {entry.actor_label} · {titleCase(entry.action)}
                    </p>
                  </div>
                ))
              ) : (
                <p className="text-sm leading-7 text-muted">
                  Select a job, then run a match or create an interview to populate the candidate audit timeline.
                </p>
              )}
            </div>
          </Card>
        </div>
      ) : null}
    </AppShell>
  );
}
