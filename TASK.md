# P04 — Evidence-Based Knowledge API V1

## Objective

Build a local HTTP service that retrieves verifiable
passages from a synthetic, client-scoped knowledge base.

This is a deterministic retrieval baseline for future
RAG applications, not an LLM or semantic answer engine.

## Runtime

Python standard library only.

Start:
python3 -m evidence_search \
  --corpus examples/documents.json \
  --port 8765

Bind exclusively to 127.0.0.1.

## Corpus

JSON root:
{"documents": [...]}

Every document requires:
- id: globally unique nonempty string
- client_id: nonempty string
- title: nonempty string
- text: nonempty string

Reject invalid corpus data before starting HTTP.

## Search API

GET /health
Returns HTTP 200 and {"status":"ok"}.

POST /search
JSON request:
{
  "client_id": "atlas-parts",
  "query": "LinkedIn product applications",
  "limit": 3
}

Require valid JSON, nonempty client_id, a query
containing searchable terms, and integer limit 1..5.

Return:
{
  "results": [
    {
      "document_id": "...",
      "title": "...",
      "score": 3,
      "quote": "...",
      "start": 0,
      "end": 50
    }
  ]
}

## Retrieval contract

- Search only documents belonging to client_id.
- Split document text into nonempty paragraphs
  separated by one or more blank lines.
- Tokenize Unicode words case-insensitively.
- Score each paragraph by the number of distinct
  query tokens that occur in that paragraph.
- Keep the best-scoring paragraph per document.
- Discard zero-score results.
- Sort by descending score, then document_id.
- Return at most limit results.
- Quote must be an exact substring of document text.
- start/end are Python string offsets in original text,
  with text[start:end] == quote.
- A query with no matches returns {"results":[]}.
- Unknown clients also return {"results":[]}.
- Never return evidence from another client.

## Errors

- Invalid requests: HTTP 400 with JSON error.
- Unknown endpoints: HTTP 404 with JSON error.
- No raw tracebacks or internal paths in HTTP errors.
- No persistent storage or external requests.

## Required verification

- Unit tests for document validation, paragraph offsets,
  token matching, ordering and client filtering.
- Integration tests using an actual local HTTP server.
- Test both matching and no-match responses.
- Verify exact quote offsets.
- Verify malformed request behavior.
- Verify no cross-client content exposure.
- README in English with commands, limitations,
  synthetic examples and truthful AI assistance disclosure.

## Scope limits

No authentication, external LLM, embeddings,
vector database, web UI, cloud deployment or new
third-party dependencies.

Do not modify TASK.md or examples/.
Do not modify earlier laboratory projects.
No remote, push, PR, deployment or customer data.
Keep the implementation proportional to the task.

One initial Builder, up to one corrective Builder
after review, and no unbounded retries.
