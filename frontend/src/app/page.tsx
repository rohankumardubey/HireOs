import Link from "next/link";
import {
  ArrowRight,
  BrainCircuit,
  ChartSpline,
  FileSearch,
  MessageSquareText,
  ShieldCheck,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

const features = [
  {
    icon: FileSearch,
    title: "Resume + JD intelligence",
    copy: "Parse resumes, extract skills, score alignment, and surface missing must-have capabilities without auto-rejecting applicants.",
  },
  {
    icon: MessageSquareText,
    title: "Structured AI interviews",
    copy: "Generate role-specific question plans, run text or voice-led screening, and capture question-by-question evidence.",
  },
  {
    icon: BrainCircuit,
    title: "Explainable scoring",
    copy: "Show matched concepts, missing concepts, strengths, weaknesses, confidence, and when human review is mandatory.",
  },
  {
    icon: ChartSpline,
    title: "Hiring analytics",
    copy: "Track funnel movement, recruiter overrides, review rates, and model-quality signals from a production-minded event backbone.",
  },
  {
    icon: ShieldCheck,
    title: "Responsible AI controls",
    copy: "Protected attributes stay out of scoring, recruiters stay in control, and every recommendation leaves an auditable trail.",
  },
];

export default function Home() {
  return (
    <div className="px-5 py-5 md:px-8 md:py-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <section className="glass overflow-hidden rounded-[36px] border border-border/80 bg-surface px-6 py-8 md:px-10 md:py-12">
          <div className="grid gap-10 lg:grid-cols-[1.1fr_0.9fr]">
            <div>
              <Badge tone="brand">HireOS AI</Badge>
              <h1 className="mt-6 max-w-4xl font-display text-5xl font-semibold leading-[1.05] text-text md:text-7xl">
                AI-powered interview,
                <br />
                screening, and hiring intelligence
                <span className="text-brand"> for recruiter-led teams.</span>
              </h1>
              <p className="mt-6 max-w-2xl text-lg leading-8 text-muted">
                Build faster, fairer, more explainable hiring loops with recruiter control at every step. HireOS AI combines resume matching, adaptive interviews, semantic scoring, analytics, and event-driven architecture into one SaaS workflow.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <Link
                  href="/login"
                  className="inline-flex items-center gap-2 rounded-full bg-brand px-6 py-3 text-sm font-semibold text-white transition hover:bg-brand-strong"
                >
                  Open recruiter demo
                  <ArrowRight className="size-4" />
                </Link>
                <Link
                  href="/pricing"
                  className="inline-flex items-center rounded-full border border-border bg-white/70 px-6 py-3 text-sm font-semibold text-text transition hover:bg-white"
                >
                  View pricing tiers
                </Link>
              </div>
              <div className="mt-10 grid gap-4 md:grid-cols-3">
                <Card>
                  <p className="text-sm text-muted">Average manual screening effort reduced</p>
                  <p className="mt-3 font-display text-4xl font-semibold text-text">63%</p>
                </Card>
                <Card>
                  <p className="text-sm text-muted">Explainable AI recommendation confidence</p>
                  <p className="mt-3 font-display text-4xl font-semibold text-text">0.84</p>
                </Card>
                <Card>
                  <p className="text-sm text-muted">Recruiter override visibility</p>
                  <p className="mt-3 font-display text-4xl font-semibold text-text">100%</p>
                </Card>
              </div>
            </div>
            <Card className="bg-[#13212a] text-white">
              <p className="text-sm uppercase tracking-[0.24em] text-slate-400">
                Product flow
              </p>
              <div className="mt-6 space-y-4">
                {[
                  "Recruiter creates a job and parses the JD into skills, responsibilities, and interview focus areas.",
                  "Candidate resumes are uploaded, parsed, matched to role requirements, and ranked with explainable AI guidance.",
                  "Candidates complete a structured text or voice screening with adaptive follow-ups and semantic answer evaluation.",
                  "Recruiters review reports, compare rankings, override AI recommendations, and advance the pipeline with auditability.",
                ].map((step, index) => (
                  <div
                    key={step}
                    className="rounded-[24px] border border-white/10 bg-white/6 p-4"
                  >
                    <p className="text-xs font-semibold uppercase tracking-[0.24em] text-brand-soft">
                      Step {index + 1}
                    </p>
                    <p className="mt-3 text-sm leading-7 text-slate-200">{step}</p>
                  </div>
                ))}
              </div>
              <div className="mt-6 rounded-[24px] border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-100">
                AI-generated scores are decision-support signals and should be reviewed by a human recruiter.
              </div>
            </Card>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          {features.map((feature) => {
            const Icon = feature.icon;
            return (
              <Card key={feature.title} className="h-full">
                <div className="inline-flex rounded-2xl bg-brand-soft p-3 text-brand">
                  <Icon className="size-5" />
                </div>
                <h2 className="mt-5 font-display text-2xl font-semibold text-text">
                  {feature.title}
                </h2>
                <p className="mt-3 text-sm leading-7 text-muted">{feature.copy}</p>
              </Card>
            );
          })}
        </section>
      </div>
    </div>
  );
}
