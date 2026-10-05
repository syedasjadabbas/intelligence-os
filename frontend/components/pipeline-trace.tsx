"use client";

import React, { useState } from "react";
import { TraceData } from "@/lib/api";
import {
  ChevronDown,
  ChevronUp,
  Activity,
  Zap,
  Layers,
  Sparkles,
  ShieldAlert,
  GitBranch,
  BarChart2,
} from "lucide-react";

interface PipelineTraceProps {
  trace: TraceData;
}

export function PipelineTrace({ trace }: PipelineTraceProps) {
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

  return (
    <div className="mt-3 rounded-xl border border-white/5 bg-slate-900/40 text-xs overflow-hidden transition-all">
      {/* Refusal Banner if guardrail triggered */}
      {trace.is_refusal && (
        <div className="p-3 bg-amber-500/10 border-b border-amber-500/20 text-amber-200 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-amber-400 shrink-0" />
            <span className="font-semibold">
              Grounded Refusal Guardrail Triggered
            </span>
          </div>
          <span className="text-[11px] px-2 py-0.5 rounded-full bg-amber-500/20 border border-amber-500/30 text-amber-300 font-medium">
            Zero Hallucination
          </span>
        </div>
      )}

      {/* Toggle Header Bar */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-3.5 py-2.5 flex items-center justify-between text-slate-400 hover:text-slate-200 hover:bg-slate-800/40 transition-colors cursor-pointer"
      >
        <div className="flex items-center gap-2">
          <Activity className="w-3.5 h-3.5 text-cyan-400" />
          <span className="font-medium text-slate-300">Pipeline Trace Telemetry</span>
          <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-slate-400 border border-slate-700/50">
            {latencies.total.toFixed(1)} ms
          </span>
          {isQueryRewritten && (
            <span className="px-1.5 py-0.5 rounded text-[10px] bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-medium">
              Rewritten
            </span>
          )}
        </div>

        <div className="flex items-center gap-1.5">
          <span className="text-[11px] text-slate-500">
            {isOpen ? "Hide Trace" : "View Trace"}
          </span>
          {isOpen ? (
            <ChevronUp className="w-3.5 h-3.5 text-slate-400" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
          )}
        </div>
      </button>

      {/* Collapsible Content */}
      {isOpen && (
        <div className="p-4 pt-2 border-t border-white/5 space-y-4 bg-slate-950/40">
          {/* Query Rewriting */}
          <div>
            <div className="flex items-center gap-1.5 text-slate-400 mb-1.5 font-medium">
              <GitBranch className="w-3.5 h-3.5 text-indigo-400" />
              <span>Query Understanding & Anaphora Resolution</span>
            </div>
            <div className="p-2.5 rounded-lg bg-slate-900/80 border border-slate-800 space-y-1.5 font-mono text-[11px]">
              <div className="flex items-start gap-2">
                <span className="text-slate-500 w-16 shrink-0">Original:</span>
                <span className="text-slate-300">{trace.original_query}</span>
              </div>
              <div className="flex items-start gap-2 pt-1 border-t border-slate-800/60">
                <span className="text-cyan-400 w-16 shrink-0 font-semibold">
                  Rewritten:
                </span>
                <span className="text-cyan-200">{trace.rewritten_query}</span>
              </div>
            </div>
          </div>

          {/* Latency Chips */}
          <div>
            <div className="flex items-center gap-1.5 text-slate-400 mb-1.5 font-medium">
              <Zap className="w-3.5 h-3.5 text-amber-400" />
              <span>Latency Metrics</span>
            </div>
            <div className="grid grid-cols-4 gap-2 text-center font-mono">
              <div className="p-2 rounded-lg bg-slate-900/60 border border-slate-800">
                <p className="text-[10px] text-slate-500">Hybrid Search</p>
                <p className="text-xs font-semibold text-cyan-300 mt-0.5">
                  {latencies.retrieval.toFixed(1)} ms
                </p>
              </div>
              <div className="p-2 rounded-lg bg-slate-900/60 border border-slate-800">
                <p className="text-[10px] text-slate-500">Reranker</p>
                <p className="text-xs font-semibold text-indigo-300 mt-0.5">
                  {latencies.rerank.toFixed(1)} ms
                </p>
              </div>
              <div className="p-2 rounded-lg bg-slate-900/60 border border-slate-800">
                <p className="text-[10px] text-slate-500">Generation</p>
                <p className="text-xs font-semibold text-emerald-300 mt-0.5">
                  {latencies.generation.toFixed(1)} ms
                </p>
              </div>
              <div className="p-2 rounded-lg bg-slate-900/60 border border-slate-800">
                <p className="text-[10px] text-slate-500">Total Latency</p>
                <p className="text-xs font-semibold text-white mt-0.5">
                  {latencies.total.toFixed(1)} ms
                </p>
              </div>
            </div>
          </div>

          {/* Candidate Funnel */}
          <div>
            <div className="flex items-center gap-1.5 text-slate-400 mb-1.5 font-medium">
              <Layers className="w-3.5 h-3.5 text-cyan-400" />
              <span>Candidate Retrieval Funnel</span>
            </div>
            <div className="p-2.5 rounded-lg bg-slate-900/60 border border-slate-800 flex items-center justify-around font-mono text-center">
              <div>
                <span className="text-[10px] text-slate-500 block">
                  Retrieved Candidates
                </span>
                <span className="text-sm font-bold text-slate-200">
                  {trace.retrieval_candidate_count || 0}
                </span>
              </div>
              <span className="text-slate-600">→</span>
              <div>
                <span className="text-[10px] text-slate-500 block">
                  Top K Reranked
                </span>
                <span className="text-sm font-bold text-indigo-300">
                  {trace.reranked_scores?.length || 0}
                </span>
              </div>
              <span className="text-slate-600">→</span>
              <div>
                <span className="text-[10px] text-slate-500 block">
                  Context Sources
                </span>
                <span className="text-sm font-bold text-cyan-300">
                  {trace.selected_sources?.length || 0}
                </span>
              </div>
            </div>
          </div>

          {/* Reranker Scores */}
          {trace.reranked_scores && trace.reranked_scores.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 text-slate-400 mb-1.5 font-medium">
                <BarChart2 className="w-3.5 h-3.5 text-emerald-400" />
                <span>Reranker Confidence Distribution</span>
              </div>
              <div className="p-2.5 rounded-lg bg-slate-900/60 border border-slate-800 space-y-2">
                {trace.reranked_scores.map((cand, idx) => {
                  const score = cand.rerank_score ?? cand.score;
                  const pct = Math.min(100, Math.max(5, score * 100));
                  return (
                    <div key={idx} className="space-y-1">
                      <div className="flex justify-between items-center text-[11px]">
                        <span className="text-slate-300 truncate max-w-[220px]">
                          {cand.document_title}
                        </span>
                        <span className="font-mono text-emerald-400">
                          {score.toFixed(4)}
                        </span>
                      </div>
                      <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                        <div
                          className="bg-gradient-to-r from-cyan-500 to-emerald-400 h-full rounded-full"
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
