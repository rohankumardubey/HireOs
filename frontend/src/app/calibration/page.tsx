"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { AppShell } from "@/components/layout/app-shell";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { useAuth } from "@/hooks/use-auth";
import { api } from "@/lib/api";
import type { CalibrationQueue } from "@/lib/types";
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

export default function CalibrationPage() {
  const auth = useAuth();
  const calibrationQueue = useQuery<CalibrationQueue>({
    queryKey: ["calibration-queue", auth.token],
    queryFn: () => api.getCalibrationQueue(auth.token as string),
    enabled: Boolean(auth.token),
  });

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
