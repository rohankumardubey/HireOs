"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
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
import type { EvaluationRun } from "@/lib/types";
import { formatScore, titleCase } from "@/lib/utils";

function qualityTone(status?: string | null) {
  if (status === "passed") {
    return "success" as const;
  }
  if (status === "failed") {
    return "danger" as const;
  }
  return "warning" as const;
}

function caseStatus(run: EvaluationRun) {
  const failedCases = run.case_results.filter(
    (result) => !result.strong_passes || result.weak_passes || result.regression_detected,
  );
  return { failedCases, healthyCases: run.total_cases - failedCases.length };
}

export default function EvaluationsPage() {
  const auth = useAuth();
  const role = auth.user?.memberships?.[0]?.role || "recruiter";
  const canRun = ["admin", "recruiter"].includes(role);
  const runs = useQuery({
    queryKey: ["evaluation-runs", auth.token],
    queryFn: () => api.getEvaluationRuns(auth.token as string),
    enabled: Boolean(auth.token),
  });
  const runEvaluation = useMutation({
    mutationFn: () => api.createEvaluationRun(auth.token as string),
    onSuccess: async () => {
      await runs.refetch();
    },
  });

  const latest = runs.data?.latest;
  const cases = latest ? caseStatus(latest) : null;
  const chartData =
    latest?.case_results.map((result) => ({
      name: `${result.role} · ${result.skill_category}`,
      strong: result.strong_score,
      weak: result.weak_score,
      threshold: result.min_passing_score,
    })) || [];

  return (
    <AppShell
      title="Model Quality"
      subtitle="Run versioned golden-set evaluations, inspect score separation, and catch scoring regressions before changing production hiring policy."
      actions={
        canRun ? (
          <button
            type="button"
            disabled={runEvaluation.isPending}
            onClick={() => runEvaluation.mutate()}
            className="rounded-full bg-brand px-5 py-3 text-sm font-semibold text-white disabled:opacity-60"
          >
            {runEvaluation.isPending ? "Running evaluation..." : "Run evaluation"}
          </button>
        ) : undefined
      }
    >
      {runs.isLoading ? (
        <Card>
          <p className="text-sm text-muted">Loading evaluation history...</p>
        </Card>
      ) : null}

      {runEvaluation.error ? (
        <div className="mb-5 rounded-[24px] bg-rose-100 px-4 py-4 text-sm text-rose-700">
          {runEvaluation.error.message}
        </div>
      ) : null}

      {latest ? (
        <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <MetricCard
              label="Strong-answer pass rate"
              value={`${formatScore(latest.strong_pass_rate)}%`}
              hint={`${latest.false_negative_count} expected-strong cases currently fail their threshold.`}
            />
            <MetricCard
              label="Weak-answer rejection"
              value={`${formatScore(latest.weak_rejection_rate)}%`}
              hint={`${latest.false_positive_count} weak cases currently pass unexpectedly.`}
            />
            <MetricCard
              label="Average separation"
              value={`${formatScore(latest.average_score_separation)} pts`}
              hint="Average score distance between the strong and weak answer for each case."
            />
            <MetricCard
              label="Regressions"
              value={String(latest.regression_count)}
              hint="Cases that degraded materially relative to the previous completed run."
            />
          </div>

          <div className="mt-6 grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
            <Card className="min-h-[430px]">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">
                    Golden-set separation
                  </p>
                  <h3 className="mt-2 font-display text-2xl font-semibold text-text">
                    Strong answers should clear weak answers and the passing threshold
                  </h3>
                </div>
                <Badge tone={qualityTone(latest.quality_status)}>
                  {titleCase(latest.quality_status || latest.status)}
                </Badge>
              </div>
              <div className="mt-6 h-[320px]">
                <ResponsiveContainer
                  width="100%"
                  height="100%"
                  minWidth={0}
                  initialDimension={{ width: 800, height: 320 }}
                >
                  <BarChart data={chartData} margin={{ left: 0, right: 12, bottom: 54 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#d9deeb" />
                    <XAxis
                      dataKey="name"
                      angle={-24}
                      textAnchor="end"
                      interval={0}
                      height={88}
                      tick={{ fontSize: 11 }}
                    />
                    <YAxis domain={[0, 100]} />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="strong" name="Strong answer" fill="#135d66" radius={[8, 8, 0, 0]} />
                    <Bar dataKey="weak" name="Weak answer" fill="#ec8f5e" radius={[8, 8, 0, 0]} />
                    <Bar dataKey="threshold" name="Passing threshold" fill="#9ba7b7" radius={[8, 8, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>

            <Card>
              <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">
                Evaluation contract
              </p>
              <div className="mt-5 space-y-3">
                <div className="rounded-[20px] bg-white/70 px-4 py-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-muted-soft">Dataset</p>
                  <p className="mt-2 font-semibold text-text">{latest.dataset_name}</p>
                  <p className="mt-1 break-all text-xs text-muted">Version {latest.dataset_version}</p>
                </div>
                <div className="rounded-[20px] bg-white/70 px-4 py-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-muted-soft">Scoring policy</p>
                  <p className="mt-2 font-semibold text-text">{latest.scoring_policy_version}</p>
                  <p className="mt-1 text-xs text-muted">Provider: {latest.provider}</p>
                </div>
                <div className="rounded-[20px] bg-white/70 px-4 py-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-muted-soft">Case health</p>
                  <p className="mt-2 font-semibold text-text">
                    {cases?.healthyCases || 0} healthy · {cases?.failedCases.length || 0} need review
                  </p>
                </div>
                <div className="rounded-[20px] bg-amber-50 px-4 py-4 text-sm leading-7 text-amber-800">
                  {runs.data?.policy_note}
                </div>
              </div>
            </Card>
          </div>

          <Card className="mt-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">
                  Case review
                </p>
                <h3 className="mt-2 font-display text-2xl font-semibold text-text">
                  Failed cases and evidence
                </h3>
              </div>
              <Badge tone={cases?.failedCases.length ? "warning" : "success"}>
                {cases?.failedCases.length || 0} need attention
              </Badge>
            </div>
            <div className="mt-5 space-y-3">
              {latest.case_results.map((result) => {
                const needsReview =
                  !result.strong_passes || result.weak_passes || result.regression_detected;
                return (
                  <div
                    key={result.id}
                    className="rounded-[24px] border border-border bg-white/70 px-4 py-4"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-text">{result.question}</p>
                        <p className="mt-1 text-sm text-muted">
                          {result.role} · {titleCase(result.skill_category)}
                        </p>
                      </div>
                      <Badge tone={needsReview ? "warning" : "success"}>
                        {needsReview ? "Review" : "Healthy"}
                      </Badge>
                    </div>
                    <div className="mt-4 grid gap-3 md:grid-cols-4">
                      <div className="rounded-[18px] bg-surface px-3 py-3">
                        <p className="text-xs uppercase tracking-[0.16em] text-muted-soft">Strong</p>
                        <p className="mt-2 font-semibold text-text">{result.strong_score}</p>
                      </div>
                      <div className="rounded-[18px] bg-surface px-3 py-3">
                        <p className="text-xs uppercase tracking-[0.16em] text-muted-soft">Weak</p>
                        <p className="mt-2 font-semibold text-text">{result.weak_score}</p>
                      </div>
                      <div className="rounded-[18px] bg-surface px-3 py-3">
                        <p className="text-xs uppercase tracking-[0.16em] text-muted-soft">Threshold</p>
                        <p className="mt-2 font-semibold text-text">{result.min_passing_score}</p>
                      </div>
                      <div className="rounded-[18px] bg-surface px-3 py-3">
                        <p className="text-xs uppercase tracking-[0.16em] text-muted-soft">Separation</p>
                        <p className="mt-2 font-semibold text-text">{result.score_separation}</p>
                      </div>
                    </div>
                    {!result.strong_passes ? (
                      <p className="mt-3 text-sm text-rose-700">
                        Expected-strong answer failed its configured threshold.
                      </p>
                    ) : null}
                    {result.weak_passes ? (
                      <p className="mt-3 text-sm text-rose-700">
                        Expected-weak answer passed unexpectedly.
                      </p>
                    ) : null}
                    {result.regression_reason ? (
                      <p className="mt-3 text-sm text-rose-700">{result.regression_reason}</p>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </Card>

          <Card className="mt-6">
            <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">
              Run history
            </p>
            <div className="mt-5 space-y-3">
              {runs.data?.runs.map((run) => (
                <div
                  key={run.id}
                  className="grid gap-3 rounded-[22px] border border-border bg-white/70 px-4 py-4 md:grid-cols-[1.4fr_0.7fr_0.7fr_0.7fr]"
                >
                  <div>
                    <p className="font-semibold text-text">{new Date(run.created_at).toLocaleString()}</p>
                    <p className="mt-1 text-xs text-muted">
                      {run.scoring_policy_version} · {run.dataset_version}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-[0.16em] text-muted-soft">Quality</p>
                    <Badge tone={qualityTone(run.quality_status)}>
                      {titleCase(run.quality_status || run.status)}
                    </Badge>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-[0.16em] text-muted-soft">Strong pass</p>
                    <p className="mt-2 font-semibold text-text">{run.strong_pass_rate}%</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-[0.16em] text-muted-soft">Regressions</p>
                    <p className="mt-2 font-semibold text-text">{run.regression_count}</p>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </>
      ) : !runs.isLoading ? (
        <Card>
          <h3 className="font-display text-2xl font-semibold text-text">
            No evaluation runs yet
          </h3>
          <p className="mt-3 text-sm leading-7 text-muted">
            Run the current golden set to establish a versioned baseline before changing interview scoring.
          </p>
        </Card>
      ) : null}
    </AppShell>
  );
}
