"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { AppShell } from "@/components/layout/app-shell";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { useAuth } from "@/hooks/use-auth";
import { api } from "@/lib/api";

export default function ReportsPage() {
  const auth = useAuth();
  const reports = useQuery({
    queryKey: ["reports", auth.token],
    queryFn: () => api.getReports(auth.token as string),
    enabled: Boolean(auth.token),
  });

  return (
    <AppShell
      title="Interview Reports"
      subtitle="Open AI-generated interview reports with skill-level evidence, gap summaries, and an explicit human-review posture."
    >
      <div className="grid gap-4 lg:grid-cols-2">
        {reports.data?.map((report) => (
          <Card key={report.id}>
            <div className="flex items-center justify-between">
              <h3 className="font-display text-2xl font-semibold text-text">
                Report {report.id.slice(0, 8)}
              </h3>
              <Badge tone={report.human_review_required ? "warning" : "success"}>
                {report.human_review_required ? "Human review required" : "Ready"}
              </Badge>
            </div>
            <p className="mt-4 text-sm leading-7 text-muted">
              Recommended next step: {report.recommended_next_step}
            </p>
            <Link
              href={`/reports/${report.id}`}
              className="mt-6 inline-flex rounded-full bg-brand px-5 py-3 text-sm font-semibold text-white"
            >
              Open report
            </Link>
          </Card>
        ))}
        {!reports.data?.length ? (
          <Card>
            <p className="text-sm text-muted">
              No interview reports yet. Invite a candidate to an AI interview and complete the flow to generate one.
            </p>
          </Card>
        ) : null}
      </div>
    </AppShell>
  );
}

