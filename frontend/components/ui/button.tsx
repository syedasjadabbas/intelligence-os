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
  "inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-md font-medium select-none cursor-pointer " +
  "transition-[background-color,border-color,color,box-shadow,opacity,transform] duration-150 ease-out " +
  "active:translate-y-px disabled:pointer-events-none disabled:opacity-45 [&_svg]:shrink-0";

const variants: Record<ButtonVariant, string> = {
  primary:
    "bg-fg text-canvas hover:bg-white shadow-[0_1px_0_0_rgb(255_255_255/0.25)_inset]",
  accent:
    "bg-accent text-accent-fg hover:bg-accent-strong shadow-[0_1px_0_0_rgb(255_255_255/0.25)_inset]",
  secondary:
    "bg-surface-3 text-fg border border-line-strong hover:bg-surface-4 hover:border-fg-faint",
  ghost: "text-fg-muted hover:text-fg hover:bg-surface-3",
  danger:
    "text-danger bg-danger/10 border border-danger/25 hover:bg-danger/18 hover:border-danger/40",
  "danger-solid": "bg-danger text-white hover:brightness-110",
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
