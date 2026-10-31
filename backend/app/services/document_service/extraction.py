
from dataclasses import dataclass
from pathlib import Path


import pymupdf
from backend.app.services.document_service.ocr import (
    OCRError,
    extract_page_with_ocr,
)

class PDFExtractionError(Exception):
    """Raised when a PDF cannot be extracted."""


@dataclass
class ExtractedPage:
    page_number: int
    text: str
    extraction_method: str = "pymupdf_native"
    ocr_attempted: bool = False

    @property
    def has_text(self) -> bool:
        return bool(self.text.strip())


@dataclass
class PDFExtractionResult:
    page_count: int
    pages: list[ExtractedPage]

    @property
    def full_text(self) -> str:
        return "\n\n".join(
            page.text for page in self.pages
        )

    @property
    def total_characters(self) -> int:
        return sum(
            len(page.text) for page in self.pages
        )

    @property
    def empty_page_numbers(self) -> list[int]:
        return [
            page.page_number
            for page in self.pages
            if not page.has_text
        ]

    @property
    def pages_without_text(self) -> list[int]:
        """Pages that may need OCR or manual inspection."""
        return self.empty_page_numbers

    @property
    def has_no_extractable_text(self) -> bool:
        return self.total_characters == 0

    @property
    def extraction_method(self) -> str:
        return "pymupdf_native"


def extract_pdf(
    path: str | Path,
    ocr_enabled: bool = True,
    ocr_language: str = "eng",
    ocr_dpi: int = 200,
) -> PDFExtractionResult:
    """
    Extract PDF text page by page.

    Native extraction is attempted first. OCR is used only when
    native extraction returns no text for a page.
    """
    pdf_path = Path(path)

    if not pdf_path.is_file():
        raise PDFExtractionError("PDF file does not exist.")

    try:
        pages = []

        with pymupdf.open(pdf_path) as document:
            if document.is_encrypted:
                raise PDFExtractionError(
                    "Encrypted PDFs are not supported."
                )

            page_count = len(document)

            if page_count == 0:
                raise PDFExtractionError("PDF contains no pages.")

            for index in range(page_count):
                page = document.load_page(index)

                text = page.get_text("text").strip()

                extraction_method = "pymupdf_native"
                ocr_attempted = False

                if not text and ocr_enabled:
                    ocr_attempted = True
                    extraction_method = "tesseract_ocr"

                    text = extract_page_with_ocr(
                        page,
                        language=ocr_language,
                        dpi=ocr_dpi,
                    )

                pages.append(
                    ExtractedPage(
                        page_number=index + 1,
                        text=text,
                        extraction_method=extraction_method,
                        ocr_attempted=ocr_attempted,
                    )
                )

        return PDFExtractionResult(
            page_count=page_count,
            pages=pages,
        )

    except (PDFExtractionError, OCRError):
        raise

    except Exception as exc:
        raise PDFExtractionError(
            "Unable to extract text from PDF."
        ) from exc