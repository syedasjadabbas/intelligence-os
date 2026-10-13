"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import {
  api,
  EvaluationRunListItem,
  EvaluationComparisonResponse,
  EvaluationComparisonDeltas,
  MetricDelta,
  DatasetListItem,
} from "@/lib/api";
import { cn, formatDate, getErrorMessage } from "@/lib/utils";
import {
  Activity,
  ArrowRight,
  Ban,
  ChevronRight,
  Cpu,
  Database,
  GitCompareArrows,
  Play,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { AppShell, PageHeader } from "@/components/app-shell";
import { JudgeBadge, RunStatusBadge, passRateTone } from "@/components/status";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button, ButtonLink } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Field, Select } from "@/components/ui/field";
import { MetricGrid, MetricTile } from "@/components/ui/metric";
import { LoadingState, Spinner } from "@/components/ui/spinner";
import { EmptyState, Eyebrow, Panel, PanelHeader, ProgressBar } from "@/components/ui/surface";
import { TableMessage, TableWrap, TBody, Td, Th, THead, Tr } from "@/components/ui/table";

const fmt3 = (v: number | null | undefined) =>
  v !== undefined && v !== null ? v.toFixed(3) : "—";

/** Rows of the comparison table; formatting matches the original per-metric cells. */
const COMPARISON_ROWS: {
  key: keyof EvaluationComparisonDeltas;
  label: string;
  format: (v: number | null | undefined) => string;
  isLatency?: boolean;
}[] = [
  { key: "pass_rate", label: "Pass Rate", format: (v) => `${((v || 0) * 100).toFixed(1)}%` },
  { key: "recall_at_3", label: "Recall@3", format: (v) => v?.toFixed(3) || "—" },
  { key: "recall_at_5", label: "Recall@5", format: (v) => v?.toFixed(3) || "—" },
  { key: "mrr", label: "MRR", format: (v) => v?.toFixed(3) || "—" },
  { key: "ndcg_at_5", label: "nDCG@5", format: (v) => v?.toFixed(3) || "—" },
  { key: "mean_faithfulness", label: "Faithfulness", format: (v) => v?.toFixed(3) || "—" },
  { key: "mean_correctness", label: "Correctness", format: (v) => v?.toFixed(3) || "—" },
  { key: "mean_completeness", label: "Completeness", format: (v) => v?.toFixed(3) || "—" },
  {
    key: "mean_latency_ms",
    label: "Mean Latency",
    format: (v) => (v ? `${Math.round(v)}ms` : "—"),
    isLatency: true,
  },
];

export default function EvaluationsDashboardPage() {
  const { user } = useAuth();
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
  const [cancellingRunId, setCancellingRunId] = useState<string | null>(null);
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
    } catch (err: unknown) {
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
    } catch (err: unknown) {
      setError(getErrorMessage(err) || "Failed to load evaluation history.");
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
    } catch (err: unknown) {
      setError(getErrorMessage(err) || "Failed to compare evaluation runs.");
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
    } catch (err: unknown) {
      setRunError(getErrorMessage(err) || "Failed to execute evaluation run.");
    } finally {
      setSubmittingRun(false);
    }
  };

  // Cancel evaluation run (Phase 5C)
  const handleCancelRun = async (runId: string) => {
    if (!isAdmin) return;
    if (!confirm("Are you sure you want to cancel this evaluation run?")) return;
    setCancellingRunId(runId);
    try {
      await api.cancelEvaluation(runId);
      await fetchRuns(true);
    } catch (err: unknown) {
      setError(getErrorMessage(err) || "Failed to cancel evaluation run.");
    } finally {
      setCancellingRunId(null);
    }
  };

  // Latest completed run for summary stats
  const latestRun = runs.find((r) => r.status === "COMPLETED") || runs[0];

  const renderDeltaBadge = (deltaItem: MetricDelta, isLatency: boolean = false) => {
    if (deltaItem.delta === null || deltaItem.delta === undefined) {
      return <span className="text-xs text-fg-faint">—</span>;
    }
    const isImproved = deltaItem.status === "improved";
    const isRegressed = deltaItem.status === "regressed";

    const sign = deltaItem.delta > 0 ? "+" : "";
    const formattedVal = isLatency
      ? `${sign}${deltaItem.delta.toFixed(1)}ms`
      : `${sign}${(deltaItem.delta * (isLatency ? 1 : 100)).toFixed(1)}%`;

    if (isImproved) {
      return (
        <Badge tone="success" mono>
          <TrendingUp />
          {formattedVal}
        </Badge>
      );
    }
    if (isRegressed) {
      return (
        <Badge tone="danger" mono>
          <TrendingDown />
          {formattedVal}
        </Badge>
      );
    }
    return (
      <Badge tone="neutral" mono>
        0.0%
      </Badge>
    );
  };

  // Limit presets for the start-run dialog (unchanged logic)
  const isCustomSelection = Boolean(selectedDatasetId && selectedDatasetId !== "golden_dataset");
  const customSelectionDs = isCustomSelection
    ? datasets.find((d) => d.id === selectedDatasetId)
    : null;
  const maxAvailable =
    isCustomSelection && customSelectionDs ? Math.max(1, customSelectionDs.test_case_count) : 50;
  const presetList = [5, 10, 25, 50].filter((p) => p <= maxAvailable);
  if (!presetList.includes(maxAvailable)) {
    presetList.push(maxAvailable);
    presetList.sort((a, b) => a - b);
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Quality"
        title="Evaluations"
        description="Deterministic and LLM-judged quality benchmarks for retrieval and generation, with run-over-run regression tracking."
        actions={
          <>
            <ButtonLink
              href="/evaluations/datasets"
              variant="secondary"
              title="Manage custom datasets and test cases"
            >
              <Database />
              Datasets
            </ButtonLink>
            <Button
              variant="secondary"
              size="icon-sm"
              onClick={() => fetchRuns()}
              title="Refresh runs"
              aria-label="Refresh runs"
            >
              <RefreshCw className={cn(loading && "animate-spin")} />
            </Button>
            <Button
              variant="primary"
              onClick={() => {
                setRunError(null);
                fetchDatasets();
                setShowRunModal(true);
              }}
            >
              <Play className="fill-current" />
              Start Evaluation
            </Button>
          </>
        }
      />

      <div className="space-y-6">
        {error && (
          <Alert tone="danger" onDismiss={() => setError(null)}>
            {error}
          </Alert>
        )}

        {/* Latest run snapshot */}
        <section aria-labelledby="latest-run-heading" className="space-y-3">
          <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
            <h2 id="latest-run-heading">
              <Eyebrow>Latest run benchmark metrics</Eyebrow>
            </h2>
            {latestRun && (
              <span className="text-xs text-fg-subtle">
                Based on run{" "}
                <Link
                  href={`/evaluations/${latestRun.id}`}
                  className="font-mono text-fg-muted underline-offset-4 hover:text-fg hover:underline"
                >
                  {latestRun.id.slice(0, 8)}
                </Link>{" "}
                · {formatDate(latestRun.created_at)}
              </span>
            )}
          </div>

          <MetricGrid>
            <MetricTile
              label="Pass rate"
              value={latestRun ? `${(latestRun.pass_rate * 100).toFixed(1)}%` : "—"}
              tone={latestRun ? passRateTone(latestRun.pass_rate) : "default"}
              meter={latestRun?.pass_rate}
              hint={
                latestRun
                  ? `${latestRun.passed_test_cases}/${latestRun.total_test_cases} passed`
                  : "No runs"
              }
            />
            <MetricTile
              label="Recall@5"
              value={fmt3(latestRun?.recall_at_5)}
              meter={latestRun?.recall_at_5}
              hint="Target ≥ 0.95"
            />
            <MetricTile
              label="nDCG@5"
              value={fmt3(latestRun?.ndcg_at_5)}
              meter={latestRun?.ndcg_at_5}
              hint="Ranking quality"
            />
            <MetricTile
              label="MRR"
              value={fmt3(latestRun?.mrr)}
              meter={latestRun?.mrr}
              hint="Reciprocal rank"
            />
            <MetricTile
              label="Faithfulness"
              value={fmt3(latestRun?.mean_faithfulness)}
              meter={latestRun?.mean_faithfulness}
              tone="accent"
              hint="Zero-hallucination"
            />
            <MetricTile
              label="Correctness"
              value={fmt3(latestRun?.mean_correctness)}
              meter={latestRun?.mean_correctness}
              hint="Factual accuracy"
            />
            <MetricTile
              label="Completeness"
              value={fmt3(latestRun?.mean_completeness)}
              meter={latestRun?.mean_completeness}
              hint="Key point coverage"
            />
            <MetricTile
              label="Mean latency"
              value={
                latestRun?.mean_latency_ms !== undefined && latestRun.mean_latency_ms !== null
                  ? `${Math.round(latestRun.mean_latency_ms)}ms`
                  : "—"
              }
              tone="warning"
              hint={`P95: ${
                latestRun?.latency_p95_ms ? `${Math.round(latestRun.latency_p95_ms)}ms` : "—"
              }`}
            />
          </MetricGrid>
        </section>

        {/* Run history */}
        <Panel>
          <PanelHeader
            title="Run history"
            count={runs.length}
            description="Select any two runs to compare regressions, or inspect a run's individual case results."
            actions={
              <>
                <Select
                  aria-label="Filter by judge"
                  value={judgeFilter}
                  onChange={(e) => setJudgeFilter(e.target.value)}
                  className="h-8 text-[13px]"
                >
                  <option value="all">All Judges</option>
                  <option value="deterministic">Deterministic</option>
                  <option value="llm">LLM Judge</option>
                </Select>
                <Select
                  aria-label="Filter by status"
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="h-8 text-[13px]"
                >
                  <option value="all">All Statuses</option>
                  <option value="COMPLETED">Completed</option>
                  <option value="RUNNING">Running</option>
                  <option value="PENDING">Queued</option>
                  <option value="CANCELLED">Cancelled</option>
                  <option value="FAILED">Failed</option>
                </Select>
              </>
            }
          />

          {/* Comparison selection bar */}
          {selectedRunIds.length > 0 && (
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line bg-accent/[0.05] px-4 py-2.5 animate-fade-in sm:px-5">
              <div className="flex items-center gap-2 text-[13px] text-fg-muted">
                <GitCompareArrows className="size-4 text-accent" />
                <span>
                  <span className="font-medium text-fg">{selectedRunIds.length} of 2</span> runs
                  selected
                  {selectedRunIds.length === 1 && (
                    <span className="text-fg-subtle"> · select one more to compare</span>
                  )}
                </span>
              </div>
              {selectedRunIds.length === 2 && (
                <Button
                  variant="accent"
                  size="sm"
                  onClick={handleCompare}
                  disabled={comparing}
                  loading={comparing}
                >
                  {!comparing && <GitCompareArrows />}
                  {comparing ? "Comparing..." : "Compare Selected (2)"}
                </Button>
              )}
            </div>
          )}

          <TableWrap>
            <THead>
              <tr>
                <Th className="w-10 pr-0">
                  <span className="sr-only">Select</span>
                </Th>
                <Th>Run</Th>
                <Th>Dataset</Th>
                <Th>Cases</Th>
                <Th>Judge</Th>
                <Th className="text-right">Pass rate</Th>
                <Th className="text-right">Recall@5</Th>
                <Th className="text-right">nDCG@5</Th>
                <Th className="text-right">Faithful.</Th>
                <Th>Status</Th>
                <Th className="text-right">
                  <span className="sr-only">Actions</span>
                </Th>
              </tr>
            </THead>
            <TBody>
              {loading ? (
                <TableMessage colSpan={11}>
                  <LoadingState label="Loading evaluation history…" />
                </TableMessage>
              ) : runs.length === 0 ? (
                <TableMessage colSpan={11}>
                  <EmptyState
                    icon={<Activity />}
                    title="No evaluation runs found"
                    description='Click "Start Evaluation" to run your first benchmark against the golden dataset or a custom dataset.'
                  />
                </TableMessage>
              ) : (
                runs.map((r) => {
                  const isSelected = selectedRunIds.includes(r.id);
                  const progressPct =
                    r.progress_total && r.progress_total > 0
                      ? Math.round(((r.progress_current ?? 0) / r.progress_total) * 100)
                      : 0;
                  return (
                    <Tr key={r.id} selected={isSelected}>
                      <Td className="pr-0">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => handleToggleSelectRun(r.id)}
                          className="size-3.5 cursor-pointer rounded"
                          title="Select for comparison"
                          aria-label={`Select run ${r.id.slice(0, 8)} for comparison`}
                        />
                      </Td>
                      <Td className="whitespace-nowrap">
                        <Link
                          href={`/evaluations/${r.id}`}
                          className="font-mono text-[13px] font-medium text-fg underline-offset-4 hover:text-accent-strong hover:underline"
                        >
                          {r.id.slice(0, 8)}
                        </Link>
                        <div className="mt-0.5 text-[11px] text-fg-subtle">
                          {formatDate(r.created_at)}
                        </div>
                      </Td>
                      <Td>
                        <div className="flex items-center gap-1.5 whitespace-nowrap">
                          <span className="font-medium text-fg-muted">{r.dataset_name}</span>
                          <span className="font-mono text-[11px] text-fg-faint">
                            v{r.dataset_version}
                          </span>
                          {r.dataset_id ? <Badge tone="accent">Custom</Badge> : null}
                        </div>
                      </Td>
                      <Td className="tabular whitespace-nowrap font-mono text-xs">
                        {r.status === "COMPLETED" ? (
                          <span className="text-fg-muted">
                            {r.passed_test_cases}/{r.total_test_cases}
                          </span>
                        ) : r.status === "RUNNING" ? (
                          <span className="text-info">
                            {r.progress_current ?? 0}/{r.progress_total || r.total_test_cases} done
                          </span>
                        ) : r.status === "PENDING" ? (
                          <span className="text-warning">Queued ({r.total_test_cases})</span>
                        ) : (
                          <span className="text-fg-subtle">
                            {r.progress_current ?? 0}/{r.total_test_cases}
                          </span>
                        )}
                      </Td>
                      <Td>
                        <JudgeBadge judgeType={r.judge_type} />
                      </Td>
                      <Td className="tabular text-right font-mono text-xs">
                        {r.status === "COMPLETED" ? (
                          <span
                            className={cn(
                              "font-medium",
                              {
                                success: "text-success",
                                warning: "text-warning",
                                danger: "text-danger",
                              }[passRateTone(r.pass_rate)]
                            )}
                          >
                            {(r.pass_rate * 100).toFixed(1)}%
                          </span>
                        ) : (
                          <span className="text-fg-faint">—</span>
                        )}
                      </Td>
                      <Td className="tabular text-right font-mono text-xs text-fg-muted">
                        {fmt3(r.recall_at_5)}
                      </Td>
                      <Td className="tabular text-right font-mono text-xs text-fg-muted">
                        {fmt3(r.ndcg_at_5)}
                      </Td>
                      <Td className="tabular text-right font-mono text-xs text-accent-strong">
                        {fmt3(r.mean_faithfulness)}
                      </Td>
                      <Td>
                        <div className="flex min-w-[8rem] flex-col items-start gap-1.5">
                          <RunStatusBadge run={r} title={r.error_message || undefined} />
                          {r.status === "RUNNING" && r.progress_total && r.progress_total > 0 ? (
                            <ProgressBar
                              value={progressPct}
                              tone="info"
                              className="h-1 w-24"
                              label={`Run ${r.id.slice(0, 8)} progress`}
                            />
                          ) : null}
                          {(r.status === "CANCELLED" || r.status === "FAILED") && r.error_message && (
                            <span
                              className={cn(
                                "max-w-[11rem] truncate text-[11px]",
                                r.status === "FAILED" ? "text-danger/80" : "text-fg-subtle"
                              )}
                              title={r.error_message}
                            >
                              {r.error_message}
                            </span>
                          )}
                        </div>
                      </Td>
                      <Td className="text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          {isAdmin && (r.status === "PENDING" || r.status === "RUNNING") && (
                            <Button
                              variant="danger"
                              size="xs"
                              onClick={() => handleCancelRun(r.id)}
                              disabled={cancellingRunId === r.id}
                              title="Cancel this evaluation run"
                            >
                              {cancellingRunId === r.id ? <Spinner /> : <Ban />}
                              Cancel
                            </Button>
                          )}
                          <ButtonLink href={`/evaluations/${r.id}`} variant="secondary" size="xs">
                            Inspect
                            <ChevronRight />
                          </ButtonLink>
                        </div>
                      </Td>
                    </Tr>
                  );
                })
              )}
            </TBody>
          </TableWrap>
        </Panel>
      </div>

      {/* Start evaluation run */}
      {showRunModal && (
        <Dialog
          onClose={() => setShowRunModal(false)}
          size="lg"
          icon={<Play />}
          title="Start Evaluation Benchmark Run"
          description="Execute a RAG quality evaluation against a benchmark dataset."
          footer={
            <>
              <Button
                variant="ghost"
                onClick={() => setShowRunModal(false)}
                disabled={submittingRun}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                form="start-evaluation-form"
                variant="primary"
                disabled={submittingRun || !isAdmin}
                loading={submittingRun}
              >
                {submittingRun ? (
                  "Executing Evaluation..."
                ) : (
                  <>
                    <Play className="fill-current" />
                    Run Benchmark ({runLimit} Cases)
                  </>
                )}
              </Button>
            </>
          }
        >
          <form id="start-evaluation-form" onSubmit={handleStartRun} className="space-y-5">
            {runError && <Alert tone="danger">{runError}</Alert>}

            <Field
              label="Benchmark dataset"
              htmlFor="eval-dataset"
              action={
                <Link
                  href="/evaluations/datasets"
                  className="inline-flex items-center gap-1 text-xs text-accent-strong hover:text-fg"
                >
                  Manage datasets
                  <ArrowRight className="size-3" />
                </Link>
              }
            >
              <Select
                id="eval-dataset"
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
              >
                <option value="golden_dataset">
                  golden_dataset.json (Built-in 50 cases - Multi-Hop, Coreference, Refusal)
                </option>
                {datasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} v{d.version} ({d.test_case_count} cases) {d.description ? `— ${d.description}` : ""}
                  </option>
                ))}
              </Select>
            </Field>

            <fieldset className="space-y-1.5">
              <legend className="mb-1.5 text-[13px] font-medium text-fg-muted">Judge mode</legend>
              <div role="radiogroup" aria-label="Judge mode" className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {(
                  [
                    {
                      value: "deterministic" as const,
                      icon: Cpu,
                      title: "Deterministic Judge",
                      body: "Strict semantic anchor matching. No API quota consumed, instant execution.",
                      tone: "text-judge-det",
                    },
                    {
                      value: "llm" as const,
                      icon: Sparkles,
                      title: "LLM Judge",
                      body: "Gemini 2.5 Flash as a judge for qualitative reasoning and hallucination checks.",
                      tone: "text-judge-llm",
                    },
                  ]
                ).map((opt) => {
                  const active = runJudgeType === opt.value;
                  return (
                    <button
                      key={opt.value}
                      type="button"
                      role="radio"
                      aria-checked={active}
                      onClick={() => setRunJudgeType(opt.value)}
                      className={cn(
                        "rounded-lg border p-3 text-left transition-colors cursor-pointer",
                        active
                          ? "border-accent/60 bg-accent/[0.06] ring-1 ring-accent/30"
                          : "border-line-strong bg-surface hover:border-fg-faint"
                      )}
                    >
                      <div className="mb-1 flex items-center gap-2 text-[13px] font-medium text-fg">
                        <opt.icon className={cn("size-4", opt.tone)} />
                        {opt.title}
                        <span
                          className={cn(
                            "ml-auto flex size-3.5 items-center justify-center rounded-full border",
                            active ? "border-accent" : "border-fg-faint"
                          )}
                          aria-hidden
                        >
                          {active && <span className="size-1.5 rounded-full bg-accent" />}
                        </span>
                      </div>
                      <p className="text-xs leading-relaxed text-fg-subtle">{opt.body}</p>
                    </button>
                  );
                })}
              </div>
            </fieldset>

            {runJudgeType === "llm" && (
              <Alert tone="warning" title="External model quota notice">
                LLM-as-a-Judge invokes the Google Gemini API for each test case. Ensure valid
                GEMINI_API_KEY credentials with available rate-limit quota.
              </Alert>
            )}

            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <label htmlFor="eval-limit" className="text-[13px] font-medium text-fg-muted">
                  Test case limit
                </label>
                <span className="tabular font-mono text-xs text-fg">
                  {runLimit} <span className="text-fg-subtle">of {maxAvailable} cases</span>
                </span>
              </div>
              {presetList.length > 1 && (
                <div className="flex flex-wrap items-center gap-1.5">
                  {presetList.map((preset) => (
                    <button
                      key={preset}
                      type="button"
                      onClick={() => setRunLimit(preset)}
                      aria-pressed={runLimit === preset}
                      className={cn(
                        "tabular h-7 rounded-md border px-2.5 font-mono text-xs transition-colors cursor-pointer",
                        runLimit === preset
                          ? "border-accent/60 bg-accent/12 text-fg"
                          : "border-line-strong bg-surface text-fg-subtle hover:border-fg-faint hover:text-fg"
                      )}
                    >
                      {preset === maxAvailable ? `All (${maxAvailable})` : preset}
                    </button>
                  ))}
                </div>
              )}
              <input
                id="eval-limit"
                type="range"
                min="1"
                max={maxAvailable}
                value={Math.min(runLimit, maxAvailable)}
                onChange={(e) => setRunLimit(Number(e.target.value))}
                className="w-full cursor-pointer"
              />
            </div>

            {runJudgeType === "deterministic" && (
              <label className="flex cursor-pointer items-center justify-between gap-4 rounded-lg border border-line-strong bg-surface-2 px-3.5 py-3">
                <span>
                  <span className="block text-[13px] font-medium text-fg">Deterministic offline mode</span>
                  <span className="mt-0.5 block text-xs text-fg-subtle">
                    Uses feature-hashing embeddings without network dependencies.
                  </span>
                </span>
                <span className="relative inline-flex shrink-0">
                  <input
                    type="checkbox"
                    checked={runOffline}
                    onChange={(e) => setRunOffline(e.target.checked)}
                    className="peer sr-only"
                  />
                  <span className="h-5 w-9 rounded-full border border-line-strong bg-surface-4 transition-colors peer-checked:border-accent/60 peer-checked:bg-accent peer-focus-visible:ring-2 peer-focus-visible:ring-accent/50" />
                  <span className="absolute left-0.5 top-0.5 size-4 rounded-full bg-fg-muted transition-transform peer-checked:translate-x-4 peer-checked:bg-accent-fg" />
                </span>
              </label>
            )}

            {!isAdmin && (
              <Alert tone="warning" icon={<ShieldAlert />}>
                Admin privileges required to start evaluations.
              </Alert>
            )}
          </form>
        </Dialog>
      )}

      {/* Run comparison */}
      {showComparisonModal && comparisonData && (
        <Dialog
          onClose={() => setShowComparisonModal(false)}
          size="xl"
          icon={<GitCompareArrows />}
          title="Side-by-Side Run Comparison"
          description="Baseline (older) run versus target (newer) run — improvements and regressions per metric."
          footer={
            <Button variant="secondary" onClick={() => setShowComparisonModal(false)}>
              Close Comparison
            </Button>
          }
          bodyClassName="space-y-4"
        >
          <div className="grid grid-cols-1 gap-px overflow-hidden rounded-lg border border-line bg-line sm:grid-cols-[1fr_auto_1fr_auto_auto]">
            <div className="bg-surface-2 px-4 py-3">
              <Eyebrow>Baseline run</Eyebrow>
              <p className="mt-1 font-mono text-[13px] text-fg">
                {comparisonData.base_run.id.slice(0, 8)}
              </p>
              <p className="text-[11px] text-fg-subtle">{formatDate(comparisonData.base_run.created_at)}</p>
            </div>
            <div className="hidden items-center bg-surface-2 px-2 text-fg-faint sm:flex">
              <ArrowRight className="size-4" />
            </div>
            <div className="bg-surface-2 px-4 py-3">
              <Eyebrow>Target run</Eyebrow>
              <p className="mt-1 font-mono text-[13px] text-fg">
                {comparisonData.target_run.id.slice(0, 8)}
              </p>
              <p className="text-[11px] text-fg-subtle">{formatDate(comparisonData.target_run.created_at)}</p>
            </div>
            <div className="bg-surface-2 px-4 py-3">
              <Eyebrow>Regressed cases</Eyebrow>
              <p className="tabular mt-1 font-mono text-lg font-medium text-danger">
                {comparisonData.regressed_cases_count}
              </p>
            </div>
            <div className="bg-surface-2 px-4 py-3">
              <Eyebrow>Improved cases</Eyebrow>
              <p className="tabular mt-1 font-mono text-lg font-medium text-success">
                {comparisonData.improved_cases_count}
              </p>
            </div>
          </div>

          <div className="overflow-hidden rounded-lg border border-line">
            <TableWrap>
              <THead>
                <tr>
                  <Th>Metric</Th>
                  <Th className="text-right">Baseline</Th>
                  <Th className="text-right">Target</Th>
                  <Th>Delta</Th>
                  <Th className="text-right">Status</Th>
                </tr>
              </THead>
              <TBody>
                {COMPARISON_ROWS.map((row) => {
                  const d = comparisonData.deltas[row.key];
                  return (
                    <Tr key={row.key}>
                      <Td className="font-medium text-fg">{row.label}</Td>
                      <Td className="tabular text-right font-mono text-xs text-fg-subtle">
                        {row.format(d.base_value)}
                      </Td>
                      <Td className="tabular text-right font-mono text-xs text-fg">
                        {row.format(d.target_value)}
                      </Td>
                      <Td>{renderDeltaBadge(d, row.isLatency)}</Td>
                      <Td
                        className={cn(
                          "text-right text-[11px] font-medium uppercase tracking-wide",
                          d.status === "improved"
                            ? "text-success"
                            : d.status === "regressed"
                            ? "text-danger"
                            : "text-fg-subtle"
                        )}
                      >
                        {d.status}
                      </Td>
                    </Tr>
                  );
                })}
              </TBody>
            </TableWrap>
          </div>
        </Dialog>
      )}
    </AppShell>
  );
}
