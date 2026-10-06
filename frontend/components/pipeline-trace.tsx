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
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-zinc-900 hover:bg-zinc-850 text-zinc-500 hover:text-zinc-300 border border-zinc-800/80 hover:border-zinc-700 text-[11px] font-mono transition-all duration-150 cursor-pointer shadow-xs group"
          title="Toggle Pipeline Trace Telemetry"
        >
          <span className="text-amber-400/90">⚡</span>
          <span>
            {latencies.total ? `${latencies.total.toFixed(0)}ms` : "<150ms"}
          </span>
          <span className="text-zinc-700">•</span>
          <span>
            Hybrid Search ({candidateCount} {candidateCount === 1 ? "chunk" : "chunks"})
          </span>
          {isQueryRewritten && (
            <>
              <span className="text-zinc-700">•</span>
              <span className="text-indigo-400">Rewritten</span>
            </>
          )}
          <span className="text-zinc-600 group-hover:text-zinc-400 ml-0.5">
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
        <div className="mt-2.5 rounded-2xl border border-zinc-800/80 bg-zinc-900/60 backdrop-blur-md p-4 space-y-3.5 shadow-xl transition-all animate-in fade-in-50 duration-200 text-left w-full">
          {/* Query Rewriting */}
          {trace.rewritten_query && (
            <div>
              <div className="flex items-center gap-1.5 text-zinc-400 mb-1.5 font-medium text-[11px] uppercase tracking-wider">
                <GitBranch className="w-3 h-3 text-indigo-400" />
                <span>Query Expansion & Anaphora</span>
              </div>
              <div className="p-3 rounded-xl bg-zinc-950/80 border border-zinc-800/70 space-y-1.5 font-mono text-[11px]">
                {trace.original_query && (
                  <div className="flex items-start gap-2">
                    <span className="text-zinc-500 w-16 shrink-0">Original:</span>
                    <span className="text-zinc-300">{trace.original_query}</span>
                  </div>
                )}
                <div className="flex items-start gap-2 pt-1.5 border-t border-zinc-800/60">
                  <span className="text-indigo-400 w-16 shrink-0 font-medium">
                    Resolved:
                  </span>
                  <span className="text-zinc-100">{trace.rewritten_query}</span>
                </div>
              </div>
            </div>
          )}

          {/* Latency Breakdown */}
          <div>
            <div className="flex items-center gap-1.5 text-zinc-400 mb-1.5 font-medium text-[11px] uppercase tracking-wider">
              <Zap className="w-3 h-3 text-amber-400" />
              <span>Latency Profiler</span>
            </div>
            <div className="grid grid-cols-4 gap-2 text-center font-mono">
              <div className="p-2.5 rounded-xl bg-zinc-950/70 border border-zinc-800/70">
                <p className="text-[10px] text-zinc-500">Retrieval</p>
                <p className="text-xs font-semibold text-zinc-200 mt-0.5">
                  {latencies.retrieval ? `${latencies.retrieval.toFixed(1)}ms` : "—"}
                </p>
              </div>
              <div className="p-2.5 rounded-xl bg-zinc-950/70 border border-zinc-800/70">
                <p className="text-[10px] text-zinc-500">Rerank</p>
                <p className="text-xs font-semibold text-zinc-200 mt-0.5">
                  {latencies.rerank ? `${latencies.rerank.toFixed(1)}ms` : "—"}
                </p>
              </div>
              <div className="p-2.5 rounded-xl bg-zinc-950/70 border border-zinc-800/70">
                <p className="text-[10px] text-zinc-500">Generation</p>
                <p className="text-xs font-semibold text-zinc-200 mt-0.5">
                  {latencies.generation ? `${latencies.generation.toFixed(1)}ms` : "—"}
                </p>
              </div>
              <div className="p-2.5 rounded-xl bg-zinc-950/70 border border-zinc-800/70">
                <p className="text-[10px] text-zinc-500">Total</p>
                <p className="text-xs font-semibold text-indigo-400 mt-0.5">
                  {latencies.total ? `${latencies.total.toFixed(1)}ms` : "—"}
                </p>
              </div>
            </div>
          </div>

          {/* Candidate Funnel */}
          <div>
            <div className="flex items-center gap-1.5 text-zinc-400 mb-1.5 font-medium text-[11px] uppercase tracking-wider">
              <Layers className="w-3 h-3 text-purple-400" />
              <span>Retrieval Funnel</span>
            </div>
            <div className="p-2.5 rounded-xl bg-zinc-950/70 border border-zinc-800/70 flex items-center justify-around font-mono text-center">
              <div>
                <span className="text-[10px] text-zinc-500 block">
                  Candidates
                </span>
                <span className="text-sm font-semibold text-zinc-200">
                  {candidateCount}
                </span>
              </div>
              <span className="text-zinc-600">→</span>
              <div>
                <span className="text-[10px] text-zinc-500 block">
                  Reranked
                </span>
                <span className="text-sm font-semibold text-zinc-200">
                  {trace.reranked_scores?.length || candidateCount}
                </span>
              </div>
              <span className="text-zinc-600">→</span>
              <div>
                <span className="text-[10px] text-zinc-500 block">
                  Context Used
                </span>
                <span className="text-sm font-semibold text-indigo-400">
                  {trace.selected_sources?.length || 0}
                </span>
              </div>
            </div>
          </div>

          {/* Reranker Scores */}
          {trace.reranked_scores && trace.reranked_scores.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 text-zinc-400 mb-1.5 font-medium text-[11px] uppercase tracking-wider">
                <BarChart2 className="w-3 h-3 text-emerald-400" />
                <span>Cross-Encoder Confidence</span>
              </div>
              <div className="p-2.5 rounded-xl bg-zinc-950/70 border border-zinc-800/70 space-y-2">
                {trace.reranked_scores.map((cand, idx) => {
                  const score = cand.rerank_score ?? cand.score;
                  const pct = Math.min(100, Math.max(5, score * 100));
                  return (
                    <div key={idx} className="space-y-1">
                      <div className="flex justify-between items-center text-[11px]">
                        <span className="text-zinc-300 truncate max-w-[220px]">
                          {cand.document_title}
                        </span>
                        <span className="font-mono text-indigo-400 font-medium">
                          {score.toFixed(4)}
                        </span>
                      </div>
                      <div className="w-full bg-zinc-800 h-1 rounded-full overflow-hidden">
                        <div
                          className="bg-gradient-to-r from-indigo-500 to-purple-500 h-full rounded-full"
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
