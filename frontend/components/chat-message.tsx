"use client";

import React, { useState } from "react";
import { MessageItem, CitationItem } from "@/lib/api";
import { PipelineTrace } from "@/components/pipeline-trace";
import { cn } from "@/lib/utils";
import { Check, Copy, FileText } from "lucide-react";

interface ChatMessageProps {
  message: MessageItem;
  onSelectCitation?: (citation: CitationItem) => void;
}

/** Assistant identity mark shown beside generated answers. */
export function AssistantAvatar({ active = false }: { active?: boolean }) {
  return (
    <span
      className={cn(
        "relative mt-0.5 flex size-6.5 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-gradient-to-b from-[#222634] to-[#12141c] shadow-xs",
        active && "border-[#ff7a45]/40"
      )}
      aria-hidden
    >
      <span className="flex flex-col gap-[2px]">
        <span className={cn("h-[2px] w-2.5 rounded-full bg-[#ff7a45]", active && "animate-pulse")} />
        <span className={cn("h-[2px] w-[7px] rounded-full bg-[#ff7a45]/70", active && "animate-pulse [animation-delay:0.15s]")} />
        <span className={cn("h-[2px] w-1 rounded-full bg-[#ff7a45]/40", active && "animate-pulse [animation-delay:0.3s]")} />
      </span>
    </span>
  );
}

export function ChatMessage({ message, onSelectCitation }: ChatMessageProps) {
  const isUser = message.role === "user";
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Clean citations from text: strip [1], [2], [Source 1], [Sources: 1, 2], superscripts, etc.
  const stripCitations = (text: string) => {
    return text
      .replace(/\s*\[\^?\s*(?:Sources?[:\s]*)?\d+[^\]]*\]/gi, "")
      .replace(/[¹²³⁴⁵⁶⁷⁸⁹⁰]+/g, "")
      .replace(/\s{2,}/g, " ");
  };

  // Parse text to render clean sentences and markdown bold **text**
  const renderFormattedLine = (line: string) => {
    const isBullet = line.trim().startsWith("- ") || line.trim().startsWith("* ");
    const cleanLine = isBullet ? line.trim().slice(2) : line;
    const stripped = stripCitations(cleanLine).trimStart();

    // Split by markdown bold markers
    const parts = stripped.split(/(\*\*[^*]+\*\*)/g);

    const formattedParts = parts.map((part, index) => {
      // Markdown bold **text**
      if (part.startsWith("**") && part.endsWith("**") && part.length >= 4) {
        return (
          <strong key={index} className="font-semibold text-white">
            {part.slice(2, -2)}
          </strong>
        );
      }

      return <span key={index}>{part}</span>;
    });

    if (isBullet) {
      return (
        <span className="my-1 flex items-start gap-2.5">
          <span className="mt-[0.7em] size-1 shrink-0 rounded-full bg-[#8e95a5] select-none" aria-hidden />
          <span className="flex-1">{formattedParts}</span>
        </span>
      );
    }

    return formattedParts;
  };

  // Render markdown paragraphs with clean spacing
  const renderParagraphs = (content: string) => {
    const paragraphs = content.split(/\n\n+/);
    return (
      <div className="space-y-3.5 text-[14px] leading-[1.75] text-[#f3f4f6]/95 sm:text-[15px]">
        {paragraphs.map((para, pIdx) => {
          const lines = para.split(/\n/);
          return (
            <p key={pIdx}>
              {lines.map((line, lIdx) => (
                <React.Fragment key={lIdx}>
                  {renderFormattedLine(line)}
                  {lIdx < lines.length - 1 && <br />}
                </React.Fragment>
              ))}
            </p>
          );
        })}
      </div>
    );
  };

  // 1. User message — right-aligned bubble
  if (isUser) {
    return (
      <div className="group flex flex-col items-end animate-rise-in">
        <div className="max-w-[88%] whitespace-pre-wrap rounded-2xl rounded-br-md border border-white/[0.08] bg-gradient-to-b from-[#181b26] to-[#111319] px-4 py-2.5 text-[14px] leading-relaxed text-white sm:max-w-[75%] shadow-[inset_0_1px_0_0_rgba(255,255,255,0.06),0_6px_20px_rgba(0,0,0,0.4)]">
          {message.content}
        </div>
        <div className="mt-1 flex items-center gap-1.5 opacity-0 transition-opacity group-hover:opacity-100">
          <button
            type="button"
            onClick={handleCopy}
            className="flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] text-[#8e95a5] hover:text-white cursor-pointer"
            title="Copy question"
          >
            {copied ? <Check className="size-3 text-emerald-400" /> : <Copy className="size-3" />}
            <span>{copied ? "Copied" : "Copy"}</span>
          </button>
        </div>
      </div>
    );
  }

  // 2. Assistant message — avatar rail + reading-optimized body + citations + trace
  const hasCitations = message.citations && message.citations.length > 0;
  const hasTrace = message.trace_data && Object.keys(message.trace_data).length > 0;

  return (
    <div className="group flex gap-3.5 animate-rise-in">
      <AssistantAvatar />
      <div className="min-w-0 flex-1">
        {renderParagraphs(message.content)}

        {/* Citation Sources */}
        {hasCitations && (
          <div className="mt-4 flex flex-wrap items-center gap-1.5 border-t border-white/[0.07] pt-3">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-[#636a7e] mr-1">
              Sources
            </span>
            {message.citations.map((citation, idx) => (
              <button
                key={citation.chunk_id || idx}
                type="button"
                onClick={() => onSelectCitation?.(citation)}
                className="inline-flex items-center gap-1.5 rounded-lg border border-white/[0.08] bg-[#12141c] px-2.5 py-1 text-xs text-[#8e95a5] transition-all duration-150 hover:border-white/20 hover:text-white cursor-pointer group/chip shadow-xs"
                title={`Inspect citation: ${citation.document_title}${citation.page_number ? ` (page ${citation.page_number})` : ""}`}
              >
                <FileText className="size-3 text-[#636a7e] group-hover/chip:text-[#ff7a45]" />
                <span className="font-mono text-[11px] font-medium text-[#ff7a45]">[{citation.source_index}]</span>
                <span className="max-w-[150px] truncate font-medium text-[#d1d5db]">{citation.document_title}</span>
                {citation.page_number !== null && citation.page_number !== undefined && (
                  <span className="text-[10px] text-[#636a7e] font-mono">p.{citation.page_number}</span>
                )}
              </button>
            ))}
          </div>
        )}

        {/* Pipeline Telemetry Trace */}
        {hasTrace && (
          <div className="mt-3">
            <PipelineTrace trace={message.trace_data} />
          </div>
        )}

        {/* Message Actions */}
        <div className="mt-2.5 flex items-center gap-2 opacity-60 transition-opacity group-hover:opacity-100">
          <button
            type="button"
            onClick={handleCopy}
            className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] text-fg-subtle transition-colors hover:bg-surface-3 hover:text-fg cursor-pointer"
            title="Copy answer"
          >
            {copied ? <Check className="size-3 text-success" /> : <Copy className="size-3" />}
            <span>{copied ? "Copied" : "Copy"}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
