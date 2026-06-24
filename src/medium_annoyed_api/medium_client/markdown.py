from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from markdown_it import MarkdownIt
from markdown_it.token import Token


@dataclass
class ListState:
    ordered: bool
    index: int = 1


@dataclass
class RenderState:
    paragraphs: list[dict[str, Any]] = field(default_factory=list)
    block: str | None = None
    blockquote_depth: int = 0
    list_stack: list[ListState] = field(default_factory=list)
    pending_list_prefix: str | None = None
    in_table: bool = False
    current_row: list[str] | None = None


def article_to_medium_paragraphs(title: str, markdown: str, base_path: Path) -> list[dict[str, Any]]:
    parser = MarkdownIt("default", {"html": False, "linkify": False, "typographer": False})
    parser.enable("table")
    tokens = parser.parse(markdown)

    state = RenderState()
    state.paragraphs.append(_paragraph(3, title))

    for token in tokens:
        if token.type == "heading_open":
            state.block = "heading"
        elif token.type == "heading_close":
            state.block = None
        elif token.type == "paragraph_open":
            state.block = "paragraph"
        elif token.type == "paragraph_close":
            state.block = None
            state.pending_list_prefix = None
        elif token.type == "blockquote_open":
            state.blockquote_depth += 1
        elif token.type == "blockquote_close":
            state.blockquote_depth = max(0, state.blockquote_depth - 1)
        elif token.type == "bullet_list_open":
            state.list_stack.append(ListState(ordered=False))
        elif token.type == "ordered_list_open":
            start = int(token.attrGet("start") or 1)
            state.list_stack.append(ListState(ordered=True, index=start))
        elif token.type in {"bullet_list_close", "ordered_list_close"}:
            if state.list_stack:
                state.list_stack.pop()
        elif token.type == "list_item_open":
            state.pending_list_prefix = _next_list_prefix(state.list_stack[-1]) if state.list_stack else None
        elif token.type == "fence":
            state.paragraphs.append(_paragraph(8, token.content.rstrip("\n")))
        elif token.type == "code_block":
            state.paragraphs.append(_paragraph(8, token.content.rstrip("\n")))
        elif token.type == "hr":
            state.paragraphs.append(_paragraph(15, ""))
        elif token.type == "table_open":
            state.in_table = True
        elif token.type == "table_close":
            state.in_table = False
        elif token.type == "tr_open":
            state.current_row = []
        elif token.type == "tr_close":
            if state.current_row:
                state.paragraphs.append(_paragraph(1, " | ".join(state.current_row)))
            state.current_row = None
        elif token.type == "inline":
            _handle_inline(state, token, base_path)

    return state.paragraphs


def _handle_inline(state: RenderState, token: Token, base_path: Path) -> None:
    children = token.children or []
    image = _sole_image(children, base_path)
    if image is not None and state.block == "paragraph":
        state.paragraphs.append(image)
        return

    text, markups = _render_inline(children)
    text = text.strip("\n")
    if not text.strip():
        return

    if state.in_table and state.current_row is not None:
        state.current_row.append(" ".join(text.split()))
        return

    if state.pending_list_prefix:
        offset = len(state.pending_list_prefix)
        markups = [_shift_markup(markup, offset) for markup in markups]
        text = f"{state.pending_list_prefix}{text}"

    if state.block == "heading":
        state.paragraphs.append(_paragraph(3, text, markups))
    elif state.blockquote_depth:
        state.paragraphs.append(_paragraph(6, text, markups))
    else:
        state.paragraphs.append(_paragraph(1, text, markups))


def _render_inline(tokens: list[Token]) -> tuple[str, list[dict[str, Any]]]:
    text = ""
    markups: list[dict[str, Any]] = []
    stack: list[tuple[str, int, str | None]] = []

    for token in tokens:
        if token.type == "text":
            text += token.content
        elif token.type in {"softbreak", "hardbreak"}:
            text += "\n"
        elif token.type == "code_inline":
            start = len(text)
            text += token.content
            markups.append({"type": 10, "start": start, "end": len(text)})
        elif token.type == "strong_open":
            stack.append(("strong", len(text), None))
        elif token.type == "strong_close":
            _close_markup(stack, markups, "strong", 1, len(text))
        elif token.type == "em_open":
            stack.append(("em", len(text), None))
        elif token.type == "em_close":
            _close_markup(stack, markups, "em", 2, len(text))
        elif token.type == "link_open":
            stack.append(("link", len(text), token.attrGet("href") or ""))
        elif token.type == "link_close":
            _close_markup(stack, markups, "link", 3, len(text))
        elif token.type == "image":
            text += token.content or token.attrGet("alt") or ""

    return text, markups


def _close_markup(
    stack: list[tuple[str, int, str | None]],
    markups: list[dict[str, Any]],
    kind: str,
    medium_type: int,
    end: int,
) -> None:
    for index in range(len(stack) - 1, -1, -1):
        item_kind, start, href = stack[index]
        if item_kind != kind:
            continue
        del stack[index]
        if end <= start:
            return
        markup: dict[str, Any] = {"type": medium_type, "start": start, "end": end}
        if href:
            markup["href"] = href
        markups.append(markup)
        return


def _sole_image(tokens: list[Token], base_path: Path) -> dict[str, Any] | None:
    meaningful = [
        token
        for token in tokens
        if token.type not in {"softbreak", "hardbreak"} and (token.type == "image" or token.content.strip())
    ]
    if len(meaningful) != 1 or meaningful[0].type != "image":
        return None

    token = meaningful[0]
    src = token.attrGet("src")
    if not src:
        return None

    source = src if src.startswith(("http://", "https://")) else str((base_path / src).resolve())
    return {
        "name": _random_name(),
        "type": 4,
        "text": token.content or token.attrGet("alt") or "",
        "markups": [],
        "source": source,
    }


def _paragraph(paragraph_type: int, text: str, markups: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "name": _random_name(),
        "type": paragraph_type,
        "text": text,
        "markups": markups or [],
    }


def _next_list_prefix(state: ListState) -> str:
    if not state.ordered:
        return "- "

    prefix = f"{state.index}. "
    state.index += 1
    return prefix


def _shift_markup(markup: dict[str, Any], offset: int) -> dict[str, Any]:
    shifted = dict(markup)
    shifted["start"] = int(shifted["start"]) + offset
    shifted["end"] = int(shifted["end"]) + offset
    return shifted


def _random_name() -> str:
    import secrets

    return secrets.token_hex(2)
