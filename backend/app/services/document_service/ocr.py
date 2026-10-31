class OCRError(Exception):
    """Raised when OCR processing fails."""


def extract_page_with_ocr(
    page,
    language: str = "eng",
    dpi: int = 200,
) -> str:
    """
    Extract text from a PDF page using Tesseract through PyMuPDF.

    An empty string is a valid result for a blank or unreadable page.
    Actual OCR failures raise OCRError.
    """
    try:
        text_page = page.get_textpage_ocr(
            language=language,
            dpi=dpi,
            full=True,
        )

        return page.get_text(
            "text",
            textpage=text_page,
        ).strip()

    except Exception as exc:
        raise OCRError(
            "OCR failed while processing a PDF page."
        ) from exc