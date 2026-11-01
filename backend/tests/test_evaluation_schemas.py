from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.app.schemas.evaluation import (
    EvaluationCase,
    EvaluationDataset,
)


def make_case(**overrides):
    data = {
        "query_id": "rag-001",
        "query": "What is retrieval augmented generation?",
        "relevant_chunk_ids": [uuid4()],
        "top_k": 5,
    }
    data.update(overrides)
    return data


def test_valid_evaluation_case():
    case = EvaluationCase(**make_case())

    assert case.query_id == "rag-001"
    assert case.top_k == 5
    assert len(case.relevant_chunk_ids) == 1


def test_valid_graded_relevance():
    chunk_id = uuid4()

    case = EvaluationCase(
        **make_case(
            relevant_chunk_ids=[chunk_id],
            relevance_grades={chunk_id: 3},
        )
    )

    assert case.relevance_grades[chunk_id] == 3


def test_rejects_empty_query():
    with pytest.raises(ValidationError):
        EvaluationCase(**make_case(query="   "))


def test_rejects_empty_query_id():
    with pytest.raises(ValidationError):
        EvaluationCase(**make_case(query_id="   "))


def test_rejects_empty_ground_truth():
    with pytest.raises(ValidationError):
        EvaluationCase(**make_case(relevant_chunk_ids=[]))


def test_rejects_duplicate_relevant_chunk_ids():
    chunk_id = uuid4()

    with pytest.raises(ValidationError, match="must be unique"):
        EvaluationCase(
            **make_case(relevant_chunk_ids=[chunk_id, chunk_id])
        )


@pytest.mark.parametrize("grade", [-1, 4, True])
def test_rejects_invalid_relevance_grades(grade):
    chunk_id = uuid4()

    with pytest.raises(ValidationError):
        EvaluationCase(
            **make_case(
                relevant_chunk_ids=[chunk_id],
                relevance_grades={chunk_id: grade},
            )
        )


def test_rejects_grade_for_unknown_chunk():
    chunk_id = uuid4()

    with pytest.raises(ValidationError, match="only reference"):
        EvaluationCase(
            **make_case(relevance_grades={chunk_id: 3})
        )


@pytest.mark.parametrize("top_k", [0, 21])
def test_rejects_invalid_top_k(top_k):
    with pytest.raises(ValidationError):
        EvaluationCase(**make_case(top_k=top_k))


def test_valid_evaluation_dataset():
    dataset = EvaluationDataset(
        dataset_name="ragforge-retrieval",
        dataset_version="1.0.0",
        cases=[
            make_case(query_id="rag-001"),
            make_case(query_id="rag-002"),
        ],
    )

    assert dataset.dataset_name == "ragforge-retrieval"
    assert len(dataset.cases) == 2


def test_rejects_duplicate_query_ids():
    case = make_case()

    with pytest.raises(ValidationError, match="must be unique"):
        EvaluationDataset(
            dataset_name="ragforge-retrieval",
            dataset_version="1.0.0",
            cases=[case, case],
        )


def test_rejects_empty_dataset():
    with pytest.raises(ValidationError):
        EvaluationDataset(
            dataset_name="ragforge-retrieval",
            dataset_version="1.0.0",
            cases=[],
        )


def test_rejects_unknown_dataset_fields():
    with pytest.raises(ValidationError):
        EvaluationDataset(
            dataset_name="ragforge-retrieval",
            dataset_version="1.0.0",
            cases=[make_case()],
            unexpected_field="not allowed",
        )


@pytest.mark.parametrize("top_k", [True, 1.5, "5"])
def test_rejects_non_integer_top_k(top_k):
    with pytest.raises(ValidationError):
        EvaluationCase(**make_case(top_k=top_k))


def test_rejects_all_zero_relevance_grades():
    chunk_id = uuid4()

    with pytest.raises(ValidationError, match="greater than zero"):
        EvaluationCase(
            **make_case(
                relevant_chunk_ids=[chunk_id],
                relevance_grades={chunk_id: 0},
            )
        )


def test_allows_empty_relevance_grades():
    case = EvaluationCase(**make_case(relevance_grades={}))

    assert case.relevance_grades == {}


def test_rejects_dataset_with_more_than_100_cases():
    cases = [
        make_case(query_id=f"query-{index}")
        for index in range(101)
    ]

    with pytest.raises(ValidationError):
        EvaluationDataset(
            dataset_name="large-dataset",
            dataset_version="1.0",
            cases=cases,
        )


def test_allows_dataset_with_exactly_100_cases():
    cases = [
        make_case(query_id=f"query-{index}")
        for index in range(100)
    ]

    dataset = EvaluationDataset(
        dataset_name="maximum-dataset",
        dataset_version="1.0",
        cases=cases,
    )

    assert len(dataset.cases) == 100
