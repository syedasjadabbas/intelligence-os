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
      <defs>
        <linearGradient id="brandGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#ff6a3d" />
          <stop offset="100%" stopColor="#ea3a0e" />
        </linearGradient>
        <linearGradient id="brandFrame" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#252936" />
          <stop offset="100%" stopColor="#14161f" />
        </linearGradient>
      </defs>
      <rect x="1" y="1" width="22" height="22" rx="6.5" fill="url(#brandFrame)" stroke="rgba(255,255,255,0.12)" strokeWidth="1" />
      <rect x="5.5" y="6" width="13" height="2.5" rx="1.25" fill="url(#brandGrad)" />
      <rect x="5.5" y="10.5" width="9.5" height="2.5" rx="1.25" fill="url(#brandGrad)" opacity="0.85" />
      <rect x="5.5" y="15" width="6" height="2.5" rx="1.25" fill="url(#brandGrad)" opacity="0.55" />
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
