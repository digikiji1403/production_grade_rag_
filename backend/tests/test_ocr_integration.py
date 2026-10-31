import shutil

import pymupdf
import pytest

from backend.app.services.document_service.extraction import extract_pdf


@pytest.mark.skipif(
    shutil.which("tesseract") is None,
    reason="Tesseract executable is not available on PATH",
)
def test_real_tesseract_extracts_text_from_image_only_pdf(tmp_path):
    source_path = tmp_path / "source.pdf"
    image_pdf_path = tmp_path / "image_only.pdf"

    # Create a temporary PDF containing recognizable text.
    source = pymupdf.open()
    page = source.new_page(width=595, height=842)
    page.insert_text(
        (72, 120),
        "RAGForge real OCR integration test",
        fontsize=24,
    )

    # Render the page into pixels.
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(3, 3))
    source.save(source_path)
    source.close()

    # Create another PDF containing only the rendered image.
    image_document = pymupdf.open()
    image_page = image_document.new_page(width=595, height=842)
    image_page.insert_image(
        image_page.rect,
        pixmap=pixmap,
    )
    image_document.save(image_pdf_path)
    image_document.close()

    # Confirm native extraction cannot read the image-only PDF.
    native_result = extract_pdf(
        image_pdf_path,
        ocr_enabled=False,
    )

    assert native_result.pages[0].text == ""

    # Run actual OCR using Tesseract.
    ocr_result = extract_pdf(
        image_pdf_path,
        ocr_enabled=True,
        ocr_language="eng",
        ocr_dpi=200,
    )

    extracted_text = ocr_result.pages[0].text.lower()

    assert "ragforge" in extracted_text
    assert "real" in extracted_text
    assert "ocr" in extracted_text
    assert ocr_result.pages[0].ocr_attempted is True
    assert ocr_result.pages[0].extraction_method == "tesseract_ocr"
