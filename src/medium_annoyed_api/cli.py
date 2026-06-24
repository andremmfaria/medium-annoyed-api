from __future__ import annotations

import asyncio
import json
from typing import Any

import click

from medium_annoyed_api.frontmatter import read_article, write_frontmatter_field
from medium_annoyed_api.medium_client import MediumClient, MediumClientError
from medium_annoyed_api.medium_client.markdown import article_to_medium_paragraphs


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def main() -> None:
    """Publish Markdown articles to Medium using session-backed editor calls."""


@main.command()
@click.option("--file", "-f", "file_path", required=True, type=click.Path(exists=True, dir_okay=False), help="Markdown article path.")
@click.option("--pretty", is_flag=True, help="Pretty-print JSON.")
def convert(file_path: str, pretty: bool) -> None:
    """Convert a Markdown article to Medium paragraph JSON."""
    article = read_article(file_path)
    paragraphs = article_to_medium_paragraphs(article.title, article.body, article.path.parent)
    output = {
        "title": article.title,
        "tags": article.tags,
        "canonical_url": article.canonical_url,
        "paragraph_count": len(paragraphs),
        "paragraphs": paragraphs,
    }
    click.echo(json.dumps(output, indent=2 if pretty else None, ensure_ascii=False))


@main.command()
@click.option("--file", "-f", "file_path", required=True, type=click.Path(exists=True, dir_okay=False), help="Markdown article path.")
@click.option("--status", type=click.Choice(["draft", "public"]), default="draft", show_default=True)
@click.option("--tags", "-t", default=None, help="Override tags with a comma-separated list.")
@click.option("--sid", default=None, help="Medium sid cookie; defaults to MEDIUM_SESSION_COOKIE.")
@click.option(
    "--auth-json",
    "--auth-state",
    "auth_json",
    default=None,
    help="Medium auth JSON path; defaults to MEDIUM_AUTH_JSON, MEDIUM_AUTH_STATE_FILE, then ~/.config/medium-auth.json.",
)
@click.option("--dry-run", is_flag=True, help="Print payload summary without calling Medium.")
@click.option("--write-metadata", is_flag=True, help="Write medium_draft_id and medium_edit_url to frontmatter.")
def draft(
    file_path: str,
    status: str,
    tags: str | None,
    sid: str | None,
    auth_json: str | None,
    dry_run: bool,
    write_metadata: bool,
) -> None:
    """Create a Medium draft from a Markdown article."""
    try:
        asyncio.run(_draft_async(file_path, status, tags, sid, auth_json, dry_run, write_metadata))
    except MediumClientError as exc:
        raise click.ClickException(str(exc)) from exc


async def _draft_async(
    file_path: str,
    status: str,
    tags: str | None,
    sid: str | None,
    auth_json: str | None,
    dry_run: bool,
    write_metadata: bool,
) -> None:
    article = read_article(file_path)
    paragraphs = article_to_medium_paragraphs(article.title, article.body, article.path.parent)
    resolved_tags = _parse_tags(tags) if tags else article.tags

    summary: dict[str, Any] = {
        "title": article.title,
        "status": status,
        "tags": resolved_tags[:5],
        "canonical_url": article.canonical_url,
        "paragraph_count": len(paragraphs),
        "image_count": sum(1 for paragraph in paragraphs if paragraph.get("type") == 4),
    }

    if dry_run:
        summary["dry_run"] = True
        summary["paragraphs"] = paragraphs
        click.echo(json.dumps(summary, indent=2, ensure_ascii=False))
        return

    client = MediumClient(auth_state_file=auth_json, sid=sid)
    result = await client.create_draft(
        title=article.title,
        paragraphs=paragraphs,
        tags=resolved_tags,
        status=status,
    )
    click.echo(json.dumps(result, indent=2, ensure_ascii=False))

    post_id = result.get("id")
    if write_metadata and post_id:
        write_frontmatter_field(article.path, "medium_draft_id", str(post_id))
        if result.get("editUrl"):
            write_frontmatter_field(article.path, "medium_edit_url", str(result["editUrl"]))
        if result.get("mediumUrl"):
            write_frontmatter_field(article.path, "medium_url", str(result["mediumUrl"]))


def _parse_tags(raw: str) -> list[str]:
    return [tag.strip() for tag in raw.split(",") if tag.strip()]
