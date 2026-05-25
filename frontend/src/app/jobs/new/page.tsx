"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { Card } from "@/components/ui/card";
import { useAuth } from "@/hooks/use-auth";
import { api } from "@/lib/api";

export default function NewJobPage() {
  const auth = useAuth();
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [form, setForm] = useState({
    title: "Data Engineer",
    department: "Data Platform",
    location: "Remote",
    work_mode: "remote",
    experience_range: "4-8 years",
    employment_type: "full-time",
    salary_range: "$120k-$165k",
    status: "open",
    required_skills: "python, sql, kafka, airflow, data modeling",
    preferred_skills: "spark, aws, dbt",
    job_description:
      "Build Kafka, Spark, and lakehouse pipelines for hiring analytics. Requires Python, SQL, Airflow, Kafka, and data modeling. Partner with recruiters and analytics teams to improve quality metrics and scale workflows.",
  });

  const mutation = useMutation({
    mutationFn: () =>
      api.createJob(auth.token as string, {
        ...form,
        required_skills: form.required_skills.split(",").map((item) => item.trim()).filter(Boolean),
        preferred_skills: form.preferred_skills.split(",").map((item) => item.trim()).filter(Boolean),
      }),
    onSuccess: (job) => {
      startTransition(() => router.push(`/jobs/${job.id}`));
    },
  });

  return (
    <AppShell
      title="Create Job"
      subtitle="Seed a production-style req with structured metadata so downstream matching, interview generation, and ranking stay consistent."
    >
      <Card>
        <form
          className="grid gap-4 md:grid-cols-2"
          onSubmit={(event) => {
            event.preventDefault();
            mutation.mutate();
          }}
        >
          {[
            ["title", "Job title"],
            ["department", "Department"],
            ["location", "Location"],
            ["experience_range", "Experience range"],
            ["employment_type", "Employment type"],
            ["salary_range", "Salary range"],
          ].map(([key, label]) => (
            <label key={key}>
              <span className="text-sm font-medium text-muted">{label}</span>
              <input
                className="mt-2 w-full rounded-2xl border border-border bg-white/80 px-4 py-3 outline-none"
                value={form[key as keyof typeof form]}
                onChange={(event) =>
                  setForm((current) => ({ ...current, [key]: event.target.value }))
                }
              />
            </label>
          ))}
          <label>
            <span className="text-sm font-medium text-muted">Work mode</span>
            <select
              className="mt-2 w-full rounded-2xl border border-border bg-white/80 px-4 py-3 outline-none"
              value={form.work_mode}
              onChange={(event) =>
                setForm((current) => ({ ...current, work_mode: event.target.value }))
              }
            >
              <option value="remote">Remote</option>
              <option value="hybrid">Hybrid</option>
              <option value="onsite">Onsite</option>
            </select>
          </label>
          <label>
            <span className="text-sm font-medium text-muted">Status</span>
            <select
              className="mt-2 w-full rounded-2xl border border-border bg-white/80 px-4 py-3 outline-none"
              value={form.status}
              onChange={(event) =>
                setForm((current) => ({ ...current, status: event.target.value }))
              }
            >
              <option value="draft">Draft</option>
              <option value="open">Open</option>
              <option value="closed">Closed</option>
            </select>
          </label>
          <label className="md:col-span-2">
            <span className="text-sm font-medium text-muted">Required skills</span>
            <input
              className="mt-2 w-full rounded-2xl border border-border bg-white/80 px-4 py-3 outline-none"
              value={form.required_skills}
              onChange={(event) =>
                setForm((current) => ({ ...current, required_skills: event.target.value }))
              }
            />
          </label>
          <label className="md:col-span-2">
            <span className="text-sm font-medium text-muted">Preferred skills</span>
            <input
              className="mt-2 w-full rounded-2xl border border-border bg-white/80 px-4 py-3 outline-none"
              value={form.preferred_skills}
              onChange={(event) =>
                setForm((current) => ({ ...current, preferred_skills: event.target.value }))
              }
            />
          </label>
          <label className="md:col-span-2">
            <span className="text-sm font-medium text-muted">Job description</span>
            <textarea
              rows={8}
              className="mt-2 w-full rounded-[24px] border border-border bg-white/80 px-4 py-3 outline-none"
              value={form.job_description}
              onChange={(event) =>
                setForm((current) => ({ ...current, job_description: event.target.value }))
              }
            />
          </label>
          {mutation.error ? (
            <p className="md:col-span-2 text-sm text-rose-700">{mutation.error.message}</p>
          ) : null}
          <button
            type="submit"
            disabled={mutation.isPending || isPending}
            className="md:col-span-2 rounded-full bg-brand px-6 py-3 text-sm font-semibold text-white disabled:opacity-60"
          >
            {mutation.isPending || isPending ? "Creating..." : "Create role"}
          </button>
        </form>
      </Card>
    </AppShell>
  );
}

