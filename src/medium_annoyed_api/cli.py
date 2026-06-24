from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

from .frontmatter import read_article, write_frontmatter_field
from .markdown_medium import article_to_medium_paragraphs
from .medium_session import MediumSessionError, create_medium_draft


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="medium-annoyed-api",
        description="Publish Markdown articles to Medium using session-backed internal editor calls.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    convert = sub.add_parser("convert", help="Convert a markdown article to Medium paragraph JSON")
    convert.add_argument("--file", "-f", required=True, help="Markdown article path")
    convert.add_argument("--pretty", action="store_true", help="Pretty-print JSON")

    draft = sub.add_parser("draft", help="Create a Medium draft from a markdown article")
    draft.add_argument("--file", "-f", required=True, help="Markdown article path")
    draft.add_argument("--status", choices=["draft", "public"], default="draft")
    draft.add_argument("--tags", "-t", default=None, help="Override tags with comma-separated list")
    draft.add_argument("--sid", default=None, help="Medium sid cookie; defaults to MEDIUM_SESSION_COOKIE")
    draft.add_argument("--auth-state", default=None, help="Playwright storage-state JSON; defaults to MEDIUM_AUTH_STATE_FILE")
    draft.add_argument("--dry-run", action="store_true", help="Print payload summary without calling Medium")
    draft.add_argument("--write-metadata", action="store_true", help="Write medium_draft_id and medium_edit_url to frontmatter")

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "convert":
            _cmd_convert(args)
        elif args.command == "draft":
            asyncio.run(_cmd_draft(args))
        else:
            parser.error(f"unknown command: {args.command}")
    except MediumSessionError as exc:
        print(f"medium-annoyed-api: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


def _cmd_convert(args: argparse.Namespace) -> None:
    article = read_article(args.file)
    paragraphs = article_to_medium_paragraphs(article.title, article.body, article.path.parent)
    output = {
        "title": article.title,
        "tags": article.tags,
        "canonical_url": article.canonical_url,
        "paragraph_count": len(paragraphs),
        "paragraphs": paragraphs,
    }
    print(json.dumps(output, indent=2 if args.pretty else None, ensure_ascii=False))


async def _cmd_draft(args: argparse.Namespace) -> None:
    article = read_article(args.file)
    paragraphs = article_to_medium_paragraphs(article.title, article.body, article.path.parent)
    tags = _parse_tags(args.tags) if args.tags else article.tags

    summary: dict[str, Any] = {
        "title": article.title,
        "status": args.status,
        "tags": tags[:5],
        "canonical_url": article.canonical_url,
        "paragraph_count": len(paragraphs),
        "image_count": sum(1 for paragraph in paragraphs if paragraph.get("type") == 4),
    }

    if args.dry_run:
        summary["dry_run"] = True
        summary["paragraphs"] = paragraphs
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return

    result = await create_medium_draft(
        title=article.title,
        paragraphs=paragraphs,
        tags=tags,
        status=args.status,
        auth_state_file=args.auth_state,
        sid=args.sid,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))

    post_id = result.get("id")
    if args.write_metadata and post_id:
        write_frontmatter_field(article.path, "medium_draft_id", str(post_id))
        if result.get("editUrl"):
            write_frontmatter_field(article.path, "medium_edit_url", str(result["editUrl"]))
        if result.get("mediumUrl"):
            write_frontmatter_field(article.path, "medium_url", str(result["mediumUrl"]))


def _parse_tags(raw: str) -> list[str]:
    return [tag.strip() for tag in raw.split(",") if tag.strip()]
