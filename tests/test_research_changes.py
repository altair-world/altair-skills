"""CLI compatibility through real loopback HTTP, without production dependencies."""
import json
import os
import pathlib
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "skills/altair-research/scripts/altair_research.py"


class ChangesCompatibility(unittest.TestCase):
    def run_cli(self, payload):
        requests = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                requests.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                body = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"structuredContent": payload}}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            env = dict(os.environ, ALTAIR_MCP_URL="http://127.0.0.1:{}/mcp/free".format(server.server_port))
            result = subprocess.run([sys.executable, str(SCRIPT), "changes", "$aapl", "AAPL"],
                                    env=env, capture_output=True, text=True, timeout=10)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]["params"], {"name": "get_research_decisions", "arguments": {"ticker": "AAPL", "includePrevious": True}})
        return result

    def test_older_server_does_not_look_unchanged(self):
        result = self.run_cli({"ticker": "AAPL", "date": "2026-10-21", "decisions": []})
        self.assertEqual(result.returncode, 1)
        self.assertIn("does not support research comparisons", result.stdout)
        self.assertNotIn("· unchanged", result.stdout)

    def test_failed_previous_keeps_both_sources_and_unavailable(self):
        current = {"date": "2026-10-21", "url": "https://altairworld.com/current", "rating": "Hold"}
        previous = {"date": "2026-10-14", "url": "https://altairworld.com/previous", "rating": None, "error": "Unavailable"}
        result = self.run_cli({"ticker": "AAPL", "date": "2026-10-21", "comparisons": [
            {"model": "exact-model", "current": current, "previous": previous, "status": "unavailable"}]})
        self.assertEqual(result.returncode, 0)
        self.assertIn("exact-model · unavailable", result.stdout)
        self.assertIn(current["url"], result.stdout)
        self.assertIn(previous["url"], result.stdout)
        self.assertIn("Previous: 2026-10-14 · unavailable", result.stdout)
        self.assertIn("not financial or investment advice", result.stdout)


if __name__ == "__main__":
    unittest.main()
