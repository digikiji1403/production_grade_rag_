const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

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
      const body = await response.json();
      if (typeof body.detail === "string") {
        message = body.detail;
      } else if (Array.isArray(body.detail)) {
        message = body.detail
          .map((item: { msg?: string }) => item.msg || "Validation error")
          .join(", ");
      } else if (typeof body.message === "string") {
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

  listBases: () => request<KnowledgeBase[]>("/knowledge-bases"),

  createBase: (data: KnowledgeBaseCreate) =>
    request<KnowledgeBase>("/knowledge-bases", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateBase: (id: string, data: KnowledgeBaseUpdate) =>
    request<KnowledgeBase>(`/knowledge-bases/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  deleteBase: (id: string) =>
    request<void>(`/knowledge-bases/${id}`, { method: "DELETE" }),

  listDocuments: (knowledgeBaseId: string) =>
    request<Document[]>(`/knowledge-bases/${knowledgeBaseId}/documents`),

  uploadDocument: (knowledgeBaseId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);

    return request<Document>(
      `/knowledge-bases/${knowledgeBaseId}/documents`,
      { method: "POST", body: form },
    );
  },

  deleteDocument: (knowledgeBaseId: string, documentId: string) =>
    request<void>(
      `/knowledge-bases/${knowledgeBaseId}/documents/${documentId}`,
      { method: "DELETE" },
    ),

  query: (knowledgeBaseId: string, query: string, topK = 5) =>
    request<QueryResponse>(`/knowledge-bases/${knowledgeBaseId}/query`, {
      method: "POST",
      body: JSON.stringify({ query, top_k: topK }),
    }),
};

