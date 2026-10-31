from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "RAGForge API"
    app_version: str = "0.1.0"
    environment: str = "development"
    log_level: str = "INFO"

    # Database configuration
    database_url: str | None = None

    # Document upload and chunking
    max_upload_size_bytes: int = 5 * 1024 * 1024 * 1024
    chunk_size: int = 3000
    chunk_overlap: int = 300

    # Environment configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Authentication
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # PDF OCR
    ocr_enabled: bool = True
    ocr_language: str = "eng"
    ocr_dpi: int = 200

    # Local Ollama embeddings
    ollama_base_url: str = "http://localhost:11434"
    embedding_model: str = "embeddinggemma"
    embedding_dimensions: int = 768
    embedding_batch_size: int = 32
    embedding_timeout_seconds: int = 120

    # Local Ollama generation
    generation_model: str = "qwen3:4b"
    generation_timeout_seconds: int = 180
    generation_temperature: float = 0.0

    # Local Qdrant vector storage
    qdrant_storage_path: str = "backend/storage/qdrant"
    qdrant_collection_name: str = "ragforge_chunks"


@lru_cache
def get_settings() -> Settings:
    return Settings()
