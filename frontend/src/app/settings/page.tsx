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
  const atsStatus = useQuery({
    queryKey: ["ats-webhook-status", auth.token],
    queryFn: () => api.getATSWebhookStatus(auth.token as string),
    enabled: Boolean(auth.token),
  });

  const [form, setForm] = useState({
    industry: "HR Tech",
    size_band: "51-200",
  });
  const [atsForm, setATSForm] = useState({
    enabled: false,
    provider_label: "Greenhouse",
    endpoint_url: "",
    auth_token: "",
    signing_secret: "",
    export_stages: ["shortlisted", "moved_to_next_round", "hired"],
  });
  const [atsFormDirty, setATSFormDirty] = useState(false);

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
  const saveATSWebhook = useMutation({
    mutationFn: () =>
      api.updateATSWebhook(auth.token as string, {
        enabled: visibleATSForm.enabled,
        provider_label: visibleATSForm.provider_label,
        endpoint_url: visibleATSForm.endpoint_url || null,
        auth_token: visibleATSForm.auth_token || null,
        signing_secret: visibleATSForm.signing_secret || null,
        export_stages: visibleATSForm.export_stages,
      }),
    onSuccess: (result) => {
      setATSForm({
        enabled: result.enabled,
        provider_label: result.provider_label,
        endpoint_url: result.endpoint_url || "",
        auth_token: "",
        signing_secret: "",
        export_stages: result.export_stages,
      });
      setATSFormDirty(false);
      atsStatus.refetch();
    },
  });
  const testATSWebhook = useMutation({
    mutationFn: () => api.testATSWebhook(auth.token as string),
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
  const visibleATSForm =
    atsFormDirty || !atsStatus.data
      ? atsForm
      : {
          ...atsForm,
          enabled: atsStatus.data.enabled,
          provider_label: atsStatus.data.provider_label || atsForm.provider_label,
          endpoint_url: atsStatus.data.endpoint_url || "",
          export_stages: atsStatus.data.export_stages?.length ? atsStatus.data.export_stages : atsForm.export_stages,
        };

  function toggleExportStage(stage: string) {
    setATSFormDirty(true);
    const exists = visibleATSForm.export_stages.includes(stage);
    setATSForm({
      ...visibleATSForm,
      export_stages: exists
        ? visibleATSForm.export_stages.filter((value) => value !== stage)
        : [...visibleATSForm.export_stages, stage],
    });
  }

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
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="font-display text-2xl font-semibold text-text">ATS webhook export</h3>
                <p className="mt-3 text-sm leading-7 text-muted">
                  Send recruiter-approved shortlist decisions into Greenhouse, Lever, or any internal hiring system using a signed webhook payload.
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge tone={atsStatus.data?.configured ? "success" : "warning"}>
                  {atsStatus.data?.configured ? "Configured" : "Not configured"}
                </Badge>
                <Badge tone={atsStatus.data?.enabled ? "success" : "neutral"}>
                  {atsStatus.data?.enabled ? "Enabled" : "Disabled"}
                </Badge>
              </div>
            </div>
            <div className="mt-5 space-y-4">
              <label className="block">
                <span className="text-sm font-medium text-muted">Provider label</span>
                <input
                  className="mt-2 w-full rounded-2xl border border-border bg-white/80 px-4 py-3 outline-none"
                  value={visibleATSForm.provider_label}
                  onChange={(event) => {
                    setATSFormDirty(true);
                    setATSForm({ ...visibleATSForm, provider_label: event.target.value });
                  }}
                />
              </label>
              <label className="block">
                <span className="text-sm font-medium text-muted">Webhook endpoint URL</span>
                <input
                  className="mt-2 w-full rounded-2xl border border-border bg-white/80 px-4 py-3 outline-none"
                  placeholder="https://hooks.example-ats.com/hireos/candidates"
                  value={visibleATSForm.endpoint_url}
                  onChange={(event) => {
                    setATSFormDirty(true);
                    setATSForm({ ...visibleATSForm, endpoint_url: event.target.value });
                  }}
                />
              </label>
              <label className="block">
                <span className="text-sm font-medium text-muted">Bearer token header</span>
                <input
                  className="mt-2 w-full rounded-2xl border border-border bg-white/80 px-4 py-3 outline-none"
                  placeholder={atsStatus.data?.has_auth_token ? "Stored. Enter a new one to rotate or leave blank to keep it." : "Optional"}
                  value={visibleATSForm.auth_token}
                  onChange={(event) => {
                    setATSFormDirty(true);
                    setATSForm({ ...visibleATSForm, auth_token: event.target.value });
                  }}
                />
              </label>
              <label className="block">
                <span className="text-sm font-medium text-muted">Signing secret</span>
                <input
                  className="mt-2 w-full rounded-2xl border border-border bg-white/80 px-4 py-3 outline-none"
                  placeholder={atsStatus.data?.has_signing_secret ? "Stored. Enter a new one to rotate or leave blank to keep it." : "Optional"}
                  value={visibleATSForm.signing_secret}
                  onChange={(event) => {
                    setATSFormDirty(true);
                    setATSForm({ ...visibleATSForm, signing_secret: event.target.value });
                  }}
                />
              </label>
              <label className="flex items-start gap-3 rounded-[20px] border border-border bg-surface-elevated px-4 py-3 text-sm text-muted">
                <input
                  type="checkbox"
                  className="mt-1 h-4 w-4"
                  checked={visibleATSForm.enabled}
                  onChange={(event) => {
                    setATSFormDirty(true);
                    setATSForm({ ...visibleATSForm, enabled: event.target.checked });
                  }}
                />
                <span>
                  Enable automatic ATS export when recruiters move candidates into approved downstream stages.
                </span>
              </label>
              <div>
                <p className="text-sm font-medium text-muted">Auto-export stages</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {[
                    ["shortlisted", "Shortlisted"],
                    ["moved_to_next_round", "Next round"],
                    ["hired", "Hired"],
                  ].map(([value, label]) => (
                    <button
                      key={value}
                      type="button"
                      onClick={() => toggleExportStage(value)}
                      className={`rounded-full px-4 py-2 text-sm font-semibold ${
                        visibleATSForm.export_stages.includes(value)
                          ? "bg-brand text-white"
                          : "border border-border bg-white/70 text-text"
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={() => saveATSWebhook.mutate()}
                  disabled={saveATSWebhook.isPending}
                  className="rounded-full bg-brand px-5 py-3 text-sm font-semibold text-white disabled:opacity-60"
                >
                  {saveATSWebhook.isPending ? "Saving..." : "Save webhook config"}
                </button>
                <button
                  type="button"
                  onClick={() => testATSWebhook.mutate()}
                  disabled={!atsStatus.data?.configured || testATSWebhook.isPending}
                  className="rounded-full border border-border bg-white/70 px-5 py-3 text-sm font-semibold text-text disabled:opacity-60"
                >
                  {testATSWebhook.isPending ? "Sending..." : "Send test export"}
                </button>
              </div>
              {testATSWebhook.data ? (
                <div className="rounded-[20px] bg-white/70 px-4 py-3 text-sm text-muted">
                  Test export status: <span className="font-semibold text-text">{testATSWebhook.data.status}</span>
                </div>
              ) : null}
              <p className="text-sm leading-7 text-muted">
                HireOS only exports recruiter-approved downstream stages. AI recommendations and human-review notes are included for context, but recruiters stay in control of the final pipeline decision.
              </p>
            </div>
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
