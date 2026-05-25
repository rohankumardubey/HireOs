"use client";

import Link from "next/link";
import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { Card } from "@/components/ui/card";
import { persistSession } from "@/hooks/use-auth";
import { api } from "@/lib/api";

export default function SignupPage() {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [form, setForm] = useState({
    full_name: "Jordan Recruiter",
    email: "jordan@newco.ai",
    password: "Demo@123",
    company_name: "NewCo Talent",
    role: "admin",
  });

  const mutation = useMutation({
    mutationFn: api.signup,
    onSuccess: (data) => {
      persistSession(data.user, data.access_token);
      startTransition(() => router.push("/dashboard"));
    },
  });

  const googleMutation = useMutation({
    mutationFn: () =>
      api.startGoogleAuth({
        flow: "signup",
        company_name: form.company_name,
        full_name: form.full_name,
        role: form.role,
      }),
    onSuccess: (data) => {
      window.location.href = data.authorization_url;
    },
  });

  return (
    <div className="flex min-h-screen items-center justify-center px-5 py-8">
      <Card className="w-full max-w-2xl p-8">
        <h1 className="font-display text-4xl font-semibold text-text">
          Create your HireOS AI workspace
        </h1>
        <p className="mt-3 text-sm text-muted">
          Start with Google in one click or create a password-based demo workspace.
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
          <p className="text-sm text-muted">
            HireOS will use your Google identity for sign-in and create the initial workspace from the company name below.
          </p>
          <div className="relative py-1 text-center text-xs uppercase tracking-[0.24em] text-muted">
            <span className="bg-surface px-3">or use email and password</span>
            <div className="absolute left-0 top-1/2 -z-10 h-px w-full -translate-y-1/2 bg-border" />
          </div>
        </div>
        <form
          className="mt-4 grid gap-4 md:grid-cols-2"
          onSubmit={(event) => {
            event.preventDefault();
            mutation.mutate(form);
          }}
        >
          {[
            ["full_name", "Full name"],
            ["email", "Work email"],
            ["company_name", "Company"],
            ["password", "Password"],
          ].map(([key, label]) => (
            <label key={key} className={key === "company_name" ? "md:col-span-2" : ""}>
              <span className="text-sm font-medium text-muted">{label}</span>
              <input
                type={key === "password" ? "password" : "text"}
                className="mt-2 w-full rounded-2xl border border-border bg-white/80 px-4 py-3 outline-none"
                value={form[key as keyof typeof form]}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    [key]: event.target.value,
                  }))
                }
              />
            </label>
          ))}
          {googleMutation.error ? (
            <p className="md:col-span-2 text-sm text-rose-700">
              {googleMutation.error.message}
            </p>
          ) : null}
          {mutation.error ? (
            <p className="md:col-span-2 text-sm text-rose-700">
              {mutation.error.message}
            </p>
          ) : null}
          <button
            type="submit"
            disabled={mutation.isPending || isPending}
            className="md:col-span-2 rounded-full bg-brand px-6 py-3 text-sm font-semibold text-white disabled:opacity-60"
          >
            {mutation.isPending || isPending ? "Creating workspace..." : "Create workspace"}
          </button>
        </form>
        <p className="mt-5 text-sm text-muted">
          Already have an account?{" "}
          <Link href="/login" className="font-semibold text-brand">
            Sign in
          </Link>
        </p>
      </Card>
    </div>
  );
}
