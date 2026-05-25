import { cn } from "@/lib/utils";

const toneMap: Record<string, string> = {
  success: "bg-emerald-100 text-emerald-800",
  warning: "bg-amber-100 text-amber-800",
  danger: "bg-rose-100 text-rose-800",
  brand: "bg-brand-soft text-brand",
  neutral: "bg-slate-100 text-slate-700",
};

export function Badge({
  children,
  tone = "neutral",
  className,
}: {
  children: React.ReactNode;
  tone?: keyof typeof toneMap;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold tracking-wide",
        toneMap[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

