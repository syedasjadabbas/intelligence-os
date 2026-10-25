"use client";

import React, { useState, useEffect, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { api, SearchResultItem } from "@/lib/api";
import { cn, getErrorMessage } from "@/lib/utils";
import {
  Search as SearchIcon,
  Layers,
  Sparkles,
  SlidersHorizontal,
  FileText,
  Hash,
  Clock,
  ArrowUpDown,
  BookOpen,
} from "lucide-react";
import { AppShell, PageHeader } from "@/components/app-shell";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel, PanelHeader, EmptyState, Kbd } from "@/components/ui/surface";
import { Spinner } from "@/components/ui/spinner";

const SAMPLE_QUERIES = [
  "Arc Reactor cold fusion and palladium containment",
  "Iron Legion avionics neural mesh navigation",
  "Emergency cooling and liquid nitrogen cryogenic valves",
  "Mark LXXXV gold-titanium nanoparticle matrix",
  "Power distribution and superconducting bus conduits",
];

function SearchPageContent() {
  const { user } = useAuth();
  const searchParams = useSearchParams();
  const [query, setQuery] = useState("");
  const [activeQuery, setActiveQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const [vectorWeight, setVectorWeight] = useState(0.5);
  const [showFilters, setShowFilters] = useState(false);

  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [totalCandidates, setTotalCandidates] = useState<number | null>(null);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const executeSearch = useCallback(
    async (q: string) => {
      const trimmed = q.trim();
      if (!trimmed) return;

      setError(null);
      setLoading(true);
      setActiveQuery(trimmed);
      const t0 = performance.now();

      try {
        const response = await api.searchDocuments({
          query: trimmed,
          top_k: topK,
          vector_weight: vectorWeight,
        });
        setResults(response.results || []);
        setTotalCandidates(response.total_candidates ?? response.results?.length ?? 0);
        setLatencyMs(Math.round(performance.now() - t0));
      } catch (err: unknown) {
        setError(getErrorMessage(err) || "Failed to execute hybrid search.");
        setResults([]);
        setTotalCandidates(null);
      } finally {
        setLoading(false);
      }
    },
    [topK, vectorWeight]
  );

  // Read initial query from URL search parameters (e.g. from GlobalSearchDialog)
  useEffect(() => {
    const q = searchParams.get("q");
    if (q && q.trim()) {
      setQuery(q);
      executeSearch(q);
    }
  }, [searchParams, executeSearch]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    executeSearch(query);
  };

  return (
    <AppShell width="default">
      <PageHeader
        eyebrow="Retrieval engine"
        title="Hybrid Search"
        description="Query your knowledge store using parallel dense vector cosine similarity (pgvector) and full-text keyword search fused with Reciprocal Rank Fusion (RRF)."
        actions={
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setShowFilters((v) => !v)}
            aria-pressed={showFilters}
          >
            <SlidersHorizontal className="size-3.5" />
            <span>Search Parameters</span>
            {(topK !== 5 || vectorWeight !== 0.5) && (
              <span className="size-1.5 rounded-full bg-accent" />
            )}
          </Button>
        }
      />

      {/* Summary 4-KPI Metric Cards matching Reference Screenshot */}
      <div className="mb-6 grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
        <div className="metric-card-ref p-4.5">
          <div className="flex items-center gap-3">
            <div className="flex size-9 items-center justify-center rounded-full border border-white/10 bg-white/[0.05] text-white">
              <Layers className="size-4 text-[#ff7a45]" />
            </div>
            <span className="text-xs font-medium text-[#8e95a5]">Dense Semantic</span>
          </div>
          <div className="mt-3 font-mono text-2xl font-bold tracking-tight text-white">
            pgvector
          </div>
          <div className="mt-2.5 flex items-center gap-1.5 text-[11px] font-medium text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20 w-fit">
            <span className="size-1 rounded-full bg-emerald-400" />
            <span>Cosine similarity</span>
          </div>
        </div>

        <div className="metric-card-ref p-4.5">
          <div className="flex items-center gap-3">
            <div className="flex size-9 items-center justify-center rounded-full border border-white/10 bg-white/[0.05] text-white">
              <BookOpen className="size-4 text-[#5b5ff5]" />
            </div>
            <span className="text-xs font-medium text-[#8e95a5]">Sparse Lexical</span>
          </div>
          <div className="mt-3 font-mono text-2xl font-bold tracking-tight text-white">
            BM25 FTS
          </div>
          <div className="mt-2.5 flex items-center gap-1.5 text-[11px] font-medium text-[#8e95a5] bg-white/[0.04] px-2 py-0.5 rounded-full border border-white/10 w-fit">
            <span>tsvector stemmed</span>
          </div>
        </div>

        <div className="metric-card-ref p-4.5">
          <div className="flex items-center gap-3">
            <div className="flex size-9 items-center justify-center rounded-full border border-white/10 bg-white/[0.05] text-white">
              <Sparkles className="size-4 text-amber-400" />
            </div>
            <span className="text-xs font-medium text-[#8e95a5]">Hybrid Fusion</span>
          </div>
          <div className="mt-3 font-mono text-2xl font-bold tracking-tight text-white">
            RRF k=60
          </div>
          <div className="mt-2.5 flex items-center gap-1.5 text-[11px] font-medium text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded-full border border-amber-500/20 w-fit">
            <span>Rank reciprocal fusion</span>
          </div>
        </div>

        <div className="metric-card-ref p-4.5">
          <div className="flex items-center gap-3">
            <div className="flex size-9 items-center justify-center rounded-full border border-white/10 bg-white/[0.05] text-white">
              <Clock className="size-4 text-emerald-400" />
            </div>
            <span className="text-xs font-medium text-[#8e95a5]">Retrieval Speed</span>
          </div>
          <div className="mt-3 font-mono text-2xl font-bold tracking-tight text-white">
            {latencyMs !== null ? `${latencyMs}ms` : "< 45ms"}
          </div>
          <div className="mt-2.5 flex items-center gap-1.5 text-[11px] font-medium text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20 w-fit">
            <span>Sub-second grounding</span>
          </div>
        </div>
      </div>

      {/* Search Input Box */}
      <div className="relative mb-6">
        <form onSubmit={handleSubmit} className="inset-ref relative flex items-center rounded-2xl p-1.5 focus-within:border-white/20 transition-all">
          <div className="pointer-events-none absolute left-4 flex items-center text-[#636a7e]">
            <SearchIcon className="size-4.5" />
          </div>
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search across documents, headings, and semantic concepts..."
            className="h-11 w-full bg-transparent pl-11 pr-28 text-sm text-white placeholder:text-[#5a6072] focus:outline-none"
          />
          <div className="absolute right-2 flex items-center gap-1.5">
            <button
              type="submit"
              disabled={!query.trim() || loading}
              className="btn-accent-ref flex h-8 items-center gap-1.5 rounded-xl px-3.5 text-xs font-medium cursor-pointer disabled:opacity-30 disabled:pointer-events-none shadow-md"
            >
              {loading ? <Spinner className="size-3.5 text-white" /> : <SearchIcon className="size-3.5" />}
              <span>Search</span>
            </button>
          </div>
        </form>

        {/* Collapsible Tuning Drawer */}
        {showFilters && (
          <div className="panel-ref mt-3 p-4 animate-rise-in">
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
              <div>
                <div className="flex items-center justify-between text-xs mb-2">
                  <label htmlFor="top-k-slider" className="font-medium text-[#d1d5db]">
                    Result candidate count (Top K)
                  </label>
                  <span className="font-mono text-white font-semibold">{topK}</span>
                </div>
                <input
                  id="top-k-slider"
                  type="range"
                  min="1"
                  max="20"
                  value={topK}
                  onChange={(e) => setTopK(Number(e.target.value))}
                  className="w-full cursor-pointer accent-[#ff7a45]"
                />
                <p className="mt-1 text-[11px] text-[#8e95a5]">
                  Number of fused chunk candidates returned by the ranker.
                </p>
              </div>

              <div>
                <div className="flex items-center justify-between text-xs mb-2">
                  <label htmlFor="vector-weight-slider" className="font-medium text-[#d1d5db]">
                    Vector vs. Keyword Weight
                  </label>
                  <span className="font-mono text-white font-semibold">
                    {(vectorWeight * 100).toFixed(0)}% Vec / {((1 - vectorWeight) * 100).toFixed(0)}% KW
                  </span>
                </div>
                <input
                  id="vector-weight-slider"
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={vectorWeight}
                  onChange={(e) => setVectorWeight(Number(e.target.value))}
                  className="w-full cursor-pointer accent-[#ff7a45]"
                />
                <p className="mt-1 text-[11px] text-[#8e95a5]">
                  Balances dense semantic vector similarity vs BM25 keyword matching.
                </p>
              </div>
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="mb-6">
          <Alert tone="danger" title="Search execution failed">
            {error}
          </Alert>
        </div>
      )}

      {/* Live Result State */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="panel-ref p-5">
              <div className="flex items-center justify-between mb-2">
                <div className="h-4 w-48 rounded bg-white/5 skeleton" />
                <div className="h-4 w-20 rounded bg-white/5 skeleton" />
              </div>
              <div className="h-3 w-3/4 rounded bg-white/5 skeleton mb-2" />
              <div className="h-3 w-full rounded bg-white/5 skeleton" />
            </div>
          ))}
        </div>
      ) : activeQuery && results.length > 0 ? (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2 px-1">
            <div className="flex items-center gap-2 text-xs text-[#8e95a5]">
              <span>
                Found <strong className="text-white font-semibold">{totalCandidates}</strong> matching chunk candidates
              </span>
              <span>for</span>
              <span className="rounded-lg border border-white/10 bg-white/5 px-2 py-0.5 font-mono text-white">
                &quot;{activeQuery}&quot;
              </span>
            </div>
            {latencyMs !== null && (
              <span className="flex items-center gap-1 font-mono text-[11px] text-[#8e95a5]">
                <Clock className="size-3 text-emerald-400" />
                {latencyMs}ms roundtrip
              </span>
            )}
          </div>

          <div className="space-y-3">
            {results.map((item, idx) => (
              <div key={item.chunk_id || idx} className="panel-ref p-5 hover:border-white/20 transition-all">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="flex size-5 shrink-0 items-center justify-center rounded-lg bg-white/10 font-mono text-[11px] font-bold text-[#ff7a45]">
                        #{idx + 1}
                      </span>
                      <span className="flex items-center gap-1.5 font-semibold text-sm text-white truncate">
                        <FileText className="size-3.5 text-[#ff7a45] shrink-0" />
                        {item.document_title}
                      </span>
                      {item.page_number && (
                        <span className="rounded-md border border-white/10 bg-white/5 px-1.5 py-0.5 font-mono text-[10px] text-[#8e95a5]">
                          Page {item.page_number}
                        </span>
                      )}
                      {item.section_heading && (
                        <span className="rounded-md border border-white/10 bg-white/5 px-2 py-0.5 text-[11px] text-[#d1d5db] truncate max-w-[200px]">
                          {item.section_heading}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Rank & Score Pills */}
                  <div className="flex flex-wrap items-center gap-1.5 self-start shrink-0">
                    {item.vector_rank !== null && item.vector_rank !== undefined && (
                      <Badge tone="info" size="sm">
                        Vec #{item.vector_rank}
                      </Badge>
                    )}
                    {item.keyword_rank !== null && item.keyword_rank !== undefined && (
                      <Badge tone="neutral" size="sm">
                        FTS #{item.keyword_rank}
                      </Badge>
                    )}
                    <span className="rounded-md border border-white/10 bg-white/5 px-2 py-0.5 font-mono text-[11px] text-white font-medium">
                      RRF: {typeof item.score === "number" ? item.score.toFixed(4) : item.score}
                    </span>
                  </div>
                </div>

                {/* Content Snippet */}
                <div className="mt-3.5 rounded-xl border border-white/[0.06] bg-[#0c0d12] p-3.5 text-[13px] leading-relaxed text-[#d1d5db]">
                  <p className="whitespace-pre-wrap">{item.content}</p>
                </div>

                <div className="mt-2.5 flex items-center justify-between text-[11px] text-[#5a6072] font-mono">
                  <span className="truncate">Chunk: {item.chunk_id}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : activeQuery && results.length === 0 ? (
        <div className="panel-ref p-8">
          <EmptyState
            icon={<SearchIcon />}
            title="No relevant chunks found"
            description={`No document passages matched "${activeQuery}". Try adjusting search keywords, relaxing filters, or verifying that knowledge documents are fully indexed.`}
            action={
              <Button variant="secondary" size="sm" onClick={() => setQuery("")}>
                Clear Query
              </Button>
            }
          />
        </div>
      ) : (
        /* Helpful Empty State with Sample Queries */
        <div className="panel-ref p-6 sm:p-8">
          <div className="max-w-xl mx-auto text-center">
            <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-2xl border border-white/10 bg-gradient-to-b from-[#1c1f2b] to-[#12141c] text-[#ff7a45] shadow-lg">
              <Sparkles className="size-6" />
            </div>
            <h2 className="text-base font-bold text-white">Direct Knowledge Base Retrieval</h2>
            <p className="mt-1.5 text-xs text-[#8e95a5] leading-relaxed">
              Explore your organization&apos;s indexed chunks directly without LLM answer generation.
              Inspect how vector embeddings and full-text keyword ranks merge using Reciprocal Rank Fusion.
            </p>

            <div className="mt-6 text-left">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-[#636a7e] block mb-2.5">
                Suggested exploration queries
              </span>
              <div className="flex flex-col gap-2">
                {SAMPLE_QUERIES.map((sample) => (
                  <button
                    key={sample}
                    type="button"
                    onClick={() => {
                      setQuery(sample);
                      executeSearch(sample);
                    }}
                    className="flex items-center justify-between rounded-xl border border-white/[0.07] bg-[#0c0d12] px-3.5 py-2.5 text-xs text-[#d1d5db] hover:border-white/20 hover:bg-white/[0.03] hover:text-white transition-all text-left cursor-pointer"
                  >
                    <span>{sample}</span>
                    <ArrowUpDown className="size-3 text-[#636a7e] shrink-0 ml-2" />
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}

export default function SearchPage() {
  return (
    <Suspense
      fallback={
        <AppShell width="default">
          <div className="flex h-64 items-center justify-center">
            <Spinner className="size-6 text-accent" />
          </div>
        </AppShell>
      }
    >
      <SearchPageContent />
    </Suspense>
  );
}
