import { useState } from "react";

import type { ConversationSummary } from "../types";

function relativeTime(iso: string): string {
  // SQLite drops the timezone; the backend stores UTC, so treat a bare timestamp as UTC.
  const date = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`);
  const minutes = Math.round((Date.now() - date.getTime()) / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  return date.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

interface Props {
  conversations: ConversationSummary[];
  activeId: string | null;
  open: boolean;
  onNew: () => void;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onClose: () => void;
}

export function Sidebar({ conversations, activeId, open, onNew, onSelect, onDelete, onClose }: Props) {
  const [confirming, setConfirming] = useState<string | null>(null);

  return (
    <>
      <div className={`backdrop ${open ? "show" : ""}`} onClick={onClose} aria-hidden />
      <aside className={`sidebar ${open ? "open" : ""}`} aria-label="Conversations">
        <button type="button" className="new-chat" onClick={onNew}>
          <span aria-hidden>＋</span> New chat
        </button>

        <h2 className="sidebar-heading">Recent</h2>
        {conversations.length === 0 ? (
          <p className="muted small sidebar-empty">No conversations yet.</p>
        ) : (
          <ul className="conversation-list">
            {conversations.map((c) => (
              <li key={c.conversation_id} className={c.conversation_id === activeId ? "active" : ""}>
                {confirming === c.conversation_id ? (
                  <div className="confirm">
                    <span>Delete this chat?</span>
                    <button
                      type="button"
                      className="danger"
                      onClick={() => {
                        setConfirming(null);
                        onDelete(c.conversation_id);
                      }}
                    >
                      Delete
                    </button>
                    <button type="button" onClick={() => setConfirming(null)}>
                      Cancel
                    </button>
                  </div>
                ) : (
                  <>
                    <button type="button" className="conversation" onClick={() => onSelect(c.conversation_id)}>
                      <span className="conversation-title">{c.title}</span>
                      <span className="conversation-meta">{relativeTime(c.updated_at)}</span>
                    </button>
                    <button
                      type="button"
                      className="delete"
                      aria-label={`Delete "${c.title}"`}
                      onClick={() => setConfirming(c.conversation_id)}
                    >
                      <svg viewBox="0 0 24 24" width="15" height="15" aria-hidden>
                        <path
                          d="M9 3h6l1 2h4v2H4V5h4l1-2zm-3 6h12l-1 12H7L6 9z"
                          fill="currentColor"
                        />
                      </svg>
                    </button>
                  </>
                )}
              </li>
            ))}
          </ul>
        )}
      </aside>
    </>
  );
}
