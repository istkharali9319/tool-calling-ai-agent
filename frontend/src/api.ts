import type { ChatResponse, ConversationDetail, ConversationSummary, Health } from "./types";

const API = "/api/v1";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** FastAPI errors are {"detail": string} or, for validation errors, {"detail": [{msg}, ...]}. */
function errorMessage(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => (d as { msg?: string }).msg ?? "Invalid request").join("; ");
  }
  return `Request failed (HTTP ${status})`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError("Can't reach the server. Is the backend running?", 0);
  }

  if (response.status === 204) return undefined as T;
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(errorMessage(body, response.status), response.status);
  return body as T;
}

export const api = {
  health: () => request<Health>("/health"),

  sendMessage: (message: string, conversationId: string | null) =>
    request<ChatResponse>(`${API}/chat`, {
      method: "POST",
      body: JSON.stringify({ message, conversation_id: conversationId }),
    }),

  listConversations: () => request<ConversationSummary[]>(`${API}/conversations`),

  getConversation: (id: string) => request<ConversationDetail>(`${API}/conversations/${id}`),

  deleteConversation: (id: string) =>
    request<void>(`${API}/conversations/${id}`, { method: "DELETE" }),
};
