// Shapes returned by the FastAPI backend (see app/schemas/chat.py).

export interface ToolCall {
  name: string;
  ok: boolean;
  arguments: Record<string, unknown>;
  result: unknown;
  error: string | null;
}

export interface ChatResponse {
  conversation_id: string;
  reply: string;
  model: string;
  tool_calls: ToolCall[];
}

export interface ApiMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  tool_calls: ToolCall[] | null;
  created_at: string;
}

export interface ConversationDetail {
  conversation_id: string;
  messages: ApiMessage[];
}

export interface ConversationSummary {
  conversation_id: string;
  title: string;
  message_count: number;
  updated_at: string;
}

export interface Health {
  status: "ok" | "degraded";
  database: string;
  openai_configured: boolean;
  model: string;
}

// A message as shown in the UI.
export interface ChatMessage {
  key: string;
  role: "user" | "assistant";
  content: string;
  toolCalls: ToolCall[];
}
