import importlib.util
import pathlib
import unittest
from unittest import mock


SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "skills/altair-research/scripts/altair_research.py"
spec = importlib.util.spec_from_file_location("altair_research", SCRIPT)
research = importlib.util.module_from_spec(spec)
spec.loader.exec_module(research)


class InvalidServerResponseTests(unittest.TestCase):
    def test_commands_report_malformed_responses_without_tracebacks(self):
        payloads = [
            b"not JSON",
            b'{}',
            b'{"result": {"content": []}}',
            b'{"result": {"content": [{"text": null}]}}',
        ]
        commands = [["tickers"], ["latest", "SPY"], ["report", "https://altairworld.com/report"]]
        for command in commands:
            for payload in payloads:
                with self.subTest(command=command, payload=payload):
                    response = mock.MagicMock()
                    response.__enter__.return_value = response
                    response.read.return_value = payload
                    response.headers = {"Content-Type": "application/json"}
                    with mock.patch.object(research.urllib.request, "urlopen", return_value=response), \
                            mock.patch("sys.argv", [str(SCRIPT)] + command), \
                            self.assertRaisesRegex(SystemExit, "altair_research: invalid server response:"):
                        research.main()


if __name__ == "__main__":
    unittest.main()
