# AI Business Assistant API

A FastAPI service that answers business questions in natural language. It uses the
**OpenAI Responses API with function calling**: the model decides which tool it needs, and the
**backend validates and runs every tool call**. The model never executes code itself.

## Features

| Area | Tools |
|---|---|
| Calculator | `add`, `subtract`, `multiply`, `divide` |
| Users (customer accounts) | `get_user`, `get_all_users`, `search_user` |
| Employees (staff) | `get_employee`, `search_employee`, `get_all_employees` |
| Date / time | `get_current_date`, `get_current_time` |
| Weather | `get_weather` (current conditions + 3-day forecast, via [Open-Meteo](https://open-meteo.com), no API key) |
| Text | `summarize_text`, `count_words` |

Also included:
- multiple tool calls per message, in parallel and across several rounds
- saved conversations, so follow-up questions have context
- strict JSON Schema tool definitions, checked again with Pydantic on the server
- retries with backoff for transient OpenAI errors, and clear HTTP errors when calls fail
- SQLite out of the box, PostgreSQL by changing one environment variable
- a React chat interface (see [Web interface](#web-interface-react))
- 62 backend and 7 frontend tests that run offline (no API key needed)

## Project structure

```
app/
  main.py                    FastAPI app, startup, error handlers, /health
  config.py                  Settings from environment / .env
  routes/chat.py             HTTP endpoints only (no business logic)
  services/
    openai_service.py        Responses API calls and the tool-calling loop
    tool_executor.py         Tool allow-list, argument validation, execution
    conversation_service.py  Saving and loading conversation history
  tools/                     Plain Python business functions (no AI code)
  schemas/chat.py            Request / response models
  database/
    connection.py            Engine, sessions, get_db dependency
    models.py                User, Employee, Conversation, Message
    seed.py                  Sample data
tests/                       Pytest suite with a fake OpenAI client
frontend/                    React chat UI (Vite + TypeScript)
  src/api.ts                 Typed client for the backend API
  src/useChat.ts             Chat state: messages, conversations, sending, errors
  src/components/            Sidebar, MessageList, ToolCalls, Composer
```

## Setup

Requires Python 3.10+ (developed on 3.12).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then set OPENAI_API_KEY in .env
uvicorn app.main:app --reload
```

- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

On startup, the app creates its tables and adds sample users and employees
(`SEED_ON_STARTUP=true`). To seed by hand, run `python -m app.database.seed`.

## Web interface (React)

Requires Node.js 20.19+.

**Development**: run the backend (above), then in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Vite forwards `/api` and `/health` to the backend on port 8000,
so no CORS setup is needed. To use a different backend address, set `API_TARGET`
(for example, `API_TARGET=http://localhost:9000 npm run dev`).

**Production**: build once, and FastAPI serves the app itself:

```bash
cd frontend && npm run build    # creates frontend/dist
uvicorn app.main:app            # UI at http://localhost:8000, API at /api/v1
```

If the frontend is hosted on another domain, add that domain to `CORS_ORIGINS`.

Features:
- conversation sidebar with new chat, reopening old chats, and delete (asks for confirmation)
- replies rendered as Markdown (lists, tables, code)
- a weather card (current conditions and 3-day forecast) whenever the weather tool runs
- a collapsible "Used N tools" panel under each reply, showing each tool's arguments and result
- suggested prompts, a typing indicator, and error messages from the server; if sending
  fails, the typed text is kept
- light and dark mode, and a slide-out sidebar on phones

Frontend tests: `cd frontend && npm test`.

### Using PostgreSQL

```env
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/assistant
```

On startup the app only creates tables that don't exist yet. For schema changes in
production, add a migration tool such as Alembic.

## API

### `POST /api/v1/chat`

```bash
curl -s localhost:8000/api/v1/chat \
  -H 'content-type: application/json' \
  -d '{"message": "Who works in Engineering, and what is 1250 * 12?"}'
```

```json
{
  "conversation_id": "5f0c…",
  "reply": "Neha Gupta, Vikram Singh and Rohan Mehta work in Engineering. 1250 × 12 = 15,000.",
  "model": "gpt-5.4-mini",
  "tool_calls": [
    {"name": "get_all_employees", "ok": true, "arguments": {}, "result": {"…": "…"}, "error": null},
    {"name": "multiply", "ok": true, "arguments": {"a": 1250, "b": 12},
     "result": {"result": 15000, "expression": "1250 * 12"}, "error": null}
  ]
}
```

To continue a conversation, send the same `conversation_id` with the next message.

| Endpoint | Description |
|---|---|
| `POST /api/v1/chat` | Send a message (`message`, optional `conversation_id`) |
| `GET /api/v1/conversations` | Recent conversations (title, message count, last update) |
| `GET /api/v1/conversations/{id}` | Conversation history, including the tools used |
| `DELETE /api/v1/conversations/{id}` | Delete a conversation |
| `GET /api/v1/tools` | The tools the assistant can use |
| `GET /health` | Database and configuration status |

### Error responses

| Status | When |
|---|---|
| 404 | Unknown `conversation_id` |
| 422 | Invalid request body (empty or too-long message, bad UUID) |
| 502 | OpenAI rejected the request or credentials, or returned no answer |
| 503 | `OPENAI_API_KEY` is not set, OpenAI is unreachable, or rate limiting continues after retries |
| 504 | OpenAI timed out |

## How tool calling works

1. The backend sends the conversation, a system prompt, and the 15 tool definitions to
   `client.responses.create(...)`.
2. If the response contains `function_call` items, the backend passes each one to
   `ToolExecutor.execute()`, which:
   - rejects any tool name that isn't on the allow-list,
   - parses the JSON arguments,
   - validates them with a Pydantic model (types, ranges, lengths, no extra fields),
   - runs the Python function and catches all errors.
3. The backend appends the model's output items and one `function_call_output` per call
   (matched by `call_id`), then calls the API again.
4. Steps 2–3 repeat until the model replies with text. After `MAX_TOOL_ITERATIONS` rounds,
   the backend makes one last call with `tool_choice="none"`, so the model must answer.

If a tool fails (bad arguments, record not found, division by zero), the model gets
`{"ok": false, "error": "..."}`. It can then fix its arguments or explain the problem.
Unexpected exceptions are logged on the server, and the model only sees a generic message.

### Weather

`get_weather` looks up the place with Open-Meteo's geocoding API, then fetches current
conditions and a 3-day forecast. Text after a comma narrows the match
(`"Paris, France"` vs `"Paris, Texas"`). Results are cached per place for
`WEATHER_CACHE_SECONDS`, failed connections are retried twice, and timeouts or outages
reach the model as a normal tool error. Open-Meteo is free for non-commercial use; for
commercial use, see their pricing and set `WEATHER_FORECAST_URL` to the commercial endpoint.

### Retries

The OpenAI SDK retries connection errors and 408/409/429/5xx responses with exponential
backoff, and respects `Retry-After`. Set the number of retries with `OPENAI_MAX_RETRIES`
and the timeout with `OPENAI_TIMEOUT_SECONDS`. Errors that remain are mapped to the HTTP
statuses above.

## Security notes

- API keys come only from the environment or `.env` (git ignores `.env`). Keys are stored
  as `SecretStr` and never logged.
- Only the 15 registered functions can run. Tool names and arguments from the model are
  treated as untrusted input.
- Database tools are read-only and use parameterized queries. `LIKE` wildcards in searches
  are escaped.
- List results are capped at 100 rows, and messages and tool text have length limits.
- A user message and its reply are saved together, so a failed request leaves nothing behind.
- This API has **no authentication**. Before exposing it publicly, add auth (an API key
  header or OAuth) and rate limiting.

## Configuration

See [.env.example](.env.example) for all settings. The main ones:

| Variable | Default | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | — | Required for `/chat` |
| `OPENAI_MODEL` | `gpt-5.4-mini` | Any Responses API model that supports function calling |
| `OPENAI_MAX_RETRIES` | `3` | SDK retry count |
| `MAX_TOOL_ITERATIONS` | `6` | Max model ↔ tool rounds per message |
| `DATABASE_URL` | `sqlite:///./assistant.db` | SQLAlchemy URL |
| `HISTORY_LIMIT` | `20` | Earlier messages sent as context |
| `TIMEZONE` | `UTC` | Timezone for the date and time tools |
| `WEATHER_TEMPERATURE_UNIT` | `celsius` | `celsius` or `fahrenheit` |
| `WEATHER_CACHE_SECONDS` | `600` | How long weather for a place is cached |

## Tests

```bash
pytest
```

The tests replace the OpenAI client with a scripted fake and use an in-memory SQLite
database, so they make no network calls. They cover each tool, the executor's validation
and allow-list, the tool-calling loop (single, parallel and multi-round calls, the iteration
limit, error mapping), and the HTTP API (persistence, history, 404/422/503).

## Adding a tool

1. Write a plain function in `app/tools/` (take `db: Session` first if it needs the database).
   Raise `ToolError` for failures the model should see.
2. Add a Pydantic argument model and a `ToolSpec` entry to `TOOLS` in
   `app/services/tool_executor.py`. The JSON Schema sent to OpenAI is generated from the
   argument model.
3. Add tests.
