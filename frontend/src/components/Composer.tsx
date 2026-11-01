import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";

const MAX_LENGTH = 8000;

interface Props {
  disabled: boolean;
  onSend: (text: string) => Promise<boolean>;
}

export function Composer({ disabled, onSend }: Props) {
  const [text, setText] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Grow the box with its content, up to the CSS max-height.
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [text]);

  useEffect(() => {
    if (!disabled) inputRef.current?.focus();
  }, [disabled]);

  async function submit() {
    const value = text;
    if (!value.trim() || disabled) return;
    setText("");
    const sent = await onSend(value);
    if (!sent) setText(value); // keep what the user typed if sending failed
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void submit();
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends, Shift+Enter adds a new line. Ignore Enter while an IME is composing.
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      void submit();
    }
  }

  const nearLimit = text.length > MAX_LENGTH * 0.9;

  return (
    <form className="composer" onSubmit={onSubmit}>
      <div className="composer-box">
        <textarea
          ref={inputRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Ask the assistant…"
          aria-label="Message"
          rows={1}
          maxLength={MAX_LENGTH}
        />
        <button type="submit" className="send" disabled={disabled || !text.trim()} aria-label="Send">
          <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden>
            <path d="M4 12l16-8-6 16-2.5-6.5L4 12z" fill="currentColor" />
          </svg>
        </button>
      </div>
      <p className="composer-hint">
        {nearLimit ? `${text.length} / ${MAX_LENGTH} characters` : "Enter to send · Shift+Enter for a new line"}
      </p>
    </form>
  );
}
