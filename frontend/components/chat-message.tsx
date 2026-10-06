"use client";

import React, { useState } from "react";
import { MessageItem, CitationItem } from "@/lib/api";
import { Sparkles, Copy, Check, RotateCw } from "lucide-react";

interface ChatMessageProps {
  message: MessageItem;
  onSelectCitation: (citation: CitationItem) => void;
}

export function ChatMessage({ message, onSelectCitation }: ChatMessageProps) {
  const isUser = message.role === "user";
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  // Parse text to render superscript citations [1] and bold **text**
  const renderFormattedLine = (line: string, citations: CitationItem[] = []) => {
    const isBullet = line.trim().startsWith("- ") || line.trim().startsWith("* ");
    const cleanLine = isBullet ? line.trim().slice(2) : line;

    // Split by citations or markdown bold markers
    const parts = cleanLine.split(/(\[Source\s+\d+\]|\[\d+\]|\*\*[^*]+\*\*)/gi);

    const formattedParts = parts.map((part, index) => {
      // Citation match [1] or [Source 1]
      const citMatch = part.match(/\[(?:Source\s+)?(\d+)\]/i);
      if (citMatch) {
        const sourceIndex = parseInt(citMatch[1], 10);
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
            className="text-xs text-indigo-400 bg-indigo-500/10 hover:bg-indigo-500/20 px-1.5 py-0.5 rounded mx-1 font-mono align-baseline cursor-pointer transition-colors"
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

      // Markdown bold **text**
      if (part.startsWith("**") && part.endsWith("**") && part.length >= 4) {
        return (
          <strong key={index} className="font-semibold text-zinc-100">
            {part.slice(2, -2)}
          </strong>
        );
      }

      return <span key={index}>{part}</span>;
    });

    if (isBullet) {
      return (
        <span className="flex items-start gap-2 my-1">
          <span className="text-zinc-500 select-none">•</span>
          <span className="flex-1">{formattedParts}</span>
        </span>
      );
    }

    return formattedParts;
  };

  // Render markdown paragraphs with clean spacing
  const renderParagraphs = (content: string, citations: CitationItem[] = []) => {
    const paragraphs = content.split(/\n\n+/);
    return (
      <div className="my-3 space-y-2.5 text-[16px] sm:text-[16.5px] text-zinc-200 font-normal leading-[1.75] tracking-[-0.01em]">
        {paragraphs.map((para, pIdx) => {
          const lines = para.split(/\n/);
          return (
            <p key={pIdx} className="leading-[1.75]">
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

  // 1. User Message (Clean Right-Aligned Bubble - Gemini/Claude Style)
  if (isUser) {
    return (
      <div className="my-6 flex justify-end">
        <div className="bg-[#242429] hover:bg-zinc-800 text-zinc-100 rounded-3xl px-5 py-3 text-[15px] font-normal leading-normal max-w-[70%] ml-auto shadow-none border-0 whitespace-pre-wrap transition-colors">
          {message.content}
        </div>
      </div>
    );
  }

  const hasCitations = message.citations && message.citations.length > 0;
  const sourcesCount = message.citations?.length || 0;
  const latencyMs = message.trace_data?.latency_ms?.total;
  const latencyLabel = latencyMs ? `${(latencyMs / 1000).toFixed(1)}s` : null;

  // 2. Assistant Message Typography & Minimalist Structure
  return (
    <div className="w-full max-w-2xl lg:max-w-3xl mx-auto my-6 text-zinc-100">
      {/* Seamless Flat Text Column */}
      <div className="min-w-0">
        {renderParagraphs(message.content, message.citations)}

        {/* 3. Minimal Utility Row (Gemini / Claude Style) */}
        <div className="mt-4 pt-2 flex items-center justify-between text-zinc-500">
          {/* Left Side: Micro action buttons */}
          <div className="flex items-center gap-1 -ml-1.5">
            <button
              type="button"
              onClick={handleCopy}
              className="text-zinc-500 hover:text-zinc-300 p-1.5 rounded-md hover:bg-zinc-900 transition-colors cursor-pointer"
              title="Copy answer"
              aria-label="Copy answer"
            >
              {copied ? (
                <Check className="w-3.5 h-3.5 text-emerald-400" />
              ) : (
                <Copy className="w-3.5 h-3.5" />
              )}
            </button>
            <button
              type="button"
              className="text-zinc-500 hover:text-zinc-300 p-1.5 rounded-md hover:bg-zinc-900 transition-colors cursor-pointer"
              title="Regenerate"
              aria-label="Regenerate"
            >
              <RotateCw className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Right Side: Discreet muted text link for sources/telemetry */}
          {(hasCitations || latencyLabel) && (
            <button
              type="button"
              onClick={() => {
                if (hasCitations && message.citations![0]) {
                  onSelectCitation(message.citations![0]);
                }
              }}
              className="text-xs text-zinc-500 hover:text-zinc-300 font-mono transition-colors cursor-pointer flex items-center gap-1.5"
              title="View cited sources & retrieval trace"
            >
              {hasCitations && (
                <span>
                  📚 {sourcesCount} {sourcesCount === 1 ? "Source" : "Sources"}
                </span>
              )}
              {hasCitations && latencyLabel && <span>•</span>}
              {latencyLabel && <span>⚡ {latencyLabel}</span>}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
