"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { Card } from "@/components/ui/card";

export default function InterviewCompletePage() {
  const searchParams = useSearchParams();
  const reportId = searchParams.get("reportId");

  return (
    <div className="flex min-h-screen items-center justify-center px-5 py-8">
      <Card className="w-full max-w-2xl text-center">
        <h1 className="font-display text-5xl font-semibold text-text">
          Interview submitted
        </h1>
        <p className="mt-4 text-sm leading-7 text-muted">
          Thanks for completing the HireOS AI interview. Your responses have been captured for recruiter review.
        </p>
        {reportId ? (
          <p className="mt-4 text-sm text-muted">
            Internal report reference: <span className="font-semibold text-text">{reportId}</span>
          </p>
        ) : null}
        <div className="mt-8 flex justify-center gap-3">
          <Link href="/" className="rounded-full bg-brand px-6 py-3 text-sm font-semibold text-white">
            Back to HireOS AI
          </Link>
        </div>
      </Card>
    </div>
  );
}
