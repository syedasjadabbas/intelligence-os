"use client";

import React from "react";
import { MessageItem, CitationItem } from "@/lib/api";
import { cn } from "@/lib/utils";

interface ChatMessageProps {
  message: MessageItem;
  onSelectCitation?: (citation: CitationItem) => void;
}

/** Assistant identity mark shown beside generated answers. */
export function AssistantAvatar({ active = false }: { active?: boolean }) {
  return (
    <span
      className={cn(
        "relative mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-md border border-line-strong bg-surface-3",
        active && "border-accent/40"
      )}
      aria-hidden
    >
      <span className="flex flex-col gap-[2px]">
        <span className={cn("h-[2px] w-2.5 rounded-full bg-accent", active && "animate-pulse")} />
        <span className={cn("h-[2px] w-[7px] rounded-full bg-accent/70", active && "animate-pulse [animation-delay:0.15s]")} />
        <span className={cn("h-[2px] w-1 rounded-full bg-accent/40", active && "animate-pulse [animation-delay:0.3s]")} />
      </span>
    </span>
  );
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user";

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
          <strong key={index} className="font-semibold text-fg">
            {part.slice(2, -2)}
          </strong>
        );
      }

      return <span key={index}>{part}</span>;
    });

    if (isBullet) {
      return (
        <span className="my-1 flex items-start gap-2.5">
          <span className="mt-[0.7em] size-1 shrink-0 rounded-full bg-fg-subtle select-none" aria-hidden />
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
      <div className="space-y-3.5 text-[15px] leading-[1.75] text-fg/90 sm:text-base">
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
      <div className="flex justify-end animate-rise-in">
        <div className="max-w-[88%] whitespace-pre-wrap rounded-2xl rounded-br-md border border-line bg-surface-3 px-4 py-2.5 text-[15px] leading-relaxed text-fg sm:max-w-[75%]">
          {message.content}
        </div>
      </div>
    );
  }

  // 2. Assistant message — avatar rail + reading-optimized body
  return (
    <div className="flex gap-3 animate-rise-in">
      <AssistantAvatar />
      <div className="min-w-0 flex-1">{renderParagraphs(message.content)}</div>
    </div>
  );
}
