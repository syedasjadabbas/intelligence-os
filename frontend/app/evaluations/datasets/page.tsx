"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  api,
  DatasetListItem,
  DatasetDetail,
  TestCaseDetail,
  TestCaseCreate,
  TestCaseUpdate,
  DatasetCreate,
  DatasetUpdate,
  EvidenceAnchor,
} from "@/lib/api";
import { formatDate } from "@/lib/utils";
import {
  ArrowLeft,
  RefreshCw,
  Plus,
  Trash2,
  Edit2,
  FileText,
  Search,
  Filter,
  Layers,
  Database,
  Sparkles,
  Shield,
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  ChevronDown,
  X,
  Play,
  Upload,
  Info,
  HelpCircle,
  Hash,
  BookOpen,
} from "lucide-react";

export default function DatasetsManagementPage() {
  const router = useRouter();
  const { user, org } = useAuth();
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

  const [showAddCaseModal, setShowAddCaseModal] = useState(false);
  const [showEditCaseModal, setShowEditCaseModal] = useState(false);
  const [showDeleteCaseModal, setShowDeleteCaseModal] = useState(false);
  const [editingCase, setEditingCase] = useState<TestCaseDetail | null>(null);
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
    } catch (err: any) {
      setGlobalError(err.message || "Failed to load datasets.");
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
    } catch (err: any) {
      setGlobalError(err.message || "Failed to load dataset details.");
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
    } catch (err: any) {
      setFormError(err.message || "Failed to create dataset.");
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
    } catch (err: any) {
      setFormError(err.message || "Failed to update dataset.");
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
    } catch (err: any) {
      setGlobalError(err.message || "Failed to delete dataset.");
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
    setShowAddCaseModal(true);
  };

  const handleOpenEditCase = (tc: TestCaseDetail) => {
    setEditingCase(tc);
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
    setShowEditCaseModal(true);
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
    if (!isAdmin || !selectedDatasetId) return;

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
      if (editingCase) {
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
        await api.updateTestCase(selectedDatasetId, editingCase.id, payload);
        setShowEditCaseModal(false);
        setEditingCase(null);
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
        setShowAddCaseModal(false);
        setSuccessMessage(`Test case "${caseIdInput.trim()}" added.`);
      }

      await fetchDatasetDetail(selectedDatasetId);
      await fetchDatasets(selectedDatasetId);
    } catch (err: any) {
      setCaseFormError(err.message || "Failed to save test case.");
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
    } catch (err: any) {
      setGlobalError(err.message || "Failed to delete test case.");
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
    let parsed: any[];
    try {
      parsed = JSON.parse(importJsonText);
      if (!Array.isArray(parsed)) {
        throw new Error("JSON must be an array of test cases: `[{ case_identifier, query, ... }]`");
      }
      if (parsed.length === 0) {
        throw new Error("JSON array cannot be empty.");
      }
    } catch (err: any) {
      setImportError(`Invalid JSON: ${err.message}`);
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
    } catch (err: any) {
      setImportError(`Import stopped after ${addedCount} cases: ${err.message}`);
    } finally {
      setImporting(false);
      setImportProgress(null);
    }
  };

  return (
    <div className="min-h-screen bg-[#090d16] text-slate-100 flex flex-col font-sans">
      {/* Top Navigation Header */}
      <header className="border-b border-slate-800/80 bg-[#0d131f] px-6 py-3.5 flex items-center justify-between sticky top-0 z-30 backdrop-blur-md">
        <div className="flex items-center gap-4">
          <Link
            href="/evaluations"
            className="p-1.5 px-2.5 rounded-lg bg-slate-800/80 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-700/60 transition-colors flex items-center gap-1.5 text-xs font-medium cursor-pointer"
          >
            <ArrowLeft className="w-4 h-4 text-slate-400" />
            <span>Back to Evaluations</span>
          </Link>
          <div className="h-5 w-px bg-slate-800" />
          <div>
            <h1 className="text-base font-semibold text-white flex items-center gap-2">
              <Layers className="w-4 h-4 text-indigo-400" />
              Evaluation Datasets & Test Cases
            </h1>
            <p className="text-[11px] text-slate-400">
              Create, view, and manage custom benchmark datasets for tenant RAG evaluation
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

          {isAdmin ? (
            <button
              onClick={handleOpenCreateDataset}
              className="py-1.5 px-3.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-1.5 transition-all shadow-sm cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Create Dataset</span>
            </button>
          ) : (
            <div className="px-2.5 py-1 rounded-lg bg-slate-800/60 border border-slate-700/50 text-[11px] text-slate-400 flex items-center gap-1.5">
              <Shield className="w-3 h-3 text-amber-400" />
              <span>Admin role required to manage datasets</span>
            </div>
          )}

          <button
            onClick={() => {
              fetchDatasets();
              if (selectedDatasetId) fetchDatasetDetail(selectedDatasetId);
            }}
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors cursor-pointer border border-slate-700/60"
            title="Refresh datasets"
          >
            <RefreshCw
              className={`w-4 h-4 ${loadingDatasets || loadingDetail ? "animate-spin" : ""}`}
            />
          </button>
        </div>
      </header>

      {/* Main Workspace Layout */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 space-y-4">
        {/* Global Notifications */}
        {globalError && (
          <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2.5 animate-in fade-in">
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
            <span className="flex-1">{globalError}</span>
            <button onClick={() => setGlobalError(null)} className="text-rose-400 hover:text-rose-200">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {successMessage && (
          <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs flex items-center gap-2.5 animate-in fade-in">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span className="flex-1">{successMessage}</span>
            <button onClick={() => setSuccessMessage(null)} className="text-emerald-400 hover:text-emerald-200">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Master-Detail Split Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left Column: Datasets List (4 cols) */}
          <div className="lg:col-span-4 space-y-3">
            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Database className="w-4 h-4 text-indigo-400" />
                  <h2 className="text-xs font-semibold text-white uppercase tracking-wider">
                    Custom Datasets ({datasets.length})
                  </h2>
                </div>
                {isAdmin && (
                  <button
                    onClick={handleOpenCreateDataset}
                    className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800"
                    title="Add Dataset"
                  >
                    <Plus className="w-4 h-4" />
                  </button>
                )}
              </div>

              {loadingDatasets ? (
                <div className="py-8 text-center text-slate-400 text-xs">
                  <RefreshCw className="w-4 h-4 animate-spin mx-auto mb-2 text-indigo-400" />
                  Loading datasets...
                </div>
              ) : datasets.length === 0 ? (
                <div className="py-8 text-center space-y-3 border border-dashed border-slate-800 rounded-xl p-4">
                  <Layers className="w-8 h-8 text-slate-600 mx-auto" />
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-slate-300">No Custom Datasets Yet</p>
                    <p className="text-[11px] text-slate-500">
                      Create a dataset to evaluate your tenant-specific documents and queries.
                    </p>
                  </div>
                  {isAdmin && (
                    <button
                      onClick={handleOpenCreateDataset}
                      className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition-colors cursor-pointer inline-flex items-center gap-1.5"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      <span>Create Dataset</span>
                    </button>
                  )}
                </div>
              ) : (
                <div className="space-y-2 max-h-[calc(100vh-250px)] overflow-y-auto pr-1">
                  {datasets.map((ds) => {
                    const isSelected = ds.id === selectedDatasetId;
                    return (
                      <div
                        key={ds.id}
                        onClick={() => setSelectedDatasetId(ds.id)}
                        className={`p-3.5 rounded-xl border transition-all cursor-pointer relative group ${
                          isSelected
                            ? "bg-indigo-950/40 border-indigo-500/60 shadow-sm"
                            : "bg-slate-900/40 border-slate-800/80 hover:border-slate-700 hover:bg-slate-900"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="space-y-1 min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              <span
                                className={`text-xs font-semibold truncate ${
                                  isSelected ? "text-indigo-200" : "text-white"
                                }`}
                              >
                                {ds.name}
                              </span>
                              <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-slate-800 text-slate-400 border border-slate-700">
                                v{ds.version}
                              </span>
                            </div>
                            {ds.description && (
                              <p className="text-[11px] text-slate-400 line-clamp-2">
                                {ds.description}
                              </p>
                            )}
                          </div>
                          <span className="text-[11px] font-mono font-medium px-2 py-0.5 rounded-full bg-slate-800/90 text-slate-300 border border-slate-700 shrink-0">
                            {ds.test_case_count} cases
                          </span>
                        </div>

                        <div className="mt-2.5 pt-2 border-t border-slate-800/60 flex items-center justify-between text-[10px] text-slate-500">
                          <span>Updated {formatDate(ds.updated_at)}</span>
                          {isSelected && (
                            <span className="text-indigo-400 font-medium flex items-center gap-1">
                              Active <ChevronRight className="w-3 h-3" />
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Benchmark Info Card */}
            <div className="p-3.5 rounded-xl bg-slate-900/30 border border-slate-800/80 text-xs space-y-2">
              <div className="flex items-center gap-2 text-indigo-400 font-semibold text-[11px] uppercase tracking-wider">
                <BookOpen className="w-3.5 h-3.5" />
                <span>Golden Benchmark</span>
              </div>
              <p className="text-[11px] text-slate-400 leading-relaxed">
                The built-in <code className="text-slate-300 font-mono">golden_dataset.json</code> (50 cases) is always available across the platform as a baseline reference. Custom datasets let you add proprietary cases and ground-truth anchors.
              </p>
            </div>
          </div>

          {/* Right Column: Selected Dataset Workspace (8 cols) */}
          <div className="lg:col-span-8 space-y-4">
            {!selectedDatasetDetail ? (
              <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-12 text-center text-slate-400 space-y-3">
                <Layers className="w-10 h-10 mx-auto text-slate-600" />
                <p className="text-sm font-medium text-slate-300">No Dataset Selected</p>
                <p className="text-xs text-slate-500 max-w-sm mx-auto">
                  Select a dataset from the left panel to inspect its test cases or create a new dataset.
                </p>
              </div>
            ) : (
              <>
                {/* Dataset Header / Action Card */}
                <div className="p-5 rounded-xl bg-slate-900/70 border border-slate-800 space-y-4">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2.5 flex-wrap">
                        <h2 className="text-lg font-bold text-white tracking-tight">
                          {selectedDatasetDetail.name}
                        </h2>
                        <span className="text-xs font-mono px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-medium">
                          v{selectedDatasetDetail.version}
                        </span>
                        <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                          {selectedDatasetDetail.test_cases?.length || 0} Test Cases
                        </span>
                      </div>
                      {selectedDatasetDetail.description && (
                        <p className="text-xs text-slate-300">
                          {selectedDatasetDetail.description}
                        </p>
                      )}
                    </div>

                    <div className="flex items-center gap-2 shrink-0 flex-wrap">
                      <Link
                        href={`/evaluations`}
                        className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-1.5 transition-all shadow-sm cursor-pointer"
                        title="Run an evaluation benchmark with this dataset"
                      >
                        <Play className="w-3.5 h-3.5 fill-current" />
                        <span>Run Evaluation</span>
                      </Link>

                      {isAdmin && (
                        <>
                          <button
                            onClick={handleOpenEditDataset}
                            className="p-1.5 px-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 transition-colors text-xs font-medium flex items-center gap-1.5 cursor-pointer"
                            title="Edit Dataset Details"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                            <span>Edit</span>
                          </button>
                          <button
                            onClick={() => setShowDeleteDatasetModal(true)}
                            className="p-1.5 px-2.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 hover:text-rose-200 border border-rose-500/30 transition-colors text-xs font-medium flex items-center gap-1.5 cursor-pointer"
                            title="Delete Dataset"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                            <span>Delete</span>
                          </button>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Test Cases Sub-Header & Action Bar */}
                  <div className="pt-3 border-t border-slate-800/80 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div className="flex items-center gap-2.5 flex-1 max-w-lg">
                      <div className="relative flex-1">
                        <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-500" />
                        <input
                          type="text"
                          placeholder="Search test cases by query or ID..."
                          value={searchQuery}
                          onChange={(e) => setSearchQuery(e.target.value)}
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                        />
                      </div>

                      <select
                        value={queryTypeFilter}
                        onChange={(e) => setQueryTypeFilter(e.target.value)}
                        className="bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500 cursor-pointer"
                      >
                        <option value="all">All Query Types</option>
                        <option value="factoid">Factoid</option>
                        <option value="multi_hop">Multi-Hop</option>
                        <option value="coreference">Coreference</option>
                        <option value="refusal">Refusal</option>
                        <option value="citation_needed">Citation Needed</option>
                        <option value="temporal">Temporal</option>
                        <option value="comparative">Comparative</option>
                        <option value="summarization">Summarization</option>
                      </select>

                      <select
                        value={behaviorFilter}
                        onChange={(e) => setBehaviorFilter(e.target.value)}
                        className="bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500 cursor-pointer"
                      >
                        <option value="all">All Behaviors</option>
                        <option value="answer">Answer</option>
                        <option value="refusal">Refusal</option>
                      </select>
                    </div>

                    {isAdmin && (
                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          onClick={() => {
                            setImportError(null);
                            setShowImportModal(true);
                          }}
                          className="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 hover:text-white border border-slate-700 transition-colors text-xs font-medium flex items-center gap-1.5 cursor-pointer"
                          title="Import cases from JSON"
                        >
                          <Upload className="w-3.5 h-3.5 text-indigo-400" />
                          <span>Import JSON</span>
                        </button>
                        <button
                          onClick={handleOpenAddCase}
                          className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer"
                        >
                          <Plus className="w-3.5 h-3.5" />
                          <span>Add Case</span>
                        </button>
                      </div>
                    )}
                  </div>
                </div>

                {/* Test Cases List */}
                <div className="space-y-3">
                  {loadingDetail ? (
                    <div className="py-12 text-center text-slate-400 text-xs">
                      <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-indigo-400" />
                      Loading test cases...
                    </div>
                  ) : filteredCases.length === 0 ? (
                    <div className="rounded-xl border border-dashed border-slate-800 p-10 text-center space-y-3">
                      <FileText className="w-8 h-8 text-slate-600 mx-auto" />
                      <div className="space-y-1">
                        <p className="text-xs font-medium text-slate-300">
                          {selectedDatasetDetail.test_cases?.length === 0
                            ? "This dataset has no test cases yet."
                            : "No test cases match your search filters."}
                        </p>
                        <p className="text-[11px] text-slate-500">
                          Add test cases with expected answers and semantic anchors to evaluate retrieval quality.
                        </p>
                      </div>
                      {isAdmin && selectedDatasetDetail.test_cases?.length === 0 && (
                        <div className="flex items-center justify-center gap-2">
                          <button
                            onClick={handleOpenAddCase}
                            className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition-colors cursor-pointer inline-flex items-center gap-1.5"
                          >
                            <Plus className="w-3.5 h-3.5" />
                            <span>Add First Case</span>
                          </button>
                          <button
                            onClick={() => {
                              setImportError(null);
                              setShowImportModal(true);
                            }}
                            className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition-colors cursor-pointer inline-flex items-center gap-1.5"
                          >
                            <Upload className="w-3.5 h-3.5 text-indigo-400" />
                            <span>Import JSON</span>
                          </button>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="space-y-2.5">
                      {filteredCases.map((tc) => {
                        const isExpanded = expandedCaseId === tc.id;
                        return (
                          <div
                            key={tc.id}
                            className="rounded-xl border border-slate-800/80 bg-slate-900/50 hover:border-slate-700/80 transition-all overflow-hidden"
                          >
                            {/* Card Header Row */}
                            <div className="p-3.5 flex items-start justify-between gap-3">
                              <div
                                onClick={() => setExpandedCaseId(isExpanded ? null : tc.id)}
                                className="flex-1 cursor-pointer space-y-1.5"
                              >
                                <div className="flex items-center gap-2 flex-wrap">
                                  <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-slate-950 text-indigo-300 border border-slate-800">
                                    {tc.case_identifier}
                                  </span>

                                  <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
                                    {tc.query_type}
                                  </span>

                                  <span
                                    className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded border ${
                                      tc.expected_behavior === "refusal"
                                        ? "bg-rose-500/15 text-rose-300 border-rose-500/30"
                                        : "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
                                    }`}
                                  >
                                    {tc.expected_behavior}
                                  </span>

                                  {tc.key_facts && tc.key_facts.length > 0 && (
                                    <span className="text-[10px] text-slate-400 bg-slate-800/60 px-2 py-0.5 rounded">
                                      {tc.key_facts.length} facts
                                    </span>
                                  )}

                                  {tc.ground_truth_evidence && tc.ground_truth_evidence.length > 0 && (
                                    <span className="text-[10px] text-slate-400 bg-slate-800/60 px-2 py-0.5 rounded">
                                      {tc.ground_truth_evidence.length} evidence anchors
                                    </span>
                                  )}
                                </div>

                                <p className="text-xs font-medium text-white pt-1">
                                  {tc.query}
                                </p>
                              </div>

                              <div className="flex items-center gap-1.5 shrink-0 pt-0.5">
                                {isAdmin && (
                                  <>
                                    <button
                                      onClick={() => handleOpenEditCase(tc)}
                                      className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800"
                                      title="Edit Test Case"
                                    >
                                      <Edit2 className="w-3.5 h-3.5" />
                                    </button>
                                    <button
                                      onClick={() => {
                                        setCaseToDelete(tc);
                                        setShowDeleteCaseModal(true);
                                      }}
                                      className="p-1 rounded text-rose-400 hover:text-rose-200 hover:bg-rose-500/10"
                                      title="Delete Test Case"
                                    >
                                      <Trash2 className="w-3.5 h-3.5" />
                                    </button>
                                  </>
                                )}
                                <button
                                  onClick={() => setExpandedCaseId(isExpanded ? null : tc.id)}
                                  className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800"
                                  title={isExpanded ? "Collapse" : "Expand"}
                                >
                                  {isExpanded ? (
                                    <ChevronDown className="w-4 h-4 text-slate-400" />
                                  ) : (
                                    <ChevronRight className="w-4 h-4 text-slate-400" />
                                  )}
                                </button>
                              </div>
                            </div>

                            {/* Expanded Details Drawer */}
                            {isExpanded && (
                              <div className="px-3.5 pb-4 pt-2 border-t border-slate-800/80 bg-slate-950/40 space-y-3 text-xs">
                                {tc.ground_truth_answer && (
                                  <div className="space-y-1">
                                    <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
                                      Ground Truth Answer
                                    </span>
                                    <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-200 font-mono text-[11px] leading-relaxed whitespace-pre-wrap">
                                      {tc.ground_truth_answer}
                                    </div>
                                  </div>
                                )}

                                {tc.key_facts && tc.key_facts.length > 0 && (
                                  <div className="space-y-1">
                                    <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
                                      Key Facts to Verify
                                    </span>
                                    <ul className="list-disc list-inside space-y-0.5 text-slate-300 text-[11px]">
                                      {tc.key_facts.map((fact, idx) => (
                                        <li key={idx}>{fact}</li>
                                      ))}
                                    </ul>
                                  </div>
                                )}

                                {tc.ground_truth_evidence && tc.ground_truth_evidence.length > 0 && (
                                  <div className="space-y-1.5">
                                    <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
                                      Evidence Anchors
                                    </span>
                                    <div className="space-y-1.5">
                                      {tc.ground_truth_evidence.map((ev, idx) => (
                                        <div
                                          key={idx}
                                          className="p-2.5 rounded-lg bg-slate-900/80 border border-slate-800 text-[11px] space-y-1"
                                        >
                                          <div className="flex items-center justify-between text-slate-400">
                                            <span className="font-semibold text-white">
                                              {ev.document_title}
                                            </span>
                                            <div className="flex items-center gap-2">
                                              {ev.page_number && (
                                                <span>Page {ev.page_number}</span>
                                              )}
                                              {ev.section_heading && (
                                                <span>Section: {ev.section_heading}</span>
                                              )}
                                            </div>
                                          </div>
                                          {ev.content_anchors && ev.content_anchors.length > 0 && (
                                            <div className="space-y-0.5 pt-1">
                                              {ev.content_anchors.map((anchor, aIdx) => (
                                                <div
                                                  key={aIdx}
                                                  className="font-mono text-[10px] text-cyan-300/90 bg-cyan-950/20 px-2 py-0.5 rounded border border-cyan-500/20"
                                                >
                                                  "{anchor}"
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
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      </main>

      {/* ========================================================================= */}
      {/* CREATE / EDIT DATASET MODAL                                               */}
      {/* ========================================================================= */}
      {(showCreateDatasetModal || showEditDatasetModal) && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-xs flex items-center justify-center z-50 p-4">
          <div className="bg-[#0e1422] border border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl relative space-y-4 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Database className="w-4 h-4 text-indigo-400" />
                <h3 className="text-sm font-semibold text-white">
                  {showCreateDatasetModal ? "Create Evaluation Dataset" : "Edit Dataset Details"}
                </h3>
              </div>
              <button
                onClick={() => {
                  setShowCreateDatasetModal(false);
                  setShowEditDatasetModal(false);
                }}
                className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {formError && (
              <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
                <span>{formError}</span>
              </div>
            )}

            <form
              onSubmit={showCreateDatasetModal ? handleCreateDataset : handleUpdateDataset}
              className="space-y-3.5"
            >
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Dataset Name <span className="text-rose-400">*</span>
                </label>
                <input
                  type="text"
                  placeholder="e.g. legal-contracts-eval"
                  value={datasetFormName}
                  onChange={(e) => setDatasetFormName(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500 placeholder-slate-500"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Version
                </label>
                <input
                  type="text"
                  placeholder="1.0.0"
                  value={datasetFormVersion}
                  onChange={(e) => setDatasetFormVersion(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500 placeholder-slate-500 font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Description
                </label>
                <textarea
                  rows={3}
                  placeholder="Describe the domain, cases, or intended scope..."
                  value={datasetFormDesc}
                  onChange={(e) => setDatasetFormDesc(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500 placeholder-slate-500 resize-none"
                />
              </div>

              <div className="pt-2 flex items-center justify-end gap-2.5">
                <button
                  type="button"
                  onClick={() => {
                    setShowCreateDatasetModal(false);
                    setShowEditDatasetModal(false);
                  }}
                  disabled={submittingDataset}
                  className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingDataset}
                  className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-2 transition-all cursor-pointer"
                >
                  {submittingDataset ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Saving...</span>
                    </>
                  ) : (
                    <span>{showCreateDatasetModal ? "Create Dataset" : "Save Changes"}</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* DELETE DATASET CONFIRMATION MODAL                                         */}
      {/* ========================================================================= */}
      {showDeleteDatasetModal && selectedDatasetDetail && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-xs flex items-center justify-center z-50 p-4">
          <div className="bg-[#0e1422] border border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl relative space-y-4 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center gap-2.5 text-rose-400">
              <div className="p-2 rounded-lg bg-rose-500/10 border border-rose-500/20">
                <Trash2 className="w-4 h-4" />
              </div>
              <h3 className="text-sm font-semibold text-white">Delete Dataset</h3>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              Are you sure you want to delete dataset{" "}
              <strong className="text-white font-semibold">{selectedDatasetDetail.name}</strong>?
              This will remove all {selectedDatasetDetail.test_cases?.length || 0} associated test cases.
            </p>

            <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 text-[11px] text-slate-400">
              <Info className="w-3.5 h-3.5 inline mr-1 text-indigo-400" />
              Past evaluation runs referencing this dataset will be safely preserved.
            </div>

            <div className="pt-2 flex items-center justify-end gap-2.5">
              <button
                onClick={() => setShowDeleteDatasetModal(false)}
                disabled={submittingDataset}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteDataset}
                disabled={submittingDataset}
                className="px-4 py-2 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold flex items-center gap-1.5 cursor-pointer"
              >
                {submittingDataset ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Deleting...</span>
                  </>
                ) : (
                  <span>Delete Dataset</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* ADD / EDIT TEST CASE MODAL                                                */}
      {/* ========================================================================= */}
      {(showAddCaseModal || showEditCaseModal) && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-xs flex items-center justify-center z-50 p-4">
          <div className="bg-[#0e1422] border border-slate-800 rounded-2xl max-w-xl w-full p-6 shadow-2xl relative space-y-4 max-h-[90vh] flex flex-col animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800 shrink-0">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-indigo-400" />
                <h3 className="text-sm font-semibold text-white">
                  {showAddCaseModal ? "Add Test Case" : `Edit Case: ${editingCase?.case_identifier}`}
                </h3>
              </div>
              <button
                onClick={() => {
                  setShowAddCaseModal(false);
                  setShowEditCaseModal(false);
                }}
                className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {caseFormError && (
              <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2 shrink-0">
                <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
                <span>{caseFormError}</span>
              </div>
            )}

            <form onSubmit={handleSaveCase} className="flex-1 overflow-y-auto space-y-3.5 pr-1">
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">
                    Identifier <span className="text-rose-400">*</span>
                  </label>
                  <input
                    type="text"
                    placeholder="case_001"
                    value={caseIdInput}
                    onChange={(e) => setCaseIdInput(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500 font-mono"
                    required
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">
                    Query Type
                  </label>
                  <select
                    value={caseQueryTypeInput}
                    onChange={(e) => setCaseQueryTypeInput(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500 cursor-pointer"
                  >
                    <option value="factoid">Factoid</option>
                    <option value="multi_hop">Multi-Hop</option>
                    <option value="coreference">Coreference</option>
                    <option value="refusal">Refusal</option>
                    <option value="citation_needed">Citation Needed</option>
                    <option value="temporal">Temporal</option>
                    <option value="comparative">Comparative</option>
                    <option value="summarization">Summarization</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">
                    Expected Behavior
                  </label>
                  <select
                    value={caseBehaviorInput}
                    onChange={(e) => setCaseBehaviorInput(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500 cursor-pointer"
                  >
                    <option value="answer">Answer (Accurate)</option>
                    <option value="refusal">Refusal (Adversarial/OOD)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Query / Question <span className="text-rose-400">*</span>
                </label>
                <textarea
                  rows={2}
                  placeholder="Enter the benchmark query to evaluate..."
                  value={caseQueryInput}
                  onChange={(e) => setCaseQueryInput(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500 resize-none"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Ground Truth Answer
                </label>
                <textarea
                  rows={2}
                  placeholder="Expected answer for correctness & faithfulness scoring..."
                  value={caseGroundTruthInput}
                  onChange={(e) => setCaseGroundTruthInput(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500 resize-none font-sans"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Key Facts to Check (one per line)
                </label>
                <textarea
                  rows={2}
                  placeholder="Fact 1&#10;Fact 2"
                  value={caseKeyFactsInput}
                  onChange={(e) => setCaseKeyFactsInput(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500 resize-none font-mono text-[11px]"
                />
              </div>

              {/* Evidence Anchor Sub-section */}
              <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2.5">
                <span className="text-[11px] font-semibold text-slate-300 block">
                  Ground Truth Evidence Anchor (Optional)
                </span>
                <div className="grid grid-cols-3 gap-2">
                  <div className="col-span-2">
                    <input
                      type="text"
                      placeholder="Document title (e.g. policy.pdf)"
                      value={evidenceDocTitle}
                      onChange={(e) => setEvidenceDocTitle(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                    />
                  </div>
                  <div>
                    <input
                      type="text"
                      placeholder="Page (e.g. 1)"
                      value={evidencePageNum}
                      onChange={(e) => setEvidencePageNum(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 font-mono"
                    />
                  </div>
                </div>
                <div>
                  <textarea
                    rows={2}
                    placeholder="Content anchors / exact quotes to match (one per line)..."
                    value={evidenceAnchorsInput}
                    onChange={(e) => setEvidenceAnchorsInput(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 resize-none font-mono text-[11px]"
                  />
                </div>
              </div>

              <div className="pt-2 flex items-center justify-end gap-2.5 shrink-0">
                <button
                  type="button"
                  onClick={() => {
                    setShowAddCaseModal(false);
                    setShowEditCaseModal(false);
                  }}
                  disabled={submittingCase}
                  className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingCase}
                  className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-2 cursor-pointer"
                >
                  {submittingCase ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Saving...</span>
                    </>
                  ) : (
                    <span>Save Test Case</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* DELETE TEST CASE CONFIRMATION MODAL                                       */}
      {/* ========================================================================= */}
      {showDeleteCaseModal && caseToDelete && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-xs flex items-center justify-center z-50 p-4">
          <div className="bg-[#0e1422] border border-slate-800 rounded-2xl max-w-sm w-full p-6 shadow-2xl relative space-y-4 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center gap-2.5 text-rose-400">
              <div className="p-2 rounded-lg bg-rose-500/10 border border-rose-500/20">
                <Trash2 className="w-4 h-4" />
              </div>
              <h3 className="text-sm font-semibold text-white">Delete Test Case</h3>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              Are you sure you want to delete test case{" "}
              <strong className="text-white font-mono">{caseToDelete.case_identifier}</strong>?
            </p>

            <div className="pt-2 flex items-center justify-end gap-2.5">
              <button
                onClick={() => {
                  setShowDeleteCaseModal(false);
                  setCaseToDelete(null);
                }}
                disabled={submittingCase}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteCase}
                disabled={submittingCase}
                className="px-4 py-2 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold flex items-center gap-1.5 cursor-pointer"
              >
                {submittingCase ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Deleting...</span>
                  </>
                ) : (
                  <span>Delete Case</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* IMPORT TEST CASES JSON MODAL                                              */}
      {/* ========================================================================= */}
      {showImportModal && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-xs flex items-center justify-center z-50 p-4">
          <div className="bg-[#0e1422] border border-slate-800 rounded-2xl max-w-xl w-full p-6 shadow-2xl relative space-y-4 animate-in fade-in zoom-in-95 duration-150 flex flex-col max-h-[90vh]">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800 shrink-0">
              <div className="flex items-center gap-2">
                <Upload className="w-4 h-4 text-indigo-400" />
                <h3 className="text-sm font-semibold text-white">Import Test Cases from JSON</h3>
              </div>
              <button
                onClick={() => setShowImportModal(false)}
                className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {importError && (
              <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2 shrink-0">
                <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
                <span>{importError}</span>
              </div>
            )}

            <form onSubmit={handleImportJson} className="flex-1 overflow-y-auto space-y-3 pr-1">
              <p className="text-xs text-slate-400">
                Paste an array of test cases formatted as JSON. Supported schema matches the benchmark format:
              </p>

              <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800 font-mono text-[10px] text-slate-400">
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
              </div>

              <div>
                <textarea
                  rows={8}
                  placeholder="Paste JSON array here..."
                  value={importJsonText}
                  onChange={(e) => setImportJsonText(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-lg p-3 text-xs text-white font-mono placeholder-slate-600 focus:outline-none focus:border-indigo-500 resize-none"
                  required
                />
              </div>

              {importProgress && (
                <div className="p-3 rounded-xl bg-indigo-500/10 border border-indigo-500/30 text-xs text-indigo-300 flex items-center gap-2">
                  <RefreshCw className="w-4 h-4 animate-spin shrink-0 text-indigo-400" />
                  <span>
                    Importing case {importProgress.current} of {importProgress.total}...
                  </span>
                </div>
              )}

              <div className="pt-2 flex items-center justify-end gap-2.5 shrink-0">
                <button
                  type="button"
                  onClick={() => setShowImportModal(false)}
                  disabled={importing}
                  className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={importing}
                  className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-2 cursor-pointer"
                >
                  {importing ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Importing...</span>
                    </>
                  ) : (
                    <span>Import Cases</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
