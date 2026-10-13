import React from "react";
import { cn } from "@/lib/utils";

/** Bordered panel used for every grouped region of content. */
export function Panel({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <section
      className={cn("rounded-lg border border-line bg-surface", className)}
      {...props}
    >
      {children}
    </section>
  );
}

export function PanelHeader({
  title,
  description,
  icon,
  count,
  actions,
  className,
  children,
}: {
  title: React.ReactNode;
  description?: React.ReactNode;
  icon?: React.ReactNode;
  count?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className={cn("border-b border-line px-4 py-3 sm:px-5", className)}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            {icon && <span className="text-fg-subtle [&_svg]:size-4">{icon}</span>}
            <h2 className="text-sm font-semibold tracking-tight text-fg">{title}</h2>
            {count !== undefined && (
              <span className="tabular rounded-[5px] border border-line-strong bg-surface-3 px-1.5 py-px font-mono text-[11px] text-fg-muted">
                {count}
              </span>
            )}
          </div>
          {description && (
            <p className="mt-0.5 text-[13px] leading-relaxed text-fg-subtle">{description}</p>
          )}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
      {children}
    </div>
  );
}

/** Small uppercase label used to title sub-sections. */
export function Eyebrow({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <p
      className={cn(
        "text-[11px] font-medium uppercase tracking-[0.08em] text-fg-subtle",
        className
      )}
    >
      {children}
    </p>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon?: React.ReactNode;
  title: React.ReactNode;
  description?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center px-6 py-14 text-center",
        className
      )}
    >
      {icon && (
        <div className="mb-4 flex size-10 items-center justify-center rounded-lg border border-line-strong bg-surface-2 text-fg-subtle [&_svg]:size-5">
          {icon}
        </div>
      )}
      <p className="text-sm font-medium text-fg">{title}</p>
      {description && (
        <p className="mt-1 max-w-sm text-[13px] leading-relaxed text-fg-subtle">{description}</p>
      )}
      {action && <div className="mt-5 flex flex-wrap items-center justify-center gap-2">{action}</div>}
    </div>
  );
}

export function Kbd({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <kbd
      className={cn(
        "inline-flex h-5 min-w-5 items-center justify-center rounded border border-line-strong bg-surface-3 px-1 font-mono text-[10px] font-medium text-fg-subtle",
        className
      )}
    >
      {children}
    </kbd>
  );
}

export function ProgressBar({
  value,
  tone = "accent",
  className,
  label,
}: {
  /** 0 – 100 */
  value: number;
  tone?: "accent" | "info" | "success" | "danger" | "warning";
  className?: string;
  label?: string;
}) {
  const fill = {
    accent: "bg-accent",
    info: "bg-info",
    success: "bg-success",
    danger: "bg-danger",
    warning: "bg-warning",
  }[tone];
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(clamped)}
      aria-label={label}
      className={cn("h-1.5 w-full overflow-hidden rounded-full bg-surface-4", className)}
    >
      <div
        className={cn("h-full rounded-full transition-[width] duration-500 ease-out", fill)}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}

/** Segmented control for mutually exclusive filters and tabs. */
export function Segmented<T extends string>({
  value,
  onChange,
  options,
  className,
  ariaLabel,
  role = "radiogroup",
}: {
  value: T;
  onChange: (value: T) => void;
  options: { value: T; label: React.ReactNode; tone?: "danger" | "success" }[];
  className?: string;
  ariaLabel: string;
  role?: "radiogroup" | "tablist";
}) {
  return (
    <div
      role={role}
      aria-label={ariaLabel}
      className={cn(
        "inline-flex items-center gap-0.5 rounded-md border border-line-strong bg-surface p-0.5",
        className
      )}
    >
      {options.map((opt) => {
        const active = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            role={role === "tablist" ? "tab" : "radio"}
            aria-checked={role === "radiogroup" ? active : undefined}
            aria-selected={role === "tablist" ? active : undefined}
            onClick={() => onChange(opt.value)}
            className={cn(
              "inline-flex h-7 items-center gap-1.5 whitespace-nowrap rounded-[5px] px-2.5 text-xs font-medium transition-colors cursor-pointer",
              active
                ? opt.tone === "danger"
                  ? "bg-danger/12 text-danger"
                  : opt.tone === "success"
                  ? "bg-success/12 text-success"
                  : "bg-surface-4 text-fg shadow-[0_1px_0_0_rgb(255_255_255/0.05)_inset]"
                : "text-fg-subtle hover:text-fg"
            )}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
