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

export interface RequestOptions extends RequestInit {
  timeoutMs?: number;
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
    options: RequestOptions = {}
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
    const timeoutMs = options.timeoutMs ?? 10000;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => {
      controller.abort();
    }, timeoutMs);

    if (options.signal) {
      if (options.signal.aborted) {
        controller.abort();
      } else {
        options.signal.addEventListener("abort", () => controller.abort());
      }
    }

    let response: Response;
    try {
      response = await fetch(url, {
        ...options,
        headers,
        signal: controller.signal,
      });
    } catch (networkError: any) {
      const isAbort =
        controller.signal.aborted ||
        networkError?.name === "AbortError" ||
        networkError?.name === "TimeoutError";
      const errMsg = networkError?.message || String(networkError);
      const isNetworkHangOrRefusal =
        isAbort ||
        errMsg.includes("Failed to fetch") ||
        errMsg.includes("ECONNREFUSED") ||
        errMsg.includes("fetch failed") ||
        errMsg.includes("NetworkError") ||
        errMsg.includes("Network request failed");

      if (isNetworkHangOrRefusal) {
        throw new Error(
          "Unable to reach the server. Please verify the backend is running."
        );
      }

      throw new Error(
        "Unable to reach the server. Please verify the backend is running."
      );
    } finally {
      clearTimeout(timeoutId);
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
      timeoutMs: 10000,
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
      timeoutMs: 10000,
    });
    if (res.access_token) {
      this.setToken(res.access_token);
    }
    return res;
  }

  async getMe(): Promise<User> {
    return this.request<User>("/auth/me", {
      timeoutMs: 10000,
    });
  }

  // --- Document APIs ---
  async uploadDocument(file: File): Promise<DocumentItem> {
    const formData = new FormData();
    formData.append("file", file);

    return this.request<DocumentItem>("/documents/upload", {
      method: "POST",
      body: formData,
      timeoutMs: 60000,
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
        timeoutMs: 60000,
      }
    );
  }

  // --- Evaluation APIs (Phase 3) ---
  async listEvaluations(params?: {
    skip?: number;
    limit?: number;
    judge_type?: string;
    status?: string;
  }): Promise<EvaluationRunsPage> {
    const searchParams = new URLSearchParams();
    if (params?.skip !== undefined) searchParams.set("skip", String(params.skip));
    if (params?.limit !== undefined) searchParams.set("limit", String(params.limit));
    if (params?.judge_type) searchParams.set("judge_type", params.judge_type);
    if (params?.status) searchParams.set("status", params.status);

    const query = searchParams.toString();
    const endpoint = `/evaluations${query ? `?${query}` : ""}`;
    return this.request<EvaluationRunsPage>(endpoint, { timeoutMs: 15000 });
  }

  async getEvaluation(runId: string): Promise<EvaluationRunDetail> {
    return this.request<EvaluationRunDetail>(`/evaluations/${runId}`, {
      timeoutMs: 15000,
    });
  }

  async listEvaluationResults(
    runId: string,
    params?: {
      skip?: number;
      limit?: number;
      passed?: boolean;
      query_type?: string;
      is_refusal?: boolean;
    }
  ): Promise<EvaluationResultsPage> {
    const searchParams = new URLSearchParams();
    if (params?.skip !== undefined) searchParams.set("skip", String(params.skip));
    if (params?.limit !== undefined) searchParams.set("limit", String(params.limit));
    if (params?.passed !== undefined) searchParams.set("passed", String(params.passed));
    if (params?.query_type) searchParams.set("query_type", params.query_type);
    if (params?.is_refusal !== undefined) searchParams.set("is_refusal", String(params.is_refusal));

    const query = searchParams.toString();
    const endpoint = `/evaluations/${runId}/results${query ? `?${query}` : ""}`;
    return this.request<EvaluationResultsPage>(endpoint, { timeoutMs: 15000 });
  }

  async getEvaluationResult(
    runId: string,
    resultId: string
  ): Promise<EvaluationResultDetail> {
    return this.request<EvaluationResultDetail>(
      `/evaluations/${runId}/results/${resultId}`,
      { timeoutMs: 15000 }
    );
  }

  async createEvaluation(payload: EvaluationRunCreate): Promise<EvaluationRunDetail> {
    return this.request<EvaluationRunDetail>("/evaluations", {
      method: "POST",
      body: JSON.stringify(payload),
      timeoutMs: 120000, // 2-min bounded evaluation limit
    });
  }

  async compareEvaluations(
    baseRunId: string,
    targetRunId: string
  ): Promise<EvaluationComparisonResponse> {
    const params = new URLSearchParams({
      base_run_id: baseRunId,
      target_run_id: targetRunId,
    });
    return this.request<EvaluationComparisonResponse>(
      `/evaluations/compare?${params.toString()}`,
      { timeoutMs: 20000 }
    );
  }
}

// Evaluation Types (Phase 3)
export interface EvaluationRunListItem {
  id: string;
  org_id: string;
  dataset_name: string;
  dataset_version: string;
  status: string;
  judge_type: string;
  llm_provider?: string | null;
  llm_model?: string | null;
  total_test_cases: number;
  passed_test_cases: number;
  pass_rate: number;
  progress_current?: number;
  progress_total?: number;
  error_message?: string | null;
  recall_at_3?: number | null;
  recall_at_5?: number | null;
  mrr?: number | null;
  ndcg_at_5?: number | null;
  citation_precision?: number | null;
  citation_coverage?: number | null;
  mean_faithfulness?: number | null;
  mean_correctness?: number | null;
  mean_completeness?: number | null;
  mean_citation_correctness?: number | null;
  mean_latency_ms?: number | null;
  latency_p95_ms?: number | null;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
}

export interface EvaluationRunDetail extends EvaluationRunListItem {
  embedding_model?: string | null;
  reranker_model?: string | null;
  correct_refusal_rate?: number | null;
  false_refusal_rate?: number | null;
  config_snapshot: Record<string, any>;
  summary_metrics: Record<string, any>;
  regression_summary: Record<string, any>;
}

export interface EvaluationRunsPage {
  items: EvaluationRunListItem[];
  total: number;
  skip: number;
  limit: number;
}

export interface EvaluationRunCreate {
  dataset_name?: string;
  judge_type?: "deterministic" | "llm" | string;
  limit?: number;
  offline?: boolean;
}

export interface EvaluationResultListItem {
  id: string;
  run_id: string;
  test_case_id: string;
  query: string;
  query_type: string;
  expected_behavior: string;
  generated_answer: string;
  passed: boolean;
  is_refusal: boolean;
  recall_at_3?: number | null;
  recall_at_5?: number | null;
  mrr?: number | null;
  ndcg_at_5?: number | null;
  citation_precision?: number | null;
  citation_coverage?: number | null;
  faithfulness?: number | null;
  correctness?: number | null;
  completeness?: number | null;
  citation_correctness?: number | null;
  total_latency_ms?: number | null;
  failure_reason?: string | null;
  created_at: string;
}

export interface EvaluationResultDetail extends EvaluationResultListItem {
  org_id: string;
  retrieved_candidates: Array<{
    chunk_id: string;
    document_id: string;
    document_title: string;
    page_number?: number | null;
    section_heading?: string | null;
    content: string;
    score: number;
    rerank_score?: number | null;
  }>;
  reranked_candidates: Array<{
    chunk_id: string;
    document_id: string;
    document_title: string;
    page_number?: number | null;
    section_heading?: string | null;
    content: string;
    score: number;
    rerank_score?: number | null;
  }>;
  citations: Array<{
    document_title: string;
    page_number?: number | null;
    section_heading?: string | null;
    content: string;
  }>;
  trace_data: Record<string, any>;
  judge_output: {
    faithfulness?: number;
    correctness?: number;
    completeness?: number;
    citation_correctness?: number;
    supported?: boolean;
    reasoning?: string;
    unsupported_claims?: string[];
  };
}

export interface EvaluationResultsPage {
  items: EvaluationResultListItem[];
  total: number;
  skip: number;
  limit: number;
}

export interface MetricDelta {
  base_value?: number | null;
  target_value?: number | null;
  delta?: number | null;
  percent_change?: number | null;
  status: "improved" | "regressed" | "neutral";
}

export interface EvaluationComparisonDeltas {
  pass_rate: MetricDelta;
  recall_at_3: MetricDelta;
  recall_at_5: MetricDelta;
  mrr: MetricDelta;
  ndcg_at_5: MetricDelta;
  citation_precision: MetricDelta;
  citation_coverage: MetricDelta;
  mean_faithfulness: MetricDelta;
  mean_correctness: MetricDelta;
  mean_completeness: MetricDelta;
  mean_citation_correctness: MetricDelta;
  mean_latency_ms: MetricDelta;
}

export interface EvaluationComparisonResponse {
  base_run: EvaluationRunListItem;
  target_run: EvaluationRunListItem;
  deltas: EvaluationComparisonDeltas;
  regressed_cases_count: number;
  improved_cases_count: number;
}

export const api = new ApiClient();

