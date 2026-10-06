"use client";

import React from "react";
import { MessageItem, CitationItem } from "@/lib/api";

interface ChatMessageProps {
  message: MessageItem;
  onSelectCitation?: (citation: CitationItem) => void;
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
  const renderParagraphs = (content: string) => {
    const paragraphs = content.split(/\n\n+/);
    return (
      <div className="my-3 space-y-2.5 text-[16px] sm:text-[16.5px] text-zinc-200 font-normal leading-[1.75] tracking-[-0.01em]">
        {paragraphs.map((para, pIdx) => {
          const lines = para.split(/\n/);
          return (
            <p key={pIdx} className="leading-[1.75]">
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

  // 1. User Message (Clean Right-Aligned Bubble - Gemini/Claude Style)
  if (isUser) {
    return (
      <div className="mt-10 mb-8 flex justify-end">
        <div className="bg-[#242429] hover:bg-zinc-800 text-zinc-100 rounded-3xl px-5 py-3 text-[15px] font-normal leading-normal max-w-[70%] ml-auto shadow-none border-0 whitespace-pre-wrap transition-colors">
          {message.content}
        </div>
      </div>
    );
  }

  // 2. Assistant Message Typography & Minimalist Clean Structure
  return (
    <div className="w-full max-w-2xl lg:max-w-3xl mx-auto mt-6 mb-12 text-zinc-100">
      <div className="min-w-0">
        {renderParagraphs(message.content)}
      </div>
    </div>
  );
}
