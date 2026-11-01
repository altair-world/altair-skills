"""Date discovery through the real CLI, HTTP and MCP process boundary."""
import json
import os
import pathlib
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "skills/altair-research/scripts/altair_research.py"


def report(number, date="2026-10-21", model="GPT"):
    return {"ticker": "NVDA", "date": date, "model": model,
            "url": "https://altairworld.com/TradingAgents/NVDA/report-{}/complete_report/".format(number)}


class ResearchDates(unittest.TestCase):
    def run_cli(self, pages, *args):
        requests = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                requests.append(request["params"])
                payload = pages[min(len(requests) - 1, len(pages) - 1)]
                result = {"isError": True, "content": [{"text": payload}]} if isinstance(payload, str) else {"structuredContent": payload}
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"jsonrpc": "2.0", "id": 1, "result": result}).encode())

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = subprocess.run([sys.executable, str(SCRIPT), "dates"] + list(args),
                env=dict(os.environ, ALTAIR_MCP_URL="http://127.0.0.1:{}/mcp/free".format(server.server_port)),
                capture_output=True, text=True, timeout=10)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        return result, requests

    def test_pagination_groups_reruns_and_models_without_reading_reports(self):
        rows = [report(n) for n in range(100)] + [report(100, "2026-10-14", "Claude"), report(101, model="Claude")]
        result, requests = self.run_cli([{"total": 102, "reports": rows[:100]}, {"total": 102, "reports": rows[100:]}], "$nvda", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertTrue(data["complete"])
        self.assertEqual(data["scannedReports"], 102)
        self.assertEqual(data["dates"], [{"date": "2026-10-21", "models": ["Claude", "GPT"], "reports": 101},
                                        {"date": "2026-10-14", "models": ["Claude"], "reports": 1}])
        self.assertEqual(requests, [{"name": "list_research_reports", "arguments": {"ticker": "NVDA", "limit": 100, "offset": offset}} for offset in (0, 100)])

    def test_bounded_scan_never_claims_complete_or_newest(self):
        page = {"total": 101, "reports": [report(n) for n in range(100)]}
        result, requests = self.run_cli([page], "NVDA", "--json", "--max-pages", "1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)["complete"])
        self.assertEqual(len(requests), 1)
        result, _ = self.run_cli([page], "NVDA", "--max-pages", "1")
        self.assertIn("Partial catalog", result.stdout)

    def test_empty_is_explicit_and_markdown_retains_sources_and_disclaimer(self):
        result, _ = self.run_cli([{"total": 0, "reports": []}], "NVDA", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["dates"], [])
        self.assertTrue(json.loads(result.stdout)["complete"])
        result, _ = self.run_cli([{"total": 1, "reports": [report(1)]}], "NVDA")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("2026-10-21", result.stdout)
        self.assertIn("latest NVDA --date", result.stdout)
        self.assertIn("not financial", result.stdout)

    def test_failure_mid_scan_emits_no_partial_success(self):
        first = {"total": 101, "reports": [report(n) for n in range(100)]}
        for second in ("Unavailable", {"total": 102, "reports": [report(100)]},
                       {"total": 101, "reports": [report(0)]}, {"total": 101, "reports": []}):
            result, _ = self.run_cli([first, second], "NVDA", "--json")
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertNotIn("Traceback", result.stderr)

    def test_invalid_metadata_and_invalid_input(self):
        for row in (dict(report(1), ticker="AAPL"), dict(report(1), date="invalid"), dict(report(1), model=None),
                    dict(report(1), url="http://remote.example/report"), dict(report(1), ticker=None), []):
            result, _ = self.run_cli([{"total": 1, "reports": [row]}], "NVDA", "--json")
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertNotIn("Traceback", result.stderr)
        for args in (("NVDA,AMD",), ("",), ("NVDA", "--max-pages", "0"), ("NVDA", "--max-pages", "11")):
            result, requests = self.run_cli([{}], *args)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(requests, [])

    def test_local_pages_source_urls_are_supported_without_fetching_them(self):
        row = dict(report(1), url="http://127.0.0.1:8813/TradingAgents/NVDA/report/complete_report/")
        result, requests = self.run_cli([{"total": 1, "reports": [row]}], "NVDA", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["complete"])
        self.assertEqual(len(requests), 1)


if __name__ == "__main__":
    unittest.main()
