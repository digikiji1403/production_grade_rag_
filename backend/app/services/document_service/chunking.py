from dataclasses import dataclass


@dataclass
class ChunkData:
    chunk_index: int
    content: str
    start_page: int
    end_page: int
    page_numbers: list[int]
    extraction_methods: list[str]


def _choose_boundary(text: str, start: int, hard_end: int) -> int:
    """Prefer paragraph, then line, then word boundaries."""
    minimum_end = start + int((hard_end - start) * 0.70)

    for separator in ("\n\n", "\n", " "):
        boundary = text.rfind(separator, minimum_end, hard_end)

        if boundary > start:
            return boundary

    return hard_end


def chunk_pages(
    pages,
    chunk_size: int = 3000,
    chunk_overlap: int = 300,
) -> list[ChunkData]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero.")

    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError(
            "chunk_overlap must be non-negative and smaller than chunk_size."
        )

    ordered_pages = sorted(pages, key=lambda page: page.page_number)

    # Build one text stream while retaining each page's source range.
    text_parts = []
    page_ranges = []
    cursor = 0

    for page in ordered_pages:
        page_text = page.text.strip()

        if not page_text:
            continue

        if text_parts:
            text_parts.append("\n\n")
            cursor += 2

        start = cursor
        text_parts.append(page_text)
        cursor += len(page_text)

        page_ranges.append(
            (
                start,
                cursor,
                page.page_number,
                page.extraction_method,
            )
        )

    full_text = "".join(text_parts)

    if not full_text:
        return []

    chunks = []
    start = 0

    while start < len(full_text):
        hard_end = min(start + chunk_size, len(full_text))
        end = hard_end

        if hard_end < len(full_text):
            end = _choose_boundary(full_text, start, hard_end)

        content = full_text[start:end].strip()

        if content:
            contributing_ranges = [
                item
                for item in page_ranges
                if item[0] < end and item[1] > start
            ]

            page_numbers = list(
                dict.fromkeys(item[2] for item in contributing_ranges)
            )

            extraction_methods = list(
                dict.fromkeys(item[3] for item in contributing_ranges)
            )

            chunks.append(
                ChunkData(
                    chunk_index=len(chunks),
                    content=content,
                    start_page=min(page_numbers),
                    end_page=max(page_numbers),
                    page_numbers=page_numbers,
                    extraction_methods=extraction_methods,
                )
            )

        if end >= len(full_text):
            break

        next_start = max(start + 1, end - chunk_overlap)

        # Avoid starting the next chunk in the middle of a word.
        if next_start < len(full_text):
            next_space = full_text.find(" ", next_start, min(next_start + 100, len(full_text)))
            if next_space != -1:
                next_start = next_space + 1

        start = next_start

    return chunks
