"""Command-line entry point for the local evidence service."""

from __future__ import annotations

import argparse

from .corpus import CorpusError, load_corpus
from .server import EvidenceHTTPServer


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Evidence Search API")
    parser.add_argument("--corpus", required=True, help="path to the JSON corpus")
    parser.add_argument("--port", required=True, type=int, help="local TCP port")
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("port must be between 0 and 65535")
    try:
        index = load_corpus(args.corpus)
    except CorpusError as exc:
        parser.error(str(exc))

    server = EvidenceHTTPServer(("127.0.0.1", args.port), index)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
