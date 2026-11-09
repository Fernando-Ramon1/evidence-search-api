import json
from pathlib import Path
import tempfile
import unittest

from evidence_search.corpus import CorpusError, build_index, load_corpus, split_paragraphs


ROOT = Path(__file__).resolve().parents[1]


def document(
    document_id="doc-1", client_id="client-a", title="Title", text="Evidence"
):
    return {
        "id": document_id,
        "client_id": client_id,
        "title": title,
        "text": text,
    }


class CorpusValidationTests(unittest.TestCase):
    def test_rejects_invalid_roots_and_documents(self):
        invalid_corpora = [
            None,
            {},
            {"documents": {}},
            {"documents": [None]},
            {"documents": [document(title="   ")]},
            {"documents": [document(text=3)]},
        ]
        for corpus in invalid_corpora:
            with self.subTest(corpus=corpus), self.assertRaises(CorpusError):
                build_index(corpus)

    def test_rejects_duplicate_document_ids_across_clients(self):
        corpus = {
            "documents": [
                document(document_id="shared", client_id="client-a"),
                document(document_id="shared", client_id="client-b"),
            ]
        }
        with self.assertRaisesRegex(CorpusError, "duplicate document id"):
            build_index(corpus)

    def test_load_rejects_malformed_json_without_exposing_path(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "private-corpus.json"
            path.write_text("{", encoding="utf-8")
            with self.assertRaises(CorpusError) as context:
                load_corpus(path)
        self.assertNotIn(str(path), str(context.exception))


class ParagraphTests(unittest.TestCase):
    def test_offsets_preserve_unicode_and_original_line_endings(self):
        text = "Café custa €5.\r\n\r\n  Ação rápida 中文.\r\ncontinua"
        paragraphs = split_paragraphs(text)
        self.assertEqual([item.text for item in paragraphs], [
            "Café custa €5.",
            "  Ação rápida 中文.\r\ncontinua",
        ])
        for paragraph in paragraphs:
            self.assertEqual(text[paragraph.start : paragraph.end], paragraph.text)

    def test_multiple_and_whitespace_only_blank_lines_are_separators(self):
        text = "first\n  \n\nsecond"
        self.assertEqual(
            [paragraph.text for paragraph in split_paragraphs(text)],
            ["first", "second"],
        )


class RetrievalTests(unittest.TestCase):
    def test_unicode_casefolding_and_distinct_query_token_scoring(self):
        index = build_index(
            {"documents": [document(text="Straße café CAFÉ 中文")]}
        )
        result = index.search("client-a", "STRASSE café café 中文", 5)[0]
        self.assertEqual(result["score"], 3)

    def test_keeps_first_best_paragraph_and_exact_offsets(self):
        text = "alpha first\n\nalpha second"
        index = build_index({"documents": [document(text=text)]})
        result = index.search("client-a", "alpha", 1)[0]
        self.assertEqual(result["quote"], "alpha first")
        self.assertEqual(text[result["start"] : result["end"]], result["quote"])

    def test_orders_by_score_then_document_id_and_applies_limit(self):
        index = build_index(
            {
                "documents": [
                    document("z-doc", text="alpha beta"),
                    document("b-doc", text="alpha"),
                    document("a-doc", text="alpha"),
                ]
            }
        )
        results = index.search("client-a", "alpha beta", 2)
        self.assertEqual([item["document_id"] for item in results], ["z-doc", "a-doc"])
        self.assertEqual([item["score"] for item in results], [2, 1])

    def test_filters_by_client_before_returning_evidence(self):
        secret = "private evidence unique"
        index = build_index(
            {
                "documents": [
                    document("a", "client-a", text="public evidence"),
                    document("b", "client-b", text=secret),
                ]
            }
        )
        results = index.search("client-a", "private unique", 5)
        self.assertEqual(results, [])
        self.assertNotIn(secret, json.dumps(results))
        self.assertEqual(index.search("unknown", "evidence", 5), [])

    def test_synthetic_queries_follow_frozen_examples(self):
        index = load_corpus(ROOT / "examples" / "documents.json")
        cases = json.loads(
            (ROOT / "examples" / "queries.json").read_text(encoding="utf-8")
        )["cases"]
        for case in cases:
            with self.subTest(case=case):
                results = index.search(case["client_id"], case["query"], case["limit"])
                if "expected_first_document" in case:
                    self.assertEqual(
                        results[0]["document_id"], case["expected_first_document"]
                    )
                else:
                    self.assertEqual(len(results), case["expected_count"])


if __name__ == "__main__":
    unittest.main()
