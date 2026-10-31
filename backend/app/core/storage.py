from pathlib import Path

# Project root: RAGForge/
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Local storage location for original uploaded documents
DOCUMENT_STORAGE_PATH = (
    PROJECT_ROOT / "backend" / "storage" / "documents"
)

def ensure_storage_directory() -> None:
    """Create the document storage directory if it does not exist."""
    DOCUMENT_STORAGE_PATH.mkdir(parents=True, exist_ok=True)