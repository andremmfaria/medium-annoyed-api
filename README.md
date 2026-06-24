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

## Browser auth state helper

The CLI can read a Playwright-compatible auth state JSON. Build one from the
browser where you are already logged into Medium:

1. Open `https://medium.com` in your browser.
2. Open DevTools.
3. Paste the contents of `scripts/create-medium-auth.js` into the browser console.
4. The script copies JSON to your clipboard.
5. Save that JSON as `medium-auth.json`.
6. Point the CLI at it:

```bash
export MEDIUM_AUTH_STATE_FILE="$PWD/medium-auth.json"
uv run medium-annoyed-api draft --file article.md --status draft
```

Browser JavaScript cannot read cookies marked `HttpOnly`. If the generated JSON
does not include `sid`, copy `sid` manually from DevTools → Application →
Cookies → Medium and add it to the `cookies` array:

```json
{
  "name": "sid",
  "value": "...",
  "domain": ".medium.com",
  "path": "/",
  "expires": 1790000000,
  "httpOnly": true,
  "secure": true,
  "sameSite": "Lax"
}
```

Use `--dry-run` first. `--status public` exists, but do not use it until draft
creation is proven against your Medium account.
