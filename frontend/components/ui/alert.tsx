import React from "react";
import { CircleAlert, CircleCheck, Info, TriangleAlert, X } from "lucide-react";
import { cn } from "@/lib/utils";

type AlertTone = "danger" | "success" | "warning" | "info" | "neutral";

const tones: Record<AlertTone, { box: string; icon: string; Icon: React.ComponentType<{ className?: string }> }> = {
  danger: { box: "border-danger/25 bg-danger/8", icon: "text-danger", Icon: CircleAlert },
  success: { box: "border-success/25 bg-success/8", icon: "text-success", Icon: CircleCheck },
  warning: { box: "border-warning/25 bg-warning/8", icon: "text-warning", Icon: TriangleAlert },
  info: { box: "border-info/25 bg-info/8", icon: "text-info", Icon: Info },
  neutral: { box: "border-line-strong bg-surface-2", icon: "text-fg-subtle", Icon: Info },
};

export function Alert({
  tone = "danger",
  title,
  children,
  onDismiss,
  icon,
  action,
  className,
}: {
  tone?: AlertTone;
  title?: React.ReactNode;
  children?: React.ReactNode;
  onDismiss?: () => void;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  const t = tones[tone];
  return (
    <div
      role={tone === "danger" ? "alert" : "status"}
      className={cn(
        "flex items-start gap-3 rounded-lg border px-3.5 py-3 text-[13px] animate-rise-in",
        t.box,
        className
      )}
    >
      <span className={cn("mt-px shrink-0 [&_svg]:size-4", t.icon)}>
        {icon ?? <t.Icon />}
      </span>
      <div className="min-w-0 flex-1 space-y-0.5">
        {title && <p className="font-medium text-fg">{title}</p>}
        {children && (
          <div className={cn("leading-relaxed break-words", title ? "text-fg-muted" : "text-fg")}>
            {children}
          </div>
        )}
      </div>
      {action && <div className="shrink-0 self-center">{action}</div>}
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          className="-m-1 shrink-0 rounded p-1 text-fg-subtle transition-colors hover:bg-surface-3 hover:text-fg cursor-pointer"
          aria-label="Dismiss"
        >
          <X className="size-3.5" />
        </button>
      )}
    </div>
  );
}
