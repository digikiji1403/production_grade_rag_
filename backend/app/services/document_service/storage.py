
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from backend.app.core.storage import (
    DOCUMENT_STORAGE_PATH,
    ensure_storage_directory,
)


@dataclass(frozen=True)
class StoredDocument:
    storage_path: str
    size_bytes: int
    checksum: str

class DocumentTooLargeError(Exception):
    """Raised when a document exceeds the configured size limit."""

def store_document(
    source: BinaryIO,
    original_filename: str,
    chunk_size: int = 1024 * 1024,
    max_size_bytes: int | None = None,
) -> StoredDocument:
    """
    Stream a document into storage using bounded-memory reads.

    Enforces an optional maximum size while reading.
    The final file becomes visible only after a successful write.
    """

    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive.")

    if max_size_bytes is not None and max_size_bytes <= 0:
        raise ValueError("max_size_bytes must be positive.")

    ensure_storage_directory()

    file_id = uuid4()
    temporary_path = DOCUMENT_STORAGE_PATH / f"{file_id}.part"
    final_path = DOCUMENT_STORAGE_PATH / f"{file_id}.bin"

    checksum = hashlib.sha256()
    total_bytes = 0

    try:
        with temporary_path.open("xb") as output:
            while True:
                # Read at most one byte beyond the remaining allowance.
                read_size = chunk_size

                if max_size_bytes is not None:
                    remaining = max_size_bytes - total_bytes
                    read_size = min(chunk_size, remaining + 1)

                chunk = source.read(read_size)

                if not chunk:
                    break

                if not isinstance(chunk, bytes):
                    raise TypeError("Document source must provide bytes.")

                if (
                    max_size_bytes is not None
                    and total_bytes + len(chunk) > max_size_bytes
                ):
                    raise DocumentTooLargeError(
                        f"Document exceeds the maximum size of "
                        f"{max_size_bytes} bytes."
                    )

                output.write(chunk)
                checksum.update(chunk)
                total_bytes += len(chunk)

            output.flush()

            import os
            os.fsync(output.fileno())

        if temporary_path.stat().st_size != total_bytes:
            raise IOError("Stored document size validation failed.")

        temporary_path.replace(final_path)

        return StoredDocument(
            storage_path=str(final_path),
            size_bytes=total_bytes,
            checksum=checksum.hexdigest(),
        )

    except Exception:
        temporary_path.unlink(missing_ok=True)
        final_path.unlink(missing_ok=True)
        raise