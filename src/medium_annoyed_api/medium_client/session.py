from __future__ import annotations

from typing import Any

from medium_annoyed_api.medium_client.client import MediumClient, MediumClientError

MediumSessionError = MediumClientError


def build_cookie_string(auth_state_file: str | None = None, sid: str | None = None) -> str:
    return MediumClient(auth_state_file=auth_state_file, sid=sid).cookie_string()


def medium_headers(cookie_string: str) -> dict[str, str]:
    return MediumClient().headers(cookie_string)


async def create_medium_draft(
    *,
    title: str,
    paragraphs: list[dict[str, Any]],
    tags: list[str],
    status: str,
    auth_state_file: str | None = None,
    sid: str | None = None,
) -> dict[str, Any]:
    client = MediumClient(auth_state_file=auth_state_file, sid=sid)
    return await client.create_draft(title=title, paragraphs=paragraphs, tags=tags, status=status)
