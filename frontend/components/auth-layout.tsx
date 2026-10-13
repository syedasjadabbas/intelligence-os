import React from "react";
import { FileSearch, Quote, ShieldCheck } from "lucide-react";
import { BrandMark } from "@/components/brand";

const CAPABILITIES = [
  {
    icon: ShieldCheck,
    title: "Isolated by tenant",
    body: "Documents, vectors and conversations are scoped to your organization on every query.",
  },
  {
    icon: FileSearch,
    title: "Hybrid retrieval",
    body: "Vector and full-text search fused with reciprocal rank fusion, then reranked.",
  },
  {
    icon: Quote,
    title: "Grounded answers",
    body: "Responses are synthesized only from retrieved sources, with page-level citations.",
  },
];

export function AuthLayout({
  title,
  description,
  footer,
  children,
}: {
  title: string;
  description: string;
  footer: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="relative grid min-h-screen bg-canvas lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]">
      {/* Product context column */}
      <aside className="relative hidden overflow-hidden border-r border-line bg-surface lg:flex lg:flex-col lg:justify-between lg:p-12">
        <div className="bg-grid pointer-events-none absolute inset-0 opacity-60 [mask-image:linear-gradient(to_bottom,black,transparent_85%)]" />
        <div className="relative flex items-center gap-2.5">
          <BrandMark className="size-7" />
          <span className="text-[15px] font-semibold tracking-tight text-fg">
            Intelligence<span className="font-medium text-fg-subtle"> OS</span>
          </span>
        </div>

        <div className="relative max-w-md space-y-10">
          <div className="space-y-3">
            <h2 className="text-[28px] font-semibold leading-[1.15] tracking-tight text-fg text-balance">
              Answers your organization can verify.
            </h2>
            <p className="text-[15px] leading-relaxed text-fg-muted">
              A private retrieval workspace for enterprise knowledge — every response traced to the
              source document and page it came from.
            </p>
          </div>
          <ul className="space-y-5">
            {CAPABILITIES.map(({ icon: Icon, title: t, body }) => (
              <li key={t} className="flex gap-3.5">
                <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-md border border-line-strong bg-surface-2 text-accent">
                  <Icon className="size-4" />
                </span>
                <div>
                  <p className="text-sm font-medium text-fg">{t}</p>
                  <p className="mt-0.5 text-[13px] leading-relaxed text-fg-subtle">{body}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <p className="relative font-mono text-[11px] text-fg-faint">
          pgvector · hybrid RRF · cross-encoder rerank
        </p>
      </aside>

      {/* Form column */}
      <main className="flex items-center justify-center px-5 py-12 sm:px-8">
        <div className="w-full max-w-[380px] animate-rise-in">
          <div className="mb-8 flex items-center gap-2.5 lg:hidden">
            <BrandMark className="size-7" />
            <span className="text-[15px] font-semibold tracking-tight text-fg">
              Intelligence<span className="font-medium text-fg-subtle"> OS</span>
            </span>
          </div>

          <div className="mb-7 space-y-1.5">
            <h1 className="text-[22px] font-semibold tracking-tight text-fg">{title}</h1>
            <p className="text-sm leading-relaxed text-fg-subtle">{description}</p>
          </div>

          {children}

          <div className="mt-8 border-t border-line pt-6 text-[13px] text-fg-subtle">{footer}</div>
        </div>
      </main>
    </div>
  );
}
