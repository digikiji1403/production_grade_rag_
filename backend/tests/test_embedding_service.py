import httpx
import pytest

from backend.app.services.embedding_service import (
    EmbeddingError,
    OllamaEmbeddingService,
)


def make_service(handler, batch_size=32):
    client = httpx.Client(
        transport=httpx.MockTransport(handler)
    )

    return OllamaEmbeddingService(
        base_url="http://localhost:11434",
        model="embeddinggemma",
        dimensions=3,
        batch_size=batch_size,
        client=client,
    )


def test_embed_texts_returns_vectors():
    def handler(request):
        assert request.url.path == "/api/embed"
        assert request.read()
        return httpx.Response(
            200,
            json={"embeddings": [[0.1, 0.2, 0.3]]},
        )

    service = make_service(handler)

    try:
        result = service.embed_texts(["hello"])

        assert len(result) == 1
        assert len(result[0]) == 3
        assert result[0] == [0.1, 0.2, 0.3]
    finally:
        service.close()


def test_empty_input_returns_empty_list():
    service = make_service(lambda request: httpx.Response(200))

    try:
        assert service.embed_texts([]) == []
    finally:
        service.close()


def test_blank_input_is_rejected():
    service = make_service(lambda request: httpx.Response(200))

    try:
        with pytest.raises(ValueError):
            service.embed_texts(["hello", "  "])
    finally:
        service.close()


def test_batches_large_input():
    import json

    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(len(body["input"]))

        return httpx.Response(
            200,
            json={
                "embeddings": [
                    [0.1, 0.2, 0.3] for _ in body["input"]
                ]
            },
        )

    service = make_service(handler, batch_size=2)

    try:
        result = service.embed_texts(["a", "b", "c", "d", "e"])

        assert calls == [2, 2, 1]
        assert len(result) == 5
    finally:
        service.close()


def test_invalid_vector_dimension_is_rejected():
    def handler(request):
        return httpx.Response(
            200,
            json={"embeddings": [[0.1, 0.2]]},
        )

    service = make_service(handler)

    try:
        with pytest.raises(EmbeddingError):
            service.embed_texts(["hello"])
    finally:
        service.close()


def test_non_finite_vector_value_is_rejected():
    def handler(request):
        return httpx.Response(
            200,
            json={"embeddings": [[0.1, float("nan"), 0.3]]},
        )

    service = make_service(handler)

    try:
        with pytest.raises(EmbeddingError):
            service.embed_texts(["hello"])
    finally:
        service.close()


def test_ollama_http_error_is_wrapped():
    def handler(request):
        return httpx.Response(500)

    service = make_service(handler)

    try:
        with pytest.raises(EmbeddingError):
            service.embed_texts(["hello"])
    finally:
        service.close()
