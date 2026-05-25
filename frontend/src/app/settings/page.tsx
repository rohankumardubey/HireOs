"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { useAuth } from "@/hooks/use-auth";
import { api } from "@/lib/api";

export default function SettingsPage() {
  const auth = useAuth();
  const company = useQuery({
    queryKey: ["company", auth.token],
    queryFn: () => api.getCompany(auth.token as string),
    enabled: Boolean(auth.token),
  });
  const googleStatus = useQuery({
    queryKey: ["google-status", auth.token],
    queryFn: () => api.getGoogleIntegrationStatus(auth.token as string),
    enabled: Boolean(auth.token),
  });

  const [form, setForm] = useState({
    industry: "HR Tech",
    size_band: "51-200",
  });

  const mutation = useMutation({
    mutationFn: () => api.updateCompany(auth.token as string, form),
    onSuccess: () => company.refetch(),
  });
  const connectGoogle = useMutation({
    mutationFn: () => api.connectGoogle(auth.token as string),
    onSuccess: (result) => {
      window.location.href = result.authorization_url;
    },
  });
  const disconnectGoogle = useMutation({
    mutationFn: () => api.disconnectGoogle(auth.token as string),
    onSuccess: () => googleStatus.refetch(),
  });
  const callbackParams = useMemo(
    () =>
      typeof window === "undefined"
        ? null
        : new URLSearchParams(window.location.search),
    [],
  );

  const integrationBanner = useMemo(() => {
    const state = callbackParams?.get("google");
    if (state === "connected") {
      return `Google connected${callbackParams?.get("email") ? `: ${callbackParams.get("email")}` : ""}.`;
    }
    if (state === "error") {
      return callbackParams?.get("message") || "Google connection failed.";
    }
    return null;
  }, [callbackParams]);

  return (
    <AppShell
      title="Settings"
      subtitle="Manage company metadata, responsible AI defaults, and connected provider accounts used for scheduling and live interview workflows."
    >
      {integrationBanner ? (
        <div className="mb-4 rounded-[24px] border border-border bg-white/80 px-4 py-4 text-sm text-text">
          {integrationBanner}
        </div>
      ) : null}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <h3 className="font-display text-2xl font-semibold text-text">Company profile</h3>
          <p className="mt-3 text-sm text-muted">
            Workspace: {company.data?.name || "Loading"}
          </p>
          <div className="mt-6 space-y-4">
            <label className="block">
              <span className="text-sm font-medium text-muted">Industry</span>
              <input
                className="mt-2 w-full rounded-2xl border border-border bg-white/80 px-4 py-3 outline-none"
                value={form.industry}
                onChange={(event) => setForm((current) => ({ ...current, industry: event.target.value }))}
              />
            </label>
            <label className="block">
              <span className="text-sm font-medium text-muted">Size band</span>
              <input
                className="mt-2 w-full rounded-2xl border border-border bg-white/80 px-4 py-3 outline-none"
                value={form.size_band}
                onChange={(event) => setForm((current) => ({ ...current, size_band: event.target.value }))}
              />
            </label>
            <button
              type="button"
              onClick={() => mutation.mutate()}
              className="rounded-full bg-brand px-6 py-3 text-sm font-semibold text-white"
            >
              Save changes
            </button>
          </div>
        </Card>

        <div className="space-y-4">
          <Card>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="font-display text-2xl font-semibold text-text">Google Meet integration</h3>
                <p className="mt-3 text-sm leading-7 text-muted">
                  Connect a recruiter Google account so HireOS can auto-create Google Calendar events with Meet links for scheduled and ad hoc live interviews.
                </p>
              </div>
              <Badge tone={googleStatus.data?.connected ? "success" : "warning"}>
                {googleStatus.data?.connected ? "Connected" : "Not connected"}
              </Badge>
            </div>
            <div className="mt-5 space-y-3 text-sm text-muted">
              <div className="rounded-[20px] bg-white/70 px-4 py-3">
                Configured on server: {googleStatus.data?.configured ? "Yes" : "No"}
              </div>
              <div className="rounded-[20px] bg-white/70 px-4 py-3">
                Connected account: {googleStatus.data?.email || "None"}
              </div>
            </div>
            <div className="mt-5 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => connectGoogle.mutate()}
                disabled={!googleStatus.data?.configured || connectGoogle.isPending}
                className="rounded-full bg-brand px-5 py-3 text-sm font-semibold text-white disabled:opacity-60"
              >
                {googleStatus.data?.connected ? "Reconnect Google" : "Connect Google"}
              </button>
              {googleStatus.data?.connected ? (
                <button
                  type="button"
                  onClick={() => disconnectGoogle.mutate()}
                  disabled={disconnectGoogle.isPending}
                  className="rounded-full border border-border bg-white/70 px-5 py-3 text-sm font-semibold text-text disabled:opacity-60"
                >
                  Disconnect
                </button>
              ) : null}
            </div>
            {!googleStatus.data?.configured ? (
              <p className="mt-4 text-sm leading-7 text-muted">
                Add `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_OAUTH_REDIRECT_URI` to your environment before connecting Google.
              </p>
            ) : null}
          </Card>

          <Card>
            <h3 className="font-display text-2xl font-semibold text-text">Responsible AI defaults</h3>
            <div className="mt-5 space-y-4 text-sm leading-7 text-muted">
              <div className="rounded-[24px] bg-white/70 px-4 py-4">
                Recruiters can always override AI recommendations and record final decisions.
              </div>
              <div className="rounded-[24px] bg-white/70 px-4 py-4">
                Protected characteristics are excluded from matching and interview scoring logic.
              </div>
              <div className="rounded-[24px] bg-white/70 px-4 py-4">
                Event and audit records are retained for traceability, analytics, and model-quality review.
              </div>
            </div>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}
