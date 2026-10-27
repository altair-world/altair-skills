# Research changes skill: unpublished verification

2026-10-26, branch `codex/research-changes`, base `b14c930`. This records local verification before publication; historical unpublished-state statements below describe that stage. The PR Verification section tracks subsequent checks. No skill release is included.

Adds `changes [TICKER ...] [--date YYYY-MM-DD]`, requesting optional `includePrevious: true` from the existing free `get_research_decisions` tool. It compares exact models across distinct analysis dates, prints both dated report URLs and preserves changed/unchanged/no-previous/unavailable states. It does not calculate comparisons independently, merge model names, infer causal explanations or turn dated research into personal advice. `latest`, `tickers` and `report` remain compatible.

Both plugin manifests target `1.2.0`; publication notes include the new behavior. Existing published-directory listings remain at their actual version. Deploy the aai server first; an old permissive server without comparisons is reported as unsupported, not unchanged.

## Evidence

- `python3 -m unittest discover -s tests -p 'test_*.py'`: 2/2 passed on Python 3.9, exercising actual CLI subprocesses and loopback HTTP. Old-server responses exit 1 and explain unsupported; failed previous report retains both sources and unavailable status. CI is configured for Python 3.8 and 3.13; those interpreter versions are not claimed run locally.
- Skill Creator `quick_validate.py skills/altair-research`: passed in an isolated temporary PyYAML environment. Python remains standard-library-only at runtime.
- Local aai fixture Pages → free MCP → this CLI: passed 2026-10-26T05:25:31.357Z–05:25:31.845Z. Covered changed/unchanged, no previous, failed previous, failed current without previous, missing-rating words and all-unavailable comparisons.
- Read-only real research → local aai Pages → free MCP → this CLI: passed 2026-10-26T05:25:33.628Z–05:25:34.311Z. AAPL current date 2026-10-24: gpt-6-astra Underweight versus Oct21 Underweight (unchanged); claude-opus-5-5 Hold versus Oct21 Overweight (changed). Both report URLs appear in CLI output.
- Required existing live commands passed: `python3 skills/altair-research/scripts/altair_research.py tickers` (69 covered) and `latest SPY NVDA --summary-chars 0` (Oct24, two and one readable models respectively), exit 0.
- `git diff --check`: passed.

Full reproducible shared implementation/evidence: the aai worktree's `docs/verification/research-changes.md`. Raw local artifacts are ignored under `/Users/yuewu/Documents/Codex/aai-research-changes/homepage/test-results/research-changes-{fixture,live}/` (JSON, skill Markdown and screenshots). They are not claimed to be hosted-preview verification.

Both review rounds are complete. The independent reviewer found and rechecked the server-side missing-rating placeholder fix; no actionable blocker remains. The parent independently reran the frozen fixture and read-only live workflows on Node 22.23.4 at 05:29:33.723Z–05:29:34.228Z and 05:29:59.382Z–05:30:00.078Z respectively, with this exact CLI. Both passed, as did the two CLI compatibility checks, official Skill Creator validation and the companion #1 package validator against this worktree. Artifacts: `/private/tmp/aai-parent-research-final-{fixture,live}-node22/`.

Locally ready for PR preparation/publication when authorized, with no commit or remote mutation performed. Hosted verification remains pending; deploy and verify the server before merging/releasing this dependent skill. Rebase against any earlier package-validation changes rather than dropping either set of CI checks.

## Third review

The parent completed the extra review directly after the new subagent passes were credit-blocked. The companion script required no further behavior change. Its two loopback CLI compatibility cases passed again, and the hardened #1 package validator accepted this worktree's `1.2.0` metadata and resources.

The exact CLI passed through the guarded, combined local aai Pages/browser/MCP workflow with fixture inputs at **2026-10-26T07:22:47.089Z–07:22:47.802Z** and public historical research at **07:25:08.392Z–07:25:09.388Z**. Artifacts: `/private/tmp/aai-round3-combined-{workflow,live}/`. These runs additionally prove the Worker used this run's upstream, rather than an unrelated/stale service at the same port. No hosted preview/native client execution is claimed; server-first rollout remains required.

## Draft PR description

### Summary

- Add `changes` to compare each represented model's rating with its nearest earlier analysis date, using the shared aai backend.
- Preserve both source reports, explicit unavailable/no-history states and the existing safety boundaries.
- Bump both plugin manifests to 1.2.0; requires the aai comparison server to be deployed first.

### Verification

- CLI loopback compatibility checks: 2/2 passed; Skill Creator validation and diff checks passed.
- Full local Pages/MCP/CLI workflows passed with deterministic edge cases and live AAPL historical research.
- Existing production `tickers` and `latest SPY NVDA` commands passed unchanged.
- New command on deployed preview/production remains pending server rollout. No PR or release created.
