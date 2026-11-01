import type { ToolCall } from "../types";

function formatArgs(args: Record<string, unknown>): string {
  return Object.entries(args)
    .map(([key, value]) => {
      if (typeof value !== "string") return `${key}=${String(value)}`;
      return `${key}=${JSON.stringify(value.length > 40 ? `${value.slice(0, 40)}…` : value)}`;
    })
    .join(", ");
}

/** Shows which backend tools ran for a reply, with their arguments and results. */
export function ToolCalls({ calls }: { calls: ToolCall[] }) {
  if (calls.length === 0) return null;
  const failed = calls.filter((c) => !c.ok).length;

  return (
    <details className="tools">
      <summary>
        <span className="tools-icon" aria-hidden>⚙</span>
        Used {calls.length} {calls.length === 1 ? "tool" : "tools"}
        <span className="tools-names">{[...new Set(calls.map((c) => c.name))].join(", ")}</span>
        {failed > 0 && <span className="badge badge-error">{failed} failed</span>}
      </summary>
      <ol className="tools-list">
        {calls.map((call, index) => (
          <li key={index} className={call.ok ? "tool ok" : "tool failed"}>
            <div className="tool-head">
              <span className="tool-status" aria-label={call.ok ? "succeeded" : "failed"}>
                {call.ok ? "✓" : "✕"}
              </span>
              <code>
                {call.name}({formatArgs(call.arguments)})
              </code>
            </div>
            {call.ok ? (
              <pre className="tool-output">{JSON.stringify(call.result, null, 2)}</pre>
            ) : (
              <p className="tool-error">{call.error}</p>
            )}
          </li>
        ))}
      </ol>
    </details>
  );
}
