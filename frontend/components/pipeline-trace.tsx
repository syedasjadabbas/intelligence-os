"use client";

import React, { useState } from "react";
import { TraceData } from "@/lib/api";
import {
  ChevronDown,
  ChevronUp,
  Zap,
  Layers,
  GitBranch,
  BarChart2,
} from "lucide-react";

interface PipelineTraceProps {
  trace: TraceData;
  className?: string;
}

export function PipelineTrace({ trace, className }: PipelineTraceProps) {
  const [isOpen, setIsOpen] = useState(false);

  if (!trace) return null;

  const isQueryRewritten =
    trace.original_query &&
    trace.rewritten_query &&
    trace.original_query.trim().toLowerCase() !==
      trace.rewritten_query.trim().toLowerCase();

  const latencies = trace.latency_ms || {
    retrieval: 0,
    rerank: 0,
    generation: 0,
    total: 0,
  };

  const candidateCount =
    trace.retrieval_candidate_count ||
    (trace.reranked_scores ? trace.reranked_scores.length : 0);

  return (
    <div className={`text-xs font-sans ${className || "mt-2"}`}>
      {/* Refusal compact badge if guardrail triggered */}
      {trace.is_refusal && (
        <div className="mb-2 inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-300 text-[11px] font-mono">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
          <span>Refusal Guardrail Active • Zero Hallucination</span>
        </div>
      )}

      {/* Minimalist Telemetry Pill */}
      <div>
        <button
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-surface-2 hover:bg-surface-3 text-fg-subtle hover:text-fg-muted border border-line hover:border-line-strong text-[11px] font-mono transition-all duration-150 cursor-pointer shadow-xs group"
          title="Toggle Pipeline Trace Telemetry"
        >
          <span className="text-amber-400">⚡</span>
          <span>
            {latencies.total ? `${latencies.total.toFixed(0)}ms` : "<150ms"}
          </span>
          <span className="text-fg-faint">•</span>
          <span>
            Hybrid Search ({candidateCount} {candidateCount === 1 ? "chunk" : "chunks"})
          </span>
          {isQueryRewritten && (
            <>
              <span className="text-fg-faint">•</span>
              <span className="text-accent">Rewritten</span>
            </>
          )}
          <span className="text-fg-faint group-hover:text-fg-subtle ml-0.5">
            {isOpen ? (
              <ChevronUp className="w-3 h-3" />
            ) : (
              <ChevronDown className="w-3 h-3" />
            )}
          </span>
        </button>
      </div>

      {/* Smooth Accordion Expansion */}
      {isOpen && (
        <div className="mt-2.5 rounded-xl border border-line-strong bg-surface-2/95 backdrop-blur-md p-4 space-y-3.5 shadow-pop transition-all animate-rise-in text-left w-full">
          {/* Query Rewriting */}
          {trace.rewritten_query && (
            <div>
              <div className="flex items-center gap-1.5 text-fg-subtle mb-1.5 font-medium text-[11px] uppercase tracking-wider">
                <GitBranch className="w-3 h-3 text-accent" />
                <span>Query Expansion &amp; Anaphora</span>
              </div>
              <div className="p-3 rounded-lg bg-surface-3 border border-line space-y-1.5 font-mono text-[11px]">
                {trace.original_query && (
                  <div className="flex items-start gap-2">
                    <span className="text-fg-subtle w-16 shrink-0">Original:</span>
                    <span className="text-fg-muted">{trace.original_query}</span>
                  </div>
                )}
                <div className="flex items-start gap-2 pt-1.5 border-t border-line">
                  <span className="text-accent w-16 shrink-0 font-medium">
                    Resolved:
                  </span>
                  <span className="text-fg font-medium">{trace.rewritten_query}</span>
                </div>
              </div>
            </div>
          )}

          {/* Latency Breakdown */}
          <div>
            <div className="flex items-center gap-1.5 text-fg-subtle mb-1.5 font-medium text-[11px] uppercase tracking-wider">
              <Zap className="w-3 h-3 text-amber-400" />
              <span>Latency Profiler</span>
            </div>
            <div className="grid grid-cols-4 gap-2 text-center font-mono">
              <div className="p-2.5 rounded-lg bg-surface-3 border border-line">
                <p className="text-[10px] text-fg-subtle">Retrieval</p>
                <p className="text-xs font-semibold text-fg mt-0.5">
                  {latencies.retrieval ? `${latencies.retrieval.toFixed(1)}ms` : "—"}
                </p>
              </div>
              <div className="p-2.5 rounded-lg bg-surface-3 border border-line">
                <p className="text-[10px] text-fg-subtle">Rerank</p>
                <p className="text-xs font-semibold text-fg mt-0.5">
                  {latencies.rerank ? `${latencies.rerank.toFixed(1)}ms` : "—"}
                </p>
              </div>
              <div className="p-2.5 rounded-lg bg-surface-3 border border-line">
                <p className="text-[10px] text-fg-subtle">Generation</p>
                <p className="text-xs font-semibold text-fg mt-0.5">
                  {latencies.generation ? `${latencies.generation.toFixed(1)}ms` : "—"}
                </p>
              </div>
              <div className="p-2.5 rounded-lg bg-surface-3 border border-line">
                <p className="text-[10px] text-fg-subtle">Total</p>
                <p className="text-xs font-semibold text-accent mt-0.5">
                  {latencies.total ? `${latencies.total.toFixed(1)}ms` : "—"}
                </p>
              </div>
            </div>
          </div>

          {/* Candidate Funnel */}
          <div>
            <div className="flex items-center gap-1.5 text-fg-subtle mb-1.5 font-medium text-[11px] uppercase tracking-wider">
              <Layers className="w-3 h-3 text-purple-400" />
              <span>Retrieval Funnel</span>
            </div>
            <div className="p-2.5 rounded-lg bg-surface-3 border border-line flex items-center justify-around font-mono text-center">
              <div>
                <span className="text-[10px] text-fg-subtle block">
                  Candidates
                </span>
                <span className="text-sm font-semibold text-fg">
                  {candidateCount}
                </span>
              </div>
              <span className="text-fg-faint">→</span>
              <div>
                <span className="text-[10px] text-fg-subtle block">
                  Reranked
                </span>
                <span className="text-sm font-semibold text-fg">
                  {trace.reranked_scores?.length || candidateCount}
                </span>
              </div>
              <span className="text-fg-faint">→</span>
              <div>
                <span className="text-[10px] text-fg-subtle block">
                  Context Used
                </span>
                <span className="text-sm font-semibold text-accent">
                  {trace.selected_sources?.length || 0}
                </span>
              </div>
            </div>
          </div>

          {/* Reranker Scores */}
          {trace.reranked_scores && trace.reranked_scores.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 text-fg-subtle mb-1.5 font-medium text-[11px] uppercase tracking-wider">
                <BarChart2 className="w-3 h-3 text-emerald-400" />
                <span>Cross-Encoder Confidence</span>
              </div>
              <div className="p-2.5 rounded-lg bg-surface-3 border border-line space-y-2">
                {trace.reranked_scores.map((cand, idx) => {
                  const score = cand.rerank_score ?? cand.score;
                  const pct = Math.min(100, Math.max(5, score * 100));
                  return (
                    <div key={idx} className="space-y-1">
                      <div className="flex justify-between items-center text-[11px]">
                        <span className="text-fg-muted truncate max-w-[220px]">
                          {cand.document_title}
                        </span>
                        <span className="font-mono text-accent font-medium">
                          {score.toFixed(4)}
                        </span>
                      </div>
                      <div className="w-full bg-surface-4 h-1.5 rounded-full overflow-hidden">
                        <div
                          className="bg-accent h-full rounded-full transition-all duration-300"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
