import math

from app.tools import ToolError


def _clean(value: float) -> int | float:
    """Show whole numbers without a trailing ".0"."""
    return int(value) if value.is_integer() and abs(value) < 2**53 else value


def _result(value: float, a: float, op: str, b: float) -> dict:
    if not math.isfinite(value):
        raise ToolError("The result is too large to represent.")
    return {"result": _clean(value), "expression": f"{_clean(a)} {op} {_clean(b)}"}


def add(a: float, b: float) -> dict:
    return _result(a + b, a, "+", b)


def subtract(a: float, b: float) -> dict:
    return _result(a - b, a, "-", b)


def multiply(a: float, b: float) -> dict:
    return _result(a * b, a, "*", b)


def divide(a: float, b: float) -> dict:
    if b == 0:
        raise ToolError("Division by zero is not allowed.")
    return _result(a / b, a, "/", b)
