"""Exercise the market alerts command over HTTP without relying on production data."""
import json
import os
import pathlib
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "skills/altair-market/scripts/altair_market.py"


def reading(signal, text, was, previous=True):
    value = {"value": 1.0, "reading": text, "signal": signal, "bands": {"bullish": {"below": 10}}}
    if previous:
        value["previous"] = None if was is None else {"date": "2026-10-29", "value": 0.5, "signal": was}
    return value


def indicator(id_, name, value):
    return {"id": id_, "name": name, "family": "f", "unit": "index", "rule": "Example rule",
            "source": {"label": "Source", "url": None}, "evidence": "e", "value": value}


def market(previous=True):
    rows = [
        indicator("rsi2", "RSI (2-day)", {"SPX": reading("bullish", "8.8, oversold", "neutral", previous),
                                          "NDX": reading("neutral", "40.0", "neutral", previous),
                                          "SOX": reading("neutral", "35.0", "neutral", previous)}),
        indicator("trend200", "200-day trend", {"SPX": reading("bullish", "3% above", "bullish", previous),
                                                "NDX": reading("bullish", "2% above", "bullish", previous),
                                                "SOX": reading("neutral", "0.9% below", "bullish", previous)}),
        indicator("vrp", "Variance risk premium", {"SPX": reading("neutral", "1.0", None, previous),
                                                   "NDX": None, "SOX": None}),
    ]
    return {"indices": [{"symbol": symbol, "name": symbol, "date": "2026-10-30", "close": 100} for symbol in ("SPX", "NDX", "SOX")],
            "indicators": [dict(row, readings=row.pop("value")) for row in rows]}


def ticker(symbol):
    rows = [indicator("rsi2", "RSI (2-day)", reading("bullish", "9.3, oversold", "neutral")),
            indicator("impliedVol", "Implied volatility", None)]
    return {"instrument": {"symbol": symbol, "name": symbol, "date": "2026-10-30", "close": 50},
            "indicators": [dict(row, reading=row.pop("value")) for row in rows], "disclaimer": "d"}


class AlertsCLI(unittest.TestCase):
    def run_cli(self, arguments, answer):
        requests = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                requests.append(request["params"])
                body = json.dumps(answer(request["params"]["name"], request["params"]["arguments"])).encode()
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
            result = subprocess.run([sys.executable, str(SCRIPT), "alerts"] + arguments,
                                    env=env, capture_output=True, text=True, timeout=10)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        return result, requests

    def test_default_lists_changes_once_and_keeps_missing_comparisons_apart(self):
        result, requests = self.run_cli([], lambda name, arguments: {"result": {"structuredContent": market()}})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([request["name"] for request in requests], ["get_market_indicators"])
        out = result.stdout
        self.assertIn("# Altair indicator alerts · SPX, NDX, SOX · reading date 2026-10-30\n", out)
        self.assertIn("| SPX | RSI (2-day) | neutral on 2026-10-29 | bullish | 8.8, oversold |", out)
        self.assertIn("## Back to neutral", out)
        self.assertIn("| SOX | 200-day trend | bullish on 2026-10-29 | 0.9% below |", out)
        self.assertNotIn("| NDX | RSI (2-day)", out)
        self.assertNotIn("3% above", out)
        self.assertIn("- SPX: Variance risk premium\n- NDX: Variance risk premium\n- SOX: Variance risk premium", out)
        self.assertIn("Disclaimer: Market readings for information", out)

    def test_symbols_are_read_in_order_and_one_failure_is_listed(self):
        def answer(name, arguments):
            if name == "get_ticker_indicators" and arguments["ticker"] == "XYZ":
                return {"error": {"message": "Yahoo Finance has no daily closes for XYZ"}}
            if name == "get_ticker_indicators":
                return {"result": {"structuredContent": ticker(arguments["ticker"])}}
            return {"result": {"structuredContent": market()}}

        result, requests = self.run_cli(["spx", "spy", "xyz", "SPY"], answer)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(requests, [{"name": "get_market_indicators", "arguments": {}},
                                    {"name": "get_ticker_indicators", "arguments": {"ticker": "SPY"}},
                                    {"name": "get_ticker_indicators", "arguments": {"ticker": "XYZ"}}])
        self.assertIn("# Altair indicator alerts · SPX, SPY · reading date 2026-10-30", result.stdout)
        self.assertIn("| SPY | RSI (2-day) | neutral on 2026-10-29 | bullish | 9.3, oversold |", result.stdout)
        self.assertIn("- SPY: Implied volatility", result.stdout)
        self.assertIn("## Unavailable symbols\n\n- XYZ: get_ticker_indicators: Yahoo Finance has no daily closes for XYZ", result.stdout)

        failing, _ = self.run_cli(["SPY", "XYZ"], lambda name, arguments: {"error": {"message": "no data"}})
        self.assertEqual(failing.returncode, 1)
        self.assertIn("no symbol could be read", failing.stderr)
        self.assertEqual(failing.stdout, "")

    def test_json_keeps_server_readings_and_failures(self):
        result, _ = self.run_cli(["SPX", "--json"], lambda name, arguments: {"result": {"structuredContent": market()}})
        self.assertEqual(result.returncode, 0, result.stderr)
        document = json.loads(result.stdout)
        self.assertEqual((document["schemaVersion"], document["command"]), (1, "alerts"))
        [spx] = document["data"]["symbols"]
        self.assertEqual([entry["id"] for entry in spx["turned"]], ["rsi2"])
        self.assertEqual(spx["turned"][0]["reading"]["previous"], {"date": "2026-10-29", "value": 0.5, "signal": "neutral"})
        self.assertEqual([entry["id"] for entry in spx["noComparison"]], ["vrp"])
        self.assertEqual(document["data"]["unavailable"], [])

    def test_server_without_previous_readings_fails_without_output(self):
        result, _ = self.run_cli([], lambda name, arguments: {"result": {"structuredContent": market(previous=False)}})
        self.assertEqual(result.returncode, 1)
        self.assertIn("previous-session", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_more_than_ten_symbols_rejected_before_network(self):
        result, requests = self.run_cli(list("ABCDEFGHIJK"), lambda name, arguments: {})
        self.assertEqual(result.returncode, 2)
        self.assertIn("at most 10 symbols", result.stderr)
        self.assertEqual(requests, [])


if __name__ == "__main__":
    unittest.main()
