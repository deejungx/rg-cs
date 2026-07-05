import hashlib
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams

from app.core.config import settings


class QdrantService:
    def __init__(self, url: str) -> None:
        self.url = url

    def _embedding(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return [round(byte / 255, 6) for byte in digest[:16]]

    def index_document(self, collection: str, point_id: str, text: str, payload: dict[str, Any]) -> None:
        try:
            client = QdrantClient(url=self.url)
            client.recreate_collection(
                collection_name=collection,
                vectors_config=VectorParams(size=16, distance=Distance.COSINE),
            )
            client.upsert(
                collection_name=collection,
                points=[
                    PointStruct(
                        id=point_id,
                        vector=self._embedding(text),
                        payload=payload,
                    )
                ],
            )
        except Exception:
            # Qdrant is optional during local tests; ignore connectivity failures.
            return


qdrant_service = QdrantService(settings.qdrant_url)
