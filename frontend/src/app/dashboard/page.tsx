"use client";

import Link from "next/link";
import { useMutation, useQuery } from "@tanstack/react-query";

import { AppShell } from "@/components/layout/app-shell";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { MetricCard } from "@/components/ui/metric-card";
import { useAuth } from "@/hooks/use-auth";
import { api } from "@/lib/api";
import { formatScore, titleCase } from "@/lib/utils";

export default function DashboardPage() {
  const auth = useAuth();
  const overview = useQuery({
    queryKey: ["overview", auth.token],
    queryFn: () => api.getAnalyticsOverview(auth.token as string),
    enabled: Boolean(auth.token),
  });
  const jobs = useQuery({
    queryKey: ["jobs", auth.token],
    queryFn: () => api.getJobs(auth.token as string),
    enabled: Boolean(auth.token),
  });
  const candidates = useQuery({
    queryKey: ["candidates", auth.token],
    queryFn: () => api.getCandidates(auth.token as string),
    enabled: Boolean(auth.token),
  });
  const reminders = useQuery({
    queryKey: ["interview-reminders", auth.token],
    queryFn: () => api.previewInterviewReminders(auth.token as string),
    enabled: Boolean(auth.token),
  });
  const runReminders = useMutation({
    mutationFn: () => api.runInterviewReminders(auth.token as string),
    onSuccess: async () => {
      await reminders.refetch();
    },
  });

  return (
    <AppShell
      title="Recruiter Overview"
      subtitle="Track the health of your hiring funnel, AI output quality, and where recruiter judgment still needs to step in."
      actions={
        <>
          <Link href="/jobs/new" className="rounded-full bg-brand px-5 py-3 text-sm font-semibold text-white">
            Create job
          </Link>
          <Link href="/candidates" className="rounded-full border border-border bg-white/70 px-5 py-3 text-sm font-semibold text-text">
            Upload resume
          </Link>
        </>
      }
    >
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Candidates"
          value={String(overview.data?.total_candidates || 0)}
          hint="Profiles currently in the recruiter-owned pipeline."
        />
        <MetricCard
          label="Active jobs"
          value={String(overview.data?.active_jobs || 0)}
          hint="Open reqs ready for AI-assisted screening."
        />
        <MetricCard
          label="Average match score"
          value={`${formatScore(overview.data?.average_match_score)}%`}
          hint="Resume versus JD alignment across active candidates."
        />
        <MetricCard
          label="Average interview score"
          value={`${formatScore(overview.data?.average_interview_score)}%`}
          hint="Semantic answer performance across completed interviews."
        />
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
        <Card>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">
                Pipeline
              </p>
              <h3 className="mt-2 font-display text-2xl font-semibold text-text">
                Candidate stages
              </h3>
            </div>
            <Badge tone="warning">
              {overview.data?.candidates_requiring_human_review || 0} require human review
            </Badge>
          </div>
          <div className="mt-6 space-y-3">
            {Object.entries(overview.data?.pipeline_by_stage || {}).map(([stage, count]) => (
              <div key={stage} className="rounded-[20px] border border-border bg-white/65 px-4 py-3">
                <div className="flex items-center justify-between">
                  <p className="font-medium text-text">{titleCase(stage)}</p>
                  <p className="text-sm text-muted">{count}</p>
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">
            Review queue
          </p>
          <h3 className="mt-2 font-display text-2xl font-semibold text-text">
            Live recruiter action areas
          </h3>
          <div className="mt-6 space-y-4">
            <div className="rounded-[24px] bg-danger-soft px-4 py-4">
              <p className="text-sm font-semibold text-text">
                {overview.data?.candidates_requiring_human_review || 0} candidates need manual review
              </p>
              <p className="mt-2 text-sm leading-6 text-muted">
                These candidates have low-confidence AI outputs, missing must-have skills, or incomplete interview answers.
              </p>
            </div>
            <div className="rounded-[24px] bg-success-soft px-4 py-4">
              <p className="text-sm font-semibold text-text">
                {overview.data?.candidates_shortlisted || 0} already shortlisted
              </p>
              <p className="mt-2 text-sm leading-6 text-muted">
                Recruiter overrides and approvals stay visible to hiring managers and admins for auditability.
              </p>
            </div>
          </div>
        </Card>
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
        <Card>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">
                Reminder automation
              </p>
              <h3 className="mt-2 font-display text-2xl font-semibold text-text">
                Recover no-shows and unfinished interviews
              </h3>
              <p className="mt-3 text-sm leading-7 text-muted">
                HireOS can nudge candidates who never started their interview or dropped off mid-flow, while respecting cooldowns and attempt caps.
              </p>
            </div>
            <button
              type="button"
              disabled={runReminders.isPending || !reminders.data?.candidates?.length}
              onClick={() => runReminders.mutate()}
              className="rounded-full bg-brand px-5 py-3 text-sm font-semibold text-white disabled:opacity-60"
            >
              {runReminders.isPending ? "Sending reminders..." : "Run reminders now"}
            </button>
          </div>
          <div className="mt-6 grid gap-3 md:grid-cols-3">
            <div className="rounded-[20px] bg-white/70 px-4 py-4">
              <p className="text-xs uppercase tracking-[0.18em] text-muted-soft">Due now</p>
              <p className="mt-2 font-display text-3xl font-semibold text-text">
                {reminders.data?.candidates.length || 0}
              </p>
              <p className="mt-2 text-sm text-muted">Candidates currently eligible for a reminder.</p>
            </div>
            <div className="rounded-[20px] bg-white/70 px-4 py-4">
              <p className="text-xs uppercase tracking-[0.18em] text-muted-soft">No-show nudges</p>
              <p className="mt-2 font-display text-3xl font-semibold text-text">
                {reminders.data?.invited_no_show_count || 0}
              </p>
              <p className="mt-2 text-sm text-muted">Invited candidates who never started.</p>
            </div>
            <div className="rounded-[20px] bg-white/70 px-4 py-4">
              <p className="text-xs uppercase tracking-[0.18em] text-muted-soft">Completion nudges</p>
              <p className="mt-2 font-display text-3xl font-semibold text-text">
                {reminders.data?.incomplete_count || 0}
              </p>
              <p className="mt-2 text-sm text-muted">Started interviews that were left unfinished.</p>
            </div>
          </div>
          {runReminders.data ? (
            <div className="mt-4 rounded-[24px] bg-success-soft px-4 py-4">
              <p className="text-sm font-semibold text-text">
                Reminder run complete
              </p>
              <p className="mt-2 text-sm leading-7 text-muted">
                Sent: {runReminders.data.sent_count} · Fallback outbox: {runReminders.data.fallback_count} · Failed: {runReminders.data.failed_count}
              </p>
            </div>
          ) : null}
          {runReminders.error ? (
            <p className="mt-4 text-sm text-rose-700">{runReminders.error.message}</p>
          ) : null}
          <p className="mt-4 text-xs leading-6 text-muted">
            {reminders.data?.policy_note}
          </p>
        </Card>

        <Card>
          <div className="flex items-center justify-between">
            <h3 className="font-display text-2xl font-semibold text-text">Candidates due for follow-up</h3>
            <Badge tone={reminders.data?.candidates.length ? "warning" : "success"}>
              {reminders.data?.candidates.length || 0} queued
            </Badge>
          </div>
          <div className="mt-5 space-y-3">
            {reminders.data?.candidates.length ? (
              reminders.data.candidates.slice(0, 6).map((item) => (
                <div
                  key={`${item.interview_id}-${item.reminder_type}`}
                  className="rounded-[24px] border border-border bg-white/70 px-4 py-4"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="font-semibold text-text">{item.candidate_name}</p>
                      <p className="mt-1 text-sm text-muted">
                        {item.job_title} · {item.candidate_email}
                      </p>
                    </div>
                    <Badge tone={item.reminder_type === "interview_no_show_reminder" ? "warning" : "brand"}>
                      {item.reminder_type === "interview_no_show_reminder" ? "No-show" : "Incomplete"}
                    </Badge>
                  </div>
                  <p className="mt-3 text-sm leading-7 text-muted">{item.reminder_reason}</p>
                  <p className="mt-3 text-xs uppercase tracking-[0.16em] text-muted-soft">
                    Last activity {new Date(item.last_activity_at).toLocaleString()} · prior attempts {item.reminder_attempts}
                  </p>
                </div>
              ))
            ) : (
              <div className="rounded-[24px] bg-success-soft px-4 py-4">
                <p className="text-sm font-semibold text-text">No reminders are due right now.</p>
                <p className="mt-2 text-sm leading-6 text-muted">
                  HireOS will keep the queue clear until invited candidates become overdue or partial interviews stall long enough to warrant a follow-up.
                </p>
              </div>
            )}
          </div>
        </Card>
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <Card>
          <div className="flex items-center justify-between">
            <h3 className="font-display text-2xl font-semibold text-text">Open jobs</h3>
            <Link href="/jobs" className="text-sm font-semibold text-brand">
              View all
            </Link>
          </div>
          <div className="mt-5 space-y-3">
            {jobs.data?.slice(0, 4).map((job) => (
              <Link
                key={job.id}
                href={`/jobs/${job.id}`}
                className="block rounded-[24px] border border-border bg-white/70 px-4 py-4"
              >
                <div className="flex items-center justify-between">
                  <p className="font-semibold text-text">{job.title}</p>
                  <Badge tone={job.status === "open" ? "success" : "neutral"}>
                    {titleCase(job.status)}
                  </Badge>
                </div>
                <p className="mt-2 text-sm text-muted">
                  {job.department || "General"} · {job.work_mode} · {job.location || "Flexible"}
                </p>
              </Link>
            ))}
          </div>
        </Card>
        <Card>
          <div className="flex items-center justify-between">
            <h3 className="font-display text-2xl font-semibold text-text">Recent candidates</h3>
            <Link href="/candidates" className="text-sm font-semibold text-brand">
              View all
            </Link>
          </div>
          <div className="mt-5 space-y-3">
            {candidates.data?.slice(0, 5).map((candidate) => (
              <Link
                key={candidate.id}
                href={`/candidates/${candidate.id}`}
                className="block rounded-[24px] border border-border bg-white/70 px-4 py-4"
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="font-semibold text-text">{candidate.name}</p>
                    <p className="mt-1 text-sm text-muted">
                      {candidate.current_role || "Candidate"} · {candidate.years_experience} yrs
                    </p>
                  </div>
                  <Badge tone={candidate.status?.includes("review") ? "warning" : "brand"}>
                    {titleCase(candidate.status)}
                  </Badge>
                </div>
              </Link>
            ))}
          </div>
        </Card>
      </div>
    </AppShell>
  );
}
