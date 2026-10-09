"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import {
  api,
  EvaluationRunListItem,
  EvaluationComparisonResponse,
  MetricDelta,
  DatasetListItem,
} from "@/lib/api";
import { formatDate } from "@/lib/utils";
import {
  ArrowLeft,
  RefreshCw,
  Play,
  GitCompare,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
  Sparkles,
  Sliders,
  Cpu,
  BarChart3,
  Layers,
  Shield,
  Search,
  ExternalLink,
  ChevronRight,
  TrendingUp,
  TrendingDown,
  Info,
  X,
} from "lucide-react";

export default function EvaluationsDashboardPage() {
  const { user, org } = useAuth();
  const isAdmin = user?.role === "ADMIN";

  // Data states
  const [runs, setRuns] = useState<EvaluationRunListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [judgeFilter, setJudgeFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  // Selection for comparison
  const [selectedRunIds, setSelectedRunIds] = useState<string[]>([]);
  const [comparisonData, setComparisonData] =
    useState<EvaluationComparisonResponse | null>(null);
  const [comparing, setComparing] = useState(false);
  const [showComparisonModal, setShowComparisonModal] = useState(false);

  // Start Evaluation Modal state
  const [showRunModal, setShowRunModal] = useState(false);
  const [submittingRun, setSubmittingRun] = useState(false);
  const [datasets, setDatasets] = useState<DatasetListItem[]>([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>("");
  const [runDataset, setRunDataset] = useState("golden_dataset");
  const [runJudgeType, setRunJudgeType] = useState<"deterministic" | "llm">(
    "deterministic"
  );
  const [runLimit, setRunLimit] = useState<number>(50);
  const [runOffline, setRunOffline] = useState(true);
  const [runError, setRunError] = useState<string | null>(null);

  // Load custom datasets
  const fetchDatasets = useCallback(async () => {
    try {
      const res = await api.listDatasets({ limit: 100 });
      setDatasets(res.items || []);
    } catch (err: any) {
      console.error("Failed to load datasets:", err);
    }
  }, []);

  // Load runs
  const fetchRuns = useCallback(async (silent: boolean = false) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const res = await api.listEvaluations({
        limit: 50,
        judge_type: judgeFilter !== "all" ? judgeFilter : undefined,
        status: statusFilter !== "all" ? statusFilter : undefined,
      });
      setRuns(res.items || []);
    } catch (err: any) {
      setError(err.message || "Failed to load evaluation history.");
    } finally {
      if (!silent) setLoading(false);
    }
  }, [judgeFilter, statusFilter]);

  useEffect(() => {
    if (user) {
      fetchRuns();
      fetchDatasets();
    }
  }, [user, fetchRuns, fetchDatasets]);

  // Active runs auto-polling
  useEffect(() => {
    const hasActiveRuns = runs.some(
      (r) => r.status === "PENDING" || r.status === "RUNNING"
    );
    if (!hasActiveRuns) return;

    const intervalId = setInterval(() => {
      fetchRuns(true);
    }, 2500);

    return () => clearInterval(intervalId);
  }, [runs, fetchRuns]);

  // Handle run selection for comparison (max 2)
  const handleToggleSelectRun = (runId: string) => {
    if (selectedRunIds.includes(runId)) {
      setSelectedRunIds(selectedRunIds.filter((id) => id !== runId));
    } else {
      if (selectedRunIds.length >= 2) {
        setSelectedRunIds([selectedRunIds[1], runId]);
      } else {
        setSelectedRunIds([...selectedRunIds, runId]);
      }
    }
  };

  // Trigger run comparison
  const handleCompare = async () => {
    if (selectedRunIds.length !== 2) return;
    setComparing(true);
    setRunError(null);
    try {
      // base = older run, target = newer run
      const runA = runs.find((r) => r.id === selectedRunIds[0]);
      const runB = runs.find((r) => r.id === selectedRunIds[1]);
      let baseId = selectedRunIds[0];
      let targetId = selectedRunIds[1];
      if (
        runA &&
        runB &&
        new Date(runA.created_at) > new Date(runB.created_at)
      ) {
        baseId = selectedRunIds[1];
        targetId = selectedRunIds[0];
      }

      const res = await api.compareEvaluations(baseId, targetId);
      setComparisonData(res);
      setShowComparisonModal(true);
    } catch (err: any) {
      setError(err.message || "Failed to compare evaluation runs.");
    } finally {
      setComparing(false);
    }
  };

  // Start new evaluation run
  const handleStartRun = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isAdmin) {
      setRunError("Organization ADMIN privileges required to start evaluations.");
      return;
    }
    setSubmittingRun(true);
    setRunError(null);
    try {
      const isCustom = Boolean(selectedDatasetId && selectedDatasetId !== "golden_dataset");
      const customDs = isCustom ? datasets.find((d) => d.id === selectedDatasetId) : null;

      await api.createEvaluation({
        dataset_name: isCustom && customDs ? customDs.name : runDataset,
        dataset_id: isCustom ? selectedDatasetId : undefined,
        judge_type: runJudgeType,
        limit: runLimit > 0 ? runLimit : undefined,
        offline: runJudgeType === "deterministic" ? runOffline : false,
      });
      setShowRunModal(false);
      await fetchRuns();
    } catch (err: any) {
      setRunError(err.message || "Failed to execute evaluation run.");
    } finally {
      setSubmittingRun(false);
    }
  };

  // Latest completed run for summary stats
  const latestRun = runs.find((r) => r.status === "COMPLETED") || runs[0];

  const renderDeltaBadge = (deltaItem: MetricDelta, isLatency: boolean = false) => {
    if (deltaItem.delta === null || deltaItem.delta === undefined) {
      return <span className="text-zinc-500 text-xs">—</span>;
    }
    const isImproved = deltaItem.status === "improved";
    const isRegressed = deltaItem.status === "regressed";

    const sign = deltaItem.delta > 0 ? "+" : "";
    const formattedVal = isLatency
      ? `${sign}${deltaItem.delta.toFixed(1)}ms`
      : `${sign}${(deltaItem.delta * (isLatency ? 1 : 100)).toFixed(1)}%`;

    if (isImproved) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
          <TrendingUp className="w-3 h-3" />
          {formattedVal}
        </span>
      );
    }
    if (isRegressed) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-rose-500/15 text-rose-400 border border-rose-500/30">
          <TrendingDown className="w-3 h-3" />
          {formattedVal}
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-zinc-800 text-zinc-400 border border-zinc-700">
        0.0%
      </span>
    );
  };

  return (
    <div className="min-h-screen bg-[#090d16] text-slate-100 flex flex-col font-sans">
      {/* Top Navigation Header */}
      <header className="border-b border-slate-800/80 bg-[#0d131f] px-6 py-3.5 flex items-center justify-between sticky top-0 z-30 backdrop-blur-md">
        <div className="flex items-center gap-4">
          <Link
            href="/workspace"
            className="p-1.5 px-2.5 rounded-lg bg-slate-800/80 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-700/60 transition-colors flex items-center gap-1.5 text-xs font-medium cursor-pointer"
          >
            <ArrowLeft className="w-4 h-4 text-slate-400" />
            <span>Back to Workspace</span>
          </Link>
          <div className="h-5 w-px bg-slate-800" />
          <div>
            <h1 className="text-base font-semibold text-white flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-indigo-400" />
              RAG Evaluation Dashboard
            </h1>
            <p className="text-[11px] text-slate-400">
              Deterministic & LLM quality evaluation, retrieval metrics, and regression testing
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {org && (
            <div className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs flex items-center gap-2">
              <Shield className="w-3.5 h-3.5 text-slate-400" />
              <span className="text-slate-400">Tenant:</span>
              <span className="font-semibold text-white">{org.name}</span>
            </div>
          )}

          {selectedRunIds.length === 2 && (
            <button
              onClick={handleCompare}
              disabled={comparing}
              className="py-1.5 px-3 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium flex items-center gap-1.5 transition-all shadow-sm cursor-pointer"
            >
              <GitCompare className="w-3.5 h-3.5" />
              <span>{comparing ? "Comparing..." : "Compare Selected (2)"}</span>
            </button>
          )}

          <Link
            href="/evaluations/datasets"
            className="py-1.5 px-3 rounded-lg bg-slate-800/90 hover:bg-slate-700 text-slate-200 hover:text-white text-xs font-medium flex items-center gap-1.5 transition-colors border border-slate-700/60 cursor-pointer"
            title="Manage custom datasets and test cases"
          >
            <Layers className="w-3.5 h-3.5 text-indigo-400" />
            <span>Datasets</span>
          </Link>

          <button
            onClick={() => {
              setRunError(null);
              fetchDatasets();
              setShowRunModal(true);
            }}
            className="py-1.5 px-3.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-1.5 transition-all shadow-sm cursor-pointer"
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            <span>Start Evaluation</span>
          </button>

          <button
            onClick={() => fetchRuns()}
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors cursor-pointer border border-slate-700/60"
            title="Refresh runs"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 space-y-6">
        {/* Error Alert */}
        {error && (
          <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2.5">
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
            <span className="flex-1">{error}</span>
            <button
              onClick={() => setError(null)}
              className="text-rose-400 hover:text-rose-200"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Aggregate Metric Cards (Latest Run Snapshot) */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-2">
              <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
              Latest Run Benchmark Metrics
            </h2>
            {latestRun && (
              <span className="text-[11px] text-slate-400">
                Based on Run <span className="font-mono text-slate-300">{latestRun.id.slice(0, 8)}</span> ({formatDate(latestRun.created_at)})
              </span>
            )}
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
            {/* Pass Rate */}
            <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800 flex flex-col justify-between">
              <span className="text-[11px] text-slate-400 font-medium">Pass Rate</span>
              <div className="mt-2 flex items-baseline gap-1">
                <span className="text-xl font-bold text-emerald-400">
                  {latestRun ? `${(latestRun.pass_rate * 100).toFixed(1)}%` : "—"}
                </span>
              </div>
              <span className="text-[10px] text-slate-500 mt-1">
                {latestRun ? `${latestRun.passed_test_cases}/${latestRun.total_test_cases} passed` : "No runs"}
              </span>
            </div>

            {/* Recall@5 */}
            <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800 flex flex-col justify-between">
              <span className="text-[11px] text-slate-400 font-medium">Recall@5</span>
              <div className="mt-2">
                <span className="text-xl font-bold text-white">
                  {latestRun?.recall_at_5 !== undefined && latestRun.recall_at_5 !== null
                    ? latestRun.recall_at_5.toFixed(3)
                    : "—"}
                </span>
              </div>
              <span className="text-[10px] text-slate-500 mt-1">Target ≥ 0.95</span>
            </div>

            {/* nDCG@5 */}
            <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800 flex flex-col justify-between">
              <span className="text-[11px] text-slate-400 font-medium">nDCG@5</span>
              <div className="mt-2">
                <span className="text-xl font-bold text-white">
                  {latestRun?.ndcg_at_5 !== undefined && latestRun.ndcg_at_5 !== null
                    ? latestRun.ndcg_at_5.toFixed(3)
                    : "—"}
                </span>
              </div>
              <span className="text-[10px] text-slate-500 mt-1">Ranking quality</span>
            </div>

            {/* MRR */}
            <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800 flex flex-col justify-between">
              <span className="text-[11px] text-slate-400 font-medium">MRR</span>
              <div className="mt-2">
                <span className="text-xl font-bold text-white">
                  {latestRun?.mrr !== undefined && latestRun.mrr !== null
                    ? latestRun.mrr.toFixed(3)
                    : "—"}
                </span>
              </div>
              <span className="text-[10px] text-slate-500 mt-1">Reciprocal rank</span>
            </div>

            {/* Faithfulness */}
            <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800 flex flex-col justify-between">
              <span className="text-[11px] text-slate-400 font-medium">Faithfulness</span>
              <div className="mt-2">
                <span className="text-xl font-bold text-indigo-400">
                  {latestRun?.mean_faithfulness !== undefined && latestRun.mean_faithfulness !== null
                    ? latestRun.mean_faithfulness.toFixed(3)
                    : "—"}
                </span>
              </div>
              <span className="text-[10px] text-slate-500 mt-1">Zero-hallucination</span>
            </div>

            {/* Correctness */}
            <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800 flex flex-col justify-between">
              <span className="text-[11px] text-slate-400 font-medium">Correctness</span>
              <div className="mt-2">
                <span className="text-xl font-bold text-white">
                  {latestRun?.mean_correctness !== undefined && latestRun.mean_correctness !== null
                    ? latestRun.mean_correctness.toFixed(3)
                    : "—"}
                </span>
              </div>
              <span className="text-[10px] text-slate-500 mt-1">Factual accuracy</span>
            </div>

            {/* Completeness */}
            <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800 flex flex-col justify-between">
              <span className="text-[11px] text-slate-400 font-medium">Completeness</span>
              <div className="mt-2">
                <span className="text-xl font-bold text-white">
                  {latestRun?.mean_completeness !== undefined && latestRun.mean_completeness !== null
                    ? latestRun.mean_completeness.toFixed(3)
                    : "—"}
                </span>
              </div>
              <span className="text-[10px] text-slate-500 mt-1">Key point coverage</span>
            </div>

            {/* Mean Latency */}
            <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800 flex flex-col justify-between">
              <span className="text-[11px] text-slate-400 font-medium">Mean Latency</span>
              <div className="mt-2">
                <span className="text-xl font-bold text-amber-400">
                  {latestRun?.mean_latency_ms !== undefined && latestRun.mean_latency_ms !== null
                    ? `${Math.round(latestRun.mean_latency_ms)}ms`
                    : "—"}
                </span>
              </div>
              <span className="text-[10px] text-slate-500 mt-1">
                P95: {latestRun?.latency_p95_ms ? `${Math.round(latestRun.latency_p95_ms)}ms` : "—"}
              </span>
            </div>
          </div>
        </div>

        {/* Evaluation History Section */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 space-y-4">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white uppercase tracking-wider flex items-center gap-2">
                <Clock className="w-4 h-4 text-slate-400" />
                Evaluation Run History
              </h2>
              <p className="text-xs text-slate-400">
                Select any two runs to compare regressions or inspect individual case results.
              </p>
            </div>

            {/* Filters */}
            <div className="flex items-center gap-2.5">
              <div className="flex items-center gap-1.5 text-xs text-slate-400 bg-slate-950 px-2.5 py-1.5 rounded-lg border border-slate-800">
                <span>Judge:</span>
                <select
                  value={judgeFilter}
                  onChange={(e) => setJudgeFilter(e.target.value)}
                  className="bg-transparent text-white font-medium focus:outline-none cursor-pointer"
                >
                  <option value="all" className="bg-slate-900">All Judges</option>
                  <option value="deterministic" className="bg-slate-900">Deterministic</option>
                  <option value="llm" className="bg-slate-900">LLM Judge</option>
                </select>
              </div>

              <div className="flex items-center gap-1.5 text-xs text-slate-400 bg-slate-950 px-2.5 py-1.5 rounded-lg border border-slate-800">
                <span>Status:</span>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="bg-transparent text-white font-medium focus:outline-none cursor-pointer"
                >
                  <option value="all" className="bg-slate-900">All Statuses</option>
                  <option value="COMPLETED" className="bg-slate-900">Completed</option>
                  <option value="RUNNING" className="bg-slate-900">Running</option>
                  <option value="FAILED" className="bg-slate-900">Failed</option>
                </select>
              </div>
            </div>
          </div>

          {/* Table */}
          <div className="overflow-x-auto rounded-lg border border-slate-800">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950/80 text-slate-400 border-b border-slate-800 uppercase tracking-wider text-[10px]">
                <tr>
                  <th className="p-3 w-10 text-center">
                    <span className="sr-only">Select</span>
                  </th>
                  <th className="p-3 font-semibold">Run ID</th>
                  <th className="p-3 font-semibold">Date</th>
                  <th className="p-3 font-semibold">Dataset</th>
                  <th className="p-3 font-semibold">Cases</th>
                  <th className="p-3 font-semibold">Judge</th>
                  <th className="p-3 font-semibold">Pass Rate</th>
                  <th className="p-3 font-semibold">Recall@5</th>
                  <th className="p-3 font-semibold">nDCG@5</th>
                  <th className="p-3 font-semibold">Faithfulness</th>
                  <th className="p-3 font-semibold">Status</th>
                  <th className="p-3 text-right font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-sans">
                {loading ? (
                  <tr>
                    <td colSpan={12} className="p-8 text-center text-slate-400">
                      <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-indigo-400" />
                      Loading evaluation history...
                    </td>
                  </tr>
                ) : runs.length === 0 ? (
                  <tr>
                    <td colSpan={12} className="p-8 text-center text-slate-400">
                      No evaluation runs found. Click "Start Evaluation" to run your first benchmark.
                    </td>
                  </tr>
                ) : (
                  runs.map((r) => {
                    const isSelected = selectedRunIds.includes(r.id);
                    return (
                      <tr
                        key={r.id}
                        className={`hover:bg-slate-800/40 transition-colors ${
                          isSelected ? "bg-indigo-950/20" : ""
                        }`}
                      >
                        <td className="p-3 text-center">
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => handleToggleSelectRun(r.id)}
                            className="rounded border-slate-700 bg-slate-900 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                            title="Select for comparison"
                          />
                        </td>
                        <td className="p-3 font-mono font-medium text-slate-200">
                          {r.id.slice(0, 8)}
                        </td>
                        <td className="p-3 text-slate-400 whitespace-nowrap">
                          {formatDate(r.created_at)}
                        </td>
                        <td className="p-3 text-slate-300 font-medium">
                          <div className="flex items-center gap-1.5">
                            <span>{r.dataset_name}</span>
                            <span className="text-[10px] text-slate-500">v{r.dataset_version}</span>
                            {r.dataset_id ? (
                              <span className="text-[9px] px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-semibold uppercase">
                                Custom
                              </span>
                            ) : null}
                          </div>
                        </td>
                        <td className="p-3 text-slate-300">
                          {r.status === "COMPLETED" ? (
                            `${r.passed_test_cases}/${r.total_test_cases}`
                          ) : r.status === "RUNNING" ? (
                            <span className="text-blue-400 font-mono text-xs">
                              {r.progress_current ?? 0}/{r.progress_total || r.total_test_cases} done
                            </span>
                          ) : r.status === "PENDING" ? (
                            <span className="text-amber-400/80 font-mono text-xs">
                              Queued ({r.total_test_cases})
                            </span>
                          ) : (
                            <span className="text-slate-400 font-mono text-xs">
                              {r.progress_current ?? 0}/{r.total_test_cases}
                            </span>
                          )}
                        </td>
                        <td className="p-3">
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium border ${
                              r.judge_type === "llm"
                                ? "bg-purple-500/15 text-purple-300 border-purple-500/30"
                                : "bg-cyan-500/15 text-cyan-300 border-cyan-500/30"
                            }`}
                          >
                            {r.judge_type === "llm" ? "LLM Judge" : "Deterministic"}
                          </span>
                        </td>
                        <td className="p-3">
                          {r.status === "COMPLETED" ? (
                            <span
                              className={`font-semibold ${
                                r.pass_rate >= 0.95
                                  ? "text-emerald-400"
                                  : r.pass_rate >= 0.8
                                  ? "text-amber-400"
                                  : "text-rose-400"
                              }`}
                            >
                              {(r.pass_rate * 100).toFixed(1)}%
                            </span>
                          ) : (
                            <span className="text-slate-500 text-xs">—</span>
                          )}
                        </td>
                        <td className="p-3 font-mono text-slate-300">
                          {r.recall_at_5 !== null && r.recall_at_5 !== undefined
                            ? r.recall_at_5.toFixed(3)
                            : "—"}
                        </td>
                        <td className="p-3 font-mono text-slate-300">
                          {r.ndcg_at_5 !== null && r.ndcg_at_5 !== undefined
                            ? r.ndcg_at_5.toFixed(3)
                            : "—"}
                        </td>
                        <td className="p-3 font-mono text-indigo-300">
                          {r.mean_faithfulness !== null && r.mean_faithfulness !== undefined
                            ? r.mean_faithfulness.toFixed(3)
                            : "—"}
                        </td>
                        <td className="p-3">
                          {r.status === "COMPLETED" ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                              <CheckCircle2 className="w-3 h-3" />
                              COMPLETED
                            </span>
                          ) : r.status === "RUNNING" ? (
                            <div className="flex flex-col gap-1">
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-blue-500/15 text-blue-400 border border-blue-500/30 animate-pulse">
                                <RefreshCw className="w-3 h-3 animate-spin" />
                                RUNNING {r.progress_total ? `(${r.progress_current ?? 0}/${r.progress_total})` : ""}
                              </span>
                              {r.progress_total && r.progress_total > 0 && (
                                <div className="w-24 bg-slate-800 rounded-full h-1 overflow-hidden">
                                  <div
                                    className="bg-blue-500 h-1 rounded-full transition-all duration-300"
                                    style={{
                                      width: `${Math.min(
                                        100,
                                        Math.round(((r.progress_current ?? 0) / r.progress_total) * 100)
                                      )}%`,
                                    }}
                                  />
                                </div>
                              )}
                            </div>
                          ) : r.status === "PENDING" ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-500/15 text-amber-400 border border-amber-500/30">
                              <Clock className="w-3 h-3" />
                              QUEUED
                            </span>
                          ) : (
                            <div className="flex flex-col gap-0.5">
                              <span
                                className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-rose-500/15 text-rose-400 border border-rose-500/30"
                                title={r.error_message || undefined}
                              >
                                <XCircle className="w-3 h-3" />
                                FAILED
                              </span>
                              {r.error_message && (
                                <span
                                  className="text-[10px] text-rose-400/80 truncate max-w-[130px]"
                                  title={r.error_message}
                                >
                                  {r.error_message}
                                </span>
                              )}
                            </div>
                          )}
                        </td>
                        <td className="p-3 text-right">
                          <Link
                            href={`/evaluations/${r.id}`}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 hover:text-white border border-slate-700/60 font-medium transition-colors"
                          >
                            <span>Inspect</span>
                            <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
                          </Link>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </main>

      {/* ========================================================================= */}
      {/* START EVALUATION RUN MODAL                                                */}
      {/* ========================================================================= */}
      {showRunModal && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-xs flex items-center justify-center z-50 p-4">
          <div className="bg-[#0e1422] border border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl relative space-y-5 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  <Play className="w-4 h-4 fill-current" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-white">
                    Start Evaluation Benchmark Run
                  </h3>
                  <p className="text-[11px] text-slate-400">
                    Execute RAG quality evaluation against the golden benchmark dataset.
                  </p>
                </div>
              </div>
              <button
                onClick={() => setShowRunModal(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {runError && (
              <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
                <span>{runError}</span>
              </div>
            )}

            <form onSubmit={handleStartRun} className="space-y-4">
              {/* Dataset Selection */}
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-xs font-medium text-slate-300">
                    Benchmark Dataset
                  </label>
                  <Link
                    href="/evaluations/datasets"
                    className="text-[11px] text-indigo-400 hover:text-indigo-300 inline-flex items-center gap-1"
                  >
                    <span>Manage datasets &rarr;</span>
                  </Link>
                </div>
                <select
                  value={selectedDatasetId}
                  onChange={(e) => {
                    const val = e.target.value;
                    setSelectedDatasetId(val);
                    if (!val || val === "golden_dataset") {
                      setRunDataset("golden_dataset");
                      setRunLimit(50);
                    } else {
                      const found = datasets.find((d) => d.id === val);
                      if (found) {
                        setRunDataset(found.name);
                        setRunLimit(Math.max(1, Math.min(found.test_case_count || 1, 50)));
                      }
                    }
                  }}
                  className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                >
                  <option value="golden_dataset">
                    golden_dataset.json (Built-in 50 cases - Multi-Hop, Coreference, Refusal)
                  </option>
                  {datasets.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name} v{d.version} ({d.test_case_count} cases) {d.description ? `— ${d.description}` : ""}
                    </option>
                  ))}
                </select>
              </div>

              {/* Judge Mode Selector */}
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">
                  Evaluation Judge Mode
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <div
                    onClick={() => setRunJudgeType("deterministic")}
                    className={`p-3 rounded-xl border cursor-pointer transition-all ${
                      runJudgeType === "deterministic"
                        ? "border-cyan-500 bg-cyan-500/10 text-cyan-200"
                        : "border-slate-800 bg-slate-900/60 text-slate-400 hover:border-slate-700"
                    }`}
                  >
                    <div className="flex items-center gap-2 font-semibold text-xs mb-1">
                      <Cpu className="w-4 h-4 text-cyan-400" />
                      <span>Deterministic Judge</span>
                    </div>
                    <p className="text-[11px] text-slate-400">
                      Strict semantic anchor matching, zero API quota consumed, instant execution.
                    </p>
                  </div>

                  <div
                    onClick={() => setRunJudgeType("llm")}
                    className={`p-3 rounded-xl border cursor-pointer transition-all ${
                      runJudgeType === "llm"
                        ? "border-purple-500 bg-purple-500/10 text-purple-200"
                        : "border-slate-800 bg-slate-900/60 text-slate-400 hover:border-slate-700"
                    }`}
                  >
                    <div className="flex items-center gap-2 font-semibold text-xs mb-1">
                      <Sparkles className="w-4 h-4 text-purple-400" />
                      <span>LLM Judge</span>
                    </div>
                    <p className="text-[11px] text-slate-400">
                      Gemini 2.5 Flash as a judge for deep qualitative reasoning and hallucination checks.
                    </p>
                  </div>
                </div>
              </div>

              {/* Quota Warning for LLM Judge */}
              {runJudgeType === "llm" && (
                <div className="p-3 rounded-xl bg-purple-500/10 border border-purple-500/30 text-purple-300 text-xs flex items-start gap-2.5">
                  <AlertTriangle className="w-4 h-4 text-purple-400 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-semibold block">External Model Quota Notice</span>
                    <span className="text-[11px] text-purple-300/80">
                      LLM-as-a-Judge invokes Google Gemini API for each test case. Ensure valid GEMINI_API_KEY credentials with available rate limit quota.
                    </span>
                  </div>
                </div>
              )}

              {/* Limit Slider / Presets */}
              {(() => {
                const isCustom = Boolean(selectedDatasetId && selectedDatasetId !== "golden_dataset");
                const customDs = isCustom ? datasets.find((d) => d.id === selectedDatasetId) : null;
                const maxAvailable = isCustom && customDs ? Math.max(1, customDs.test_case_count) : 50;
                const presetList = [5, 10, 25, 50].filter((p) => p <= maxAvailable);
                if (!presetList.includes(maxAvailable)) {
                  presetList.push(maxAvailable);
                  presetList.sort((a, b) => a - b);
                }

                return (
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <label className="text-xs font-medium text-slate-300">
                        Test Case Limit
                      </label>
                      <span className="text-xs font-mono font-semibold text-indigo-400">
                        {runLimit} of {maxAvailable} cases
                      </span>
                    </div>
                    {presetList.length > 1 && (
                      <div className="flex items-center gap-2 mb-2 flex-wrap">
                        {presetList.map((preset) => (
                          <button
                            key={preset}
                            type="button"
                            onClick={() => setRunLimit(preset)}
                            className={`px-2.5 py-1 rounded text-xs font-medium border transition-colors ${
                              runLimit === preset
                                ? "bg-indigo-600 text-white border-indigo-500"
                                : "bg-slate-900 text-slate-400 border-slate-800 hover:border-slate-700 hover:text-white"
                            }`}
                          >
                            {preset === maxAvailable ? `All (${maxAvailable})` : preset}
                          </button>
                        ))}
                      </div>
                    )}
                    <input
                      type="range"
                      min="1"
                      max={maxAvailable}
                      value={Math.min(runLimit, maxAvailable)}
                      onChange={(e) => setRunLimit(Number(e.target.value))}
                      className="w-full accent-indigo-500 cursor-pointer"
                    />
                  </div>
                );
              })()}

              {/* Offline mode toggle for deterministic */}
              {runJudgeType === "deterministic" && (
                <div className="flex items-center justify-between p-3 rounded-xl bg-slate-900 border border-slate-800">
                  <div>
                    <span className="text-xs font-medium text-slate-200 block">
                      Deterministic Offline Mode
                    </span>
                    <span className="text-[11px] text-slate-400 block">
                      Uses feature-hashing embeddings without network dependencies.
                    </span>
                  </div>
                  <input
                    type="checkbox"
                    checked={runOffline}
                    onChange={(e) => setRunOffline(e.target.checked)}
                    className="rounded border-slate-700 bg-slate-800 text-indigo-600 focus:ring-indigo-500 h-4 w-4 cursor-pointer"
                  />
                </div>
              )}

              {!isAdmin && (
                <div className="p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs flex items-center gap-2">
                  <Shield className="w-4 h-4 text-amber-400" />
                  <span>Admin privileges required to start evaluations.</span>
                </div>
              )}

              {/* Actions */}
              <div className="pt-2 flex items-center justify-end gap-2.5">
                <button
                  type="button"
                  onClick={() => setShowRunModal(false)}
                  disabled={submittingRun}
                  className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-xs font-medium transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingRun || !isAdmin}
                  className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-xs font-semibold flex items-center gap-2 transition-all shadow-sm cursor-pointer"
                >
                  {submittingRun ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Executing Evaluation...</span>
                    </>
                  ) : (
                    <>
                      <Play className="w-3.5 h-3.5 fill-current" />
                      <span>Run Benchmark ({runLimit} Cases)</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* RUN COMPARISON MODAL                                                      */}
      {/* ========================================================================= */}
      {showComparisonModal && comparisonData && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-xs flex items-center justify-center z-50 p-4">
          <div className="bg-[#0e1422] border border-slate-800 rounded-2xl max-w-3xl w-full p-6 shadow-2xl relative space-y-5 animate-in fade-in zoom-in-95 duration-150 max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800 shrink-0">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                  <GitCompare className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-white">
                    Side-by-Side Run Comparison
                  </h3>
                  <p className="text-[11px] text-slate-400">
                    Comparing Baseline Run vs Target Run to detect improvements and regressions.
                  </p>
                </div>
              </div>
              <button
                onClick={() => setShowComparisonModal(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Regression Summary Banner */}
            <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-between text-xs shrink-0">
              <div className="flex items-center gap-4">
                <div>
                  <span className="text-slate-400 block text-[11px]">Baseline Run:</span>
                  <span className="font-mono font-medium text-white">
                    {comparisonData.base_run.id.slice(0, 8)} ({formatDate(comparisonData.base_run.created_at)})
                  </span>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-600" />
                <div>
                  <span className="text-slate-400 block text-[11px]">Target Run:</span>
                  <span className="font-mono font-medium text-white">
                    {comparisonData.target_run.id.slice(0, 8)} ({formatDate(comparisonData.target_run.created_at)})
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <div className="text-right">
                  <span className="text-[10px] uppercase font-semibold text-rose-400 block">
                    Regressed Cases
                  </span>
                  <span className="font-mono font-bold text-sm text-rose-300">
                    {comparisonData.regressed_cases_count}
                  </span>
                </div>
                <div className="text-right">
                  <span className="text-[10px] uppercase font-semibold text-emerald-400 block">
                    Improved Cases
                  </span>
                  <span className="font-mono font-bold text-sm text-emerald-300">
                    {comparisonData.improved_cases_count}
                  </span>
                </div>
              </div>
            </div>

            {/* Metrics Delta Table */}
            <div className="flex-1 overflow-y-auto border border-slate-800 rounded-lg">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-950/80 text-slate-400 border-b border-slate-800 uppercase tracking-wider text-[10px] sticky top-0">
                  <tr>
                    <th className="p-3 font-semibold">Metric</th>
                    <th className="p-3 font-semibold">Baseline</th>
                    <th className="p-3 font-semibold">Target</th>
                    <th className="p-3 font-semibold">Delta</th>
                    <th className="p-3 text-right font-semibold">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-sans">
                  {/* Pass Rate */}
                  <tr className="hover:bg-slate-800/30">
                    <td className="p-3 font-medium text-slate-200">Pass Rate</td>
                    <td className="p-3 font-mono text-slate-400">
                      {((comparisonData.deltas.pass_rate.base_value || 0) * 100).toFixed(1)}%
                    </td>
                    <td className="p-3 font-mono text-slate-200">
                      {((comparisonData.deltas.pass_rate.target_value || 0) * 100).toFixed(1)}%
                    </td>
                    <td className="p-3">
                      {renderDeltaBadge(comparisonData.deltas.pass_rate)}
                    </td>
                    <td className="p-3 text-right uppercase text-[10px] font-semibold text-slate-400">
                      {comparisonData.deltas.pass_rate.status}
                    </td>
                  </tr>

                  {/* Recall@3 */}
                  <tr className="hover:bg-slate-800/30">
                    <td className="p-3 font-medium text-slate-200">Recall@3</td>
                    <td className="p-3 font-mono text-slate-400">
                      {comparisonData.deltas.recall_at_3.base_value?.toFixed(3) || "—"}
                    </td>
                    <td className="p-3 font-mono text-slate-200">
                      {comparisonData.deltas.recall_at_3.target_value?.toFixed(3) || "—"}
                    </td>
                    <td className="p-3">
                      {renderDeltaBadge(comparisonData.deltas.recall_at_3)}
                    </td>
                    <td className="p-3 text-right uppercase text-[10px] font-semibold text-slate-400">
                      {comparisonData.deltas.recall_at_3.status}
                    </td>
                  </tr>

                  {/* Recall@5 */}
                  <tr className="hover:bg-slate-800/30">
                    <td className="p-3 font-medium text-slate-200">Recall@5</td>
                    <td className="p-3 font-mono text-slate-400">
                      {comparisonData.deltas.recall_at_5.base_value?.toFixed(3) || "—"}
                    </td>
                    <td className="p-3 font-mono text-slate-200">
                      {comparisonData.deltas.recall_at_5.target_value?.toFixed(3) || "—"}
                    </td>
                    <td className="p-3">
                      {renderDeltaBadge(comparisonData.deltas.recall_at_5)}
                    </td>
                    <td className="p-3 text-right uppercase text-[10px] font-semibold text-slate-400">
                      {comparisonData.deltas.recall_at_5.status}
                    </td>
                  </tr>

                  {/* MRR */}
                  <tr className="hover:bg-slate-800/30">
                    <td className="p-3 font-medium text-slate-200">MRR</td>
                    <td className="p-3 font-mono text-slate-400">
                      {comparisonData.deltas.mrr.base_value?.toFixed(3) || "—"}
                    </td>
                    <td className="p-3 font-mono text-slate-200">
                      {comparisonData.deltas.mrr.target_value?.toFixed(3) || "—"}
                    </td>
                    <td className="p-3">
                      {renderDeltaBadge(comparisonData.deltas.mrr)}
                    </td>
                    <td className="p-3 text-right uppercase text-[10px] font-semibold text-slate-400">
                      {comparisonData.deltas.mrr.status}
                    </td>
                  </tr>

                  {/* nDCG@5 */}
                  <tr className="hover:bg-slate-800/30">
                    <td className="p-3 font-medium text-slate-200">nDCG@5</td>
                    <td className="p-3 font-mono text-slate-400">
                      {comparisonData.deltas.ndcg_at_5.base_value?.toFixed(3) || "—"}
                    </td>
                    <td className="p-3 font-mono text-slate-200">
                      {comparisonData.deltas.ndcg_at_5.target_value?.toFixed(3) || "—"}
                    </td>
                    <td className="p-3">
                      {renderDeltaBadge(comparisonData.deltas.ndcg_at_5)}
                    </td>
                    <td className="p-3 text-right uppercase text-[10px] font-semibold text-slate-400">
                      {comparisonData.deltas.ndcg_at_5.status}
                    </td>
                  </tr>

                  {/* Faithfulness */}
                  <tr className="hover:bg-slate-800/30">
                    <td className="p-3 font-medium text-slate-200">Faithfulness</td>
                    <td className="p-3 font-mono text-slate-400">
                      {comparisonData.deltas.mean_faithfulness.base_value?.toFixed(3) || "—"}
                    </td>
                    <td className="p-3 font-mono text-slate-200">
                      {comparisonData.deltas.mean_faithfulness.target_value?.toFixed(3) || "—"}
                    </td>
                    <td className="p-3">
                      {renderDeltaBadge(comparisonData.deltas.mean_faithfulness)}
                    </td>
                    <td className="p-3 text-right uppercase text-[10px] font-semibold text-slate-400">
                      {comparisonData.deltas.mean_faithfulness.status}
                    </td>
                  </tr>

                  {/* Correctness */}
                  <tr className="hover:bg-slate-800/30">
                    <td className="p-3 font-medium text-slate-200">Correctness</td>
                    <td className="p-3 font-mono text-slate-400">
                      {comparisonData.deltas.mean_correctness.base_value?.toFixed(3) || "—"}
                    </td>
                    <td className="p-3 font-mono text-slate-200">
                      {comparisonData.deltas.mean_correctness.target_value?.toFixed(3) || "—"}
                    </td>
                    <td className="p-3">
                      {renderDeltaBadge(comparisonData.deltas.mean_correctness)}
                    </td>
                    <td className="p-3 text-right uppercase text-[10px] font-semibold text-slate-400">
                      {comparisonData.deltas.mean_correctness.status}
                    </td>
                  </tr>

                  {/* Completeness */}
                  <tr className="hover:bg-slate-800/30">
                    <td className="p-3 font-medium text-slate-200">Completeness</td>
                    <td className="p-3 font-mono text-slate-400">
                      {comparisonData.deltas.mean_completeness.base_value?.toFixed(3) || "—"}
                    </td>
                    <td className="p-3 font-mono text-slate-200">
                      {comparisonData.deltas.mean_completeness.target_value?.toFixed(3) || "—"}
                    </td>
                    <td className="p-3">
                      {renderDeltaBadge(comparisonData.deltas.mean_completeness)}
                    </td>
                    <td className="p-3 text-right uppercase text-[10px] font-semibold text-slate-400">
                      {comparisonData.deltas.mean_completeness.status}
                    </td>
                  </tr>

                  {/* Mean Latency */}
                  <tr className="hover:bg-slate-800/30">
                    <td className="p-3 font-medium text-slate-200">Mean Latency</td>
                    <td className="p-3 font-mono text-slate-400">
                      {comparisonData.deltas.mean_latency_ms.base_value ? `${Math.round(comparisonData.deltas.mean_latency_ms.base_value)}ms` : "—"}
                    </td>
                    <td className="p-3 font-mono text-slate-200">
                      {comparisonData.deltas.mean_latency_ms.target_value ? `${Math.round(comparisonData.deltas.mean_latency_ms.target_value)}ms` : "—"}
                    </td>
                    <td className="p-3">
                      {renderDeltaBadge(comparisonData.deltas.mean_latency_ms, true)}
                    </td>
                    <td className="p-3 text-right uppercase text-[10px] font-semibold text-slate-400">
                      {comparisonData.deltas.mean_latency_ms.status}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div className="pt-2 flex justify-end shrink-0">
              <button
                onClick={() => setShowComparisonModal(false)}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-xs font-medium cursor-pointer transition-colors"
              >
                Close Comparison
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
