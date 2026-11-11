import os
from uuid import uuid4

from src.logistics_deduper import InfraiClient, LogisticsDeduper, ShipmentEvent


def main() -> None:
    if not os.environ.get("INFRAI_API_KEY"):
        raise SystemExit("Set INFRAI_API_KEY before running the demo")
    client = InfraiClient()
    collection = "shipment-demo-" + uuid4().hex
    deduper = LogisticsDeduper(client, collection=collection)
    event = ShipmentEvent("evt-1002", "ship-42", "delivered", "Shanghai", "Signed by receiving desk")
    try:
        print(deduper.inspect(event))
    finally:
        if deduper.dimension is not None:
            client.delete_collection(collection)
            print(f"Deleted and verified demo collection: {collection}")


if __name__ == "__main__":
    main()
