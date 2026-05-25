"use client";

import Link from "next/link";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";

import { AppShell } from "@/components/layout/app-shell";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { useAuth } from "@/hooks/use-auth";
import { api } from "@/lib/api";
import { formatScore, titleCase } from "@/lib/utils";

export default function JobDetailPage() {
  const auth = useAuth();
  const params = useParams<{ jobId: string }>();
  const jobId = params.jobId;
  const job = useQuery({
    queryKey: ["job", auth.token, jobId],
    queryFn: () => api.getJob(auth.token as string, jobId),
    enabled: Boolean(auth.token && jobId),
  });
  const candidates = useQuery({
    queryKey: ["job-candidates", auth.token, jobId],
    queryFn: () => api.getJobCandidates(auth.token as string, jobId),
    enabled: Boolean(auth.token && jobId),
  });
  const ranking = useQuery({
    queryKey: ["job-ranking", auth.token, jobId],
    queryFn: () => api.getJobRanking(auth.token as string, jobId),
    enabled: Boolean(auth.token && jobId),
  });
  const parseMutation = useMutation({
    mutationFn: () => api.parseJob(auth.token as string, jobId),
    onSuccess: () => {
      job.refetch();
    },
  });

  return (
    <AppShell
      title={job.data?.title || "Job detail"}
      subtitle="Review structured JD analysis, see matched candidates, and monitor how AI ranking aligns with recruiter review."
      actions={
        <button
          type="button"
          onClick={() => parseMutation.mutate()}
          className="rounded-full bg-brand px-5 py-3 text-sm font-semibold text-white"
        >
          Re-parse JD
        </button>
      }
    >
      <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
        <Card>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="success">{titleCase(job.data?.status || "draft")}</Badge>
            <Badge tone="brand">{job.data?.work_mode || "remote"}</Badge>
            <Badge tone="neutral">{job.data?.experience_range || "Flexible"}</Badge>
          </div>
          <p className="mt-5 text-sm leading-7 text-muted">{job.data?.job_description}</p>
          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">
                Required skills
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {(job.data?.jd_analysis.required_skills || []).map((skill) => (
                  <Badge key={skill} tone="brand">
                    {skill}
                  </Badge>
                ))}
              </div>
            </div>
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">
                Focus areas
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {(job.data?.jd_analysis.interview_focus_areas || []).map((skill) => (
                  <Badge key={skill} tone="neutral">
                    {skill}
                  </Badge>
                ))}
              </div>
            </div>
          </div>
        </Card>
        <Card>
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">
            Ranked shortlist
          </p>
          <div className="mt-5 space-y-3">
            {ranking.data?.slice(0, 5).map((item) => (
              <Link
                key={item.candidate_id}
                href={`/candidates/${item.candidate_id}`}
                className="block rounded-[24px] border border-border bg-white/70 px-4 py-4"
              >
                <div className="flex items-center justify-between">
                  <p className="font-semibold text-text">
                    #{item.rank} {item.candidate_name}
                  </p>
                  <Badge tone={item.final_score >= 70 ? "success" : "warning"}>
                    {formatScore(item.final_score)}%
                  </Badge>
                </div>
                <p className="mt-2 text-sm text-muted">
                  Match {formatScore(item.match_score)} · Interview {formatScore(item.interview_score)} · {titleCase(item.ai_recommendation)}
                </p>
              </Link>
            ))}
          </div>
        </Card>
      </div>

      <Card className="mt-6">
        <div className="flex items-center justify-between">
          <h3 className="font-display text-2xl font-semibold text-text">Matched candidates</h3>
          <Link href="/candidates" className="text-sm font-semibold text-brand">
            Upload more candidates
          </Link>
        </div>
        <div className="mt-5 space-y-3">
          {candidates.data?.map((row) => {
            const candidate = row.candidate as { id: string; name: string; status: string; email: string };
            const match = row.match as { score: number; recommendation: string; human_review_required: boolean };
            return (
              <Link
                key={candidate.id}
                href={`/candidates/${candidate.id}`}
                className="grid gap-3 rounded-[24px] border border-border bg-white/70 px-4 py-4 md:grid-cols-[1.4fr_0.8fr_0.8fr_0.8fr]"
              >
                <div>
                  <p className="font-semibold text-text">{candidate.name}</p>
                  <p className="mt-1 text-sm text-muted">{candidate.email}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-muted-soft">Match</p>
                  <p className="mt-1 font-semibold text-text">{formatScore(match.score)}%</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-muted-soft">AI view</p>
                  <p className="mt-1 font-semibold text-text">{titleCase(match.recommendation)}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-muted-soft">Status</p>
                  <p className="mt-1 font-semibold text-text">{titleCase(candidate.status)}</p>
                </div>
              </Link>
            );
          })}
          {!candidates.data?.length ? (
            <div className="rounded-[24px] border border-dashed border-border px-4 py-6 text-sm text-muted">
              No candidates have been matched to this role yet.
            </div>
          ) : null}
        </div>
      </Card>
    </AppShell>
  );
}
