"""Deterministic, client-scoped evidence retrieval."""

from .corpus import CorpusError, EvidenceIndex, load_corpus

__all__ = ["CorpusError", "EvidenceIndex", "load_corpus"]
