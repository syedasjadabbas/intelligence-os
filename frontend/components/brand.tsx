import { cn } from "@/lib/utils";

/**
 * Intelligence OS mark: three ranked bars inside a frame — retrieval results
 * ordered by relevance, the core of the product.
 */
export function BrandMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={cn("size-6 shrink-0", className)}
      aria-hidden
      fill="none"
    >
      <rect x="0.75" y="0.75" width="22.5" height="22.5" rx="6" className="fill-surface-3 stroke-line-strong" strokeWidth="1.5" />
      <rect x="6" y="6.5" width="12" height="2.5" rx="1.25" className="fill-accent" />
      <rect x="6" y="10.75" width="8.5" height="2.5" rx="1.25" className="fill-accent" opacity="0.7" />
      <rect x="6" y="15" width="5" height="2.5" rx="1.25" className="fill-accent" opacity="0.4" />
    </svg>
  );
}

export function BrandWordmark({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <BrandMark />
      <span className="text-sm font-semibold tracking-tight text-fg">
        Intelligence<span className="text-fg-subtle font-medium"> OS</span>
      </span>
    </span>
  );
}
