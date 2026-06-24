from __future__ import annotations

import json
import mimetypes
import os
import time
from pathlib import Path
from typing import Any

import httpx


class MediumClientError(RuntimeError):
    pass


class MediumClient:
    web_base = "https://medium.com"

    def __init__(
        self,
        *,
        auth_state_file: str | None = None,
        sid: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.auth_state_file = auth_state_file
        self.sid = sid
        self.timeout = timeout

    async def create_draft(
        self,
        *,
        title: str,
        paragraphs: list[dict[str, Any]],
        tags: list[str],
        status: str = "draft",
    ) -> dict[str, Any]:
        cookie_string = self.cookie_string()
        headers = self.headers(cookie_string)

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as http:
            post = await self._create_empty_post(http, headers)
            post_id = post.get("id")
            if not post_id:
                raise MediumClientError(f"Medium createPost returned no id: {post}")

            resolved = await self._resolve_images(http, headers, cookie_string, paragraphs)
            latest_rev = await self._write_paragraph_deltas(http, headers, cookie_string, post_id, resolved)

            if tags:
                await self._set_tags(http, headers, post_id, tags[:5])

            if status == "public":
                published = await self._publish_post(http, headers, post_id)
                post.update(published)
                post["publishStatus"] = "public"
            else:
                post["publishStatus"] = "draft"

            post["latestRev"] = latest_rev
            post["paragraphCount"] = len(resolved)
            post["editUrl"] = f"{self.web_base}/p/{post_id}/edit"
            return post

    def cookie_string(self) -> str:
        auth_path = self.auth_state_file or os.environ.get("MEDIUM_AUTH_STATE_FILE")
        if auth_path:
            path = Path(auth_path).expanduser()
            if path.is_file():
                state = json.loads(path.read_text(encoding="utf-8"))
                cookies = {
                    item["name"]: item["value"]
                    for item in state.get("cookies", [])
                    if "medium.com" in item.get("domain", "")
                }
                if "sid" in cookies:
                    return "; ".join(f"{key}={value}" for key, value in cookies.items())

        sid_value = self.sid or os.environ.get("MEDIUM_SESSION_COOKIE")
        if sid_value:
            return f"sid={sid_value}"

        raise MediumClientError(
            "No Medium auth found. Set MEDIUM_AUTH_STATE_FILE to a Playwright storage-state JSON "
            "or set MEDIUM_SESSION_COOKIE to your Medium sid cookie."
        )

    def headers(self, cookie_string: str) -> dict[str, str]:
        headers = {
            "Cookie": cookie_string,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
        }
        xsrf = self._cookie_value(cookie_string, "xsrf")
        if xsrf:
            headers["x-xsrf-token"] = xsrf
        return headers

    async def _create_empty_post(self, http: httpx.AsyncClient, headers: dict[str, str]) -> dict[str, Any]:
        response = await http.post(
            f"{self.web_base}/_/graphql",
            headers=headers,
            json={
                "query": (
                    "mutation CreatePost($input: CreatePostInput!) { "
                    "createPost(input: $input) { id title mediumUrl } }"
                ),
                "variables": {"input": {}},
            },
        )
        self._raise_for_medium(response, "createPost")
        data = response.json()
        if data.get("errors"):
            raise MediumClientError(f"Medium GraphQL error: {data['errors']}")
        return data.get("data", {}).get("createPost", {})

    async def _write_paragraph_deltas(
        self,
        http: httpx.AsyncClient,
        headers: dict[str, str],
        cookie_string: str,
        post_id: str,
        paragraphs: list[dict[str, Any]],
    ) -> int | None:
        delta_headers = self._delta_headers(headers, cookie_string, post_id)
        deltas: list[dict[str, Any]] = [
            {
                "type": 8,
                "index": 0,
                "section": {"name": self._random_name(), "startIndex": 0},
            }
        ]

        for index, paragraph in enumerate(paragraphs):
            is_image = paragraph["type"] == 4
            insert: dict[str, Any] = {
                "name": paragraph["name"],
                "type": paragraph["type"],
                "text": "",
                "markups": [],
            }
            if is_image:
                insert["layout"] = 1
                insert["metadata"] = {}

            deltas.append(
                {
                    "type": 1,
                    "index": index,
                    "paragraph": insert,
                    **({"isStartOfSection": False} if index > 0 else {}),
                }
            )

            update: dict[str, Any] = {
                "name": paragraph["name"],
                "type": paragraph["type"],
                "text": paragraph.get("text", ""),
                "markups": paragraph.get("markups", []),
            }
            if is_image:
                update["layout"] = 1
                update["metadata"] = paragraph.get("metadata", {})

            if update["text"] or update.get("metadata"):
                deltas.append(
                    {
                        "type": 3,
                        "index": index,
                        "paragraph": update,
                        "verifySameName": True,
                    }
                )

        response = await http.post(
            f"{self.web_base}/p/{post_id}/deltas?logLockId={self._random_lock_id()}",
            headers=delta_headers,
            json={"id": post_id, "deltas": deltas, "baseRev": -1},
        )
        self._raise_for_medium(response, "write deltas")
        data = self._parse_medium_json(response.text)
        return data.get("payload", {}).get("value", {}).get("latestRev")

    async def _resolve_images(
        self,
        http: httpx.AsyncClient,
        headers: dict[str, str],
        cookie_string: str,
        paragraphs: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        resolved = []
        for paragraph in paragraphs:
            if paragraph.get("type") != 4 or not paragraph.get("source"):
                resolved.append(paragraph)
                continue

            source = str(paragraph["source"])
            image_bytes, filename, mime_type = await self._load_image(http, source)
            upload = await self._upload_image(http, headers, cookie_string, image_bytes, filename, mime_type)
            clean = dict(paragraph)
            clean.pop("source", None)
            clean["metadata"] = {
                "id": upload["fileId"],
                "originalWidth": upload.get("imgWidth", 0),
                "originalHeight": upload.get("imgHeight", 0),
            }
            resolved.append(clean)

        return resolved

    async def _load_image(self, http: httpx.AsyncClient, source: str) -> tuple[bytes, str, str]:
        if source.startswith(("http://", "https://")):
            response = await http.get(source)
            response.raise_for_status()
            filename = source.rstrip("/").split("/")[-1] or "image"
            mime_type = response.headers.get("content-type", "").split(";")[0] or "image/jpeg"
            return response.content, filename, mime_type

        path = Path(source)
        mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return path.read_bytes(), path.name, mime_type

    async def _upload_image(
        self,
        http: httpx.AsyncClient,
        headers: dict[str, str],
        cookie_string: str,
        image_bytes: bytes,
        filename: str,
        mime_type: str,
    ) -> dict[str, Any]:
        upload_headers = {
            "Cookie": cookie_string,
            "Accept": "application/json",
            "User-Agent": headers["User-Agent"],
            "X-Obvious-CID": "web",
        }
        if headers.get("x-xsrf-token"):
            upload_headers["X-XSRF-Token"] = headers["x-xsrf-token"]

        response = await http.post(
            f"{self.web_base}/_/upload?source=6",
            headers=upload_headers,
            files={"uploadedFile": (filename, image_bytes, mime_type)},
        )
        self._raise_for_medium(response, "upload image")
        data = self._parse_medium_json(response.text)
        value = data.get("payload", {}).get("value", {})
        if not value.get("fileId"):
            raise MediumClientError(f"Medium upload returned no fileId: {data}")
        return value

    async def _set_tags(self, http: httpx.AsyncClient, headers: dict[str, str], post_id: str, tags: list[str]) -> None:
        response = await http.post(
            f"{self.web_base}/_/graphql",
            headers=headers,
            json={
                "query": (
                    "mutation SetPostTags($targetPostId: ID!, $tagNames: [String!]!) { "
                    "setPostTags(targetPostId: $targetPostId, tagNames: $tagNames) { id title } }"
                ),
                "variables": {"targetPostId": post_id, "tagNames": tags},
            },
        )
        self._raise_for_medium(response, "set tags")
        data = response.json()
        if data.get("errors"):
            raise MediumClientError(f"Medium tag error: {data['errors']}")

    async def _publish_post(self, http: httpx.AsyncClient, headers: dict[str, str], post_id: str) -> dict[str, Any]:
        response = await http.post(
            f"{self.web_base}/_/graphql",
            headers=headers,
            json={
                "query": (
                    "mutation PublishPost($postId: ID!) { "
                    "publishPost(postId: $postId) { id title mediumUrl } }"
                ),
                "variables": {"postId": post_id},
            },
        )
        self._raise_for_medium(response, "publish")
        data = response.json()
        if data.get("errors"):
            raise MediumClientError(f"Medium publish error: {data['errors']}")
        return data.get("data", {}).get("publishPost", {})

    def _delta_headers(self, headers: dict[str, str], cookie_string: str, post_id: str) -> dict[str, str]:
        delta_headers = {
            "Cookie": cookie_string,
            "X-Client-Date": str(int(time.time() * 1000)),
            "X-Obvious-CID": "web",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": headers["User-Agent"],
            "Referer": f"{self.web_base}/p/{post_id}/edit",
        }
        if headers.get("x-xsrf-token"):
            delta_headers["X-XSRF-Token"] = headers["x-xsrf-token"]
        return delta_headers

    def _parse_medium_json(self, text: str) -> Any:
        for prefix in ("])}while(1);</x>", "])}while(1);<x>", "])}while(1);"):
            if text.startswith(prefix):
                text = text[len(prefix) :]
                break
        return json.loads(text)

    def _raise_for_medium(self, response: httpx.Response, context: str) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:800]
            raise MediumClientError(f"Medium {context} failed: HTTP {exc.response.status_code}: {body}") from exc

    def _cookie_value(self, cookie_string: str, name: str) -> str | None:
        for part in cookie_string.split(";"):
            key, _, value = part.strip().partition("=")
            if key == name:
                return value
        return None

    def _random_name(self) -> str:
        import secrets

        return secrets.token_hex(2)

    def _random_lock_id(self) -> str:
        import random

        return str(random.randint(1000, 9999))
