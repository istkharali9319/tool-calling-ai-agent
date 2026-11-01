import { useCallback, useEffect, useRef, useState } from "react";

import { api, ApiError } from "./api";
import type { ChatMessage, ConversationSummary, Health } from "./types";

let keyCounter = 0;
const nextKey = () => `local-${++keyCounter}`;

function describe(error: unknown): string {
  return error instanceof ApiError ? error.message : "Something went wrong. Please try again.";
}

/** All chat state and the actions that change it. Components only render what this returns. */
export function useChat() {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sending, setSending] = useState(false);
  const [loadingConversation, setLoadingConversation] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<Health | null>(null);

  // Bumped whenever the user switches conversation. A reply that arrives after a switch
  // belongs to a screen that is no longer shown, so it must not be drawn.
  const viewRef = useRef(0);

  const refreshConversations = useCallback(async () => {
    try {
      setConversations(await api.listConversations());
    } catch {
      // The sidebar is not essential; keep the old list if this fails.
    }
  }, []);

  useEffect(() => {
    void refreshConversations();
    api.health().then(setHealth).catch(() => setHealth(null));
  }, [refreshConversations]);

  const newConversation = useCallback(() => {
    viewRef.current += 1;
    setActiveId(null);
    setMessages([]);
    setError(null);
    setLoadingConversation(false);
  }, []);

  const openConversation = useCallback(async (id: string) => {
    const view = ++viewRef.current;
    setActiveId(id);
    setError(null);
    setLoadingConversation(true);
    try {
      const detail = await api.getConversation(id);
      if (viewRef.current !== view) return;
      setMessages(
        detail.messages.map((m) => ({
          key: `db-${m.id}`,
          role: m.role,
          content: m.content,
          toolCalls: m.tool_calls ?? [],
        })),
      );
    } catch (e) {
      if (viewRef.current === view) {
        setMessages([]);
        setError(describe(e));
      }
    } finally {
      if (viewRef.current === view) setLoadingConversation(false);
    }
  }, []);

  /** Sends a message. Returns false when it failed, so the caller can keep the typed text. */
  const send = useCallback(
    async (text: string): Promise<boolean> => {
      const message = text.trim();
      if (!message || sending) return false;

      const view = viewRef.current;
      const userMessage: ChatMessage = { key: nextKey(), role: "user", content: message, toolCalls: [] };
      setMessages((prev) => [...prev, userMessage]);
      setError(null);
      setSending(true);

      try {
        const response = await api.sendMessage(message, activeId);
        if (viewRef.current === view) {
          setActiveId(response.conversation_id);
          setMessages((prev) => [
            ...prev,
            { key: nextKey(), role: "assistant", content: response.reply, toolCalls: response.tool_calls },
          ]);
        }
        void refreshConversations();
        return true;
      } catch (e) {
        // The backend saves nothing when a request fails, so take the message back off screen.
        if (viewRef.current === view) {
          setMessages((prev) => prev.filter((m) => m.key !== userMessage.key));
          setError(describe(e));
        }
        return false;
      } finally {
        setSending(false);
      }
    },
    [activeId, sending, refreshConversations],
  );

  const deleteConversation = useCallback(
    async (id: string) => {
      try {
        await api.deleteConversation(id);
        if (activeId === id) newConversation();
        setConversations((prev) => prev.filter((c) => c.conversation_id !== id));
      } catch (e) {
        setError(describe(e));
      }
    },
    [activeId, newConversation],
  );

  return {
    conversations,
    activeId,
    messages,
    sending,
    loadingConversation,
    error,
    health,
    send,
    newConversation,
    openConversation,
    deleteConversation,
    dismissError: () => setError(null),
  };
}
