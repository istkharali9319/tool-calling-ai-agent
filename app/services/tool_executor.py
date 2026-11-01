"""Tool registry and executor.

The model only *requests* a tool call (a name plus JSON arguments). This module is the only
place that turns such a request into a Python call, and it:
  1. accepts only tools in the allow-list below,
  2. parses the JSON arguments,
  3. validates them with a Pydantic model (types, ranges, lengths, no extra fields),
  4. runs the function and returns a structured result.
Failures become error results that are sent back to the model, never exceptions that escape.
"""

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, StringConstraints, ValidationError
from sqlalchemy.orm import Session

from app.tools import (
    ToolError,
    calculator,
    date_tools,
    employee_tools,
    summary_tools,
    user_tools,
    weather_tools,
)

logger = logging.getLogger(__name__)

MAX_ARGUMENT_BYTES = 100_000


# ---------------------------------------------------------------------------
# Argument models (the validation contract for every tool)
# ---------------------------------------------------------------------------


class ToolArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NoArgs(ToolArgs):
    pass


class TwoNumbers(ToolArgs):
    a: FiniteFloat = Field(description="The first number.")
    b: FiniteFloat = Field(description="The second number.")


class Divide(ToolArgs):
    a: FiniteFloat = Field(description="The dividend (number to be divided).")
    b: FiniteFloat = Field(description="The divisor. Must not be zero.")


class UserId(ToolArgs):
    user_id: int = Field(gt=0, description="The numeric ID of the user.")


class EmployeeId(ToolArgs):
    employee_id: int = Field(gt=0, description="The numeric ID of the employee.")


SearchName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class NameQuery(ToolArgs):
    name: SearchName = Field(description="Full or partial name to search for (case-insensitive).")


class LocationQuery(ToolArgs):
    location: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)] = Field(
        description="City or place name, optionally followed by a comma and the country or region, "
        "e.g. 'Mumbai', 'Paris, France' or 'Portland, Oregon'."
    )


class TextInput(ToolArgs):
    text: Annotated[str, StringConstraints(min_length=1, max_length=50_000)] = Field(
        description="The text to process."
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    args_model: type[ToolArgs]
    func: Callable[..., Any]
    needs_db: bool = False

    def definition(self) -> dict[str, Any]:
        """OpenAI Responses API function-tool definition (strict JSON Schema)."""
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": _strict_schema(self.args_model),
            "strict": True,
        }


def _strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Build a JSON Schema that satisfies OpenAI strict mode: every property required and no
    additional properties. Only type/description are sent; range and length limits are
    enforced by Pydantic on our side, which is the check that counts."""
    properties = {
        name: {key: prop[key] for key in ("type", "description", "enum") if key in prop}
        for name, prop in model.model_json_schema().get("properties", {}).items()
    }
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec("add", "Add two numbers (a + b).", TwoNumbers, calculator.add),
    ToolSpec("subtract", "Subtract b from a (a - b).", TwoNumbers, calculator.subtract),
    ToolSpec("multiply", "Multiply two numbers (a * b).", TwoNumbers, calculator.multiply),
    ToolSpec("divide", "Divide a by b (a / b).", Divide, calculator.divide),
    ToolSpec(
        "get_user", "Look up one user (customer account) by numeric ID.",
        UserId, user_tools.get_user, needs_db=True,
    ),
    ToolSpec(
        "get_all_users", "List all users (customer accounts).",
        NoArgs, user_tools.get_all_users, needs_db=True,
    ),
    ToolSpec(
        "search_user", "Find users whose name contains the given text.",
        NameQuery, user_tools.search_user, needs_db=True,
    ),
    ToolSpec(
        "get_employee", "Look up one company employee by numeric ID.",
        EmployeeId, employee_tools.get_employee, needs_db=True,
    ),
    ToolSpec(
        "search_employee", "Find employees whose name contains the given text.",
        NameQuery, employee_tools.search_employee, needs_db=True,
    ),
    ToolSpec(
        "get_all_employees", "List all company employees.",
        NoArgs, employee_tools.get_all_employees, needs_db=True,
    ),
    ToolSpec(
        "get_current_date", "Get today's date and day of the week.",
        NoArgs, date_tools.get_current_date,
    ),
    ToolSpec(
        "get_current_time", "Get the current time.",
        NoArgs, date_tools.get_current_time,
    ),
    ToolSpec(
        "get_weather",
        "Get the current weather and a 3-day forecast for a city or place.",
        LocationQuery, weather_tools.get_weather,
    ),
    ToolSpec(
        "summarize_text", "Produce a short extractive summary of a piece of text.",
        TextInput, summary_tools.summarize_text,
    ),
    ToolSpec(
        "count_words", "Count the words, characters and sentences in a piece of text.",
        TextInput, summary_tools.count_words,
    ),
)


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


@dataclass
class ToolResult:
    name: str
    ok: bool
    arguments: dict[str, Any] = field(default_factory=dict)
    output: Any = None
    error: str | None = None

    def to_model_output(self) -> str:
        """The string sent back to the model as the function_call_output."""
        payload = {"ok": True, "result": self.output} if self.ok else {"ok": False, "error": self.error}
        return json.dumps(payload, default=str)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ok": self.ok,
            "arguments": self.arguments,
            "result": self.output,
            "error": self.error,
        }


class ToolExecutor:
    def __init__(self, tools: tuple[ToolSpec, ...] = TOOLS) -> None:
        self._tools = {tool.name: tool for tool in tools}

    @property
    def tools(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def definitions(self) -> list[dict[str, Any]]:
        return [tool.definition() for tool in self._tools.values()]

    def execute(self, name: str, raw_arguments: str | None, db: Session | None = None) -> ToolResult:
        started = time.perf_counter()
        result = self._execute(name, raw_arguments, db)
        logger.info(
            "tool=%s ok=%s duration_ms=%.1f%s",
            name, result.ok, (time.perf_counter() - started) * 1000,
            "" if result.ok else f" error={result.error!r}",
        )
        return result

    def _execute(self, name: str, raw_arguments: str | None, db: Session | None) -> ToolResult:
        spec = self._tools.get(name)
        if spec is None:
            return ToolResult(name=name, ok=False, error=f"Unknown tool '{name}'.")

        raw = raw_arguments or "{}"
        if len(raw.encode()) > MAX_ARGUMENT_BYTES:
            return ToolResult(name=name, ok=False, error="Tool arguments are too large.")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return ToolResult(name=name, ok=False, error="Tool arguments are not valid JSON.")
        if not isinstance(parsed, dict):
            return ToolResult(name=name, ok=False, error="Tool arguments must be a JSON object.")

        try:
            args = spec.args_model.model_validate(parsed)
        except ValidationError as exc:
            problems = "; ".join(
                f"{'.'.join(str(p) for p in err['loc']) or 'arguments'}: {err['msg']}"
                for err in exc.errors()
            )
            return ToolResult(name=name, ok=False, arguments=parsed, error=f"Invalid arguments: {problems}")

        kwargs = args.model_dump()
        if spec.needs_db:
            if db is None:
                return ToolResult(name=name, ok=False, arguments=kwargs, error="Database is unavailable.")
            kwargs_with_db = {"db": db, **kwargs}
        else:
            kwargs_with_db = kwargs

        try:
            output = spec.func(**kwargs_with_db)
        except ToolError as exc:
            return ToolResult(name=name, ok=False, arguments=kwargs, error=str(exc))
        except Exception:
            logger.exception("Tool %s raised an unexpected error", name)
            if db is not None:
                db.rollback()  # PostgreSQL rejects further queries in a failed transaction
            return ToolResult(name=name, ok=False, arguments=kwargs, error="The tool failed unexpectedly.")

        return ToolResult(name=name, ok=True, arguments=kwargs, output=output)
