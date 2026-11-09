from http.client import HTTPConnection
import json
from pathlib import Path
import threading
import unittest

from evidence_search.corpus import load_corpus
from evidence_search.server import EvidenceHTTPServer


ROOT = Path(__file__).resolve().parents[1]


class HTTPIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        index = load_corpus(ROOT / "examples" / "documents.json")
        cls.server = EvidenceHTTPServer(("127.0.0.1", 0), index)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        if cls.thread.is_alive():
            raise RuntimeError("HTTP test server did not stop")

    def request(self, method, path, body=None, headers=None):
        connection = HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            payload = json.loads(response.read().decode("utf-8"))
            return response.status, response.getheader("Content-Type"), payload
        finally:
            connection.close()

    def search(self, payload):
        return self.request(
            "POST",
            "/search",
            json.dumps(payload).encode("utf-8"),
            {"Content-Type": "application/json"},
        )

    def test_health_and_unknown_endpoint_return_json(self):
        status, content_type, payload = self.request("GET", "/health")
        self.assertEqual((status, payload), (200, {"status": "ok"}))
        self.assertTrue(content_type.startswith("application/json"))

        status, content_type, payload = self.request("GET", "/missing")
        self.assertEqual(status, 404)
        self.assertTrue(content_type.startswith("application/json"))
        self.assertIn("error", payload)

    def test_matching_search_has_exact_quote_offsets(self):
        status, _, payload = self.search(
            {"client_id": "atlas-parts", "query": "LinkedIn product applications", "limit": 3}
        )
        self.assertEqual(status, 200)
        first = payload["results"][0]
        self.assertEqual(first["document_id"], "atlas-01")
        documents = json.loads(
            (ROOT / "examples" / "documents.json").read_text(encoding="utf-8")
        )["documents"]
        source = next(item["text"] for item in documents if item["id"] == "atlas-01")
        self.assertEqual(source[first["start"] : first["end"]], first["quote"])

    def test_no_match_unknown_client_and_cross_client_queries_are_empty(self):
        requests = [
            {"client_id": "atlas-parts", "query": "unconfirmed event dates", "limit": 3},
            {"client_id": "unknown-client", "query": "LinkedIn", "limit": 3},
            {"client_id": "northstar-events", "query": "automotive durability", "limit": 3},
        ]
        for request in requests:
            with self.subTest(request=request):
                status, _, payload = self.search(request)
                self.assertEqual(status, 200)
                self.assertEqual(payload, {"results": []})

    def test_malformed_and_invalid_requests_return_safe_json_errors(self):
        invalid_requests = [
            (b"{", {"Content-Type": "application/json"}),
            (json.dumps([]).encode(), {"Content-Type": "application/json"}),
            (json.dumps({"client_id": "x", "query": "!!!", "limit": 1}).encode(), {}),
            (json.dumps({"client_id": "x", "query": "word", "limit": True}).encode(), {}),
            (json.dumps({"client_id": "x", "query": "word", "limit": 0}).encode(), {}),
            (json.dumps({"client_id": "x", "query": "word", "limit": 6}).encode(), {}),
        ]
        for body, headers in invalid_requests:
            with self.subTest(body=body):
                status, content_type, payload = self.request(
                    "POST", "/search", body, headers
                )
                self.assertEqual(status, 400)
                self.assertTrue(content_type.startswith("application/json"))
                self.assertEqual(set(payload), {"error"})
                self.assertNotIn("Traceback", payload["error"])
                self.assertNotIn(str(ROOT), payload["error"])

    def test_server_rejects_non_loopback_bind_address(self):
        index = load_corpus(ROOT / "examples" / "documents.json")
        with self.assertRaisesRegex(ValueError, "127.0.0.1"):
            EvidenceHTTPServer(("0.0.0.0", 0), index)


if __name__ == "__main__":
    unittest.main()
