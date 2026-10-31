from types import SimpleNamespace

import pytest

from backend.app.services.document_service.chunking import chunk_pages


def make_page(number, text, method="pymupdf_native"):
    return SimpleNamespace(
        page_number=number,
        text=text,
        extraction_method=method,
    )


def test_empty_pages_return_no_chunks():
    assert chunk_pages([]) == []


def test_blank_pages_return_no_chunks():
    pages = [
        make_page(1, ""),
        make_page(2, "   \n "),
    ]

    assert chunk_pages(pages) == []


def test_short_document_creates_one_chunk():
    pages = [make_page(1, "This is a short document.")]

    chunks = chunk_pages(pages, chunk_size=100, chunk_overlap=10)

    assert len(chunks) == 1
    assert chunks[0].content == "This is a short document."
    assert chunks[0].chunk_index == 0


def test_chunks_respect_configured_character_limit():
    pages = [make_page(1, "abcdefghijklmnopqrstuvwxyz")]

    chunks = chunk_pages(pages, chunk_size=10, chunk_overlap=3)

    assert len(chunks) > 1
    assert all(len(chunk.content) <= 10 for chunk in chunks)


def test_overlap_is_preserved_between_chunks():
    pages = [make_page(1, "abcdefghijklmnopqrstuvwxyz")]

    chunks = chunk_pages(pages, chunk_size=10, chunk_overlap=3)

    assert chunks[0].content[-3:] == chunks[1].content[:3]


def test_chunk_tracks_page_provenance():
    pages = [
        make_page(1, "First page content."),
        make_page(2, "Second page content.", "tesseract_ocr"),
    ]

    chunks = chunk_pages(pages, chunk_size=1000, chunk_overlap=100)

    assert len(chunks) == 1
    assert chunks[0].start_page == 1
    assert chunks[0].end_page == 2
    assert chunks[0].page_numbers == [1, 2]
    assert chunks[0].extraction_methods == [
        "pymupdf_native",
        "tesseract_ocr",
    ]


def test_blank_pages_do_not_break_page_provenance():
    pages = [
        make_page(1, "Page one."),
        make_page(2, "   "),
        make_page(3, "Page three."),
    ]

    chunks = chunk_pages(pages, chunk_size=1000, chunk_overlap=100)

    assert len(chunks) == 1
    assert chunks[0].page_numbers == [1, 3]
    assert chunks[0].start_page == 1
    assert chunks[0].end_page == 3


def test_chunks_have_sequential_indexes():
    pages = [make_page(1, "abcdefghijklmnopqrstuvwxyz")]

    chunks = chunk_pages(pages, chunk_size=10, chunk_overlap=3)

    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))


@pytest.mark.parametrize(
    ("chunk_size", "chunk_overlap"),
    [
        (0, 0),
        (-1, 0),
        (10, -1),
        (10, 10),
        (10, 11),
    ],
)
def test_invalid_chunk_configuration_is_rejected(chunk_size, chunk_overlap):
    with pytest.raises(ValueError):
        chunk_pages(
            [make_page(1, "Some content.")],
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
