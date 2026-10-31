import hashlib
from io import BytesIO

import pytest
from pathlib import Path

from backend.app.services.document_service.storage import store_document


def test_store_document(tmp_path, monkeypatch):
    from backend.app.services.document_service import storage

    monkeypatch.setattr(storage, "DOCUMENT_STORAGE_PATH", tmp_path)

    content = b"RAGForge document test"

    result = store_document(
        source=BytesIO(content),
        original_filename="sample.pdf",
    )

    saved_file = tmp_path / result.storage_path.split("\\")[-1]

    assert saved_file.exists()
    assert saved_file.read_bytes() == content
    assert result.size_bytes == len(content)
    assert result.checksum == hashlib.sha256(content).hexdigest()


def test_store_document_uses_bounded_reads(tmp_path, monkeypatch):
    from backend.app.services.document_service import storage

    monkeypatch.setattr(storage, "DOCUMENT_STORAGE_PATH", tmp_path)

    class TrackingStream(BytesIO):
        def __init__(self, content):
            super().__init__(content)
            self.largest_read = 0

        def read(self, size=-1):
            self.largest_read = max(self.largest_read, size)
            return super().read(size)

    source = TrackingStream(b"x" * (3 * 1024 * 1024))

    store_document(
        source=source,
        original_filename="large.pdf",
        chunk_size=64 * 1024,
    )

    assert source.largest_read == 64 * 1024


def test_store_document_rejects_invalid_chunk_size():
    with pytest.raises(ValueError):
        store_document(
            source=BytesIO(b"test"),
            original_filename="sample.pdf",
            chunk_size=0,
        )


def test_failed_write_removes_partial_file(tmp_path, monkeypatch):
    from backend.app.services.document_service import storage

    monkeypatch.setattr(storage, "DOCUMENT_STORAGE_PATH", tmp_path)

    class BrokenStream:
        def read(self, size=-1):
            raise OSError("Simulated read failure")

    with pytest.raises(OSError):
        store_document(
            source=BrokenStream(),
            original_filename="sample.pdf",
        )

    assert list(tmp_path.iterdir()) == []



def test_successful_storage_leaves_no_temporary_file(tmp_path, monkeypatch):
    from backend.app.services.document_service import storage

    monkeypatch.setattr(storage, "DOCUMENT_STORAGE_PATH", tmp_path)

    result = store_document(
        source=BytesIO(b"complete document"),
        original_filename="sample.pdf",
    )

    saved_path = Path(result.storage_path)

    assert saved_path.exists()
    assert saved_path.suffix == ".bin"
    assert not list(tmp_path.glob("*.part"))


def test_failed_storage_removes_temporary_file(tmp_path, monkeypatch):
    from backend.app.services.document_service import storage

    monkeypatch.setattr(storage, "DOCUMENT_STORAGE_PATH", tmp_path)

    class BrokenStream:
        def __init__(self):
            self.calls = 0

        def read(self, size=-1):
            self.calls += 1

            if self.calls == 1:
                return b"partial content"

            raise OSError("Simulated failure")

    with pytest.raises(OSError):
        store_document(
            source=BrokenStream(),
            original_filename="sample.pdf",
        )

    assert list(tmp_path.iterdir()) == []

def test_store_document_rejects_file_exceeding_size_limit(
    tmp_path,
    monkeypatch,
):
    from backend.app.services.document_service import storage

    monkeypatch.setattr(storage, "DOCUMENT_STORAGE_PATH", tmp_path)

    content = b"x" * 101

    with pytest.raises(storage.DocumentTooLargeError):
        store_document(
            source=BytesIO(content),
            original_filename="large.pdf",
            chunk_size=32,
            max_size_bytes=100,
        )

    # Failed uploads must leave no temporary or final files.
    assert list(tmp_path.iterdir()) == []


def test_store_document_accepts_file_at_exact_size_limit(
    tmp_path,
    monkeypatch,
):
    from backend.app.services.document_service import storage

    monkeypatch.setattr(storage, "DOCUMENT_STORAGE_PATH", tmp_path)

    content = b"x" * 100

    result = store_document(
        source=BytesIO(content),
        original_filename="valid.pdf",
        chunk_size=32,
        max_size_bytes=100,
    )

    saved_file = Path(result.storage_path)

    assert saved_file.exists()
    assert result.size_bytes == 100
    assert saved_file.read_bytes() == content