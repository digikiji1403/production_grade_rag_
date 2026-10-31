import math

import httpx


class EmbeddingError(Exception):
    """Raised when text cannot be converted into valid embeddings."""


class OllamaEmbeddingService:
    """Generate text embeddings through Ollama's local API."""

    def __init__(
        self,
        base_url: str,
        model: str,
        dimensions: int,
        batch_size: int = 32,
        timeout: float = 120.0,
        client: httpx.Client | None = None,
    ):
        if dimensions <= 0:
            raise ValueError("Embedding dimensions must be positive.")
        if batch_size <= 0:
            raise ValueError("Batch size must be positive.")

        self.base_url = base_url.rstrip("/")
        self.model = model
        self.dimensions = dimensions
        self.batch_size = batch_size
        self.client = client or httpx.Client(timeout=timeout)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed texts in batches and validate every returned vector."""

        if not texts:
            return []

        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise ValueError("Every input must be a non-empty string.")

        vectors = []

        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]

            try:
                response = self.client.post(
                    f"{self.base_url}/api/embed",
                    json={
                        "model": self.model,
                        "input": batch,
                    },
                )
                response.raise_for_status()
                data = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise EmbeddingError(
                    "Ollama embedding request failed."
                ) from exc

            embeddings = data.get("embeddings") if isinstance(data, dict) else None

            if not isinstance(embeddings, list) or len(embeddings) != len(batch):
                raise EmbeddingError(
                    "Ollama returned an unexpected number of embeddings."
                )

            for vector in embeddings:
                if not isinstance(vector, list) or len(vector) != self.dimensions:
                    raise EmbeddingError(
                        "Ollama returned an embedding with an invalid dimension."
                    )

                if any(
                    not isinstance(value, (int, float))
                    or isinstance(value, bool)
                    or not math.isfinite(value)
                    for value in vector
                ):
                    raise EmbeddingError(
                        "Ollama returned an embedding containing invalid values."
                    )

                vectors.append([float(value) for value in vector])

        return vectors

    def close(self) -> None:
        self.client.close()
