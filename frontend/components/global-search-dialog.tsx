"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  Search,
  FileText,
  ArrowRight,
  Sparkles,
  Layers,
  X,
  AlertCircle,
  ExternalLink,
  ChevronRight,
} from "lucide-react";
import { api, SearchResultItem } from "@/lib/api";
import { cn, getErrorMessage } from "@/lib/utils";
import { Spinner } from "@/components/ui/spinner";
import { Kbd } from "@/components/ui/surface";

interface GlobalSearchDialogProps {
  isOpen: boolean;
  onClose: () => void;
}

const SUGGESTED_TOPICS = [
  "Arc Reactor cold fusion and palladium containment",
  "Iron Legion avionics neural mesh navigation",
  "Emergency cooling and liquid nitrogen cryogenic valves",
  "Mark LXXXV gold-titanium nanoparticle matrix",
];

export function GlobalSearchDialog({ isOpen, onClose }: GlobalSearchDialogProps) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [totalCandidates, setTotalCandidates] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedIndex, setSelectedIndex] = useState<number>(-1);
  const [hasSearched, setHasSearched] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);
  const resultsContainerRef = useRef<HTMLDivElement>(null);
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Focus input on open and reset state
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => {
        inputRef.current?.focus();
        inputRef.current?.select();
      }, 50);
      setSelectedIndex(-1);
    } else {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      setQuery("");
      setResults([]);
      setError(null);
      setHasSearched(false);
      setLoading(false);
    }
  }, [isOpen]);

  // Execute real backend hybrid search
  const performSearch = useCallback(async (searchQuery: string) => {
    const trimmed = searchQuery.trim();
    if (!trimmed) {
      setResults([]);
      setTotalCandidates(null);
      setError(null);
      setLoading(false);
      setHasSearched(false);
      return;
    }

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setLoading(true);
    setError(null);
    setHasSearched(true);

    try {
      const response = await api.searchDocuments({
        query: trimmed,
        top_k: 6,
        vector_weight: 0.5,
      });
      if (controller.signal.aborted) return;
      setResults(response.results || []);
      setTotalCandidates(response.total_candidates ?? response.results?.length ?? 0);
      setSelectedIndex(response.results?.length > 0 ? 0 : -1);
    } catch (err: any) {
      if (controller.signal.aborted || err?.name === "AbortError") return;
      setError(getErrorMessage(err) || "Failed to query knowledge base.");
      setResults([]);
      setTotalCandidates(null);
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false);
      }
    }
  }, []);

  // Debounced search on query change
  const handleQueryChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setQuery(val);

    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    if (!val.trim()) {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      setResults([]);
      setTotalCandidates(null);
      setError(null);
      setHasSearched(false);
      setLoading(false);
      return;
    }

    debounceTimerRef.current = setTimeout(() => {
      performSearch(val);
    }, 350);
  };

  // Navigate to full search page with the active query
  const handleOpenInFullSearch = useCallback((overrideQuery?: string) => {
    const targetQuery = (overrideQuery ?? query).trim();
    onClose();
    if (targetQuery) {
      router.push(`/search?q=${encodeURIComponent(targetQuery)}`);
    } else {
      router.push("/search");
    }
  }, [query, onClose, router]);

  // Keyboard navigation & execution
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      e.preventDefault();
      onClose();
      return;
    }

    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (results.length > 0) {
        setSelectedIndex((prev) => (prev + 1) % results.length);
      }
      return;
    }

    if (e.key === "ArrowUp") {
      e.preventDefault();
      if (results.length > 0) {
        setSelectedIndex((prev) => (prev <= 0 ? results.length - 1 : prev - 1));
      }
      return;
    }

    if (e.key === "Enter") {
      e.preventDefault();
      if (selectedIndex >= 0 && selectedIndex < results.length) {
        const selected = results[selectedIndex];
        handleOpenInFullSearch(selected.document_title || query);
      } else if (query.trim()) {
        handleOpenInFullSearch(query);
      }
    }
  };

  // Scroll selected item into view smoothly
  useEffect(() => {
    if (selectedIndex >= 0 && resultsContainerRef.current) {
      const activeEl = resultsContainerRef.current.children[selectedIndex] as HTMLElement;
      if (activeEl) {
        activeEl.scrollIntoView({ block: "nearest" });
      }
    }
  }, [selectedIndex]);

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="global-search-title"
      className="fixed inset-0 z-50 flex items-start justify-center px-4 pt-[10vh] sm:pt-[12vh]"
      onKeyDown={handleKeyDown}
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/75 backdrop-blur-xs transition-opacity animate-fade-in"
        onClick={onClose}
        aria-hidden
      />

      {/* Dialog Window */}
      <div className="relative z-10 flex w-full max-w-2xl flex-col overflow-hidden rounded-xl border border-[#232630] bg-[#101217] shadow-[0_24px_64px_-12px_rgba(0,0,0,0.85),0_0_0_1px_rgba(255,255,255,0.05)] animate-scale-in">
        {/* Header / Search Input */}
        <div className="flex items-center gap-3 border-b border-[#1e2027] bg-[#12141a] px-4 py-3.5">
          {loading ? (
            <Spinner className="size-4 shrink-0 text-accent" />
          ) : (
            <Search className="size-4 shrink-0 text-[#8b919e]" />
          )}

          <input
            id="global-search-title"
            ref={inputRef}
            type="text"
            value={query}
            onChange={handleQueryChange}
            placeholder="Search documents, section titles, and semantic chunks..."
            className="flex-1 bg-transparent text-sm text-[#f3f4f6] placeholder:text-[#5d6371] focus:outline-none"
            autoComplete="off"
            spellCheck="false"
          />

          {query && (
            <button
              type="button"
              onClick={() => {
                setQuery("");
                setResults([]);
                setHasSearched(false);
                inputRef.current?.focus();
              }}
              className="rounded p-1 text-[#6b7280] hover:text-[#e5e7eb] cursor-pointer"
              aria-label="Clear search query"
            >
              <X className="size-3.5" />
            </button>
          )}

          <button
            type="button"
            onClick={onClose}
            className="rounded border border-[#262832] bg-[#161820] px-1.5 py-0.5 text-[10px] font-mono font-medium text-[#8b919e] hover:text-white cursor-pointer"
          >
            ESC
          </button>
        </div>

        {/* Content Area */}
        <div
          ref={resultsContainerRef}
          className="max-h-[58vh] min-h-[160px] overflow-y-auto p-2"
        >
          {/* 1. Loading Skeleton */}
          {loading && results.length === 0 && (
            <div className="space-y-2 p-3">
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="rounded-lg border border-[#1e2028] bg-[#14161c] p-3 space-y-2 animate-pulse"
                >
                  <div className="h-3 w-1/3 rounded bg-[#222530]" />
                  <div className="h-2.5 w-4/5 rounded bg-[#1c1e26]" />
                </div>
              ))}
            </div>
          )}

          {/* 2. Error State */}
          {error && (
            <div className="m-2 flex items-start gap-3 rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-xs text-red-300">
              <AlertCircle className="size-4 shrink-0 text-red-400 mt-0.5" />
              <div className="flex-1">
                <p className="font-medium text-red-200">Search request failed</p>
                <p className="mt-0.5 text-red-300/80">{error}</p>
              </div>
              <button
                type="button"
                onClick={() => performSearch(query)}
                className="rounded bg-red-500/20 px-2 py-1 text-[11px] font-medium text-red-200 hover:bg-red-500/30 cursor-pointer"
              >
                Retry
              </button>
            </div>
          )}

          {/* 3. Empty Search Results */}
          {!loading && hasSearched && results.length === 0 && !error && (
            <div className="py-10 text-center">
              <FileText className="mx-auto size-8 text-[#4a505e]" />
              <p className="mt-2 text-sm font-medium text-[#e5e7eb]">No matching chunks found</p>
              <p className="mt-1 text-xs text-[#8b919e]">
                No verified document chunks matched &ldquo;{query}&rdquo; in the indexed store.
              </p>
              <button
                type="button"
                onClick={() => handleOpenInFullSearch(query)}
                className="mt-4 inline-flex items-center gap-1.5 rounded-md border border-[#2a2e3a] bg-[#161820] px-3 py-1.5 text-xs text-[#e5e7eb] hover:bg-[#1c1f28] hover:text-white cursor-pointer"
              >
                <span>Try Hybrid Search page</span>
                <ChevronRight className="size-3.5" />
              </button>
            </div>
          )}

          {/* 4. Real Results List */}
          {results.length > 0 && (
            <div className="space-y-1">
              <div className="flex items-center justify-between px-2.5 py-1 text-[11px] font-medium uppercase tracking-wider text-[#6b7280]">
                <span>Indexed Sources</span>
                {totalCandidates !== null && (
                  <span className="font-mono text-[10px]">
                    {totalCandidates} {totalCandidates === 1 ? "candidate" : "candidates"}
                  </span>
                )}
              </div>

              {results.map((item, idx) => {
                const isSelected = idx === selectedIndex;
                return (
                  <div
                    key={item.chunk_id || idx}
                    onClick={() => handleOpenInFullSearch(item.document_title || query)}
                    onMouseEnter={() => setSelectedIndex(idx)}
                    className={cn(
                      "group flex flex-col gap-1 rounded-lg p-3 text-left transition-colors cursor-pointer border",
                      isSelected
                        ? "border-[#2e3342] bg-[#181a22] text-white"
                        : "border-transparent bg-transparent hover:bg-[#14161c] text-[#d1d5db]"
                    )}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex min-w-0 items-center gap-2">
                        <FileText
                          className={cn(
                            "size-3.5 shrink-0",
                            isSelected ? "text-accent-strong" : "text-[#717784]"
                          )}
                        />
                        <span className="truncate text-xs font-medium text-[#f3f4f6]">
                          {item.document_title}
                        </span>
                        {item.page_number !== null && item.page_number !== undefined && (
                          <span className="rounded bg-[#1e212a] px-1.5 py-0.5 font-mono text-[10px] text-[#9ca3af]">
                            p.{item.page_number}
                          </span>
                        )}
                        {item.section_heading && (
                          <span className="hidden sm:inline truncate font-mono text-[11px] text-[#8b919e]">
                            · {item.section_heading}
                          </span>
                        )}
                      </div>

                      <div className="flex shrink-0 items-center gap-2 font-mono text-[10px]">
                        <span className="rounded border border-[#282c38] bg-[#14161c] px-1.5 py-0.5 text-[#8b919e]">
                          RRF {(item.score * 100).toFixed(0)}%
                        </span>
                        <ArrowRight
                          className={cn(
                            "size-3 text-[#6b7280] transition-transform",
                            isSelected && "translate-x-0.5 text-accent-strong"
                          )}
                        />
                      </div>
                    </div>

                    <p className="line-clamp-2 text-xs leading-relaxed text-[#9ca3af]">
                      {item.content}
                    </p>
                  </div>
                );
              })}
            </div>
          )}

          {/* 5. Initial State (Query empty) */}
          {!hasSearched && (
            <div className="p-2 space-y-4">
              <div>
                <p className="px-2 text-[11px] font-medium uppercase tracking-wider text-[#6b7280]">
                  Suggested Exploration Queries
                </p>
                <div className="mt-1.5 space-y-1">
                  {SUGGESTED_TOPICS.map((topic, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => {
                        setQuery(topic);
                        performSearch(topic);
                        inputRef.current?.focus();
                      }}
                      className="group flex w-full items-center justify-between rounded-lg px-2.5 py-2 text-left text-xs text-[#9ca3af] hover:bg-[#15171e] hover:text-[#f3f4f6] transition-colors cursor-pointer"
                    >
                      <div className="flex items-center gap-2">
                        <Sparkles className="size-3 text-[#6b7280] group-hover:text-accent-strong" />
                        <span>{topic}</span>
                      </div>
                      <ChevronRight className="size-3 text-[#505663] group-hover:text-[#9ca3af]" />
                    </button>
                  ))}
                </div>
              </div>

              <div className="border-t border-[#1c1f26] pt-3">
                <p className="px-2 text-[11px] font-medium uppercase tracking-wider text-[#6b7280]">
                  Direct Navigation
                </p>
                <div className="mt-1.5 grid grid-cols-2 gap-1">
                  <button
                    type="button"
                    onClick={() => {
                      onClose();
                      router.push("/documents");
                    }}
                    className="flex items-center gap-2 rounded-lg px-2.5 py-2 text-xs text-[#9ca3af] hover:bg-[#15171e] hover:text-white transition-colors cursor-pointer text-left"
                  >
                    <Layers className="size-3 text-[#6b7280]" />
                    <span>Documents Store</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      onClose();
                      router.push("/search");
                    }}
                    className="flex items-center gap-2 rounded-lg px-2.5 py-2 text-xs text-[#9ca3af] hover:bg-[#15171e] hover:text-white transition-colors cursor-pointer text-left"
                  >
                    <Search className="size-3 text-[#6b7280]" />
                    <span>Hybrid Search Engine</span>
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer Bar */}
        <div className="flex items-center justify-between border-t border-[#1e2027] bg-[#0d0e12] px-4 py-2.5 text-[11px] text-[#6b7280]">
          <div className="flex items-center gap-2">
            <span>
              <Kbd>↑</Kbd> <Kbd>↓</Kbd> to navigate
            </span>
            <span className="text-[#3b404d]">·</span>
            <span>
              <Kbd>↵</Kbd> to select
            </span>
            <span className="text-[#3b404d]">·</span>
            <span>
              <Kbd>Esc</Kbd> to close
            </span>
          </div>

          <button
            type="button"
            onClick={() => handleOpenInFullSearch(query)}
            className="inline-flex items-center gap-1 font-medium text-[#9ca3af] hover:text-white cursor-pointer transition-colors"
          >
            <span>Open in Search</span>
            <ExternalLink className="size-3" />
          </button>
        </div>
      </div>
    </div>
  );
}
