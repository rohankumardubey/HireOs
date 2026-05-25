"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";

import { AppShell } from "@/components/layout/app-shell";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { useAuth } from "@/hooks/use-auth";
import { api } from "@/lib/api";

export default function ReportDetailPage() {
  const auth = useAuth();
  const params = useParams<{ reportId: string }>();
  const reportId = params.reportId;
  const report = useQuery({
    queryKey: ["report", auth.token, reportId],
    queryFn: () => api.getReport(auth.token as string, reportId),
    enabled: Boolean(auth.token && reportId),
  });

  return (
    <AppShell
      title="Interview Report"
      subtitle="Review AI evidence, compliance notes, strengths, gaps, and recruiter-oriented next-step recommendations."
    >
      <Card>
        <div className="flex items-center justify-between">
          <h3 className="font-display text-3xl font-semibold text-text">Report {reportId.slice(0, 8)}</h3>
          <Badge tone={report.data?.human_review_required ? "warning" : "success"}>
            {report.data?.human_review_required ? "Human review required" : "Ready"}
          </Badge>
        </div>
        <div className="mt-6 rounded-[24px] bg-[#15222d] p-5 text-sm leading-7 text-slate-200">
          <pre className="overflow-x-auto whitespace-pre-wrap">{report.data?.report_markdown}</pre>
        </div>
      </Card>
    </AppShell>
  );
}

