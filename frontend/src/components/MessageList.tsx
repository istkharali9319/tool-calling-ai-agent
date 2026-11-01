import { useEffect, useRef } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { ChatMessage } from "../types";
import { ToolCalls } from "./ToolCalls";
import { WeatherCard, weatherResults } from "./WeatherCard";

const SUGGESTIONS = [
  { label: "Calculate", prompt: "What is 144 divided by 12, minus 3?" },
  { label: "Find an employee", prompt: "Find employees named Singh" },
  { label: "List users", prompt: "List all users and their roles" },
  { label: "Weather", prompt: "What's the weather in Mumbai today?" },
  { label: "Date and time", prompt: "What's today's date and the current time?" },
  {
    label: "Summarize text",
    prompt:
      "Summarize this: Our Q3 revenue grew 18% thanks to new enterprise customers. Support tickets dropped by a third after the onboarding redesign. The office moved to a larger floor in August. Enterprise renewals hit a record 94%. Next quarter we plan to expand the sales team.",
  },
];

interface Props {
  messages: ChatMessage[];
  sending: boolean;
  loading: boolean;
  onSuggestion: (prompt: string) => void;
}

export function MessageList({ messages, sending, loading, onSuggestion }: Props) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ behavior: "smooth", block: "end" });
  }, [messages, sending]);

  if (loading) {
    return (
      <div className="messages centered">
        <p className="muted">Loading conversation…</p>
      </div>
    );
  }

  if (messages.length === 0 && !sending) {
    return (
      <div className="messages centered">
        <div className="empty">
          <h2>How can I help?</h2>
          <p className="muted">
            Ask about users, employees, calculations, the date and time, or paste text to summarize.
          </p>
          <div className="suggestions">
            {SUGGESTIONS.map((s) => (
              <button key={s.label} type="button" className="suggestion" onClick={() => onSuggestion(s.prompt)}>
                <strong>{s.label}</strong>
                <span>{s.prompt}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="messages" aria-live="polite">
      {messages.map((m) => (
        <div key={m.key} className={`message ${m.role}`}>
          <div className="bubble">
            {m.role === "assistant" ? (
              <div className="markdown">
                <Markdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    a: (props) => <a {...props} target="_blank" rel="noopener noreferrer" />,
                  }}
                >
                  {m.content}
                </Markdown>
              </div>
            ) : (
              <p className="plain">{m.content}</p>
            )}
          </div>
          {m.role === "assistant" &&
            weatherResults(m.toolCalls).map((w, i) => <WeatherCard key={i} data={w} />)}
          {m.role === "assistant" && <ToolCalls calls={m.toolCalls} />}
        </div>
      ))}
      {sending && (
        <div className="message assistant">
          <div className="bubble typing" aria-label="Assistant is thinking">
            <span />
            <span />
            <span />
          </div>
        </div>
      )}
      <div ref={endRef} />
    </div>
  );
}
