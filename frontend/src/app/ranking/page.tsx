"use client";

import { useDeferredValue, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { AppShell } from "@/components/layout/app-shell";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { useAuth } from "@/hooks/use-auth";
import { api } from "@/lib/api";
import { formatScore, titleCase } from "@/lib/utils";

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function statusTone(rankChange: number) {
  if (rankChange > 0) {
    return "success" as const;
  }
  if (rankChange < 0) {
    return "danger" as const;
  }
  return "neutral" as const;
}

export default function RankingPage() {
  const auth = useAuth();
  const jobs = useQuery({
    queryKey: ["jobs", auth.token],
    queryFn: () => api.getJobs(auth.token as string),
    enabled: Boolean(auth.token),
  });
  const selectedJobId = useMemo(() => jobs.data?.[0]?.id || "", [jobs.data]);
  const [jobId, setJobId] = useState("");
  const activeJobId = jobId || selectedJobId;
  const [simulator, setSimulator] = useState({
    resume_weight: 55,
    interview_weight: 45,
    missing_skill_penalty: 6,
    human_review_penalty: 8,
    shortlist_boost: 4,
  });
  const deferredSimulator = useDeferredValue(simulator);

  const ranking = useQuery({
    queryKey: ["ranking", auth.token, activeJobId],
    queryFn: () => api.getJobRanking(auth.token as string, activeJobId),
    enabled: Boolean(auth.token && activeJobId),
  });

  const simulation = useQuery({
    queryKey: [
      "ranking-simulation",
      auth.token,
      activeJobId,
      deferredSimulator.resume_weight,
      deferredSimulator.interview_weight,
      deferredSimulator.missing_skill_penalty,
      deferredSimulator.human_review_penalty,
      deferredSimulator.shortlist_boost,
    ],
    queryFn: () => api.simulateJobRanking(auth.token as string, activeJobId, deferredSimulator),
    enabled: Boolean(auth.token && activeJobId),
  });

  return (
    <AppShell
      title="Candidate Ranking"
      subtitle="Simulate different hiring scorecards, stress-test your shortlist policy, and keep the recruiter in control of the final ranking logic."
    >
      <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
        <Card>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">
                Shortlist simulator
              </p>
              <h2 className="mt-3 font-display text-3xl font-semibold text-text">
                Pressure-test the hiring scorecard
              </h2>
              <p className="mt-3 max-w-xl text-sm leading-7 text-muted">
                Change the weighting between resume alignment and interview evidence, then see who rises or falls before you commit a shortlist.
              </p>
            </div>
            <label className="block min-w-[240px]">
              <span className="text-sm font-medium text-muted">Job</span>
              <select
                className="mt-2 w-full rounded-2xl border border-border bg-white/80 px-4 py-3 outline-none"
                value={activeJobId}
                onChange={(event) => setJobId(event.target.value)}
              >
                {jobs.data?.map((job) => (
                  <option key={job.id} value={job.id}>
                    {job.title}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-2">
            {[
              {
                key: "resume_weight",
                label: "Resume weight",
                hint: "How much structured job-match evidence should drive the shortlist.",
                max: 100,
                suffix: "%",
              },
              {
                key: "interview_weight",
                label: "Interview weight",
                hint: "How much interview performance should shape the simulated ranking.",
                max: 100,
                suffix: "%",
              },
              {
                key: "missing_skill_penalty",
                label: "Missing skill penalty",
                hint: "Penalty applied per missing required skill.",
                max: 25,
                suffix: " pts",
              },
              {
                key: "human_review_penalty",
                label: "Human review penalty",
                hint: "Penalty for candidates still flagged for human review.",
                max: 25,
                suffix: " pts",
              },
              {
                key: "shortlist_boost",
                label: "Recruiter shortlist boost",
                hint: "Boost for candidates already advanced by a recruiter.",
                max: 20,
                suffix: " pts",
              },
            ].map((control) => (
              <div
                key={control.key}
                className={control.key === "shortlist_boost" ? "rounded-[24px] border border-border bg-white/70 p-4 md:col-span-2" : "rounded-[24px] border border-border bg-white/70 p-4"}
              >
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="font-semibold text-text">{control.label}</p>
                    <p className="mt-1 text-sm leading-6 text-muted">{control.hint}</p>
                  </div>
                  <Badge tone="brand">
                    {simulator[control.key as keyof typeof simulator]}
                    {control.suffix}
                  </Badge>
                </div>
                <input
                  type="range"
                  min={0}
                  max={control.max}
                  step={1}
                  value={simulator[control.key as keyof typeof simulator]}
                  onChange={(event) =>
                    setSimulator((current) => ({
                      ...current,
                      [control.key]: clamp(Number(event.target.value), 0, control.max),
                    }))
                  }
                  className="mt-4 w-full accent-[#0f6b78]"
                />
              </div>
            ))}
          </div>

          <div className="mt-6 rounded-[24px] bg-brand-soft px-5 py-4">
            <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">
              Policy readout
            </p>
            <p className="mt-3 text-sm leading-7 text-text">
              {simulation.data?.summary ||
                "Choose a job to simulate how different shortlist policies change the ranking."}
            </p>
            <p className="mt-3 text-xs leading-6 text-muted">
              {simulation.data?.policy_note ||
                "These sliders are for scenario planning only. Recruiters should confirm the policy remains fair and role-appropriate before acting on it."}
            </p>
          </div>
        </Card>

        <Card>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">
                Simulated shortlist
              </p>
              <h2 className="mt-3 font-display text-3xl font-semibold text-text">
                Baseline vs reweighted ranking
              </h2>
            </div>
            {simulation.data?.top_mover_candidate_id ? (
              <Badge tone="warning">Top mover detected</Badge>
            ) : (
              <Badge tone="neutral">Stable ranking</Badge>
            )}
          </div>

          <div className="mt-6 space-y-3">
            {simulation.data?.candidates?.length ? (
              simulation.data.candidates.map((candidate) => (
                <div
                  key={candidate.candidate_id}
                  className="rounded-[24px] border border-border bg-white/70 px-4 py-4"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-3">
                        <p className="font-semibold text-text">{candidate.candidate_name}</p>
                        <Badge tone={statusTone(candidate.rank_change)}>
                          {candidate.rank_change > 0
                            ? `Up ${candidate.rank_change}`
                            : candidate.rank_change < 0
                              ? `Down ${Math.abs(candidate.rank_change)}`
                              : "No move"}
                        </Badge>
                      </div>
                      <p className="mt-2 text-sm text-muted">
                        Baseline #{candidate.baseline_rank} {"->"} Simulated #{candidate.simulated_rank} · {titleCase(candidate.ai_recommendation)}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-xs uppercase tracking-[0.2em] text-muted-soft">Simulated score</p>
                      <p className="mt-1 font-display text-3xl font-semibold text-brand">
                        {formatScore(candidate.simulated_score)}%
                      </p>
                    </div>
                  </div>

                  <div className="mt-4 grid gap-3 md:grid-cols-4">
                    <div className="rounded-[18px] bg-surface-elevated px-3 py-3">
                      <p className="text-xs uppercase tracking-[0.18em] text-muted-soft">Resume match</p>
                      <p className="mt-2 font-semibold text-text">{formatScore(candidate.match_score)}%</p>
                    </div>
                    <div className="rounded-[18px] bg-surface-elevated px-3 py-3">
                      <p className="text-xs uppercase tracking-[0.18em] text-muted-soft">Interview</p>
                      <p className="mt-2 font-semibold text-text">{formatScore(candidate.interview_score)}%</p>
                    </div>
                    <div className="rounded-[18px] bg-surface-elevated px-3 py-3">
                      <p className="text-xs uppercase tracking-[0.18em] text-muted-soft">Required coverage</p>
                      <p className="mt-2 font-semibold text-text">
                        {formatScore(candidate.required_skill_coverage)}%
                      </p>
                    </div>
                    <div className="rounded-[18px] bg-surface-elevated px-3 py-3">
                      <p className="text-xs uppercase tracking-[0.18em] text-muted-soft">Baseline</p>
                      <p className="mt-2 font-semibold text-text">{formatScore(candidate.baseline_score)}%</p>
                    </div>
                  </div>

                  <p className="mt-4 text-sm leading-7 text-muted">{candidate.movement_reason}</p>

                  <div className="mt-4 flex flex-wrap gap-2">
                    {candidate.human_review_required ? <Badge tone="warning">Human review required</Badge> : null}
                    {candidate.recruiter_decision ? (
                      <Badge tone="brand">Recruiter: {titleCase(candidate.recruiter_decision)}</Badge>
                    ) : null}
                    {candidate.missing_skills.slice(0, 3).map((skill) => (
                      <Badge key={skill} tone="danger">
                        Missing: {skill}
                      </Badge>
                    ))}
                  </div>
                </div>
              ))
            ) : ranking.data?.length ? (
              ranking.data.map((item) => (
                <div
                  key={item.candidate_id}
                  className="grid gap-3 rounded-[24px] border border-border bg-white/70 px-4 py-4 md:grid-cols-[0.4fr_1.2fr_0.8fr_0.8fr_0.8fr]"
                >
                  <div className="font-display text-3xl font-semibold text-brand">#{item.rank}</div>
                  <div>
                    <p className="font-semibold text-text">{item.candidate_name}</p>
                    <p className="mt-1 text-sm text-muted">
                      {titleCase(item.ai_recommendation)} · {titleCase(item.status)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-muted-soft">Match</p>
                    <p className="mt-1 font-semibold text-text">{formatScore(item.match_score)}%</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-muted-soft">Interview</p>
                    <p className="mt-1 font-semibold text-text">{formatScore(item.interview_score)}%</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-muted-soft">Final</p>
                    <div className="mt-1">
                      <Badge tone={item.final_score >= 70 ? "success" : "warning"}>
                        {formatScore(item.final_score)}%
                      </Badge>
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <p className="text-sm leading-7 text-muted">
                Choose a job that already has matched candidates to simulate different shortlist strategies.
              </p>
            )}
          </div>
        </Card>
      </div>
    </AppShell>
  );
}
