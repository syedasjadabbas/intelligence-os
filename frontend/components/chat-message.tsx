"use client";

import React from "react";
import { MessageItem, CitationItem } from "@/lib/api";
import { PipelineTrace } from "@/components/pipeline-trace";
import { Sparkles, ExternalLink, Bookmark } from "lucide-react";

interface ChatMessageProps {
  message: MessageItem;
  onSelectCitation: (citation: CitationItem) => void;
}

export function ChatMessage({ message, onSelectCitation }: ChatMessageProps) {
  const isUser = message.role === "user";

  // Parse text to render [Source X] as clickable footnote pills
  const renderFormattedContent = (content: string, citations: CitationItem[] = []) => {
    const parts = content.split(/(\[Source\s+\d+\]|\[\d+\])/gi);

    return parts.map((part, index) => {
      const match = part.match(/\[(?:Source\s+)?(\d+)\]/i);
      if (match) {
        const sourceIndex = parseInt(match[1], 10);
        const matchingCitation = citations.find(
          (c) => c.source_index === sourceIndex
        );

        const shortLabel = matchingCitation
          ? `${matchingCitation.document_title.replace(/\.[^/.]+$/, "").slice(0, 14)}${
              matchingCitation.page_number ? ` p.${matchingCitation.page_number}` : ""
            }`
          : `${sourceIndex}`;

        return (
          <button
            key={index}
            type="button"
            onClick={() => {
              if (matchingCitation) {
                onSelectCitation(matchingCitation);
              }
            }}
            className="inline-flex items-center gap-1 mx-1 px-2 py-0.5 rounded-full text-[11px] font-mono bg-zinc-900/90 hover:bg-zinc-800 text-zinc-300 hover:text-zinc-100 border border-zinc-800 hover:border-zinc-700 transition-all cursor-pointer align-baseline shadow-xs"
            title={
              matchingCitation
                ? `${matchingCitation.document_title} (Page ${matchingCitation.page_number || "N/A"})`
                : `Inspect Source ${sourceIndex}`
            }
          >
            <span className="text-indigo-400 font-semibold">[{sourceIndex}]</span>
            <span className="truncate max-w-[120px] text-zinc-400 font-sans">
              {shortLabel}
            </span>
          </button>
        );
      }
      return <span key={index}>{part}</span>;
    });
  };

  // User Message: Subtle elevated card aligned right
  if (isUser) {
    return (
      <div className="flex justify-end mb-6">
        <div className="bg-zinc-900/90 border border-zinc-800 text-zinc-100 rounded-2xl px-4 py-3 max-w-[80%] text-sm shadow-md leading-relaxed whitespace-pre-wrap tracking-tight">
          {message.content}
        </div>
      </div>
    );
  }

  // Assistant Response: Seamless flat layout with clean avatar icon & no bulky borders
  return (
    <div className="flex items-start gap-3.5 mb-8 text-zinc-100">
      {/* Clean Modern Assistant Icon */}
      <div className="w-7 h-7 rounded-lg bg-zinc-900 border border-zinc-800/90 flex items-center justify-center shrink-0 text-indigo-400 mt-1 shadow-xs">
        <Sparkles className="w-3.5 h-3.5" />
      </div>

      <div className="flex-1 min-w-0 max-w-full">
        {/* Answer Body - Seamless flat layout */}
        <div className="text-sm leading-relaxed text-zinc-200 tracking-tight whitespace-pre-wrap selection:bg-indigo-500/20">
          {renderFormattedContent(message.content, message.citations)}
        </div>

        {/* Micro Badges for Citations & Guardrails */}
        {message.citations && message.citations.length > 0 && (
          <div className="mt-3.5 flex flex-wrap items-center gap-2">
            {/* Status chip */}
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-zinc-900/90 border border-zinc-800/90 text-zinc-400 text-xs font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <span>
                Verified • {message.citations.length}{" "}
                {message.citations.length === 1 ? "source" : "sources"}
              </span>
            </span>

            {/* Footnote tags */}
            {message.citations.map((c, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => onSelectCitation(c)}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-zinc-900/70 hover:bg-zinc-800 text-zinc-300 hover:text-zinc-100 border border-zinc-800/80 hover:border-zinc-700 text-xs font-mono transition-all cursor-pointer group shadow-xs"
              >
                <span className="text-indigo-400 font-semibold">[{c.source_index}]</span>
                <span className="truncate max-w-[140px] text-zinc-300 font-sans">
                  {c.document_title}
                </span>
                {c.page_number && (
                  <span className="text-zinc-500 text-[10px]">p.{c.page_number}</span>
                )}
                <ExternalLink className="w-2.5 h-2.5 text-zinc-500 group-hover:text-zinc-300 ml-0.5" />
              </button>
            ))}
          </div>
        )}

        {/* Telemetry Drawer */}
        {message.trace_data && (
          <PipelineTrace trace={message.trace_data} />
        )}
      </div>
    </div>
  );
}
