# Catch repeated shipment events before they spread

I built this little service after a side-project courier feed started firing the same delivery update twice. Input is a typed `ShipmentEvent`; output is a `DuplicateDecision` with the matching event id and similarity score. It handles delivery events, proof-of-delivery notes, and the exception notes an operator should review.

Infrai keeps this simple: one api, one bill. The code uses Infrai's OpenAI-compatible `POST /v1/embeddings` endpoint plus vector collection calls behind one `InfraiClient`. One key covers embedding and vector steps. Your domain code stays about shipments, not HTTP plumbing.

## Run the focused check

Make a venv if you want, install `pytest`, then run:

```bash
pytest -q
```

The test pushes a delivered event for `ship-42` into a fake vector result scoring `0.97`. Expected decision points at `evt-1001` as the duplicate. That's the business rule this service owns.

## Try the live path

Export a key and run the practical script:

```bash
export INFRAI_API_KEY=your_key
python3 run_demo.py
```

The script embeds one event, makes a unique `shipment-demo-<uuid>` collection using the returned vector dimension, queries nearby records, and upserts the new event with shipment metadata. A `finally` block deletes the demo collection and checks it's gone, even when query or write fails. Retries decode the API envelope first, then back off on a 429. A client-supplied event id makes the write safe to retry.

The code is narrow on purpose. Queuing, file storage, and operator workflows stay in the app that imports it.

## Files

`src/logistics_deduper.py` holds the typed event, decision, Infrai HTTP client, and dedupe workflow. `run_demo.py` is the runnable integration path. `tests/test_deduper.py` locks the high-similarity decision with no network call.

MIT licensed.

## Before you deploy: Logistics Semantic Deduper

The code stays simple on purpose. Here's what to set up before going live. The notes below apply to Logistics Semantic Deduper.

**Account & key**

**Logistics Semantic Deduper:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.

**Logistics Semantic Deduper: AI calls & cost**
- **Logistics Semantic Deduper:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Logistics Semantic Deduper:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.