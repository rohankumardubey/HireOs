"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { useAuth } from "@/hooks/use-auth";
import { api } from "@/lib/api";
import { formatScore, titleCase } from "@/lib/utils";

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
  const ranking = useQuery({
    queryKey: ["ranking", auth.token, activeJobId],
    queryFn: () => api.getJobRanking(auth.token as string, activeJobId),
    enabled: Boolean(auth.token && activeJobId),
  });

  return (
    <AppShell
      title="Candidate Ranking"
      subtitle="Blend resume alignment, interview performance, skills coverage, and recruiter overrides into a transparent shortlist."
    >
      <Card>
        <label className="block max-w-sm">
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
        <div className="mt-6 space-y-3">
          {ranking.data?.map((item) => (
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
          ))}
        </div>
      </Card>
    </AppShell>
  );
}

