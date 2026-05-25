"use client";

import Link from "next/link";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { useAuth } from "@/hooks/use-auth";
import { api } from "@/lib/api";
import { formatScore, titleCase } from "@/lib/utils";

export default function ComparePage() {
  const auth = useAuth();
  const jobs = useQuery({
    queryKey: ["jobs", auth.token],
    queryFn: () => api.getJobs(auth.token as string),
    enabled: Boolean(auth.token),
  });
  const [selectedJobId, setSelectedJobId] = useState("");
  const defaultJobId = useMemo(() => jobs.data?.[0]?.id || "", [jobs.data]);
  const activeJobId = selectedJobId || defaultJobId;

  const ranking = useQuery({
    queryKey: ["ranking", auth.token, activeJobId],
    queryFn: () => api.getJobRanking(auth.token as string, activeJobId),
    enabled: Boolean(auth.token && activeJobId),
  });

  const [selectedCandidateIds, setSelectedCandidateIds] = useState<string[]>([]);
  const defaultCandidateIds = useMemo(
    () => ranking.data?.slice(0, 2).map((candidate) => candidate.candidate_id) || [],
    [ranking.data],
  );
  const effectiveSelectedCandidateIds = useMemo(() => {
    if (!ranking.data?.length) {
      return [];
    }

    const validCurrent = selectedCandidateIds.filter((id) =>
      ranking.data.some((candidate) => candidate.candidate_id === id),
    );
    return validCurrent.length ? validCurrent.slice(0, 3) : defaultCandidateIds;
  }, [defaultCandidateIds, ranking.data, selectedCandidateIds]);

  const comparison = useMutation({
    mutationFn: () =>
      api.compareCandidates(auth.token as string, activeJobId, {
        candidate_ids: effectiveSelectedCandidateIds,
      }),
  });

  const toggleCandidate = (candidateId: string) => {
    const baseSelection = effectiveSelectedCandidateIds;
    if (baseSelection.includes(candidateId)) {
      setSelectedCandidateIds(baseSelection.filter((id) => id !== candidateId));
      return;
    }
    if (baseSelection.length >= 3) {
      setSelectedCandidateIds([...baseSelection.slice(1), candidateId]);
      return;
    }
    setSelectedCandidateIds([...baseSelection, candidateId]);
  };

  return (
    <AppShell
      title="Candidate Comparison"
      subtitle="Pin finalists side by side, compare score evidence across the same job, and prepare a human-reviewed shortlist with clearer tradeoffs."
      actions={
        <button
          type="button"
          onClick={() => comparison.mutate()}
          disabled={
            !activeJobId ||
            effectiveSelectedCandidateIds.length < 2 ||
            comparison.isPending
          }
          className="rounded-full bg-brand px-5 py-3 text-sm font-semibold text-white disabled:opacity-60"
        >
          {comparison.isPending ? "Comparing..." : "Compare candidates"}
        </button>
      }
    >
      <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
        <Card>
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">
            Comparison setup
          </p>
          <h3 className="mt-2 font-display text-2xl font-semibold text-text">
            Pick a role and 2-3 finalists
          </h3>
          <div className="mt-5 space-y-5">
            <label className="block">
              <span className="text-sm font-medium text-muted">Job</span>
              <select
                className="mt-2 w-full rounded-2xl border border-border bg-white/80 px-4 py-3 outline-none"
                value={activeJobId}
                onChange={(event) => {
                  setSelectedJobId(event.target.value);
                  setSelectedCandidateIds([]);
                  comparison.reset();
                }}
              >
                {jobs.data?.map((job) => (
                  <option key={job.id} value={job.id}>
                    {job.title}
                  </option>
                ))}
              </select>
            </label>
            <div>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <span className="text-sm font-medium text-muted">Candidates</span>
                <Badge
                  tone={
                    effectiveSelectedCandidateIds.length >= 2 ? "success" : "warning"
                  }
                >
                  {effectiveSelectedCandidateIds.length}/3 selected
                </Badge>
              </div>
              <div className="mt-3 grid gap-3">
                {ranking.data?.length ? (
                  ranking.data.slice(0, 6).map((candidate) => {
                    const selected = effectiveSelectedCandidateIds.includes(candidate.candidate_id);
                    return (
                      <button
                        key={candidate.candidate_id}
                        type="button"
                        onClick={() => {
                          toggleCandidate(candidate.candidate_id);
                          comparison.reset();
                        }}
                        className={`rounded-[24px] border px-4 py-4 text-left transition ${
                          selected
                            ? "border-brand bg-brand-soft/70 text-brand"
                            : "border-border bg-white/80 text-text hover:border-brand/40"
                        }`}
                      >
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <p className="font-semibold">{candidate.candidate_name}</p>
                            <p className="mt-1 text-xs text-muted">
                              {titleCase(candidate.status)} · {titleCase(candidate.ai_recommendation)}
                            </p>
                          </div>
                          <Badge tone={candidate.final_score >= 70 ? "success" : "warning"}>
                            Final {formatScore(candidate.final_score)}%
                          </Badge>
                        </div>
                        <div className="mt-4 grid gap-3 sm:grid-cols-3">
                          <div>
                            <p className="text-[11px] uppercase tracking-[0.2em] text-muted-soft">
                              Match
                            </p>
                            <p className="mt-1 text-sm font-semibold text-text">
                              {formatScore(candidate.match_score)}%
                            </p>
                          </div>
                          <div>
                            <p className="text-[11px] uppercase tracking-[0.2em] text-muted-soft">
                              Interview
                            </p>
                            <p className="mt-1 text-sm font-semibold text-text">
                              {formatScore(candidate.interview_score)}%
                            </p>
                          </div>
                          <div>
                            <p className="text-[11px] uppercase tracking-[0.2em] text-muted-soft">
                              Rank
                            </p>
                            <p className="mt-1 text-sm font-semibold text-text">#{candidate.rank}</p>
                          </div>
                        </div>
                      </button>
                    );
                  })
                ) : (
                  <div className="rounded-[24px] bg-amber-50 px-4 py-4 text-sm text-amber-800">
                    No ranked candidates found for this job yet. Run resume matching and complete interviews to unlock comparison.
                  </div>
                )}
              </div>
            </div>
          </div>
        </Card>

        <div className="space-y-4">
          <Card>
            <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">
              Why this matters
            </p>
            <h3 className="mt-2 font-display text-2xl font-semibold text-text">
              Faster shortlist reviews without blind automation
            </h3>
            <div className="mt-5 space-y-3 text-sm leading-7 text-muted">
              <p>
                The comparison workspace helps recruiters defend why one candidate is ahead, where the gaps are still acceptable, and when a hiring manager should be pulled into the loop.
              </p>
              <p>
                Scores are blended with matched skills, missing requirements, interview evidence, and human-review flags so the outcome stays explainable.
              </p>
            </div>
            <Link
              href="/copilot"
              className="mt-6 inline-flex rounded-full border border-border bg-white/80 px-4 py-2 text-sm font-semibold text-text transition hover:border-brand hover:text-brand"
            >
              Open recruiter copilot
            </Link>
          </Card>
          <Card>
            <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">
              Recruiter checklist
            </p>
            <div className="mt-5 space-y-3">
              {[
                "Check whether the leading candidate is actually strongest on must-have skills or only lifted by interview performance.",
                "Look for missing requirements that could become delivery risk in the first 90 days.",
                "Use the final recommendation as a discussion starter, then record your override or shortlist decision.",
              ].map((item) => (
                <div key={item} className="rounded-[20px] bg-white/70 px-4 py-3 text-sm text-text">
                  {item}
                </div>
              ))}
            </div>
          </Card>
          {comparison.error ? (
            <Card className="border-rose-200 bg-rose-50 text-rose-700">
              <p className="text-sm">{comparison.error.message}</p>
            </Card>
          ) : null}
        </div>
      </div>

      {comparison.data ? (
        <div className="mt-6 space-y-4">
          <Card>
            <Badge tone="brand">Comparison outcome</Badge>
            <h3 className="mt-4 font-display text-3xl font-semibold text-text">
              {comparison.data.comparison_answer}
            </h3>
            <p className="mt-4 text-sm leading-7 text-muted">{comparison.data.summary}</p>
            <div className="mt-6 rounded-[24px] bg-brand-soft/60 px-4 py-4 text-sm leading-7 text-brand">
              {comparison.data.recommendation}
            </div>
            <div className="mt-4 rounded-[24px] bg-amber-50 px-4 py-4 text-sm text-amber-800">
              {comparison.data.human_review_note}
            </div>
          </Card>

          <div className="grid gap-4 xl:grid-cols-3">
            {comparison.data.candidates.map((candidate) => {
              const isLeader = candidate.candidate_id === comparison.data.top_candidate_id;
              return (
                <Card
                  key={candidate.candidate_id}
                  className={isLeader ? "border-brand/40 bg-brand-soft/30" : undefined}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="font-display text-2xl font-semibold text-text">
                          {candidate.candidate_name}
                        </h3>
                        {isLeader ? <Badge tone="success">Current leader</Badge> : null}
                      </div>
                      <p className="mt-2 text-sm text-muted">
                        {candidate.current_role || "Candidate"} · {candidate.years_experience} years experience
                      </p>
                    </div>
                    <Badge tone={candidate.human_review_required ? "warning" : "neutral"}>
                      {candidate.human_review_required ? "Human review" : "Review ready"}
                    </Badge>
                  </div>

                  <div className="mt-5 grid gap-3 sm:grid-cols-2">
                    <Metric label="Final score" value={`${formatScore(candidate.final_score)}%`} />
                    <Metric label="Confidence" value={`${formatScore(candidate.confidence_score)}%`} />
                    <Metric
                      label="Resume match"
                      value={`${formatScore(candidate.resume_match_score)}%`}
                    />
                    <Metric
                      label="Interview score"
                      value={`${formatScore(candidate.interview_score)}%`}
                    />
                    <Metric
                      label="Must-have coverage"
                      value={`${formatScore(candidate.must_have_coverage)}%`}
                    />
                    <Metric
                      label="AI recommendation"
                      value={titleCase(candidate.ai_recommendation)}
                    />
                  </div>

                  <div className="mt-5">
                    <p className="text-xs uppercase tracking-[0.2em] text-muted-soft">
                      Strengths
                    </p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {candidate.strengths.map((item) => (
                        <Badge key={`${candidate.candidate_id}-${item}`} tone="success">
                          {item}
                        </Badge>
                      ))}
                    </div>
                  </div>

                  <div className="mt-5">
                    <p className="text-xs uppercase tracking-[0.2em] text-muted-soft">
                      Matched skills
                    </p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {candidate.matched_skills.length ? (
                        candidate.matched_skills.map((skill) => (
                          <Badge key={`${candidate.candidate_id}-skill-${skill}`} tone="brand">
                            {skill}
                          </Badge>
                        ))
                      ) : (
                        <span className="text-sm text-muted">No matched skills captured yet.</span>
                      )}
                    </div>
                  </div>

                  <div className="mt-5">
                    <p className="text-xs uppercase tracking-[0.2em] text-muted-soft">
                      Missing skills
                    </p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {candidate.missing_skills.length ? (
                        candidate.missing_skills.map((skill) => (
                          <Badge key={`${candidate.candidate_id}-missing-${skill}`} tone="danger">
                            {skill}
                          </Badge>
                        ))
                      ) : (
                        <span className="text-sm text-muted">No missing must-have skills detected.</span>
                      )}
                    </div>
                  </div>

                  <div className="mt-5">
                    <p className="text-xs uppercase tracking-[0.2em] text-muted-soft">
                      Risk notes
                    </p>
                    <div className="mt-3 space-y-2">
                      {candidate.risk_notes.map((note) => (
                        <div
                          key={`${candidate.candidate_id}-risk-${note}`}
                          className="rounded-[18px] bg-white/80 px-3 py-3 text-sm text-text"
                        >
                          {note}
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="mt-5 rounded-[20px] bg-white/80 px-4 py-4 text-sm text-text">
                    <p className="font-semibold text-text">Report excerpt</p>
                    <p className="mt-2 leading-7 text-muted">{candidate.report_excerpt}</p>
                    {candidate.recruiter_decision ? (
                      <p className="mt-3 text-sm text-text">
                        Recruiter decision: {titleCase(candidate.recruiter_decision)}
                      </p>
                    ) : null}
                  </div>
                </Card>
              );
            })}
          </div>

          <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
            <Card>
              <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">
                Comparison axes
              </p>
              <div className="mt-5 space-y-3">
                {comparison.data.axes.map((axis) => {
                  const winner = comparison.data.candidates.find(
                    (candidate) => candidate.candidate_id === axis.winner_candidate_id,
                  );
                  return (
                    <div
                      key={axis.label}
                      className="rounded-[24px] border border-border bg-white/70 px-4 py-4"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <p className="font-semibold text-text">{axis.label}</p>
                        <Badge tone="brand">{winner?.candidate_name || "Candidate"}</Badge>
                      </div>
                      <p className="mt-3 text-sm leading-7 text-muted">{axis.description}</p>
                    </div>
                  );
                })}
              </div>
            </Card>

            <Card>
              <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">
                Recruiter follow-up questions
              </p>
              <div className="mt-5 space-y-3">
                {comparison.data.recruiter_questions.map((question) => (
                  <div
                    key={question}
                    className="rounded-[24px] border border-border bg-white/70 px-4 py-4 text-sm leading-7 text-text"
                  >
                    {question}
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[20px] bg-white/80 px-4 py-4">
      <p className="text-[11px] uppercase tracking-[0.2em] text-muted-soft">{label}</p>
      <p className="mt-2 text-lg font-semibold text-text">{value}</p>
    </div>
  );
}
