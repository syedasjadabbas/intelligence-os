"use client";

import React, { useState, useEffect, useCallback, use } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import {
  api,
  EvaluationRunDetail,
  EvaluationResultListItem,
  EvaluationResultDetail,
} from "@/lib/api";
import { formatDate } from "@/lib/utils";
import {
  ArrowLeft,
  RefreshCw,
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
  FileText,
  Filter,
  Check,
  ChevronLeft,
} from "lucide-react";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function EvaluationRunDetailPage({ params }: PageProps) {
  const resolvedParams = use(params);
  const runId = resolvedParams.id;

  const { user, org } = useAuth();

  // Run detail state
  const [run, setRun] = useState<EvaluationRunDetail | null>(null);
  const [loadingRun, setLoadingRun] = useState(true);
  const [runError, setRunError] = useState<string | null>(null);

  // Results list state
  const [results, setResults] = useState<EvaluationResultListItem[]>([]);
  const [totalResults, setTotalResults] = useState(0);
  const [loadingResults, setLoadingResults] = useState(true);
  const [page, setPage] = useState(1);
  const pageSize = 20;

  // Filters
  const [statusFilter, setStatusFilter] = useState<"all" | "passed" | "failed">("all");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");

  // Case Inspection Drawer / Modal
  const [selectedResultId, setSelectedResultId] = useState<string | null>(null);
  const [inspectingResult, setInspectingResult] =
    useState<EvaluationResultDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [detailTab, setDetailTab] = useState<"overview" | "chunks" | "judge">("overview");

  // Fetch Run Details
  const fetchRunDetail = useCallback(async (silent: boolean = false) => {
    if (!silent) setLoadingRun(true);
    setRunError(null);
    try {
      const data = await api.getEvaluation(runId);
      setRun(data);
    } catch (err: any) {
      setRunError(err.message || "Failed to load evaluation run details.");
    } finally {
      if (!silent) setLoadingRun(false);
    }
  }, [runId]);

  // Fetch Results List
  const fetchResults = useCallback(async (silent: boolean = false) => {
    if (!silent) setLoadingResults(true);
    try {
      const passedParam =
        statusFilter === "passed"
          ? true
          : statusFilter === "failed"
          ? false
          : undefined;

      const categoryParam = categoryFilter !== "all" ? categoryFilter : undefined;

      const res = await api.listEvaluationResults(runId, {
        skip: (page - 1) * pageSize,
        limit: pageSize,
        passed: passedParam,
        query_type: categoryParam,
      });

      setResults(res.items || []);
      setTotalResults(res.total || 0);
    } catch (err: any) {
      console.error("Failed to fetch evaluation results:", err);
    } finally {
      if (!silent) setLoadingResults(false);
    }
  }, [runId, page, statusFilter, categoryFilter]);

  useEffect(() => {
    if (user && runId) {
      fetchRunDetail();
      fetchResults();
    }
  }, [user, runId, fetchRunDetail, fetchResults]);

  // Auto-polling when run is active
  useEffect(() => {
    if (!run || (run.status !== "PENDING" && run.status !== "RUNNING")) return;

    const intervalId = setInterval(() => {
      fetchRunDetail(true);
      fetchResults(true);
    }, 2500);

    return () => clearInterval(intervalId);
  }, [run, fetchRunDetail, fetchResults]);

  // Fetch individual result detail on inspection
  const handleInspectCase = async (resultId: string) => {
    setSelectedResultId(resultId);
    setLoadingDetail(true);
    setDetailTab("overview");
    try {
      const detail = await api.getEvaluationResult(runId, resultId);
      setInspectingResult(detail);
    } catch (err: any) {
      console.error("Failed to inspect evaluation result:", err);
    } finally {
      setLoadingDetail(false);
    }
  };

  // Filtered in-memory search for query text
  const filteredResults = searchQuery.trim()
    ? results.filter(
        (r) =>
          r.query.toLowerCase().includes(searchQuery.toLowerCase()) ||
          r.test_case_id.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : results;

  // Categories list
  const categories = [
    "all",
    "single_hop",
    "multi_hop",
    "coreference_followup",
    "retrieval_hard",
    "semantic_search",
    "citation_sensitive",
    "unanswerable",
  ];

  const failedCount =
    run && run.total_test_cases > 0
      ? run.total_test_cases - run.passed_test_cases
      : 0;

  return (
    <div className="min-h-screen bg-[#090d16] text-slate-100 flex flex-col font-sans">
      {/* Top Header */}
      <header className="border-b border-slate-800/80 bg-[#0d131f] px-6 py-3.5 flex items-center justify-between sticky top-0 z-30 backdrop-blur-md">
        <div className="flex items-center gap-4">
          <Link
            href="/evaluations"
            className="p-1.5 px-2.5 rounded-lg bg-slate-800/80 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-700/60 transition-colors flex items-center gap-1.5 text-xs font-medium cursor-pointer"
          >
            <ArrowLeft className="w-4 h-4 text-slate-400" />
            <span>All Evaluations</span>
          </Link>
          <div className="h-5 w-px bg-slate-800" />
          <div>
            <h1 className="text-base font-semibold text-white flex items-center gap-2">
              <span className="font-mono text-indigo-400">Run {runId.slice(0, 8)}</span>
              {run && (
                <span className="text-xs px-2 py-0.5 rounded font-normal bg-slate-800 text-slate-300 border border-slate-700">
                  {run.dataset_name} v{run.dataset_version}
                </span>
              )}
            </h1>
            <p className="text-[11px] text-slate-400">
              Benchmark execution details, candidate rankings, grounding evidence, and judge diagnostics
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {run && (
            <div className="flex items-center gap-2">
              <span
                className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold border ${
                  run.judge_type === "llm"
                    ? "bg-purple-500/15 text-purple-300 border-purple-500/30"
                    : "bg-cyan-500/15 text-cyan-300 border-cyan-500/30"
                }`}
              >
                {run.judge_type === "llm" ? "LLM Judge" : "Deterministic Judge"}
              </span>
              <span
                className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border ${
                  run.status === "COMPLETED"
                    ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
                    : run.status === "RUNNING"
                    ? "bg-blue-500/15 text-blue-400 border-blue-500/30 animate-pulse"
                    : run.status === "PENDING"
                    ? "bg-amber-500/15 text-amber-400 border-amber-500/30"
                    : "bg-rose-500/15 text-rose-400 border-rose-500/30"
                }`}
              >
                {run.status === "COMPLETED" ? (
                  <CheckCircle2 className="w-3.5 h-3.5" />
                ) : run.status === "RUNNING" ? (
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                ) : run.status === "PENDING" ? (
                  <Clock className="w-3.5 h-3.5" />
                ) : (
                  <XCircle className="w-3.5 h-3.5" />
                )}
                {run.status === "PENDING"
                  ? "QUEUED"
                  : run.status === "RUNNING"
                  ? `RUNNING (${run.progress_current ?? 0}/${run.progress_total || run.total_test_cases})`
                  : run.status}
              </span>
            </div>
          )}

          <button
            onClick={() => {
              fetchRunDetail();
              fetchResults();
            }}
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors cursor-pointer border border-slate-700/60"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loadingRun ? "animate-spin" : ""}`} />
          </button>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 space-y-6">
        {runError && (
          <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2.5">
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{runError}</span>
          </div>
        )}

        {/* Live Progress Banner when RUNNING */}
        {run && run.status === "RUNNING" && (
          <div className="p-4 rounded-xl border border-blue-500/30 bg-blue-500/10 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 animate-in fade-in">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-lg bg-blue-500/20 text-blue-400 border border-blue-500/30">
                <RefreshCw className="w-5 h-5 animate-spin" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-white">
                  Evaluation Run in Progress
                </h3>
                <p className="text-xs text-blue-200/80">
                  Executing benchmark cases and evaluating retrieval & generation quality in background...
                </p>
              </div>
            </div>
            <div className="w-full sm:w-64 flex flex-col gap-1.5">
              <div className="flex items-center justify-between text-xs font-medium">
                <span className="text-blue-300">
                  {run.progress_current ?? 0} / {run.progress_total || run.total_test_cases} Cases
                </span>
                <span className="text-blue-300 font-mono">
                  {Math.round(((run.progress_current ?? 0) / (run.progress_total || 1)) * 100)}%
                </span>
              </div>
              <div className="w-full bg-slate-900 rounded-full h-2 overflow-hidden border border-blue-500/20">
                <div
                  className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                  style={{
                    width: `${Math.min(
                      100,
                      Math.round(((run.progress_current ?? 0) / (run.progress_total || 1)) * 100)
                    )}%`,
                  }}
                />
              </div>
            </div>
          </div>
        )}

        {/* Queued Banner when PENDING */}
        {run && run.status === "PENDING" && (
          <div className="p-4 rounded-xl border border-amber-500/30 bg-amber-500/10 flex items-center gap-3 text-amber-200 animate-in fade-in">
            <Clock className="w-5 h-5 text-amber-400 shrink-0 animate-pulse" />
            <div>
              <h3 className="text-sm font-semibold text-white">Evaluation Queued</h3>
              <p className="text-xs text-amber-200/80">
                The run has been registered and is queued for execution. Polling for live updates...
              </p>
            </div>
          </div>
        )}

        {/* Failure Banner when FAILED */}
        {run && run.status === "FAILED" && (
          <div className="p-4 rounded-xl border border-rose-500/30 bg-rose-500/10 flex items-start gap-3 text-rose-200 animate-in fade-in">
            <XCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <h3 className="text-sm font-semibold text-white">Evaluation Run Failed</h3>
              <p className="text-xs text-rose-300">
                {run.error_message || "An unexpected error interrupted benchmark evaluation."}
              </p>
              <p className="text-[11px] text-rose-400/80">
                {run.progress_current ?? 0} out of {run.progress_total || run.total_test_cases} test cases were evaluated before failure.
              </p>
            </div>
          </div>
        )}

        {/* Run Not Found / Inaccessible Empty State */}
        {!loadingRun && !run && (
          <div className="p-12 text-center rounded-xl border border-slate-800 bg-slate-900/60 space-y-3">
            <XCircle className="w-10 h-10 text-rose-400 mx-auto" />
            <h2 className="text-base font-semibold text-white">Evaluation Run Not Found</h2>
            <p className="text-xs text-slate-400 max-w-md mx-auto">
              This evaluation run does not exist, has been deleted, or belongs to another tenant organization.
            </p>
            <div className="pt-2">
              <Link
                href="/evaluations"
                className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold inline-flex items-center gap-2"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                Return to Evaluation Dashboard
              </Link>
            </div>
          </div>
        )}

        {/* Aggregate Metrics Grid */}
        {run && (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
              {/* Pass Rate */}
              <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800 flex flex-col justify-between">
                <span className="text-[11px] text-slate-400 font-medium">Pass Rate</span>
                <div className="mt-2">
                  <span className="text-2xl font-bold text-emerald-400">
                    {(run.pass_rate * 100).toFixed(1)}%
                  </span>
                </div>
                <span className="text-[10px] text-slate-500 mt-1">
                  {run.passed_test_cases}/{run.total_test_cases} passed
                </span>
              </div>

              {/* Recall@5 */}
              <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800 flex flex-col justify-between">
                <span className="text-[11px] text-slate-400 font-medium">Recall@5</span>
                <div className="mt-2">
                  <span className="text-2xl font-bold text-white font-mono">
                    {run.recall_at_5 !== null && run.recall_at_5 !== undefined ? run.recall_at_5.toFixed(3) : "—"}
                  </span>
                </div>
                <span className="text-[10px] text-slate-500 mt-1">R@3: {run.recall_at_3?.toFixed(3) || "—"}</span>
              </div>

              {/* nDCG@5 */}
              <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800 flex flex-col justify-between">
                <span className="text-[11px] text-slate-400 font-medium">nDCG@5</span>
                <div className="mt-2">
                  <span className="text-2xl font-bold text-white font-mono">
                    {run.ndcg_at_5 !== null && run.ndcg_at_5 !== undefined ? run.ndcg_at_5.toFixed(3) : "—"}
                  </span>
                </div>
                <span className="text-[10px] text-slate-500 mt-1">Rank discounted gain</span>
              </div>

              {/* MRR */}
              <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800 flex flex-col justify-between">
                <span className="text-[11px] text-slate-400 font-medium">MRR</span>
                <div className="mt-2">
                  <span className="text-2xl font-bold text-white font-mono">
                    {run.mrr !== null && run.mrr !== undefined ? run.mrr.toFixed(3) : "—"}
                  </span>
                </div>
                <span className="text-[10px] text-slate-500 mt-1">First hit rank</span>
              </div>

              {/* Faithfulness */}
              <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800 flex flex-col justify-between">
                <span className="text-[11px] text-slate-400 font-medium">Faithfulness</span>
                <div className="mt-2">
                  <span className="text-2xl font-bold text-indigo-400 font-mono">
                    {run.mean_faithfulness !== null && run.mean_faithfulness !== undefined ? run.mean_faithfulness.toFixed(3) : "—"}
                  </span>
                </div>
                <span className="text-[10px] text-slate-500 mt-1">Zero-hallucination</span>
              </div>

              {/* Correctness */}
              <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800 flex flex-col justify-between">
                <span className="text-[11px] text-slate-400 font-medium">Correctness</span>
                <div className="mt-2">
                  <span className="text-2xl font-bold text-white font-mono">
                    {run.mean_correctness !== null && run.mean_correctness !== undefined ? run.mean_correctness.toFixed(3) : "—"}
                  </span>
                </div>
                <span className="text-[10px] text-slate-500 mt-1">Factual match</span>
              </div>

              {/* Completeness */}
              <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800 flex flex-col justify-between">
                <span className="text-[11px] text-slate-400 font-medium">Completeness</span>
                <div className="mt-2">
                  <span className="text-2xl font-bold text-white font-mono">
                    {run.mean_completeness !== null && run.mean_completeness !== undefined ? run.mean_completeness.toFixed(3) : "—"}
                  </span>
                </div>
                <span className="text-[10px] text-slate-500 mt-1">Key facts coverage</span>
              </div>

              {/* Mean Latency */}
              <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800 flex flex-col justify-between">
                <span className="text-[11px] text-slate-400 font-medium">Latency</span>
                <div className="mt-2">
                  <span className="text-2xl font-bold text-amber-400 font-mono">
                    {run.mean_latency_ms ? `${Math.round(run.mean_latency_ms)}ms` : "—"}
                  </span>
                </div>
                <span className="text-[10px] text-slate-500 mt-1">
                  P95: {run.latency_p95_ms ? `${Math.round(run.latency_p95_ms)}ms` : "—"}
                </span>
              </div>
            </div>

            {/* Failed Cases Alert Section */}
            {failedCount > 0 ? (
              <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-rose-500/20 text-rose-400">
                    <XCircle className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-xs font-bold text-rose-300 uppercase tracking-wider">
                      {failedCount} Benchmark Case{failedCount > 1 ? "s" : ""} Failed
                    </h3>
                    <p className="text-[11px] text-rose-300/80">
                      Retrieval or judge threshold deficiencies identified. Click to isolate failed cases for rapid triaging.
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => {
                    setStatusFilter("failed");
                    setPage(1);
                  }}
                  className="px-3.5 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold shadow-sm transition-colors cursor-pointer"
                >
                  Show Failed Cases Only
                </button>
              </div>
            ) : (
              <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center gap-3">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                <span className="text-xs text-emerald-300 font-medium">
                  All benchmark test cases in this run passed all validation gates and quality thresholds.
                </span>
              </div>
            )}
          </>
        )}

        {/* Test Case Results Section */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 space-y-4">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white uppercase tracking-wider flex items-center gap-2">
                <FileText className="w-4 h-4 text-slate-400" />
                Benchmark Test Case Results ({totalResults})
              </h2>
              <p className="text-xs text-slate-400">
                Inspect candidate chunks, reranker position shifts, citations, and judge scores.
              </p>
            </div>

            {/* Filter Tabs & Search */}
            <div className="flex flex-wrap items-center gap-2.5">
              {/* Pass/Fail Tabs */}
              <div className="flex items-center bg-slate-950 p-1 rounded-lg border border-slate-800 text-xs">
                <button
                  onClick={() => {
                    setStatusFilter("all");
                    setPage(1);
                  }}
                  className={`px-2.5 py-1 rounded font-medium transition-colors ${
                    statusFilter === "all"
                      ? "bg-slate-800 text-white"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  All ({run?.total_test_cases || 0})
                </button>
                <button
                  onClick={() => {
                    setStatusFilter("failed");
                    setPage(1);
                  }}
                  className={`px-2.5 py-1 rounded font-medium transition-colors ${
                    statusFilter === "failed"
                      ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  Failed ({failedCount})
                </button>
                <button
                  onClick={() => {
                    setStatusFilter("passed");
                    setPage(1);
                  }}
                  className={`px-2.5 py-1 rounded font-medium transition-colors ${
                    statusFilter === "passed"
                      ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  Passed ({run?.passed_test_cases || 0})
                </button>
              </div>

              {/* Category Dropdown */}
              <div className="flex items-center gap-1.5 text-xs text-slate-400 bg-slate-950 px-2.5 py-1.5 rounded-lg border border-slate-800">
                <Filter className="w-3.5 h-3.5" />
                <select
                  value={categoryFilter}
                  onChange={(e) => {
                    setCategoryFilter(e.target.value);
                    setPage(1);
                  }}
                  className="bg-transparent text-white font-medium focus:outline-none cursor-pointer"
                >
                  {categories.map((c) => (
                    <option key={c} value={c} className="bg-slate-900">
                      {c === "all" ? "All Categories" : c}
                    </option>
                  ))}
                </select>
              </div>

              {/* Search */}
              <div className="relative">
                <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-slate-500" />
                <input
                  type="text"
                  placeholder="Filter queries..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="bg-slate-950 border border-slate-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500 placeholder-slate-500 w-44"
                />
              </div>
            </div>
          </div>

          {/* Results Table */}
          <div className="overflow-x-auto rounded-lg border border-slate-800">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950/80 text-slate-400 border-b border-slate-800 uppercase tracking-wider text-[10px]">
                <tr>
                  <th className="p-3 font-semibold">Case ID</th>
                  <th className="p-3 font-semibold">Query</th>
                  <th className="p-3 font-semibold">Category</th>
                  <th className="p-3 font-semibold">Status</th>
                  <th className="p-3 font-semibold">Recall@5</th>
                  <th className="p-3 font-semibold">nDCG@5</th>
                  <th className="p-3 font-semibold">Faithfulness</th>
                  <th className="p-3 font-semibold">Correctness</th>
                  <th className="p-3 font-semibold">Latency</th>
                  <th className="p-3 text-right font-semibold">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-sans">
                {loadingResults ? (
                  <tr>
                    <td colSpan={10} className="p-8 text-center text-slate-400">
                      <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-indigo-400" />
                      Loading benchmark results...
                    </td>
                  </tr>
                ) : filteredResults.length === 0 ? (
                  <tr>
                    <td colSpan={10} className="p-8 text-center text-slate-400">
                      No matching test cases found.
                    </td>
                  </tr>
                ) : (
                  filteredResults.map((r) => (
                    <tr
                      key={r.id}
                      className="hover:bg-slate-800/40 transition-colors"
                    >
                      <td className="p-3 font-mono font-medium text-slate-200">
                        {r.test_case_id}
                      </td>
                      <td className="p-3 max-w-xs truncate text-slate-300 font-medium">
                        {r.query}
                      </td>
                      <td className="p-3">
                        <span className="inline-flex px-2 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-slate-300 border border-slate-700">
                          {r.query_type}
                        </span>
                      </td>
                      <td className="p-3">
                        {r.passed ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                            <Check className="w-3 h-3" />
                            PASS
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-rose-500/15 text-rose-400 border border-rose-500/30">
                            <X className="w-3 h-3" />
                            FAIL
                          </span>
                        )}
                      </td>
                      <td className="p-3 font-mono text-slate-300">
                        {r.recall_at_5 !== null && r.recall_at_5 !== undefined ? r.recall_at_5.toFixed(2) : "—"}
                      </td>
                      <td className="p-3 font-mono text-slate-300">
                        {r.ndcg_at_5 !== null && r.ndcg_at_5 !== undefined ? r.ndcg_at_5.toFixed(2) : "—"}
                      </td>
                      <td className="p-3 font-mono text-indigo-300">
                        {r.faithfulness !== null && r.faithfulness !== undefined ? r.faithfulness.toFixed(2) : "—"}
                      </td>
                      <td className="p-3 font-mono text-slate-300">
                        {r.correctness !== null && r.correctness !== undefined ? r.correctness.toFixed(2) : "—"}
                      </td>
                      <td className="p-3 font-mono text-amber-300">
                        {r.total_latency_ms ? `${Math.round(r.total_latency_ms)}ms` : "—"}
                      </td>
                      <td className="p-3 text-right">
                        <button
                          onClick={() => handleInspectCase(r.id)}
                          className="px-2.5 py-1 rounded bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 hover:text-white border border-indigo-500/30 text-xs font-medium cursor-pointer transition-colors"
                        >
                          Inspect
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination Controls */}
          {totalResults > pageSize && (
            <div className="flex items-center justify-between pt-3 text-xs text-slate-400">
              <span>
                Showing {(page - 1) * pageSize + 1} -{" "}
                {Math.min(page * pageSize, totalResults)} of {totalResults} cases
              </span>
              <div className="flex items-center gap-2">
                <button
                  disabled={page <= 1}
                  onClick={() => setPage(page - 1)}
                  className="px-3 py-1 rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed text-white flex items-center gap-1"
                >
                  <ChevronLeft className="w-3.5 h-3.5" />
                  Previous
                </button>
                <span>
                  Page {page} of {Math.ceil(totalResults / pageSize)}
                </span>
                <button
                  disabled={page * pageSize >= totalResults}
                  onClick={() => setPage(page + 1)}
                  className="px-3 py-1 rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed text-white flex items-center gap-1"
                >
                  Next
                  <ChevronRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* ========================================================================= */}
      {/* CASE DETAIL INSPECTION MODAL / DRAWER                                     */}
      {/* ========================================================================= */}
      {selectedResultId && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-xs flex items-center justify-center z-50 p-4">
          <div className="bg-[#0e1422] border border-slate-800 rounded-2xl max-w-4xl w-full p-6 shadow-2xl relative space-y-5 animate-in fade-in zoom-in-95 duration-150 max-h-[92vh] flex flex-col">
            {/* Modal Header */}
            <div className="flex items-center justify-between pb-3 border-b border-slate-800 shrink-0">
              <div className="flex items-center gap-3">
                <div
                  className={`p-2 rounded-lg font-bold text-xs ${
                    inspectingResult?.passed
                      ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                      : "bg-rose-500/20 text-rose-400 border border-rose-500/30"
                  }`}
                >
                  {inspectingResult?.passed ? "PASSED" : "FAILED"}
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                    Case {inspectingResult?.test_case_id}
                    <span className="text-xs px-2 py-0.5 rounded font-mono bg-slate-800 text-slate-300">
                      {inspectingResult?.query_type}
                    </span>
                  </h3>
                  <p className="text-[11px] text-slate-400">
                    Expected Behavior:{" "}
                    <span className="uppercase font-semibold text-slate-200">
                      {inspectingResult?.expected_behavior}
                    </span>
                  </p>
                </div>
              </div>

              <button
                onClick={() => {
                  setSelectedResultId(null);
                  setInspectingResult(null);
                }}
                className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {loadingDetail ? (
              <div className="p-12 text-center text-slate-400">
                <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-indigo-400" />
                Loading case detail inspection...
              </div>
            ) : inspectingResult ? (
              <>
                {/* Navigation Tabs */}
                <div className="flex items-center gap-2 border-b border-slate-800/80 pb-2 shrink-0 text-xs">
                  <button
                    onClick={() => setDetailTab("overview")}
                    className={`px-3 py-1.5 rounded-lg font-medium transition-colors ${
                      detailTab === "overview"
                        ? "bg-indigo-600 text-white"
                        : "text-slate-400 hover:text-white hover:bg-slate-800"
                    }`}
                  >
                    Overview & Synthesis
                  </button>
                  <button
                    onClick={() => setDetailTab("chunks")}
                    className={`px-3 py-1.5 rounded-lg font-medium transition-colors ${
                      detailTab === "chunks"
                        ? "bg-indigo-600 text-white"
                        : "text-slate-400 hover:text-white hover:bg-slate-800"
                    }`}
                  >
                    Retrieved vs Reranked Chunks ({inspectingResult.reranked_candidates?.length || 0})
                  </button>
                  <button
                    onClick={() => setDetailTab("judge")}
                    className={`px-3 py-1.5 rounded-lg font-medium transition-colors ${
                      detailTab === "judge"
                        ? "bg-indigo-600 text-white"
                        : "text-slate-400 hover:text-white hover:bg-slate-800"
                    }`}
                  >
                    Judge Diagnostics & Trace
                  </button>
                </div>

                {/* Tab 1: Overview & Synthesis */}
                {detailTab === "overview" && (
                  <div className="flex-1 overflow-y-auto space-y-4 pr-1">
                    {/* Failure Alert */}
                    {!inspectingResult.passed && inspectingResult.failure_reason && (
                      <div className="p-3.5 rounded-xl bg-rose-500/15 border border-rose-500/30 text-xs text-rose-300">
                        <span className="font-semibold block mb-1">Failure Reason:</span>
                        <span>{inspectingResult.failure_reason}</span>
                      </div>
                    )}

                    {/* Query */}
                    <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800">
                      <span className="text-[10px] uppercase font-semibold text-slate-400 block mb-1">
                        Benchmark Query
                      </span>
                      <p className="text-sm font-medium text-white">
                        {inspectingResult.query}
                      </p>
                    </div>

                    {/* Generated Answer */}
                    <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800">
                      <span className="text-[10px] uppercase font-semibold text-indigo-400 block mb-1">
                        Generated Answer
                      </span>
                      <p className="text-xs text-slate-200 leading-relaxed whitespace-pre-wrap">
                        {inspectingResult.generated_answer || "(Empty answer)"}
                      </p>
                    </div>

                    {/* Citations Generated */}
                    <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800">
                      <span className="text-[10px] uppercase font-semibold text-slate-400 block mb-2">
                        Grounded Citations ({inspectingResult.citations?.length || 0})
                      </span>
                      {inspectingResult.citations?.length === 0 ? (
                        <p className="text-xs text-slate-500 italic">No citations attached (Refusal or ungrounded response).</p>
                      ) : (
                        <div className="space-y-2">
                          {inspectingResult.citations.map((c, idx) => (
                            <div
                              key={idx}
                              className="p-2.5 rounded-lg bg-slate-950/70 border border-slate-800/80 text-xs"
                            >
                              <div className="flex items-center justify-between text-slate-300 font-medium mb-1">
                                <span>[Source {idx + 1}] {c.document_title}</span>
                                {c.page_number && <span className="text-[10px] text-slate-400">Page {c.page_number}</span>}
                              </div>
                              <p className="text-[11px] text-slate-400 italic">
                                "{c.content?.slice(0, 200)}..."
                              </p>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Tab 2: Chunks Comparison */}
                {detailTab === "chunks" && (
                  <div className="flex-1 overflow-y-auto space-y-3 pr-1">
                    <p className="text-xs text-slate-400">
                      Top candidates returned by Hybrid Search and reranked by the Cross-Encoder:
                    </p>
                    <div className="space-y-2.5">
                      {inspectingResult.reranked_candidates.map((cand, idx) => (
                        <div
                          key={idx}
                          className="p-3 rounded-xl bg-slate-900 border border-slate-800 text-xs space-y-1.5"
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-semibold text-slate-200 flex items-center gap-2">
                              <span className="w-5 h-5 rounded-full bg-indigo-600/30 text-indigo-300 flex items-center justify-center text-[10px] font-bold">
                                {idx + 1}
                              </span>
                              {cand.document_title}
                              {cand.section_heading && (
                                <span className="text-slate-400 font-normal">
                                  — {cand.section_heading}
                                </span>
                              )}
                            </span>
                            <div className="flex items-center gap-2 text-[11px] font-mono">
                              <span className="text-indigo-400">
                                Rerank: {cand.rerank_score !== null && cand.rerank_score !== undefined ? cand.rerank_score.toFixed(3) : "—"}
                              </span>
                              <span className="text-slate-500">
                                Hybrid: {cand.score?.toFixed(4)}
                              </span>
                            </div>
                          </div>
                          <p className="text-[11px] text-slate-300 bg-slate-950 p-2.5 rounded-lg border border-slate-850 leading-relaxed font-sans">
                            {cand.content}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Tab 3: Judge Diagnostics & Trace */}
                {detailTab === "judge" && (
                  <div className="flex-1 overflow-y-auto space-y-4 pr-1">
                    {/* Scores Grid */}
                    <div className="grid grid-cols-4 gap-2.5 text-center">
                      <div className="p-3 rounded-xl bg-slate-900 border border-slate-800">
                        <span className="text-[10px] uppercase text-slate-400 block mb-1">Faithfulness</span>
                        <span className="text-lg font-bold text-indigo-400 font-mono">
                          {inspectingResult.faithfulness != null ? inspectingResult.faithfulness.toFixed(2) : "—"}
                        </span>
                      </div>
                      <div className="p-3 rounded-xl bg-slate-900 border border-slate-800">
                        <span className="text-[10px] uppercase text-slate-400 block mb-1">Correctness</span>
                        <span className="text-lg font-bold text-white font-mono">
                          {inspectingResult.correctness != null ? inspectingResult.correctness.toFixed(2) : "—"}
                        </span>
                      </div>
                      <div className="p-3 rounded-xl bg-slate-900 border border-slate-800">
                        <span className="text-[10px] uppercase text-slate-400 block mb-1">Completeness</span>
                        <span className="text-lg font-bold text-white font-mono">
                          {inspectingResult.completeness != null ? inspectingResult.completeness.toFixed(2) : "—"}
                        </span>
                      </div>
                      <div className="p-3 rounded-xl bg-slate-900 border border-slate-800">
                        <span className="text-[10px] uppercase text-slate-400 block mb-1">Citation Correctness</span>
                        <span className="text-lg font-bold text-emerald-400 font-mono">
                          {inspectingResult.citation_correctness != null ? inspectingResult.citation_correctness.toFixed(2) : "—"}
                        </span>
                      </div>
                    </div>

                    {/* Judge Reasoning */}
                    <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800">
                      <span className="text-[10px] uppercase font-semibold text-slate-400 block mb-1">
                        Judge Qualitative Reasoning
                      </span>
                      <p className="text-xs text-slate-300 leading-relaxed whitespace-pre-wrap">
                        {inspectingResult.judge_output?.reasoning || "No qualitative notes provided."}
                      </p>
                    </div>

                    {/* Trace Metadata */}
                    <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
                      <span className="text-[10px] uppercase font-semibold text-slate-400 block">
                        Reranker Shift & Trace Metadata
                      </span>
                      <div className="grid grid-cols-2 gap-2 text-xs font-mono text-slate-300">
                        <div>Position Shift: {inspectingResult.trace_data?.position_shift ?? 0}</div>
                        <div>Promoted to Top 3: {inspectingResult.trace_data?.promoted_to_top3 ? "Yes" : "No"}</div>
                        <div>Rank Before: {inspectingResult.trace_data?.rank_before ?? "—"}</div>
                        <div>Rank After: {inspectingResult.trace_data?.rank_after ?? "—"}</div>
                      </div>
                    </div>
                  </div>
                )}
              </>
            ) : null}

            {/* Modal Footer */}
            <div className="pt-2 flex justify-end shrink-0 border-t border-slate-800">
              <button
                onClick={() => {
                  setSelectedResultId(null);
                  setInspectingResult(null);
                }}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-xs font-medium cursor-pointer transition-colors"
              >
                Close Inspection
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
