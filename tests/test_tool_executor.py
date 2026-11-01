import json

from app.services.tool_executor import ToolExecutor, ToolSpec, TwoNumbers

EXPECTED_TOOLS = {
    "add", "subtract", "multiply", "divide",
    "get_user", "get_all_users", "search_user",
    "get_employee", "search_employee", "get_all_employees",
    "get_current_date", "get_current_time",
    "get_weather",
    "summarize_text", "count_words",
}


def test_all_tools_registered():
    assert {d["name"] for d in ToolExecutor().definitions()} == EXPECTED_TOOLS


def test_definitions_are_strict_json_schema():
    for definition in ToolExecutor().definitions():
        params = definition["parameters"]
        assert definition["type"] == "function" and definition["strict"] is True
        assert params["type"] == "object"
        assert params["additionalProperties"] is False
        assert set(params["required"]) == set(params["properties"])
        for prop in params["properties"].values():
            assert prop["type"] in {"number", "integer", "string"}
            assert prop["description"]


def test_successful_call():
    result = ToolExecutor().execute("multiply", '{"a": 1250, "b": 12}')
    assert result.ok and result.output["result"] == 15000
    assert json.loads(result.to_model_output()) == {"ok": True, "result": result.output}


def test_unknown_tool_is_rejected():
    result = ToolExecutor().execute("os_system", '{"cmd": "rm -rf /"}')
    assert not result.ok and "Unknown tool" in result.error


def test_invalid_json():
    result = ToolExecutor().execute("add", "{not json")
    assert not result.ok and "not valid JSON" in result.error


def test_non_object_arguments():
    assert "JSON object" in ToolExecutor().execute("add", "[1, 2]").error


def test_validation_errors_are_reported_to_model():
    executor = ToolExecutor()
    assert "a:" in executor.execute("add", '{"a": "abc", "b": 1}').error
    assert "user_id" in executor.execute("get_user", '{"user_id": -5}').error


def test_extra_arguments_rejected():
    result = ToolExecutor().execute("add", '{"a": 1, "b": 2, "c": 3}')
    assert not result.ok and "c:" in result.error


def test_tool_error_becomes_error_result():
    result = ToolExecutor().execute("divide", '{"a": 1, "b": 0}')
    assert not result.ok and result.error == "Division by zero is not allowed."
    assert json.loads(result.to_model_output()) == {"ok": False, "error": result.error}


def test_db_tool(db):
    result = ToolExecutor().execute("search_employee", '{"name": "  singh "}', db=db)
    assert result.ok and result.output["employees"][0]["name"] == "Vikram Singh"


def test_db_tool_without_session():
    assert ToolExecutor().execute("get_all_users", "{}").error == "Database is unavailable."


def test_empty_arguments_for_no_arg_tool():
    assert ToolExecutor().execute("get_current_date", "").ok


def test_unexpected_exception_is_contained():
    def boom(a, b):
        raise RuntimeError("secret internal detail")

    executor = ToolExecutor((ToolSpec("add", "Add.", TwoNumbers, boom),))
    result = executor.execute("add", '{"a": 1, "b": 2}')
    assert not result.ok
    assert "secret" not in result.error
