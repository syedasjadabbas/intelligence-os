"use client";

import React from "react";
import { MessageItem, CitationItem } from "@/lib/api";
import { PipelineTrace } from "@/components/pipeline-trace";
import { Sparkles, FileText, User } from "lucide-react";

interface ChatMessageProps {
  message: MessageItem;
  onSelectCitation: (citation: CitationItem) => void;
}

export function ChatMessage({ message, onSelectCitation }: ChatMessageProps) {
  const isUser = message.role === "user";

  // Parse text to render simply [1], [2] as sleek superscript-style footnote chips
  const renderFormattedLine = (line: string, citations: CitationItem[] = []) => {
    // Regex matching [Source X] or [X]
    const parts = line.split(/(\[Source\s+\d+\]|\[\d+\])/gi);

    return parts.map((part, index) => {
      const match = part.match(/\[(?:Source\s+)?(\d+)\]/i);
      if (match) {
        const sourceIndex = parseInt(match[1], 10);
        const matchingCitation = citations.find(
          (c) => c.source_index === sourceIndex
        );

        return (
          <button
            key={index}
            type="button"
            onClick={() => {
              if (matchingCitation) {
                onSelectCitation(matchingCitation);
              }
            }}
            className="inline-flex items-center justify-center text-[11px] font-mono font-medium text-indigo-400 bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/30 rounded px-1.5 py-0.2 mx-1 cursor-pointer align-baseline transition-colors"
            title={
              matchingCitation
                ? `${matchingCitation.document_title}${
                    matchingCitation.page_number
                      ? ` (Page ${matchingCitation.page_number})`
                      : ""
                  }`
                : `Source [${sourceIndex}]`
            }
          >
            [{sourceIndex}]
          </button>
        );
      }
      return <span key={index}>{part}</span>;
    });
  };

  // Render markdown paragraphs with clean spacing (space-y-3)
  const renderParagraphs = (content: string, citations: CitationItem[] = []) => {
    const paragraphs = content.split(/\n\n+/);
    return (
      <div className="space-y-3 text-[15px] text-zinc-200 leading-relaxed tracking-normal font-sans antialiased selection:bg-indigo-500/20">
        {paragraphs.map((para, pIdx) => {
          const lines = para.split(/\n/);
          return (
            <p key={pIdx} className="leading-relaxed">
              {lines.map((line, lIdx) => (
                <React.Fragment key={lIdx}>
                  {renderFormattedLine(line, citations)}
                  {lIdx < lines.length - 1 && <br />}
                </React.Fragment>
              ))}
            </p>
          );
        })}
      </div>
    );
  };

  // User Message: Clear top separation, sender identity, and refined bubble
  if (isUser) {
    return (
      <div className="mt-6 mb-3 flex justify-end items-end gap-2.5">
        <div className="flex flex-col items-end max-w-[75%]">
          <span className="text-[11px] font-medium text-zinc-400 mb-1 text-right">
            You
          </span>
          <div className="bg-zinc-800/80 border border-zinc-700/50 text-zinc-100 rounded-2xl rounded-tr-sm px-4 py-2.5 text-[14px] shadow-sm leading-relaxed whitespace-pre-wrap font-sans">
            {message.content}
          </div>
        </div>
        <div className="w-7 h-7 rounded-full bg-zinc-800 border border-zinc-700/70 flex items-center justify-center text-[11px] font-medium text-zinc-300 shrink-0 mb-0.5 shadow-xs">
          <User className="w-3.5 h-3.5 text-zinc-400" />
        </div>
      </div>
    );
  }

  const hasCitations = message.citations && message.citations.length > 0;
  const hasTrace = Boolean(message.trace_data);

  // Assistant Response: Proper breathing room, top-left avatar alignment, and subtle bottom turn separator border
  return (
    <div className="mt-2 mb-6 flex items-start gap-3.5 max-w-3xl text-zinc-100 border-b border-zinc-800/40 pb-6">
      {/* Clean Assistant Avatar Icon aligned to top-left */}
      <div className="w-7 h-7 rounded-lg bg-zinc-900 border border-zinc-800/90 flex items-center justify-center shrink-0 text-indigo-400 mt-0.5 shadow-xs">
        <Sparkles className="w-3.5 h-3.5" />
      </div>

      <div className="flex-1 min-w-0">
        {/* Answer Body */}
        {renderParagraphs(message.content, message.citations)}

        {/* Modern Source / Footer Bar (Perplexity Style) */}
        {(hasCitations || hasTrace) && (
          <div className="mt-4 pt-3 border-t border-zinc-800/60 flex flex-wrap items-center justify-between gap-2.5">
            {/* Left side: Clean quiet source pill row showing micro cards */}
            {hasCitations && (
              <div className="flex flex-wrap items-center gap-1.5">
                {message.citations!.map((c, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => onSelectCitation(c)}
                    className="text-xs text-zinc-400 hover:text-zinc-200 bg-zinc-900 hover:bg-zinc-850 border border-zinc-800 hover:border-zinc-700 rounded-lg px-2.5 py-1 flex items-center gap-1.5 transition-all cursor-pointer group shadow-xs"
                    title={c.document_title}
                  >
                    <FileText className="w-3.5 h-3.5 text-zinc-500 group-hover:text-indigo-400 shrink-0" />
                    <span className="truncate max-w-[160px]">{c.document_title}</span>
                    {c.page_number && (
                      <span className="text-zinc-500 text-[11px] font-mono">
                        (p.{c.page_number})
                      </span>
                    )}
                  </button>
                ))}
              </div>
            )}

            {/* Right side / inline: Minimalist telemetry indicator */}
            {hasTrace && (
              <div className="flex items-center ml-auto">
                <PipelineTrace trace={message.trace_data!} className="mt-0" />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
