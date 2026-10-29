#!/usr/bin/env python3
"""Fetch the newest Altair TradingAgents research through the public MCP server.

Standard library only (Python 3.8+). No API key, no MCP client setup.

  python3 altair_research.py tickers                   # covered tickers and report counts
  python3 altair_research.py latest                    # SPY QQQ SOXX XBI, newest analysis date
  python3 altair_research.py latest NVDA AAPL          # any covered ticker
  python3 altair_research.py latest SPY --date 2026-10-14
  python3 altair_research.py report <url> [--section pm|analysts|research|trader|risk|full]

Set ALTAIR_MCP_URL to an HTTPS deployment; HTTP is allowed only for localhost/127.0.0.1.
"""

import argparse
import concurrent.futures
import datetime
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ENDPOINT = os.environ.get("ALTAIR_MCP_URL", "https://altairworld.com/mcp/free")
INDEX_TICKERS = ["SPY", "QQQ", "SOXX", "XBI"]
WORKERS = 4
ATTEMPTS = 3
STALE_DAYS = 10
SUMMARY_CHARS = 600
DISCLAIMER = ("AI-generated reports for AI testing and experimentation only. They are not financial or "
              "investment advice and may contain errors; do not use them to make investment or trading decisions.")
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    # The endpoint sits behind Cloudflare, which rejects the default Python-urllib agent.
    "User-Agent": "altair-research-skill/1.2",
}
SECTIONS = {
    "analysts": "## I. ",
    "research": "## II. ",
    "trader": "## III. ",
    "risk": "## IV. ",
    "pm": "## V. ",
}


class ToolError(Exception):
    pass


class Transient(Exception):
    pass


def post(body):
    request = urllib.request.Request(ENDPOINT, data=body, headers=HEADERS, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            text = response.read().decode("utf-8")
            streamed = "text/event-stream" in response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as error:
        if error.code in (429, 500, 502, 503, 504):
            raise Transient("HTTP {}".format(error.code))
        raise ToolError("{} returned HTTP {}".format(ENDPOINT, error.code))
    except (urllib.error.URLError, OSError) as error:
        raise Transient(str(getattr(error, "reason", error)))
    if streamed:
        events = [line[5:].strip() for line in text.splitlines() if line.startswith("data:")]
        if not events:
            raise Transient("empty event stream")
        text = events[-1]
    return json.loads(text)


def call_tool(name, arguments):
    body = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments}}
    ).encode()
    # The server is a Cloudflare Worker that sometimes drops a request under load; reads are idempotent.
    for attempt in range(ATTEMPTS):
        try:
            message = post(body)
            break
        except Transient as error:
            if attempt == ATTEMPTS - 1:
                raise ToolError("{} failed after {} attempts: {}".format(name, ATTEMPTS, error))
            time.sleep(2 ** attempt)
    if "error" in message:
        raise ToolError("{}: {}".format(name, message["error"].get("message", message["error"])))
    result = message["result"]
    if not isinstance(result, dict):
        raise ValueError("expected MCP tool result object")
    if result.get("isError"):
        detail = " ".join(part.get("text", "") for part in result.get("content", []))
        detail = detail.replace("Use list_research_reports to see covered tickers.",
                                "Run `tickers` to see covered tickers.")
        detail = detail.replace("Use a url returned by list_research_reports.",
                                "Use a report URL from `latest TICKER`.")
        raise ToolError(detail.strip() or "{}: tool error".format(name))
    if result.get("structuredContent") is not None:
        return result["structuredContent"]
    return json.loads(result["content"][0]["text"])


def section(markdown, name):
    if name == "full":
        return markdown
    start = markdown.find(SECTIONS[name])
    if start < 0:
        return ""
    following = [markdown.find(h, start + 1) for h in SECTIONS.values()]
    end = min([i for i in following if i > start] or [len(markdown)])
    return markdown[start:end].strip()


def first_number(value):
    match = re.search(r"\d[\d,]*(?:\.\d+)?", value or "")
    return float(match.group(0).replace(",", "")) if match else None


def short(value, limit):
    value = (value or "").strip()
    if len(value) <= limit:
        return value
    cut = value[:limit]
    stop = cut.rfind(". ")
    return cut[: stop + 1] if stop > limit // 2 else cut.rstrip() + "…"


def money(value):
    return "n/a" if value is None else "{:,.2f}".format(value)


def lead(value, pattern):
    """The leading phrase of a field such as "Medium. The Hold has broad support…"."""
    return re.split(pattern, value or "")[0].strip() or "not stated"


def render_ticker(ticker, research, summary_chars):
    if isinstance(research, ToolError):
        return "## {}\n\n{}\n".format(ticker, research)
    rows = []
    for decision in research["decisions"]:
        if "error" in decision:
            rows.append(dict(decision, rating="unavailable"))
            continue
        close, target = first_number(decision["currentPrice"]), first_number(decision["priceTarget"])
        rows.append(dict(decision, rating=decision["rating"] or "not stated", close=close, target=target,
                         upside=(target / close - 1) if close and target else None))
    read = [row for row in rows if "error" not in row]
    counts = {}
    for row in read:
        counts[row["rating"]] = counts.get(row["rating"], 0) + 1
    split = ", ".join("{} {}".format(n, rating) for rating, n in sorted(counts.items(), key=lambda kv: -kv[1]))
    lines = [
        "## {} · analysis date {} · {} models: {}".format(
            research["ticker"], research["date"], len(read), split or "none readable"),
        "",
        "| Model | Rating | Close at report | Target | Target vs close | Confidence | Horizon |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in read:
        upside = "n/a" if row["upside"] is None else "{:+.1%}".format(row["upside"])
        lines.append("| [{}]({}) | {} | {} | {} | {} | {} | {} |".format(
            row["model"], row["url"], row["rating"], money(row["close"]), money(row["target"]), upside,
            lead(row["confidence"], r"[.;,(]"), short(lead(row["timeHorizon"], r"\. "), 60)))
    for row in rows:
        if "error" in row:
            lines.append("| [{}]({}) | unavailable: {} | | | | | |".format(row["model"], row["url"], row["error"]))
    lines.append("")
    if summary_chars:
        for row in read:
            lines.append("- **{}**: {}".format(row["model"], short(row["summary"], summary_chars) or "no summary"))
    return "\n".join(lines) + "\n"


def normalize(raw):
    tickers = []
    for item in raw:
        for part in re.split(r"[,\s]+", item):
            ticker = part.strip().lstrip("$").upper()
            if ticker and ticker not in tickers:
                tickers.append(ticker)
    return tickers


def decisions_for(ticker, date, include_previous=False):
    arguments = {"ticker": ticker}
    if date:
        arguments["date"] = date
    if include_previous:
        arguments["includePrevious"] = True
    try:
        return call_tool("get_research_decisions", arguments)
    except ToolError as error:
        return error


def json_research(args):
    """Emit one versioned document; retain source fields rather than deriving prices."""
    tickers = normalize(args.tickers) or INDEX_TICKERS
    include_previous = args.command == "changes"
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        researched = list(pool.map(lambda ticker: decisions_for(ticker, args.date, include_previous), tickers))
    results, errors = [], []
    for ticker, research in zip(tickers, researched):
        if isinstance(research, ToolError):
            errors.append({"ticker": ticker, "message": str(research)})
            continue
        if not isinstance(research, dict) or not isinstance(research.get("decisions"), list):
            raise ValueError("expected research decisions")
        if args.command == "changes" and not isinstance(research.get("comparisons"), list):
            errors.append({"ticker": ticker, "message": "Server does not support research comparisons; missing is not unchanged."})
            continue
        if research.get("ticker") != ticker:
            raise ValueError("research ticker does not match request")
        try:
            analysis_date(research["date"])
        except argparse.ArgumentTypeError as error:
            raise ValueError(str(error))
        if args.date and research["date"] != args.date:
            raise ValueError("research date does not match request")
        results.append(research)
    print(json.dumps({
        "schemaVersion": 1, "command": args.command,
        "fetchedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source": ENDPOINT, "requestedDate": args.date,
        "results": results, "errors": errors, "disclaimer": DISCLAIMER,
    }, ensure_ascii=False, allow_nan=False))
    if not results:
        sys.exit(1)


def changes(args):
    if args.json:
        return json_research(args)
    tickers = normalize(args.tickers) or INDEX_TICKERS
    failed = 0
    print("# Altair research rating changes\n")
    print("Same ticker and exact model name; nearest strictly earlier analysis date. "
          "Latest rerun per date. Only models on the selected/newest ticker date are included. "
          "Unchanged means the rating only, not the report or its other fields.\n")
    for ticker in tickers:
        research = decisions_for(ticker, args.date, include_previous=True)
        if isinstance(research, ToolError):
            failed += 1
            print("## {}\n\n{}\n".format(ticker, research))
            continue
        if "comparisons" not in research:
            failed += 1
            print("## {}\n\nThis server does not support research comparisons yet. "
                  "Use `latest` for decisions; do not interpret missing comparisons as unchanged.\n".format(ticker))
            continue
        print("## {} · analysis date {}\n".format(research["ticker"], research["date"]))
        for item in research["comparisons"]:
            print("### {} · {}\n".format(item["model"], item["status"].replace("_", " ")))
            for label, value in (("Previous", item["previous"]), ("Current", item["current"])):
                if value is None:
                    print("- Previous: no earlier published report for this exact model name.")
                else:
                    rating = "unavailable" if value.get("error") else value.get("rating") or "rating not stated"
                    print("- {}: {} · {} · {}".format(label, value["date"], rating, value["url"]))
            print("")
    print("No reason for a rating change is inferred. Read both reports for context.\n")
    print("Disclaimer: " + DISCLAIMER)
    if failed == len(tickers):
        sys.exit(1)


def latest(args):
    if args.json:
        return json_research(args)
    tickers = normalize(args.tickers) or INDEX_TICKERS
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        researched = list(pool.map(lambda ticker: decisions_for(ticker, args.date), tickers))

    today = datetime.date.today()
    out = [
        "# Altair TradingAgents research (fetched {})".format(today.isoformat()),
        "",
        "Source: https://altairworld.com/TradingAgents/ through the public MCP server {}. "
        "Each model runs the same multi-agent pipeline (analysts, bull/bear debate, trader, risk team, "
        "portfolio manager); rows are the portfolio manager's final decision. "
        "\"Close at report\" is the report-time close, not a live quote.".format(ENDPOINT),
        "",
    ]
    for ticker, research in zip(tickers, researched):
        out.append(render_ticker(ticker, research, args.summary_chars))
        if isinstance(research, dict) and (today - datetime.date.fromisoformat(research["date"])).days > STALE_DAYS:
            out.append("> {} research is from {}, more than {} days old.\n".format(ticker, research["date"], STALE_DAYS))
    out.append("Disclaimer: " + DISCLAIMER)
    print("\n".join(out))
    if all(isinstance(research, ToolError) for research in researched):
        sys.exit(1)


def tickers(args):
    # A ticker filter that matches nothing still returns counts for every covered ticker.
    covered = call_tool("list_research_reports", {"ticker": "-", "limit": 1}).get("tickers", [])
    index = [t for t in covered if t["ticker"] in INDEX_TICKERS]
    others = [t for t in covered if t["ticker"] not in INDEX_TICKERS]
    print("# Tickers with Altair research ({} covered)\n".format(len(covered)))
    print("Report counts are all runs across models and dates. Index ETFs are refreshed about weekly; "
          "other tickers less regularly, so check the analysis date `latest` prints.\n")
    for title, group in (("Index ETFs", index), ("Stocks and other funds", others)):
        print("{}: {}\n".format(title, ", ".join("{} ({})".format(t["ticker"], t["reports"]) for t in group)))


def report(args):
    data = call_tool("read_research_report", {"url": args.url})
    print("# {} · {} · {}\n{}\n".format(data["ticker"], data["date"], data["model"], data["url"]))
    print(section(data["markdown"], args.section) or "Section not found in this report.")
    print("\nDisclaimer: " + DISCLAIMER)


def analysis_date(value):
    try:
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            raise ValueError
        return datetime.date.fromisoformat(value).isoformat()
    except ValueError:
        raise argparse.ArgumentTypeError("expected a YYYY-MM-DD date, got {!r}".format(value))


def summary_length(value):
    try:
        length = int(value)
        if length >= 0:
            return length
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("expected a non-negative integer, got {!r}".format(value))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    tickers_parser = commands.add_parser("tickers", help="covered tickers with report counts")
    tickers_parser.set_defaults(run=tickers)
    latest_parser = commands.add_parser("latest", help="final decisions from every model on the newest analysis date")
    latest_parser.add_argument("tickers", nargs="*",
                               help="tickers, space- or comma-separated (default: {})".format(" ".join(INDEX_TICKERS)))
    latest_parser.add_argument("--date", type=analysis_date, help="analysis date YYYY-MM-DD instead of the newest")
    latest_parser.add_argument("--json", action="store_true", help="versioned JSON with unmodified source fields; no summary truncation")
    latest_parser.add_argument("--summary-chars", type=summary_length, default=SUMMARY_CHARS,
                               help="executive summary length per model; 0 hides summaries (default %(default)s)")
    latest_parser.set_defaults(run=latest)
    changes_parser = commands.add_parser("changes", help="same-model rating changes versus the nearest earlier analysis date")
    changes_parser.add_argument("tickers", nargs="*", help="tickers (default: SPY QQQ SOXX XBI)")
    changes_parser.add_argument("--date", type=analysis_date, help="analysis date YYYY-MM-DD instead of the newest")
    changes_parser.add_argument("--json", action="store_true", help="versioned JSON with decisions, comparisons and explicit errors")
    changes_parser.set_defaults(run=changes)
    report_parser = commands.add_parser("report", help="one section of a report url from `latest`")
    report_parser.add_argument("url")
    report_parser.add_argument("--section", choices=list(SECTIONS) + ["full"], default="pm")
    report_parser.set_defaults(run=report)
    args = parser.parse_args()
    if args.command in ("latest", "changes") and args.tickers and not normalize(args.tickers):
        parser.error("provide at least one ticker, or omit tickers for the index ETFs")
    try:
        endpoint = urllib.parse.urlsplit(ENDPOINT)
        valid_endpoint = bool(endpoint.hostname) and (
            endpoint.scheme == "https" or
            (endpoint.scheme == "http" and endpoint.hostname in ("localhost", "127.0.0.1"))
        )
    except ValueError:
        valid_endpoint = False
    if not valid_endpoint:
        print("altair_research: ALTAIR_MCP_URL must use HTTPS (HTTP only for localhost/127.0.0.1)",
              file=sys.stderr)
        sys.exit(2)
    try:
        args.run(args)
    except ToolError as error:
        sys.exit("altair_research: {}".format(error))
    except (ValueError, KeyError, IndexError, TypeError) as error:
        sys.exit("altair_research: invalid server response: {}".format(error))


if __name__ == "__main__":
    main()
