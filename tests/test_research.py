import datetime
import importlib.util
import io
import pathlib
import unittest
from unittest import mock


SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "skills/altair-research/scripts/altair_research.py"
spec = importlib.util.spec_from_file_location("altair_research", SCRIPT)
research = importlib.util.module_from_spec(spec)
spec.loader.exec_module(research)
DECISION = {"model": "model-a", "url": "https://altairworld.com/report", "rating": "Hold", "currentPrice": "100",
            "priceTarget": "110", "confidence": "Medium", "timeHorizon": "3 months", "summary": "Hold."}


class SummaryAndPriceTests(unittest.TestCase):
    def test_a_shortened_summary_always_ends_with_an_ellipsis(self):
        self.assertEqual(research.short("A" * 400 + ". " + "B" * 400, 600), "A" * 400 + ". …")
        self.assertEqual(research.short("C" * 700, 600), "C" * 600 + "…")
        self.assertEqual(research.short("Short. Whole.", 600), "Short. Whole.")
        # A sentence whose period is the last character that fits is kept.
        self.assertEqual(research.short("A" * 400 + ". " + "B" * 197 + ". " + "C" * 50, 600),
                         "A" * 400 + ". " + "B" * 197 + ". …")

    def test_prices_round_half_up_from_the_number_as_written(self):
        for value, text in ((59.555, "59.56"), (59.545, "59.55"), (350.385, "350.39"), (154.425, "154.43"),
                            (1234.5, "1,234.50"), (359.0, "359.00"), (None, "n/a"),
                            (1e26, "100,000,000,000,000,000,000,000,000.00"), (float("inf"), "Infinity")):
            with self.subTest(value=value):
                self.assertEqual(research.money(value), text)


class LatestNoteTests(unittest.TestCase):
    def run_latest(self, research_by_ticker, *argv):
        def fake(ticker, date, include_previous=False):
            return research_by_ticker[ticker]
        with mock.patch.object(research, "decisions_for", side_effect=fake), \
                mock.patch("sys.argv", [str(SCRIPT), "latest"] + list(argv)), \
                mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            research.main()
        return out.getvalue()

    def days_ago(self, days):
        return (datetime.date.today() - datetime.timedelta(days=days)).isoformat()

    def test_one_model_on_the_newest_date_points_to_dates(self):
        day = self.days_ago(2)
        text = self.run_latest({"SPY": {"ticker": "SPY", "date": day, "decisions": [DECISION]}}, "SPY")
        self.assertIn("| Model | Rating | Price at report | Target | Target vs price | Confidence | Horizon |", text)
        self.assertIn("\"Price at report\" is the price each report states: intraday or a close on the analysis date, "
                      "or an earlier session's close; most reports date it in the \"Price As Of\" line that opens "
                      "their `market` section. It is not a live quote.", text)
        self.assertIn("> Only model-a has SPY research for {}; other models' newest reports may be from earlier "
                      "dates. Run `dates SPY`.".format(day), text)
        self.assertNotIn("days old", text)

    def test_summaries_print_whole_up_to_1500_characters_by_default(self):
        whole = "Hold. " + "A" * 990
        text = self.run_latest({"SPY": {"ticker": "SPY", "date": self.days_ago(2),
                                        "decisions": [dict(DECISION, summary=whole)]}}, "SPY")
        self.assertIn("- **model-a**: " + whole + "\n", text)

    def test_an_unreadable_second_model_still_counts_as_a_model(self):
        unreadable = {"model": "model-b", "url": "https://altairworld.com/other", "error": "Unavailable"}
        text = self.run_latest({"SPY": {"ticker": "SPY", "date": self.days_ago(2),
                                        "decisions": [DECISION, unreadable]}}, "SPY")
        self.assertIn("unavailable: Unavailable", text)
        self.assertNotIn("> Only", text)

    def test_research_ten_or_more_days_old_is_flagged(self):
        for days, flagged in ((9, False), (10, True), (31, True)):
            with self.subTest(days=days):
                day = self.days_ago(days)
                text = self.run_latest({"SPY": {"ticker": "SPY", "date": day,
                                                "decisions": [DECISION, dict(DECISION, model="model-b")]}}, "SPY")
                if flagged:
                    self.assertIn("> SPY research is from {}, {} days old.".format(day, days), text)
                else:
                    self.assertNotIn("days old", text)

    def test_a_picked_date_keeps_its_age_but_not_the_one_model_note(self):
        # Agents pick dates too (other models' recent reports), so an old picked date is still marked.
        day = self.days_ago(40)
        text = self.run_latest({"SPY": {"ticker": "SPY", "date": day, "decisions": [DECISION]}}, "SPY", "--date", day)
        self.assertIn("> SPY research is from {}, 40 days old.".format(day), text)
        self.assertNotIn("> Only", text)


class LatestHeaderTests(unittest.TestCase):
    def test_model_count_is_singular_only_for_one_model(self):
        decision = {"model": "one", "url": "https://altairworld.com/report", "rating": "Hold", "currentPrice": "100",
                    "priceTarget": "110", "confidence": "Medium", "timeHorizon": "3 months", "summary": "Hold."}
        for decisions, split in (([decision], "1 model: 1 Hold"), ([decision, dict(decision, model="two")], "2 models: 2 Hold")):
            with self.subTest(split=split):
                text = research.render_ticker("SPY", {"ticker": "SPY", "date": "2026-11-12", "decisions": decisions}, 0)
                self.assertTrue(text.startswith("## SPY · analysis date 2026-11-12 · {}\n".format(split)))


class InvalidServerResponseTests(unittest.TestCase):
    def test_commands_report_malformed_responses_without_tracebacks(self):
        payloads = [
            b"not JSON",
            b'{}',
            b'{"result": {"content": []}}',
            b'{"result": {"content": [{"text": null}]}}',
        ]
        commands = [["tickers"], ["latest", "SPY"], ["changes", "SPY"],
                    ["report", "https://altairworld.com/report"]]
        for command in commands:
            for payload in payloads:
                with self.subTest(command=command, payload=payload):
                    response = mock.MagicMock()
                    response.__enter__.return_value = response
                    response.read.return_value = payload
                    response.headers = {"Content-Type": "application/json"}
                    with mock.patch.object(research.urllib.request, "urlopen", return_value=response), \
                            mock.patch("sys.argv", [str(SCRIPT)] + command), \
                            mock.patch("sys.stdout", io.StringIO()), \
                            self.assertRaisesRegex(SystemExit, "altair_research: invalid server response:"):
                        research.main()


if __name__ == "__main__":
    unittest.main()
