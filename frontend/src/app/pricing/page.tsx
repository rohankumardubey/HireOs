import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

const plans = [
  {
    name: "Free trial",
    price: "$0",
    note: "Try the full recruiter workflow with limited volume.",
    items: ["25 candidates", "3 active jobs", "Text interviews", "Local event export"],
  },
  {
    name: "Startup",
    price: "$399",
    note: "For lean talent teams standardizing high-volume screening.",
    items: ["500 candidates", "Unlimited recruiters", "Interview scoring", "Candidate ranking"],
  },
  {
    name: "Growth",
    price: "$1,290",
    note: "For scaling companies that need analytics and workflow control.",
    items: ["3,000 candidates", "Analytics dashboards", "Usage tracking", "Lakehouse exports"],
  },
  {
    name: "Enterprise",
    price: "Custom",
    note: "For global teams with compliance, control, and integration needs.",
    items: ["SSO", "Custom scoring rubrics", "ATS integrations", "Private deployment options"],
  },
];

export default function PricingPage() {
  return (
    <div className="px-5 py-5 md:px-8 md:py-8">
      <div className="mx-auto max-w-7xl">
        <div className="glass rounded-[36px] border border-border/80 bg-surface p-8 md:p-10">
          <Badge tone="brand">Billing-ready design</Badge>
          <h1 className="mt-5 font-display text-5xl font-semibold text-text">
            Flexible plans for hiring teams that want AI with accountability.
          </h1>
          <p className="mt-4 max-w-3xl text-lg leading-8 text-muted">
            HireOS AI is designed to monetize on usage, recruiter collaboration, analytics depth, and deployment posture.
          </p>
          <div className="mt-8 grid gap-4 lg:grid-cols-4">
            {plans.map((plan) => (
              <Card key={plan.name} className="h-full">
                <p className="text-sm uppercase tracking-[0.22em] text-brand">{plan.name}</p>
                <p className="mt-4 font-display text-4xl font-semibold text-text">{plan.price}</p>
                <p className="mt-3 text-sm leading-7 text-muted">{plan.note}</p>
                <div className="mt-5 space-y-2 text-sm text-text">
                  {plan.items.map((item) => (
                    <div key={item} className="rounded-2xl bg-white/70 px-3 py-2">
                      {item}
                    </div>
                  ))}
                </div>
              </Card>
            ))}
          </div>
          <div className="mt-8 flex gap-3">
            <Link
              href="/signup"
              className="rounded-full bg-brand px-6 py-3 text-sm font-semibold text-white"
            >
              Start trial
            </Link>
            <Link
              href="/login"
              className="rounded-full border border-border bg-white/70 px-6 py-3 text-sm font-semibold text-text"
            >
              Open demo
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
