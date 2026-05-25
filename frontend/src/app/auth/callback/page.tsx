"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useTransition } from "react";
import { useMutation } from "@tanstack/react-query";

import { Card } from "@/components/ui/card";
import { persistSession } from "@/hooks/use-auth";
import { api } from "@/lib/api";

export default function AuthCallbackPage() {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  const params = useMemo(
    () => (typeof window === "undefined" ? null : new URLSearchParams(window.location.search)),
    [],
  );
  const code = params?.get("code");
  const errorMessage = !code ? "Google sign-in did not return a complete session." : null;

  const exchangeMutation = useMutation({
    mutationFn: (exchangeCode: string) => api.exchangeGoogleAuth({ code: exchangeCode }),
    onSuccess: (data) => {
      persistSession(data.user, data.access_token);
      startTransition(() => router.replace("/dashboard"));
    },
    onError: () => {
      router.replace("/login?auth=error&message=Google%20sign-in%20could%20not%20be%20completed.");
    },
  });
  const exchangePending = exchangeMutation.isPending;
  const exchangeSuccess = exchangeMutation.isSuccess;
  const runExchange = exchangeMutation.mutate;

  useEffect(() => {
    if (!params || !code || exchangePending || exchangeSuccess) {
      return;
    }
    runExchange(code);
  }, [code, exchangePending, exchangeSuccess, params, runExchange]);

  return (
    <div className="flex min-h-screen items-center justify-center px-5 py-8">
      <Card className="w-full max-w-xl p-8 text-center">
        <p className="text-sm uppercase tracking-[0.22em] text-brand">Google SSO</p>
        <h1 className="mt-4 font-display text-4xl font-semibold text-text">
          {errorMessage ? "We could not finish sign-in" : "Finishing your sign-in"}
        </h1>
        <p className="mt-4 text-sm text-muted">
          {errorMessage ||
            (exchangePending || isPending
              ? "Your workspace is ready. Redirecting to the recruiter dashboard now."
              : "Setting up your HireOS session and taking you into the app.")}
        </p>
      </Card>
    </div>
  );
}
