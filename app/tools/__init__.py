"""Plain Python business functions the assistant can ask the backend to run."""


class ToolError(Exception):
    """An expected failure the model should see and can recover from (e.g. "user not found")."""
