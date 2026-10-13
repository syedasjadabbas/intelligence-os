"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { useAuth } from "@/lib/auth-context";
import {
  api,
  ConversationItem,
  MessageItem,
  CitationItem,
} from "@/lib/api";
import { ChatMessage, AssistantAvatar } from "@/components/chat-message";
import { CitationDrawer } from "@/components/citation-drawer";
import { TopBar } from "@/components/app-shell";
import { BrandMark } from "@/components/brand";
import { Alert } from "@/components/ui/alert";
import { Kbd } from "@/components/ui/surface";
import { Skeleton } from "@/components/ui/spinner";
import { cn, formatRelativeTime, getErrorMessage } from "@/lib/utils";
import {
  ArrowDown,
  ArrowUp,
  ArrowUpRight,
  MessageSquare,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  ShieldCheck,
  SquarePen,
  Trash2,
} from "lucide-react";

/**
 * Chat workspace shared by `/` and `/workspace`. State, handlers and API calls
 * are carried over unchanged from the original page implementations.
 */
export function ChatWorkspace() {
  const { user, org } = useAuth();

  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [loadingConv, setLoadingConv] = useState(false);
  const [sending, setSending] = useState(false);
  const [inputQuery, setInputQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);

  // Citation Drawer state
  const [selectedCitation, setSelectedCitation] = useState<CitationItem | null>(
    null
  );
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [activeMessageCitations, setActiveMessageCitations] = useState<
    CitationItem[]
  >([]);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatScrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = () => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTo({
        top: chatScrollRef.current.scrollHeight,
        behavior: "smooth",
      });
    } else {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  };

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const { scrollTop, scrollHeight, clientHeight } = e.currentTarget;
    const atBottom = scrollHeight - scrollTop - clientHeight < 60;
    setIsAtBottom(atBottom);
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, sending]);

  // Global ⌘K / Ctrl+K shortcut to focus search input
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        textareaRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Auto-resize textarea height as query expands
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(
        textareaRef.current.scrollHeight,
        180
      )}px`;
    }
  }, [inputQuery]);

  // Load user's conversations
  const loadConversations = useCallback(async () => {
    try {
      const list = await api.listConversations();
      setConversations(list);
      if (!activeConvId && list.length > 0) {
        setActiveConvId(list[0].id);
      }
    } catch (err: unknown) {
      console.warn("Failed to load conversations from backend:", err);
    }
  }, [activeConvId]);

  useEffect(() => {
    if (user || api.getToken()) {
      loadConversations();
    }
  }, [user, loadConversations]);

  // Load message history when active conversation changes
  const loadMessages = useCallback(async (convId: string) => {
    if (!convId || convId.startsWith("local-")) {
      setMessages([]);
      return;
    }
    setLoadingConv(true);
    setError(null);
    try {
      const detail = await api.getConversation(convId);
      setMessages(detail.messages || []);
    } catch (err: unknown) {
      setError(getErrorMessage(err) || "Failed to load message history.");
      setMessages([]);
    } finally {
      setLoadingConv(false);
    }
  }, []);

  useEffect(() => {
    if (activeConvId) {
      loadMessages(activeConvId);
    } else {
      setMessages([]);
    }
  }, [activeConvId, loadMessages]);

  const handleNewChat = async () => {
    if (activeConvId && messages.length === 0) {
      setInputQuery("");
      textareaRef.current?.focus();
      return;
    }

    setError(null);
    try {
      const newConv = await api.createConversation("New Thread");
      setConversations((prev) => [newConv, ...prev.filter((c) => c.id !== newConv.id)]);
      setActiveConvId(newConv.id);
      setMessages([]);
      setInputQuery("");
      setTimeout(() => textareaRef.current?.focus(), 50);
    } catch (err: unknown) {
      console.warn("Backend conversation creation deferred, initializing local session:", err);
      const localId = "local-" + Date.now();
      const localConv: ConversationItem = {
        id: localId,
        title: "New Thread",
        org_id: org?.id || "default",
        user_id: user?.id || "default",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      setConversations((prev) => [localConv, ...prev]);
      setActiveConvId(localId);
      setMessages([]);
      setInputQuery("");
      setTimeout(() => textareaRef.current?.focus(), 50);
    }
  };

  const handleDeleteConversation = async (
    e: React.MouseEvent,
    convId: string
  ) => {
    e.stopPropagation();
    if (!window.confirm("Delete this conversation thread?")) return;

    try {
      if (!convId.startsWith("local-")) {
        await api.deleteConversation(convId);
      }
      setConversations((prev) => prev.filter((c) => c.id !== convId));
      if (activeConvId === convId) {
        setActiveConvId(null);
        setMessages([]);
      }
    } catch (err: unknown) {
      setError(getErrorMessage(err) || "Failed to delete conversation.");
    }
  };

  const handleSendMessage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const query = inputQuery.trim();
    if (!query || sending) return;

    setError(null);
    setSending(true);
    setInputQuery("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }

    let currentConvId = activeConvId;
    if (!currentConvId || currentConvId.startsWith("local-")) {
      try {
        const titleSnippet =
          query.slice(0, 32) + (query.length > 32 ? "..." : "");
        const created = await api.createConversation(titleSnippet);
        currentConvId = created.id;
        setActiveConvId(created.id);
        setConversations((prev) => [
          created,
          ...prev.filter((c) => c.id !== currentConvId && !c.id.startsWith("local-")),
        ]);
      } catch (err: unknown) {
        setError(getErrorMessage(err) || "Failed to start conversation. Please check backend connection.");
        setSending(false);
        setInputQuery(query);
        return;
      }
    }

    const tempUserMsg: MessageItem = {
      id: "temp-" + Date.now(),
      conversation_id: currentConvId,
      role: "user",
      content: query,
      citations: [],
      trace_data: {} as MessageItem["trace_data"],
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      const response = await api.sendMessage(currentConvId, query);

      const assistantMsg: MessageItem = {
        id: response.assistant_message_id,
        conversation_id: response.conversation_id,
        role: "assistant",
        content: response.answer,
        citations: response.citations,
        trace_data: response.trace_data,
        created_at: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, assistantMsg]);

      setConversations((prev) =>
        prev.map((c) =>
          c.id === currentConvId
            ? {
                ...c,
                title:
                  c.title === "New Thread" || c.title === "New Conversation"
                    ? query.slice(0, 35) + "..."
                    : c.title,
                updated_at: new Date().toISOString(),
              }
            : c
        )
      );
    } catch (err: unknown) {
      setError(getErrorMessage(err) || "Failed to generate answer.");
    } finally {
      setSending(false);
      textareaRef.current?.focus();
    }
  };

  const handleCitationClick = (
    citation: CitationItem,
    allMsgCitations: CitationItem[]
  ) => {
    setSelectedCitation(citation);
    setActiveMessageCitations(allMsgCitations);
    setDrawerOpen(true);
  };

  const promptSuggestions = [
    "What core material catalyzes cold fusion in the Arc Reactor?",
    "What fluid cools it during emergency shutdown?",
    "What is the radioactive half-life decay rate of Kryptonite?",
    "Summarize the autonomous drone avionics and swarm tactics.",
  ];

  const activeConv = conversations.find((c) => c.id === activeConvId);

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-canvas text-fg">
      <TopBar
        leading={
          <button
            type="button"
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            className="flex size-8 shrink-0 items-center justify-center rounded-md text-fg-subtle transition-colors hover:bg-surface-3 hover:text-fg cursor-pointer"
            title={isSidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
            aria-label="Toggle sidebar"
            aria-expanded={isSidebarOpen}
            aria-controls="chat-thread-sidebar"
          >
            {isSidebarOpen ? (
              <PanelLeftClose className="size-4" />
            ) : (
              <PanelLeftOpen className="size-4" />
            )}
          </button>
        }
        center={
          <button
            type="button"
            onClick={() => textareaRef.current?.focus()}
            className="hidden h-8 w-full max-w-xs items-center justify-between gap-2 rounded-md border border-line-strong bg-surface px-2.5 text-[13px] text-fg-subtle transition-colors hover:border-fg-faint hover:text-fg-muted lg:flex cursor-pointer"
            title="Search documents & index (⌘K / Ctrl+K)"
          >
            <span className="flex min-w-0 items-center gap-2">
              <Search className="size-3.5 shrink-0" />
              <span className="truncate">Ask your knowledge base…</span>
            </span>
            <span className="flex items-center gap-0.5">
              <Kbd>⌘</Kbd>
              <Kbd>K</Kbd>
            </span>
          </button>
        }
      />

      <div className="relative flex min-h-0 flex-1 overflow-hidden">
        {/* Mobile backdrop */}
        {isSidebarOpen && (
          <div
            className="fixed inset-0 top-12 z-30 bg-black/60 animate-fade-in md:hidden"
            onClick={() => setIsSidebarOpen(false)}
            aria-hidden
          />
        )}

        {/* Thread sidebar */}
        <aside
          id="chat-thread-sidebar"
          aria-label="Conversation threads"
          className={cn(
            "fixed bottom-0 left-0 top-12 z-40 flex shrink-0 flex-col border-r border-line bg-surface transition-[width,transform,opacity] duration-300 ease-[cubic-bezier(0.2,0.8,0.2,1)] md:static md:z-auto",
            isSidebarOpen
              ? "w-72 translate-x-0 opacity-100 md:w-64"
              : "pointer-events-none w-0 -translate-x-full overflow-hidden border-r-0 opacity-0"
          )}
          inert={!isSidebarOpen}
        >
          <div className="w-72 p-3 md:w-64">
            <button
              id="btn-new-conversation"
              type="button"
              onClick={handleNewChat}
              className="group flex h-9 w-full items-center gap-2 rounded-md border border-line-strong bg-surface-2 px-3 text-[13px] font-medium text-fg transition-colors hover:border-fg-faint hover:bg-surface-3 cursor-pointer"
            >
              <SquarePen className="size-4 text-fg-subtle transition-colors group-hover:text-accent" />
              New thread
            </button>
          </div>

          <div className="flex w-72 items-center justify-between px-4 pb-1.5 pt-1 md:w-64">
            <span className="text-[11px] font-medium uppercase tracking-[0.08em] text-fg-subtle">
              Recent threads
            </span>
            {conversations.length > 0 && (
              <span className="tabular font-mono text-[11px] text-fg-faint">
                {conversations.length}
              </span>
            )}
          </div>

          <nav className="min-h-0 w-72 flex-1 overflow-y-auto px-2 pb-3 md:w-64">
            {conversations.length === 0 ? (
              <div className="mx-1 mt-1 rounded-md border border-dashed border-line-strong px-3 py-6 text-center">
                <MessageSquare className="mx-auto mb-2 size-4 text-fg-faint" />
                <p className="text-xs text-fg-subtle">No conversations yet.</p>
              </div>
            ) : (
              <ul className="space-y-px">
                {conversations.map((conv) => {
                  const isActive = conv.id === activeConvId;
                  return (
                    <li key={conv.id} className="group relative">
                      <button
                        type="button"
                        onClick={() => setActiveConvId(conv.id)}
                        aria-current={isActive ? "true" : undefined}
                        className={cn(
                          "relative flex w-full items-center gap-2 rounded-md py-2 pl-3 pr-9 text-left text-[13px] transition-colors cursor-pointer",
                          isActive
                            ? "bg-surface-3 text-fg"
                            : "text-fg-muted hover:bg-surface-2 hover:text-fg"
                        )}
                      >
                        {isActive && (
                          <span className="absolute inset-y-2 left-0 w-0.5 rounded-full bg-accent" aria-hidden />
                        )}
                        <span className="min-w-0 flex-1 truncate">
                          {conv.title || "Untitled Session"}
                        </span>
                        <span className="tabular shrink-0 font-mono text-[10px] text-fg-faint transition-opacity group-hover:opacity-0 group-focus-within:opacity-0">
                          {formatRelativeTime(conv.updated_at || conv.created_at)}
                        </span>
                      </button>
                      <button
                        type="button"
                        onClick={(e) => handleDeleteConversation(e, conv.id)}
                        className="absolute right-1.5 top-1/2 flex size-6 -translate-y-1/2 items-center justify-center rounded text-fg-subtle opacity-0 transition-[opacity,color,background-color] hover:bg-danger/12 hover:text-danger focus-visible:opacity-100 group-hover:opacity-100 group-focus-within:opacity-100 cursor-pointer"
                        title="Delete thread"
                        aria-label={`Delete thread ${conv.title || "Untitled Session"}`}
                      >
                        <Trash2 className="size-3.5" />
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </nav>

          <div className="w-72 border-t border-line px-4 py-3 md:w-64">
            <div className="flex items-center gap-2 text-xs text-fg-subtle">
              <ShieldCheck className="size-3.5 shrink-0 text-success" />
              <span className="truncate">
                Isolated tenant
                {org?.slug ? (
                  <span className="font-mono text-fg-faint"> · {org.slug}</span>
                ) : null}
              </span>
            </div>
          </div>
        </aside>

        {/* Conversation viewport */}
        <div className="relative flex min-w-0 flex-1 flex-col overflow-hidden">
          <div
            ref={chatScrollRef}
            onScroll={handleScroll}
            className="flex w-full flex-1 flex-col items-center overflow-y-auto px-4 pb-40 pt-6 sm:px-6"
          >
            <div className="flex w-full max-w-3xl flex-1 flex-col">
              {activeConv && messages.length > 0 && (
                <div className="mb-6 hidden items-center gap-2 text-xs text-fg-subtle sm:flex">
                  <MessageSquare className="size-3.5" />
                  <span className="truncate">{activeConv.title || "Untitled Session"}</span>
                </div>
              )}

              {error && (
                <Alert tone="danger" className="mb-6" onDismiss={() => setError(null)}>
                  {error}
                </Alert>
              )}

              {/* Loading history */}
              {loadingConv && messages.length === 0 && (
                <div className="space-y-8 pt-2" role="status" aria-label="Loading conversation">
                  <div className="flex justify-end">
                    <Skeleton className="h-10 w-2/5 rounded-2xl" />
                  </div>
                  <div className="flex gap-3">
                    <Skeleton className="size-6 shrink-0 rounded-md" />
                    <div className="flex-1 space-y-2.5">
                      <Skeleton className="h-3.5 w-11/12" />
                      <Skeleton className="h-3.5 w-4/5" />
                      <Skeleton className="h-3.5 w-3/5" />
                    </div>
                  </div>
                </div>
              )}

              {/* Welcome / empty conversation */}
              {messages.length === 0 && !loadingConv && (
                <div className="my-auto flex flex-col items-center py-10 text-center animate-rise-in">
                  <BrandMark className="mb-6 size-10" />
                  <h1 className="text-2xl font-semibold tracking-tight text-fg text-balance sm:text-[28px]">
                    Ask anything across your organization
                  </h1>
                  <p className="mt-3 max-w-md text-sm leading-relaxed text-fg-subtle">
                    Every response is grounded in your indexed documents with verified page
                    citations. When the sources don&apos;t support an answer, it says so.
                  </p>

                  <div className="mt-10 grid w-full max-w-2xl grid-cols-1 gap-2 sm:grid-cols-2">
                    {promptSuggestions.map((prompt, idx) => (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => {
                          setInputQuery(prompt);
                          textareaRef.current?.focus();
                        }}
                        className="group flex items-start justify-between gap-3 rounded-lg border border-line bg-surface px-3.5 py-3 text-left text-[13px] leading-relaxed text-fg-muted transition-colors hover:border-line-strong hover:bg-surface-2 hover:text-fg cursor-pointer"
                      >
                        <span className="line-clamp-2">{prompt}</span>
                        <ArrowUpRight className="mt-0.5 size-3.5 shrink-0 text-fg-faint transition-colors group-hover:text-accent" />
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Messages */}
              <div className="space-y-8">
                {messages.map((msg) => (
                  <ChatMessage
                    key={msg.id}
                    message={msg}
                    onSelectCitation={(citation) =>
                      handleCitationClick(citation, msg.citations || [])
                    }
                  />
                ))}

                {/* Generating indicator */}
                {sending && (
                  <div className="flex items-start gap-3 animate-rise-in" role="status">
                    <AssistantAvatar active />
                    <div className="flex items-center gap-2 pt-0.5 text-[13px] text-fg-subtle">
                      <span>Executing hybrid retrieval &amp; synthesis</span>
                      <span className="flex gap-1" aria-hidden>
                        <span className="size-1 rounded-full bg-fg-subtle animate-pulse" />
                        <span className="size-1 rounded-full bg-fg-subtle animate-pulse [animation-delay:0.2s]" />
                        <span className="size-1 rounded-full bg-fg-subtle animate-pulse [animation-delay:0.4s]" />
                      </span>
                    </div>
                  </div>
                )}
              </div>

              <div ref={messagesEndRef} />
            </div>
          </div>

          {/* Composer — hides while reading back through history */}
          <div
            className={cn(
              "pointer-events-none absolute inset-x-0 bottom-0 z-20 transition-[transform,opacity] duration-300 ease-out",
              isAtBottom ? "translate-y-0 opacity-100" : "translate-y-24 opacity-0"
            )}
          >
            <div className="h-10 bg-gradient-to-t from-canvas to-transparent" />
            <div className="bg-canvas px-4 pb-4 sm:px-6 sm:pb-5">
              <form
                onSubmit={handleSendMessage}
                className={cn(
                  "mx-auto w-full max-w-3xl rounded-xl border border-line-strong bg-surface shadow-pop transition-[border-color,box-shadow] focus-within:border-fg-faint focus-within:ring-3 focus-within:ring-accent/10",
                  isAtBottom ? "pointer-events-auto" : "pointer-events-none"
                )}
              >
                <label htmlFor="chat-query-input" className="sr-only">
                  Ask a question
                </label>
                <textarea
                  id="chat-query-input"
                  ref={textareaRef}
                  rows={1}
                  value={inputQuery}
                  onChange={(e) => setInputQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSendMessage();
                    }
                  }}
                  placeholder="Ask about corporate policies, specs, or contracts..."
                  className="block max-h-44 w-full resize-none bg-transparent px-4 pt-3.5 pb-1 text-[15px] leading-6 text-fg placeholder:text-fg-faint focus:outline-none"
                />

                <div className="flex items-center justify-between gap-3 px-3 pb-2.5 pt-1">
                  <div className="hidden items-center gap-1.5 text-[11px] text-fg-faint sm:flex">
                    <Kbd>Enter</Kbd>
                    <span>to send</span>
                    <span className="mx-1 text-line-strong">·</span>
                    <Kbd>Shift</Kbd>
                    <Kbd>Enter</Kbd>
                    <span>for newline</span>
                  </div>
                  <span className="flex items-center gap-1.5 text-[11px] text-fg-subtle sm:hidden">
                    <ShieldCheck className="size-3.5 text-success" />
                    Isolated Tenant
                  </span>

                  <div className="flex items-center gap-3">
                    <span className="hidden items-center gap-1.5 text-[11px] text-fg-subtle sm:flex">
                      <ShieldCheck className="size-3.5 text-success" />
                      Isolated Tenant
                    </span>
                    <button
                      id="btn-send-message"
                      type="submit"
                      disabled={!inputQuery.trim() || sending}
                      className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-fg text-canvas transition-[background-color,opacity,transform] hover:bg-white active:translate-y-px disabled:opacity-25 disabled:hover:bg-fg cursor-pointer disabled:cursor-not-allowed"
                      title="Send query"
                      aria-label="Send query"
                    >
                      <ArrowUp className="size-4 stroke-[2.5]" />
                    </button>
                  </div>
                </div>
              </form>
            </div>
          </div>

          {/* Scroll to latest */}
          {!isAtBottom && (
            <div className="pointer-events-none absolute inset-x-0 bottom-6 z-20 flex justify-center">
              <button
                type="button"
                onClick={() => {
                  chatScrollRef.current?.scrollTo({
                    top: chatScrollRef.current.scrollHeight,
                    behavior: "smooth",
                  });
                }}
                className="pointer-events-auto flex h-8 items-center gap-1.5 rounded-full border border-line-strong bg-surface-3 px-3.5 text-xs font-medium text-fg-muted shadow-pop transition-colors animate-rise-in hover:bg-surface-4 hover:text-fg cursor-pointer"
              >
                <ArrowDown className="size-3.5" />
                Scroll to bottom
              </button>
            </div>
          )}
        </div>
      </div>

      <CitationDrawer
        isOpen={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        citation={selectedCitation}
        allCitations={activeMessageCitations}
        onSelectCitation={(newCitation) => setSelectedCitation(newCitation)}
      />
    </div>
  );
}
