import httpx2
import openai
import pytest

from app.services.openai_service import AIServiceError, OpenAIService
from app.config import Settings
from tests.conftest import function_call, make_service, text_response, tool_response

REQUEST = httpx2.Request("POST", "https://api.openai.com/v1/responses")


def test_plain_answer_without_tools():
    service, fake = make_service([text_response("Hello!")])
    reply = service.generate_reply(None, [], "Hi")
    assert reply.text == "Hello!" and reply.tool_calls == []

    request = fake.responses.requests[0]
    assert request["model"] == "test-model"
    assert request["input"] == [{"role": "user", "content": "Hi"}]
    assert {t["name"] for t in request["tools"]} >= {"add", "get_user"}
    assert request["instructions"]


def test_tool_call_round_trip():
    call = function_call("multiply", {"a": 1250, "b": 12}, call_id="call_abc")
    service, fake = make_service([tool_response(call), text_response("1250 x 12 = 15000.")])

    reply = service.generate_reply(None, [], "What is 1250 times 12?")

    assert reply.text == "1250 x 12 = 15000."
    assert [(c.name, c.ok, c.output["result"]) for c in reply.tool_calls] == [("multiply", True, 15000)]

    second_input = fake.responses.requests[1]["input"]
    assert call in second_input  # the model's function_call item is sent back
    output = second_input[-1]
    assert output["type"] == "function_call_output" and output["call_id"] == "call_abc"
    assert '"result": 15000' in output["output"]


def test_parallel_and_sequential_tool_calls(db):
    first = tool_response(
        function_call("search_employee", {"name": "Neha"}, "c1"),
        function_call("get_current_date", {}, "c2"),
    )
    second = tool_response(function_call("add", {"a": 2, "b": 3}, "c3"))
    service, fake = make_service([first, second, text_response("Done.")])

    reply = service.generate_reply(db, [], "Find Neha, today's date, and 2+3")

    assert [c.name for c in reply.tool_calls] == ["search_employee", "get_current_date", "add"]
    assert all(c.ok for c in reply.tool_calls)
    outputs = [i for i in fake.responses.requests[2]["input"] if isinstance(i, dict) and i.get("type") == "function_call_output"]
    assert [o["call_id"] for o in outputs] == ["c1", "c2", "c3"]


def test_invalid_tool_call_returns_error_to_model():
    call = function_call("get_user", {"user_id": "not-a-number"})
    service, fake = make_service([tool_response(call), text_response("Sorry, that ID is invalid.")])

    reply = service.generate_reply(None, [], "Get user abc")

    assert not reply.tool_calls[0].ok
    assert '"ok": false' in fake.responses.requests[1]["input"][-1]["output"]


def test_unknown_tool_is_never_executed():
    call = function_call("delete_all_users", {})
    service, _ = make_service([tool_response(call), text_response("I can't do that.")])
    reply = service.generate_reply(None, [], "Delete everyone")
    assert reply.tool_calls[0].error == "Unknown tool 'delete_all_users'."


def test_iteration_limit_forces_final_answer():
    looping = [tool_response(function_call("get_current_time", {}, f"c{i}")) for i in range(2)]
    service, fake = make_service([*looping, text_response("It is noon.")], max_tool_iterations=2)

    reply = service.generate_reply(None, [], "Time?")

    assert reply.text == "It is noon."
    assert len(fake.responses.requests) == 3
    assert fake.responses.requests[-1]["tool_choice"] == "none"


def test_history_is_sent_before_new_message():
    history = [{"role": "user", "content": "My name is Sam."}, {"role": "assistant", "content": "Hi Sam!"}]
    service, fake = make_service([text_response("Your name is Sam.")])
    service.generate_reply(None, history, "What's my name?")
    assert fake.responses.requests[0]["input"] == [*history, {"role": "user", "content": "What's my name?"}]


def test_empty_model_output_raises():
    service, _ = make_service([text_response("")])
    with pytest.raises(AIServiceError) as exc:
        service.generate_reply(None, [], "Hi")
    assert exc.value.status_code == 502


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (openai.APITimeoutError(request=REQUEST), 504),
        (openai.APIConnectionError(request=REQUEST), 503),
        (openai.RateLimitError("slow down", response=httpx2.Response(429, request=REQUEST), body=None), 503),
        (openai.AuthenticationError("bad key", response=httpx2.Response(401, request=REQUEST), body=None), 502),
        (openai.InternalServerError("boom", response=httpx2.Response(500, request=REQUEST), body=None), 502),
    ],
)
def test_openai_errors_are_mapped(error, status):
    service, _ = make_service([error])
    with pytest.raises(AIServiceError) as exc:
        service.generate_reply(None, [], "Hi")
    assert exc.value.status_code == status


def test_missing_api_key():
    with pytest.raises(AIServiceError) as exc:
        OpenAIService.from_settings(Settings(openai_api_key=""))
    assert exc.value.status_code == 503


def test_client_is_configured_from_settings():
    settings = Settings(openai_api_key="sk-test", openai_max_retries=5, openai_timeout_seconds=12)
    service = OpenAIService.from_settings(settings)
    assert service._client.max_retries == 5
    assert service._client.timeout == 12
