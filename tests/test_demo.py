import pytest

import run_demo
from src.logistics_deduper import InfraiClient, InfraiError


@pytest.mark.parametrize("fail", [False, True])
def test_demo_cleans_its_unique_collection(monkeypatch, fail):
    created, deleted = [], []

    class Client:
        def embedding(self, text):
            return [1.0, 0.0]

        def ensure_collection(self, collection, dimension):
            created.append(collection)

        def query(self, collection, embedding):
            if fail:
                raise RuntimeError("query failed")
            return []

        def upsert(self, *args):
            pass

        def delete_collection(self, collection):
            deleted.append(collection)

    monkeypatch.setenv("INFRAI_API_KEY", "test")
    monkeypatch.setattr(run_demo, "InfraiClient", Client)
    for _ in range(2):
        if fail:
            with pytest.raises(RuntimeError, match="query failed"):
                run_demo.main()
        else:
            run_demo.main()
    assert created == deleted
    assert len(set(created)) == 2
    assert all(name.startswith("shipment-demo-") for name in created)


def test_delete_verifies_absence(monkeypatch):
    client = InfraiClient(api_key="test")
    calls = []

    def request(path, payload, *, method):
        calls.append((path, payload, method))
        if method == "GET":
            raise InfraiError("NOT_FOUND", {}, 404)
        return {}

    monkeypatch.setattr(client, "post", request)
    client.delete_collection("demo")
    assert calls == [
        ("/v1/vector/collection/delete", {"collection": "demo"}, "DELETE"),
        ("/v1/vector/collection/get?collection=demo", {}, "GET"),
    ]


def test_delete_rejects_resource_still_present(monkeypatch):
    client = InfraiClient(api_key="test")
    monkeypatch.setattr(client, "post", lambda *args, **kwargs: {})
    with pytest.raises(RuntimeError, match="still exists"):
        client.delete_collection("demo")
