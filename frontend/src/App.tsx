import { useState } from "react";

import { Composer } from "./components/Composer";
import { MessageList } from "./components/MessageList";
import { Sidebar } from "./components/Sidebar";
import { useChat } from "./useChat";

export default function App() {
  const chat = useChat();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const closeSidebarThen = (action: () => void) => () => {
    setSidebarOpen(false);
    action();
  };

  return (
    <div className="app">
      <Sidebar
        conversations={chat.conversations}
        activeId={chat.activeId}
        open={sidebarOpen}
        onNew={closeSidebarThen(chat.newConversation)}
        onSelect={(id) => closeSidebarThen(() => void chat.openConversation(id))()}
        onDelete={(id) => void chat.deleteConversation(id)}
        onClose={() => setSidebarOpen(false)}
      />

      <main className="chat">
        <header className="topbar">
          <button
            type="button"
            className="menu"
            aria-label="Show conversations"
            onClick={() => setSidebarOpen(true)}
          >
            <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden>
              <path d="M3 6h18v2H3zm0 5h18v2H3zm0 5h18v2H3z" fill="currentColor" />
            </svg>
          </button>
          <h1>Business Assistant</h1>
          {chat.health && (
            <span className={`status ${chat.health.openai_configured ? "ready" : "off"}`}>
              <span className="dot" aria-hidden />
              {chat.health.openai_configured ? chat.health.model : "AI not configured"}
            </span>
          )}
        </header>

        {chat.health && !chat.health.openai_configured && (
          <div className="banner warn" role="status">
            The server has no OpenAI API key, so chat is unavailable. Set <code>OPENAI_API_KEY</code> in{" "}
            <code>.env</code> and restart the backend.
          </div>
        )}

        <MessageList
          messages={chat.messages}
          sending={chat.sending}
          loading={chat.loadingConversation}
          onSuggestion={(prompt) => void chat.send(prompt)}
        />

        {chat.error && (
          <div className="banner error" role="alert">
            <span>{chat.error}</span>
            <button type="button" onClick={chat.dismissError} aria-label="Dismiss error">
              ✕
            </button>
          </div>
        )}

        <Composer disabled={chat.sending} onSend={chat.send} />
      </main>
    </div>
  );
}
