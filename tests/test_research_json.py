"""Exercise the shipped CLI across real HTTP and process boundaries."""
import json
import os
import pathlib
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "skills/altair-research/scripts/altair_research.py"


class ResearchJson(unittest.TestCase):
    def run_cli(self, command, payloads, *extra):
        requests = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                requests.append(request["params"])
                payload = payloads[request["params"]["arguments"]["ticker"]]
                result = {"isError": True, "content": [{"text": payload}]} if isinstance(payload, str) else {"structuredContent": payload}
                body = json.dumps({"jsonrpc": "2.0", "id": 1, "result": result}).encode()
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
            result = subprocess.run([sys.executable, str(SCRIPT), command] + list(extra),
                                    env=env, capture_output=True, text=True, timeout=10)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        return result, requests

    def test_latest_preserves_raw_fields_sources_and_partial_failure(self):
        payload = {"ticker": "AAPL", "date": "2026-10-21", "decisions": [
            {"model": "one", "url": "https://altairworld.com/report", "rating": None,
             "currentPrice": "$200 (report time)", "summary": "x" * 800}]}
        result, requests = self.run_cli("latest", {"AAPL": payload, "MISSING": "No research"},
                                        "$aapl", "AAPL", "MISSING", "--json", "--summary-chars", "0")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["results"], [payload])
        self.assertEqual(data["errors"], [{"ticker": "MISSING", "message": "No research"}])
        self.assertEqual(data["schemaVersion"], 1)
        self.assertIsNone(data["requestedDate"])
        self.assertIn("not financial", data["disclaimer"])
        self.assertEqual(len(requests), 2)
        self.assertNotIn("includePrevious", requests[0]["arguments"])

    def test_changes_preserves_unavailable_and_both_dates(self):
        payload = {"ticker": "AAPL", "date": "2026-10-21", "decisions": [], "comparisons": [
            {"model": "one", "status": "unavailable", "current": {"date": "2026-10-21", "url": "https://altairworld.com/current"},
             "previous": {"date": "2026-10-14", "url": "https://altairworld.com/previous", "rating": None, "error": "Unavailable"}}]}
        result, requests = self.run_cli("changes", {"AAPL": payload}, "AAPL", "--json", "--date", "2026-10-21")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["results"], [payload])
        self.assertEqual(data["requestedDate"], "2026-10-21")
        self.assertEqual(requests[0]["arguments"], {"ticker": "AAPL", "date": "2026-10-21", "includePrevious": True})

    def test_older_server_is_explicit_failure_not_unchanged(self):
        result, _ = self.run_cli("changes", {"AAPL": {"ticker": "AAPL", "date": "2026-10-21", "decisions": []}}, "AAPL", "--json")
        self.assertEqual(result.returncode, 1)
        data = json.loads(result.stdout)
        self.assertEqual(data["results"], [])
        self.assertIn("missing is not unchanged", data["errors"][0]["message"])

    def test_malformed_response_does_not_emit_partial_json(self):
        result, _ = self.run_cli("latest", {"AAPL": {"ticker": "AAPL", "date": "bad", "decisions": []}}, "AAPL", "--json")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("invalid server response", result.stderr)

    def test_default_still_emits_markdown(self):
        result, _ = self.run_cli("latest", {"AAPL": {"ticker": "AAPL", "date": "2026-10-21", "decisions": []}}, "AAPL")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("# Altair TradingAgents research"))
        self.assertIn("Disclaimer:", result.stdout)

    def test_all_ticker_errors_still_produce_one_json_document(self):
        result, _ = self.run_cli("latest", {"AAPL": "No research"}, "AAPL", "--json")
        self.assertEqual(result.returncode, 1)
        data = json.loads(result.stdout)
        self.assertEqual(data["results"], [])
        self.assertEqual(len(data["errors"]), 1)
        self.assertEqual(result.stderr, "")

    def test_wrong_ticker_or_requested_date_cannot_be_reported_as_success(self):
        for payload in (
            {"ticker": "NVDA", "date": "2026-10-21", "decisions": []},
            {"ticker": "AAPL", "date": "2026-10-14", "decisions": []},
        ):
            with self.subTest(payload=payload):
                result, _ = self.run_cli("latest", {"AAPL": payload}, "AAPL", "--json", "--date", "2026-10-21")
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                self.assertIn("does not match request", result.stderr)


if __name__ == "__main__":
    unittest.main()
