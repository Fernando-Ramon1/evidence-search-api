# Evidence-Based Knowledge API V1

This repository provides a small, deterministic HTTP service for retrieving
verifiable passages from a client-scoped JSON corpus. It uses only the Python
standard library and requires no installation or network access.

## Run the service

Python 3.10 or newer is required. From the repository root:

```sh
python3 -m evidence_search --corpus examples/documents.json --port 8765
```

The server binds exclusively to `127.0.0.1`. Check it with:

```sh
curl http://127.0.0.1:8765/health
curl -X POST http://127.0.0.1:8765/search \
  -H 'Content-Type: application/json' \
  -d '{"client_id":"atlas-parts","query":"LinkedIn product applications","limit":3}'
```

The second command returns the best matching paragraph from `atlas-01`, with
its exact quote and Python string offsets into the original document. The
corpus and requests shown here are synthetic.

## Tests

Run the unit and local HTTP integration tests with:

```sh
python3 -m unittest discover -s tests -v
```

The integration tests start a real server on an operating-system-assigned
loopback port and shut it down after the test class completes.

## Retrieval behavior and limitations

The service splits documents into paragraphs at blank lines and indexes
case-folded Unicode word tokens. A paragraph's score is the number of distinct
query tokens it contains. It keeps one best paragraph per document, then sorts
results by descending score and document ID. Client filtering occurs before
retrieval, and unknown clients or unmatched queries return an empty result.

This is a lexical retrieval baseline. It does not understand synonyms,
meaning, word importance, or natural-language answers. The corpus is loaded
into memory at startup and cannot be changed through the API. There is no
authentication, persistent storage, LLM, embedding model, vector database,
web interface, external request, or cloud deployment. Loopback binding makes
the service local-only; it is not intended to be exposed as a production API.

## AI assistance disclosure

The implementation, tests, and documentation were produced with AI
assistance. Their behavior is supported by the included automated tests; this
is not a claim of independent human review or certification.
