import React from "react";
import { cn } from "@/lib/utils";

export type BadgeTone =
  | "neutral"
  | "accent"
  | "success"
  | "warning"
  | "danger"
  | "info"
  | "llm"
  | "deterministic";

const tones: Record<BadgeTone, string> = {
  neutral: "bg-surface-3 text-fg-muted border-line-strong",
  accent: "bg-accent/12 text-accent-strong border-accent/25",
  success: "bg-success/10 text-success border-success/25",
  warning: "bg-warning/10 text-warning border-warning/25",
  danger: "bg-danger/10 text-danger border-danger/25",
  info: "bg-info/10 text-info border-info/25",
  llm: "bg-judge-llm/10 text-judge-llm border-judge-llm/25",
  deterministic: "bg-judge-det/10 text-judge-det border-judge-det/25",
};

const dotTones: Record<BadgeTone, string> = {
  neutral: "bg-fg-subtle",
  accent: "bg-accent",
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
  info: "bg-info",
  llm: "bg-judge-llm",
  deterministic: "bg-judge-det",
};

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
  dot?: boolean;
  pulse?: boolean;
  mono?: boolean;
  size?: "sm" | "md";
}

export function Badge({
  tone = "neutral",
  dot = false,
  pulse = false,
  mono = false,
  size = "sm",
  className,
  children,
  ...props
}: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-[5px] border font-medium whitespace-nowrap leading-none [&_svg]:size-3 [&_svg]:shrink-0",
        size === "sm" ? "h-5 px-1.5 text-[11px]" : "h-6 px-2 text-xs",
        mono && "font-mono tracking-tight",
        tones[tone],
        className
      )}
      {...props}
    >
      {dot && (
        <span className="relative flex size-1.5 shrink-0">
          {pulse && (
            <span
              className={cn(
                "absolute inline-flex size-full animate-ping rounded-full opacity-60",
                dotTones[tone]
              )}
            />
          )}
          <span className={cn("relative inline-flex size-1.5 rounded-full", dotTones[tone])} />
        </span>
      )}
      {children}
    </span>
  );
}
