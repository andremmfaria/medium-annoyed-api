from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Article:
    path: Path
    meta: dict[str, Any]
    body: str

    @property
    def title(self) -> str:
        title = self.meta.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()

        for line in self.body.splitlines():
            if line.startswith("# "):
                return line[2:].strip()

        return self.path.stem

    @property
    def tags(self) -> list[str]:
        raw = self.meta.get("tags", [])
        if raw is None:
            return []
        if isinstance(raw, str):
            return [tag.strip() for tag in raw.split(",") if tag.strip()]
        if isinstance(raw, list):
            return [str(tag).strip() for tag in raw if str(tag).strip()]
        return []

    @property
    def canonical_url(self) -> str | None:
        value = self.meta.get("canonical_url") or self.meta.get("canonicalUrl")
        return str(value).strip() if value else None


def read_article(path: str | Path) -> Article:
    article_path = Path(path).expanduser().resolve()
    raw = article_path.read_text(encoding="utf-8")

    if not raw.startswith("---"):
        return Article(path=article_path, meta={}, body=raw.strip())

    end = raw.find("\n---", 3)
    if end == -1:
        return Article(path=article_path, meta={}, body=raw.strip())

    frontmatter = raw[3:end].strip()
    body = raw[end + 4 :].strip()
    meta = yaml.safe_load(frontmatter) or {}
    if not isinstance(meta, dict):
        meta = {}
    return Article(path=article_path, meta=meta, body=body)


def write_frontmatter_field(path: str | Path, key: str, value: str) -> None:
    article_path = Path(path).expanduser().resolve()
    raw = article_path.read_text(encoding="utf-8")

    if not raw.startswith("---"):
        return

    end = raw.find("\n---", 3)
    if end == -1:
        return

    frontmatter = raw[3:end].strip()
    body = raw[end + 4 :]
    meta = yaml.safe_load(frontmatter) or {}
    if not isinstance(meta, dict):
        return

    meta[key] = value
    rendered = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()
    article_path.write_text(f"---\n{rendered}\n---{body}", encoding="utf-8")
