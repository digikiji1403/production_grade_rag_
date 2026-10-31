import pymupdf
import pytest

from backend.app.services.document_service import extraction
from backend.app.services.document_service.extraction import (
    ExtractedPage,
    OCRError,
    PDFExtractionError,
    extract_pdf,
)


@pytest.fixture
def sample_pdf(tmp_path):
    path = tmp_path / "sample.pdf"

    document = pymupdf.open()

    page1 = document.new_page()
    page1.insert_text((72, 72), "RAGForge first page")

    page2 = document.new_page()
    page2.insert_text((72, 72), "RAGForge second page")

    document.save(path)
    document.close()

    return path


@pytest.fixture
def mixed_pdf(tmp_path):
    path = tmp_path / "mixed.pdf"

    document = pymupdf.open()

    page1 = document.new_page()
    page1.insert_text((72, 72), "Native text page")

    document.new_page()

    document.save(path)
    document.close()

    return path


def test_extracts_text_from_all_pages(sample_pdf):
    result = extract_pdf(sample_pdf)

    assert result.page_count == 2
    assert len(result.pages) == 2

    assert result.pages[0].page_number == 1
    assert "RAGForge first page" in result.pages[0].text

    assert result.pages[1].page_number == 2
    assert "RAGForge second page" in result.pages[1].text


def test_full_text_combines_pages(sample_pdf):
    result = extract_pdf(sample_pdf)

    assert "RAGForge first page" in result.full_text
    assert "RAGForge second page" in result.full_text


def test_preserves_empty_pages(tmp_path):
    path = tmp_path / "empty_page.pdf"

    document = pymupdf.open()
    document.new_page()
    document.new_page()
    document.save(path)
    document.close()

    result = extract_pdf(path, ocr_enabled=False)

    assert result.page_count == 2
    assert len(result.pages) == 2
    assert result.pages[0].text == ""
    assert result.pages[1].text == ""


def test_rejects_missing_pdf():
    with pytest.raises(PDFExtractionError):
        extract_pdf("missing.pdf")


def test_rejects_invalid_pdf(tmp_path):
    path = tmp_path / "invalid.pdf"
    path.write_text("This is not a PDF")

    with pytest.raises(PDFExtractionError):
        extract_pdf(path)


def test_reports_total_characters(sample_pdf):
    result = extract_pdf(sample_pdf)

    expected = sum(len(page.text) for page in result.pages)

    assert result.total_characters == expected


def test_reports_empty_page_numbers(tmp_path):
    path = tmp_path / "mixed_pages.pdf"

    document = pymupdf.open()

    page1 = document.new_page()
    page1.insert_text((72, 72), "Text page")

    document.new_page()

    page3 = document.new_page()
    page3.insert_text((72, 72), "Another text page")

    document.save(path)
    document.close()

    result = extract_pdf(path, ocr_enabled=False)

    assert result.empty_page_numbers == [2]
    assert result.pages_without_text == [2]


def test_detects_document_without_extractable_text(tmp_path):
    path = tmp_path / "image_only_candidate.pdf"

    document = pymupdf.open()
    document.new_page()
    document.new_page()
    document.save(path)
    document.close()

    result = extract_pdf(path, ocr_enabled=False)

    assert result.has_no_extractable_text is True
    assert result.total_characters == 0
    assert result.empty_page_numbers == [1, 2]


def test_detects_document_with_native_text(sample_pdf):
    result = extract_pdf(sample_pdf)

    assert result.has_no_extractable_text is False


def test_reports_extraction_method(sample_pdf):
    result = extract_pdf(sample_pdf)

    assert result.extraction_method == "pymupdf_native"


def test_page_has_text_property():
    assert ExtractedPage(1, "Hello").has_text is True
    assert ExtractedPage(2, "   ").has_text is False


def test_rejects_encrypted_pdf(tmp_path):
    path = tmp_path / "encrypted.pdf"

    document = pymupdf.open()
    document.new_page()

    document.save(
        path,
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        owner_pw="owner123",
        user_pw="user123",
    )
    document.close()

    with pytest.raises(
        PDFExtractionError,
        match="Encrypted PDFs are not supported",
    ):
        extract_pdf(path)


def test_native_text_pages_do_not_invoke_ocr(
    sample_pdf, monkeypatch
):
    def unexpected_ocr(*args, **kwargs):
        pytest.fail("OCR should not run for pages with native text")

    monkeypatch.setattr(
        extraction,
        "extract_page_with_ocr",
        unexpected_ocr,
    )

    result = extract_pdf(sample_pdf)

    assert result.page_count == 2

    for page in result.pages:
        assert page.extraction_method == "pymupdf_native"
        assert page.ocr_attempted is False


def test_image_only_pages_invoke_ocr(
    tmp_path, monkeypatch
):
    path = tmp_path / "image_only.pdf"

    document = pymupdf.open()
    document.new_page()
    document.save(path)
    document.close()

    calls = []

    def fake_ocr(page, language="eng", dpi=200):
        calls.append((language, dpi))
        return "OCR extracted text"

    monkeypatch.setattr(
        extraction,
        "extract_page_with_ocr",
        fake_ocr,
    )

    result = extract_pdf(
        path,
        ocr_enabled=True,
        ocr_language="eng",
        ocr_dpi=200,
    )

    assert len(calls) == 1
    assert result.pages[0].text == "OCR extracted text"
    assert result.pages[0].extraction_method == "tesseract_ocr"
    assert result.pages[0].ocr_attempted is True


def test_mixed_pdf_uses_native_and_ocr_extraction(
    mixed_pdf, monkeypatch
):
    calls = []

    def fake_ocr(page, language="eng", dpi=200):
        calls.append(page)
        return "OCR extracted second page"

    monkeypatch.setattr(
        extraction,
        "extract_page_with_ocr",
        fake_ocr,
    )

    result = extract_pdf(mixed_pdf)

    assert len(calls) == 1
    assert result.page_count == 2

    assert result.pages[0].text == "Native text page"
    assert result.pages[0].extraction_method == "pymupdf_native"
    assert result.pages[0].ocr_attempted is False

    assert result.pages[1].text == "OCR extracted second page"
    assert result.pages[1].extraction_method == "tesseract_ocr"
    assert result.pages[1].ocr_attempted is True


def test_disabling_ocr_prevents_ocr_execution(
    tmp_path, monkeypatch
):
    path = tmp_path / "no_ocr.pdf"

    document = pymupdf.open()
    document.new_page()
    document.save(path)
    document.close()

    def unexpected_ocr(*args, **kwargs):
        pytest.fail("OCR was invoked even though it is disabled")

    monkeypatch.setattr(
        extraction,
        "extract_page_with_ocr",
        unexpected_ocr,
    )

    result = extract_pdf(path, ocr_enabled=False)

    assert result.pages[0].text == ""
    assert result.pages[0].extraction_method == "pymupdf_native"
    assert result.pages[0].ocr_attempted is False


def test_ocr_failure_propagates_as_ocr_error(
    tmp_path, monkeypatch
):
    path = tmp_path / "ocr_failure.pdf"

    document = pymupdf.open()
    document.new_page()
    document.save(path)
    document.close()

    def failing_ocr(*args, **kwargs):
        raise OCRError("OCR test failure")

    monkeypatch.setattr(
        extraction,
        "extract_page_with_ocr",
        failing_ocr,
    )

    with pytest.raises(OCRError, match="OCR test failure"):
        extract_pdf(path)
