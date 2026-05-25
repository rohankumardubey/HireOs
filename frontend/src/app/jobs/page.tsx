"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { AppShell } from "@/components/layout/app-shell";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { useAuth } from "@/hooks/use-auth";
import { api } from "@/lib/api";
import { titleCase } from "@/lib/utils";

export default function JobsPage() {
  const auth = useAuth();
  const jobs = useQuery({
    queryKey: ["jobs", auth.token],
    queryFn: () => api.getJobs(auth.token as string),
    enabled: Boolean(auth.token),
  });

  return (
    <AppShell
      title="Job Openings"
      subtitle="Create and manage reqs, parse job descriptions into structured skill requirements, and compare ranked candidates role by role."
      actions={
        <Link href="/jobs/new" className="rounded-full bg-brand px-5 py-3 text-sm font-semibold text-white">
          New job opening
        </Link>
      }
    >
      <div className="grid gap-4 xl:grid-cols-2">
        {jobs.data?.map((job) => (
          <Card key={job.id}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm uppercase tracking-[0.22em] text-brand">{job.department || "Talent"}</p>
                <h3 className="mt-2 font-display text-3xl font-semibold text-text">{job.title}</h3>
                <p className="mt-3 text-sm leading-7 text-muted">
                  {job.job_description.slice(0, 180)}...
                </p>
              </div>
              <Badge tone={job.status === "open" ? "success" : "neutral"}>
                {titleCase(job.status)}
              </Badge>
            </div>
            <div className="mt-5 flex flex-wrap gap-2">
              {(job.jd_analysis.required_skills || []).slice(0, 5).map((skill) => (
                <Badge key={skill} tone="brand">
                  {skill}
                </Badge>
              ))}
            </div>
            <div className="mt-6 flex gap-3">
              <Link href={`/jobs/${job.id}`} className="rounded-full bg-brand px-5 py-3 text-sm font-semibold text-white">
                Open detail
              </Link>
              <button className="rounded-full border border-border bg-white/70 px-5 py-3 text-sm font-semibold text-text">
                {job.location || "Flexible"} · {job.work_mode}
              </button>
            </div>
          </Card>
        ))}
      </div>
    </AppShell>
  );
}

