"use client";

import React from "react";
import { MessageItem, CitationItem } from "@/lib/api";
import { PipelineTrace } from "@/components/pipeline-trace";
import { Cpu, User, Bookmark, ExternalLink } from "lucide-react";

interface ChatMessageProps {
  message: MessageItem;
  onSelectCitation: (citation: CitationItem) => void;
}

export function ChatMessage({ message, onSelectCitation }: ChatMessageProps) {
  const isUser = message.role === "user";

  // Parse text to render [Source X] as clickable buttons
  const renderFormattedContent = (content: string, citations: CitationItem[] = []) => {
    // Regex matching [Source X]
    const parts = content.split(/(\[Source\s+\d+\])/g);

    return parts.map((part, index) => {
      const match = part.match(/\[Source\s+(\d+)\]/i);
      if (match) {
        const sourceIndex = parseInt(match[1], 10);
        const matchingCitation = citations.find(
          (c) => c.source_index === sourceIndex
        );

        return (
          <button
            key={index}
            onClick={() => {
              if (matchingCitation) {
                onSelectCitation(matchingCitation);
              }
            }}
            className="inline-flex items-center gap-0.5 mx-1 px-2 py-0.5 rounded-md text-[11px] font-mono font-bold bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 hover:bg-cyan-500/30 hover:border-cyan-400 hover:text-cyan-200 transition-all shadow-sm cursor-pointer align-baseline"
            title={
              matchingCitation
                ? `${matchingCitation.document_title} (Page ${matchingCitation.page_number || "N/A"})`
                : `Inspect Source ${sourceIndex}`
            }
          >
            <Bookmark className="w-2.5 h-2.5 inline mr-0.5 text-cyan-400" />
            Source {sourceIndex}
          </button>
        );
      }
      return <span key={index}>{part}</span>;
    });
  };

  if (isUser) {
    return (
      <div className="flex justify-end gap-3 mb-6">
        <div className="max-w-[75%] rounded-2xl rounded-tr-sm bg-gradient-to-r from-cyan-600 to-indigo-600 text-white p-4 shadow-lg shadow-cyan-600/15">
          <p className="text-sm leading-relaxed whitespace-pre-wrap">
            {message.content}
          </p>
        </div>
        <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center shrink-0 text-slate-300">
          <User className="w-4 h-4" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start gap-3.5 mb-8">
      <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-cyan-500 to-indigo-600 flex items-center justify-center shrink-0 shadow-md shadow-cyan-500/20 text-white mt-1">
        <Cpu className="w-4 h-4" />
      </div>

      <div className="flex-1 max-w-[85%]">
        <div className="glass-card rounded-2xl rounded-tl-sm p-5 shadow-xl border border-white/10">
          {/* Answer Body */}
          <div className="text-sm leading-relaxed text-slate-200 font-sans whitespace-pre-wrap">
            {renderFormattedContent(message.content, message.citations)}
          </div>

          {/* Source Badges Row if citations exist */}
          {message.citations && message.citations.length > 0 && (
            <div className="mt-4 pt-3.5 border-t border-white/5 flex flex-wrap items-center gap-2">
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                Grounded Citations:
              </span>
              {message.citations.map((c, idx) => (
                <button
                  key={idx}
                  onClick={() => onSelectCitation(c)}
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs bg-slate-800/80 hover:bg-slate-800 border border-slate-700 text-slate-300 hover:text-white transition-all cursor-pointer font-medium"
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
                  <span className="font-semibold text-cyan-300">
                    [Source {c.source_index}]
                  </span>
                  <span className="text-slate-400 truncate max-w-[140px]">
                    {c.document_title}
                  </span>
                  {c.page_number && (
                    <span className="text-[10px] text-slate-500">
                      p.{c.page_number}
                    </span>
                  )}
                  <ExternalLink className="w-3 h-3 text-slate-400 ml-0.5" />
                </button>
              ))}
            </div>
          )}

          {/* Telemetry Trace */}
          {message.trace_data && (
            <PipelineTrace trace={message.trace_data} />
          )}
        </div>
      </div>
    </div>
  );
}
