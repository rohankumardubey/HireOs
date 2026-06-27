"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AlertTriangle, ClipboardList, MessageSquareText, ShieldCheck } from "lucide-react";

import { AppShell } from "@/components/layout/app-shell";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { MetricCard } from "@/components/ui/metric-card";
import { useAuth } from "@/hooks/use-auth";
import { api } from "@/lib/api";
import type { ShortlistBriefCandidate } from "@/lib/types";
import { formatScore, titleCase } from "@/lib/utils";

type BadgeTone = "success" | "warning" | "danger" | "brand" | "neutral";

function decisionTone(candidate: ShortlistBriefCandidate): BadgeTone {
  if (candidate.recruiter_decision === "rejected" || candidate.recruiter_decision === "archived") {
    return "danger";
  }
  if (candidate.recruiter_decision) {
    return "success";
  }
  if (candidate.human_review_required) {
    return "warning";
  }
  return "brand";
}

export default function ShortlistBriefPage() {
  const auth = useAuth();
  const params = useParams<{ jobId: string }>();
  const jobId = params.jobId;

  const brief = useQuery({
    queryKey: ["shortlist-brief", auth.token, jobId],
    queryFn: () => api.getShortlistBrief(auth.token as string, jobId),
    enabled: Boolean(auth.token && jobId),
  });

  const summary = brief.data?.summary;

  return (
    <AppShell
      title="Shortlist Brief"
      subtitle="Prepare an evidence-backed hiring-manager packet from resume match, interview evidence, recruiter decisions, and human-review signals."
      actions={
        <Link
          href={`/jobs/${jobId}`}
          className="rounded-full border border-border bg-white/80 px-5 py-3 text-sm font-semibold text-text transition hover:border-brand hover:text-brand"
        >
          Back to job
        </Link>
      }
    >
      <div className="grid gap-4 lg:grid-cols-4">
        <MetricCard
          label="Matched candidates"
          value={String(summary?.total_matched_candidates || 0)}
          hint="Candidates with a resume-to-job match for this role."
        />
        <MetricCard
          label="Recommended shortlist"
          value={String(summary?.recommended_shortlist_count || 0)}
          hint="Top candidates included in the hiring-manager packet."
        />
        <MetricCard
          label="Avg final score"
          value={`${formatScore(summary?.average_final_score)}%`}
          hint="Blended resume match and interview evidence."
        />
        <MetricCard
          label="Human review"
          value={String(summary?.human_review_required_count || 0)}
          hint="Candidates with active review flags."
        />
      </div>

      <div className="mt-6 grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <Card>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="brand">{brief.data?.job_title || "Role"}</Badge>
            {brief.data?.generated_at ? (
              <Badge tone="neutral">Generated {new Date(brief.data.generated_at).toLocaleString()}</Badge>
            ) : null}
          </div>
          <h3 className="mt-5 font-display text-3xl font-semibold text-text">
            Hiring-manager summary
          </h3>
          <p className="mt-4 text-sm leading-7 text-muted">
            {brief.data?.hiring_manager_summary ||
              "No shortlist brief is available yet. Match candidates to this role to generate one."}
          </p>
          <div className="mt-6 rounded-[24px] border border-brand/10 bg-brand-soft/60 p-4 text-sm leading-7 text-brand">
            {brief.data?.policy_note || "Shortlist briefs are decision-support artifacts for human review."}
          </div>
        </Card>

        <Card>
          <div className="flex items-start gap-3">
            <MessageSquareText className="mt-1 size-5 text-brand" />
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">
                Discussion guide
              </p>
              <p className="mt-3 text-sm leading-7 text-muted">
                Use these prompts to keep hiring-manager review focused on evidence, gaps, and calibration.
              </p>
            </div>
          </div>
          <div className="mt-5 space-y-3">
            {(brief.data?.discussion_questions || []).map((question) => (
              <div
                key={question}
                className="rounded-[22px] border border-border/70 bg-white/75 px-4 py-4 text-sm leading-7 text-text"
              >
                {question}
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card className="mt-6">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">
              Recommended candidate packet
            </p>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-muted">
              Ranked evidence for the candidates most worth discussing. Each row is deliberately framed as
              human-review support, not an automated decision.
            </p>
          </div>
          <Badge tone={brief.data?.candidates.length ? "success" : "neutral"}>
            {brief.data?.candidates.length || 0} candidates
          </Badge>
        </div>

        <div className="mt-6 space-y-4">
          {brief.data?.candidates.length ? (
            brief.data.candidates.map((candidate) => (
              <CandidateBriefCard key={candidate.candidate_id} candidate={candidate} />
            ))
          ) : (
            <div className="rounded-[24px] border border-dashed border-border bg-white/60 px-6 py-10 text-center text-sm text-muted">
              {brief.isLoading
                ? "Loading shortlist brief..."
                : "No matched candidates are available yet. Upload resumes and run matching to create a shortlist brief."}
            </div>
          )}
        </div>
      </Card>

      <div className="mt-6 grid gap-4 xl:grid-cols-[0.85fr_1.15fr]">
        <Card>
          <div className="flex items-center gap-3">
            <AlertTriangle className="size-5 text-amber-600" />
            <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">
              Brief-level risks
            </p>
          </div>
          <div className="mt-5 space-y-3">
            {(brief.data?.risk_flags || []).map((flag) => (
              <div
                key={flag}
                className="rounded-[22px] border border-border/70 bg-white/75 px-4 py-4 text-sm leading-7 text-muted"
              >
                {flag}
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <div className="flex items-center gap-3">
            <ShieldCheck className="size-5 text-brand" />
            <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">
              Responsible review guardrails
            </p>
          </div>
          <div className="mt-5 grid gap-3 md:grid-cols-3">
            {[
              "Treat scores as evidence, not outcomes.",
              "Discuss missing must-have skills explicitly.",
              "Resolve human-review flags before final decisions.",
            ].map((item) => (
              <div key={item} className="rounded-[22px] bg-white/75 px-4 py-4 text-sm leading-7 text-text">
                {item}
              </div>
            ))}
          </div>
        </Card>
      </div>
    </AppShell>
  );
}

function CandidateBriefCard({ candidate }: { candidate: ShortlistBriefCandidate }) {
  return (
    <div className="rounded-[28px] border border-border/80 bg-white/75 p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <Badge tone="brand">#{candidate.rank}</Badge>
            <Link
              href={`/candidates/${candidate.candidate_id}`}
              className="font-display text-2xl font-semibold text-text transition hover:text-brand"
            >
              {candidate.candidate_name}
            </Link>
            <Badge tone={decisionTone(candidate)}>
              {candidate.recruiter_decision
                ? titleCase(candidate.recruiter_decision)
                : candidate.human_review_required
                  ? "Human review"
                  : "Review ready"}
            </Badge>
          </div>
          <p className="mt-2 text-sm text-muted">
            {candidate.current_role || "Candidate"} · {candidate.years_experience} years · {candidate.candidate_email}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge tone={candidate.final_score >= 70 ? "success" : "warning"}>
            Final {formatScore(candidate.final_score)}%
          </Badge>
          <Badge tone={candidate.human_review_required ? "warning" : "neutral"}>
            {titleCase(candidate.ai_recommendation)}
          </Badge>
        </div>
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-5">
        <Metric label="Resume" value={`${formatScore(candidate.resume_match_score)}%`} />
        <Metric label="Interview" value={`${formatScore(candidate.interview_score)}%`} />
        <Metric label="Coverage" value={`${formatScore(candidate.must_have_coverage)}%`} />
        <Metric label="Confidence" value={`${formatScore(candidate.confidence_score)}%`} />
        <Metric label="Interview state" value={titleCase(candidate.interview_status)} />
      </div>

      <div className="mt-5 rounded-[22px] bg-brand-soft/50 px-4 py-4 text-sm leading-7 text-brand">
        {candidate.evidence_summary}
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        <EvidenceList
          icon={<ClipboardList className="size-4" />}
          title="Strengths"
          tone="success"
          items={candidate.strengths}
        />
        <EvidenceList
          icon={<AlertTriangle className="size-4" />}
          title="Risks"
          tone="warning"
          items={candidate.risks}
        />
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        <SkillList title="Matched must-haves" skills={candidate.matched_required_skills} tone="brand" empty="No matched must-have skills captured." />
        <SkillList title="Missing must-haves" skills={candidate.missing_required_skills} tone="danger" empty="No missing must-have skills recorded." />
      </div>

      <div className="mt-5 rounded-[22px] border border-border/70 bg-white/80 px-4 py-4">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-soft">
          Suggested next step
        </p>
        <p className="mt-2 text-sm leading-7 text-text">{candidate.suggested_next_step}</p>
        <p className="mt-3 text-sm leading-7 text-muted">{candidate.report_excerpt}</p>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[20px] bg-white/80 px-4 py-4">
      <p className="text-[11px] uppercase tracking-[0.2em] text-muted-soft">{label}</p>
      <p className="mt-2 text-sm font-semibold text-text">{value}</p>
    </div>
  );
}

function EvidenceList({
  icon,
  title,
  tone,
  items,
}: {
  icon: React.ReactNode;
  title: string;
  tone: BadgeTone;
  items: string[];
}) {
  return (
    <div>
      <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.18em] text-muted-soft">
        {icon}
        {title}
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {items.map((item) => (
          <Badge key={item} tone={tone}>
            {item}
          </Badge>
        ))}
      </div>
    </div>
  );
}

function SkillList({
  title,
  skills,
  tone,
  empty,
}: {
  title: string;
  skills: string[];
  tone: BadgeTone;
  empty: string;
}) {
  return (
    <div>
      <p className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-soft">{title}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {skills.length ? (
          skills.map((skill) => (
            <Badge key={`${title}-${skill}`} tone={tone}>
              {skill}
            </Badge>
          ))
        ) : (
          <span className="text-sm text-muted">{empty}</span>
        )}
      </div>
    </div>
  );
}
