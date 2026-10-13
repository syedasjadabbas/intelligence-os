"use client";

import React from "react";
import { CitationItem } from "@/lib/api";
import {
  Bookmark,
  Check,
  ChevronLeft,
  ChevronRight,
  Copy,
  FileText,
  Hash,
  ShieldCheck,
} from "lucide-react";
import { Dialog } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Eyebrow } from "@/components/ui/surface";

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
    <Dialog
      variant="right"
      onClose={onClose}
      panelClassName="sm:max-w-lg lg:max-w-lg"
      title="Citation Inspector"
      icon={<FileText />}
      meta={
        <Badge tone="accent" mono>
          {citation.source_tag || `[Source ${citation.source_index}]`}
        </Badge>
      }
      description="Source passage used to ground this answer."
      footer={
        <div className="flex w-full items-center justify-between gap-3 text-xs text-fg-subtle">
          <span>Grounded Source Verification</span>
          <span className="flex items-center gap-1.5 font-medium text-success">
            <ShieldCheck className="size-3.5" />
            Deterministic Chunk Match
          </span>
        </div>
      }
      bodyClassName="space-y-6"
    >
      {allCitations.length > 1 && (
        <div className="flex items-center justify-between rounded-md border border-line bg-surface-2 px-2 py-1.5">
          <button
            type="button"
            onClick={handlePrev}
            disabled={currentIndex <= 0}
            className="flex items-center gap-1 rounded px-1.5 py-1 text-xs text-fg-muted transition-colors hover:bg-surface-3 hover:text-fg disabled:opacity-30 disabled:hover:bg-transparent cursor-pointer disabled:cursor-not-allowed"
            title="Previous citation"
          >
            <ChevronLeft className="size-3.5" />
            Previous
          </button>
          <span className="tabular font-mono text-[11px] text-fg-subtle">
            {currentIndex + 1} / {allCitations.length}
          </span>
          <button
            type="button"
            onClick={handleNext}
            disabled={currentIndex >= allCitations.length - 1}
            className="flex items-center gap-1 rounded px-1.5 py-1 text-xs text-fg-muted transition-colors hover:bg-surface-3 hover:text-fg disabled:opacity-30 disabled:hover:bg-transparent cursor-pointer disabled:cursor-not-allowed"
            title="Next citation"
          >
            Next
            <ChevronRight className="size-3.5" />
          </button>
        </div>
      )}

      {/* Document metadata */}
      <div className="space-y-3">
        <Eyebrow>Document</Eyebrow>
        <p className="text-[15px] font-medium leading-snug text-fg">{citation.document_title}</p>
        <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-md border border-line bg-line text-xs">
          <div className="flex items-center gap-2 bg-surface-2 px-3 py-2.5">
            <Bookmark className="size-3.5 shrink-0 text-fg-subtle" />
            <dt className="text-fg-subtle">Page</dt>
            <dd className="tabular ml-auto font-mono font-medium text-fg">
              {citation.page_number !== undefined && citation.page_number !== null
                ? citation.page_number
                : "N/A"}
            </dd>
          </div>
          <div className="flex min-w-0 items-center gap-2 bg-surface-2 px-3 py-2.5">
            <Hash className="size-3.5 shrink-0 text-fg-subtle" />
            <dt className="shrink-0 text-fg-subtle">Section</dt>
            <dd className="ml-auto truncate font-medium text-fg">
              {citation.section_heading || "General Content"}
            </dd>
          </div>
        </dl>
      </div>

      {/* Chunk excerpt */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <Eyebrow>Source excerpt</Eyebrow>
          <button
            type="button"
            onClick={handleCopy}
            className="flex items-center gap-1.5 rounded px-1.5 py-1 text-xs text-fg-subtle transition-colors hover:bg-surface-3 hover:text-fg cursor-pointer"
          >
            {copied ? (
              <>
                <Check className="size-3.5 text-success" />
                <span className="text-success">Copied</span>
              </>
            ) : (
              <>
                <Copy className="size-3.5" />
                <span>Copy Text</span>
              </>
            )}
          </button>
        </div>
        <blockquote className="whitespace-pre-wrap rounded-md border-l-2 border-accent/60 bg-surface-2 px-4 py-3.5 text-sm leading-relaxed text-fg/90">
          {citation.content_snippet || "No snippet content provided."}
        </blockquote>
      </div>

      {/* Identifiers */}
      <dl className="space-y-1.5 rounded-md border border-line px-3 py-2.5 font-mono text-[11px]">
        <div className="flex justify-between gap-4">
          <dt className="text-fg-subtle">Chunk ID</dt>
          <dd className="truncate text-fg-muted">{citation.chunk_id}</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-fg-subtle">Document ID</dt>
          <dd className="truncate text-fg-muted">{citation.document_id}</dd>
        </div>
      </dl>
    </Dialog>
  );
}
