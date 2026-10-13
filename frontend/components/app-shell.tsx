"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  ChevronsUpDown,
  Database,
  FileText,
  LogOut,
  Menu,
  MessagesSquare,
  X,
} from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";
import { BrandMark } from "@/components/brand";
import { Badge } from "@/components/ui/badge";

interface NavItem {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  isActive: (pathname: string) => boolean;
}

const NAV_ITEMS: NavItem[] = [
  {
    href: "/",
    label: "Chat",
    icon: MessagesSquare,
    isActive: (p) => p === "/" || p === "/workspace",
  },
  {
    href: "/documents",
    label: "Documents",
    icon: FileText,
    isActive: (p) => p.startsWith("/documents"),
  },
  {
    href: "/evaluations",
    label: "Evaluations",
    icon: Activity,
    isActive: (p) => p.startsWith("/evaluations") && !p.startsWith("/evaluations/datasets"),
  },
  {
    href: "/evaluations/datasets",
    label: "Datasets",
    icon: Database,
    isActive: (p) => p.startsWith("/evaluations/datasets"),
  },
];

function useDismiss(open: boolean, close: () => void, ref: React.RefObject<HTMLElement | null>) {
  useEffect(() => {
    if (!open) return;
    const onPointer = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) close();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, close, ref]);
}

function UserMenu() {
  const { user, org, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useDismiss(open, () => setOpen(false), ref);

  const initial = user?.email?.charAt(0).toUpperCase() || "U";

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex h-8 items-center gap-2 rounded-md pl-1 pr-1.5 text-fg-muted transition-colors hover:bg-surface-3 hover:text-fg cursor-pointer"
      >
        <span className="flex size-6 items-center justify-center rounded-full border border-line-strong bg-surface-4 text-[11px] font-semibold text-fg">
          {initial}
        </span>
        <ChevronsUpDown className="hidden size-3.5 sm:block" />
        <span className="sr-only">Account menu</span>
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 top-full z-50 mt-2 w-64 rounded-lg border border-line-strong bg-surface-2 p-1 shadow-overlay animate-scale-in origin-top-right"
        >
          <div className="px-3 py-2.5">
            <p className="truncate text-[13px] font-medium text-fg">{user?.email || "—"}</p>
            <div className="mt-1.5 flex items-center gap-1.5">
              {user?.role && (
                <Badge tone={user.role === "ADMIN" ? "accent" : "neutral"}>
                  {user.role === "ADMIN" ? "Admin" : "Member"}
                </Badge>
              )}
              {org?.slug && (
                <span className="truncate font-mono text-[11px] text-fg-subtle">{org.slug}</span>
              )}
            </div>
          </div>
          <div className="my-1 h-px bg-line" />
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              logout();
            }}
            className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-[13px] text-fg-muted transition-colors hover:bg-surface-3 hover:text-fg cursor-pointer"
          >
            <LogOut className="size-4" />
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}

/**
 * Global top bar shared by every authenticated surface.
 * `leading` renders before the brand (e.g. the chat sidebar toggle);
 * `center` renders in the middle on wide screens.
 */
export function TopBar({
  leading,
  center,
  trailing,
}: {
  leading?: React.ReactNode;
  center?: React.ReactNode;
  trailing?: React.ReactNode;
}) {
  const pathname = usePathname() || "/";
  const { org } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);
  const mobileRef = useRef<HTMLDivElement>(null);
  useDismiss(mobileOpen, () => setMobileOpen(false), mobileRef);

  return (
    <header className="relative z-40 flex h-12 shrink-0 items-center gap-2 border-b border-line bg-canvas/90 px-2.5 backdrop-blur-md sm:px-4">
      {leading}

      <Link
        href="/"
        className="flex items-center gap-2 rounded-md px-1 py-1 transition-opacity hover:opacity-90"
        aria-label="Intelligence OS home"
      >
        <BrandMark />
        <span className="hidden text-sm font-semibold tracking-tight text-fg lg:inline">
          Intelligence<span className="font-medium text-fg-subtle"> OS</span>
        </span>
      </Link>

      {org?.name && (
        <>
          <span className="text-fg-faint select-none" aria-hidden>
            /
          </span>
          <span
            className="max-w-[9rem] truncate text-[13px] font-medium text-fg-muted sm:max-w-[12rem]"
            title={org.name}
          >
            {org.name}
          </span>
        </>
      )}

      <nav aria-label="Primary" className="ml-3 hidden items-center gap-0.5 md:flex">
        {NAV_ITEMS.map((item) => {
          const active = item.isActive(pathname);
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "relative flex h-8 items-center gap-1.5 rounded-md px-2.5 text-[13px] font-medium transition-colors",
                active ? "text-fg bg-surface-3" : "text-fg-subtle hover:text-fg hover:bg-surface-2"
              )}
            >
              <item.icon className={cn("size-3.5", active ? "text-accent" : "")} />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="flex min-w-0 flex-1 justify-center px-2">{center}</div>

      <div className="flex items-center gap-1.5">
        {trailing}
        <div className="relative md:hidden" ref={mobileRef}>
          <button
            type="button"
            onClick={() => setMobileOpen((v) => !v)}
            aria-expanded={mobileOpen}
            aria-label={mobileOpen ? "Close navigation" : "Open navigation"}
            className="flex size-8 items-center justify-center rounded-md text-fg-muted transition-colors hover:bg-surface-3 hover:text-fg cursor-pointer"
          >
            {mobileOpen ? <X className="size-4" /> : <Menu className="size-4" />}
          </button>
          {mobileOpen && (
            <nav
              aria-label="Primary"
              className="absolute right-0 top-full z-50 mt-2 w-56 rounded-lg border border-line-strong bg-surface-2 p-1 shadow-overlay animate-scale-in origin-top-right"
            >
              {NAV_ITEMS.map((item) => {
                const active = item.isActive(pathname);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setMobileOpen(false)}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "flex items-center gap-2.5 rounded-md px-3 py-2 text-[13px] font-medium transition-colors",
                      active ? "bg-surface-3 text-fg" : "text-fg-muted hover:bg-surface-3 hover:text-fg"
                    )}
                  >
                    <item.icon className={cn("size-4", active ? "text-accent" : "text-fg-subtle")} />
                    {item.label}
                  </Link>
                );
              })}
            </nav>
          )}
        </div>
        <UserMenu />
      </div>
    </header>
  );
}

/** Standard layout for content pages: top bar + centered, padded main column. */
export function AppShell({
  children,
  width = "wide",
}: {
  children: React.ReactNode;
  width?: "default" | "wide";
}) {
  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <TopBar />
      <main
        className={cn(
          "mx-auto w-full flex-1 px-4 pb-16 pt-6 sm:px-6 lg:pt-8",
          width === "wide" ? "max-w-7xl" : "max-w-6xl"
        )}
      >
        {children}
      </main>
    </div>
  );
}

export function PageHeader({
  eyebrow,
  title,
  description,
  meta,
  actions,
  className,
}: {
  eyebrow?: React.ReactNode;
  title: React.ReactNode;
  description?: React.ReactNode;
  meta?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "mb-6 flex flex-col gap-4 lg:mb-8 lg:flex-row lg:items-end lg:justify-between",
        className
      )}
    >
      <div className="min-w-0 space-y-1.5">
        {eyebrow && <div className="text-[13px] text-fg-subtle">{eyebrow}</div>}
        <div className="flex flex-wrap items-center gap-2.5">
          <h1 className="text-xl font-semibold tracking-tight text-fg sm:text-[22px]">{title}</h1>
          {meta}
        </div>
        {description && (
          <p className="max-w-2xl text-sm leading-relaxed text-fg-subtle">{description}</p>
        )}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
