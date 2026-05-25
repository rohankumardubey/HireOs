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

  const matchMutation = useMutation({
    mutationFn: () => api.matchCandidate(auth.token as string, candidateId, selectedJobId),
    onSuccess: (result) => setMatchResult(result),
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
    onSuccess: (interview) => setInviteResult(interview),
  });

  const inviteDisabled =
    !selectedJobId ||
    inviteMutation.isPending ||
    (interviewMode === "video" &&
      meetingProvider === "zoom" &&
      !meetingJoinUrl.trim()) ||
    (interviewMode === "video" &&
      meetingProvider === "google_meet" &&
      !googleStatus.data?.connected &&
      !meetingJoinUrl.trim()) ||
    (interviewMode === "video" && scheduleType === "scheduled" && !scheduledAt);

  return (
    <AppShell
      title={candidate.data?.name || "Candidate detail"}
      subtitle="Inspect the parsed resume profile, run role matching, and generate an AI interview invitation with a shareable candidate link."
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
            <Badge tone={candidate.data?.status?.includes("review") ? "warning" : "brand"}>
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
                      ? "https://zoom.us/j/..."
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
                    : "Paste the real Zoom join link that the candidate should open. For scheduled interviews, add the meeting time above."}
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
                  {interviewMode === "video"
                    ? "Live video"
                    : interviewMode === "voice"
                      ? "Voice"
                      : "Text"}{" "}
                  interview created for{" "}
                  {inviteResult.share_links.candidate_email}.
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
                    {interviewMode === "video"
                      ? "Open candidate join link"
                      : "Open candidate interview"}
                  </a>
                </div>
                <div className="mt-4 rounded-[20px] bg-white/80 px-4 py-4">
                  <p className="text-xs uppercase tracking-[0.2em] text-muted-soft">
                    {interviewMode === "video"
                      ? "Candidate video join link"
                      : "Candidate interview link"}
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
    </AppShell>
  );
}
