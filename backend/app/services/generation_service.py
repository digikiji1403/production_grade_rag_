import httpx


class GenerationError(Exception):
    """Raised when the LLM generation service fails."""


class OllamaGenerationService:
    """Generate answers using a locally hosted Ollama chat model."""

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: float = 180.0,
        temperature: float = 0.0,
        client: httpx.Client | None = None,
    ):
        if not model.strip():
            raise ValueError("Model name cannot be empty.")

        if timeout <= 0:
            raise ValueError("Timeout must be greater than zero.")

        if not 0 <= temperature <= 2:
            raise ValueError("Temperature must be between 0 and 2.")

        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.client = client or httpx.Client(timeout=timeout)

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Generate and validate a non-streaming response."""

        if not system_prompt.strip() or not user_prompt.strip():
            raise ValueError("Prompts cannot be empty.")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {
                "temperature": self.temperature,
            },
        }

        try:
            response = self.client.post(
                f"{self.base_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            message = data.get("message")
            if not isinstance(message, dict):
                raise GenerationError("Ollama returned an invalid response.")

            content = message.get("content")
            if not isinstance(content, str) or not content.strip():
                raise GenerationError("Ollama returned an empty response.")

            return content.strip()

        except GenerationError:
            raise
        except (httpx.HTTPError, ValueError, TypeError, AttributeError) as exc:
            raise GenerationError(
                "The language model is temporarily unavailable."
            ) from exc

    def close(self) -> None:
        self.client.close()
