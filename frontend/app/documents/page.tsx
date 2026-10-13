"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { useAuth } from "@/lib/auth-context";
import { api, DocumentItem } from "@/lib/api";
import { cn, formatBytes, formatDate, getErrorMessage } from "@/lib/utils";
import { CloudUpload, FileText, RefreshCw, Trash2 } from "lucide-react";
import { AppShell, PageHeader } from "@/components/app-shell";
import { DocumentStatusBadge } from "@/components/status";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Spinner, LoadingState } from "@/components/ui/spinner";
import { EmptyState, Panel, PanelHeader } from "@/components/ui/surface";
import { TableMessage, TableWrap, TBody, Td, Th, THead, Tr } from "@/components/ui/table";

export default function DocumentsPage() {
  const { user, org } = useAuth();
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

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
    } catch (err: unknown) {
      alert(getErrorMessage(err) || "Failed to delete document.");
    } finally {
      setDeletingId(null);
    }
  };

  // Derived summary counts (presentation only)
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
        description="Manage your organization's knowledge store. Uploaded PDFs are parsed, chunked by section, embedded and indexed for hybrid search."
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

      {/* Summary */}
      <dl className="mb-6 grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-line bg-line sm:grid-cols-4">
        {[
          { label: "Documents", value: documents.length, tone: "text-fg" },
          { label: "Indexed", value: indexedCount, tone: "text-success" },
          { label: "In progress", value: activeCount, tone: activeCount ? "text-info" : "text-fg" },
          { label: "Failed", value: failedCount, tone: failedCount ? "text-danger" : "text-fg" },
        ].map((s) => (
          <div key={s.label} className="bg-surface px-4 py-3.5">
            <dt className="text-xs font-medium text-fg-subtle">{s.label}</dt>
            <dd className={cn("tabular mt-1.5 font-mono text-xl font-medium", s.tone)}>
              {loading && documents.length === 0 ? "—" : s.value}
            </dd>
          </div>
        ))}
      </dl>

      {/* Upload */}
      <Panel className="mb-6">
        <PanelHeader
          title="Ingest document"
          description="PDF files are parsed for text and section headings, embedded as 1536-dim vectors and added to the full-text index."
        />
        <div className="space-y-4 p-4 sm:p-5">
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
              "group flex cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed px-6 py-10 text-center transition-[border-color,background-color] duration-150",
              dragActive
                ? "border-accent bg-accent/[0.06]"
                : "border-line-strong bg-canvas/40 hover:border-fg-faint hover:bg-surface-2"
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
                "mb-4 flex size-11 items-center justify-center rounded-lg border bg-surface-2 transition-colors",
                dragActive
                  ? "border-accent/50 text-accent"
                  : "border-line-strong text-fg-subtle group-hover:text-fg-muted"
              )}
            >
              {uploading ? <Spinner className="size-5 text-accent" /> : <CloudUpload className="size-5" />}
            </div>

            <p className="text-sm font-medium text-fg">
              {uploading
                ? "Uploading and starting background pipeline…"
                : dragActive
                ? "Drop to upload"
                : (
                  <>
                    Drop a PDF here, or <span className="text-accent-strong">browse files</span>
                  </>
                )}
            </p>
            <p className="mt-1.5 max-w-sm text-[13px] leading-relaxed text-fg-subtle">
              PDF only · 20 MB maximum · chunks stay isolated to{" "}
              <span className="font-medium text-fg-muted">{org?.name || "your organization"}</span>
            </p>
          </div>
        </div>
      </Panel>

      {/* Documents table */}
      <Panel>
        <PanelHeader
          title="Indexed documents"
          count={documents.length}
          actions={
            activeCount > 0 ? (
              <Badge tone="info" dot pulse>
                Live status auto-polling active
              </Badge>
            ) : (
              <span className="text-xs text-fg-subtle">Status refreshes automatically while processing</span>
            )
          }
        />

        <TableWrap>
          {documents.length > 0 && (
            <THead>
              <tr>
                <Th>Document</Th>
                <Th>Status</Th>
                <Th className="hidden sm:table-cell">Size</Th>
                <Th className="hidden md:table-cell">Uploaded</Th>
                <Th className="text-right">
                  <span className="sr-only">Actions</span>
                </Th>
              </tr>
            </THead>
          )}
          <TBody>
            {documents.length === 0 ? (
              <TableMessage colSpan={5}>
                {loading ? (
                  <LoadingState label="Loading documents…" />
                ) : (
                  <EmptyState
                    icon={<FileText />}
                    title="No documents indexed yet"
                    description="Upload your first PDF above to enable grounded hybrid retrieval across your organization."
                  />
                )}
              </TableMessage>
            ) : (
              documents.map((doc) => (
                <Tr key={doc.id}>
                  <Td className="max-w-0 w-full">
                    <div className="flex items-center gap-3">
                      <div className="flex size-8 shrink-0 items-center justify-center rounded-md border border-line-strong bg-surface-2 text-fg-subtle">
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
                    {formatBytes(doc.file_size_bytes)}
                  </Td>
                  <Td className="hidden whitespace-nowrap text-xs text-fg-muted md:table-cell">
                    {formatDate(doc.created_at)}
                  </Td>
                  <Td className="text-right">
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
                  </Td>
                </Tr>
              ))
            )}
          </TBody>
        </TableWrap>
      </Panel>
    </AppShell>
  );
}
