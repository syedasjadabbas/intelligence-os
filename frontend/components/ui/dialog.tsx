"use client";

import React, { useEffect, useId, useRef } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

type DialogSize = "sm" | "md" | "lg" | "xl";

const widths: Record<DialogSize, string> = {
  sm: "sm:max-w-sm",
  md: "sm:max-w-md",
  lg: "sm:max-w-xl",
  xl: "sm:max-w-3xl",
};

export interface DialogProps {
  onClose: () => void;
  title: React.ReactNode;
  description?: React.ReactNode;
  icon?: React.ReactNode;
  /** Extra content placed beside the title (badges, status). */
  meta?: React.ReactNode;
  footer?: React.ReactNode;
  size?: DialogSize;
  /** "center" renders a modal; "right" renders a full-height side sheet. */
  variant?: "center" | "right";
  /** Classes for the scrollable body region. */
  bodyClassName?: string;
  /** Extra classes for the panel (e.g. a narrower sheet width). */
  panelClassName?: string;
  children?: React.ReactNode;
}

/**
 * Accessible modal surface. Callers keep controlling visibility by rendering it
 * conditionally, exactly like the original inline modals. Escape and the
 * backdrop call `onClose`, focus is trapped inside and restored on close.
 */
export function Dialog({
  onClose,
  title,
  description,
  icon,
  meta,
  footer,
  size = "md",
  variant = "center",
  bodyClassName,
  panelClassName,
  children,
}: DialogProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);
  const titleId = useId();
  const descId = useId();

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const panel = panelRef.current;
    const firstField = panel?.querySelector<HTMLElement>(
      "input:not([type=hidden]):not([disabled]), textarea:not([disabled]), select:not([disabled])"
    );
    (firstField ?? panel)?.focus();

    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onCloseRef.current();
        return;
      }
      if (e.key !== "Tab" || !panel) return;
      const items = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
        (el) => el.offsetParent !== null
      );
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", handleKey);

    return () => {
      document.removeEventListener("keydown", handleKey);
      document.body.style.overflow = originalOverflow;
      previouslyFocused?.focus?.();
    };
  }, []);

  const isSheet = variant === "right";

  return (
    <div
      className={cn(
        "fixed inset-0 z-50 flex",
        isSheet ? "justify-end" : "items-end sm:items-center justify-center sm:p-4"
      )}
    >
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-[2px] animate-fade-in"
        onClick={onClose}
        aria-hidden
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descId : undefined}
        tabIndex={-1}
        className={cn(
          "relative flex flex-col bg-surface border-line-strong shadow-overlay focus:outline-none",
          isSheet
            ? "h-full w-full sm:max-w-2xl lg:max-w-3xl border-l animate-slide-in-right"
            : cn(
                "w-full max-h-[92vh] rounded-t-xl sm:rounded-xl border animate-scale-in",
                widths[size]
              ),
          panelClassName
        )}
      >
        <header className="flex items-start gap-3 border-b border-line px-5 py-4 shrink-0">
          {icon && (
            <div className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-md border border-line-strong bg-surface-3 text-fg-muted [&_svg]:size-4">
              {icon}
            </div>
          )}
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h2 id={titleId} className="text-[15px] font-semibold tracking-tight text-fg">
                {title}
              </h2>
              {meta}
            </div>
            {description && (
              <p id={descId} className="mt-0.5 text-[13px] leading-relaxed text-fg-subtle">
                {description}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="-mr-1.5 -mt-0.5 rounded-md p-1.5 text-fg-subtle transition-colors hover:bg-surface-3 hover:text-fg cursor-pointer"
            aria-label="Close dialog"
          >
            <X className="size-4" />
          </button>
        </header>

        <div className={cn("min-h-0 flex-1 overflow-y-auto px-5 py-4", bodyClassName)}>
          {children}
        </div>

        {footer && (
          <footer className="flex flex-wrap items-center justify-end gap-2 border-t border-line bg-surface-2/60 px-5 py-3 shrink-0 rounded-b-xl">
            {footer}
          </footer>
        )}
      </div>
    </div>
  );
}
