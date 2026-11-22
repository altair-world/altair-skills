"""Exercise `report --section` across real HTTP and process boundaries."""
import json
import os
import pathlib
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "skills/altair-research/scripts/altair_research.py"
URL = "https://altairworld.com/TradingAgents/NVDA/run/complete_report/"
ROLES = {
    "I. Analyst Team Reports": ["Market Analyst", "Sentiment Analyst", "News Analyst", "Fundamentals Analyst"],
    "II. Research Team Decision": ["Bull Researcher", "Bear Researcher", "Research Manager"],
    "III. Trading Team Plan": ["Trader"],
    "IV. Risk Management Team Decision": ["Aggressive Analyst", "Conservative Analyst", "Neutral Analyst"],
    "V. Portfolio Manager Decision": ["Portfolio Manager"],
}
# Headings that roles write inside their own text, shaped like the report's own. None is a boundary.
STRAY = [
    "#### Own heading",
    "## I. Executive summary",
    "## V. Bullish catalysts",
    "#### V. Portfolio Manager Decision",
    "#### Market Analyst",
    "### Market Analyst view",
    "### Trader:",
]


def report_markdown(roles=ROLES):
    lines = ["# Trading Analysis Report: NVDA", "", "- Analysis date: 2026-11-17", ""]
    for part, names in roles.items():
        lines.extend(["## " + part, ""])
        for name in names:
            lines.extend(["### " + name, "", "{} body.".format(name), ""] + STRAY + [""])
    return "\n".join(lines)


class ResearchReport(unittest.TestCase):
    def run_cli(self, *extra, markdown=None):
        requests = []
        document = report_markdown() if markdown is None else markdown

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                requests.append(request["params"])
                payload = {"ticker": "NVDA", "date": "2026-11-17", "model": "GPT", "url": URL, "markdown": document}
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
            result = subprocess.run([sys.executable, str(SCRIPT), "report", URL] + list(extra),
                                    env=env, capture_output=True, text=True, timeout=10)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        return result, requests

    def bodies(self, output):
        return [line[:-len(" body.")] for line in output.splitlines() if line.endswith(" body.")]

    def test_default_is_the_portfolio_manager_decision_with_source_and_disclaimer(self):
        result, requests = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(requests, [{"name": "read_research_report", "arguments": {"url": URL}}])
        self.assertTrue(result.stdout.startswith("# NVDA · 2026-11-17 · GPT\n{}\n\n## V. Portfolio Manager Decision\n".format(URL)))
        self.assertEqual(self.bodies(result.stdout), ["Portfolio Manager"])
        self.assertIn("\nDisclaimer: ", result.stdout)

    def test_each_part_holds_exactly_its_own_roles(self):
        parts = {"analysts": "I. Analyst Team Reports", "research": "II. Research Team Decision",
                 "trader": "III. Trading Team Plan", "risk": "IV. Risk Management Team Decision",
                 "pm": "V. Portfolio Manager Decision"}
        for name, title in parts.items():
            with self.subTest(section=name):
                result, _ = self.run_cli("--section", name)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.bodies(result.stdout), ROLES[title])
                self.assertEqual(result.stdout.count("\n## " + title + "\n"), 1)
                self.assertEqual(result.stdout.count("\n".join(STRAY)), len(ROLES[title]))

    def test_each_role_is_one_block_including_its_own_headings(self):
        roles = {"market": "Market Analyst", "sentiment": "Sentiment Analyst", "news": "News Analyst",
                 "fundamentals": "Fundamentals Analyst", "bull": "Bull Researcher", "bear": "Bear Researcher",
                 "manager": "Research Manager", "aggressive": "Aggressive Analyst",
                 "conservative": "Conservative Analyst", "neutral": "Neutral Analyst"}
        for name, title in roles.items():
            with self.subTest(section=name):
                result, _ = self.run_cli("--section", name)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.bodies(result.stdout), [title])
                self.assertIn("\n\n### {}\n".format(title), result.stdout)
                self.assertEqual(result.stdout.count("\n".join(STRAY)), 1)
                for part in ROLES:
                    self.assertNotIn("\n## {}\n".format(part), result.stdout)

    def test_several_sections_print_in_the_requested_order_from_one_request(self):
        # The same pair in both orders, so neither report order nor a fixed name order can pass.
        for value, expected in (("MANAGER, pm,manager", ["Research Manager", "Portfolio Manager"]),
                                ("PM, manager,pm", ["Portfolio Manager", "Research Manager"])):
            with self.subTest(section=value):
                result, requests = self.run_cli("--section", value)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(len(requests), 1)
                self.assertEqual(self.bodies(result.stdout), expected)

    def test_full_returns_the_whole_report_once(self):
        result, _ = self.run_cli("--section", "pm,full")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.bodies(result.stdout), [name for names in ROLES.values() for name in names])
        self.assertIn("# Trading Analysis Report: NVDA", result.stdout)

    def test_a_missing_part_is_named_and_never_replaced_by_another(self):
        markdown = report_markdown({part: names for part, names in ROLES.items() if not part.startswith("II.")})
        result, _ = self.run_cli("--section", "manager,research,pm", markdown=markdown)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Section `manager` not found in this report.", result.stdout)
        self.assertIn("Section `research` not found in this report.", result.stdout)
        self.assertEqual(self.bodies(result.stdout), ["Portfolio Manager"])

    def test_a_missing_role_is_named_and_never_replaced_by_its_part(self):
        markdown = report_markdown(dict(ROLES, **{"II. Research Team Decision": ["Research Manager"]}))
        result, _ = self.run_cli("--section", "bull,bear,manager", markdown=markdown)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Section `bull` not found in this report.", result.stdout)
        self.assertIn("Section `bear` not found in this report.", result.stdout)
        self.assertEqual(self.bodies(result.stdout), ["Research Manager"])

    def test_a_role_ends_at_the_next_role_even_without_its_part_title(self):
        markdown = report_markdown().replace("\n## III. Trading Team Plan\n", "\n")
        result, _ = self.run_cli("--section", "manager", markdown=markdown)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.bodies(result.stdout), ["Research Manager"])

    def test_unknown_empty_or_space_separated_names_are_rejected_before_any_request(self):
        for value in ("valuation", "pm,valuation", ",", "", "research manager", "trader;pm"):
            with self.subTest(section=value):
                result, requests = self.run_cli("--section", value)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertIn("comma-separated", result.stderr)
                self.assertEqual(requests, [])


if __name__ == "__main__":
    unittest.main()
