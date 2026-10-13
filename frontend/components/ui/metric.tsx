import React from "react";
import { cn } from "@/lib/utils";

type MetricTone = "default" | "success" | "accent" | "warning" | "danger";

const valueTones: Record<MetricTone, string> = {
  default: "text-fg",
  success: "text-success",
  accent: "text-accent-strong",
  warning: "text-warning",
  danger: "text-danger",
};

const meterTones: Record<MetricTone, string> = {
  default: "bg-fg-muted",
  success: "bg-success",
  accent: "bg-accent",
  warning: "bg-warning",
  danger: "bg-danger",
};

/**
 * Compact KPI tile. `meter` (0–1) draws a hairline gauge under the value for
 * ratio metrics; omit it for unbounded values such as latency.
 */
export function MetricTile({
  label,
  value,
  hint,
  tone = "default",
  meter,
  className,
}: {
  label: React.ReactNode;
  value: React.ReactNode;
  hint?: React.ReactNode;
  tone?: MetricTone;
  meter?: number | null;
  className?: string;
}) {
  const hasMeter = typeof meter === "number" && Number.isFinite(meter);
  return (
    <div className={cn("flex min-w-0 flex-col bg-surface px-4 py-3.5", className)}>
      <span className="truncate text-xs font-medium text-fg-subtle">{label}</span>
      <span
        className={cn(
          "tabular mt-2 font-mono text-[22px] leading-none font-medium tracking-tight",
          valueTones[tone]
        )}
      >
        {value}
      </span>
      <div className="mt-3 h-[3px] w-full overflow-hidden rounded-full bg-surface-4">
        {hasMeter && (
          <div
            className={cn("h-full rounded-full transition-[width] duration-500", meterTones[tone])}
            style={{ width: `${Math.max(0, Math.min(1, meter as number)) * 100}%` }}
          />
        )}
      </div>
      {hint && <span className="mt-2 truncate text-[11px] text-fg-subtle">{hint}</span>}
    </div>
  );
}

/** Hairline-divided grid of metric tiles. */
export function MetricGrid({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <div
      className={cn(
        "grid gap-px overflow-hidden rounded-lg border border-line bg-line",
        "grid-cols-2 sm:grid-cols-4 xl:grid-cols-8",
        className
      )}
    >
      {children}
    </div>
  );
}
