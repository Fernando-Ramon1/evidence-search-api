"""Corpus validation, paragraph indexing, and lexical retrieval."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import unicodedata
from typing import Any


LINE_BOUNDARY_RE = (
    r"(?:\r\n|(?<!\r)\n|\r(?!\n)|[\v\f\x1c-\x1e\x85\u2028\u2029])"
)
PARAGRAPH_SEPARATOR_RE = re.compile(
    LINE_BOUNDARY_RE
    + r"(?:[^\S\n\v\f\r\x1c-\x1e\x85\u2028\u2029]*"
    + LINE_BOUNDARY_RE
    + r")+"
)


class CorpusError(ValueError):
    """Raised when a corpus does not satisfy the input contract."""


@dataclass(frozen=True)
class Paragraph:
    text: str
    start: int
    end: int
    tokens: frozenset[str]


@dataclass(frozen=True)
class Document:
    document_id: str
    client_id: str
    title: str
    text: str
    paragraphs: tuple[Paragraph, ...]


def tokenize(text: str) -> frozenset[str]:
    """Return distinct, case-folded Unicode word tokens."""
    tokens: set[str] = set()
    word: list[str] = []
    for character in unicodedata.normalize("NFC", text):
        if character == "_" or character.isalnum():
            word.append(character)
        elif word and unicodedata.category(character).startswith("M"):
            word.append(character)
        else:
            _append_token(tokens, word)
    _append_token(tokens, word)
    return frozenset(tokens)


def _append_token(tokens: set[str], word: list[str]) -> None:
    if not word:
        return
    tokens.add(unicodedata.normalize("NFC", "".join(word).casefold()))
    word.clear()


def split_paragraphs(text: str) -> tuple[Paragraph, ...]:
    """Split text on blank lines while retaining offsets into the source text."""
    paragraphs: list[Paragraph] = []
    start = 0
    for separator in PARAGRAPH_SEPARATOR_RE.finditer(text):
        _append_paragraph(paragraphs, text, start, separator.start())
        start = separator.end()
    _append_paragraph(paragraphs, text, start, len(text))
    return tuple(paragraphs)


def _append_paragraph(
    paragraphs: list[Paragraph], text: str, start: int, end: int
) -> None:
    if start == end or not text[start:end].strip():
        return
    quote = text[start:end]
    paragraphs.append(Paragraph(quote, start, end, tokenize(quote)))


class EvidenceIndex:
    """An immutable in-memory index partitioned by client."""

    def __init__(self, documents: tuple[Document, ...]) -> None:
        by_client: dict[str, list[Document]] = {}
        for document in documents:
            by_client.setdefault(document.client_id, []).append(document)
        self._by_client = {
            client_id: tuple(client_documents)
            for client_id, client_documents in by_client.items()
        }

    def search(self, client_id: str, query: str, limit: int) -> list[dict[str, Any]]:
        query_tokens = tokenize(query)
        ranked: list[tuple[int, str, Document, Paragraph]] = []
        for document in self._by_client.get(client_id, ()):
            best: Paragraph | None = None
            best_score = 0
            for paragraph in document.paragraphs:
                score = len(query_tokens & paragraph.tokens)
                if score > best_score:
                    best = paragraph
                    best_score = score
            if best is not None:
                ranked.append((-best_score, document.document_id, document, best))

        ranked.sort(key=lambda item: (item[0], item[1]))
        return [
            {
                "document_id": document.document_id,
                "title": document.title,
                "score": -negative_score,
                "quote": paragraph.text,
                "start": paragraph.start,
                "end": paragraph.end,
            }
            for negative_score, _, document, paragraph in ranked[:limit]
        ]


def load_corpus(path: str | Path) -> EvidenceIndex:
    try:
        with Path(path).open(encoding="utf-8") as corpus_file:
            data = json.load(corpus_file)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CorpusError("corpus could not be read as UTF-8 JSON") from exc
    return build_index(data)


def build_index(data: Any) -> EvidenceIndex:
    if not isinstance(data, dict) or not isinstance(data.get("documents"), list):
        raise CorpusError("corpus root must contain a documents array")

    documents: list[Document] = []
    seen_ids: set[str] = set()
    for position, raw_document in enumerate(data["documents"]):
        if not isinstance(raw_document, dict):
            raise CorpusError(f"document {position} must be an object")
        values: dict[str, str] = {}
        for field in ("id", "client_id", "title", "text"):
            value = raw_document.get(field)
            if not isinstance(value, str) or not value.strip():
                raise CorpusError(
                    f"document {position} field {field} must be a nonempty string"
                )
            values[field] = value
        if values["id"] in seen_ids:
            raise CorpusError(f"duplicate document id: {values['id']}")
        seen_ids.add(values["id"])
        documents.append(
            Document(
                document_id=values["id"],
                client_id=values["client_id"],
                title=values["title"],
                text=values["text"],
                paragraphs=split_paragraphs(values["text"]),
            )
        )
    return EvidenceIndex(tuple(documents))
