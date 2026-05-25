import { cn } from "@/lib/utils";

export function Card({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "glass rounded-[28px] border border-border/80 bg-surface p-6",
        className,
      )}
    >
      {children}
    </div>
  );
}

