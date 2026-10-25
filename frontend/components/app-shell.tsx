"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  ArrowRight,
  ChevronsUpDown,
  Database,
  FileText,
  LogOut,
  Menu,
  MessagesSquare,
  Search,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";
import { BrandMark } from "@/components/brand";
import { Badge } from "@/components/ui/badge";
import { Kbd } from "@/components/ui/surface";
import { GlobalSearchDialog } from "@/components/global-search-dialog";

export interface NavItem {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  isActive: (pathname: string) => boolean;
  badge?: string;
}

export interface NavGroup {
  title: string;
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    title: "WORKSPACE",
    items: [
      {
        href: "/",
        label: "Chat",
        icon: MessagesSquare,
        isActive: (p) => p === "/" || p === "/workspace",
      },
      {
        href: "/search",
        label: "Search",
        icon: Search,
        isActive: (p) => p.startsWith("/search"),
      },
    ],
  },
  {
    title: "KNOWLEDGE BASE",
    items: [
      {
        href: "/documents",
        label: "Documents",
        icon: FileText,
        isActive: (p) => p.startsWith("/documents"),
      },
      {
        href: "/evaluations/datasets",
        label: "Datasets",
        icon: Database,
        isActive: (p) => p.startsWith("/evaluations/datasets"),
      },
    ],
  },
  {
    title: "BENCHMARKS",
    items: [
      {
        href: "/evaluations",
        label: "Evaluations",
        icon: Activity,
        isActive: (p) => p.startsWith("/evaluations") && !p.startsWith("/evaluations/datasets"),
      },
    ],
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
        className="flex h-8 items-center gap-2 rounded-xl pl-1 pr-2 text-fg-muted transition-all hover:bg-white/[0.05] hover:text-fg cursor-pointer border border-transparent hover:border-white/[0.08]"
      >
        <span className="flex size-6.5 items-center justify-center rounded-full border border-white/10 bg-gradient-to-b from-[#222633] to-[#14161f] text-[11px] font-semibold text-white shadow-xs">
          {initial}
        </span>
        <span className="hidden text-xs font-medium text-[#d1d5db] sm:inline max-w-[100px] truncate">
          {user?.email?.split("@")[0] || "User"}
        </span>
        <ChevronsUpDown className="size-3 text-[#6b7280]" />
        <span className="sr-only">Account menu</span>
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 top-full z-50 mt-2 w-64 rounded-xl border border-white/[0.09] bg-[#12141c] p-1.5 shadow-[0_20px_50px_rgba(0,0,0,0.85)] animate-scale-in origin-top-right backdrop-blur-md"
        >
          <div className="px-3 py-2.5">
            <p className="truncate text-xs font-medium text-white">{user?.email || "—"}</p>
            <div className="mt-1.5 flex items-center gap-1.5">
              {user?.role && (
                <Badge tone={user.role === "ADMIN" ? "accent" : "neutral"}>
                  {user.role === "ADMIN" ? "Admin" : "Member"}
                </Badge>
              )}
              {org?.slug && (
                <span className="truncate font-mono text-[10px] text-[#8e95a5]">{org.slug}</span>
              )}
            </div>
          </div>
          <div className="my-1 h-px bg-white/[0.06]" />
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              logout();
            }}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs text-[#8e95a5] transition-colors hover:bg-white/[0.05] hover:text-white cursor-pointer"
          >
            <LogOut className="size-3.5" />
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}

/** Left sidebar navigation matching the reference image layout and aesthetics */
export function AppSidebar({
  className,
  onItemClick,
  onOpenSearch,
}: {
  className?: string;
  onItemClick?: () => void;
  onOpenSearch?: () => void;
}) {
  const pathname = usePathname() || "/";
  const { org } = useAuth();

  return (
    <aside
      className={cn(
        "flex flex-col w-60 shrink-0 border-r border-white/[0.07] bg-[#0c0e14] p-3.5 select-none",
        className
      )}
    >
      {/* Brand header */}
      <div className="flex items-center justify-between px-2 pt-1 pb-4">
        <Link
          href="/"
          onClick={onItemClick}
          className="flex items-center gap-2.5 transition-opacity hover:opacity-90"
          aria-label="Intelligence OS home"
        >
          <BrandMark className="size-6" />
          <div className="flex flex-col">
            <span className="text-sm font-semibold tracking-tight text-white leading-none">
              Intelligence <span className="font-normal text-[#8e95a5]">OS</span>
            </span>
          </div>
        </Link>
      </div>

      {/* Grouped navigation items */}
      <nav aria-label="Primary" className="flex-1 space-y-5 overflow-y-auto pt-1">
        {NAV_GROUPS.map((group) => (
          <div key={group.title} className="space-y-1">
            <div className="px-2.5 pb-1 text-[10px] font-semibold tracking-wider text-[#636a7e] uppercase">
              {group.title}
            </div>
            <div className="space-y-0.5">
              {group.items.map((item) => {
                const active = item.isActive(pathname);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={onItemClick}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "flex items-center justify-between rounded-xl px-2.5 py-2 text-xs font-medium transition-all duration-150 cursor-pointer",
                      active
                        ? "nav-pill-active"
                        : "text-[#8e95a5] hover:text-white hover:bg-white/[0.04] border border-transparent"
                    )}
                  >
                    <span className="flex items-center gap-2.5">
                      <item.icon
                        className={cn(
                          "size-4 shrink-0 transition-colors",
                          active ? "text-white" : "text-[#71788c]"
                        )}
                      />
                      <span>{item.label}</span>
                    </span>
                    {item.badge && (
                      <span className="rounded-md border border-white/10 bg-white/5 px-1.5 py-0.5 font-mono text-[10px] text-[#8e95a5]">
                        {item.badge}
                      </span>
                    )}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Bottom utility card matching reference's "Upgrade Pro!" container */}
      <div className="mt-auto pt-3">
        <div className="relative overflow-hidden rounded-2xl border border-white/[0.08] bg-gradient-to-b from-[#181b25] to-[#101218] p-3.5 shadow-lg">
          <div className="absolute top-0 inset-x-0 h-8 bg-gradient-to-b from-white/[0.06] to-transparent pointer-events-none" />
          <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-[#ff7a45]">
            <Sparkles className="size-3 shrink-0" />
            <span>Enterprise RAG</span>
          </div>
          <h3 className="mt-1 text-xs font-semibold text-white truncate" title={org?.name || "Acme Corp"}>
            {org?.name || "Acme Corp"}
          </h3>
          <p className="mt-0.5 text-[11px] leading-relaxed text-[#8e95a5]">
            Tenant isolated · Hybrid pgvector &amp; BM25 active.
          </p>
          <button
            type="button"
            onClick={onOpenSearch}
            className="btn-accent-ref mt-2.5 flex w-full items-center justify-center gap-1.5 rounded-lg py-1.5 text-xs font-medium cursor-pointer"
          >
            <span>Quick Query</span>
            <ArrowRight className="size-3" />
          </button>
        </div>
      </div>
    </aside>
  );
}

/** Global top bar rendered in the main content canvas */
export function TopBar({
  leading,
  center,
  trailing,
  onOpenMobileMenu,
  onOpenSearch,
}: {
  leading?: React.ReactNode;
  center?: React.ReactNode;
  trailing?: React.ReactNode;
  onOpenMobileMenu?: () => void;
  onOpenSearch?: () => void;
}) {
  const [isMac, setIsMac] = useState(false);

  useEffect(() => {
    setIsMac(/Mac|iPhone|iPad|iPod/.test(navigator.userAgent));
  }, []);

  return (
    <header className="relative z-30 flex h-14 shrink-0 items-center justify-between gap-3 border-b border-white/[0.06] bg-[#090a0f]/80 backdrop-blur-md px-4 sm:px-6">
      <div className="flex items-center gap-2.5 min-w-0">
        {onOpenMobileMenu && (
          <button
            type="button"
            onClick={onOpenMobileMenu}
            className="flex size-8 shrink-0 items-center justify-center rounded-lg border border-white/[0.08] bg-[#12141c] text-[#8e95a5] hover:text-white md:hidden cursor-pointer"
            aria-label="Open navigation sidebar"
          >
            <Menu className="size-4" />
          </button>
        )}
        {leading}
      </div>

      <div className="flex flex-1 justify-center max-w-md px-2">
        {center || (
          <button
            type="button"
            onClick={onOpenSearch}
            className="inset-ref group flex w-full items-center justify-between gap-2.5 rounded-xl px-3.5 py-1.5 text-xs text-[#8e95a5] hover:border-white/15 hover:text-white transition-all cursor-pointer"
            title={`Ask your knowledge base (${isMac ? "⌘K" : "Ctrl+K"})`}
          >
            <span className="flex min-w-0 items-center gap-2">
              <Search className="size-3.5 text-[#636a7e] group-hover:text-[#ff7a45] transition-colors" />
              <span className="truncate">Ask your knowledge base...</span>
            </span>
            <Kbd>{isMac ? "⌘K" : "Ctrl+K"}</Kbd>
          </button>
        )}
      </div>

      <div className="flex items-center gap-2.5 shrink-0">
        <div className="hidden sm:flex items-center gap-2 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-0.5 text-xs text-emerald-400">
          <span className="size-1.5 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-[11px] font-medium">RAG Online</span>
        </div>

        {trailing}

        <UserMenu />
      </div>
    </header>
  );
}

/** Standard layout for content pages: Left sidebar + top bar + framed content surface */
export function AppShell({
  children,
  width = "wide",
  fullHeight = false,
  leading,
}: {
  children: React.ReactNode;
  width?: "default" | "wide" | "full";
  fullHeight?: boolean;
  leading?: React.ReactNode;
}) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const mobileRef = useRef<HTMLDivElement>(null);
  useDismiss(mobileOpen, () => setMobileOpen(false), mobileRef);

  // Global ⌘K / Ctrl+K keyboard shortcut
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSearchOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#090a0f] text-[#f3f4f6]">
      {/* Desktop Left Sidebar */}
      <AppSidebar
        className="hidden md:flex"
        onOpenSearch={() => setSearchOpen(true)}
      />

      {/* Mobile Slide-over Drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 flex md:hidden" aria-modal="true" role="dialog">
          <div
            className="fixed inset-0 bg-black/70 backdrop-blur-xs animate-fade-in"
            onClick={() => setMobileOpen(false)}
            aria-hidden
          />
          <div
            ref={mobileRef}
            className="relative flex w-72 max-w-[85vw] flex-col bg-[#0c0e14] shadow-2xl animate-slide-in-right"
          >
            <div className="absolute right-2.5 top-3.5 z-10">
              <button
                type="button"
                onClick={() => setMobileOpen(false)}
                className="flex size-7 items-center justify-center rounded-lg text-[#8e95a5] hover:text-white hover:bg-white/[0.06] cursor-pointer"
                aria-label="Close menu"
              >
                <X className="size-4" />
              </button>
            </div>
            <AppSidebar
              className="w-full flex-1 border-r-0"
              onItemClick={() => setMobileOpen(false)}
              onOpenSearch={() => {
                setMobileOpen(false);
                setSearchOpen(true);
              }}
            />
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex flex-1 flex-col min-w-0 min-h-0 overflow-hidden bg-[#090a0f]">
        <TopBar
          leading={leading}
          onOpenMobileMenu={() => setMobileOpen(true)}
          onOpenSearch={() => setSearchOpen(true)}
        />
        <main
          className={cn(
            "flex-1 min-w-0",
            fullHeight ? "flex flex-col min-h-0 overflow-hidden" : "overflow-y-auto px-4 pb-16 pt-5 sm:px-6 sm:pt-6 lg:px-8",
            width === "default" && !fullHeight && "max-w-6xl mx-auto w-full",
            width === "wide" && !fullHeight && "max-w-7xl mx-auto w-full"
          )}
        >
          {children}
        </main>
      </div>

      {/* Global Command Palette Search Overlay */}
      <GlobalSearchDialog isOpen={searchOpen} onClose={() => setSearchOpen(false)} />
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
        "mb-6 flex flex-col gap-4 lg:mb-7 lg:flex-row lg:items-end lg:justify-between",
        className
      )}
    >
      <div className="min-w-0 space-y-1">
        {eyebrow && <div className="text-xs font-medium text-[#8e95a5] uppercase tracking-wider">{eyebrow}</div>}
        <div className="flex flex-wrap items-center gap-2.5">
          <h1 className="text-xl font-bold tracking-tight text-white sm:text-2xl">{title}</h1>
          {meta}
        </div>
        {description && (
          <p className="max-w-2xl text-xs sm:text-[13px] leading-relaxed text-[#8e95a5]">{description}</p>
        )}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
