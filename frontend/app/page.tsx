"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import {
  api,
  ConversationItem,
  MessageItem,
  CitationItem,
} from "@/lib/api";
import { ChatMessage } from "@/components/chat-message";
import { CitationDrawer } from "@/components/citation-drawer";
import {
  Plus,
  MessageSquare,
  Trash2,
  ArrowUp,
  Layers,
  LogOut,
  Cpu,
  Building2,
  ShieldCheck,
  Sparkles,
  Bot,
  AlertCircle,
  Command,
} from "lucide-react";

export default function ChatWorkspacePage() {
  const { user, org, logout } = useAuth();

  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [loadingConv, setLoadingConv] = useState(false);
  const [sending, setSending] = useState(false);
  const [inputQuery, setInputQuery] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Citation Drawer state
  const [selectedCitation, setSelectedCitation] = useState<CitationItem | null>(
    null
  );
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [activeMessageCitations, setActiveMessageCitations] = useState<
    CitationItem[]
  >([]);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, sending]);

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
    } catch (err: any) {
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
    } catch (err: any) {
      setError(err.message || "Failed to load message history.");
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
    } catch (err: any) {
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
    } catch (err: any) {
      setError(err.message || "Failed to delete conversation.");
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
      } catch (err: any) {
        setError(err.message || "Failed to start conversation. Please check backend connection.");
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
      trace_data: {} as any,
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
    } catch (err: any) {
      setError(err.message || "Failed to generate answer.");
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
    <div className="flex h-screen bg-[#090a0f] text-zinc-100 font-sans antialiased overflow-hidden selection:bg-indigo-500/25 selection:text-indigo-200">
      {/* ========================================================================= */}
      {/* SIDEBAR: Linear / Perplexity Minimalist Hierarchy                        */}
      {/* ========================================================================= */}
      <aside className="w-64 lg:w-72 bg-[#0c0d14] border-r border-zinc-800/70 flex flex-col shrink-0">
        {/* Brand Header */}
        <div className="p-4 border-b border-zinc-800/70 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-zinc-900 border border-zinc-800 flex items-center justify-center text-indigo-400 shadow-xs">
              <Cpu className="w-3.5 h-3.5" />
            </div>
            <div>
              <h2 className="font-semibold text-xs tracking-tight text-zinc-100 flex items-center gap-1">
                Intelligence <span className="text-zinc-500 font-normal">OS</span>
              </h2>
              <p className="text-[10px] text-zinc-500 font-mono tracking-tight">Enterprise RAG</p>
            </div>
          </div>
        </div>

        {/* New Thread CTA */}
        <div className="p-3">
          <button
            id="btn-new-conversation"
            type="button"
            onClick={handleNewChat}
            className="w-full py-2 px-3 rounded-xl bg-zinc-900 hover:bg-zinc-800/80 text-zinc-200 hover:text-white border border-zinc-800 hover:border-zinc-700 font-medium text-xs flex items-center justify-between transition-all duration-150 cursor-pointer shadow-xs group"
          >
            <div className="flex items-center gap-2">
              <Plus className="w-3.5 h-3.5 text-zinc-400 group-hover:text-zinc-200" />
              <span>New Thread</span>
            </div>
            <span className="text-[10px] font-mono text-zinc-500 group-hover:text-zinc-400 border border-zinc-800 px-1.5 py-0.2 rounded bg-zinc-950/60">
              ⌘N
            </span>
          </button>
        </div>

        {/* Conversation List */}
        <div className="flex-1 overflow-y-auto px-2 space-y-0.5">
          <div className="px-2.5 py-1.5 text-[10px] font-medium text-zinc-500 uppercase tracking-wider">
            Recent Threads
          </div>

          {conversations.length === 0 ? (
            <div className="p-4 text-center text-xs text-zinc-500">
              No conversations yet.
            </div>
          ) : (
            conversations.map((conv) => {
              const isActive = conv.id === activeConvId;
              return (
                <div
                  key={conv.id}
                  onClick={() => setActiveConvId(conv.id)}
                  className={`group relative flex items-center justify-between py-2 px-2.5 rounded-lg text-xs cursor-pointer transition-all duration-150 ${
                    isActive
                      ? "bg-zinc-900 text-zinc-100 border-l-2 border-indigo-500 shadow-xs font-medium"
                      : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/40 border-l-2 border-transparent"
                  }`}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <MessageSquare
                      className={`w-3.5 h-3.5 shrink-0 ${
                        isActive ? "text-indigo-400" : "text-zinc-500"
                      }`}
                    />
                    <span className="truncate max-w-[160px] tracking-tight">
                      {conv.title || "Untitled Session"}
                    </span>
                  </div>

                  <button
                    onClick={(e) => handleDeleteConversation(e, conv.id)}
                    className="opacity-0 group-hover:opacity-100 p-1 hover:text-rose-400 text-zinc-500 transition-opacity cursor-pointer"
                    title="Delete thread"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              );
            })
          )}
        </div>

        {/* Refined User & Tenant Pill at Bottom Left */}
        <div className="p-3 border-t border-zinc-800/70 bg-[#0c0d14] space-y-2">
          {org && (
            <div className="px-2.5 py-1.5 rounded-lg bg-zinc-900/60 border border-zinc-800/60 text-xs flex items-center gap-2">
              <Building2 className="w-3.5 h-3.5 text-zinc-500 shrink-0" />
              <div className="min-w-0 flex-1">
                <p className="font-medium text-zinc-200 truncate text-[11px] tracking-tight">
                  {org.name}
                </p>
                <p className="text-[10px] text-zinc-500 font-mono truncate">
                  {org.slug}
                </p>
              </div>
            </div>
          )}

          <div className="flex items-center justify-between px-1 text-xs">
            <div className="flex items-center gap-2 min-w-0 flex-1">
              <div className="w-6 h-6 rounded-full bg-zinc-800 border border-zinc-700/80 flex items-center justify-center text-[10px] font-semibold text-zinc-300 shrink-0">
                {user?.email ? user.email[0].toUpperCase() : "U"}
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-[11px] font-medium text-zinc-300 truncate">
                  {user?.email}
                </p>
                <span className="text-[9px] px-1 py-0.2 rounded bg-zinc-900 border border-zinc-800 text-zinc-500 font-mono uppercase">
                  {user?.role}
                </span>
              </div>
            </div>

            <button
              onClick={logout}
              className="p-1 rounded-md text-zinc-500 hover:text-rose-400 hover:bg-zinc-900 transition-colors cursor-pointer"
              title="Sign out"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </div>

          <Link
            href="/documents"
            className="w-full mt-1 py-1.5 px-2.5 rounded-lg bg-zinc-900/80 hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 border border-zinc-800/80 text-[11px] font-medium flex items-center justify-center gap-2 transition-all cursor-pointer"
          >
            <Layers className="w-3.5 h-3.5 text-zinc-500" />
            <span>Document Admin</span>
          </Link>
        </div>
      </aside>

      {/* ========================================================================= */}
      {/* MAIN CHAT VIEWPORT                                                       */}
      {/* ========================================================================= */}
      <div className="flex-1 flex flex-col h-full overflow-hidden bg-[#090a0f] relative">
        {/* Top Navbar Header */}
        <header className="px-6 py-3 border-b border-zinc-800/70 bg-[#090a0f]/80 backdrop-blur-md flex items-center justify-between z-20">
          <div className="flex items-center gap-2 text-xs">
            <span className="text-zinc-500">Intelligence OS</span>
            <span className="text-zinc-700">/</span>
            <span className="text-zinc-200 font-medium truncate max-w-sm">
              {activeConv?.title || "Search & Synthesis"}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-zinc-900/90 border border-zinc-800 text-[11px] text-zinc-400 font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              <span>Grounded Guardrails</span>
            </div>
          </div>
        </header>

        {/* Message Stream */}
        <div className="flex-1 overflow-y-auto px-6 pt-6 pb-28 max-w-3xl w-full mx-auto space-y-4">
          {error && (
            <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/25 text-rose-300 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
              <span>{error}</span>
            </div>
          )}

          {/* Welcome Screen / Empty Conversation */}
          {messages.length === 0 && !loadingConv && (
            <div className="h-full flex flex-col items-center justify-center text-center p-8 space-y-6 my-auto">
              <div className="w-10 h-10 rounded-2xl bg-zinc-900 border border-zinc-800 flex items-center justify-center text-indigo-400 shadow-md">
                <Sparkles className="w-5 h-5" />
              </div>

              <div className="max-w-md space-y-2">
                <h3 className="text-lg font-semibold text-zinc-100 tracking-tight">
                  Ask anything across your organization
                </h3>
                <p className="text-xs text-zinc-400 leading-relaxed tracking-tight">
                  Every response is grounded in factual vectors with verified page citations.
                  Strict refusal guardrails eliminate hallucinations.
                </p>
              </div>

              {/* Prompt Suggestions */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-xl pt-2">
                {promptSuggestions.map((prompt, idx) => (
                  <button
                    key={idx}
                    onClick={() => {
                      setInputQuery(prompt);
                      textareaRef.current?.focus();
                    }}
                    className="p-3 rounded-xl bg-zinc-900/50 hover:bg-zinc-900 border border-zinc-800/70 hover:border-zinc-700 text-left text-xs text-zinc-300 hover:text-zinc-100 transition-all duration-150 cursor-pointer shadow-xs group"
                  >
                    <div className="flex items-center justify-between">
                      <span className="line-clamp-2 leading-relaxed">{prompt}</span>
                      <span className="text-zinc-600 group-hover:text-zinc-300 text-xs ml-2">
                        →
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Render Messages */}
          {messages.map((msg) => (
            <ChatMessage
              key={msg.id}
              message={msg}
              onSelectCitation={(citation) =>
                handleCitationClick(citation, msg.citations || [])
              }
            />
          ))}

          {/* Generating Indicator */}
          {sending && (
            <div className="flex items-center gap-3 py-2 text-xs text-zinc-400 font-mono animate-in fade-in duration-200">
              <div className="w-6 h-6 rounded-lg bg-zinc-900 border border-zinc-800 flex items-center justify-center text-indigo-400">
                <Cpu className="w-3.5 h-3.5 animate-pulse" />
              </div>
              <div className="flex items-center gap-2">
                <span>Executing hybrid retrieval & synthesis</span>
                <span className="flex gap-1">
                  <span className="w-1 h-1 rounded-full bg-zinc-500 animate-pulse" />
                  <span className="w-1 h-1 rounded-full bg-zinc-500 animate-pulse [animation-delay:0.2s]" />
                  <span className="w-1 h-1 rounded-full bg-zinc-500 animate-pulse [animation-delay:0.4s]" />
                </span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* ========================================================================= */}
        {/* SLEEK FLOATING PROMPT BAR                                                */}
        {/* ========================================================================= */}
        <div className="absolute bottom-5 inset-x-0 px-4 max-w-3xl mx-auto z-30 pointer-events-none">
          <form
            onSubmit={handleSendMessage}
            className="pointer-events-auto bg-zinc-900/80 backdrop-blur-md border border-zinc-800/90 rounded-2xl p-2 shadow-2xl transition-all focus-within:border-zinc-700/90 focus-within:ring-1 focus-within:ring-zinc-700/50"
          >
            <div className="flex items-end gap-2 px-2 pt-1">
              {/* Auto-growing clean textarea without heavy outline */}
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
                className="w-full bg-transparent text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none resize-none leading-relaxed max-h-44 py-1"
              />

              {/* Clean circular action button for Send */}
              <button
                id="btn-send-message"
                type="submit"
                disabled={!inputQuery.trim() || sending}
                className="w-8 h-8 rounded-full bg-indigo-600 hover:bg-indigo-500 text-white flex items-center justify-center shrink-0 transition-all disabled:opacity-25 disabled:hover:bg-indigo-600 shadow-md cursor-pointer mb-0.5"
                title="Send query"
              >
                <ArrowUp className="w-4 h-4 stroke-[2.5]" />
              </button>
            </div>

            {/* Discreet Bottom Bar with Hotkey Badge */}
            <div className="flex items-center justify-between text-[11px] text-zinc-500 px-2 pt-1 pb-0.5 border-t border-zinc-800/40 mt-1">
              <span className="flex items-center gap-1.5 font-mono text-[10px]">
                <span className="px-1.5 py-0.2 rounded bg-zinc-800/70 border border-zinc-700/60 text-zinc-400">
                  Enter
                </span>
                <span>to send</span>
                <span className="text-zinc-600">•</span>
                <span className="px-1.5 py-0.2 rounded bg-zinc-800/70 border border-zinc-700/60 text-zinc-400">
                  Shift+Enter
                </span>
                <span>for newline</span>
              </span>

              <span className="flex items-center gap-1 text-zinc-400 text-[10px] font-medium">
                <ShieldCheck className="w-3 h-3 text-emerald-500" />
                <span>Isolated Tenant</span>
              </span>
            </div>
          </form>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* CITATION DRAWER                                                          */}
      {/* ========================================================================= */}
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
