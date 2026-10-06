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
  Send,
  Layers,
  LogOut,
  Cpu,
  Building2,
  Shield,
  Sparkles,
  Bot,
  AlertCircle,
  Home,
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

  // Load user's conversations
  const loadConversations = useCallback(async () => {
    try {
      const list = await api.listConversations();
      setConversations(list);
      // Auto-select latest conversation if none selected
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
      const newConv = await api.createConversation("New Conversation");
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
        title: "New Conversation",
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

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    const query = inputQuery.trim();
    if (!query || sending) return;

    setError(null);
    setSending(true);
    setInputQuery("");

    let currentConvId = activeConvId;
    if (!currentConvId || currentConvId.startsWith("local-")) {
      try {
        const titleSnippet =
          query.slice(0, 30) + (query.length > 30 ? "..." : "");
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
                  c.title === "New Conversation"
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
    "What is the radioactive half-life decay rate of Kryptonite in Gotham City?",
    "Describe the autonomous drone avionics and swarm flight tactics.",
  ];

  return (
    <div className="flex h-screen bg-[#090d16] overflow-hidden text-slate-100">
      {/* LEFT SIDEBAR: Conversation History & Tenant Controls */}
      <aside className="w-72 bg-[#0d131f] border-r border-slate-800 flex flex-col shrink-0">
        <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/40">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-slate-800 border border-slate-700/80 flex items-center justify-center text-slate-200">
              <Cpu className="w-4 h-4 text-slate-300" />
            </div>
            <div>
              <h2 className="font-semibold text-sm tracking-tight text-slate-100">
                Intelligence <span className="text-slate-400 font-normal">OS</span>
              </h2>
              <p className="text-[10px] text-slate-400 font-mono">Enterprise RAG</p>
            </div>
          </div>
          <Link
            href="/"
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            title="Return to Landing Page"
          >
            <Home className="w-4 h-4" />
          </Link>
        </div>

        <div className="p-3">
          <button
            id="btn-new-conversation"
            type="button"
            onClick={handleNewChat}
            className="w-full py-2 px-3 rounded-lg bg-white/10 hover:bg-white/15 text-white border border-white/10 font-medium text-sm flex items-center justify-center gap-2 transition-all cursor-pointer shadow-sm"
          >
            <Plus className="w-4 h-4 text-slate-300" />
            <span>New Conversation</span>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-2 space-y-1">
          <div className="px-2 py-1 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
            Conversations
          </div>

          {conversations.length === 0 ? (
            <div className="p-4 text-center text-xs text-slate-400">
              No conversations yet. Start one above!
            </div>
          ) : (
            conversations.map((conv) => {
              const isActive = conv.id === activeConvId;
              return (
                <div
                  key={conv.id}
                  onClick={() => setActiveConvId(conv.id)}
                  className={`group relative flex items-center justify-between p-2 rounded-lg text-xs cursor-pointer transition-all ${
                    isActive
                      ? "bg-slate-800 text-slate-100 border border-slate-700 font-medium shadow-sm"
                      : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/40 border border-transparent"
                  }`}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <MessageSquare
                      className={`w-3.5 h-3.5 shrink-0 ${
                        isActive ? "text-slate-200" : "text-slate-400"
                      }`}
                    />
                    <span className="truncate max-w-[170px]">
                      {conv.title || "Untitled Session"}
                    </span>
                  </div>

                  <button
                    onClick={(e) => handleDeleteConversation(e, conv.id)}
                    className="opacity-0 group-hover:opacity-100 p-1 hover:text-rose-400 text-slate-500 transition-opacity cursor-pointer"
                    title="Delete thread"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              );
            })
          )}
        </div>

        <div className="p-3 border-t border-slate-800 bg-slate-900/40 space-y-2">
          {org && (
            <div className="px-2.5 py-1.5 rounded-lg bg-slate-800/60 border border-slate-700/60 text-xs flex items-center gap-2">
              <Building2 className="w-3.5 h-3.5 text-slate-400 shrink-0" />
              <div className="min-w-0 flex-1">
                <p className="font-medium text-slate-200 truncate text-[11px]">
                  {org.name}
                </p>
                <p className="text-[10px] text-slate-400 font-mono truncate">
                  org: {org.slug}
                </p>
              </div>
            </div>
          )}

          <div className="flex items-center justify-between px-1.5 pt-0.5 text-xs">
            <div className="flex items-center gap-2 min-w-0 flex-1">
              <div className="w-6 h-6 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-[10px] font-semibold text-slate-300 shrink-0">
                {user?.email ? user.email[0].toUpperCase() : "U"}
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-[11px] font-medium text-slate-300 truncate">
                  {user?.email}
                </p>
                <span className="text-[9px] px-1 py-0.2 rounded bg-slate-800 border border-slate-700/60 text-slate-400 font-mono uppercase">
                  {user?.role}
                </span>
              </div>
            </div>

            <button
              onClick={logout}
              className="p-1 rounded-md text-slate-400 hover:text-rose-300 hover:bg-slate-800 transition-colors cursor-pointer"
              title="Sign out"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </div>

          <Link
            href="/documents"
            className="w-full mt-1 py-1.5 px-2.5 rounded-lg bg-slate-800/80 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-700/80 text-xs font-medium flex items-center justify-center gap-2 transition-all cursor-pointer"
          >
            <Layers className="w-3.5 h-3.5 text-slate-400" />
            <span>Document Admin Console</span>
          </Link>
        </div>
      </aside>

      {/* MAIN CHAT VIEWPORT */}
      <div className="flex-1 flex flex-col h-full overflow-hidden bg-[#090d16] relative">
        <header className="px-6 py-3.5 border-b border-slate-800 bg-slate-900/60 backdrop-blur-md flex items-center justify-between z-20">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-lg bg-slate-800 border border-slate-700/80 flex items-center justify-center text-slate-300">
              <Bot className="w-4 h-4 text-slate-300" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
                {activeConvId
                  ? conversations.find((c) => c.id === activeConvId)?.title ||
                    "Active Session"
                  : "Welcome to Intelligence OS"}
              </h2>
              <p className="text-[11px] text-slate-400">
                Hybrid dense-sparse retrieval • Cross-encoder reranking • Verified citations
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-900 border border-slate-800 text-xs text-slate-300">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              <span className="font-medium text-slate-300 text-[11px]">Guardrails Active</span>
            </div>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto p-6 max-w-4xl w-full mx-auto space-y-4">
          {error && (
            <div className="p-3.5 rounded-xl bg-rose-500/15 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
              <span>{error}</span>
            </div>
          )}

          {messages.length === 0 && !loadingConv && (
            <div className="h-full flex flex-col items-center justify-center text-center p-8 space-y-6">
              <div className="w-12 h-12 rounded-2xl bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-200 shadow-sm">
                <Sparkles className="w-6 h-6 text-slate-300" />
              </div>

              <div className="max-w-md space-y-2">
                <h3 className="text-lg font-bold text-white">
                  Enterprise Contextual Intelligence
                </h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Ask factual questions grounded in your organization’s uploaded documents.
                  Every statement is backed by verifiable source citations. If no evidence exists,
                  the strict refusal guardrail prevents hallucinations.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5 w-full max-w-2xl pt-2">
                {promptSuggestions.map((prompt, idx) => (
                  <button
                    key={idx}
                    onClick={() => {
                      setInputQuery(prompt);
                      textareaRef.current?.focus();
                    }}
                    className="p-3 rounded-xl bg-slate-900/60 hover:bg-slate-800/80 border border-slate-800 hover:border-slate-700 text-left text-xs text-slate-300 hover:text-white transition-all cursor-pointer shadow-sm group"
                  >
                    <div className="flex items-center justify-between">
                      <span className="line-clamp-2">{prompt}</span>
                      <span className="text-slate-500 group-hover:text-slate-300 text-xs ml-2">
                        →
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <ChatMessage
              key={msg.id}
              message={msg}
              onSelectCitation={(citation) =>
                handleCitationClick(citation, msg.citations || [])
              }
            />
          ))}

          {sending && (
            <div className="flex items-start gap-3 mb-6">
              <div className="w-8 h-8 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center shrink-0 text-slate-300 mt-1">
                <Cpu className="w-4 h-4 text-slate-300" />
              </div>
              <div className="rounded-xl px-4 py-3 border border-slate-800 bg-slate-900/60 flex items-center gap-3 shadow-sm">
                <div className="flex gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-pulse" />
                  <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-pulse [animation-delay:0.2s]" />
                  <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-pulse [animation-delay:0.4s]" />
                </div>
                <span className="text-xs text-slate-400 font-mono">
                  Executing Hybrid Retrieval, Cross-Encoder Rerank & Grounded Synthesis...
                </span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        <div className="p-4 border-t border-slate-800 bg-[#090d16]/90 backdrop-blur-lg">
          <form
            onSubmit={handleSendMessage}
            className="max-w-4xl mx-auto relative bg-slate-900 border border-slate-800 focus-within:border-slate-600 rounded-xl transition-all shadow-sm"
          >
            <textarea
              id="chat-query-input"
              ref={textareaRef}
              rows={2}
              value={inputQuery}
              onChange={(e) => setInputQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSendMessage(e);
                }
              }}
              placeholder="Ask a question about your organization's documents (e.g. 'What catalyzes cold fusion?')..."
              className="w-full pl-4 pr-14 py-3 bg-transparent text-sm text-slate-100 placeholder-slate-500 focus:outline-none transition-all resize-none"
            />

            <button
              id="btn-send-message"
              type="submit"
              disabled={!inputQuery.trim() || sending}
              className="absolute right-3 top-1/2 -translate-y-1/2 p-2 rounded-lg bg-slate-100 hover:bg-white text-slate-900 disabled:opacity-30 disabled:hover:bg-slate-100 transition-all shadow-sm cursor-pointer"
              title="Send message"
            >
              <Send className="w-3.5 h-3.5" />
            </button>
          </form>

          <div className="max-w-4xl mx-auto flex items-center justify-between text-[11px] text-slate-500 mt-2 px-1">
            <span>
              <kbd className="font-mono bg-slate-800 border border-slate-700/60 text-slate-400 px-1 py-0.5 rounded text-[10px]">Enter ↵</kbd> to send, <kbd className="font-mono bg-slate-800 border border-slate-700/60 text-slate-400 px-1 py-0.5 rounded text-[10px]">Shift+Enter</kbd> for newline
            </span>
            <span className="flex items-center gap-1.5 text-slate-400 font-medium">
              <Shield className="w-3 h-3 text-slate-400" />
              100% Tenant Isolated
            </span>
          </div>
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
