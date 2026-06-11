"use client";

import Link from "next/link";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { useAuth } from "@/hooks/use-auth";
import { api } from "@/lib/api";
import type {
  CalibrationQueue,
  CalibrationQueueEntry,
  CalibrationReminderPreview,
  CalibrationReminderPreviewResponse,
  CalibrationReminderRunResponse,
} from "@/lib/types";
import { formatScore, titleCase } from "@/lib/utils";

function toneForPriority(priority?: string) {
  if (priority === "critical") {
    return "danger" as const;
  }
  if (priority === "high") {
    return "warning" as const;
  }
  if (priority === "medium") {
    return "brand" as const;
  }
  return "neutral" as const;
}

function toneForConsensus(status?: string) {
  if (status === "conflicted") {
    return "danger" as const;
  }
  if (status === "mixed") {
    return "warning" as const;
  }
  if (status === "pending") {
    return "brand" as const;
  }
  return "success" as const;
}

function toneForSla(status?: string) {
  if (status === "overdue") {
    return "danger" as const;
  }
  if (status === "due_today") {
    return "warning" as const;
  }
  if (status === "resolved") {
    return "success" as const;
  }
  return "brand" as const;
}

function toDateTimeLocal(value?: string | null) {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

type DraftState = {
  status: string;
  due_at: string;
  resolution_summary: string;
  resolution_notes: string;
};

export default function CalibrationPage() {
  const auth = useAuth();
  const [drafts, setDrafts] = useState<Record<string, DraftState>>({});
  const currentRole = auth.user?.memberships?.[0]?.role || "recruiter";
  const calibrationQueue = useQuery<CalibrationQueue>({
    queryKey: ["calibration-queue", auth.token],
    queryFn: () => api.getCalibrationQueue(auth.token as string),
    enabled: Boolean(auth.token),
  });
  const calibrationReminders = useQuery<CalibrationReminderPreviewResponse>({
    queryKey: ["calibration-reminders", auth.token],
    queryFn: () => api.previewCalibrationReminders(auth.token as string),
    enabled: Boolean(auth.token),
  });
  const updateCaseMutation = useMutation({
    mutationFn: ({
      candidateId,
      jobId,
      payload,
    }: {
      candidateId: string;
      jobId: string;
      payload: Record<string, unknown>;
    }) => api.updateCalibrationCase(auth.token as string, candidateId, jobId, payload),
    onSuccess: async () => {
      await calibrationQueue.refetch();
      await calibrationReminders.refetch();
    },
  });
  const runReminderMutation = useMutation<CalibrationReminderRunResponse>({
    mutationFn: () => api.runCalibrationReminders(auth.token as string),
    onSuccess: async () => {
      await calibrationReminders.refetch();
    },
  });

  function draftKey(entry: CalibrationQueueEntry) {
    return `${entry.candidate_id}:${entry.job_id}`;
  }

  function getDraft(entry: CalibrationQueueEntry): DraftState {
    const key = draftKey(entry);
    return (
      drafts[key] || {
        status: entry.calibration_case?.status || "open",
        due_at: toDateTimeLocal(entry.calibration_case?.due_at),
        resolution_summary: entry.calibration_case?.resolution_summary || "",
        resolution_notes: entry.calibration_case?.resolution_notes || "",
      }
    );
  }

  function updateDraft(entry: CalibrationQueueEntry, patch: Partial<DraftState>) {
    const key = draftKey(entry);
    setDrafts((current) => ({
      ...current,
      [key]: {
        ...getDraft(entry),
        ...patch,
      },
    }));
  }

  function saveCase(entry: CalibrationQueueEntry, overrides?: Record<string, unknown>) {
    const draft = getDraft(entry);
    updateCaseMutation.mutate({
      candidateId: entry.candidate_id,
      jobId: entry.job_id,
      payload: {
        status: draft.status,
        due_at: draft.due_at ? new Date(draft.due_at).toISOString() : null,
        resolution_summary: draft.resolution_summary || null,
        resolution_notes: draft.resolution_notes || null,
        ...overrides,
      },
    });
  }

  return (
    <AppShell
      title="Calibration Queue"
      subtitle="Work the candidates whose AI, hiring manager, and recruiter signals are not yet aligned enough for a confident final move."
      actions={
        <Link href="/dashboard" className="rounded-full border border-border bg-white/70 px-5 py-3 text-sm font-semibold text-text">
          Back to overview
        </Link>
      }
    >
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card>
          <p className="text-xs uppercase tracking-[0.2em] text-muted-soft">Queued items</p>
          <p className="mt-3 font-display text-5xl font-semibold text-text">
            {calibrationQueue.data?.total_items || 0}
          </p>
          <p className="mt-2 text-sm leading-7 text-muted">Candidate-job reviews currently waiting for recruiter calibration.</p>
        </Card>
        <Card>
          <p className="text-xs uppercase tracking-[0.2em] text-muted-soft">Conflicted</p>
          <p className="mt-3 font-display text-5xl font-semibold text-text">
            {calibrationQueue.data?.conflicted_count || 0}
          </p>
          <p className="mt-2 text-sm leading-7 text-muted">Direct disagreement between advance and reject signals.</p>
        </Card>
        <Card>
          <p className="text-xs uppercase tracking-[0.2em] text-muted-soft">Mixed</p>
          <p className="mt-3 font-display text-5xl font-semibold text-text">
            {calibrationQueue.data?.mixed_count || 0}
          </p>
          <p className="mt-2 text-sm leading-7 text-muted">Partially aligned signals that still need recruiter synthesis.</p>
        </Card>
        <Card>
          <p className="text-xs uppercase tracking-[0.2em] text-muted-soft">Pending</p>
          <p className="mt-3 font-display text-5xl font-semibold text-text">
            {calibrationQueue.data?.pending_count || 0}
          </p>
          <p className="mt-2 text-sm leading-7 text-muted">Reviews that need more human evidence before a final call.</p>
        </Card>
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-[0.95fr_1.05fr]">
        <Card>
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">How to use it</p>
          <h3 className="mt-2 font-display text-2xl font-semibold text-text">Recruiter calibration workflow</h3>
          <div className="mt-5 space-y-3 text-sm leading-7 text-muted">
            <p>Start with `critical` conflicts where one signal advances the candidate while another rejects them.</p>
            <p>Use `high` items to review explicit recruiter overrides and manager disagreement before downstream ATS export.</p>
            <p>Use `medium` items to gather missing human judgment when AI still marks the profile for review.</p>
          </div>
        </Card>

        <Card>
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">Queue health</p>
              <h3 className="mt-2 font-display text-2xl font-semibold text-text">Escalation posture</h3>
            </div>
            <Badge tone={calibrationQueue.data?.conflicted_count ? "danger" : "success"}>
              {calibrationQueue.data?.conflicted_count ? "Action required" : "Stable"}
            </Badge>
          </div>
          <div className="mt-5 space-y-3">
            <div className="rounded-[20px] bg-danger-soft px-4 py-4">
              <p className="font-semibold text-text">
                {calibrationQueue.data?.entries.filter((entry) => entry.requires_escalation).length || 0} items need escalation
              </p>
              <p className="mt-2 text-sm leading-6 text-muted">
                These candidates should be discussed before any shortlist, reject, or export action.
              </p>
            </div>
            <div className="rounded-[20px] bg-brand-soft/70 px-4 py-4">
              <p className="font-semibold text-text">
                Average queue agreement{" "}
                {calibrationQueue.data?.entries.length
                  ? `${formatScore(
                      calibrationQueue.data.entries.reduce((total, entry) => total + entry.agreement_score, 0) /
                        calibrationQueue.data.entries.length,
                    )}%`
                  : "0%"}
              </p>
              <p className="mt-2 text-sm leading-6 text-muted">
                Lower agreement means the recruiter should spend more time reconciling evidence before closing the loop.
              </p>
            </div>
          </div>
        </Card>
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-[0.95fr_1.05fr]">
        <Card>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">Reminder automation</p>
              <h3 className="mt-2 font-display text-2xl font-semibold text-text">Overdue case nudges</h3>
              <p className="mt-3 text-sm leading-7 text-muted">
                Notify the assignee or fallback recruiter when a calibration case is overdue or due today and still unresolved.
              </p>
            </div>
            {["admin", "recruiter"].includes(currentRole) ? (
              <button
                type="button"
                disabled={runReminderMutation.isPending || !calibrationReminders.data?.cases?.length}
                onClick={() => runReminderMutation.mutate()}
                className="rounded-full bg-brand px-5 py-3 text-sm font-semibold text-white disabled:opacity-60"
              >
                {runReminderMutation.isPending ? "Sending reminders..." : "Run reminders now"}
              </button>
            ) : null}
          </div>
          <div className="mt-5 grid gap-3 md:grid-cols-3">
            <div className="rounded-[20px] bg-white/70 px-4 py-4">
              <p className="text-xs uppercase tracking-[0.18em] text-muted-soft">Queued</p>
              <p className="mt-2 font-display text-3xl font-semibold text-text">
                {calibrationReminders.data?.cases?.length || 0}
              </p>
              <p className="mt-2 text-sm text-muted">Cases currently eligible for a reminder.</p>
            </div>
            <div className="rounded-[20px] bg-white/70 px-4 py-4">
              <p className="text-xs uppercase tracking-[0.18em] text-muted-soft">Overdue</p>
              <p className="mt-2 font-display text-3xl font-semibold text-text">
                {calibrationReminders.data?.overdue_count || 0}
              </p>
              <p className="mt-2 text-sm text-muted">Cases already beyond their SLA due date.</p>
            </div>
            <div className="rounded-[20px] bg-white/70 px-4 py-4">
              <p className="text-xs uppercase tracking-[0.18em] text-muted-soft">Due today</p>
              <p className="mt-2 font-display text-3xl font-semibold text-text">
                {calibrationReminders.data?.due_today_count || 0}
              </p>
              <p className="mt-2 text-sm text-muted">Cases that should be closed before the day ends.</p>
            </div>
          </div>
          {runReminderMutation.data ? (
            <div className="mt-4 rounded-[20px] bg-success-soft px-4 py-4">
              <p className="text-sm font-semibold text-text">Reminder run complete</p>
              <p className="mt-2 text-sm leading-7 text-muted">
                Sent: {runReminderMutation.data.sent_count} · Fallback outbox: {runReminderMutation.data.fallback_count} · Failed: {runReminderMutation.data.failed_count}
              </p>
            </div>
          ) : null}
          <p className="mt-4 text-xs leading-6 text-muted">{calibrationReminders.data?.policy_note}</p>
        </Card>

        <Card>
          <div className="flex items-center justify-between gap-3">
            <h3 className="font-display text-2xl font-semibold text-text">Cases due for reminder</h3>
            <Badge tone={calibrationReminders.data?.cases?.length ? "warning" : "success"}>
              {calibrationReminders.data?.cases?.length || 0} queued
            </Badge>
          </div>
          <div className="mt-5 space-y-3">
            {calibrationReminders.data?.cases?.length ? (
              calibrationReminders.data.cases.slice(0, 6).map((item: CalibrationReminderPreview) => (
                <div key={item.calibration_case_id} className="rounded-[20px] border border-border bg-white/70 px-4 py-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="font-semibold text-text">{item.candidate_name}</p>
                      <p className="mt-1 text-sm text-muted">
                        {item.job_title} · {item.recipient_name} · {item.recipient_email}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Badge tone={toneForPriority(item.priority)}>{titleCase(item.priority)}</Badge>
                      <Badge tone={toneForSla(item.sla_status)}>{titleCase(item.sla_status)}</Badge>
                    </div>
                  </div>
                  <p className="mt-3 text-sm leading-7 text-muted">{item.reminder_reason}</p>
                  <p className="mt-3 text-xs uppercase tracking-[0.16em] text-muted-soft">
                    Due {new Date(item.due_at).toLocaleString()} · prior attempts {item.reminder_attempts}
                  </p>
                </div>
              ))
            ) : (
              <div className="rounded-[20px] bg-success-soft px-4 py-4">
                <p className="text-sm font-semibold text-text">No calibration reminders are due right now.</p>
                <p className="mt-2 text-sm leading-6 text-muted">
                  Once a case becomes overdue or due today and remains unresolved, HireOS will queue it here for notification.
                </p>
              </div>
            )}
          </div>
        </Card>
      </div>

      <div className="mt-6 space-y-4">
        {calibrationQueue.data?.entries.length ? (
          calibrationQueue.data.entries.map((entry) => (
            <Card key={`${entry.candidate_id}-${entry.job_id}`}>
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="flex flex-wrap items-center gap-3">
                    <h3 className="font-display text-2xl font-semibold text-text">{entry.candidate_name}</h3>
                    <Badge tone={toneForPriority(entry.priority)}>{titleCase(entry.priority)}</Badge>
                    <Badge tone={toneForConsensus(entry.consensus_status)}>
                      {titleCase(entry.consensus_status)} consensus
                    </Badge>
                  </div>
                  <p className="mt-2 text-sm text-muted">
                    {entry.job_title} · {entry.current_role || "Candidate"} · {entry.candidate_email}
                  </p>
                </div>
                <div className="flex flex-wrap gap-3">
                  <Link
                    href={`/candidates/${entry.candidate_id}?job=${entry.job_id}`}
                    className="rounded-full bg-brand px-5 py-3 text-sm font-semibold text-white"
                  >
                    Open calibration workspace
                  </Link>
                  {["admin", "recruiter"].includes(currentRole) ? (
                    <button
                      type="button"
                      onClick={() => saveCase(entry, { assign_to_me: true })}
                      className="rounded-full border border-border bg-white/80 px-5 py-3 text-sm font-semibold text-text"
                    >
                      Assign to me
                    </button>
                  ) : null}
                </div>
              </div>

              <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
                <div className="rounded-[20px] bg-white/70 px-4 py-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-muted-soft">Agreement</p>
                  <p className="mt-2 font-display text-3xl font-semibold text-text">{formatScore(entry.agreement_score)}%</p>
                </div>
                <div className="rounded-[20px] bg-white/70 px-4 py-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-muted-soft">AI</p>
                  <p className="mt-2 font-semibold text-text">{titleCase(entry.ai_recommendation || "pending")}</p>
                </div>
                <div className="rounded-[20px] bg-white/70 px-4 py-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-muted-soft">Hiring manager</p>
                  <p className="mt-2 font-semibold text-text">{titleCase(entry.hiring_manager_recommendation || "pending")}</p>
                </div>
                <div className="rounded-[20px] bg-white/70 px-4 py-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-muted-soft">Recruiter</p>
                  <p className="mt-2 font-semibold text-text">{titleCase(entry.recruiter_decision || "pending")}</p>
                </div>
                <div className="rounded-[20px] bg-white/70 px-4 py-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-muted-soft">Last signal</p>
                  <p className="mt-2 font-semibold text-text">{new Date(entry.latest_signal_at).toLocaleString()}</p>
                </div>
              </div>

              <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <div className="rounded-[20px] bg-white/70 px-4 py-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-muted-soft">Case owner</p>
                  <p className="mt-2 font-semibold text-text">
                    {entry.calibration_case?.assigned_to_name || "Unassigned"}
                  </p>
                </div>
                <div className="rounded-[20px] bg-white/70 px-4 py-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-muted-soft">Case status</p>
                  <div className="mt-2">
                    <Badge tone={toneForPriority(entry.priority)}>
                      {titleCase(entry.calibration_case?.status || "open")}
                    </Badge>
                  </div>
                </div>
                <div className="rounded-[20px] bg-white/70 px-4 py-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-muted-soft">SLA</p>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <Badge tone={toneForSla(entry.calibration_case?.sla_status)}>
                      {titleCase(entry.calibration_case?.sla_status || "on_track")}
                    </Badge>
                    <p className="text-sm font-semibold text-text">
                      {entry.calibration_case?.due_at ? new Date(entry.calibration_case.due_at).toLocaleString() : "Not set"}
                    </p>
                  </div>
                </div>
                <div className="rounded-[20px] bg-white/70 px-4 py-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-muted-soft">Resolution</p>
                  <p className="mt-2 text-sm font-semibold text-text">
                    {entry.calibration_case?.resolution_summary || "Pending"}
                  </p>
                </div>
              </div>

              <div className="mt-5 grid gap-4 lg:grid-cols-[1fr_0.9fr]">
                <div className="rounded-[22px] border border-border bg-surface-elevated px-4 py-4">
                  <p className="font-semibold text-text">Conflict reasons</p>
                  <div className="mt-4 space-y-3">
                    {entry.conflict_reasons.length ? (
                      entry.conflict_reasons.map((reason) => (
                        <div key={reason} className="rounded-[18px] bg-white/80 px-4 py-3 text-sm leading-7 text-muted">
                          {reason}
                        </div>
                      ))
                    ) : (
                      <div className="rounded-[18px] bg-white/80 px-4 py-3 text-sm leading-7 text-muted">
                        No explicit conflict reason was captured yet. Review the evidence and decide whether another human signal is needed.
                      </div>
                    )}
                  </div>
                </div>
                <div className="rounded-[22px] border border-border bg-surface-elevated px-4 py-4">
                  <p className="font-semibold text-text">Recommended next step</p>
                  <p className="mt-4 text-sm leading-7 text-muted">
                    {entry.recommended_next_step || "No interview report recommendation has been generated yet."}
                  </p>
                  <p className="mt-4 text-xs uppercase tracking-[0.18em] text-muted-soft">
                    Candidate status: {titleCase(entry.candidate_status)}
                  </p>
                </div>
              </div>

              <div className="mt-5 rounded-[22px] border border-border bg-surface-elevated px-4 py-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="font-semibold text-text">Case management</p>
                    <p className="mt-2 text-sm leading-7 text-muted">
                      Assign ownership, set an SLA, and capture how the recruiter resolved the disagreement.
                    </p>
                  </div>
                  {updateCaseMutation.isPending ? <Badge tone="brand">Saving...</Badge> : null}
                </div>
                {["admin", "recruiter"].includes(currentRole) ? (
                  <>
                    <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                      <label className="block">
                        <span className="text-sm font-medium text-muted">Case status</span>
                        <select
                          className="mt-2 w-full rounded-2xl border border-border bg-white/80 px-4 py-3 outline-none"
                          value={getDraft(entry).status}
                          onChange={(event) => updateDraft(entry, { status: event.target.value })}
                        >
                          <option value="open">Open</option>
                          <option value="in_progress">In progress</option>
                          <option value="reopened">Reopened</option>
                          <option value="resolved">Resolved</option>
                        </select>
                      </label>
                      <label className="block md:col-span-1 xl:col-span-2">
                        <span className="text-sm font-medium text-muted">Due by</span>
                        <input
                          type="datetime-local"
                          className="mt-2 w-full rounded-2xl border border-border bg-white/80 px-4 py-3 outline-none"
                          value={getDraft(entry).due_at}
                          onChange={(event) => updateDraft(entry, { due_at: event.target.value })}
                        />
                      </label>
                      <label className="block">
                        <span className="text-sm font-medium text-muted">Resolution summary</span>
                        <input
                          className="mt-2 w-full rounded-2xl border border-border bg-white/80 px-4 py-3 outline-none"
                          value={getDraft(entry).resolution_summary}
                          onChange={(event) => updateDraft(entry, { resolution_summary: event.target.value })}
                          placeholder="Example: Aligned on moving to system design"
                        />
                      </label>
                    </div>
                    <label className="mt-4 block">
                      <span className="text-sm font-medium text-muted">Resolution notes</span>
                      <textarea
                        className="mt-2 min-h-[120px] w-full rounded-2xl border border-border bg-white/80 px-4 py-3 outline-none"
                        value={getDraft(entry).resolution_notes}
                        onChange={(event) => updateDraft(entry, { resolution_notes: event.target.value })}
                        placeholder="Capture the discussion outcome, compensation constraints, evidence reviewed, and the next recruiter action."
                      />
                    </label>
                    <div className="mt-4 flex flex-wrap gap-3">
                      <button
                        type="button"
                        onClick={() => saveCase(entry, { status: "in_progress", assign_to_me: true })}
                        className="rounded-full border border-border bg-white/80 px-5 py-3 text-sm font-semibold text-text"
                      >
                        Start working
                      </button>
                      <button
                        type="button"
                        onClick={() => saveCase(entry, { status: "resolved" })}
                        className="rounded-full bg-brand px-5 py-3 text-sm font-semibold text-white"
                      >
                        Resolve case
                      </button>
                      <button
                        type="button"
                        onClick={() => saveCase(entry)}
                        className="rounded-full border border-border bg-white/80 px-5 py-3 text-sm font-semibold text-text"
                      >
                        Save updates
                      </button>
                    </div>
                  </>
                ) : (
                  <div className="mt-4 rounded-[18px] bg-white/80 px-4 py-3 text-sm leading-7 text-muted">
                    Recruiters and admins can update case ownership, SLA, and resolution notes. Hiring managers can still review the queue in read-only mode.
                  </div>
                )}
              </div>
            </Card>
          ))
        ) : (
          <Card>
            <p className="font-display text-2xl font-semibold text-text">Calibration queue is clear</p>
            <p className="mt-3 text-sm leading-7 text-muted">
              No candidate-job pairs currently require recruiter calibration. New conflicts, mixed signals, or pending review states will show up here automatically.
            </p>
          </Card>
        )}
      </div>
    </AppShell>
  );
}
