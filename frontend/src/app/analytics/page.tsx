"use client";

import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { AppShell } from "@/components/layout/app-shell";
import { Card } from "@/components/ui/card";
import { useAuth } from "@/hooks/use-auth";
import { api } from "@/lib/api";

const colors = ["#135d66", "#ec8f5e", "#f4b55f", "#7bb284", "#56667c"];

export default function AnalyticsPage() {
  const auth = useAuth();
  const overview = useQuery({
    queryKey: ["overview", auth.token],
    queryFn: () => api.getAnalyticsOverview(auth.token as string),
    enabled: Boolean(auth.token),
  });
  const funnel = useQuery({
    queryKey: ["funnel", auth.token],
    queryFn: () => api.getAnalyticsFunnel(auth.token as string),
    enabled: Boolean(auth.token),
  });
  const modelQuality = useQuery({
    queryKey: ["model-quality", auth.token],
    queryFn: () => api.getModelQuality(auth.token as string),
    enabled: Boolean(auth.token),
  });

  return (
    <AppShell
      title="Analytics"
      subtitle="Monitor hiring funnel health, AI quality, and the human-review posture behind every recommendation."
    >
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="h-[360px]">
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">Pipeline funnel</p>
          <div className="mt-6 h-[260px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={funnel.data?.stages || []}>
                <CartesianGrid strokeDasharray="3 3" stroke="#d9deeb" />
                <XAxis dataKey="stage" tick={{ fontSize: 12 }} />
                <YAxis />
                <Tooltip />
                <Bar dataKey="count" radius={[12, 12, 0, 0]} fill="#135d66" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card className="h-[360px]">
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">Review distribution</p>
          <div className="mt-6 h-[260px]">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={[
                    {
                      name: "Human review required",
                      value: overview.data?.candidates_requiring_human_review || 0,
                    },
                    {
                      name: "Shortlisted",
                      value: overview.data?.candidates_shortlisted || 0,
                    },
                    {
                      name: "Completed interviews",
                      value: overview.data?.interviews_completed || 0,
                    },
                  ]}
                  dataKey="value"
                  nameKey="name"
                  outerRadius={96}
                  innerRadius={54}
                >
                  {colors.map((color) => (
                    <Cell key={color} fill={color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>
      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        <Card>
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">Average answer score</p>
          <p className="mt-4 font-display text-5xl font-semibold text-text">
            {Math.round(modelQuality.data?.average_answer_score || 0)}%
          </p>
        </Card>
        <Card>
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">Recruiter overrides</p>
          <p className="mt-4 font-display text-5xl font-semibold text-text">
            {modelQuality.data?.override_rate || 0}
          </p>
        </Card>
        <Card>
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">Compliance note</p>
          <p className="mt-4 text-sm leading-7 text-muted">
            {modelQuality.data?.compliance_note}
          </p>
        </Card>
      </div>
    </AppShell>
  );
}

