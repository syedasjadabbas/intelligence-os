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
import { cn, getErrorMessage } from "@/lib/utils";
import {
  ArrowLeft,
  Ban,
  ChevronLeft,
  ChevronRight,
  Clock,
  CircleX,
  FileSearch,
  ListFilter,
  RefreshCw,
  ScanSearch,
  Search,
} from "lucide-react";
import { AppShell, PageHeader } from "@/components/app-shell";
import { JudgeBadge, PassFailBadge, RunStatusBadge, passRateTone } from "@/components/status";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button, ButtonLink } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { IconInput, Select } from "@/components/ui/field";
import { MetricGrid, MetricTile } from "@/components/ui/metric";
import { LoadingState, Skeleton, Spinner } from "@/components/ui/spinner";
import {
  EmptyState,
  Eyebrow,
  Panel,
  PanelHeader,
  ProgressBar,
  Segmented,
} from "@/components/ui/surface";
import { TableMessage, TableWrap, TBody, Td, Th, THead, Tr } from "@/components/ui/table";

interface PageProps {
  params: Promise<{ id: string }>;
}

const fmt = (v: number | null | undefined, digits: number) =>
  v !== null && v !== undefined ? v.toFixed(digits) : "—";

export default function EvaluationRunDetailPage({ params }: PageProps) {
  const resolvedParams = use(params);
  const runId = resolvedParams.id;

  const { user } = useAuth();
  const isAdmin = user?.role === "ADMIN";

  // Run detail state
  const [run, setRun] = useState<EvaluationRunDetail | null>(null);
  const [loadingRun, setLoadingRun] = useState(true);
  const [runError, setRunError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [actionFeedback, setActionFeedback] = useState<string | null>(null);

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
    } catch (err: unknown) {
      setRunError(getErrorMessage(err) || "Failed to load evaluation run details.");
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
    } catch (err: unknown) {
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
    } catch (err: unknown) {
      console.error("Failed to inspect evaluation result:", err);
    } finally {
      setLoadingDetail(false);
    }
  };

  // Cancel run handler (Phase 5C)
  const handleCancelRun = async () => {
    if (!isAdmin) return;
    if (!confirm("Are you sure you want to cancel this evaluation run?")) return;
    setCancelling(true);
    setActionFeedback(null);
    try {
      await api.cancelEvaluation(runId);
      setActionFeedback("Evaluation run cancelled successfully.");
      await fetchRunDetail();
      await fetchResults();
    } catch (err: unknown) {
      setRunError(getErrorMessage(err) || "Failed to cancel evaluation run.");
    } finally {
      setCancelling(false);
    }
  };

  const closeInspector = () => {
    setSelectedResultId(null);
    setInspectingResult(null);
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

  const runProgressPct = run
    ? Math.round(((run.progress_current ?? 0) / (run.progress_total || 1)) * 100)
    : 0;

  return (
    <AppShell>
      <PageHeader
        eyebrow={
          <Link
            href="/evaluations"
            className="inline-flex items-center gap-1.5 text-fg-subtle transition-colors hover:text-fg"
          >
            <ArrowLeft className="size-3.5" />
            All Evaluations
          </Link>
        }
        title={
          <span className="flex items-baseline gap-2">
            <span className="font-normal text-fg-subtle">Run</span>
            <span className="font-mono">{runId.slice(0, 8)}</span>
          </span>
        }
        meta={
          run && (
            <>
              <Badge tone="neutral" size="md">
                {run.dataset_name}
                <span className="font-mono text-fg-subtle">v{run.dataset_version}</span>
              </Badge>
              <JudgeBadge judgeType={run.judge_type} long />
              <RunStatusBadge
                size="md"
                run={{
                  ...run,
                  progress_total: run.progress_total || run.total_test_cases,
                }}
              />
            </>
          )
        }
        description="Benchmark execution details, candidate rankings, grounding evidence and judge diagnostics."
        actions={
          <>
            {isAdmin && run && (run.status === "PENDING" || run.status === "RUNNING") && (
              <Button
                variant="danger"
                onClick={handleCancelRun}
                disabled={cancelling}
                title="Cancel this evaluation run"
              >
                {cancelling ? <Spinner /> : <Ban />}
                Cancel Run
              </Button>
            )}
            <Button
              variant="secondary"
              onClick={() => {
                fetchRunDetail();
                fetchResults();
              }}
              title="Refresh"
            >
              <RefreshCw className={cn(loadingRun && "animate-spin")} />
              Refresh
            </Button>
          </>
        }
      />

      <div className="space-y-6">
        {runError && <Alert tone="danger">{runError}</Alert>}

        {actionFeedback && <Alert tone="success">{actionFeedback}</Alert>}

        {/* Lifecycle banners */}
        {run && run.status === "CANCELLED" && (
          <Alert tone="neutral" icon={<Ban />} title="Evaluation Run Cancelled">
            {run.error_message || "This evaluation run was cancelled by an administrator."} Completed
            test cases ({run.progress_current ?? 0}/{run.total_test_cases}) and partial results are
            preserved below.
          </Alert>
        )}

        {run && run.status === "RUNNING" && (
          <div className="flex flex-col gap-4 rounded-lg border border-info/25 bg-info/[0.06] px-4 py-3.5 animate-rise-in sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <Spinner className="mt-0.5 size-4 text-info" />
              <div>
                <p className="text-[13px] font-medium text-fg">Evaluation Run in Progress</p>
                <p className="text-[13px] text-fg-muted">
                  Executing benchmark cases and evaluating retrieval &amp; generation quality in the
                  background…
                </p>
              </div>
            </div>
            <div className="w-full space-y-1.5 sm:w-64">
              <div className="tabular flex items-center justify-between font-mono text-xs">
                <span className="text-fg-muted">
                  {run.progress_current ?? 0} / {run.progress_total || run.total_test_cases} cases
                </span>
                <span className="text-info">{runProgressPct}%</span>
              </div>
              <ProgressBar value={runProgressPct} tone="info" label="Evaluation progress" />
            </div>
          </div>
        )}

        {run && run.status === "PENDING" && (
          <Alert tone="warning" icon={<Clock className="animate-pulse" />} title="Evaluation Queued">
            The run has been registered and is queued for execution. Polling for live updates…
          </Alert>
        )}

        {run && run.status === "FAILED" && (
          <Alert tone="danger" title="Evaluation Run Failed">
            <p>{run.error_message || "An unexpected error interrupted benchmark evaluation."}</p>
            <p className="mt-1 text-xs text-fg-subtle">
              {run.progress_current ?? 0} out of {run.progress_total || run.total_test_cases} test
              cases were evaluated before failure.
            </p>
          </Alert>
        )}

        {/* Loading skeleton for first load */}
        {loadingRun && !run && (
          <div className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-line bg-line sm:grid-cols-4 xl:grid-cols-8">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="space-y-3 bg-surface px-4 py-3.5">
                <Skeleton className="h-3 w-16" />
                <Skeleton className="h-6 w-20" />
                <Skeleton className="h-[3px] w-full" />
              </div>
            ))}
          </div>
        )}

        {/* Not found / inaccessible */}
        {!loadingRun && !run && (
          <Panel>
            <EmptyState
              icon={<CircleX className="text-danger" />}
              title="Evaluation Run Not Found"
              description="This evaluation run does not exist, has been deleted, or belongs to another tenant organization."
              action={
                <ButtonLink href="/evaluations" variant="primary">
                  <ArrowLeft />
                  Return to Evaluation Dashboard
                </ButtonLink>
              }
            />
          </Panel>
        )}

        {run && (
          <>
            <MetricGrid>
              <MetricTile
                label="Pass rate"
                value={`${(run.pass_rate * 100).toFixed(1)}%`}
                tone={passRateTone(run.pass_rate)}
                meter={run.pass_rate}
                hint={`${run.passed_test_cases}/${run.total_test_cases} passed`}
              />
              <MetricTile
                label="Recall@5"
                value={fmt(run.recall_at_5, 3)}
                meter={run.recall_at_5}
                hint={`R@3: ${run.recall_at_3?.toFixed(3) || "—"}`}
              />
              <MetricTile
                label="nDCG@5"
                value={fmt(run.ndcg_at_5, 3)}
                meter={run.ndcg_at_5}
                hint="Rank discounted gain"
              />
              <MetricTile label="MRR" value={fmt(run.mrr, 3)} meter={run.mrr} hint="First hit rank" />
              <MetricTile
                label="Faithfulness"
                value={fmt(run.mean_faithfulness, 3)}
                meter={run.mean_faithfulness}
                tone="accent"
                hint="Zero-hallucination"
              />
              <MetricTile
                label="Correctness"
                value={fmt(run.mean_correctness, 3)}
                meter={run.mean_correctness}
                hint="Factual match"
              />
              <MetricTile
                label="Completeness"
                value={fmt(run.mean_completeness, 3)}
                meter={run.mean_completeness}
                hint="Key facts coverage"
              />
              <MetricTile
                label="Latency"
                value={run.mean_latency_ms ? `${Math.round(run.mean_latency_ms)}ms` : "—"}
                tone="warning"
                hint={`P95: ${run.latency_p95_ms ? `${Math.round(run.latency_p95_ms)}ms` : "—"}`}
              />
            </MetricGrid>

            {failedCount > 0 ? (
              <Alert
                tone="danger"
                title={`${failedCount} Benchmark Case${failedCount > 1 ? "s" : ""} Failed`}
                action={
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => {
                      setStatusFilter("failed");
                      setPage(1);
                    }}
                  >
                    Show Failed Cases Only
                  </Button>
                }
              >
                Retrieval or judge threshold deficiencies identified. Isolate failed cases for
                triage.
              </Alert>
            ) : (
              <Alert tone="success">
                All benchmark test cases in this run passed all validation gates and quality
                thresholds.
              </Alert>
            )}
          </>
        )}

        {/* Case results */}
        <Panel>
          <PanelHeader
            title="Test case results"
            count={totalResults}
            description="Inspect candidate chunks, reranker position shifts, citations and judge scores."
          >
            <div className="mt-3 flex flex-col gap-2 lg:flex-row lg:items-center">
              <Segmented
                ariaLabel="Filter by result"
                value={statusFilter}
                onChange={(v) => {
                  setStatusFilter(v);
                  setPage(1);
                }}
                options={[
                  { value: "all", label: <>All <span className="tabular font-mono opacity-70">{run?.total_test_cases || 0}</span></> },
                  { value: "failed", tone: "danger", label: <>Failed <span className="tabular font-mono opacity-70">{failedCount}</span></> },
                  { value: "passed", tone: "success", label: <>Passed <span className="tabular font-mono opacity-70">{run?.passed_test_cases || 0}</span></> },
                ]}
              />
              <div className="flex flex-1 flex-col gap-2 sm:flex-row lg:justify-end">
                <div className="relative">
                  <ListFilter className="pointer-events-none absolute left-2.5 top-1/2 z-10 size-3.5 -translate-y-1/2 text-fg-subtle" />
                  <Select
                    aria-label="Filter by category"
                    value={categoryFilter}
                    onChange={(e) => {
                      setCategoryFilter(e.target.value);
                      setPage(1);
                    }}
                    className="h-8 pl-8 font-mono text-xs"
                  >
                    {categories.map((c) => (
                      <option key={c} value={c}>
                        {c === "all" ? "All Categories" : c}
                      </option>
                    ))}
                  </Select>
                </div>
                <IconInput
                  icon={Search}
                  type="text"
                  aria-label="Filter queries"
                  placeholder="Filter queries..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="h-8 text-[13px]"
                  wrapperClassName="sm:w-56"
                />
              </div>
            </div>
          </PanelHeader>

          <TableWrap>
            <THead>
              <tr>
                <Th>Case</Th>
                <Th className="min-w-[16rem]">Query</Th>
                <Th>Category</Th>
                <Th>Result</Th>
                <Th className="text-right">R@5</Th>
                <Th className="text-right">nDCG@5</Th>
                <Th className="text-right">Faithful.</Th>
                <Th className="text-right">Correct.</Th>
                <Th className="text-right">Latency</Th>
                <Th className="text-right">
                  <span className="sr-only">Action</span>
                </Th>
              </tr>
            </THead>
            <TBody>
              {loadingResults ? (
                <TableMessage colSpan={10}>
                  <LoadingState label="Loading benchmark results…" />
                </TableMessage>
              ) : filteredResults.length === 0 ? (
                <TableMessage colSpan={10}>
                  <EmptyState
                    icon={<FileSearch />}
                    title="No matching test cases found"
                    description="Adjust the result, category or query filters."
                  />
                </TableMessage>
              ) : (
                filteredResults.map((r) => (
                  <Tr
                    key={r.id}
                    selected={selectedResultId === r.id}
                    className={cn(!r.passed && "[&>td:first-child]:shadow-[inset_2px_0_0_0_var(--color-danger)]")}
                  >
                    <Td className="whitespace-nowrap font-mono text-xs text-fg-muted">{r.test_case_id}</Td>
                    <Td className="max-w-xs">
                      <p className="truncate text-fg" title={r.query}>
                        {r.query}
                      </p>
                    </Td>
                    <Td>
                      <Badge tone="neutral" mono>
                        {r.query_type}
                      </Badge>
                    </Td>
                    <Td>
                      <PassFailBadge passed={r.passed} />
                    </Td>
                    <Td className="tabular text-right font-mono text-xs text-fg-muted">{fmt(r.recall_at_5, 2)}</Td>
                    <Td className="tabular text-right font-mono text-xs text-fg-muted">{fmt(r.ndcg_at_5, 2)}</Td>
                    <Td className="tabular text-right font-mono text-xs text-accent-strong">{fmt(r.faithfulness, 2)}</Td>
                    <Td className="tabular text-right font-mono text-xs text-fg-muted">{fmt(r.correctness, 2)}</Td>
                    <Td className="tabular whitespace-nowrap text-right font-mono text-xs text-warning">
                      {r.total_latency_ms ? `${Math.round(r.total_latency_ms)}ms` : "—"}
                    </Td>
                    <Td className="text-right">
                      <Button variant="secondary" size="xs" onClick={() => handleInspectCase(r.id)}>
                        <ScanSearch />
                        Inspect
                      </Button>
                    </Td>
                  </Tr>
                ))
              )}
            </TBody>
          </TableWrap>

          {totalResults > pageSize && (
            <div className="flex flex-col items-center justify-between gap-3 border-t border-line px-4 py-3 text-xs text-fg-subtle sm:flex-row sm:px-5">
              <span className="tabular">
                Showing {(page - 1) * pageSize + 1} - {Math.min(page * pageSize, totalResults)} of{" "}
                {totalResults} cases
              </span>
              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  size="xs"
                  disabled={page <= 1}
                  onClick={() => setPage(page - 1)}
                >
                  <ChevronLeft />
                  Previous
                </Button>
                <span className="tabular px-1">
                  Page {page} of {Math.ceil(totalResults / pageSize)}
                </span>
                <Button
                  variant="secondary"
                  size="xs"
                  disabled={page * pageSize >= totalResults}
                  onClick={() => setPage(page + 1)}
                >
                  Next
                  <ChevronRight />
                </Button>
              </div>
            </div>
          )}
        </Panel>
      </div>

      {/* Case inspection sheet */}
      {selectedResultId && (
        <Dialog
          variant="right"
          onClose={closeInspector}
          title={
            inspectingResult ? (
              <span>
                Case <span className="font-mono">{inspectingResult.test_case_id}</span>
              </span>
            ) : (
              "Case inspection"
            )
          }
          meta={
            inspectingResult && (
              <>
                <PassFailBadge passed={inspectingResult.passed} />
                <Badge tone="neutral" mono>
                  {inspectingResult.query_type}
                </Badge>
              </>
            )
          }
          description={
            inspectingResult ? (
              <>
                Expected behavior:{" "}
                <span className="font-medium uppercase text-fg-muted">
                  {inspectingResult.expected_behavior}
                </span>
              </>
            ) : undefined
          }
          footer={
            <Button variant="secondary" onClick={closeInspector}>
              Close Inspection
            </Button>
          }
          bodyClassName="p-0"
        >
          {loadingDetail ? (
            <LoadingState label="Loading case detail inspection…" className="py-24" />
          ) : inspectingResult ? (
            <>
              <div className="sticky top-0 z-10 border-b border-line bg-surface/95 px-5 py-3 backdrop-blur">
                <Segmented
                  role="tablist"
                  ariaLabel="Inspection sections"
                  value={detailTab}
                  onChange={setDetailTab}
                  className="w-full overflow-x-auto sm:w-auto"
                  options={[
                    { value: "overview", label: "Overview & Synthesis" },
                    {
                      value: "chunks",
                      label: (
                        <>
                          Retrieved vs Reranked
                          <span className="tabular font-mono opacity-70">
                            {inspectingResult.reranked_candidates?.length || 0}
                          </span>
                        </>
                      ),
                    },
                    { value: "judge", label: "Judge & Trace" },
                  ]}
                />
              </div>

              <div className="space-y-6 px-5 py-5" role="tabpanel">
                {detailTab === "overview" && (
                  <>
                    {!inspectingResult.passed && inspectingResult.failure_reason && (
                      <Alert tone="danger" title="Failure reason">
                        {inspectingResult.failure_reason}
                      </Alert>
                    )}

                    <div className="space-y-2">
                      <Eyebrow>Benchmark query</Eyebrow>
                      <p className="text-[15px] font-medium leading-relaxed text-fg">
                        {inspectingResult.query}
                      </p>
                    </div>

                    <div className="space-y-2">
                      <Eyebrow className="text-accent-strong">Generated answer</Eyebrow>
                      <div className="whitespace-pre-wrap rounded-md border border-line bg-surface-2 px-4 py-3 text-[13px] leading-relaxed text-fg/90">
                        {inspectingResult.generated_answer || "(Empty answer)"}
                      </div>
                    </div>

                    <div className="space-y-2">
                      <Eyebrow>Grounded citations ({inspectingResult.citations?.length || 0})</Eyebrow>
                      {inspectingResult.citations?.length === 0 ? (
                        <p className="text-[13px] italic text-fg-subtle">
                          No citations attached (Refusal or ungrounded response).
                        </p>
                      ) : (
                        <ol className="space-y-2">
                          {inspectingResult.citations.map((c, idx) => (
                            <li key={idx} className="rounded-md border border-line bg-surface-2 px-3.5 py-3">
                              <div className="mb-1.5 flex items-center justify-between gap-3 text-[13px]">
                                <span className="min-w-0 truncate font-medium text-fg">
                                  <span className="mr-1.5 font-mono text-xs text-accent-strong">[Source {idx + 1}]</span>
                                  {c.document_title}
                                </span>
                                {c.page_number && (
                                  <span className="shrink-0 font-mono text-[11px] text-fg-subtle">p. {c.page_number}</span>
                                )}
                              </div>
                              <p className="text-xs italic leading-relaxed text-fg-subtle">
                                &ldquo;{c.content?.slice(0, 200)}...&rdquo;
                              </p>
                            </li>
                          ))}
                        </ol>
                      )}
                    </div>
                  </>
                )}

                {detailTab === "chunks" && (
                  <>
                    <p className="text-[13px] text-fg-subtle">
                      Top candidates returned by hybrid search and reranked by the cross-encoder:
                    </p>
                    <ol className="space-y-2.5">
                      {inspectingResult.reranked_candidates.map((cand, idx) => (
                        <li key={idx} className="rounded-md border border-line bg-surface-2">
                          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-3.5 py-2.5">
                            <span className="flex min-w-0 items-center gap-2.5 text-[13px]">
                              <span className="tabular flex size-5 shrink-0 items-center justify-center rounded bg-accent/15 font-mono text-[11px] font-medium text-accent-strong">
                                {idx + 1}
                              </span>
                              <span className="truncate font-medium text-fg">{cand.document_title}</span>
                              {cand.section_heading && (
                                <span className="truncate text-fg-subtle">— {cand.section_heading}</span>
                              )}
                            </span>
                            <span className="tabular flex items-center gap-3 font-mono text-[11px]">
                              <span className="text-accent-strong">
                                Rerank {cand.rerank_score !== null && cand.rerank_score !== undefined ? cand.rerank_score.toFixed(3) : "—"}
                              </span>
                              <span className="text-fg-subtle">Hybrid {cand.score?.toFixed(4)}</span>
                            </span>
                          </div>
                          <p className="px-3.5 py-3 text-xs leading-relaxed text-fg-muted">{cand.content}</p>
                        </li>
                      ))}
                    </ol>
                  </>
                )}

                {detailTab === "judge" && (
                  <>
                    <div className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-line bg-line sm:grid-cols-4">
                      {[
                        { label: "Faithfulness", value: inspectingResult.faithfulness, tone: "text-accent-strong" },
                        { label: "Correctness", value: inspectingResult.correctness, tone: "text-fg" },
                        { label: "Completeness", value: inspectingResult.completeness, tone: "text-fg" },
                        { label: "Citation correctness", value: inspectingResult.citation_correctness, tone: "text-success" },
                      ].map((s) => (
                        <div key={s.label} className="bg-surface-2 px-3.5 py-3">
                          <p className="truncate text-[11px] text-fg-subtle">{s.label}</p>
                          <p className={cn("tabular mt-1.5 font-mono text-lg font-medium", s.tone)}>
                            {s.value != null ? s.value.toFixed(2) : "—"}
                          </p>
                        </div>
                      ))}
                    </div>

                    <div className="space-y-2">
                      <Eyebrow>Judge qualitative reasoning</Eyebrow>
                      <p className="whitespace-pre-wrap rounded-md border border-line bg-surface-2 px-4 py-3 text-[13px] leading-relaxed text-fg-muted">
                        {inspectingResult.judge_output?.reasoning || "No qualitative notes provided."}
                      </p>
                    </div>

                    <div className="space-y-2">
                      <Eyebrow>Reranker shift &amp; trace metadata</Eyebrow>
                      <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-md border border-line bg-line font-mono text-xs">
                        {[
                          ["Position Shift", String(inspectingResult.trace_data?.position_shift ?? 0)],
                          ["Promoted to Top 3", inspectingResult.trace_data?.promoted_to_top3 ? "Yes" : "No"],
                          ["Rank Before", String(inspectingResult.trace_data?.rank_before ?? "—")],
                          ["Rank After", String(inspectingResult.trace_data?.rank_after ?? "—")],
                        ].map(([k, v]) => (
                          <div key={k} className="flex items-center justify-between gap-3 bg-surface-2 px-3.5 py-2.5">
                            <dt className="text-fg-subtle">{k}</dt>
                            <dd className="tabular text-fg">{v}</dd>
                          </div>
                        ))}
                      </dl>
                    </div>
                  </>
                )}
              </div>
            </>
          ) : null}
        </Dialog>
      )}
    </AppShell>
  );
}
