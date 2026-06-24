# medium-annoyed-api

Experimental Medium publisher for Markdown articles.

Medium no longer gives new API tokens, so this CLI uses the logged-in web
session path: create an empty Medium draft, translate Markdown into Medium
paragraph deltas, write those deltas, and optionally publish.

This is intentionally a CLI, not an MCP server.

## Install

```bash
uv sync
```

## Dry-run conversion

```bash
uv run medium-annoyed-api convert --file ../articles/articles/example/example.md --pretty
```

## Draft creation

Provide either a full Playwright storage-state file:

```bash
export MEDIUM_AUTH_STATE_FILE=/path/to/medium-auth.json
uv run medium-annoyed-api draft --file article.md --status draft --write-metadata
```

Or only the Medium `sid` cookie:

```bash
export MEDIUM_SESSION_COOKIE='...'
uv run medium-annoyed-api draft --file article.md --status draft
```

Use `--dry-run` first. `--status public` exists, but do not use it until draft
creation is proven against your Medium account.
