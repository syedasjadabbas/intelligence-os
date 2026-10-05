/**
 * Centralized API client for Intelligence OS.
 * Manages JWT tokens, multi-tenant headers, and API methods.
 */

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1";

// Auth & Tenant Types
export interface Organization {
  id: string;
  name: string;
  slug: string;
  created_at?: string;
}

export interface User {
  id: string;
  org_id: string;
  email: string;
  role: "ADMIN" | "MEMBER";
  is_active: boolean;
  created_at?: string;
  organization?: Organization;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  organization: Organization;
  user: User;
}

export interface RegisterOrgPayload {
  org_name: string;
  org_slug: string;
  admin_email: string;
  admin_password: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

// Document Types
export type DocumentStatus = "QUEUED" | "PROCESSING" | "COMPLETED" | "FAILED";

export interface DocumentItem {
  id: string;
  org_id: string;
  title: string;
  status: DocumentStatus;
  file_size_bytes: number;
  total_chunks?: number;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentChunkItem {
  id: string;
  chunk_index: number;
  content: string;
  page_number?: number | null;
  section_heading?: string | null;
}

export interface DocumentDetail extends DocumentItem {
  chunks: DocumentChunkItem[];
}

// Chat & Citation Types
export interface CitationItem {
  source_index: number;
  source_tag: string;
  chunk_id: string;
  document_id: string;
  document_title: string;
  page_number?: number | null;
  section_heading?: string | null;
  content_snippet?: string | null;
}

export interface TraceData {
  original_query: string;
  rewritten_query: string;
  retrieval_candidate_count: number;
  reranked_scores: Array<{
    chunk_id: string;
    document_id: string;
    document_title: string;
    score: number;
    rerank_score?: number | null;
  }>;
  selected_sources: Array<{
    source_index: number;
    chunk_id: string;
    document_id: string;
    document_title: string;
    page_number?: number | null;
    section_heading?: string | null;
  }>;
  latency_ms: {
    retrieval: number;
    rerank: number;
    generation: number;
    total: number;
  };
  is_refusal: boolean;
}

export interface MessageItem {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  citations: CitationItem[];
  trace_data: TraceData;
  created_at: string;
}

export interface ConversationItem {
  id: string;
  org_id: string;
  user_id: string;
  title?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail extends ConversationItem {
  messages: MessageItem[];
}

export interface ChatMessageResponse {
  conversation_id: string;
  user_message_id: string;
  assistant_message_id: string;
  answer: string;
  citations: CitationItem[];
  trace_data: TraceData;
}

class ApiClient {
  private tokenKey = "intelligence_os_jwt";

  public getToken(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem(this.tokenKey);
  }

  public setToken(token: string): void {
    if (typeof window === "undefined") return;
    localStorage.setItem(this.tokenKey, token);
  }

  public clearToken(): void {
    if (typeof window === "undefined") return;
    localStorage.removeItem(this.tokenKey);
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const token = this.getToken();
    const headers: Record<string, string> = {
      ...(options.headers as Record<string, string>),
    };

    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }

    const url = `${API_BASE_URL}${endpoint}`;
    let response: Response;
    try {
      response = await fetch(url, {
        ...options,
        headers,
      });
    } catch (networkError: any) {
      throw new Error(
        `Backend server unreachable at ${url}: ${networkError.message || networkError}`
      );
    }

    if (response.status === 401) {
      this.clearToken();
      if (
        typeof window !== "undefined" &&
        !window.location.pathname.startsWith("/login") &&
        !window.location.pathname.startsWith("/register")
      ) {
        window.location.href = "/login";
      }
    }

    const contentType = response.headers.get("content-type") || "";
    const isJson = contentType.includes("application/json");

    if (!response.ok) {
      let errorMessage = `HTTP Error ${response.status}`;
      if (isJson) {
        try {
          const errorData = await response.json();
          errorMessage = errorData.detail || errorData.message || errorMessage;
        } catch {
          // fallback to status code message
        }
      } else {
        const textContent = await response.text();
        const snippet = textContent.slice(0, 150).replace(/<[^>]*>/g, "").trim();
        errorMessage = `Backend server returned non-JSON response (${response.status}): ${snippet || "Unknown error"}`;
      }
      throw new Error(errorMessage);
    }

    if (response.status === 204) {
      return null as T;
    }

    if (!isJson) {
      const textContent = await response.text();
      const snippet = textContent.slice(0, 150).replace(/<[^>]*>/g, "").trim();
      throw new Error(
        `Backend server returned non-JSON response (${response.status}): ${snippet || "Expected JSON but received HTML/text"}`
      );
    }

    return response.json();
  }

  // --- Auth APIs ---
  async registerOrg(payload: RegisterOrgPayload): Promise<AuthResponse> {
    const res = await this.request<AuthResponse>("/auth/register-org", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    if (res.access_token) {
      this.setToken(res.access_token);
    }
    return res;
  }

  async login(payload: LoginPayload): Promise<AuthResponse> {
    const res = await this.request<AuthResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    if (res.access_token) {
      this.setToken(res.access_token);
    }
    return res;
  }

  async getMe(): Promise<User> {
    return this.request<User>("/auth/me");
  }

  // --- Document APIs ---
  async uploadDocument(file: File): Promise<DocumentItem> {
    const formData = new FormData();
    formData.append("file", file);

    return this.request<DocumentItem>("/documents/upload", {
      method: "POST",
      body: formData,
    });
  }

  async listDocuments(): Promise<DocumentItem[]> {
    return this.request<DocumentItem[]>("/documents");
  }

  async getDocument(documentId: string): Promise<DocumentDetail> {
    return this.request<DocumentDetail>(`/documents/${documentId}`);
  }

  async deleteDocument(documentId: string): Promise<{ message: string }> {
    return this.request<{ message: string }>(`/documents/${documentId}`, {
      method: "DELETE",
    });
  }

  // --- Conversation & Chat APIs ---
  async createConversation(title?: string): Promise<ConversationItem> {
    return this.request<ConversationItem>("/chat/conversations", {
      method: "POST",
      body: JSON.stringify({ title: title || "New Conversation" }),
    });
  }

  async listConversations(): Promise<ConversationItem[]> {
    return this.request<ConversationItem[]>("/chat/conversations");
  }

  async getConversation(convId: string): Promise<ConversationDetail> {
    return this.request<ConversationDetail>(`/chat/conversations/${convId}`);
  }

  async deleteConversation(convId: string): Promise<void> {
    return this.request<void>(`/chat/conversations/${convId}`, {
      method: "DELETE",
    });
  }

  async sendMessage(
    convId: string,
    question: string
  ): Promise<ChatMessageResponse> {
    return this.request<ChatMessageResponse>(
      `/chat/conversations/${convId}/messages`,
      {
        method: "POST",
        body: JSON.stringify({ question }),
      }
    );
  }
}

export const api = new ApiClient();
