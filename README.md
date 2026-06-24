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

## Auth state helper

The CLI can read a Playwright-compatible auth state JSON. Build one from your
Medium cookies with:

```bash
MEDIUM_SESSION_COOKIE='...' node scripts/create-medium-auth.js --output medium-auth.json
export MEDIUM_AUTH_STATE_FILE="$PWD/medium-auth.json"
```

If you also have `xsrf`, `uid`, or Cloudflare cookies, include them:

```bash
node scripts/create-medium-auth.js \
  --sid '...' \
  --xsrf '...' \
  --uid '...' \
  --cookie 'cf_clearance=...'
```

Use `--dry-run` first. `--status public` exists, but do not use it until draft
creation is proven against your Medium account.
