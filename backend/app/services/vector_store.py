import math
from pathlib import Path
from uuid import UUID

from qdrant_client import QdrantClient, models


class VectorStoreError(Exception):
    """Raised when vector storage operations fail."""


class QdrantVectorStore:
    """Persistent local vector storage for RAGForge document chunks."""

    def __init__(
        self,
        storage_path: str,
        collection_name: str,
        vector_size: int = 768,
    ):
        if vector_size <= 0:
            raise ValueError("Vector size must be positive.")

        self.collection_name = collection_name
        self.vector_size = vector_size

        Path(storage_path).mkdir(parents=True, exist_ok=True)

        self.client = QdrantClient(path=storage_path)

        if not self.client.collection_exists(collection_name):
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE,
                ),
            )

        self.client.create_payload_index(
            collection_name=collection_name,
            field_name="knowledge_base_id",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )

        self.client.create_payload_index(
            collection_name=collection_name,
            field_name="document_id",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )

    def _validate_vector(self, vector: list[float]) -> list[float]:
        if not isinstance(vector, list) or len(vector) != self.vector_size:
            raise ValueError("Vector has an invalid dimension.")

        if any(
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(value)
            for value in vector
        ):
            raise ValueError("Vector contains invalid numeric values.")

        return [float(value) for value in vector]

    def upsert_chunks(self, chunks: list[dict]) -> None:
        """Insert or update chunks using their PostgreSQL UUIDs."""

        if not chunks:
            return

        points = []

        for chunk in chunks:
            try:
                chunk_id = str(UUID(str(chunk["id"])))
                document_id = str(UUID(str(chunk["document_id"])))
                knowledge_base_id = str(
                    UUID(str(chunk["knowledge_base_id"]))
                )

                vector = self._validate_vector(chunk["vector"])

                payload = {
                    "document_id": document_id,
                    "knowledge_base_id": knowledge_base_id,
                    "chunk_index": int(chunk["chunk_index"]),
                    "content": str(chunk["content"]),
                    "page_numbers": chunk["page_numbers"],
                    "extraction_methods": chunk["extraction_methods"],
                }

                points.append(
                    models.PointStruct(
                        id=chunk_id,
                        vector=vector,
                        payload=payload,
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(
                    "Invalid chunk data supplied to vector store."
                ) from exc

        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
            wait=True,
        )

    def search(
        self,
        query_vector: list[float],
        knowledge_base_id: UUID,
        limit: int = 5,
    ):
        """Search only within the requested knowledge base."""

        if limit <= 0:
            raise ValueError("Search limit must be positive.")

        vector = self._validate_vector(query_vector)

        result = self.client.query_points(
            collection_name=self.collection_name,
            query=vector,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="knowledge_base_id",
                        match=models.MatchValue(
                            value=str(knowledge_base_id)
                        ),
                    )
                ]
            ),
            limit=limit,
            with_payload=True,
        )

        return result.points

    def delete_document(self, document_id: UUID) -> None:
        """Delete all vectors belonging to a document."""

        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(
                                value=str(document_id)
                            ),
                        )
                    ]
                )
            ),
            wait=True,
        )

    def close(self) -> None:
        self.client.close()
