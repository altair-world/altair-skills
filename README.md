# Altair skills

Agent skills from [Altair AI](https://altairworld.com): `altair-research` for stock and ETF research, and `altair-market` for market breadth and factor indicators. They read Altair's free public MCP server, so installed skills return the newest available readings and research without updates.

Docs site: [altair-world.github.io/altair-skills](https://altair-world.github.io/altair-skills/), built by GitHub Pages from this README on `main`.

Both skills are for dated published research and market readings. They have no brokerage access or live prices and do not provide personal buy/sell advice or position sizing. For those requests, they explain the limitation without fetching research or web-searching a substitute, and offer dated research only if requested.

## altair-research

The latest AI research on about 70 US stocks and ETFs: the **SPY** (S&P 500), **QQQ** (Nasdaq-100), **SOXX** (semiconductors) and **XBI** (biotech) index ETFs, refreshed weekly, and stocks such as NVDA, AAPL, MSFT, TSLA, AVGO and META.

Claude, GPT and Gemini models each run the same multi-agent [TradingAgents](https://github.com/BichengWang/TradingAgents) pipeline on every ticker: technical, sentiment, news and fundamentals analysts, a bull/bear debate, a trader, a risk team and a portfolio manager. Reports are published at [altairworld.com/TradingAgents](https://altairworld.com/TradingAgents/). The skill pulls every model's final decision for the newest analysis date and shows where the models disagree:

```text
## SOXX · analysis date 2026-10-21 · 4 models: 2 Hold, 2 Underweight

| Model            | Rating      | Close at report | Target | Target vs close | Confidence | Horizon    |
| claude-fable-5-1 | Hold        | 510.36          | 522.51 | +2.4%           | Low        | 1-2 months |
| gpt-6-astra      | Underweight | 512.64          | 493.39 | -3.8%           | Medium     | 4-8 weeks  |
| gemini-4-argon   | Underweight | 510.36          | 470.12 | -7.9%           | High       | 1-3 months |
| claude-opus-5-5  | Hold        | 512.64          | 535.33 | +4.4%           | Medium     | 1-2 months |
```

Then ask your agent things like "What do the AI models think of Nvidia?", "Compare the research on AMD and AVGO", "What's the semiconductor ETF outlook this week?" or "Why is GPT underweight XBI?"

### Install

Any agent that supports skills (Claude Code, Codex, Cursor, Gemini CLI and others), using the [skills CLI](https://github.com/vercel-labs/skills):

```bash
npx skills add altair-world/altair-skills --skill altair-research
```

Claude Code plugin:

```bash
claude plugin marketplace add altair-world/altair-skills
claude plugin install altair@altair-skills
```

The Claude Code plugin ships both skills and also adds the free `altair` MCP server (no key needed).

GitHub CLI: `gh skill install altair-world/altair-skills altair-research`. OpenClaw, from [ClawHub](https://clawhub.ai): `clawhub install altair-research`. Or copy `skills/altair-research` into your agent's skills folder.

Needs Python 3.8+ and internet access. No API key or sign-in.

### Run it yourself

```bash
python3 skills/altair-research/scripts/altair_research.py tickers
python3 skills/altair-research/scripts/altair_research.py latest
python3 skills/altair-research/scripts/altair_research.py latest NVDA AMD --date 2026-10-14
python3 skills/altair-research/scripts/altair_research.py report <report-url> --section research
```

Ticker arguments accept spaces or commas, any case, and optional `$` prefixes; duplicates are removed. Omit ticker arguments to cover the four index ETFs; an explicitly empty list is an input error. Dates must use `YYYY-MM-DD`. `--summary-chars 0` hides summaries; negative lengths are rejected. Uncovered tickers point to `tickers`, and invalid report URLs point to `latest TICKER`; malformed server responses exit 1 with an error message.

The script calls the MCP tools `get_research_decisions`, `list_research_reports` and `read_research_report` at `https://altairworld.com/mcp/free`, the endpoint with only Altair's free tools, over plain HTTPS; set `ALTAIR_MCP_URL` to point it at another deployment. The plugin's MCP server uses the same endpoint. To use those tools directly in an MCP client instead: `claude mcp add --transport http altair https://altairworld.com/mcp/free`. See [altairworld.com/mcp](https://altairworld.com/mcp) for the other free tools; `altair-market` below wraps the market breadth and indicator tools.

### Data and security

Research comes from Altair AI, the publisher of this skill, through its read-only public endpoint at `https://altairworld.com/mcp/free`. No API key is needed. Fetched text is treated as data to quote or summarize, never as instructions. Custom endpoints set through `ALTAIR_MCP_URL` must use HTTPS; HTTP is allowed only for `localhost` or `127.0.0.1` during local development.

## altair-market

Market breadth for the **S&P 500**, **Nasdaq-100** and **PHLX Semiconductor (SOX)**: the percentage of eligible constituents above their 20-day simple moving average, an S&P 500 sector table, and up to 252 recent trading sessions of breadth history. It also returns ten factor indicators and daily/weekly **TD Sequential 9** for **SPX**, **NDX** and **SOX**, with each reading's value, bullish/neutral/bearish label, rule and source.

Excerpt from a live `breadth` run:

```text
# Altair market breadth · reading date 2026-10-23

| Index | Above SMA20 | Price-index close |
| --- | --- | --- |
| SPX (S&P 500) | 70% | 7,623.68 |
| NDX (Nasdaq-100) | 48% | 28,957.53 |
| SOX (PHLX Semiconductor) | 7% | 10,779.46 |

## S&P 500 sector breadth

| Sector | Constituents | Above SMA20 |
| --- | --- | --- |
| Communication Services | 22 | 41% |
```

The percentages are breadth, not stock counts. Values are from the last available close, not live quotes; during trading hours indicator readings can include the current session, whose close may not be final. SPX, NDX and SOX are price-only indices without dividends. Breadth history uses the loader's constituent lists, not point-in-time membership. Indicator labels are rule readings, several contrarian, rather than forecasts or buy/sell instructions; SOX implied volatility uses Cboe's semiconductor ETF index VXSMH.

Ask your agent "How broad is the rally?", "What's semiconductor breadth?", "Which S&P 500 sectors have the strongest breadth?", "Is the market overbought or oversold?" or "Show TD Sequential 9 on SPX, NDX and SOX."

### Install

Any agent that supports skills, using the [skills CLI](https://github.com/vercel-labs/skills):

```bash
npx skills add altair-world/altair-skills --skill altair-market
```

GitHub CLI:

```bash
gh skill install altair-world/altair-skills altair-market
```

OpenClaw, from [ClawHub](https://clawhub.ai):

```bash
clawhub install altair-market
```

The Claude Code plugin installation above ships both skills. Or copy `skills/altair-market` into your agent's skills folder. Needs Python 3.8+ and internet access; no API key or sign-in.

### Run it yourself

```bash
python3 skills/altair-market/scripts/altair_market.py breadth
python3 skills/altair-market/scripts/altair_market.py breadth --days 5
python3 skills/altair-market/scripts/altair_market.py indicators
python3 skills/altair-market/scripts/altair_market.py indicators NDX SOX
```

`breadth` shows the latest index and sector readings; `--days N` also shows 1–252 recent trading sessions. `indicators` defaults to all three indices, accepts either case and removes duplicates. Indicators have no date or history parameter. Missing readings are shown as unavailable. Server or tool failures exit 1; invalid arguments or an insecure remote endpoint exit 2.

### Data and security

Market data comes from Altair AI, the publisher of this skill, through the read-only `get_market_breadth` and `get_market_indicators` tools at `https://altairworld.com/mcp/free`. The script sends only a recent-session count, with index selection applied locally; it sends no files or credentials. Fetched text is data to quote or summarize, never instructions. Set `ALTAIR_MCP_URL` to use another deployment; HTTPS is required, with HTTP allowed only for `localhost` or `127.0.0.1` during local development. See [altairworld.com/mcp](https://altairworld.com/mcp) for the tool documentation.

## Listings

| Market | altair-research | altair-market |
| --- | --- | --- |
| skills.sh | [listing](https://www.skills.sh/altair-world/altair-skills/altair-research) | [listing](https://www.skills.sh/altair-world/altair-skills/altair-market) |
| ClawHub | [listing](https://clawhub.ai/altair-world/skills/altair-research) | [listing](https://clawhub.ai/altair-world/skills/altair-market) |
| LobeHub | [listing](https://lobehub.com/skills/altair-world-altair-skills-altair-research) | [listing](https://lobehub.com/skills/altair-world-altair-skills-altair-market) |
| GitHub (`gh skill`) | [v1.1.1 release](https://github.com/altair-world/altair-skills/releases/tag/v1.1.1) | same release |

The plugin is also submitted to the Claude directory and the OpenAI plugin directory (ChatGPT and Codex). Both are reviewing version 1.0.0, which has only altair-research; 1.1.1, which adds altair-market, follows once they approve it. SkillsMP indexes public GitHub repos on its own schedule and hasn't listed this one yet.

## Disclaimer

Research reports are AI-generated, and market readings are computed from public market data. Both are for information and AI testing only. They are not financial or investment advice, may contain errors, and must not be used to make investment or trading decisions.

## Contributing

Changes reach `main` only through pull requests that pass the `check` workflow: manifest and `SKILL.md` frontmatter checks, then both scripts against the live MCP server on Python 3.8 and 3.13. Add the `auto-merge` label to a pull request and it squash-merges once `check` passes. If a server change is not deployed yet, `check` fails; re-run it after the deploy.

The [main ruleset](https://github.com/altair-world/altair-skills/blob/main/.github/main-ruleset.json) enforces this. To recreate it: `gh api --method POST repos/altair-world/altair-skills/rulesets --input .github/main-ruleset.json`.

## License

[MIT](https://github.com/altair-world/altair-skills/blob/main/LICENSE)
