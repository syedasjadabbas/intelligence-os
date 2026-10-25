"use client";

import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { useAuth } from "@/lib/auth-context";
import { api, DocumentItem, DocumentDetail } from "@/lib/api";
import { cn, formatBytes, formatDate, getErrorMessage } from "@/lib/utils";
import {
  CloudUpload,
  FileText,
  RefreshCw,
  Trash2,
  Search,
  Layers,
  Database,
  CheckCircle2,
  AlertTriangle,
  Info,
  Clock,
  ExternalLink,
} from "lucide-react";
import { AppShell, PageHeader } from "@/components/app-shell";
import { DocumentStatusBadge } from "@/components/status";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Spinner, LoadingState } from "@/components/ui/spinner";
import { EmptyState, Panel, PanelHeader, Eyebrow } from "@/components/ui/surface";
import { TableMessage, TableWrap, TBody, Td, Th, THead, Tr } from "@/components/ui/table";
import { Dialog } from "@/components/ui/dialog";

export default function DocumentsPage() {
  const { user, org } = useAuth();
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedDoc, setSelectedDoc] = useState<DocumentItem | null>(null);
  const [docDetail, setDocDetail] = useState<DocumentDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchDocuments = useCallback(async () => {
    try {
      const docs = await api.listDocuments();
      setDocuments(docs);
    } catch (err: unknown) {
      console.error("Failed to fetch documents:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) {
      fetchDocuments();
    }
  }, [user, fetchDocuments]);

  // Auto-polling for active background processing tasks
  useEffect(() => {
    const hasActiveProcessing = documents.some(
      (d) => d.status === "QUEUED" || d.status === "PROCESSING"
    );

    if (!hasActiveProcessing) return;

    const interval = setInterval(() => {
      fetchDocuments();
    }, 2500);

    return () => clearInterval(interval);
  }, [documents, fetchDocuments]);

  const handleUploadFile = async (file: File) => {
    setUploadError(null);

    // Validation: PDF extension
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setUploadError("Only PDF (.pdf) documents are accepted.");
      return;
    }

    // Validation: 20MB limit
    const MAX_SIZE = 20 * 1024 * 1024;
    if (file.size > MAX_SIZE) {
      setUploadError("File size exceeds 20MB maximum limit.");
      return;
    }

    setUploading(true);
    try {
      await api.uploadDocument(file);
      await fetchDocuments();
    } catch (err: unknown) {
      setUploadError(getErrorMessage(err) || "Failed to upload document.");
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleUploadFile(e.dataTransfer.files[0]);
    }
  };

  const handleDelete = async (docId: string, title: string) => {
    if (!window.confirm(`Are you sure you want to delete "${title}"? This will permanently delete its chunks and vector embeddings.`)) {
      return;
    }

    setDeletingId(docId);
    try {
      await api.deleteDocument(docId);
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
      if (selectedDoc?.id === docId) {
        setSelectedDoc(null);
        setDocDetail(null);
      }
    } catch (err: unknown) {
      alert(getErrorMessage(err) || "Failed to delete document.");
    } finally {
      setDeletingId(null);
    }
  };

  const handleInspectDoc = async (doc: DocumentItem) => {
    setSelectedDoc(doc);
    setLoadingDetail(true);
    try {
      const detail = await api.getDocument(doc.id);
      setDocDetail(detail);
    } catch (err: unknown) {
      console.warn("Failed to load document detail:", err);
      setDocDetail(null);
    } finally {
      setLoadingDetail(false);
    }
  };

  // Filtered documents
  const filteredDocuments = useMemo(() => {
    if (!searchQuery.trim()) return documents;
    const q = searchQuery.toLowerCase();
    return documents.filter(
      (d) => d.title.toLowerCase().includes(q) || d.id.toLowerCase().includes(q)
    );
  }, [documents, searchQuery]);

  // Derived metrics
  const totalChunks = documents.reduce((acc, d) => acc + (d.total_chunks || 0), 0);
  const totalBytes = documents.reduce((acc, d) => acc + d.file_size_bytes, 0);
  const indexedCount = documents.filter((d) => d.status === "COMPLETED").length;
  const activeCount = documents.filter(
    (d) => d.status === "QUEUED" || d.status === "PROCESSING"
  ).length;
  const failedCount = documents.filter((d) => d.status === "FAILED").length;

  return (
    <AppShell width="default">
      <PageHeader
        eyebrow="Knowledge base"
        title="Documents"
        description="Manage your organization's knowledge store. Uploaded PDFs are parsed, chunked by section, embedded as vector representations and added to the hybrid search index."
        actions={
          <Button
            variant="secondary"
            onClick={() => fetchDocuments()}
            title="Refresh documents"
          >
            <RefreshCw className={cn(loading && "animate-spin")} />
            Refresh
          </Button>
        }
      />

      {/* Summary 4-KPI Metric Cards matching Reference Screenshot */}
      <div className="mb-6 grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
        <div className="metric-card-ref p-4.5">
          <div className="flex items-center gap-3">
            <div className="flex size-9 items-center justify-center rounded-full border border-white/10 bg-white/[0.05] text-white">
              <FileText className="size-4 text-[#ff7a45]" />
            </div>
            <span className="text-xs font-medium text-[#8e95a5]">Total Documents</span>
          </div>
          <div className="mt-3 font-mono text-2xl font-bold tracking-tight text-white">
            {loading && documents.length === 0 ? "—" : documents.length}
          </div>
          <div className="mt-2.5 flex items-center gap-1.5 text-[11px] font-medium text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20 w-fit">
            <span className="size-1 rounded-full bg-emerald-400" />
            <span>100% Tenant isolated</span>
          </div>
        </div>

        <div className="metric-card-ref p-4.5">
          <div className="flex items-center gap-3">
            <div className="flex size-9 items-center justify-center rounded-full border border-white/10 bg-white/[0.05] text-white">
              <Layers className="size-4 text-[#5b5ff5]" />
            </div>
            <span className="text-xs font-medium text-[#8e95a5]">Indexed Chunks</span>
          </div>
          <div className="mt-3 font-mono text-2xl font-bold tracking-tight text-white">
            {loading && documents.length === 0 ? "—" : totalChunks}
          </div>
          <div className="mt-2.5 flex items-center gap-1.5 text-[11px] font-medium text-[#8e95a5] bg-white/[0.04] px-2 py-0.5 rounded-full border border-white/10 w-fit">
            <span>384-dim all-MiniLM</span>
          </div>
        </div>

        <div className="metric-card-ref p-4.5">
          <div className="flex items-center gap-3">
            <div className="flex size-9 items-center justify-center rounded-full border border-white/10 bg-white/[0.05] text-white">
              <Database className="size-4 text-amber-400" />
            </div>
            <span className="text-xs font-medium text-[#8e95a5]">Storage Volume</span>
          </div>
          <div className="mt-3 font-mono text-2xl font-bold tracking-tight text-white">
            {loading && documents.length === 0 ? "—" : formatBytes(totalBytes)}
          </div>
          <div className="mt-2.5 flex items-center gap-1.5 text-[11px] font-medium text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded-full border border-amber-500/20 w-fit">
            <span>PDF payload allocated</span>
          </div>
        </div>

        <div className="metric-card-ref p-4.5">
          <div className="flex items-center gap-3">
            <div className="flex size-9 items-center justify-center rounded-full border border-white/10 bg-white/[0.05] text-white">
              {failedCount > 0 ? (
                <AlertTriangle className="size-4 text-rose-400" />
              ) : activeCount > 0 ? (
                <Clock className="size-4 text-amber-400 animate-spin" />
              ) : (
                <CheckCircle2 className="size-4 text-emerald-400" />
              )}
            </div>
            <span className="text-xs font-medium text-[#8e95a5]">Pipeline Health</span>
          </div>
          <div className="mt-3 font-mono text-2xl font-bold tracking-tight text-white">
            {activeCount > 0 ? (
              <span className="text-amber-400">{activeCount} running</span>
            ) : failedCount > 0 ? (
              <span className="text-rose-400">{failedCount} failed</span>
            ) : (
              <span className="text-emerald-400">Optimal</span>
            )}
          </div>
          <div className="mt-2.5 flex items-center gap-1.5 text-[11px] font-medium text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20 w-fit">
            <span>{indexedCount} of {documents.length} verified</span>
          </div>
        </div>
      </div>

      {/* Upload Panel */}
      <div className="panel-ref mb-6 overflow-hidden">
        <div className="border-b border-white/[0.06] bg-white/[0.02] px-5 py-4">
          <h2 className="text-sm font-semibold tracking-tight text-white">Ingest Document</h2>
          <p className="mt-0.5 text-xs text-[#8e95a5]">
            PDF files are parsed for text and section headings, embedded as high-dimensional vectors and added to the full-text BM25 index.
          </p>
        </div>
        <div className="space-y-4 p-5">
          {uploadError && (
            <Alert tone="danger" onDismiss={() => setUploadError(null)}>
              {uploadError}
            </Alert>
          )}

          <div
            role="button"
            tabIndex={0}
            aria-label="Upload a PDF document"
            aria-busy={uploading || undefined}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                fileInputRef.current?.click();
              }
            }}
            className={cn(
              "group flex cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed px-6 py-10 text-center transition-all duration-150",
              dragActive
                ? "border-[#ff7a45] bg-[#ff7a45]/[0.08]"
                : "border-white/10 bg-[#0c0d12] hover:border-white/20 hover:bg-white/[0.02]"
            )}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              className="hidden"
              onChange={(e) => {
                if (e.target.files && e.target.files[0]) {
                  handleUploadFile(e.target.files[0]);
                }
              }}
            />

            <div
              className={cn(
                "mb-3.5 flex size-12 items-center justify-center rounded-2xl border bg-white/[0.04] transition-transform duration-150 group-hover:scale-105",
                dragActive
                  ? "border-[#ff7a45] text-[#ff7a45]"
                  : "border-white/10 text-[#8e95a5] group-hover:text-white"
              )}
            >
              {uploading ? <Spinner className="size-5 text-[#ff7a45]" /> : <CloudUpload className="size-6" />}
            </div>

            <p className="text-sm font-medium text-white">
              {uploading
                ? "Uploading PDF and dispatching background worker…"
                : dragActive
                ? "Drop file to start processing"
                : (
                  <>
                    Drop a PDF here, or <span className="text-[#ff7a45] underline underline-offset-2">browse files</span>
                  </>
                )}
            </p>
            <p className="mt-1 text-xs text-[#8e95a5]">
              PDF only · 20 MB maximum · partitioned strictly for{" "}
              <span className="font-medium text-white">{org?.name || "your organization"}</span>
            </p>
          </div>
        </div>
      </div>

      {/* Documents Table with Filter Bar */}
      <div className="panel-ref overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-white/[0.06] bg-white/[0.02] p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
          <div className="flex items-center gap-2.5">
            <h2 className="text-sm font-semibold tracking-tight text-white">Knowledge Assets</h2>
            <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 font-mono text-[11px] text-[#8e95a5]">
              {filteredDocuments.length}
            </span>
            {activeCount > 0 && (
              <Badge tone="info" dot pulse>
                Polling active
              </Badge>
            )}
          </div>

          <div className="relative w-full sm:w-72">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-[#636a7e]" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search documents by name or ID…"
              className="w-full rounded-xl border border-white/10 bg-[#0c0d12] py-1.5 pl-8 pr-3 text-xs text-white placeholder:text-[#5a6072] focus:border-white/20 focus:outline-none"
            />
          </div>
        </div>

        <TableWrap>
          {filteredDocuments.length > 0 && (
            <THead>
              <tr>
                <Th>Document</Th>
                <Th>Status</Th>
                <Th className="hidden sm:table-cell">Chunks</Th>
                <Th className="hidden md:table-cell">Size</Th>
                <Th className="hidden lg:table-cell">Uploaded</Th>
                <Th className="text-right">Actions</Th>
              </tr>
            </THead>
          )}
          <TBody>
            {filteredDocuments.length === 0 ? (
              <TableMessage colSpan={6}>
                {loading ? (
                  <LoadingState label="Loading documents…" />
                ) : documents.length === 0 ? (
                  <EmptyState
                    icon={<FileText />}
                    title="No documents indexed yet"
                    description="Upload your first PDF above to enable grounded hybrid retrieval across your organization."
                  />
                ) : (
                  <EmptyState
                    icon={<Search />}
                    title="No matching documents"
                    description={`No documents matching "${searchQuery}". Clear your search query to see all documents.`}
                  />
                )}
              </TableMessage>
            ) : (
              filteredDocuments.map((doc) => (
                <Tr
                  key={doc.id}
                  className="cursor-pointer transition-colors hover:bg-surface-2/60"
                  onClick={() => handleInspectDoc(doc)}
                >
                  <Td className="max-w-0 w-full">
                    <div className="flex items-center gap-3">
                      <div className="flex size-8 shrink-0 items-center justify-center rounded-lg border border-line-strong bg-surface-2 text-fg-subtle">
                        <FileText className="size-4" />
                      </div>
                      <div className="min-w-0">
                        <p className="truncate font-medium text-fg" title={doc.title}>
                          {doc.title}
                        </p>
                        <p className="truncate font-mono text-[11px] text-fg-faint">{doc.id}</p>
                        {doc.error_message && (
                          <p className="mt-0.5 text-xs text-danger">Error: {doc.error_message}</p>
                        )}
                      </div>
                    </div>
                  </Td>
                  <Td>
                    <DocumentStatusBadge status={doc.status} />
                  </Td>
                  <Td className="tabular hidden whitespace-nowrap font-mono text-xs text-fg-muted sm:table-cell">
                    {doc.total_chunks !== undefined && doc.total_chunks !== null ? (
                      <span className="font-semibold text-fg">{doc.total_chunks}</span>
                    ) : (
                      "—"
                    )}
                  </Td>
                  <Td className="tabular hidden whitespace-nowrap font-mono text-xs text-fg-muted md:table-cell">
                    {formatBytes(doc.file_size_bytes)}
                  </Td>
                  <Td className="hidden whitespace-nowrap text-xs text-fg-muted lg:table-cell">
                    {formatDate(doc.created_at)}
                  </Td>
                  <Td className="text-right">
                    <div className="flex items-center justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleInspectDoc(doc)}
                        className="text-xs text-fg-subtle hover:text-fg"
                      >
                        Inspect
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => handleDelete(doc.id, doc.title)}
                        disabled={deletingId === doc.id}
                        className="hover:bg-danger/10 hover:text-danger"
                        title="Delete Document"
                        aria-label={`Delete ${doc.title}`}
                      >
                        {deletingId === doc.id ? <Spinner /> : <Trash2 />}
                      </Button>
                    </div>
                  </Td>
                </Tr>
              ))
            )}
          </TBody>
        </TableWrap>
      </div>

      {/* Document Inspector Sheet */}
      {selectedDoc && (
        <Dialog
          variant="right"
          onClose={() => {
            setSelectedDoc(null);
            setDocDetail(null);
          }}
          panelClassName="sm:max-w-md lg:max-w-lg"
          title={selectedDoc.title}
          icon={<FileText />}
          meta={<DocumentStatusBadge status={selectedDoc.status} />}
          description="Detailed metadata and indexing parameters for this knowledge asset."
          bodyClassName="space-y-6"
          footer={
            <div className="flex w-full items-center justify-between">
              <span className="text-xs text-fg-subtle">
                ID: <span className="font-mono">{selectedDoc.id.slice(0, 8)}…</span>
              </span>
              <Button
                variant="danger"
                size="sm"
                onClick={() => handleDelete(selectedDoc.id, selectedDoc.title)}
                disabled={deletingId === selectedDoc.id}
              >
                <Trash2 className="size-3.5 mr-1" />
                Delete Asset
              </Button>
            </div>
          }
        >
          {/* Metadata Cards */}
          <div className="space-y-3">
            <Eyebrow>Storage &amp; Index Metrics</Eyebrow>
            <dl className="grid grid-cols-2 gap-2 text-xs">
              <div className="rounded-lg border border-line bg-surface-2 p-3">
                <dt className="text-fg-subtle">Total Chunks</dt>
                <dd className="mt-1 font-mono text-base font-semibold text-fg">
                  {docDetail?.total_chunks ?? selectedDoc.total_chunks ?? "—"}
                </dd>
              </div>
              <div className="rounded-lg border border-line bg-surface-2 p-3">
                <dt className="text-fg-subtle">File Size</dt>
                <dd className="mt-1 font-mono text-base font-semibold text-fg">
                  {formatBytes(selectedDoc.file_size_bytes)}
                </dd>
              </div>
              <div className="rounded-lg border border-line bg-surface-2 p-3">
                <dt className="text-fg-subtle">Created</dt>
                <dd className="mt-1 text-fg-muted font-medium">
                  {formatDate(selectedDoc.created_at)}
                </dd>
              </div>
              <div className="rounded-lg border border-line bg-surface-2 p-3">
                <dt className="text-fg-subtle">Updated</dt>
                <dd className="mt-1 text-fg-muted font-medium">
                  {formatDate(selectedDoc.updated_at)}
                </dd>
              </div>
            </dl>
          </div>

          {/* Identifier block */}
          <div className="space-y-3">
            <Eyebrow>Identifiers</Eyebrow>
            <div className="rounded-lg border border-line bg-surface-2 p-3 font-mono text-xs space-y-1.5">
              <div className="flex justify-between">
                <span className="text-fg-subtle">Document ID:</span>
                <span className="text-fg-muted select-all">{selectedDoc.id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-fg-subtle">Tenant Org ID:</span>
                <span className="text-fg-muted select-all">{selectedDoc.org_id}</span>
              </div>
            </div>
          </div>

          {/* Error Message if Failed */}
          {selectedDoc.error_message && (
            <Alert tone="danger" title="Processing Pipeline Failure">
              {selectedDoc.error_message}
            </Alert>
          )}

          {/* Chunks Inspection list if loaded */}
          {loadingDetail ? (
            <div className="py-6 text-center">
              <Spinner className="mx-auto size-5 text-accent" />
              <p className="mt-2 text-xs text-fg-subtle">Loading chunk partition details…</p>
            </div>
          ) : docDetail?.chunks && docDetail.chunks.length > 0 ? (
            <div className="space-y-3">
              <Eyebrow>Indexed Chunks ({docDetail.chunks.length})</Eyebrow>
              <div className="max-h-72 space-y-2 overflow-y-auto pr-1">
                {docDetail.chunks.map((chunk) => (
                  <div
                    key={chunk.id}
                    className="rounded-lg border border-line bg-surface-2 p-3 text-xs space-y-1"
                  >
                    <div className="flex items-center justify-between text-[11px] text-fg-subtle font-mono">
                      <span>Chunk #{chunk.chunk_index + 1}</span>
                      {chunk.page_number && <span>Page {chunk.page_number}</span>}
                    </div>
                    {chunk.section_heading && (
                      <p className="font-medium text-accent text-[12px]">{chunk.section_heading}</p>
                    )}
                    <p className="line-clamp-3 text-fg-muted font-mono text-[11px] leading-relaxed">
                      {chunk.content}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </Dialog>
      )}
    </AppShell>
  );
}
