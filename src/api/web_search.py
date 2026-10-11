"""Restricted web-search adapter for the web-search agent."""

from __future__ import annotations

from html.parser import HTMLParser
import re
from typing import Any

import httpx


class _ResultParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._current: dict[str, str] | None = None
        self._capture = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "a" and "result__a" in values.get("class", ""):
            self._current = {"title": "", "url": values.get("href", "")}
            self._capture = True

    def handle_data(self, data: str) -> None:
        if self._capture and self._current is not None:
            self._current["title"] += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._capture and self._current:
            self._current["title"] = " ".join(self._current["title"].split())
            self.results.append(self._current)
            self._current = None
            self._capture = False


class WebSearchAgent:
    """Search public web results with bounded requests and no arbitrary URL fetch."""

    def __init__(self, endpoint: str, timeout: float = 10):
        self.endpoint = endpoint
        self.timeout = timeout

    async def search(self, query: str, limit: int = 5) -> list[dict[str, str]]:
        if len(query) > 500:
            raise ValueError("Search query is too long")
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
            response = await client.post(self.endpoint, data={"q": query}, headers={"User-Agent": "AgricultureRAG/3"})
            response.raise_for_status()
        parser = _ResultParser()
        parser.feed(response.text)
        return parser.results[: max(1, min(limit, 10))]
