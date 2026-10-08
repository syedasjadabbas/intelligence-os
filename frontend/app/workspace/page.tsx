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
  ArrowDown,
  Layers,
  LogOut,
  Cpu,
  Building2,
  ShieldCheck,
  Sparkles,
  AlertCircle,
  Search,
  PanelLeft,
  BarChart3,
} from "lucide-react";

export default function ChatWorkspacePage() {
  const { user, org, logout } = useAuth();

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
    <div className="flex flex-col h-screen bg-[#090a0f] text-zinc-100 font-sans antialiased overflow-hidden selection:bg-indigo-500/25 selection:text-indigo-200">
      {/* ========================================================================= */}
      {/* HIGH-END ENTERPRISE TOP NAVBAR                                           */}
      {/* ========================================================================= */}
      <header className="h-14 w-full border-b border-zinc-800/80 bg-zinc-950/80 backdrop-blur-md px-4 sm:px-5 flex items-center justify-between z-30 select-none shrink-0">
        {/* Left Section: Sidebar Toggle + Organization & Workspace Identity */}
        <div className="flex items-center gap-2 sm:gap-3 min-w-0">
          {/* Sidebar Toggle Button */}
          <button
            type="button"
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            className="p-2 rounded-lg text-zinc-400 hover:text-zinc-100 hover:bg-zinc-900 border border-transparent hover:border-zinc-800 transition-colors cursor-pointer shrink-0"
            title={isSidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
            aria-label="Toggle sidebar"
          >
            <PanelLeft className="w-4 h-4" />
          </button>

          {/* Company/Tenant Badge */}
          <div className="flex items-center gap-2 px-2.5 py-1 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-100 font-medium text-xs shadow-xs shrink-0">
            <Building2 className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
            <span className="truncate max-w-[130px] font-medium">
              {org?.name || "Lonetex"}
            </span>
          </div>

          {/* Breadcrumb Divider */}
          <span className="text-zinc-600 text-xs shrink-0 hidden sm:inline">/</span>

          {/* Active View / Thread Title */}
          <span className="text-xs text-zinc-400 font-mono tracking-tight truncate max-w-[160px] sm:max-w-[200px] hidden sm:inline">
            {activeConv?.title || "Search & Synthesis"}
          </span>
        </div>

        {/* Center Section: Enterprise Quick Command Bar */}
        <div
          onClick={() => textareaRef.current?.focus()}
          className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-xl bg-zinc-900/60 border border-zinc-800/80 text-zinc-400 text-xs hover:border-zinc-700 hover:text-zinc-300 transition-colors w-64 lg:w-72 justify-between cursor-pointer shadow-xs group"
          title="Search documents & index (⌘K / Ctrl+K)"
        >
          <div className="flex items-center gap-2 min-w-0 truncate">
            <Search className="w-3.5 h-3.5 text-zinc-500 group-hover:text-zinc-400 shrink-0" />
            <span className="truncate">Search documents & index...</span>
          </div>
          <kbd className="text-[10px] bg-zinc-800 text-zinc-400 px-1.5 py-0.5 rounded border border-zinc-700 font-mono shrink-0">
            ⌘K
          </kbd>
        </div>

        {/* Right Section: Clean, Minimalist Enterprise Utilities */}
        <div className="flex items-center gap-3 shrink-0">
          {/* System Status (Subtle) */}
          <div className="hidden sm:flex items-center gap-2 text-xs text-zinc-400 font-normal mr-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
            <span>Operational</span>
          </div>

          {/* Document Management Link */}
          <Link
            href="/documents"
            className="text-xs font-medium text-zinc-300 hover:text-white px-3 py-1.5 rounded-md hover:bg-zinc-900 transition-colors"
          >
            Documents
          </Link>

          {/* Evaluations Link */}
          <Link
            href="/evaluations"
            className="text-xs font-medium text-zinc-300 hover:text-white px-3 py-1.5 rounded-md hover:bg-zinc-900 transition-colors flex items-center gap-1.5"
          >
            <BarChart3 className="w-3.5 h-3.5 text-indigo-400" />
            <span>Evaluations</span>
          </Link>

          {/* Vertical Divider */}
          <div className="h-4 w-px bg-zinc-850"></div>

          {/* User Profile Avatar & Dropdown */}
          <div className="flex items-center gap-2.5 pl-1 cursor-pointer">
            <div className="w-8 h-8 rounded-full bg-zinc-800 text-zinc-200 border border-zinc-750 flex items-center justify-center text-xs font-medium">
              {user?.email?.charAt(0).toUpperCase() || "U"}
            </div>
          </div>
        </div>
      </header>

      {/* ========================================================================= */}
      {/* LOWER WORKSPACE AREA: Fixed to h-[calc(100vh-3.5rem)]                    */}
      {/* ========================================================================= */}
      <div className="flex h-[calc(100vh-3.5rem)] overflow-hidden relative">
        {/* Mobile Backdrop Overlay */}
        {isSidebarOpen && (
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-xs z-35 md:hidden"
            onClick={() => setIsSidebarOpen(false)}
          />
        )}

        {/* ======================================================================= */}
        {/* SIDEBAR: Collapsible with Smooth Transition                             */}
        {/* ======================================================================= */}
        <aside
          className={`h-full flex flex-col shrink-0 bg-[#0c0d14] border-r border-zinc-800/80 transition-all duration-300 ease-in-out z-40 md:static fixed inset-y-0 left-0 top-14 md:top-auto ${
            isSidebarOpen
              ? "w-64 opacity-100 translate-x-0"
              : "w-0 opacity-0 -translate-x-full overflow-hidden pointer-events-none border-r-0"
          }`}
        >
          {/* New Thread Button */}
          <div className="p-3 border-b border-zinc-800/70 w-64">
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
          <div className="flex-1 overflow-y-auto px-2 py-2 space-y-0.5 w-64">
            <div className="px-2.5 py-1 text-[10px] font-medium text-zinc-500 uppercase tracking-wider">
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

          {/* Fixed User Identity at Bottom of Sidebar */}
          <div className="p-3 border-t border-zinc-800/70 bg-[#0c0d14] space-y-2 w-64">
            <div className="flex items-center justify-between px-1 text-xs">
              <div className="flex items-center gap-2.5 min-w-0 flex-1">
                <div className="w-8 h-8 rounded-full bg-zinc-800 border border-zinc-700 shrink-0 flex items-center justify-center font-bold text-xs text-zinc-200">
                  {user?.email ? user.email[0].toUpperCase() : "U"}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-xs text-zinc-300 font-medium truncate max-w-[140px]">
                    {user?.email || "user@lonetex.com"}
                  </p>
                  <p className="text-[10px] text-zinc-500 font-mono truncate max-w-[140px]">
                    org: {org?.slug || "lonetex"}
                  </p>
                </div>
              </div>

              <button
                onClick={logout}
                className="shrink-0 p-1.5 hover:bg-zinc-800 rounded-md text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer"
                title="Sign out"
              >
                <LogOut className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </aside>

        {/* ======================================================================= */}
        {/* MAIN CHAT VIEWPORT: Wide-Screen Centered Layout                        */}
        {/* ======================================================================= */}
        <div className="flex-1 flex flex-col h-full overflow-hidden bg-[#090a0f] relative min-w-0">
          {/* Centered Message Feed */}
          <div
            ref={chatScrollRef}
            onScroll={handleScroll}
            className="flex-1 flex flex-col items-center overflow-y-auto px-4 py-6 pb-28 w-full"
          >
            <div className="w-full max-w-2xl lg:max-w-3xl mx-auto space-y-6">
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
          </div>

          {/* ===================================================================== */}
          {/* SLEEK FLOATING PROMPT BAR: Auto-hides on Scroll Up                   */}
          {/* ===================================================================== */}
          <div
            className={`absolute bottom-5 inset-x-0 w-full max-w-2xl lg:max-w-3xl mx-auto px-4 z-30 transition-all duration-300 ease-out ${
              isAtBottom
                ? "translate-y-0 opacity-100 pointer-events-auto"
                : "translate-y-24 opacity-0 pointer-events-none"
            }`}
          >
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

          {/* ===================================================================== */}
          {/* SCROLL TO BOTTOM PILL: Appears when user scrolls up                   */}
          {/* ===================================================================== */}
          {!isAtBottom && (
            <div className="absolute bottom-5 inset-x-0 flex justify-center z-30 pointer-events-auto">
              <button
                type="button"
                onClick={() => {
                  chatScrollRef.current?.scrollTo({
                    top: chatScrollRef.current.scrollHeight,
                    behavior: "smooth",
                  });
                }}
                className="bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border border-zinc-700 rounded-full px-3.5 py-1.5 text-xs shadow-lg flex items-center gap-1.5 cursor-pointer animate-fade-in transition-colors"
              >
                <ArrowDown className="w-3.5 h-3.5" />
                <span>Scroll to bottom</span>
              </button>
            </div>
          )}
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
