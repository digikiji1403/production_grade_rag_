const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1"
).replace(/\/+$/, "");

export interface User {
  id: string;
  email: string;
  is_active: boolean;
  created_at: string;
}

export interface AuthToken {
  access_token: string;
  token_type: string;
}

export interface KnowledgeBase {
  id: string;
  owner_id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface Document {
  id: string;
  knowledge_base_id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  checksum: string;
  status: string;
  page_count: number | null;
  created_at: string;
}

export interface ProcessingRun {
  id: string;
  document_id: string;
  attempt_number: number;
  status: string;
  current_stage: string | null;
  stage_timings_ms: Record<string, number>;
  page_count: number | null;
  chunk_count: number | null;
  embedding_count: number | null;
  error_stage: string | null;
  error_message: string | null;
  started_at: string;
  completed_at: string | null;
  duration_ms: number | null;
}

export interface HealthCheck {
  status: string;
  service?: string;
  version?: string;
  database?: string;
}

export interface QuerySource {
  source_id: string;
  chunk_id: string;
  document_id: string;
  filename: string;
  chunk_index: number;
  page_numbers: number[];
  extraction_methods: string[];
  score: number;
}

export interface QueryResult {
  chunk_id: string;
  document_id: string;
  filename: string;
  chunk_index: number;
  content: string;
  page_numbers: number[];
  extraction_methods: string[];
  score: number;
}

export interface QueryResponse {
  query: string;
  knowledge_base_id: string;
  answer: string;
  sources: QuerySource[];
  results: QueryResult[];
}

export interface KnowledgeBaseCreate {
  name: string;
  description?: string | null;
}

export interface KnowledgeBaseUpdate {
  name?: string;
  description?: string | null;
}

export interface EvaluationCase {
  query_id: string;
  query: string;
  relevant_chunk_ids: string[];
  relevance_grades: Record<string, number>;
  top_k: number;
}

export interface EvaluationDataset {
  dataset_name: string;
  dataset_version: string;
  cases: EvaluationCase[];
}

export interface EvaluationRun {
  id: string;
  knowledge_base_id: string;
  dataset_name: string;
  dataset_version: string;
  status: string;
  total_queries: number;
  completed_queries: number;
  aggregate_metrics: Record<string, number>;
  started_at: string;
  completed_at: string | null;
  duration_ms: number | null;
}

export interface EvaluationRetrievedChunk {
  chunk_id: string;
  document_id: string;
  filename: string;
  chunk_index: number;
  score: number;
}

export interface EvaluationResult {
  id: string;
  query_id: string;
  query: string;
  top_k: number;
  relevant_chunk_ids: string[];
  retrieved_chunk_ids: string[];
  retrieved_results: EvaluationRetrievedChunk[];
  metrics: Record<string, number>;
  duration_ms: number;
}

export interface EvaluationRunDetail extends EvaluationRun {
  results: EvaluationResult[];
}

export interface EvaluationHistory {
  items: EvaluationRun[];
  total: number;
  skip: number;
  limit: number;
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("ragforge_access_token");
}

export function setToken(token: string): void {
  localStorage.setItem("ragforge_access_token", token);
}

export function clearToken(): void {
  localStorage.removeItem("ragforge_access_token");
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  const token = getToken();

  if (token) headers.set("Authorization", `Bearer ${token}`);

  if (
    options.body &&
    !(options.body instanceof FormData) &&
    !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let message = `Request failed (${response.status})`;

    try {
      const body: unknown = await response.json();
      if (typeof body === "object" && body !== null && "detail" in body) {
        const detail = body.detail;
        if (typeof detail === "string") {
          message = detail;
        } else if (Array.isArray(detail)) {
          message = detail
            .map((item: unknown) => {
              if (
                typeof item === "object" &&
                item !== null &&
                "msg" in item &&
                typeof item.msg === "string"
              ) {
                return item.msg;
              }
              return "Validation error";
            })
            .join(", ");
        } else if (typeof detail === "object" && detail !== null) {
          const parts = [
            "status" in detail && typeof detail.status === "string" ? detail.status : null,
            "database" in detail && typeof detail.database === "string"
              ? `database: ${detail.database}`
              : null,
          ].filter((part): part is string => part !== null);
          if (parts.length > 0) message = parts.join(" · ");
        }
      } else if (
        typeof body === "object" &&
        body !== null &&
        "message" in body &&
        typeof body.message === "string"
      ) {
        message = body.message;
      }
    } catch {
      // Keep the HTTP status message when the response isn't JSON.
    }

    throw new Error(message);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  register: (email: string, password: string) =>
    request<User>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  login: (email: string, password: string) =>
    request<AuthToken>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  me: () => request<User>("/auth/me"),

  health: () => request<HealthCheck>("/health"),

  readiness: () => request<HealthCheck>("/health/ready"),

  listBases: () => request<KnowledgeBase[]>("/knowledge-bases"),

  createBase: (data: KnowledgeBaseCreate) =>
    request<KnowledgeBase>("/knowledge-bases", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateBase: (id: string, data: KnowledgeBaseUpdate) =>
    request<KnowledgeBase>(`/knowledge-bases/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  deleteBase: (id: string) =>
    request<void>(`/knowledge-bases/${encodeURIComponent(id)}`, {
      method: "DELETE",
    }),

  listDocuments: (knowledgeBaseId: string, skip = 0, limit = 100) =>
    request<Document[]>(
      `/knowledge-bases/${encodeURIComponent(knowledgeBaseId)}/documents?skip=${skip}&limit=${limit}`,
    ),

  uploadDocument: (knowledgeBaseId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);

    return request<Document>(
      `/knowledge-bases/${encodeURIComponent(knowledgeBaseId)}/documents`,
      { method: "POST", body: form },
    );
  },

  uploadDocuments: (knowledgeBaseId: string, files: File[]) =>
    Promise.all(files.map((file) => api.uploadDocument(knowledgeBaseId, file))),

  deleteDocument: (knowledgeBaseId: string, documentId: string) =>
    request<void>(
      `/knowledge-bases/${encodeURIComponent(knowledgeBaseId)}/documents/${encodeURIComponent(documentId)}`,
      { method: "DELETE" },
    ),

  processingRuns: (
    knowledgeBaseId: string,
    documentId: string,
    skip = 0,
    limit = 100,
  ) =>
    request<ProcessingRun[]>(
      `/knowledge-bases/${encodeURIComponent(knowledgeBaseId)}/documents/${encodeURIComponent(documentId)}/processing-runs?skip=${skip}&limit=${limit}`,
    ),

  query: (knowledgeBaseId: string, query: string, topK = 5) =>
    request<QueryResponse>(
      `/knowledge-bases/${encodeURIComponent(knowledgeBaseId)}/query`,
      {
        method: "POST",
        body: JSON.stringify({ query, top_k: topK }),
      },
    ),

  createEvaluation: (knowledgeBaseId: string, dataset: EvaluationDataset) =>
    request<EvaluationRun>(
      `/knowledge-bases/${encodeURIComponent(knowledgeBaseId)}/evaluations`,
      { method: "POST", body: JSON.stringify(dataset) },
    ),

  evaluationHistory: (knowledgeBaseId: string, skip = 0, limit = 20) =>
    request<EvaluationHistory>(
      `/knowledge-bases/${encodeURIComponent(knowledgeBaseId)}/evaluations?skip=${skip}&limit=${limit}`,
    ),

  evaluationDetail: (knowledgeBaseId: string, runId: string) =>
    request<EvaluationRunDetail>(
      `/knowledge-bases/${encodeURIComponent(knowledgeBaseId)}/evaluations/${encodeURIComponent(runId)}`,
    ),
};
