"use client";

import React from "react";
import { CitationItem } from "@/lib/api";
import {
  X,
  FileText,
  Bookmark,
  Hash,
  Copy,
  Check,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";

interface CitationDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  citation: CitationItem | null;
  allCitations?: CitationItem[];
  onSelectCitation?: (citation: CitationItem) => void;
}

export function CitationDrawer({
  isOpen,
  onClose,
  citation,
  allCitations = [],
  onSelectCitation,
}: CitationDrawerProps) {
  const [copied, setCopied] = React.useState(false);

  if (!isOpen || !citation) return null;

  const currentIndex = allCitations.findIndex(
    (c) => c.source_index === citation.source_index
  );

  const handlePrev = () => {
    if (currentIndex > 0 && onSelectCitation) {
      onSelectCitation(allCitations[currentIndex - 1]);
    }
  };

  const handleNext = () => {
    if (currentIndex < allCitations.length - 1 && onSelectCitation) {
      onSelectCitation(allCitations[currentIndex + 1]);
    }
  };

  const handleCopy = () => {
    if (citation.content_snippet) {
      navigator.clipboard.writeText(citation.content_snippet);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden flex justify-end">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />

      {/* Drawer Panel */}
      <div className="relative w-full max-w-lg bg-[#0e1628] border-l border-white/10 shadow-2xl h-full flex flex-col z-10 animate-in slide-in-from-right duration-200">
        {/* Header */}
        <div className="px-6 py-5 border-b border-white/10 flex items-center justify-between bg-slate-900/40">
          <div className="flex items-center gap-3">
            <span className="px-2.5 py-1 rounded-md text-xs font-bold bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 font-mono">
              {citation.source_tag || `[Source ${citation.source_index}]`}
            </span>
            <h3 className="font-semibold text-white text-base">Citation Inspector</h3>
          </div>

          <div className="flex items-center gap-1">
            {allCitations.length > 1 && (
              <div className="flex items-center gap-1 mr-2 bg-slate-800/80 p-1 rounded-lg border border-slate-700/50">
                <button
                  onClick={handlePrev}
                  disabled={currentIndex <= 0}
                  className="p-1 rounded text-slate-400 hover:text-white disabled:opacity-30 disabled:hover:text-slate-400 cursor-pointer"
                  title="Previous citation"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <span className="text-[11px] text-slate-400 px-1 font-mono">
                  {currentIndex + 1}/{allCitations.length}
                </span>
                <button
                  onClick={handleNext}
                  disabled={currentIndex >= allCitations.length - 1}
                  className="p-1 rounded text-slate-400 hover:text-white disabled:opacity-30 disabled:hover:text-slate-400 cursor-pointer"
                  title="Next citation"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            )}
            <button
              onClick={onClose}
              className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800/60 transition-colors cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Document Metadata Card */}
          <div className="p-4 rounded-xl bg-slate-900/60 border border-white/5 space-y-3">
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-lg bg-cyan-500/10 text-cyan-400 shrink-0">
                <FileText className="w-5 h-5" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs text-slate-400 font-medium">Document Title</p>
                <p className="text-sm font-semibold text-white truncate mt-0.5">
                  {citation.document_title}
                </p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2 pt-2 border-t border-slate-800/80">
              <div className="flex items-center gap-2">
                <Bookmark className="w-3.5 h-3.5 text-indigo-400" />
                <span className="text-xs text-slate-400">Page:</span>
                <span className="text-xs font-semibold text-slate-200">
                  {citation.page_number !== undefined && citation.page_number !== null
                    ? citation.page_number
                    : "N/A"}
                </span>
              </div>
              <div className="flex items-center gap-2 truncate">
                <Hash className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                <span className="text-xs text-slate-400 shrink-0">Section:</span>
                <span className="text-xs font-semibold text-slate-200 truncate">
                  {citation.section_heading || "General Content"}
                </span>
              </div>
            </div>
          </div>

          {/* Chunk Excerpt */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Source Document Excerpt
              </label>
              <button
                onClick={handleCopy}
                className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-cyan-300 transition-colors cursor-pointer"
              >
                {copied ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                    <span className="text-emerald-400">Copied</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5" />
                    <span>Copy Text</span>
                  </>
                )}
              </button>
            </div>
            <div className="p-4 rounded-xl bg-slate-950/80 border border-cyan-500/20 text-slate-200 text-sm leading-relaxed font-sans shadow-inner whitespace-pre-wrap">
              {citation.content_snippet || "No snippet content provided."}
            </div>
          </div>

          {/* Identifiers */}
          <div className="p-3 rounded-lg bg-slate-900/30 border border-white/5 space-y-1 text-[11px] font-mono text-slate-400">
            <div className="flex justify-between">
              <span>Chunk ID:</span>
              <span className="text-slate-300 truncate max-w-[240px]">
                {citation.chunk_id}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Document ID:</span>
              <span className="text-slate-300 truncate max-w-[240px]">
                {citation.document_id}
              </span>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-white/10 bg-slate-900/60 flex items-center justify-between text-xs text-slate-400">
          <span>Grounded Fact Inspection</span>
          <span className="text-emerald-400 font-medium">100% Deterministic Match</span>
        </div>
      </div>
    </div>
  );
}
