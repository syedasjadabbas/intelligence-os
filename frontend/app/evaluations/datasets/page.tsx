"use client";

import React, { useState, useEffect, useCallback, useMemo, useReducer } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import {
  api,
  DatasetListItem,
  DatasetDetail,
  TestCaseDetail,
  TestCaseCreate,
  TestCaseUpdate,
  EvidenceAnchor,
} from "@/lib/api";
import { cn, formatDate, getErrorMessage } from "@/lib/utils";
import {
  ArrowLeft,
  BookOpen,
  ChevronDown,
  Database,
  FileJson,
  FileText,
  Info,
  Pencil,
  Play,
  Plus,
  RefreshCw,
  Search,
  ShieldAlert,
  Trash2,
  Upload,
} from "lucide-react";
import { AppShell, PageHeader } from "@/components/app-shell";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button, ButtonLink } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Field, IconInput, Input, Select, Textarea } from "@/components/ui/field";
import { LoadingState, Spinner } from "@/components/ui/spinner";
import { EmptyState, Eyebrow, Panel, PanelHeader } from "@/components/ui/surface";
import {
  caseFormReducer,
  getCaseSubmitTarget,
  initialCaseFormState,
} from "./case-form-state";

/** Raw item shape accepted by the JSON importer (validated field by field below). */
interface ImportedCase {
  case_identifier?: string;
  query?: string;
  question?: string;
  query_type?: string;
  expected_behavior?: string;
  ground_truth_answer?: string | null;
  answer?: string | null;
  key_facts?: unknown;
  ground_truth_evidence?: unknown;
}

const QUERY_TYPE_OPTIONS = [
  { value: "factoid", label: "Factoid" },
  { value: "multi_hop", label: "Multi-Hop" },
  { value: "coreference", label: "Coreference" },
  { value: "refusal", label: "Refusal" },
  { value: "citation_needed", label: "Citation Needed" },
  { value: "temporal", label: "Temporal" },
  { value: "comparative", label: "Comparative" },
  { value: "summarization", label: "Summarization" },
];

export default function DatasetsManagementPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "ADMIN";

  // Datasets state
  const [datasets, setDatasets] = useState<DatasetListItem[]>([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState<string | null>(null);
  const [selectedDatasetDetail, setSelectedDatasetDetail] = useState<DatasetDetail | null>(null);
  const [loadingDatasets, setLoadingDatasets] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Filters for test cases
  const [searchQuery, setSearchQuery] = useState("");
  const [queryTypeFilter, setQueryTypeFilter] = useState("all");
  const [behaviorFilter, setBehaviorFilter] = useState("all");
  const [expandedCaseId, setExpandedCaseId] = useState<string | null>(null);

  // Modals state
  const [showCreateDatasetModal, setShowCreateDatasetModal] = useState(false);
  const [showEditDatasetModal, setShowEditDatasetModal] = useState(false);
  const [showDeleteDatasetModal, setShowDeleteDatasetModal] = useState(false);

  // Add / edit case dialog: the edited case is cleared whenever the dialog closes
  const [caseForm, dispatchCaseForm] = useReducer(caseFormReducer, initialCaseFormState);
  const showAddCaseModal = caseForm.mode === "add";
  const showEditCaseModal = caseForm.mode === "edit";
  const editingCase = caseForm.editingCase;
  const [showDeleteCaseModal, setShowDeleteCaseModal] = useState(false);
  const [caseToDelete, setCaseToDelete] = useState<TestCaseDetail | null>(null);

  const [showImportModal, setShowImportModal] = useState(false);

  // Form states - Dataset
  const [datasetFormName, setDatasetFormName] = useState("");
  const [datasetFormVersion, setDatasetFormVersion] = useState("1.0.0");
  const [datasetFormDesc, setDatasetFormDesc] = useState("");
  const [submittingDataset, setSubmittingDataset] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Form states - Test Case
  const [caseIdInput, setCaseIdInput] = useState("");
  const [caseQueryInput, setCaseQueryInput] = useState("");
  const [caseQueryTypeInput, setCaseQueryTypeInput] = useState("factoid");
  const [caseBehaviorInput, setCaseBehaviorInput] = useState("answer");
  const [caseGroundTruthInput, setCaseGroundTruthInput] = useState("");
  const [caseKeyFactsInput, setCaseKeyFactsInput] = useState("");
  const [evidenceDocTitle, setEvidenceDocTitle] = useState("");
  const [evidenceSection, setEvidenceSection] = useState("");
  const [evidencePageNum, setEvidencePageNum] = useState<string>("");
  const [evidenceAnchorsInput, setEvidenceAnchorsInput] = useState("");
  const [submittingCase, setSubmittingCase] = useState(false);
  const [caseFormError, setCaseFormError] = useState<string | null>(null);

  // Import JSON state
  const [importJsonText, setImportJsonText] = useState("");
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [importProgress, setImportProgress] = useState<{ current: number; total: number } | null>(null);

  // Dismiss notifications
  useEffect(() => {
    if (successMessage) {
      const timer = setTimeout(() => setSuccessMessage(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [successMessage]);

  // Fetch dataset list
  const fetchDatasets = useCallback(async (autoSelectId?: string) => {
    setLoadingDatasets(true);
    setGlobalError(null);
    try {
      const res = await api.listDatasets({ limit: 100 });
      const items = res.items || [];
      setDatasets(items);

      if (autoSelectId) {
        setSelectedDatasetId(autoSelectId);
      } else if (items.length > 0 && (!selectedDatasetId || !items.find((d) => d.id === selectedDatasetId))) {
        setSelectedDatasetId(items[0].id);
      } else if (items.length === 0) {
        setSelectedDatasetId(null);
        setSelectedDatasetDetail(null);
      }
    } catch (err: unknown) {
      setGlobalError(getErrorMessage(err) || "Failed to load datasets.");
    } finally {
      setLoadingDatasets(false);
    }
  }, [selectedDatasetId]);

  // Fetch dataset details when selectedDatasetId changes
  const fetchDatasetDetail = useCallback(async (datasetId: string) => {
    setLoadingDetail(true);
    setGlobalError(null);
    try {
      const detail = await api.getDataset(datasetId);
      setSelectedDatasetDetail(detail);
    } catch (err: unknown) {
      setGlobalError(getErrorMessage(err) || "Failed to load dataset details.");
      setSelectedDatasetDetail(null);
    } finally {
      setLoadingDetail(false);
    }
  }, []);

  useEffect(() => {
    if (user) {
      fetchDatasets();
    }
  }, [user, fetchDatasets]);

  useEffect(() => {
    if (selectedDatasetId) {
      fetchDatasetDetail(selectedDatasetId);
    }
  }, [selectedDatasetId, fetchDatasetDetail]);

  // Filtered Test Cases
  const filteredCases = useMemo(() => {
    if (!selectedDatasetDetail?.test_cases) return [];
    return selectedDatasetDetail.test_cases.filter((tc) => {
      const matchesSearch =
        searchQuery === "" ||
        tc.query.toLowerCase().includes(searchQuery.toLowerCase()) ||
        tc.case_identifier.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (tc.ground_truth_answer &&
          tc.ground_truth_answer.toLowerCase().includes(searchQuery.toLowerCase()));

      const matchesType =
        queryTypeFilter === "all" || tc.query_type === queryTypeFilter;

      const matchesBehavior =
        behaviorFilter === "all" || tc.expected_behavior === behaviorFilter;

      return matchesSearch && matchesType && matchesBehavior;
    });
  }, [selectedDatasetDetail, searchQuery, queryTypeFilter, behaviorFilter]);

  // ==========================================
  // Dataset CRUD Handlers
  // ==========================================
  const handleOpenCreateDataset = () => {
    setDatasetFormName("");
    setDatasetFormVersion("1.0.0");
    setDatasetFormDesc("");
    setFormError(null);
    setShowCreateDatasetModal(true);
  };

  const handleOpenEditDataset = () => {
    if (!selectedDatasetDetail) return;
    setDatasetFormName(selectedDatasetDetail.name);
    setDatasetFormVersion(selectedDatasetDetail.version);
    setDatasetFormDesc(selectedDatasetDetail.description || "");
    setFormError(null);
    setShowEditDatasetModal(true);
  };

  const handleCreateDataset = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isAdmin) return;
    if (!datasetFormName.trim()) {
      setFormError("Dataset name is required.");
      return;
    }

    setSubmittingDataset(true);
    setFormError(null);
    try {
      const created = await api.createDataset({
        name: datasetFormName.trim(),
        version: datasetFormVersion.trim() || "1.0.0",
        description: datasetFormDesc.trim() || null,
      });
      setShowCreateDatasetModal(false);
      setSuccessMessage(`Dataset "${created.name}" created successfully.`);
      await fetchDatasets(created.id);
    } catch (err: unknown) {
      setFormError(getErrorMessage(err) || "Failed to create dataset.");
    } finally {
      setSubmittingDataset(false);
    }
  };

  const handleUpdateDataset = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isAdmin || !selectedDatasetId) return;
    if (!datasetFormName.trim()) {
      setFormError("Dataset name is required.");
      return;
    }

    setSubmittingDataset(true);
    setFormError(null);
    try {
      const updated = await api.updateDataset(selectedDatasetId, {
        name: datasetFormName.trim(),
        version: datasetFormVersion.trim() || "1.0.0",
        description: datasetFormDesc.trim() || null,
      });
      setShowEditDatasetModal(false);
      setSuccessMessage(`Dataset "${updated.name}" updated successfully.`);
      await fetchDatasets(updated.id);
      await fetchDatasetDetail(updated.id);
    } catch (err: unknown) {
      setFormError(getErrorMessage(err) || "Failed to update dataset.");
    } finally {
      setSubmittingDataset(false);
    }
  };

  const handleDeleteDataset = async () => {
    if (!isAdmin || !selectedDatasetId) return;
    setSubmittingDataset(true);
    try {
      await api.deleteDataset(selectedDatasetId);
      setShowDeleteDatasetModal(false);
      setSuccessMessage("Dataset deleted successfully.");
      await fetchDatasets();
    } catch (err: unknown) {
      setGlobalError(getErrorMessage(err) || "Failed to delete dataset.");
    } finally {
      setSubmittingDataset(false);
    }
  };

  // ==========================================
  // Test Case CRUD Handlers
  // ==========================================
  const resetCaseForm = () => {
    setCaseIdInput("");
    setCaseQueryInput("");
    setCaseQueryTypeInput("factoid");
    setCaseBehaviorInput("answer");
    setCaseGroundTruthInput("");
    setCaseKeyFactsInput("");
    setEvidenceDocTitle("");
    setEvidenceSection("");
    setEvidencePageNum("");
    setEvidenceAnchorsInput("");
    setCaseFormError(null);
  };

  const handleOpenAddCase = () => {
    resetCaseForm();
    const nextNum = (selectedDatasetDetail?.test_cases?.length || 0) + 1;
    setCaseIdInput(`case_${String(nextNum).padStart(3, "0")}`);
    dispatchCaseForm({ type: "openAdd" });
  };

  const handleOpenEditCase = (tc: TestCaseDetail) => {
    setCaseIdInput(tc.case_identifier);
    setCaseQueryInput(tc.query);
    setCaseQueryTypeInput(tc.query_type || "factoid");
    setCaseBehaviorInput(tc.expected_behavior || "answer");
    setCaseGroundTruthInput(tc.ground_truth_answer || "");
    setCaseKeyFactsInput((tc.key_facts || []).join("\n"));

    if (tc.ground_truth_evidence && tc.ground_truth_evidence.length > 0) {
      const firstEvidence = tc.ground_truth_evidence[0];
      setEvidenceDocTitle(firstEvidence.document_title || "");
      setEvidenceSection(firstEvidence.section_heading || "");
      setEvidencePageNum(firstEvidence.page_number ? String(firstEvidence.page_number) : "");
      setEvidenceAnchorsInput((firstEvidence.content_anchors || []).join("\n"));
    } else {
      setEvidenceDocTitle("");
      setEvidenceSection("");
      setEvidencePageNum("");
      setEvidenceAnchorsInput("");
    }

    setCaseFormError(null);
    dispatchCaseForm({ type: "openEdit", testCase: tc });
  };

  const buildEvidencePayload = (): EvidenceAnchor[] => {
    if (!evidenceDocTitle.trim()) return [];
    const anchors = evidenceAnchorsInput
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);
    return [
      {
        document_title: evidenceDocTitle.trim(),
        section_heading: evidenceSection.trim() || null,
        page_number: evidencePageNum ? parseInt(evidencePageNum, 10) || null : null,
        content_anchors: anchors,
      },
    ];
  };

  const handleSaveCase = async (e: React.FormEvent) => {
    e.preventDefault();
    const submitTarget = getCaseSubmitTarget(caseForm);
    if (!isAdmin || !selectedDatasetId || !submitTarget) return;

    if (!caseIdInput.trim()) {
      setCaseFormError("Case identifier is required.");
      return;
    }
    if (!caseQueryInput.trim()) {
      setCaseFormError("Query / question is required.");
      return;
    }

    setSubmittingCase(true);
    setCaseFormError(null);

    const keyFacts = caseKeyFactsInput
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);

    const evidence = buildEvidencePayload();

    try {
      if (submitTarget.kind === "update") {
        // Edit Case
        const payload: TestCaseUpdate = {
          case_identifier: caseIdInput.trim(),
          query: caseQueryInput.trim(),
          query_type: caseQueryTypeInput,
          expected_behavior: caseBehaviorInput,
          ground_truth_answer: caseGroundTruthInput.trim() || null,
          key_facts: keyFacts,
          ground_truth_evidence: evidence,
        };
        await api.updateTestCase(selectedDatasetId, submitTarget.caseId, payload);
        dispatchCaseForm({ type: "close" });
        setSuccessMessage(`Test case "${caseIdInput.trim()}" updated.`);
      } else {
        // Create Case
        const payload: TestCaseCreate = {
          case_identifier: caseIdInput.trim(),
          query: caseQueryInput.trim(),
          query_type: caseQueryTypeInput,
          expected_behavior: caseBehaviorInput,
          ground_truth_answer: caseGroundTruthInput.trim() || null,
          key_facts: keyFacts,
          ground_truth_evidence: evidence,
        };
        await api.addTestCase(selectedDatasetId, payload);
        dispatchCaseForm({ type: "close" });
        setSuccessMessage(`Test case "${caseIdInput.trim()}" added.`);
      }

      await fetchDatasetDetail(selectedDatasetId);
      await fetchDatasets(selectedDatasetId);
    } catch (err: unknown) {
      setCaseFormError(getErrorMessage(err) || "Failed to save test case.");
    } finally {
      setSubmittingCase(false);
    }
  };

  const handleDeleteCase = async () => {
    if (!isAdmin || !selectedDatasetId || !caseToDelete) return;
    setSubmittingCase(true);
    try {
      await api.deleteTestCase(selectedDatasetId, caseToDelete.id);
      setShowDeleteCaseModal(false);
      setCaseToDelete(null);
      setSuccessMessage("Test case deleted successfully.");
      await fetchDatasetDetail(selectedDatasetId);
      await fetchDatasets(selectedDatasetId);
    } catch (err: unknown) {
      setGlobalError(getErrorMessage(err) || "Failed to delete test case.");
    } finally {
      setSubmittingCase(false);
    }
  };

  // ==========================================
  // Import Test Cases JSON
  // ==========================================
  const handleImportJson = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isAdmin || !selectedDatasetId) return;

    setImportError(null);
    let parsed: ImportedCase[];
    try {
      parsed = JSON.parse(importJsonText);
      if (!Array.isArray(parsed)) {
        throw new Error("JSON must be an array of test cases: `[{ case_identifier, query, ... }]`");
      }
      if (parsed.length === 0) {
        throw new Error("JSON array cannot be empty.");
      }
    } catch (err: unknown) {
      setImportError(`Invalid JSON: ${getErrorMessage(err)}`);
      return;
    }

    setImporting(true);
    setImportProgress({ current: 0, total: parsed.length });

    let addedCount = 0;
    try {
      for (let i = 0; i < parsed.length; i++) {
        const item = parsed[i];
        const tcPayload: TestCaseCreate = {
          case_identifier: item.case_identifier || `case_${String(i + 1).padStart(3, "0")}`,
          query: item.query || item.question || "",
          query_type: item.query_type || "factoid",
          expected_behavior: item.expected_behavior || "answer",
          ground_truth_answer: item.ground_truth_answer || item.answer || null,
          key_facts: Array.isArray(item.key_facts) ? item.key_facts : [],
          ground_truth_evidence: Array.isArray(item.ground_truth_evidence)
            ? item.ground_truth_evidence
            : [],
        };

        if (!tcPayload.query) {
          throw new Error(`Item index ${i} is missing required 'query' field.`);
        }

        await api.addTestCase(selectedDatasetId, tcPayload);
        addedCount++;
        setImportProgress({ current: addedCount, total: parsed.length });
      }

      setShowImportModal(false);
      setImportJsonText("");
      setSuccessMessage(`Successfully imported ${addedCount} test cases into dataset.`);
      await fetchDatasetDetail(selectedDatasetId);
      await fetchDatasets(selectedDatasetId);
    } catch (err: unknown) {
      setImportError(`Import stopped after ${addedCount} cases: ${getErrorMessage(err)}`);
    } finally {
      setImporting(false);
      setImportProgress(null);
    }
  };

  const openImport = () => {
    setImportError(null);
    setShowImportModal(true);
  };

  const closeDatasetForm = () => {
    setShowCreateDatasetModal(false);
    setShowEditDatasetModal(false);
  };

  const closeCaseForm = () => {
    dispatchCaseForm({ type: "close" });
  };

  const closeDeleteCase = () => {
    setShowDeleteCaseModal(false);
    setCaseToDelete(null);
  };

  return (
    <AppShell>
      <PageHeader
        eyebrow={
          <Link
            href="/evaluations"
            className="inline-flex items-center gap-1.5 text-fg-subtle transition-colors hover:text-fg"
          >
            <ArrowLeft className="size-3.5" />
            Back to Evaluations
          </Link>
        }
        title="Datasets & test cases"
        description="Create and manage custom benchmark datasets for tenant-specific RAG evaluation."
        actions={
          <>
            {!isAdmin && (
              <Badge tone="warning" size="md">
                <ShieldAlert />
                Admin role required to manage datasets
              </Badge>
            )}
            <Button
              variant="secondary"
              size="icon-sm"
              onClick={() => {
                fetchDatasets();
                if (selectedDatasetId) fetchDatasetDetail(selectedDatasetId);
              }}
              title="Refresh datasets"
              aria-label="Refresh datasets"
            >
              <RefreshCw className={cn((loadingDatasets || loadingDetail) && "animate-spin")} />
            </Button>
            {isAdmin && (
              <button
                type="button"
                onClick={handleOpenCreateDataset}
                className="btn-accent-ref flex h-8 items-center gap-1.5 rounded-xl px-3.5 text-xs font-medium cursor-pointer shadow-md"
              >
                <Plus className="size-3.5" />
                <span>Create Dataset</span>
              </button>
            )}
          </>
        }
      />

      <div className="space-y-4">
        {globalError && (
          <Alert tone="danger" onDismiss={() => setGlobalError(null)}>
            {globalError}
          </Alert>
        )}

        {successMessage && (
          <Alert tone="success" onDismiss={() => setSuccessMessage(null)}>
            {successMessage}
          </Alert>
        )}

        <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-12">
          {/* Dataset list */}
          <div className="space-y-4 lg:sticky lg:top-6 lg:col-span-4">
            <div className="panel-ref overflow-hidden">
              <div className="flex items-center justify-between border-b border-white/[0.06] bg-white/[0.02] px-4 py-3.5">
                <div className="flex items-center gap-2">
                  <Database className="size-4 text-[#ff7a45]" />
                  <h2 className="text-sm font-semibold tracking-tight text-white">Custom Datasets</h2>
                  <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 font-mono text-[10px] text-[#8e95a5]">
                    {datasets.length}
                  </span>
                </div>
                {isAdmin && (
                  <button
                    type="button"
                    onClick={handleOpenCreateDataset}
                    className="flex size-6 items-center justify-center rounded-lg border border-white/10 bg-white/5 text-[#8e95a5] hover:text-white hover:bg-white/10 cursor-pointer"
                    title="Add Dataset"
                    aria-label="Add dataset"
                  >
                    <Plus className="size-3.5" />
                  </button>
                )}
              </div>

              {loadingDatasets ? (
                <LoadingState label="Loading datasets…" />
              ) : datasets.length === 0 ? (
                <EmptyState
                  icon={<Database />}
                  title="No custom datasets yet"
                  description="Create a dataset to evaluate your tenant-specific documents and queries."
                  action={
                    isAdmin && (
                      <button
                        type="button"
                        onClick={handleOpenCreateDataset}
                        className="btn-accent-ref flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-medium cursor-pointer mt-2"
                      >
                        <Plus className="size-3.5" />
                        Create Dataset
                      </button>
                    )
                  }
                  className="py-10"
                />
              ) : (
                <ul className="max-h-[calc(100vh-320px)] space-y-1 overflow-y-auto p-2">
                  {datasets.map((ds) => {
                    const isSelected = ds.id === selectedDatasetId;
                    return (
                      <li key={ds.id}>
                        <button
                          type="button"
                          onClick={() => setSelectedDatasetId(ds.id)}
                          aria-current={isSelected ? "true" : undefined}
                          className={cn(
                            "relative w-full rounded-xl px-3 py-2.5 text-left transition-all cursor-pointer",
                            isSelected
                              ? "nav-pill-active"
                              : "text-[#8e95a5] hover:bg-white/[0.04] hover:text-white border border-transparent"
                          )}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center gap-2">
                                <span
                                  className={cn(
                                    "truncate text-xs font-semibold",
                                    isSelected ? "text-white" : "text-[#d1d5db]"
                                  )}
                                >
                                  {ds.name}
                                </span>
                                <span className="shrink-0 font-mono text-[10px] text-[#636a7e]">
                                  v{ds.version}
                                </span>
                              </div>
                              {ds.description && (
                                <p className="mt-0.5 line-clamp-2 text-xs leading-relaxed text-fg-subtle">
                                  {ds.description}
                                </p>
                              )}
                              <p className="mt-1.5 text-[11px] text-fg-faint">
                                Updated {formatDate(ds.updated_at)}
                              </p>
                            </div>
                            <span className="tabular shrink-0 rounded-[5px] border border-line-strong bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] text-fg-muted">
                              {ds.test_case_count} cases
                            </span>
                          </div>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            <div className="panel-ref p-4">
              <div className="mb-1.5 flex items-center gap-2 text-xs font-semibold text-white">
                <BookOpen className="size-3.5 text-[#ff7a45]" />
                Golden Benchmark
              </div>
              <p className="text-xs leading-relaxed text-[#8e95a5]">
                The built-in <code className="font-mono text-white">golden_dataset.json</code> (50
                cases) is always available as a baseline reference. Custom datasets add proprietary
                cases and ground-truth anchors.
              </p>
            </div>
          </div>

          {/* Selected dataset workspace */}
          <div className="min-w-0 lg:col-span-8">
            {!selectedDatasetDetail ? (
              <Panel>
                {loadingDetail ? (
                  <LoadingState label="Loading dataset…" className="py-24" />
                ) : (
                  <EmptyState
                    icon={<Database />}
                    title="No dataset selected"
                    description="Select a dataset from the list to inspect its test cases, or create a new dataset."
                    className="py-24"
                  />
                )}
              </Panel>
            ) : (
              <Panel>
                {/* Dataset header */}
                <div className="border-b border-line px-4 py-4 sm:px-5">
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0 space-y-1.5">
                      <div className="flex flex-wrap items-center gap-2">
                        <h2 className="text-lg font-semibold tracking-tight text-fg">
                          {selectedDatasetDetail.name}
                        </h2>
                        <Badge tone="accent" mono>
                          v{selectedDatasetDetail.version}
                        </Badge>
                        <Badge tone="neutral">
                          {selectedDatasetDetail.test_cases?.length || 0} Test Cases
                        </Badge>
                      </div>
                      {selectedDatasetDetail.description && (
                        <p className="text-[13px] leading-relaxed text-fg-subtle">
                          {selectedDatasetDetail.description}
                        </p>
                      )}
                    </div>

                    <div className="flex shrink-0 flex-wrap items-center gap-2">
                      <ButtonLink
                        href={`/evaluations`}
                        variant="secondary"
                        title="Run an evaluation benchmark with this dataset"
                      >
                        <Play className="fill-current" />
                        Run Evaluation
                      </ButtonLink>
                      {isAdmin && (
                        <>
                          <Button
                            variant="secondary"
                            size="icon-sm"
                            onClick={handleOpenEditDataset}
                            title="Edit Dataset Details"
                            aria-label="Edit dataset details"
                          >
                            <Pencil />
                          </Button>
                          <Button
                            variant="danger"
                            size="icon-sm"
                            onClick={() => setShowDeleteDatasetModal(true)}
                            title="Delete Dataset"
                            aria-label="Delete dataset"
                          >
                            <Trash2 />
                          </Button>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Toolbar */}
                  <div className="mt-4 flex flex-col gap-2 xl:flex-row xl:items-center">
                    <div className="flex flex-1 flex-col gap-2 sm:flex-row">
                      <IconInput
                        icon={Search}
                        type="text"
                        aria-label="Search test cases"
                        placeholder="Search by query, ID or answer..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="h-8 text-[13px]"
                        wrapperClassName="flex-1 min-w-0"
                      />
                      <Select
                        aria-label="Filter by query type"
                        value={queryTypeFilter}
                        onChange={(e) => setQueryTypeFilter(e.target.value)}
                        className="h-8 text-[13px]"
                      >
                        <option value="all">All Query Types</option>
                        {QUERY_TYPE_OPTIONS.map((o) => (
                          <option key={o.value} value={o.value}>
                            {o.label}
                          </option>
                        ))}
                      </Select>
                      <Select
                        aria-label="Filter by expected behavior"
                        value={behaviorFilter}
                        onChange={(e) => setBehaviorFilter(e.target.value)}
                        className="h-8 text-[13px]"
                      >
                        <option value="all">All Behaviors</option>
                        <option value="answer">Answer</option>
                        <option value="refusal">Refusal</option>
                      </Select>
                    </div>

                    {isAdmin && (
                      <div className="flex shrink-0 items-center gap-2">
                        <Button variant="secondary" onClick={openImport} title="Import cases from JSON">
                          <Upload />
                          Import JSON
                        </Button>
                        <Button variant="primary" onClick={handleOpenAddCase}>
                          <Plus />
                          Add Case
                        </Button>
                      </div>
                    )}
                  </div>
                </div>

                {/* Test cases */}
                {loadingDetail ? (
                  <LoadingState label="Loading test cases…" />
                ) : filteredCases.length === 0 ? (
                  <EmptyState
                    icon={<FileText />}
                    title={
                      selectedDatasetDetail.test_cases?.length === 0
                        ? "This dataset has no test cases yet."
                        : "No test cases match your search filters."
                    }
                    description="Add test cases with expected answers and semantic anchors to evaluate retrieval quality."
                    action={
                      isAdmin &&
                      selectedDatasetDetail.test_cases?.length === 0 && (
                        <>
                          <Button variant="primary" onClick={handleOpenAddCase}>
                            <Plus />
                            Add First Case
                          </Button>
                          <Button variant="secondary" onClick={openImport}>
                            <Upload />
                            Import JSON
                          </Button>
                        </>
                      )
                    }
                  />
                ) : (
                  <ul className="divide-y divide-line">
                    {filteredCases.map((tc) => {
                      const isExpanded = expandedCaseId === tc.id;
                      const detailId = `case-detail-${tc.id}`;
                      return (
                        <li key={tc.id} className={cn(isExpanded && "bg-surface-2/40")}>
                          <div className="flex items-start gap-3 px-4 py-3 sm:px-5">
                            <button
                              type="button"
                              onClick={() => setExpandedCaseId(isExpanded ? null : tc.id)}
                              aria-expanded={isExpanded}
                              aria-controls={detailId}
                              className="group min-w-0 flex-1 space-y-1.5 text-left cursor-pointer"
                            >
                              <div className="flex flex-wrap items-center gap-1.5">
                                <span className="font-mono text-xs font-medium text-accent-strong">
                                  {tc.case_identifier}
                                </span>
                                <Badge tone="deterministic" mono>
                                  {tc.query_type}
                                </Badge>
                                <Badge tone={tc.expected_behavior === "refusal" ? "danger" : "success"}>
                                  {tc.expected_behavior}
                                </Badge>
                                {tc.key_facts && tc.key_facts.length > 0 && (
                                  <span className="text-[11px] text-fg-subtle">
                                    · {tc.key_facts.length} facts
                                  </span>
                                )}
                                {tc.ground_truth_evidence && tc.ground_truth_evidence.length > 0 && (
                                  <span className="text-[11px] text-fg-subtle">
                                    · {tc.ground_truth_evidence.length} evidence anchors
                                  </span>
                                )}
                              </div>
                              <p className="text-[13px] leading-relaxed text-fg group-hover:text-white">
                                {tc.query}
                              </p>
                            </button>

                            <div className="flex shrink-0 items-center gap-0.5">
                              {isAdmin && (
                                <>
                                  <Button
                                    variant="ghost"
                                    size="icon-xs"
                                    onClick={() => handleOpenEditCase(tc)}
                                    title="Edit Test Case"
                                    aria-label={`Edit test case ${tc.case_identifier}`}
                                  >
                                    <Pencil />
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="icon-xs"
                                    onClick={() => {
                                      setCaseToDelete(tc);
                                      setShowDeleteCaseModal(true);
                                    }}
                                    className="hover:bg-danger/10 hover:text-danger"
                                    title="Delete Test Case"
                                    aria-label={`Delete test case ${tc.case_identifier}`}
                                  >
                                    <Trash2 />
                                  </Button>
                                </>
                              )}
                              <Button
                                variant="ghost"
                                size="icon-xs"
                                onClick={() => setExpandedCaseId(isExpanded ? null : tc.id)}
                                title={isExpanded ? "Collapse" : "Expand"}
                                aria-label={isExpanded ? "Collapse details" : "Expand details"}
                                aria-expanded={isExpanded}
                                aria-controls={detailId}
                              >
                                <ChevronDown
                                  className={cn("transition-transform duration-200", isExpanded && "rotate-180")}
                                />
                              </Button>
                            </div>
                          </div>

                          {isExpanded && (
                            <div
                              id={detailId}
                              className="space-y-4 px-4 pb-4 animate-fade-in sm:px-5"
                            >
                              {tc.ground_truth_answer && (
                                <div className="space-y-1.5">
                                  <Eyebrow>Ground truth answer</Eyebrow>
                                  <div className="whitespace-pre-wrap rounded-md border border-line bg-canvas/60 px-3.5 py-2.5 text-[13px] leading-relaxed text-fg/90">
                                    {tc.ground_truth_answer}
                                  </div>
                                </div>
                              )}

                              {tc.key_facts && tc.key_facts.length > 0 && (
                                <div className="space-y-1.5">
                                  <Eyebrow>Key facts to verify</Eyebrow>
                                  <ul className="space-y-1">
                                    {tc.key_facts.map((fact, idx) => (
                                      <li key={idx} className="flex gap-2.5 text-[13px] text-fg-muted">
                                        <span className="mt-[0.6em] size-1 shrink-0 rounded-full bg-fg-subtle" aria-hidden />
                                        {fact}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              )}

                              {tc.ground_truth_evidence && tc.ground_truth_evidence.length > 0 && (
                                <div className="space-y-1.5">
                                  <Eyebrow>Evidence anchors</Eyebrow>
                                  <div className="space-y-2">
                                    {tc.ground_truth_evidence.map((ev, idx) => (
                                      <div
                                        key={idx}
                                        className="rounded-md border border-line bg-canvas/60 px-3.5 py-2.5"
                                      >
                                        <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                                          <span className="font-medium text-fg">{ev.document_title}</span>
                                          <span className="flex items-center gap-3 text-fg-subtle">
                                            {ev.page_number && <span className="font-mono">p. {ev.page_number}</span>}
                                            {ev.section_heading && <span>Section: {ev.section_heading}</span>}
                                          </span>
                                        </div>
                                        {ev.content_anchors && ev.content_anchors.length > 0 && (
                                          <div className="mt-2 space-y-1">
                                            {ev.content_anchors.map((anchor, aIdx) => (
                                              <div
                                                key={aIdx}
                                                className="border-l-2 border-judge-det/50 bg-judge-det/[0.05] px-2.5 py-1 font-mono text-[11px] text-judge-det"
                                              >
                                                &ldquo;{anchor}&rdquo;
                                              </div>
                                            ))}
                                          </div>
                                        )}
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                )}
              </Panel>
            )}
          </div>
        </div>
      </div>

      {/* Create / edit dataset */}
      {(showCreateDatasetModal || showEditDatasetModal) && (
        <Dialog
          onClose={closeDatasetForm}
          icon={<Database />}
          title={showCreateDatasetModal ? "Create Evaluation Dataset" : "Edit Dataset Details"}
          footer={
            <>
              <Button variant="ghost" onClick={closeDatasetForm} disabled={submittingDataset}>
                Cancel
              </Button>
              <Button
                type="submit"
                form="dataset-form"
                variant="primary"
                disabled={submittingDataset}
                loading={submittingDataset}
              >
                {submittingDataset
                  ? "Saving..."
                  : showCreateDatasetModal
                  ? "Create Dataset"
                  : "Save Changes"}
              </Button>
            </>
          }
        >
          <form
            id="dataset-form"
            onSubmit={showCreateDatasetModal ? handleCreateDataset : handleUpdateDataset}
            className="space-y-4"
          >
            {formError && <Alert tone="danger">{formError}</Alert>}

            <Field label="Dataset name" htmlFor="ds-name" required>
              <Input
                id="ds-name"
                type="text"
                placeholder="e.g. legal-contracts-eval"
                value={datasetFormName}
                onChange={(e) => setDatasetFormName(e.target.value)}
                required
              />
            </Field>

            <Field label="Version" htmlFor="ds-version">
              <Input
                id="ds-version"
                type="text"
                placeholder="1.0.0"
                value={datasetFormVersion}
                onChange={(e) => setDatasetFormVersion(e.target.value)}
                className="font-mono"
              />
            </Field>

            <Field label="Description" htmlFor="ds-desc">
              <Textarea
                id="ds-desc"
                rows={3}
                placeholder="Describe the domain, cases, or intended scope..."
                value={datasetFormDesc}
                onChange={(e) => setDatasetFormDesc(e.target.value)}
              />
            </Field>
          </form>
        </Dialog>
      )}

      {/* Delete dataset */}
      {showDeleteDatasetModal && selectedDatasetDetail && (
        <Dialog
          onClose={() => setShowDeleteDatasetModal(false)}
          icon={<Trash2 className="text-danger" />}
          title="Delete Dataset"
          footer={
            <>
              <Button
                variant="ghost"
                onClick={() => setShowDeleteDatasetModal(false)}
                disabled={submittingDataset}
              >
                Cancel
              </Button>
              <Button
                variant="danger-solid"
                onClick={handleDeleteDataset}
                disabled={submittingDataset}
                loading={submittingDataset}
              >
                {submittingDataset ? "Deleting..." : "Delete Dataset"}
              </Button>
            </>
          }
          bodyClassName="space-y-4"
        >
          <p className="text-sm leading-relaxed text-fg-muted">
            Are you sure you want to delete dataset{" "}
            <strong className="font-semibold text-fg">{selectedDatasetDetail.name}</strong>? This will
            remove all {selectedDatasetDetail.test_cases?.length || 0} associated test cases.
          </p>
          <Alert tone="info" icon={<Info />}>
            Past evaluation runs referencing this dataset will be safely preserved.
          </Alert>
        </Dialog>
      )}

      {/* Add / edit test case */}
      {(showAddCaseModal || showEditCaseModal) && (
        <Dialog
          onClose={closeCaseForm}
          size="lg"
          icon={<FileText />}
          title={
            showAddCaseModal ? (
              "Add Test Case"
            ) : (
              <>
                Edit Case: <span className="font-mono">{editingCase?.case_identifier}</span>
              </>
            )
          }
          footer={
            <>
              <Button variant="ghost" onClick={closeCaseForm} disabled={submittingCase}>
                Cancel
              </Button>
              <Button
                type="submit"
                form="test-case-form"
                variant="primary"
                disabled={submittingCase}
                loading={submittingCase}
              >
                {submittingCase ? "Saving..." : "Save Test Case"}
              </Button>
            </>
          }
        >
          <form id="test-case-form" onSubmit={handleSaveCase} className="space-y-4">
            {caseFormError && <Alert tone="danger">{caseFormError}</Alert>}

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <Field label="Identifier" htmlFor="tc-id" required>
                <Input
                  id="tc-id"
                  type="text"
                  placeholder="case_001"
                  value={caseIdInput}
                  onChange={(e) => setCaseIdInput(e.target.value)}
                  className="font-mono text-[13px]"
                  required
                />
              </Field>
              <Field label="Query type" htmlFor="tc-type">
                <Select
                  id="tc-type"
                  value={caseQueryTypeInput}
                  onChange={(e) => setCaseQueryTypeInput(e.target.value)}
                >
                  {QUERY_TYPE_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Expected behavior" htmlFor="tc-behavior">
                <Select
                  id="tc-behavior"
                  value={caseBehaviorInput}
                  onChange={(e) => setCaseBehaviorInput(e.target.value)}
                >
                  <option value="answer">Answer (Accurate)</option>
                  <option value="refusal">Refusal (Adversarial/OOD)</option>
                </Select>
              </Field>
            </div>

            <Field label="Query / question" htmlFor="tc-query" required>
              <Textarea
                id="tc-query"
                rows={2}
                placeholder="Enter the benchmark query to evaluate..."
                value={caseQueryInput}
                onChange={(e) => setCaseQueryInput(e.target.value)}
                required
              />
            </Field>

            <Field label="Ground truth answer" htmlFor="tc-answer">
              <Textarea
                id="tc-answer"
                rows={2}
                placeholder="Expected answer for correctness & faithfulness scoring..."
                value={caseGroundTruthInput}
                onChange={(e) => setCaseGroundTruthInput(e.target.value)}
              />
            </Field>

            <Field label="Key facts to check" htmlFor="tc-facts" hint="One fact per line.">
              <Textarea
                id="tc-facts"
                rows={2}
                placeholder={"Fact 1\nFact 2"}
                value={caseKeyFactsInput}
                onChange={(e) => setCaseKeyFactsInput(e.target.value)}
                className="font-mono text-xs"
              />
            </Field>

            <fieldset className="space-y-3 rounded-lg border border-line bg-surface-2/60 p-3.5">
              <legend className="px-1 text-[13px] font-medium text-fg-muted">
                Ground truth evidence anchor <span className="font-normal text-fg-subtle">(optional)</span>
              </legend>
              <div className="grid grid-cols-3 gap-2">
                <Input
                  type="text"
                  aria-label="Evidence document title"
                  placeholder="Document title (e.g. policy.pdf)"
                  value={evidenceDocTitle}
                  onChange={(e) => setEvidenceDocTitle(e.target.value)}
                  className="col-span-2 h-8 text-[13px]"
                />
                <Input
                  type="text"
                  aria-label="Evidence page number"
                  placeholder="Page (e.g. 1)"
                  value={evidencePageNum}
                  onChange={(e) => setEvidencePageNum(e.target.value)}
                  className="h-8 font-mono text-[13px]"
                />
              </div>
              <Textarea
                rows={2}
                aria-label="Evidence content anchors"
                placeholder="Content anchors / exact quotes to match (one per line)..."
                value={evidenceAnchorsInput}
                onChange={(e) => setEvidenceAnchorsInput(e.target.value)}
                className="font-mono text-xs"
              />
            </fieldset>
          </form>
        </Dialog>
      )}

      {/* Delete test case */}
      {showDeleteCaseModal && caseToDelete && (
        <Dialog
          onClose={closeDeleteCase}
          size="sm"
          icon={<Trash2 className="text-danger" />}
          title="Delete Test Case"
          footer={
            <>
              <Button variant="ghost" onClick={closeDeleteCase} disabled={submittingCase}>
                Cancel
              </Button>
              <Button
                variant="danger-solid"
                onClick={handleDeleteCase}
                disabled={submittingCase}
                loading={submittingCase}
              >
                {submittingCase ? "Deleting..." : "Delete Case"}
              </Button>
            </>
          }
        >
          <p className="text-sm leading-relaxed text-fg-muted">
            Are you sure you want to delete test case{" "}
            <strong className="font-mono font-medium text-fg">{caseToDelete.case_identifier}</strong>?
          </p>
        </Dialog>
      )}

      {/* Import JSON */}
      {showImportModal && (
        <Dialog
          onClose={() => setShowImportModal(false)}
          size="lg"
          icon={<FileJson />}
          title="Import Test Cases from JSON"
          description="Paste an array of test cases. The schema matches the benchmark format."
          footer={
            <>
              <Button variant="ghost" onClick={() => setShowImportModal(false)} disabled={importing}>
                Cancel
              </Button>
              <Button
                type="submit"
                form="import-json-form"
                variant="primary"
                disabled={importing}
                loading={importing}
              >
                {importing ? "Importing..." : "Import Cases"}
              </Button>
            </>
          }
        >
          <form id="import-json-form" onSubmit={handleImportJson} className="space-y-4">
            {importError && <Alert tone="danger">{importError}</Alert>}

            <div className="space-y-1.5">
              <Eyebrow>Example</Eyebrow>
              <pre className="overflow-x-auto rounded-md border border-line bg-canvas px-3.5 py-3 font-mono text-[11px] leading-relaxed text-fg-subtle">
                {`[
  {
    "case_identifier": "case_001",
    "query": "What is our refund window?",
    "query_type": "factoid",
    "expected_behavior": "answer",
    "ground_truth_answer": "30 days from purchase.",
    "key_facts": ["30 days"]
  }
]`}
              </pre>
            </div>

            <Field label="JSON array" htmlFor="import-json">
              <Textarea
                id="import-json"
                rows={8}
                placeholder="Paste JSON array here..."
                value={importJsonText}
                onChange={(e) => setImportJsonText(e.target.value)}
                className="font-mono text-xs"
                spellCheck={false}
                required
              />
            </Field>

            {importProgress && (
              <Alert tone="info" icon={<Spinner />}>
                Importing case {importProgress.current} of {importProgress.total}...
              </Alert>
            )}
          </form>
        </Dialog>
      )}
    </AppShell>
  );
}
