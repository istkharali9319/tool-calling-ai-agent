import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

type Handler = (url: string, init?: RequestInit) => { status?: number; body?: unknown };

const json = (status: number, body: unknown) =>
  new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

/** Routes fetch calls to handlers keyed by "METHOD path". */
function mockApi(routes: Record<string, Handler>) {
  const calls: { key: string; body: unknown }[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    const key = `${init?.method ?? "GET"} ${url}`;
    calls.push({ key, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    const handler = routes[key];
    if (!handler) return json(404, { detail: `No mock for ${key}` });
    const { status = 200, body } = handler(url, init);
    return json(status, body);
  });
  return calls;
}

const HEALTH = { status: "ok", database: "ok", openai_configured: true, model: "gpt-test" };

describe("App", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("sends a message and shows the reply with the tools used", async () => {
    let conversations: unknown[] = [];
    const calls = mockApi({
      "GET /health": () => ({ body: HEALTH }),
      "GET /api/v1/conversations": () => ({ body: conversations }),
      "POST /api/v1/chat": () => {
        conversations = [
          { conversation_id: "c1", title: "What is 1250 * 12?", message_count: 2, updated_at: new Date().toISOString() },
        ];
        return {
          body: {
            conversation_id: "c1",
            reply: "1250 × 12 = **15,000**",
            model: "gpt-test",
            tool_calls: [
              { name: "multiply", ok: true, arguments: { a: 1250, b: 12 }, result: { result: 15000 }, error: null },
            ],
          },
        };
      },
    });
    const user = userEvent.setup();
    render(<App />);

    expect(await screen.findByText("gpt-test")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Message"), "What is 1250 * 12?{Enter}");

    expect(await screen.findByText("15,000")).toBeInTheDocument(); // rendered from markdown bold
    expect(screen.getByText(/Used 1 tool/)).toBeInTheDocument();
    expect(screen.getByText("multiply(a=1250, b=12)")).toBeInTheDocument();
    expect(calls.find((c) => c.key === "POST /api/v1/chat")?.body).toEqual({
      message: "What is 1250 * 12?",
      conversation_id: null,
    });

    // The new conversation appears in the sidebar.
    const sidebar = screen.getByRole("complementary", { name: "Conversations" });
    expect(await within(sidebar).findByText("What is 1250 * 12?")).toBeInTheDocument();
  });

  it("continues the same conversation on the next message", async () => {
    let n = 0;
    const calls = mockApi({
      "GET /health": () => ({ body: HEALTH }),
      "GET /api/v1/conversations": () => ({ body: [] }),
      "POST /api/v1/chat": () => ({
        body: { conversation_id: "c9", reply: `Reply ${++n}`, model: "gpt-test", tool_calls: [] },
      }),
    });
    const user = userEvent.setup();
    render(<App />);

    await user.type(screen.getByLabelText("Message"), "First{Enter}");
    await screen.findByText("Reply 1");
    await user.type(screen.getByLabelText("Message"), "Second{Enter}");
    await screen.findByText("Reply 2");

    const chatBodies = calls.filter((c) => c.key === "POST /api/v1/chat").map((c) => c.body);
    expect(chatBodies).toEqual([
      { message: "First", conversation_id: null },
      { message: "Second", conversation_id: "c9" },
    ]);
  });

  it("shows the server error and keeps the typed text when sending fails", async () => {
    mockApi({
      "GET /health": () => ({ body: HEALTH }),
      "GET /api/v1/conversations": () => ({ body: [] }),
      "POST /api/v1/chat": () => ({ status: 503, body: { detail: "The AI provider is rate limiting requests." } }),
    });
    const user = userEvent.setup();
    render(<App />);

    const input = screen.getByLabelText("Message");
    await user.type(input, "Hello{Enter}");

    expect(await screen.findByRole("alert")).toHaveTextContent("rate limiting");
    await waitFor(() => expect(input).toHaveValue("Hello"));
    expect(screen.queryByText("Hello", { selector: ".plain" })).not.toBeInTheDocument();
  });

  it("shows a weather card when the weather tool ran", async () => {
    mockApi({
      "GET /health": () => ({ body: HEALTH }),
      "GET /api/v1/conversations": () => ({ body: [] }),
      "POST /api/v1/chat": () => ({
        body: {
          conversation_id: "w1",
          reply: "It's partly cloudy in Mumbai, 34°C.",
          model: "gpt-test",
          tool_calls: [
            {
              name: "get_weather",
              ok: true,
              arguments: { location: "Mumbai" },
              error: null,
              result: {
                location: { name: "Mumbai", region: "Maharashtra", country: "India", timezone: "Asia/Kolkata" },
                current: {
                  time: "2026-11-01T13:00", condition: "Partly cloudy", weather_code: 2, is_day: true,
                  temperature: 34.0, feels_like: 37.3, humidity: 55, wind_speed: 12.0,
                },
                daily: [
                  { date: "2026-11-01", condition: "Partly cloudy", weather_code: 2, temperature_max: 35, temperature_min: 26, precipitation_probability: 10 },
                  { date: "2026-11-02", condition: "Slight rain", weather_code: 61, temperature_max: 33, temperature_min: 25, precipitation_probability: 60 },
                ],
                units: { temperature: "°C", wind_speed: "km/h" },
              },
            },
          ],
        },
      }),
    });
    const user = userEvent.setup();
    render(<App />);

    await user.type(screen.getByLabelText("Message"), "Weather in Mumbai?{Enter}");

    const card = await screen.findByRole("region", { name: "Weather in Mumbai" });
    expect(within(card).getByText("Maharashtra, India")).toBeInTheDocument();
    expect(within(card).getByText("Partly cloudy", { selector: "strong" })).toBeInTheDocument();
    expect(within(card).getByText(/Humidity 55% · Wind 12 km\/h/)).toBeInTheDocument();
    expect(within(card).getByText("Today")).toBeInTheDocument();
    expect(within(card).getByText("💧 60%")).toBeInTheDocument();
  });

  it("warns when the backend has no OpenAI key", async () => {
    mockApi({
      "GET /health": () => ({ body: { ...HEALTH, openai_configured: false } }),
      "GET /api/v1/conversations": () => ({ body: [] }),
    });
    render(<App />);
    expect(await screen.findByText(/has no OpenAI API key/)).toBeInTheDocument();
  });

  it("opens a saved conversation from the sidebar", async () => {
    mockApi({
      "GET /health": () => ({ body: HEALTH }),
      "GET /api/v1/conversations": () => ({
        body: [{ conversation_id: "old", title: "Find Sara", message_count: 2, updated_at: "2026-01-01T10:00:00" }],
      }),
      "GET /api/v1/conversations/old": () => ({
        body: {
          conversation_id: "old",
          messages: [
            { id: 1, role: "user", content: "Find Sara", tool_calls: null, created_at: "2026-01-01T10:00:00" },
            {
              id: 2,
              role: "assistant",
              content: "Sara Khan is a manager.",
              tool_calls: [{ name: "search_user", ok: true, arguments: { name: "Sara" }, result: {}, error: null }],
              created_at: "2026-01-01T10:00:01",
            },
          ],
        },
      }),
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: /^Find Sara/ }));

    expect(await screen.findByText("Sara Khan is a manager.")).toBeInTheDocument();
    expect(screen.getByText(/Used 1 tool/)).toBeInTheDocument();
  });

  it("asks for confirmation before deleting a conversation", async () => {
    const calls = mockApi({
      "GET /health": () => ({ body: HEALTH }),
      "GET /api/v1/conversations": () => ({
        body: [{ conversation_id: "x", title: "Old chat", message_count: 2, updated_at: "2026-01-01T10:00:00" }],
      }),
      "DELETE /api/v1/conversations/x": () => ({ status: 204 }),
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: 'Delete "Old chat"' }));
    expect(calls.some((c) => c.key.startsWith("DELETE"))).toBe(false);

    await user.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(screen.queryByText("Old chat")).not.toBeInTheDocument());
    expect(calls.some((c) => c.key === "DELETE /api/v1/conversations/x")).toBe(true);
  });
});
