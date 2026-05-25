import { ArrowUpRight } from "lucide-react";

import { Card } from "@/components/ui/card";

export function MetricCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <Card className="relative overflow-hidden">
      <div className="absolute right-4 top-4 rounded-full bg-brand-soft p-2 text-brand">
        <ArrowUpRight className="size-4" />
      </div>
      <p className="text-sm font-medium text-muted">{label}</p>
      <p className="mt-4 font-display text-4xl font-semibold text-text">{value}</p>
      <p className="mt-3 text-sm text-muted-soft">{hint}</p>
    </Card>
  );
}

