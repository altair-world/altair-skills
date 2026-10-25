# AGENTS.md

Notes for agents working on this repo. Edit this file; `CLAUDE.md` imports it.

## Layout

- `skills/<name>/SKILL.md` plus `scripts/`: one folder per skill. The frontmatter `name` must match the folder; `description` is at most 1024 characters.
- `.claude-plugin/plugin.json` and `marketplace.json`: the Claude Code plugin. Keep the plugin name and description the same in both.
- `README.md`: install and usage for each skill. Update it with any user-visible change. GitHub Pages (legacy Jekyll build from `main` at `/`) renders it as https://altair-world.github.io/altair-skills/, so link to files outside Markdown (`LICENSE`, `.github/`) with full GitHub URLs; relative links to them break on the site.

## Changing a skill

- Scripts use the standard library only and must run on Python 3.8.
- Verify against the live server: `python3 skills/altair-research/scripts/altair_research.py tickers` and `latest SPY NVDA`. Set `ALTAIR_MCP_URL` to test against a preview deployment.
- For altair-market, run `python3 skills/altair-market/scripts/altair_market.py breadth`, `breadth --days 5` and `indicators SPX NDX SOX` against the live server.
- If a change depends on a new server tool, merge only after the server change is deployed.
- Bump the semver `version` in `.claude-plugin/plugin.json` and `.codex-plugin/plugin.json` together when skill behavior changes.
- Keep the disclaimers: research reports are AI-generated, and neither reports nor market readings are financial advice.

## Pull requests

- `main` changes only through pull requests; the main ruleset requires the `check` job.
- Fill in `.github/pull_request_template.md`: Summary and Verification.
- The `auto-merge` label squash-merges a PR once `check` passes.
- Use the system git identity; no co-authors.

## Release

From merged `main`, after bumping the version:

1. GitHub: `gh skill publish --tag vX.Y.Z` (validates the skill and creates the release).
2. ClawHub, once per skill folder (replace `<skill>` with `altair-research` or `altair-market`): `clawhub skill publish skills/<skill> --slug <skill> --owner altair-world --version X.Y.Z --changelog "<what changed>" --source-repo altair-world/altair-skills --source-commit "$(git rev-list -n1 vX.Y.Z)" --source-ref vX.Y.Z --source-path skills/<skill>`. `--source-repo` needs `--source-commit`. Published versions can't be replaced, and the new version stays private until ClawHub's security scan passes.
3. Claude directory: the submission at claude.ai/directory/manage tracks the `v*` tag set in its settings; point it at the new tag, wait for the scan, then Publish. While a version waits for an Anthropic reviewer, leave it; move the tag after it is published so the queue position isn't lost.
4. OpenAI plugin directory: build the ZIP and upload it as a new version at platform.openai.com/plugins:

   ```bash
   git archive --format=zip --output=/tmp/altair-openai-plugin.zip HEAD -- . ':!.github' ':!AGENTS.md' ':!CLAUDE.md'
   ```

   Keep `.mcp.json` at `https://altairworld.com/mcp/free`: OpenAI won't change an existing plugin's MCP URL, and its guidelines forbid selling digital services, so the plugin must not reach the paid `get_research_signals` tool on `/mcp`.

   Each submission needs a demo recording URL under Review information → Supporting content. It should show every positive and negative test case in `.codex-plugin/plugin.json`. The 1.0.0 recording is the `altair-research-codex-demo.mp4` asset on release `v1.0.1` and does not cover the market test case added in 1.1.0. It runs each test case through `codex exec --json` with the plugin installed in a clean `CODEX_HOME`, recorded with `vhs`. Upload a new version only after the one in review is decided.
5. LobeHub doesn't find the repo on its own: submit it once from lobehub.com → Community → your profile → Submit Repo (reviewed by LobeHub). Once it lists a skill, `npx @lobehub/market-cli skill claim <identifier>`, then `skill publish --dir skills/<skill> --identifier <identifier>` for new versions.
6. skills.sh and SkillsMP index public GitHub repos themselves; there is nothing to submit. skills.sh lists a skill path once someone installs it; after the repo moved from `bichengwang` it showed only the old path until one `npx skills add altair-world/altair-skills --skill altair-research` run. Run the same for each new skill.
