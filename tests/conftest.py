import json
import os
from types import SimpleNamespace
from typing import Any

# Configure the app for tests before any app module is imported.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SEED_ON_STARTUP"] = "false"
os.environ["OPENAI_API_KEY"] = ""
os.environ["TIMEZONE"] = "UTC"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import models  # noqa: E402,F401
from app.database.connection import Base, SessionLocal, engine  # noqa: E402
from app.database.seed import seed_database  # noqa: E402
from app.main import app  # noqa: E402
from app.services.openai_service import OpenAIService, get_openai_service  # noqa: E402


# --- Fake OpenAI client --------------------------------------------------------------------


def function_call(name: str, arguments: dict | str, call_id: str = "call_1") -> SimpleNamespace:
    args = arguments if isinstance(arguments, str) else json.dumps(arguments)
    return SimpleNamespace(type="function_call", name=name, arguments=args, call_id=call_id, id=f"fc_{call_id}")


def tool_response(*calls: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(id="resp_tools", model="test-model", status="completed", output=list(calls), output_text="")


def text_response(text: str) -> SimpleNamespace:
    message = SimpleNamespace(type="message", role="assistant", content=[])
    return SimpleNamespace(id="resp_text", model="test-model", status="completed", output=[message], output_text=text)


class FakeResponses:
    """Returns scripted responses in order (or raises scripted exceptions) and records requests."""

    def __init__(self, scripted: list[Any]) -> None:
        self.scripted = list(scripted)
        self.requests: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.requests.append({**kwargs, "input": list(kwargs["input"])})
        item = self.scripted.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeClient:
    def __init__(self, scripted: list[Any]) -> None:
        self.responses = FakeResponses(scripted)


def make_service(scripted: list[Any], **kwargs: Any) -> tuple[OpenAIService, FakeClient]:
    client = FakeClient(scripted)
    return OpenAIService(client=client, model="test-model", **kwargs), client


# --- Fixtures ------------------------------------------------------------------------------


@pytest.fixture
def db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    session = SessionLocal()
    seed_database(session)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def use_fake_ai():
    """Install a fake-backed OpenAIService for API tests. Returns the fake client."""

    def install(scripted: list[Any]) -> FakeClient:
        service, fake = make_service(scripted)
        app.dependency_overrides[get_openai_service] = lambda: service
        return fake

    return install
