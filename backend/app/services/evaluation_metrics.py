from collections.abc import Mapping, Sequence
from math import log2
from uuid import UUID


def _normalize_ids(values: Sequence[UUID | str]) -> list[str]:
    """Normalize identifiers and preserve their original order."""

    normalized = []
    seen = set()

    for value in values:
        identifier = str(value)

        if identifier not in seen:
            normalized.append(identifier)
            seen.add(identifier)

    return normalized


def calculate_retrieval_metrics(
    retrieved_chunk_ids: Sequence[UUID | str],
    relevant_chunk_ids: Sequence[UUID | str],
    k: int = 5,
    relevance_grades: Mapping[UUID | str, int] | None = None,
) -> dict[str, float]:
    """Calculate Precision, Recall, HitRate, MRR and nDCG at K."""

    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError("k must be a positive integer.")

    retrieved = _normalize_ids(retrieved_chunk_ids)
    relevant = _normalize_ids(relevant_chunk_ids)

    if not relevant:
        raise ValueError("At least one relevant chunk is required.")

    if relevance_grades is None:
        grades = {identifier: 1 for identifier in relevant}
    else:
        grades = {
            str(identifier): grade
            for identifier, grade in relevance_grades.items()
        }

        for identifier in relevant:
            grade = grades.get(identifier, 1)

            if isinstance(grade, bool) or not isinstance(grade, int):
                raise ValueError("Relevance grades must be integers.")

            if grade < 0:
                raise ValueError("Relevance grades cannot be negative.")

            grades[identifier] = grade

    # Grade zero means explicitly non-relevant.
    relevant_positive = {
        identifier
        for identifier in relevant
        if grades.get(identifier, 1) > 0
    }

    if not relevant_positive:
        raise ValueError(
            "At least one relevant chunk must have a positive grade."
        )

    retrieved_at_k = retrieved[:k]

    relevant_retrieved = [
        identifier
        for identifier in retrieved_at_k
        if identifier in relevant_positive
    ]

    relevant_count = len(relevant_retrieved)

    precision = relevant_count / k
    recall = relevant_count / len(relevant_positive)
    hit_rate = float(relevant_count > 0)

    reciprocal_rank = 0.0

    for rank, identifier in enumerate(retrieved_at_k, start=1):
        if identifier in relevant_positive:
            reciprocal_rank = 1.0 / rank
            break

    def dcg(identifiers: Sequence[str]) -> float:
        score = 0.0

        for rank, identifier in enumerate(identifiers[:k], start=1):
            relevance = grades.get(identifier, 0)
            gain = (2**relevance) - 1
            score += gain / log2(rank + 1)

        return score

    ideal_relevance = sorted(
        (grades.get(identifier, 1) for identifier in relevant_positive),
        reverse=True,
    )

    ideal_dcg = sum(
        ((2**relevance) - 1) / log2(rank + 1)
        for rank, relevance in enumerate(ideal_relevance[:k], start=1)
    )

    normalized_dcg = (
        dcg(retrieved_at_k) / ideal_dcg
        if ideal_dcg > 0
        else 0.0
    )

    return {
        "precision_at_k": precision,
        "recall_at_k": recall,
        "hit_rate_at_k": hit_rate,
        "mrr_at_k": reciprocal_rank,
        "ndcg_at_k": normalized_dcg,
    }
