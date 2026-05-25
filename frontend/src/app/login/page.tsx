"use client";

import Link from "next/link";
import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useMemo, useState, useTransition } from "react";

import { Card } from "@/components/ui/card";
import { persistSession } from "@/hooks/use-auth";
import { api } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [form, setForm] = useState({
    email: "recruiter1@hireos.ai",
    password: "Demo@123",
  });

  const callbackParams = useMemo(
    () => (typeof window === "undefined" ? null : new URLSearchParams(window.location.search)),
    [],
  );
  const oauthMessage =
    callbackParams?.get("auth") === "error"
      ? callbackParams.get("message") || "Google sign-in could not be completed."
      : null;

  const mutation = useMutation({
    mutationFn: api.login,
    onSuccess: (data) => {
      persistSession(data.user, data.access_token);
      startTransition(() => router.push("/dashboard"));
    },
  });

  const googleMutation = useMutation({
    mutationFn: () => api.startGoogleAuth({ flow: "login" }),
    onSuccess: (data) => {
      window.location.href = data.authorization_url;
    },
  });

  return (
    <div className="flex min-h-screen items-center justify-center px-5 py-8">
      <div className="grid w-full max-w-6xl gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <Card className="bg-[#15222d] text-white">
          <p className="text-sm uppercase tracking-[0.22em] text-slate-400">
            Demo credentials
          </p>
          <h1 className="mt-5 font-display text-5xl font-semibold">
            Recruiters stay in control while AI handles the heavy screening lift.
          </h1>
          <div className="mt-8 grid gap-4 md:grid-cols-2">
            {[
              { role: "Recruiter", email: "recruiter1@hireos.ai", password: "Demo@123" },
              { role: "Admin", email: "admin@hireos.ai", password: "Demo@123" },
            ].map((item) => (
              <div key={item.role} className="rounded-[24px] border border-white/10 bg-white/6 p-4">
                <p className="text-sm font-semibold text-white">{item.role}</p>
                <p className="mt-3 text-sm text-slate-300">{item.email}</p>
                <p className="mt-1 text-sm text-slate-300">{item.password}</p>
              </div>
            ))}
          </div>
        </Card>
        <Card className="p-8">
          <h2 className="font-display text-4xl font-semibold text-text">Login</h2>
          <p className="mt-3 text-sm text-muted">
            Open the seeded recruiter dashboard or continue with Google without managing a local password.
          </p>
          <div className="mt-8 space-y-4">
            <button
              type="button"
              disabled={googleMutation.isPending}
              onClick={() => googleMutation.mutate()}
              className="flex w-full items-center justify-center gap-3 rounded-full border border-border bg-white px-6 py-3 text-sm font-semibold text-text shadow-soft transition hover:border-brand/40 disabled:opacity-60"
            >
              <span className="text-base">G</span>
              {googleMutation.isPending ? "Redirecting to Google..." : "Continue with Google"}
            </button>
            <div className="relative py-1 text-center text-xs uppercase tracking-[0.24em] text-muted">
              <span className="bg-surface px-3">or use demo login</span>
              <div className="absolute left-0 top-1/2 -z-10 h-px w-full -translate-y-1/2 bg-border" />
            </div>
          </div>
          <form
            className="mt-4 space-y-4"
            onSubmit={(event) => {
              event.preventDefault();
              mutation.mutate(form);
            }}
          >
            <label className="block">
              <span className="text-sm font-medium text-muted">Work email</span>
              <input
                className="mt-2 w-full rounded-2xl border border-border bg-white/80 px-4 py-3 outline-none"
                value={form.email}
                onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))}
              />
            </label>
            <label className="block">
              <span className="text-sm font-medium text-muted">Password</span>
              <input
                type="password"
                className="mt-2 w-full rounded-2xl border border-border bg-white/80 px-4 py-3 outline-none"
                value={form.password}
                onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
              />
            </label>
            {oauthMessage ? <p className="text-sm text-rose-700">{oauthMessage}</p> : null}
            {googleMutation.error ? (
              <p className="text-sm text-rose-700">{googleMutation.error.message}</p>
            ) : null}
            {mutation.error ? <p className="text-sm text-rose-700">{mutation.error.message}</p> : null}
            <button
              type="submit"
              disabled={mutation.isPending || isPending}
              className="w-full rounded-full bg-brand px-6 py-3 text-sm font-semibold text-white disabled:opacity-60"
            >
              {mutation.isPending || isPending ? "Signing in..." : "Sign in"}
            </button>
          </form>
          <p className="mt-5 text-sm text-muted">
            Need a new workspace?{" "}
            <Link href="/signup" className="font-semibold text-brand">
              Create account
            </Link>
          </p>
        </Card>
      </div>
    </div>
  );
}
