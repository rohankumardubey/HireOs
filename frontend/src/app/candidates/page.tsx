"use client";

import Link from "next/link";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { useAuth } from "@/hooks/use-auth";
import { api } from "@/lib/api";
import { titleCase } from "@/lib/utils";

export default function CandidatesPage() {
  const auth = useAuth();
  const [parsedResult, setParsedResult] = useState<Record<string, unknown> | null>(null);
  const candidates = useQuery({
    queryKey: ["candidates", auth.token],
    queryFn: () => api.getCandidates(auth.token as string),
    enabled: Boolean(auth.token),
  });

  const uploadMutation = useMutation({
    mutationFn: async (formData: FormData) => api.uploadResume(auth.token as string, formData),
    onSuccess: (data) => {
      setParsedResult(data.parsed_resume);
      candidates.refetch();
    },
  });

  return (
    <AppShell
      title="Candidate Pipeline"
      subtitle="Upload resumes, capture parsed candidate profiles, and route applicants into AI-assisted matching and interviews."
    >
      <div className="grid gap-4 lg:grid-cols-[0.95fr_1.05fr]">
        <Card>
          <h3 className="font-display text-2xl font-semibold text-text">Upload resume</h3>
          <p className="mt-3 text-sm leading-7 text-muted">
            PDF, DOCX, and TXT are supported. HireOS extracts structured fields and stores raw plus parsed resume data.
          </p>
          <form
            className="mt-6 space-y-4"
            onSubmit={(event) => {
              event.preventDefault();
              const formData = new FormData(event.currentTarget);
              uploadMutation.mutate(formData);
            }}
          >
            <input
              name="name"
              placeholder="Candidate name"
              className="w-full rounded-2xl border border-border bg-white/80 px-4 py-3 outline-none"
            />
            <input
              name="email"
              placeholder="Candidate email"
              className="w-full rounded-2xl border border-border bg-white/80 px-4 py-3 outline-none"
            />
            <input
              name="location"
              placeholder="Location"
              className="w-full rounded-2xl border border-border bg-white/80 px-4 py-3 outline-none"
            />
            <input
              type="file"
              name="file"
              accept=".pdf,.docx,.txt"
              className="w-full rounded-2xl border border-border bg-white/80 px-4 py-3"
              required
            />
            {uploadMutation.error ? (
              <p className="text-sm text-rose-700">{uploadMutation.error.message}</p>
            ) : null}
            <button
              type="submit"
              disabled={uploadMutation.isPending}
              className="rounded-full bg-brand px-6 py-3 text-sm font-semibold text-white disabled:opacity-60"
            >
              {uploadMutation.isPending ? "Uploading..." : "Upload and parse"}
            </button>
          </form>
          {parsedResult ? (
            <div className="mt-6 rounded-[24px] bg-brand-soft/60 px-4 py-4">
              <p className="text-sm font-semibold text-brand">Parsed skills</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {((parsedResult.skills as string[]) || []).map((skill) => (
                  <Badge key={skill} tone="brand">
                    {skill}
                  </Badge>
                ))}
              </div>
            </div>
          ) : null}
        </Card>

        <Card>
          <div className="flex items-center justify-between">
            <h3 className="font-display text-2xl font-semibold text-text">Candidates</h3>
            <Badge tone="neutral">{candidates.data?.length || 0} total</Badge>
          </div>
          <div className="mt-5 space-y-3">
            {candidates.data?.map((candidate) => (
              <Link
                key={candidate.id}
                href={`/candidates/${candidate.id}`}
                className="block rounded-[24px] border border-border bg-white/70 px-4 py-4"
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="font-semibold text-text">{candidate.name}</p>
                    <p className="mt-1 text-sm text-muted">
                      {candidate.current_role || "Candidate"} · {candidate.years_experience} yrs
                    </p>
                  </div>
                  <Badge tone={candidate.status?.includes("review") ? "warning" : "brand"}>
                    {titleCase(candidate.status)}
                  </Badge>
                </div>
                <p className="mt-3 text-sm leading-6 text-muted">
                  {candidate.profile_summary || "Resume parsed and ready for matching."}
                </p>
              </Link>
            ))}
          </div>
        </Card>
      </div>
    </AppShell>
  );
}
