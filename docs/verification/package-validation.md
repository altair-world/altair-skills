# Package validation evidence

Local verification record, captured before publication after three review rounds. Native plugin loading and exact supported CI-runtime checks were pending at that point; the PR Verification section tracks subsequent results. No release or directory submission is included.

- Base: `b14c93057029d46a72cc9ed902a18f6d24d04203`; branch `codex/discovery-install`.
- Verified 2026-10-26 approximately 05:16–05:20 UTC.
- Before: CI checked only Claude metadata and skill frontmatter. Codex manifest wiring, version alignment, bundled resources, marketplace source and MCP endpoint were not checked.
- After: an offline, Python-stdlib repository contract validator checks both client packages and the exact credential-free shared MCP configuration. Existing manifests, skills and release version remain unchanged; no behavior change/version bump.

## Results

```sh
python3 scripts/validate_package.py
python3 -m unittest discover -s scripts -p 'test_*.py' -v
```

Passed on Python 3.9.6 and 3.12: eight tests covering valid layout and broken version, traversal, marketplace root, missing skill/script, paid endpoint and symlink escape. Python 3.8 syntax parsing passed. CI executes the same checks on 3.8 and 3.13; exact runtime execution on those versions is not claimed locally.

Skills CLI 1.7.4 installed the local worktree into an empty disposable directory with `--skill altair-research altair-market --agent codex claude-code --copy --yes`, `DISABLE_TELEMETRY=1` and `DO_NOT_TRACK=1`. All four copied skill folders match source recursively. No global client configuration was modified.

Installed copies successfully executed `tickers`, `latest SPY NVDA --summary-chars 120`, `breadth --days 5` and `indicators SPX NDX SOX` against the read-only public MCP endpoint. Research date: 2026-10-24; market reading date: 2026-10-23; breadth returned five sessions, 11 sectors and SPX/NDX/SOX breadth of 70%/48%/7%. This is installation-to-data verification, not a new independent source-price comparison or actual agent behavioral evaluation.

`git diff --check` and Python compilation passed. Skill Creator's initial validator attempt was blocked by missing PyYAML; parent subsequently ran the official `quick_validate.py` successfully for both skills using disposable `/private/tmp/aai-skill-validation.G1V3W2/venv` (Python 3.9.6 and PyYAML 6.0.3, approximately 05:28 UTC; global configuration untouched). Skill instructions were not edited. Full native plugin loading and actual Codex/Claude model execution were not tested; Claude CLI is not installed. Public directory approval/availability is unchanged.

Round 1 reviewed path containment, failure detection, standard-library/Python compatibility and CI execution. Round 2 parent independently inspected the validator, tests, workflow and documentation, reran the Python 3.9 validator and all eight mutations (passed), and checked patch hygiene (passed). Its documentation finding was fixed by clarifying that helpers need no separately configured client connection, not that they avoid MCP. No outstanding actionable review blocker remains. Parent also independently verified the companion website's 29 browser checks on Node 22.23.4; all passed in 6.6 seconds (`/private/tmp/aai-parent-discovery-browser-node22.log`).

## Third review and feedback

The parent completed the additional review on 2026-10-26. The extra subagent passes were interrupted by workspace credit exhaustion and are not counted as completed independent reviews.

Two newly introduced validator gaps were reproduced in disposable package copies: a referenced `.py` helper could be a directory, and Claude/marketplace component declarations were ignored. An inline Claude `altair` server pointing to paid `/mcp` still passed the old check of the root free `.mcp.json`. A marketplace selection of only one skill likewise bypassed the advertised two-skill check. These were false passes in the new validator, not defects in the actual published package.

The validator now requires helpers to be files and checks explicit Claude/marketplace declarations against this repository's shared component paths. It intentionally does not implement every client-supported configuration. [Claude's manifest reference](https://code.claude.com/docs/en/plugins-reference) documents merged MCP declarations and marketplace skill selection; the narrower local contract is explained in the README.

Final checks: package validation passed, and **13/13** mutation/layout cases passed on Python 3.9.6 and 3.12. The validator also passed against the companion research-change worktree with its `1.2.0` manifests. The five additional cases cover directory helpers, paid inline override, missing Claude skill path, marketplace skill subset, and valid explicit shared paths. CI already discovers these cases on Python 3.8/3.13; those exact interpreters remain unclaimed locally. No manifests, installed skills or publication settings were changed by this review.

## Draft PR description

### Summary

- Validate Claude and Codex package wiring, versions, resources and the free MCP endpoint offline.
- Add disposable broken-package checks and run them in the existing supported Python CI matrix.
- Clarify Codex skill versus plugin packaging without implying public-directory availability.

### Verification

- Offline validation and 13 package/layout tests passed on Python 3.9.6/3.12; Python 3.8 syntax check passed.
- Clean local-source skills CLI install for both Codex and Claude Code succeeded; installed helpers returned real public research and market readings.
- No skill behavior changes; version bump not applicable. Exact Python 3.8/3.13 CI and native plugin loading remain unverified locally.
