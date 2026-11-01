from tests.conftest import function_call, text_response, tool_response


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["database"] == "ok"


def test_chat_without_api_key_returns_503(client):
    response = client.post("/api/v1/chat", json={"message": "Hi"})
    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.json()["detail"]


def test_chat_runs_tool_and_persists_turn(client, use_fake_ai):
    use_fake_ai([
        tool_response(function_call("get_employee", {"employee_id": 2})),
        text_response("Employee 2 is Vikram Singh, Engineering Manager."),
    ])

    response = client.post("/api/v1/chat", json={"message": "Who is employee 2?"})

    assert response.status_code == 200
    body = response.json()
    assert body["reply"].startswith("Employee 2 is Vikram Singh")
    assert body["tool_calls"][0]["name"] == "get_employee"
    assert body["tool_calls"][0]["result"]["job_title"] == "Engineering Manager"

    history = client.get(f"/api/v1/conversations/{body['conversation_id']}").json()
    assert [m["role"] for m in history["messages"]] == ["user", "assistant"]
    assert history["messages"][1]["tool_calls"][0]["name"] == "get_employee"


def test_follow_up_message_includes_history(client, use_fake_ai):
    fake = use_fake_ai([text_response("Nice to meet you, Sam."), text_response("You are Sam.")])
    first = client.post("/api/v1/chat", json={"message": "I am Sam."}).json()

    client.post("/api/v1/chat", json={"message": "Who am I?", "conversation_id": first["conversation_id"]})

    assert fake.responses.requests[1]["input"] == [
        {"role": "user", "content": "I am Sam."},
        {"role": "assistant", "content": "Nice to meet you, Sam."},
        {"role": "user", "content": "Who am I?"},
    ]


def test_failed_ai_call_saves_nothing(client, use_fake_ai, db):
    from app.database.models import Conversation

    use_fake_ai([text_response("")])
    assert client.post("/api/v1/chat", json={"message": "Hi"}).status_code == 502
    assert db.query(Conversation).count() == 0


def test_unknown_conversation_returns_404(client, use_fake_ai):
    use_fake_ai([text_response("unused")])
    response = client.post(
        "/api/v1/chat",
        json={"message": "Hi", "conversation_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 404


def test_request_validation(client, use_fake_ai):
    use_fake_ai([])
    assert client.post("/api/v1/chat", json={"message": "   "}).status_code == 422
    assert client.post("/api/v1/chat", json={"message": "x" * 8001}).status_code == 422
    assert client.post("/api/v1/chat", json={"message": "hi", "conversation_id": "bad"}).status_code == 422


def test_delete_conversation(client, use_fake_ai):
    use_fake_ai([text_response("Hello")])
    conversation_id = client.post("/api/v1/chat", json={"message": "Hi"}).json()["conversation_id"]

    assert client.delete(f"/api/v1/conversations/{conversation_id}").status_code == 204
    assert client.get(f"/api/v1/conversations/{conversation_id}").status_code == 404


def test_list_conversations_newest_first(client, use_fake_ai):
    use_fake_ai([text_response("A"), text_response("B")])
    first = client.post("/api/v1/chat", json={"message": "First   question"}).json()
    second = client.post("/api/v1/chat", json={"message": "x" * 100}).json()

    listed = client.get("/api/v1/conversations").json()

    assert [c["conversation_id"] for c in listed] == [second["conversation_id"], first["conversation_id"]]
    assert listed[1]["title"] == "First question"
    assert listed[0]["title"] == "x" * 60 + "…"
    assert listed[0]["message_count"] == 2


def test_list_tools(client):
    names = {tool["name"] for tool in client.get("/api/v1/tools").json()}
    assert len(names) == 15 and "summarize_text" in names
