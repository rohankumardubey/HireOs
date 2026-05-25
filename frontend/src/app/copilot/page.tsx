"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { useAuth } from "@/hooks/use-auth";
import { api } from "@/lib/api";
import { formatScore, titleCase } from "@/lib/utils";

const starterPrompts = [
  "Why is Aarav Patel 1 ranked above Mia Chen 2?",
  "Show me candidates missing kafka but strong in sql.",
  "Draft a hiring-manager shortlist summary for this job.",
  "What evidence supports this weak match score?",
  "What should I review next before moving candidates forward?",
];

export default function CopilotPage() {
  const auth = useAuth();
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

  const defaultJobId = useMemo(() => jobs.data?.[0]?.id || "", [jobs.data]);
  const [selectedJobId, setSelectedJobId] = useState("");
  const [selectedCandidateIds, setSelectedCandidateIds] = useState<string[]>([]);
  const [query, setQuery] = useState(starterPrompts[0]);

  const activeJobId = selectedJobId || defaultJobId;

  const copilotMutation = useMutation({
    mutationFn: () =>
      api.copilotQuery(auth.token as string, {
        query,
        job_id: activeJobId || null,
        candidate_ids: selectedCandidateIds,
      }),
  });

  return (
    <AppShell
      title="Recruiter Copilot"
      subtitle="Ask recruiter-style questions over jobs, candidates, reports, and rankings to understand evidence, compare applicants, and prepare manager-ready summaries."
      actions={
        <button
          type="button"
          onClick={() => copilotMutation.mutate()}
          disabled={!query.trim() || copilotMutation.isPending}
          className="rounded-full bg-brand px-5 py-3 text-sm font-semibold text-white disabled:opacity-60"
        >
          {copilotMutation.isPending ? "Thinking..." : "Run copilot"}
        </button>
      }
    >
      <div className="grid gap-4 lg:grid-cols-[0.95fr_1.05fr]">
        <Card>
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">
            Query workspace
          </p>
          <h3 className="mt-2 font-display text-2xl font-semibold text-text">
            Ask with job context
          </h3>
          <div className="mt-5 space-y-4">
            <label className="block">
              <span className="text-sm font-medium text-muted">Job</span>
              <select
                className="mt-2 w-full rounded-2xl border border-border bg-white/80 px-4 py-3 outline-none"
                value={activeJobId}
                onChange={(event) => setSelectedJobId(event.target.value)}
              >
                {jobs.data?.map((job) => (
                  <option key={job.id} value={job.id}>
                    {job.title}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="text-sm font-medium text-muted">Query</span>
              <textarea
                rows={6}
                className="mt-2 w-full rounded-[24px] border border-border bg-white/80 px-4 py-4 outline-none"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </label>
            <div>
              <p className="text-sm font-medium text-muted">Optional candidate focus</p>
              <div className="mt-3 grid gap-2">
                {candidates.data?.slice(0, 8).map((candidate) => {
                  const selected = selectedCandidateIds.includes(candidate.id);
                  return (
                    <button
                      key={candidate.id}
                      type="button"
                      onClick={() =>
                        setSelectedCandidateIds((current) =>
                          current.includes(candidate.id)
                            ? current.filter((id) => id !== candidate.id)
                            : [...current, candidate.id],
                        )
                      }
                      className={`rounded-2xl border px-4 py-3 text-left text-sm transition ${
                        selected
                          ? "border-brand bg-brand-soft text-brand"
                          : "border-border bg-white/70 text-text"
                      }`}
                    >
                      <span className="font-semibold">{candidate.name}</span>
                      <span className="mt-1 block text-xs text-muted">
                        {candidate.current_role || "Candidate"} · {titleCase(candidate.status)}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </Card>

        <Card>
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">
            Prompt shortcuts
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            {starterPrompts.map((prompt) => (
              <button
                key={prompt}
                type="button"
                onClick={() => setQuery(prompt)}
                className="rounded-full border border-border bg-white/80 px-4 py-2 text-sm text-text transition hover:border-brand hover:text-brand"
              >
                {prompt}
              </button>
            ))}
          </div>
          <div className="mt-6 rounded-[24px] bg-brand-soft/60 px-4 py-4 text-sm leading-7 text-brand">
            This copilot uses stored hiring evidence such as match explanations, missing skills, interview scores, and recruiter-review signals. It does not make final hiring decisions.
          </div>
          {copilotMutation.error ? (
            <div className="mt-4 rounded-[24px] bg-rose-100 px-4 py-4 text-sm text-rose-700">
              {copilotMutation.error.message}
            </div>
          ) : null}
        </Card>
      </div>

      {copilotMutation.data ? (
        <div className="mt-6 space-y-4">
          <Card>
            <Badge tone="brand">Copilot answer</Badge>
            <h3 className="mt-4 font-display text-3xl font-semibold text-text">
              {copilotMutation.data.answer}
            </h3>
            <p className="mt-4 text-sm leading-7 text-muted">
              {copilotMutation.data.recommendation}
            </p>
            <div className="mt-6 rounded-[24px] bg-amber-50 px-4 py-4 text-sm text-amber-800">
              {copilotMutation.data.human_review_note}
            </div>
          </Card>

          <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
            <Card>
              <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">
                Evidence
              </p>
              <div className="mt-5 space-y-3">
                {copilotMutation.data.evidence.map((item) => (
                  <div
                    key={item.label}
                    className="rounded-[24px] border border-border bg-white/70 px-4 py-4"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <p className="font-semibold text-text">{item.label}</p>
                      <div className="flex flex-wrap gap-2">
                        {item.resume_match !== undefined && item.resume_match !== null ? (
                          <Badge tone="brand">Match {formatScore(item.resume_match)}%</Badge>
                        ) : null}
                        {item.interview_score !== undefined && item.interview_score !== null ? (
                          <Badge tone="neutral">Interview {formatScore(item.interview_score)}%</Badge>
                        ) : null}
                        {item.human_review_required ? (
                          <Badge tone="warning">Human review</Badge>
                        ) : null}
                      </div>
                    </div>
                    {item.ai_recommendation ? (
                      <p className="mt-3 text-sm text-muted">
                        AI recommendation: {titleCase(item.ai_recommendation)}
                      </p>
                    ) : null}
                    {item.missing_skills?.length ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {item.missing_skills.map((skill) => (
                          <Badge key={`${item.label}-${skill}`} tone="danger">
                            Missing: {skill}
                          </Badge>
                        ))}
                      </div>
                    ) : null}
                    {item.strength_skills?.length ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {item.strength_skills.map((skill) => (
                          <Badge key={`${item.label}-${skill}`} tone="success">
                            Strong: {skill}
                          </Badge>
                        ))}
                      </div>
                    ) : null}
                    {item.match_explanation ? (
                      <p className="mt-3 text-sm leading-7 text-muted">
                        {item.match_explanation}
                      </p>
                    ) : null}
                    {item.report_excerpt ? (
                      <p className="mt-3 rounded-2xl bg-white px-3 py-3 text-sm text-text">
                        {item.report_excerpt}
                      </p>
                    ) : null}
                  </div>
                ))}
              </div>
            </Card>

            <div className="space-y-4">
              <Card>
                <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">
                  Suggested next actions
                </p>
                <div className="mt-5 space-y-3">
                  {copilotMutation.data.action_items.map((item) => (
                    <div key={item} className="rounded-[20px] bg-white/70 px-4 py-3 text-sm text-text">
                      {item}
                    </div>
                  ))}
                </div>
              </Card>
              <Card>
                <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">
                  Follow-up prompts
                </p>
                <div className="mt-5 space-y-3">
                  {copilotMutation.data.follow_up_questions.map((item) => (
                    <button
                      key={item}
                      type="button"
                      onClick={() => setQuery(item)}
                      className="w-full rounded-[20px] border border-border bg-white/80 px-4 py-3 text-left text-sm text-text transition hover:border-brand hover:text-brand"
                    >
                      {item}
                    </button>
                  ))}
                </div>
              </Card>
            </div>
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}
