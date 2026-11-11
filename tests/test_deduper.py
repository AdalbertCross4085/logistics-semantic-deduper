from src.logistics_deduper import DuplicateDecision, LogisticsDeduper, ShipmentEvent


class FakeClient:
    def __init__(self):
        self.saved = []

    def embedding(self, text):
        return [1.0, 0.0]

    def ensure_collection(self, collection, dimension):
        self.collection = (collection, dimension)

    def query(self, collection, embedding):
        return [{"id": "evt-1001", "score": 0.97}]

    def upsert(self, collection, vector_id, embedding, metadata):
        self.saved.append(vector_id)


def test_high_similarity_event_is_marked_duplicate():
    decision = LogisticsDeduper(FakeClient()).inspect(
        ShipmentEvent("evt-1002", "ship-42", "delivered", "Shanghai", "Signed by receiving desk")
    )
    assert decision == DuplicateDecision("evt-1002", "evt-1001", 0.97)
