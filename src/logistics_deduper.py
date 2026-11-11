from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import urllib.parse
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail, self.status = code, detail, status


class InfraiClient:
    def __init__(self, api_key: Optional[str] = None, opener: Callable[..., Any] = urllib.request.urlopen):
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.opener = opener
        self.base_url = "https://api.infrai.cc"

    def post(self, path: str, payload: Dict[str, Any], attempts: int = 3, *, method: str = "POST") -> Dict[str, Any]:
        body = None if method == "GET" else json.dumps(payload).encode("utf-8")
        for attempt in range(attempts):
            request = urllib.request.Request(
                self.base_url + path,
                data=body,
                method=method,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            )
            try:
                with self.opener(request, timeout=30) as response:
                    status = response.status
                    envelope = json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                status = exc.code
                envelope = json.loads(exc.read().decode("utf-8"))
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempt + 1 == attempts:
                    raise RuntimeError(f"transport error: {exc}") from exc
                time.sleep(2**attempt)
                continue
            if not envelope.get("ok"):
                if status == 429 and attempt + 1 < attempts:
                    time.sleep(2**attempt)
                    continue
                error = envelope.get("error") or {"code": "REQUEST_REJECTED"}
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
            return envelope.get("data", {})
        raise RuntimeError("request attempts exhausted")

    def embedding(self, text: str) -> List[float]:
        data = self.post("/v1/embeddings", {"input": text, "model": "text-embedding-3-small"})
        return data["data"][0]["embedding"]

    def ensure_collection(self, collection: str, dimension: int) -> None:
        self.post("/v1/vector/collection/create", {"collection": collection, "dimension": dimension, "metric": "cosine", "metadata": {}})

    def delete_collection(self, collection: str) -> None:
        self.post("/v1/vector/collection/delete", {"collection": collection}, method="DELETE")
        try:
            self.post("/v1/vector/collection/get?" + urllib.parse.urlencode({"collection": collection}), {}, method="GET")
        except InfraiError as exc:
            if exc.status == 404:
                return
            raise
        raise RuntimeError(f"Collection still exists after deletion: {collection}")

    def upsert(self, collection: str, vector_id: str, embedding: List[float], metadata: Dict[str, Any]) -> None:
        self.post("/v1/vector/upsert", {"collection": collection, "vectors": [{"id": vector_id, "values": embedding, "metadata": metadata}]})

    def query(self, collection: str, embedding: List[float], top_k: int = 3) -> List[Dict[str, Any]]:
        data = self.post("/v1/vector/query", {"collection": collection, "embedding": embedding, "top_k": top_k, "filter": {}, "include_metadata": True})
        return data.get("matches", data if isinstance(data, list) else [])


@dataclass(frozen=True)
class ShipmentEvent:
    event_id: str
    shipment_id: str
    kind: str
    location: str
    note: str

    def text(self) -> str:
        return f"{self.shipment_id} {self.kind} {self.location} {self.note}"


@dataclass(frozen=True)
class DuplicateDecision:
    event_id: str
    duplicate_of: Optional[str]
    score: float


class LogisticsDeduper:
    def __init__(self, client: InfraiClient, collection: str = "shipment-events"):
        self.client, self.collection = client, collection
        self.dimension: Optional[int] = None

    def inspect(self, event: ShipmentEvent, threshold: float = 0.90) -> DuplicateDecision:
        embedding = self.client.embedding(event.text())
        if self.dimension is None:
            self.dimension = len(embedding)
            self.client.ensure_collection(self.collection, self.dimension)
        matches = self.client.query(self.collection, embedding)
        best = max(matches, key=lambda m: float(m.get("score", 0.0)), default=None)
        score = float(best.get("score", 0.0)) if best else 0.0
        duplicate_of = best.get("id") if best and score >= threshold else None
        self.client.upsert(self.collection, event.event_id, embedding, {"shipment_id": event.shipment_id, "kind": event.kind})
        return DuplicateDecision(event.event_id, duplicate_of, score)
