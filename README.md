# Altair skills

Agent skills from [Altair AI](https://altairworld.com). They read live data from Altair's free public MCP server, so an installed skill always returns the newest research without updates.

Docs site: [altair-world.github.io/altair-skills](https://altair-world.github.io/altair-skills/), built by GitHub Pages from this README on `main`.

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

The plugin also adds the free `altair` MCP server (no key needed).

GitHub CLI: `gh skill install altair-world/altair-skills altair-research`. OpenClaw, from [ClawHub](https://clawhub.ai): `clawhub install altair-research`. Or copy `skills/altair-research` into your agent's skills folder.

Needs Python 3.8+ and internet access. No API key or sign-in.

### Listings

- [skills.sh](https://www.skills.sh/altair-world/altair-skills/altair-research)
- [ClawHub](https://clawhub.ai/altair-world/skills/altair-research)
- Claude directory: submitted, in review.
- OpenAI plugin directory (ChatGPT and Codex): submitted, in review.

### Run it yourself

```bash
python3 skills/altair-research/scripts/altair_research.py tickers
python3 skills/altair-research/scripts/altair_research.py latest
python3 skills/altair-research/scripts/altair_research.py latest NVDA AMD --date 2026-10-14
python3 skills/altair-research/scripts/altair_research.py report <report-url> --section research
```

Ticker arguments accept spaces or commas, any case, and optional `$` prefixes; duplicates are removed. Omit ticker arguments to cover the four index ETFs; an explicitly empty list is an input error. Dates must use `YYYY-MM-DD`. `--summary-chars 0` hides summaries; negative lengths are rejected. Uncovered tickers point to `tickers`, and invalid report URLs point to `latest TICKER`.

The script calls the MCP tools `get_research_decisions`, `list_research_reports` and `read_research_report` at `https://altairworld.com/mcp/free`, the endpoint with only Altair's free tools, over plain HTTPS; set `ALTAIR_MCP_URL` to point it at another deployment. The plugin's MCP server uses the same endpoint. To use those tools directly in an MCP client instead: `claude mcp add --transport http altair https://altairworld.com/mcp/free`. See [altairworld.com/mcp](https://altairworld.com/mcp) for the other free tools, such as market breadth.

## Disclaimer

The reports are AI-generated for AI testing and experimentation only. They are not financial or investment advice, may contain errors, and must not be used to make investment or trading decisions.

## Contributing

Changes reach `main` only through pull requests that pass the `check` workflow: manifest and `SKILL.md` frontmatter checks, then the script against the live MCP server on Python 3.8 and 3.13. Add the `auto-merge` label to a pull request and it squash-merges once `check` passes. If a server change is not deployed yet, `check` fails; re-run it after the deploy.

The [main ruleset](https://github.com/altair-world/altair-skills/blob/main/.github/main-ruleset.json) enforces this. To recreate it: `gh api --method POST repos/altair-world/altair-skills/rulesets --input .github/main-ruleset.json`.

## License

[MIT](https://github.com/altair-world/altair-skills/blob/main/LICENSE)
