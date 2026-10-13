import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Typed equivalent of reading `err?.message` from a caught value. Returns
 * undefined when the value carries no string message, so callers can keep
 * their `|| "fallback"` behavior unchanged.
 */
export function getErrorMessage(err: unknown): string | undefined {
  if (err && typeof err === "object" && "message" in err) {
    const { message } = err as { message: unknown };
    return typeof message === "string" ? message : undefined;
  }
  return undefined;
}

export function formatBytes(bytes: number, decimals = 1): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + " " + sizes[i];
}

/**
 * Parses an API timestamp. The backend serializes UTC datetimes without a
 * timezone designator (e.g. "2026-10-13T11:11:46.56"), which `new Date()`
 * would otherwise read as local time; those are treated as UTC here.
 */
export function parseApiDate(dateString: string): Date {
  const isNaiveIso =
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/.test(dateString);
  return new Date(isNaiveIso ? `${dateString}Z` : dateString);
}

/** Compact relative timestamp ("now", "5m", "3h", "2d", "Oct 4") for dense lists. */
export function formatRelativeTime(dateString: string): string {
  const time = parseApiDate(dateString).getTime();
  if (Number.isNaN(time)) return "";
  const diffSec = Math.max(0, (Date.now() - time) / 1000);
  if (diffSec < 60) return "now";
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h`;
  if (diffSec < 86400 * 7) return `${Math.floor(diffSec / 86400)}d`;
  return new Date(time).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function formatDate(dateString: string): string {
  try {
    const d = parseApiDate(dateString);
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return dateString;
  }
}
