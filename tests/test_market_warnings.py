"""Run the actual CLI over HTTP: withheld readings must keep their explanation."""
import json
import unittest
import test_market_alerts as alerts
import test_market_ticker as ticker

WARNING = "Price readings withheld: suspect split | check source.\nNot a forecast."


class WarningCLI(unittest.TestCase):
    def test_ticker_warning_keeps_nulls_and_healthy_macro(self):
        data = ticker.snapshot()
        data["instrument"]["dataWarning"] = WARNING
        data["indicators"][0]["reading"] = None
        data["indicators"].append(dict(data["indicators"][0], name="Macro context",
                                      reading={"value": .01, "reading": "Available", "signal": "neutral"}))
        for json_output in (False, True):
            result, requests = ticker.TickerCLI().run_cli({"result": {"structuredContent": data}},
                ["ticker", "NVDA"] + (["--json"] if json_output else []))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(requests), 1)
            if json_output:
                self.assertEqual(json.loads(result.stdout)["data"], data)
            else:
                self.assertIn("Data quality warning: Price readings withheld: suspect split \\| check source. Not a forecast.", result.stdout)
                self.assertIn("| Trend | n/a | unavailable | n/a |", result.stdout)
                self.assertIn("| Macro context | 1.00% | Available | neutral |", result.stdout)

    def test_indices_selection_keeps_warning_for_selected_symbol(self):
        data = alerts.market()
        data["indices"][1]["dataWarning"] = WARNING
        data["indicators"][0]["readings"]["NDX"] = None
        for json_output in (False, True):
            result, _ = ticker.TickerCLI().run_cli({"result": {"structuredContent": data}},
                ["indicators", "NDX"] + (["--json"] if json_output else []))
            self.assertEqual(result.returncode, 0, result.stderr)
            if json_output:
                output = json.loads(result.stdout)["data"]
                self.assertEqual(output["indices"], [data["indices"][1]])
                self.assertIsNone(output["indicators"][0]["readings"]["NDX"])
            else:
                self.assertIn("Data quality warning:", result.stdout)
                self.assertNotIn("## SPX", result.stdout)

    def test_alerts_carry_both_index_and_ticker_warnings_without_inventing_changes(self):
        def answer(name, arguments):
            data = alerts.market() if name == "get_market_indicators" else alerts.ticker(arguments["ticker"])
            instrument = data["indices"][0] if "indices" in data else data["instrument"]
            instrument["dataWarning"] = WARNING
            for row in data["indicators"]:
                if "readings" in row:
                    row["readings"]["SPX"] = None
                else:
                    row["reading"] = None
            return {"result": {"structuredContent": data}}
        for json_output in (False, True):
            result, requests = alerts.AlertsCLI().run_cli(["SPX", "NVDA"] + (["--json"] if json_output else []), answer)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(requests), 2)
            if json_output:
                for symbol in json.loads(result.stdout)["data"]["symbols"]:
                    self.assertEqual(symbol["dataWarning"], WARNING)
                    self.assertEqual(symbol["turned"], [])
                    self.assertEqual(symbol["backToNeutral"], [])
                    self.assertGreater(len(symbol["noComparison"]), 0)
            else:
                self.assertEqual(result.stdout.count("Data quality warning ("), 2)
                self.assertIn("not counted as unchanged", result.stdout)
                self.assertIn("not the weekly email", result.stdout)

    def test_malformed_warning_fails_before_any_output(self):
        for warning in (42, {}, " "):
            data = ticker.snapshot()
            data["instrument"]["dataWarning"] = warning
            result, requests = ticker.TickerCLI().run_cli({"result": {"structuredContent": data}}, ["ticker", "NVDA", "--json"])
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertIn("dataWarning", result.stderr)
            self.assertEqual(len(requests), 1)
