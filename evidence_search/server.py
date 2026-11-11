"""Standard-library HTTP interface for evidence retrieval."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from typing import Any
from urllib.parse import urlsplit

from .corpus import EvidenceIndex, tokenize


MAX_REQUEST_BYTES = 1_048_576


class RequestError(ValueError):
    pass


class EvidenceHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], index: EvidenceIndex) -> None:
        if address[0] != "127.0.0.1":
            raise ValueError("server must bind to 127.0.0.1")
        self.index = index
        super().__init__(address, EvidenceRequestHandler)


class EvidenceRequestHandler(BaseHTTPRequestHandler):
    server: EvidenceHTTPServer

    def do_GET(self) -> None:
        try:
            path = self._request_path()
        except RequestError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        if path == "/health":
            self._send_json(200, {"status": "ok"})
            return
        self._send_json(404, {"error": "endpoint not found"})

    def do_POST(self) -> None:
        try:
            path = self._request_path()
        except RequestError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        if path != "/search":
            self._send_json(404, {"error": "endpoint not found"})
            return
        try:
            request = self._read_search_request()
        except RequestError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        results = self.server.index.search(
            request["client_id"], request["query"], request["limit"]
        )
        self._send_json(200, {"results": results})

    def do_DELETE(self) -> None:
        self._send_json(404, {"error": "endpoint not found"})

    do_HEAD = do_DELETE
    do_OPTIONS = do_DELETE
    do_PATCH = do_DELETE
    do_PUT = do_DELETE

    def _request_path(self) -> str:
        try:
            return urlsplit(self.path).path
        except ValueError as exc:
            raise RequestError("invalid request target") from exc

    def _read_search_request(self) -> dict[str, Any]:
        content_length = self.headers.get("Content-Length")
        try:
            length = int(content_length) if content_length is not None else -1
        except ValueError as exc:
            raise RequestError("invalid Content-Length") from exc
        if length < 0 or length > MAX_REQUEST_BYTES:
            raise RequestError("invalid request body length")
        try:
            raw_body = self.rfile.read(length).decode("utf-8")
            request = json.loads(raw_body, parse_constant=self._reject_json_constant)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RequestError("request body must be valid UTF-8 JSON") from exc
        if not isinstance(request, dict):
            raise RequestError("request body must be a JSON object")

        client_id = request.get("client_id")
        if not isinstance(client_id, str) or not client_id.strip():
            raise RequestError("client_id must be a nonempty string")
        query = request.get("query")
        if not isinstance(query, str) or not tokenize(query):
            raise RequestError("query must contain searchable terms")
        limit = request.get("limit")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 5:
            raise RequestError("limit must be an integer from 1 to 5")
        return {"client_id": client_id, "query": query, "limit": limit}

    def _reject_json_constant(self, constant: str) -> None:
        raise RequestError("request body must be valid UTF-8 JSON")

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode(
            "utf-8"
        )
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def send_error(
        self,
        code: int,
        message: str | None = None,
        explain: str | None = None,
    ) -> None:
        self._send_json(code, {"error": "invalid HTTP request"})

    def log_message(self, format: str, *args: object) -> None:
        return
