"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import {
  api,
  DocumentItem,
  DocumentStatus,
} from "@/lib/api";
import { formatBytes, formatDate } from "@/lib/utils";
import {
  UploadCloud,
  FileText,
  Trash2,
  RefreshCw,
  ArrowLeft,
  CheckCircle2,
  Clock,
  AlertTriangle,
  XCircle,
  Shield,
  Layers,
  FileCheck,
  BarChart3,
} from "lucide-react";

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
    } catch (err: any) {
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
    } catch (err: any) {
      setUploadError(err.message || "Failed to upload document.");
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
    } catch (err: any) {
      alert(err.message || "Failed to delete document.");
    } finally {
      setDeletingId(null);
    }
  };

  const getStatusBadge = (status: DocumentStatus) => {
    switch (status) {
      case "COMPLETED":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
            <CheckCircle2 className="w-3.5 h-3.5" />
            COMPLETED
          </span>
        );
      case "PROCESSING":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/30 animate-pulse">
            <Clock className="w-3.5 h-3.5" />
            PROCESSING
          </span>
        );
      case "QUEUED":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-500/15 text-slate-300 border border-slate-500/30">
            <Clock className="w-3.5 h-3.5" />
            QUEUED
          </span>
        );
      case "FAILED":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-500/15 text-rose-300 border border-rose-500/30">
            <XCircle className="w-3.5 h-3.5" />
            FAILED
          </span>
        );
    }
  };

  return (
    <div className="min-h-screen bg-[#090d16] text-slate-100 flex flex-col">
      {/* Navigation Header */}
      <header className="border-b border-slate-800 bg-[#0d131f] px-6 py-3.5 flex items-center justify-between sticky top-0 z-30">
        <div className="flex items-center gap-4">
          <Link
            href="/"
            className="p-1.5 px-2.5 rounded-lg bg-slate-800/80 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-700/60 transition-colors flex items-center gap-1.5 text-xs font-medium cursor-pointer"
          >
            <ArrowLeft className="w-4 h-4 text-slate-400" />
            <span>Back to Chat</span>
          </Link>
          <div className="h-5 w-px bg-slate-800" />
          <div>
            <h1 className="text-base font-semibold text-white flex items-center gap-2">
              <Layers className="w-4 h-4 text-slate-300" />
              Document Admin Console
            </h1>
            <p className="text-[11px] text-slate-400">
              Manage organization knowledge store, chunking, and pgvector embeddings
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
          <Link
            href="/evaluations"
            className="p-1.5 px-2.5 rounded-lg bg-slate-800/80 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-700/60 transition-colors flex items-center gap-1.5 text-xs font-medium cursor-pointer"
          >
            <BarChart3 className="w-3.5 h-3.5 text-indigo-400" />
            <span>Evaluations</span>
          </Link>
          <button
            onClick={() => fetchDocuments()}
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors cursor-pointer border border-slate-700/60"
            title="Refresh documents"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-6xl w-full mx-auto p-6 space-y-6">
        {/* Upload Card */}
        <div className="rounded-xl p-6 border border-slate-800 bg-slate-900/60 shadow-sm">
          <h2 className="text-sm font-semibold text-white uppercase tracking-wider mb-2 flex items-center gap-2">
            <UploadCloud className="w-4 h-4 text-slate-300" />
            Ingest Knowledge Document
          </h2>
          <p className="text-xs text-slate-400 mb-4">
            Upload PDF files to parse text, extract section headings, generate 1536-dim vector embeddings, and build full-text search indexes.
          </p>

          {uploadError && (
            <div className="mb-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>{uploadError}</span>
            </div>
          )}

          {/* Drag & Drop Zone */}
          <div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            className={`border border-dashed rounded-xl p-8 text-center transition-all flex flex-col items-center justify-center cursor-pointer ${
              dragActive
                ? "border-blue-500 bg-blue-500/10 scale-[1.01]"
                : "border-slate-800 bg-slate-950/60 hover:border-slate-700 hover:bg-slate-900/60"
            }`}
            onClick={() => fileInputRef.current?.click()}
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

            <div className="w-12 h-12 rounded-xl bg-slate-800 border border-slate-700/80 flex items-center justify-center text-slate-300 mb-3 shadow-sm">
              {uploading ? (
                <div className="w-5 h-5 border-2 border-slate-500 border-t-white rounded-full animate-spin" />
              ) : (
                <UploadCloud className="w-6 h-6 text-slate-300" />
              )}
            </div>

            <p className="text-sm font-semibold text-white mb-1">
              {uploading
                ? "Uploading & Spawning Background Pipeline..."
                : "Click or drag & drop PDF here"}
            </p>
            <p className="text-xs text-slate-400 max-w-sm">
              Maximum file size: 20MB. Document chunks will be isolated exclusively to{" "}
              <span className="text-slate-200 font-medium">{org?.name || "your organization"}</span>.
            </p>
          </div>
        </div>

        {/* Documents Table */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/40">
            <div className="flex items-center gap-2">
              <FileCheck className="w-4 h-4 text-slate-300" />
              <h3 className="font-semibold text-white text-sm">Indexed Documents</h3>
              <span className="px-2 py-0.5 rounded-full text-xs font-mono bg-slate-800 text-slate-300 border border-slate-700">
                {documents.length}
              </span>
            </div>

            <span className="text-xs text-slate-400">
              Live status auto-polling active
            </span>
          </div>

          {documents.length === 0 ? (
            <div className="p-12 text-center text-slate-400">
              <FileText className="w-12 h-12 text-slate-600 mx-auto mb-3" />
              <p className="text-sm font-medium text-slate-300">No documents indexed yet</p>
              <p className="text-xs text-slate-500 mt-1">
                Upload your first technical PDF above to enable grounded hybrid retrieval.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-900/80 text-slate-400 border-b border-white/5 uppercase tracking-wider font-semibold">
                  <tr>
                    <th className="py-3.5 px-6">Document Title</th>
                    <th className="py-3.5 px-6">Status</th>
                    <th className="py-3.5 px-6">Size</th>
                    <th className="py-3.5 px-6">Uploaded At</th>
                    <th className="py-3.5 px-6 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5 text-slate-300">
                  {documents.map((doc) => (
                    <tr
                      key={doc.id}
                      className="hover:bg-slate-800/40 transition-colors"
                    >
                      <td className="py-4 px-6 font-medium text-white flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-slate-800 text-cyan-400 shrink-0">
                          <FileText className="w-4 h-4" />
                        </div>
                        <div className="min-w-0">
                          <p className="font-semibold text-sm truncate max-w-md">
                            {doc.title}
                          </p>
                          <p className="text-[11px] font-mono text-slate-500">
                            ID: {doc.id}
                          </p>
                          {doc.error_message && (
                            <p className="text-[11px] text-rose-400 mt-0.5">
                              Error: {doc.error_message}
                            </p>
                          )}
                        </div>
                      </td>
                      <td className="py-4 px-6">
                        {getStatusBadge(doc.status)}
                      </td>
                      <td className="py-4 px-6 font-mono text-slate-400">
                        {formatBytes(doc.file_size_bytes)}
                      </td>
                      <td className="py-4 px-6 text-slate-400">
                        {formatDate(doc.created_at)}
                      </td>
                      <td className="py-4 px-6 text-right">
                        <button
                          onClick={() => handleDelete(doc.id, doc.title)}
                          disabled={deletingId === doc.id}
                          className="p-2 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors disabled:opacity-50 cursor-pointer"
                          title="Delete Document"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
