"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import {
  AlertTriangle,
  CheckCircle2,
  FileSearch,
  Scale,
  ShieldCheck,
  UserCheck,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { AppShell } from "@/components/layout/app-shell";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { MetricCard } from "@/components/ui/metric-card";
import { useAuth } from "@/hooks/use-auth";
import { api } from "@/lib/api";
import { formatScore, titleCase } from "@/lib/utils";

type BadgeTone = "success" | "warning" | "danger" | "brand" | "neutral";

const chartColors = ["#135d66", "#ec8f5e", "#f4b55f", "#7bb284", "#56667c"];

function controlTone(status: string): BadgeTone {
  if (status === "active") {
    return "success";
  }
  if (status === "attention") {
    return "warning";
  }
  return "brand";
}

function eventLabel(value: string) {
  return titleCase(value.replace("evaluation.", "eval."));
}

function emptyCopy(isLoading: boolean, copy: string) {
  if (isLoading) {
    return "Loading governance signals...";
  }
  return copy;
}

export default function ResponsibleAIPage() {
  const auth = useAuth();
  const dashboard = useQuery({
    queryKey: ["responsible-ai", auth.token],
    queryFn: () => api.getResponsibleAI(auth.token as string),
    enabled: Boolean(auth.token),
  });

  const summary = dashboard.data?.summary;
  const redactionData = dashboard.data?.redaction_categories || [];
  const humanReviewBreakdown = dashboard.data?.human_review_breakdown || [];
  const governanceEvents = dashboard.data?.governance_events || [];
  const candidateSignals = dashboard.data?.recent_candidate_signals || [];

  const reviewPie = humanReviewBreakdown.map((item) => ({
    name: item.label,
    value: item.requires_review,
  }));

  return (
    <AppShell
      title="Bias Shield"
      subtitle="Track protected-attribute redaction, human-review posture, recruiter overrides, calibration backlog, and governance events from one responsible-AI control room."
    >
      <div className="grid gap-4 lg:grid-cols-4">
        <MetricCard
          label="Protected signal rate"
          value={`${formatScore(summary?.protected_signal_rate)}%`}
          hint={`${summary?.redacted_resumes || 0}/${summary?.resumes_processed || 0} resumes had demographic signals redacted.`}
        />
        <MetricCard
          label="Human review rate"
          value={`${formatScore(summary?.human_review_rate)}%`}
          hint={`${summary?.human_review_candidates || 0} candidates currently carry a human-review signal.`}
        />
        <MetricCard
          label="Override rate"
          value={`${formatScore(summary?.override_rate)}%`}
          hint={`${summary?.override_count || 0}/${summary?.total_decisions || 0} recruiter decisions overrode AI.`}
        />
        <MetricCard
          label="Open calibration"
          value={String(summary?.open_calibration_cases || 0)}
          hint={`${summary?.overdue_calibration_cases || 0} overdue calibration cases need attention.`}
        />
      </div>

      <div className="mt-6 grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <Card className="min-h-[390px]">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">
                Protected-attribute redaction
              </p>
              <p className="mt-3 max-w-2xl text-sm leading-7 text-muted">
                Categories detected by the resume bias shield before AI parsing and matching. Counts represent
                redaction evidence, not candidate quality signals.
              </p>
            </div>
            <Badge tone={redactionData.length ? "success" : "neutral"}>
              {summary?.total_redactions || 0} redactions
            </Badge>
          </div>
          <div className="mt-6 h-[260px] min-w-0">
            {redactionData.length ? (
              <ResponsiveContainer width="100%" height="100%" minWidth={0} initialDimension={{ width: 800, height: 260 }}>
                <BarChart data={redactionData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#d9deeb" />
                  <XAxis
                    dataKey="category"
                    tickFormatter={(value) => titleCase(String(value)).slice(0, 18)}
                    tick={{ fontSize: 12 }}
                  />
                  <YAxis allowDecimals={false} />
                  <Tooltip labelFormatter={(value) => titleCase(String(value))} />
                  <Bar dataKey="count" radius={[12, 12, 0, 0]} fill="#135d66" />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center rounded-[24px] border border-dashed border-border bg-white/60 px-6 text-center text-sm text-muted">
                {emptyCopy(dashboard.isLoading, "No protected-attribute redactions have been recorded for this workspace yet.")}
              </div>
            )}
          </div>
        </Card>

        <Card className="min-h-[390px]">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">
                Human-review posture
              </p>
              <p className="mt-3 text-sm leading-7 text-muted">
                Where the platform is asking a person to review AI-assisted output before a hiring decision advances.
              </p>
            </div>
            <UserCheck className="size-6 text-brand" />
          </div>
          <div className="mt-5 h-[210px] min-w-0">
            {reviewPie.some((item) => item.value > 0) ? (
              <ResponsiveContainer width="100%" height="100%" minWidth={0} initialDimension={{ width: 420, height: 210 }}>
                <PieChart>
                  <Pie data={reviewPie} dataKey="value" nameKey="name" outerRadius={86} innerRadius={52}>
                    {reviewPie.map((entry, index) => (
                      <Cell key={entry.name} fill={chartColors[index % chartColors.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center rounded-[24px] border border-dashed border-border bg-white/60 px-6 text-center text-sm text-muted">
                {emptyCopy(dashboard.isLoading, "No human-review signals are active yet.")}
              </div>
            )}
          </div>
          <div className="mt-4 space-y-3">
            {humanReviewBreakdown.map((item) => (
              <div key={item.label} className="flex items-center justify-between rounded-2xl bg-white/70 px-4 py-3 text-sm">
                <span className="font-medium text-text">{item.label}</span>
                <span className="text-muted">
                  {item.requires_review}/{item.total} · {formatScore(item.rate)}%
                </span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="mt-6 grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
        <Card>
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">
            Governance controls
          </p>
          <div className="mt-5 space-y-4">
            {(dashboard.data?.controls || []).map((control) => (
              <div key={control.name} className="rounded-[24px] border border-border/70 bg-white/70 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    {control.status === "attention" ? (
                      <AlertTriangle className="size-5 text-amber-600" />
                    ) : (
                      <CheckCircle2 className="size-5 text-emerald-700" />
                    )}
                    <p className="font-semibold text-text">{control.name}</p>
                  </div>
                  <Badge tone={controlTone(control.status)}>
                    {titleCase(control.status)} · {control.evidence_count}
                  </Badge>
                </div>
                <p className="mt-3 text-sm leading-7 text-muted">{control.description}</p>
              </div>
            ))}
          </div>
          <div className="mt-5 rounded-[24px] border border-brand/10 bg-brand-soft/60 p-4 text-sm leading-7 text-brand">
            {dashboard.data?.policy_note || "Responsible-AI metrics are loading."}
          </div>
        </Card>

        <Card>
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">
                Governance event coverage
              </p>
              <p className="mt-3 text-sm leading-7 text-muted">
                Event outbox signals that prove the workflow is auditable beyond the transactional UI.
              </p>
            </div>
            <ShieldCheck className="size-6 text-brand" />
          </div>
          <div className="mt-6 h-[250px] min-w-0">
            {governanceEvents.length ? (
              <ResponsiveContainer width="100%" height="100%" minWidth={0} initialDimension={{ width: 760, height: 250 }}>
                <BarChart data={governanceEvents} layout="vertical" margin={{ left: 28 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#d9deeb" />
                  <XAxis type="number" allowDecimals={false} />
                  <YAxis
                    type="category"
                    dataKey="event_type"
                    tickFormatter={(value) => eventLabel(String(value)).slice(0, 22)}
                    width={132}
                    tick={{ fontSize: 12 }}
                  />
                  <Tooltip labelFormatter={(value) => eventLabel(String(value))} />
                  <Bar dataKey="count" radius={[0, 12, 12, 0]} fill="#ec8f5e" />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center rounded-[24px] border border-dashed border-border bg-white/60 px-6 text-center text-sm text-muted">
                {emptyCopy(dashboard.isLoading, "No governance events have been emitted yet.")}
              </div>
            )}
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            <MiniMetric icon={<FileSearch className="size-4" />} label="Audit logs" value={summary?.audit_log_count || 0} />
            <MiniMetric icon={<Scale className="size-4" />} label="Governance events" value={summary?.governance_event_count || 0} />
            <MiniMetric icon={<ShieldCheck className="size-4" />} label="Reports reviewed" value={summary?.human_review_reports || 0} />
          </div>
        </Card>
      </div>

      <Card className="mt-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">
              Candidate governance queue
            </p>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-muted">
              Recent candidates with redaction evidence, human-review requirements, explicit AI overrides, or
              calibration activity. This is the “show your work” layer behind responsible hiring.
            </p>
          </div>
          <Badge tone={candidateSignals.length ? "warning" : "success"}>
            {candidateSignals.length} active signals
          </Badge>
        </div>
        <div className="mt-6 space-y-4">
          {candidateSignals.length ? (
            candidateSignals.map((candidate) => (
              <div key={candidate.candidate_id} className="rounded-[24px] border border-border/70 bg-white/75 p-5">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <div className="flex flex-wrap items-center gap-3">
                      <Link
                        href={`/candidates/${candidate.candidate_id}${candidate.job_id ? `?job=${candidate.job_id}` : ""}`}
                        className="font-display text-2xl font-semibold text-text hover:text-brand"
                      >
                        {candidate.candidate_name}
                      </Link>
                      <Badge tone={candidate.human_review_required ? "warning" : "neutral"}>
                        {candidate.human_review_required ? "Human review" : "Monitored"}
                      </Badge>
                      {candidate.override_ai_recommendation ? <Badge tone="danger">AI override</Badge> : null}
                      {candidate.open_calibration_case_count ? (
                        <Badge tone="brand">{candidate.open_calibration_case_count} calibration case</Badge>
                      ) : null}
                    </div>
                    <p className="mt-2 text-sm text-muted">
                      {candidate.job_title || "No job attached"} · {titleCase(candidate.status)}
                      {candidate.match_score !== null && candidate.match_score !== undefined
                        ? ` · Match ${formatScore(candidate.match_score)}%`
                        : ""}
                    </p>
                  </div>
                  <p className="text-sm text-muted">
                    {new Date(candidate.latest_signal_at).toLocaleString()}
                  </p>
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  {candidate.reasons.map((reason) => (
                    <Badge key={`${candidate.candidate_id}-${reason}`} tone="neutral">
                      {reason}
                    </Badge>
                  ))}
                </div>
                {candidate.redaction_categories.length ? (
                  <div className="mt-4 flex flex-wrap items-center gap-2 text-sm text-muted">
                    <span>Redacted categories:</span>
                    {candidate.redaction_categories.map((category) => (
                      <Badge key={`${candidate.candidate_id}-${category}`} tone="brand">
                        {titleCase(category)}
                      </Badge>
                    ))}
                  </div>
                ) : null}
              </div>
            ))
          ) : (
            <div className="rounded-[24px] border border-dashed border-border bg-white/60 px-6 py-10 text-center text-sm text-muted">
              {emptyCopy(dashboard.isLoading, "No candidate governance signals yet. Upload resumes, run matching, and record decisions to populate this queue.")}
            </div>
          )}
        </div>
      </Card>

      <Card className="mt-6">
        <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">
          Risk flags
        </p>
        <div className="mt-5 grid gap-3 lg:grid-cols-2">
          {(dashboard.data?.risk_flags || []).map((flag) => (
            <div key={flag} className="flex gap-3 rounded-[22px] border border-border/70 bg-white/75 p-4 text-sm leading-7 text-muted">
              <AlertTriangle className="mt-1 size-4 shrink-0 text-amber-600" />
              <span>{flag}</span>
            </div>
          ))}
        </div>
      </Card>
    </AppShell>
  );
}

function MiniMetric({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
}) {
  return (
    <div className="rounded-2xl bg-white/70 px-4 py-3">
      <div className="flex items-center gap-2 text-brand">
        {icon}
        <span className="text-xs font-semibold uppercase tracking-[0.18em]">{label}</span>
      </div>
      <p className="mt-2 font-display text-3xl font-semibold text-text">{value}</p>
    </div>
  );
}
