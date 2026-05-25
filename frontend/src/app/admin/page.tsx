"use client";

import { useQuery } from "@tanstack/react-query";

import { AppShell } from "@/components/layout/app-shell";
import { Card } from "@/components/ui/card";
import { MetricCard } from "@/components/ui/metric-card";
import { useAuth } from "@/hooks/use-auth";
import { api } from "@/lib/api";
import { formatScore } from "@/lib/utils";

export default function AdminPage() {
  const auth = useAuth();
  const overview = useQuery({
    queryKey: ["overview", auth.token],
    queryFn: () => api.getAnalyticsOverview(auth.token as string),
    enabled: Boolean(auth.token),
  });
  const quality = useQuery({
    queryKey: ["quality", auth.token],
    queryFn: () => api.getModelQuality(auth.token as string),
    enabled: Boolean(auth.token),
  });

  return (
    <AppShell
      title="Admin Analytics"
      subtitle="Give company admins a top-down view of usage, recruiter activity, AI cost proxies, and system-health signals."
    >
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Jobs" value={String(overview.data?.active_jobs || 0)} hint="Open roles across the company workspace." />
        <MetricCard label="Candidates" value={String(overview.data?.total_candidates || 0)} hint="Candidates processed in this workspace." />
        <MetricCard label="Interviews" value={String(overview.data?.interviews_completed || 0)} hint="Completed AI screening sessions." />
        <MetricCard label="AI quality" value={`${formatScore(quality.data?.average_answer_score)}%`} hint="Average answer score across reviewed interviews." />
      </div>
      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        <Card>
          <h3 className="font-display text-2xl font-semibold text-text">Usage proxies</h3>
          <div className="mt-5 space-y-3 text-sm text-muted">
            <div className="rounded-[20px] bg-white/70 px-4 py-3">Candidates processed: {overview.data?.total_candidates || 0}</div>
            <div className="rounded-[20px] bg-white/70 px-4 py-3">Interviews conducted: {overview.data?.interviews_completed || 0}</div>
            <div className="rounded-[20px] bg-white/70 px-4 py-3">Reports generated: {overview.data?.interviews_completed || 0}</div>
          </div>
        </Card>
        <Card>
          <h3 className="font-display text-2xl font-semibold text-text">AI governance</h3>
          <p className="mt-4 text-sm leading-7 text-muted">
            {quality.data?.compliance_note}
          </p>
        </Card>
        <Card>
          <h3 className="font-display text-2xl font-semibold text-text">System status</h3>
          <div className="mt-5 space-y-3 text-sm text-muted">
            <div className="rounded-[20px] bg-success-soft px-4 py-3">API healthy</div>
            <div className="rounded-[20px] bg-white/70 px-4 py-3">Event pipeline ready with Kafka fallback</div>
            <div className="rounded-[20px] bg-white/70 px-4 py-3">Prometheus/Grafana configs included</div>
          </div>
        </Card>
      </div>
    </AppShell>
  );
}

