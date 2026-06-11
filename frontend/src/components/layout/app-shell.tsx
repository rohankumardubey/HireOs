"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  AlertTriangle,
  BarChart3,
  Bot,
  BriefcaseBusiness,
  FileText,
  Gauge,
  GitCompareArrows,
  Settings,
  Shield,
  Users2,
} from "lucide-react";
import { useEffect } from "react";

import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/hooks/use-auth";
import { cn } from "@/lib/utils";

const nav = [
  { href: "/dashboard", label: "Overview", icon: Gauge },
  { href: "/jobs", label: "Jobs", icon: BriefcaseBusiness },
  { href: "/candidates", label: "Candidates", icon: Users2 },
  { href: "/copilot", label: "Copilot", icon: Bot },
  { href: "/compare", label: "Compare", icon: GitCompareArrows },
  { href: "/calibration", label: "Calibration", icon: AlertTriangle },
  { href: "/ranking", label: "Ranking", icon: BarChart3 },
  { href: "/reports", label: "Reports", icon: FileText },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/admin", label: "Admin", icon: Shield },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function AppShell({
  title,
  subtitle,
  actions,
  children,
}: {
  title: string;
  subtitle: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const auth = useAuth();

  useEffect(() => {
    if (!auth.loading && !auth.isAuthenticated) {
      router.replace("/login");
    }
  }, [auth.isAuthenticated, auth.loading, router]);

  if (auth.loading || !auth.isAuthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="glass rounded-[28px] border border-border bg-surface px-6 py-4 text-sm text-muted">
          Loading HireOS AI workspace...
        </div>
      </div>
    );
  }

  const membership = auth.user?.memberships[0];
  const role = membership?.role || "recruiter";

  return (
    <div className="app-shell-grid">
      <aside className="border-r border-border/70 bg-[#15222d] px-6 py-8 text-white">
        <div>
          <Badge tone="brand" className="bg-white/12 text-white">
            HireOS AI
          </Badge>
          <h1 className="mt-5 font-display text-3xl font-semibold">
            Hiring intelligence,
            <br />
            without autopilot risk.
          </h1>
          <p className="mt-3 text-sm leading-6 text-slate-300">
            Recruiter-controlled screening, explainable scoring, and analytics built for business demos and real teams.
          </p>
        </div>
        <nav className="mt-10 space-y-2">
          {nav.map((item) => {
            const Icon = item.icon;
            const active =
              pathname === item.href ||
              (item.href !== "/dashboard" && pathname.startsWith(item.href));

            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-2xl px-4 py-3 text-sm transition",
                  active
                    ? "bg-[#f5f1e8] !text-[#15222d] font-semibold shadow-sm"
                    : "text-slate-300 hover:bg-white/8 hover:text-white",
                )}
              >
                <Icon className="size-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="mt-10 rounded-[24px] border border-white/10 bg-white/6 p-4 text-sm text-slate-300">
          <p className="font-semibold text-white">{auth.user?.full_name}</p>
          <p className="mt-1">{auth.user?.email}</p>
          <p className="mt-4 text-xs uppercase tracking-[0.22em] text-slate-400">
            Role
          </p>
          <p className="mt-1 capitalize">{role.replaceAll("_", " ")}</p>
          <button
            type="button"
            onClick={async () => {
              await auth.logout();
              router.push("/login");
            }}
            className="mt-5 rounded-full border border-white/20 px-4 py-2 text-xs font-semibold tracking-[0.14em] text-white transition hover:bg-white hover:text-slate-900"
          >
            Sign out
          </button>
        </div>
      </aside>
      <main className="px-5 py-5 md:px-8 md:py-8">
        <div className="glass rounded-[32px] border border-border/80 bg-surface p-6 md:p-8">
          <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.22em] text-brand">
                Recruiter workspace
              </p>
              <h2 className="mt-3 font-display text-4xl font-semibold text-text">
                {title}
              </h2>
              <p className="mt-3 max-w-2xl text-sm leading-7 text-muted">
                {subtitle}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">{actions}</div>
          </div>
          <div className="mt-6 rounded-[24px] border border-brand/10 bg-brand-soft/60 px-4 py-3 text-sm text-brand">
            AI-generated scores are decision-support signals and should be reviewed by a human recruiter.
          </div>
          <div className="mt-8">{children}</div>
        </div>
      </main>
    </div>
  );
}
