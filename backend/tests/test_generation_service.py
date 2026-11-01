import httpx
import pytest

from backend.app.services.generation_service import (
    GenerationError,
    OllamaGenerationService,
)


def make_service(handler):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return OllamaGenerationService(
        base_url="http://localhost:11434",
        model="qwen3:4b",
        client=client,
    )


def test_generates_answer_and_sends_expected_payload():
    def handler(request):
        assert request.url.path == "/api/chat"

        payload = request.read().decode()
        assert '"model":"qwen3:4b"' in payload.replace(" ", "")
        assert '"stream":false' in payload.replace(" ", "")

        return httpx.Response(
            200,
            json={"message": {"content": "  Grounded answer.  "}},
        )

    service = make_service(handler)
    try:
        result = service.generate("You are helpful.", "What is RAG?")
        assert result == "Grounded answer."
    finally:
        service.close()


def test_rejects_empty_prompts():
    service = make_service(
        lambda request: httpx.Response(200, json={})
    )
    try:
        with pytest.raises(ValueError):
            service.generate("", "Question")
    finally:
        service.close()


def test_rejects_empty_model_name():
    with pytest.raises(ValueError):
        OllamaGenerationService(
            base_url="http://localhost:11434",
            model=" ",
        )


def test_rejects_invalid_temperature():
    with pytest.raises(ValueError):
        OllamaGenerationService(
            base_url="http://localhost:11434",
            model="qwen3:4b",
            temperature=3,
        )


def test_rejects_empty_model_response():
    service = make_service(
        lambda request: httpx.Response(
            200,
            json={"message": {"content": "  "}},
        )
    )
    try:
        with pytest.raises(GenerationError):
            service.generate("System", "Question")
    finally:
        service.close()


def test_handles_http_failure():
    service = make_service(
        lambda request: httpx.Response(503)
    )
    try:
        with pytest.raises(GenerationError):
            service.generate("System", "Question")
    finally:
        service.close()


def test_handles_invalid_json_response():
    service = make_service(
        lambda request: httpx.Response(
            200,
            content=b"not-json",
        )
    )
    try:
        with pytest.raises(GenerationError):
            service.generate("System", "Question")
    finally:
        service.close()


def test_handles_missing_message():
    service = make_service(
        lambda request: httpx.Response(200, json={})
    )
    try:
        with pytest.raises(GenerationError):
            service.generate("System", "Question")
    finally:
        service.close()


def test_default_client_uses_separate_connection_and_read_timeouts():
    service = OllamaGenerationService(
        base_url="http://localhost:11434",
        model="qwen3:4b",
        timeout=600,
        connect_timeout=5,
    )
    try:
        assert service.client.timeout.read == 600
        assert service.client.timeout.connect == 5
    finally:
        service.close()


def test_rejects_invalid_connection_timeout():
    with pytest.raises(ValueError):
        OllamaGenerationService(
            base_url="http://localhost:11434",
            model="qwen3:4b",
            connect_timeout=0,
        )

