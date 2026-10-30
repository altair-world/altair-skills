"""Exercise the real market CLI over HTTP without relying on production data."""
import json
import os
import pathlib
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "skills/altair-market/scripts/altair_market.py"


def snapshot():
    def indicator(name, reading):
        return {"name": name, "unit": "percent", "reading": reading,
                "rule": "Example rule", "source": {"label": "Research source", "url": "https://example.com/paper"}}
    return {"instrument": {"symbol": "NVDA", "name": "Nvidia", "date": "2026-10-27", "close": 217.94},
            "indicators": [indicator("Trend", {"value": 0.12, "reading": "Above average", "signal": "bullish"}),
                           indicator("Implied volatility", None), indicator("Variance risk premium", None)],
            "disclaimer": "Server informational disclaimer"}


class TickerCLI(unittest.TestCase):
    def run_cli(self, message, arguments=None):
        requests = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                requests.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                body = json.dumps(message).encode()
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
            result = subprocess.run([sys.executable, str(SCRIPT)] + (arguments or ["ticker", " nvda "]),
                                    env=env, capture_output=True, text=True, timeout=10)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        return result, requests

    def test_latest_sources_nulls_and_context(self):
        result, requests = self.run_cli({"result": {"structuredContent": snapshot()}})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(requests[0]["params"], {"name": "get_ticker_indicators", "arguments": {"ticker": "NVDA"}})
        self.assertIn("reading date 2026-10-27", result.stdout)
        self.assertIn("close 217.94", result.stdout)
        self.assertIn("12.00%", result.stdout)
        self.assertIn("| Implied volatility | n/a | unavailable | n/a |", result.stdout)
        self.assertIn("| Variance risk premium | n/a | unavailable | n/a |", result.stdout)
        for text in ("Example rule", "https://example.com/paper", "Server informational disclaimer",
                     "not financial or investment advice", "session can still be open",
                     "not measurements of this stock", "does not validate returns"):
            self.assertIn(text, result.stdout)
        self.assertEqual(len(requests), 1)

    def test_json_preserves_source_payload_without_display_rounding(self):
        data = snapshot()
        data["instrument"]["close"] = 217.941234
        result, requests = self.run_cli({"result": {"structuredContent": data}}, ["ticker", "nvda", "--json"])
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["data"], data)
        self.assertEqual(output["schemaVersion"], 1)
        self.assertEqual(output["command"], "ticker")
        self.assertIn("+00:00", output["fetchedAt"])
        self.assertIn("not financial", output["disclaimer"])
        self.assertEqual(len(requests), 1)

    def test_json_index_selection_preserves_null_and_missing_readings(self):
        data = {"indices": [{"symbol": symbol, "name": symbol, "date": "2026-10-27", "close": 100}
                            for symbol in ("SPX", "NDX", "SOX")], "indicators": [
            {"name": "Trend", "unit": "percent", "readings": {"SPX": {"value": 0.1234567, "reading": "Above", "signal": "bullish"}, "NDX": None},
             "rule": "Rule", "source": {"label": "Source", "url": "https://example.com"}}]}
        result, requests = self.run_cli({"result": {"structuredContent": data}}, ["indicators", "ndx", "NDX", "sox", "--json"])
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)["data"]
        self.assertEqual([index["symbol"] for index in output["indices"]], ["NDX", "SOX"])
        self.assertEqual(output["indicators"][0]["readings"], {"NDX": None})
        self.assertEqual(output["indicators"][0]["source"], data["indicators"][0]["source"])
        self.assertEqual(requests[0]["params"]["arguments"], {})

    def test_json_breadth_history_is_source_data(self):
        row = {"date": "2026-10-27", "all": 70, "nasdaq100": 60, "sox": None}
        data = {"movingAverage": 20, "latest": dict(row, benchmarks={"SPX": 100, "NDX": 200, "SOX": None}, sectors=[]), "history": [row]}
        result, requests = self.run_cli({"result": {"structuredContent": data}}, ["breadth", "--days", "5", "--json"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["data"], data)
        self.assertEqual(requests[0]["params"]["arguments"], {"days": 5})

    def test_json_errors_never_emit_success_or_partial_document(self):
        mismatch = snapshot()
        mismatch["instrument"]["symbol"] = "SPX"
        for message in ({"result": {"structuredContent": mismatch}},
                        {"result": {"structuredContent": {}}},
                        {"result": {"isError": True, "content": [{"text": "Unavailable"}]}}):
            result, requests = self.run_cli(message, ["ticker", "NVDA", "--json"])
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertEqual(len(requests), 1)

    def test_unsupported_tool_and_upstream_error_do_not_fallback(self):
        for message in ({"error": {"message": "Unknown tool get_ticker_indicators"}},
                        {"result": {"isError": True, "content": [{"text": "Ticker unavailable"}]}}):
            with self.subTest(message=message):
                result, requests = self.run_cli(message)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                self.assertNotIn("Traceback", result.stderr)
                self.assertEqual(len(requests), 1)

    def test_malformed_or_mismatched_payload_never_prints_partial_readings(self):
        mismatch = snapshot()
        mismatch["instrument"]["symbol"] = "SPX"
        for message in ({"result": None}, {"result": {"structuredContent": {}}},
                        {"result": {"structuredContent": mismatch}},
                        {"result": {"structuredContent": {"instrument": None}}}):
            with self.subTest(message=message):
                result, _ = self.run_cli(message)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                self.assertIn("invalid server response", result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_invalid_symbols_rejected_before_network(self):
        for symbol in ("", "A B", "$NVDA", "NVDA/AMD", "A" * 21, "-NVDA"):
            with self.subTest(symbol=symbol):
                result, requests = self.run_cli({}, ["ticker", symbol])
                self.assertEqual(result.returncode, 2)
                self.assertEqual(requests, [])

    def test_yahoo_symbol_formats_are_preserved(self):
        for symbol in ("brk-b", "0700.hk", "^gspc", "es=f"):
            with self.subTest(symbol=symbol):
                data = snapshot()
                data["instrument"]["symbol"] = symbol.upper()
                result, requests = self.run_cli({"result": {"structuredContent": data}}, ["ticker", symbol])
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(requests[0]["params"]["arguments"], {"ticker": symbol.upper()})

    def test_existing_indices_remain_index_only_and_empty_input_contract(self):
        result, requests = self.run_cli({"result": {"structuredContent": {"indices": [], "indicators": []}}}, ["indicators", "NDX"])
        self.assertEqual(requests[0]["params"], {"name": "get_market_indicators", "arguments": {}})
        self.assertEqual(result.returncode, 1)
        result, requests = self.run_cli({}, ["indicators", "NVDA"])
        self.assertEqual(result.returncode, 2)
        self.assertEqual(requests, [])

    def test_existing_index_rendering_and_local_selection(self):
        data = {"indices": [{"symbol": symbol, "name": symbol, "date": "2026-10-27", "close": 100}
                            for symbol in ("SPX", "NDX", "SOX")], "indicators": []}
        result, requests = self.run_cli({"result": {"structuredContent": data}}, ["indicators", "ndx", "NDX", "sox"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(requests[0]["params"], {"name": "get_market_indicators", "arguments": {}})
        self.assertEqual(result.stdout.count("## NDX ·"), 1)
        self.assertIn("## SOX ·", result.stdout)
        self.assertNotIn("## SPX ·", result.stdout)

    def test_existing_breadth_latest_and_history(self):
        row = {"date": "2026-10-27", "all": 70, "nasdaq100": 60, "sox": 50}
        data = {"movingAverage": 20, "latest": dict(row, benchmarks={"SPX": 100, "NDX": 200, "SOX": 300},
                sectors=[{"name": "Information Technology", "stocks": 69, "above": 72}]), "history": [row]}
        for args, days in ((["breadth"], 1), (["breadth", "--days", "5"], 5)):
            with self.subTest(args=args):
                result, requests = self.run_cli({"result": {"structuredContent": data}}, args)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(requests[0]["params"], {"name": "get_market_breadth", "arguments": {"days": days}})
                self.assertIn("| Information Technology | 69 | 72% |", result.stdout)
                self.assertEqual("## Recent breadth" in result.stdout, days == 5)


if __name__ == "__main__":
    unittest.main()
