import React from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { Spinner } from "@/components/ui/spinner";

export type ButtonVariant =
  | "primary"
  | "accent"
  | "secondary"
  | "ghost"
  | "danger"
  | "danger-solid";

export type ButtonSize = "xs" | "sm" | "md" | "lg" | "icon-xs" | "icon-sm" | "icon-md";

const base =
  "inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-xl font-medium select-none cursor-pointer " +
  "transition-[background-color,border-color,color,box-shadow,opacity,transform] duration-150 ease-out " +
  "active:translate-y-px disabled:pointer-events-none disabled:opacity-45 [&_svg]:shrink-0";

const variants: Record<ButtonVariant, string> = {
  primary:
    "bg-gradient-to-b from-[#ff5c2b] to-[#ea3a0e] text-white border border-white/20 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.3),0_4px_16px_rgba(234,58,14,0.35)] hover:brightness-110",
  accent:
    "bg-gradient-to-b from-[#ff5c2b] to-[#ea3a0e] text-white border border-white/20 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.3),0_4px_16px_rgba(234,58,14,0.35)] hover:brightness-110",
  secondary:
    "bg-white/[0.04] text-[#f3f4f6] border border-white/10 hover:bg-white/[0.08] hover:border-white/20 shadow-xs",
  ghost: "text-[#8e95a5] hover:text-white hover:bg-white/[0.05]",
  danger:
    "text-rose-400 bg-rose-500/10 border border-rose-500/20 hover:bg-rose-500/20 hover:border-rose-500/30",
  "danger-solid": "bg-rose-600 text-white hover:brightness-110",
};

const sizes: Record<ButtonSize, string> = {
  xs: "h-7 px-2 text-xs [&_svg]:size-3.5",
  sm: "h-8 px-2.5 text-[13px] [&_svg]:size-3.5",
  md: "h-9 px-3.5 text-sm [&_svg]:size-4",
  lg: "h-10 px-4 text-sm [&_svg]:size-4",
  "icon-xs": "size-7 [&_svg]:size-3.5",
  "icon-sm": "size-8 [&_svg]:size-4",
  "icon-md": "size-9 [&_svg]:size-4",
};

export function buttonStyles({
  variant = "secondary",
  size = "sm",
  className,
}: {
  variant?: ButtonVariant;
  size?: ButtonSize;
  className?: string;
} = {}) {
  return cn(base, variants[variant], sizes[size], className);
}

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  function Button(
    { variant, size, loading = false, className, children, type = "button", ...props },
    ref
  ) {
    return (
      <button
        ref={ref}
        type={type}
        className={buttonStyles({ variant, size, className })}
        aria-busy={loading || undefined}
        {...props}
      >
        {loading && <Spinner className="size-3.5" />}
        {children}
      </button>
    );
  }
);

export interface ButtonLinkProps extends React.ComponentProps<typeof Link> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

export function ButtonLink({ variant, size, className, ...props }: ButtonLinkProps) {
  return <Link className={buttonStyles({ variant, size, className })} {...props} />;
}
