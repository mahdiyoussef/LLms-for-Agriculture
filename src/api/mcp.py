"""Constrained HTTP MCP client for approved remote MCP servers."""

from __future__ import annotations

from urllib.parse import urlparse
import ipaddress
import socket
from typing import Any
import uuid

import httpx


class MCPClient:
    """Small JSON-RPC client with explicit server allowlisting."""

    def __init__(self, allowed_servers: tuple[str, ...], timeout: float = 10):
        self.allowed_servers = allowed_servers
        self.timeout = timeout

    def _validate(self, base_url: str) -> None:
        parsed = urlparse(base_url)
        if not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("MCP URL must contain a hostname and no embedded credentials")
        if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1"}:
            raise ValueError("MCP servers must use HTTPS unless running locally")
        try:
            addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, None)}
        except socket.gaierror as exc:
            raise ValueError("MCP hostname could not be resolved") from exc
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if not (ip.is_loopback and parsed.hostname in {"localhost", "127.0.0.1"}):
                if ip.is_private or ip.is_link_local or ip.is_multicast or ip.is_reserved:
                    raise ValueError("MCP server resolves to a restricted network address")
        if self.allowed_servers and base_url.rstrip("/") not in {url.rstrip("/") for url in self.allowed_servers}:
            raise ValueError("MCP server is not allowlisted")

    async def request(self, base_url: str, method: str, params: dict[str, Any] | None = None) -> Any:
        self._validate(base_url)
        payload = {"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": method, "params": params or {}}
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
            response = await client.post(base_url, json=payload)
            response.raise_for_status()
        result = response.json()
        if "error" in result:
            raise RuntimeError(result["error"].get("message", "MCP request failed"))
        return result.get("result")

    async def list_tools(self, base_url: str) -> Any:
        return await self.request(base_url, "tools/list")
