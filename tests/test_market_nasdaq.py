"""Actual CLI/HTTP contract checks for the constituent snapshot command."""
import copy
import json
import unittest
import test_market_ticker as cli


def snapshot():
    rows = []
    for symbol, close, previous in (("AAPL", 101.123456, 100), ("MSFT", 100, 100), ("NVDA", 99, 100)):
        change = close - previous
        rows.append(dict(symbol=symbol, close=close, previousClose=previous, change=change,
                         changePercent=change / previous * 100, sma20=100, sma50=100))
    return dict(index="Nasdaq-100", generatedAt="2026-11-13T21:30:00Z", asOf="2026-11-13T21:00:00Z",
                date="2026-11-13", previousDate="2026-11-12", membersAsOf="2026-10-01", constituents=3,
                priced=3, compared=3, missing=0, uncompared=0, advancing=1, unchanged=1, declining=1,
                sma20=dict(eligible=3, above=1, percent=33), sma50=dict(eligible=3, above=1, percent=33), stocks=rows)


class NasdaqCLI(unittest.TestCase):
    def run_cli(self, data, arguments=None, sequence=None):
        return cli.TickerCLI().run_cli({"result": {"structuredContent": data}}, arguments or ["nasdaq"], sequence)

    def test_complete_markdown_and_unrounded_json(self):
        data = snapshot()
        for args in (["nasdaq"], ["nasdaq", "--json"]):
            result, requests = self.run_cli(data, args)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual([request["params"] for request in requests], [{"name": "get_nasdaq_breadth", "arguments": {}}])
            if "--json" in args:
                document = json.loads(result.stdout)
                self.assertEqual((document["schemaVersion"], document["command"]), (1, "nasdaq"))
                self.assertEqual(document["data"], data)
            else:
                for text in ("reading date 2026-11-13", "Previous session: 2026-11-12", "Membership as of 2026-10-01",
                             "3/3 priced; 3 compared", "| AAPL | 101.12 | 100.00 | 1.12 | 1.12% |",
                             "| SMA20 | 3 | 1 | 33% |", "latest session may still be open", "not financial or investment advice"):
                    self.assertIn(text, result.stdout)

    def test_partial_and_single_session_data_preserve_nulls(self):
        for single_session in (False, True):
            data = snapshot()
            data["stocks"][0]["previousClose"] = None
            data["stocks"][0]["change"] = data["stocks"][0]["changePercent"] = None
            data["stocks"][2].update(close=None, change=None, changePercent=None, sma20=None, sma50=None)
            data.update(priced=2, compared=1, missing=1, uncompared=1, advancing=0, unchanged=1, declining=0)
            if single_session:
                data["previousDate"] = None
                for stock in data["stocks"]:
                    stock.update(previousClose=None, change=None, changePercent=None)
                data.update(compared=0, uncompared=2, unchanged=0)
            for key in ("sma20", "sma50"):
                data[key] = dict(eligible=2, above=1, percent=None)
            for args in (["nasdaq"], ["nasdaq", "--json"]):
                result, _ = self.run_cli(data, args)
                self.assertEqual(result.returncode, 0, result.stderr)
                if "--json" in args:
                    self.assertEqual(json.loads(result.stdout)["data"], data)
                else:
                    self.assertIn("| SMA20 | 2 | 1 | n/a |", result.stdout)
                    self.assertIn("| AAPL | 101.12 | n/a | n/a | n/a |", result.stdout)

    def test_invalid_payloads_fail_without_output_or_retry(self):
        cases = []
        for key, value in (("index", "S&P 500"), ("date", "2026-02-30"), ("previousDate", "2026-11-13"),
                           ("priced", 2), ("compared", True), ("advancing", 2), ("stocks", [])):
            data = snapshot()
            data[key] = value
            cases.append(data)
        for key, value in (("change", 0), ("changePercent", None), ("close", float("nan")), ("previousClose", 0), ("symbol", "MSFT")):
            data = snapshot()
            data["stocks"][0][key] = value
            cases.append(data)
        for key, value in (("eligible", 2), ("above", 4), ("percent", 34), ("percent", None)):
            data = snapshot()
            data["sma20"][key] = value
            cases.append(data)
        for data in cases:
            with self.subTest(data=data):
                result, requests = self.run_cli(data, ["nasdaq", "--json"])
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertEqual(result.stdout, "")
                self.assertEqual(len(requests), 1)
                self.assertNotIn("Traceback", result.stderr)

    def test_unsupported_tool_fails_without_substitution(self):
        result, requests = self.run_cli({}, ["nasdaq", "--json"], sequence=[{"error": {"message": "Unknown tool get_nasdaq_breadth"}}])
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(len(requests), 1)
        self.assertIn("Unknown tool", result.stderr)

    def test_temporary_error_uses_one_shared_three_attempt_budget(self):
        temporary = {"result": {"isError": True, "content": [{"text": "Nasdaq-100 breadth is temporarily unavailable. Please try again later."}]}}
        for final, status in (({"result": {"structuredContent": snapshot()}}, 0), (temporary, 1)):
            result, requests = self.run_cli({}, ["nasdaq", "--json"], sequence=[(503, {}), temporary, final])
            self.assertEqual(result.returncode, status, result.stderr)
            self.assertEqual(len(requests), 3)
            self.assertEqual(result.stderr.count("retrying"), 2)
            if status:
                self.assertEqual(result.stdout, "")
            else:
                self.assertEqual(json.loads(result.stdout)["data"], snapshot())

    def test_parameters_rejected_before_network(self):
        for args in (["nasdaq", "--days", "5"], ["nasdaq", "AAPL"]):
            result, requests = self.run_cli({}, args)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(requests, [])
