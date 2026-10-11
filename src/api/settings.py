"""Environment-backed settings for the secure API surface."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class APISettings:
    """Runtime settings with safe defaults for local development."""

    api_title: str = os.getenv("API_TITLE", "Agriculture RAG API")
    api_version: str = os.getenv("API_VERSION", "3.0.0")
    jwt_secret: str = os.getenv("JWT_SECRET", "")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    auth_mode: str = os.getenv("API_AUTH_MODE", "local")
    oidc_issuer: str = os.getenv("OIDC_ISSUER", "")
    oidc_audience: str = os.getenv("OIDC_AUDIENCE", "")
    access_token_minutes: int = int(os.getenv("JWT_ACCESS_TOKEN_MINUTES", "30"))
    admin_username: str = os.getenv("API_ADMIN_USERNAME", "admin")
    admin_password: str = os.getenv("API_ADMIN_PASSWORD", "")
    admin_password_hash: str = os.getenv("API_ADMIN_PASSWORD_HASH", "")
    require_auth: bool = _bool("API_REQUIRE_AUTH", True)
    allowed_origins: tuple[str, ...] = tuple(
        item.strip() for item in os.getenv("API_ALLOWED_ORIGINS", "").split(",") if item.strip()
    )
    provider: str = os.getenv("RAG_PROVIDER", "local")
    bedrock_region: str = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
    bedrock_model_id: str = os.getenv(
        "BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0"
    )
    bedrock_guardrail_id: str = os.getenv("BEDROCK_GUARDRAIL_ID", "")
    bedrock_guardrail_version: str = os.getenv("BEDROCK_GUARDRAIL_VERSION", "DRAFT")
    web_search_url: str = os.getenv("WEB_SEARCH_URL", "https://html.duckduckgo.com/html/")
    mcp_servers: tuple[str, ...] = tuple(
        item.strip() for item in os.getenv("MCP_SERVER_URLS", "").split(",") if item.strip()
    )
    request_timeout_seconds: float = float(os.getenv("API_REQUEST_TIMEOUT", "20"))
    rate_limit_per_minute: int = int(os.getenv("API_RATE_LIMIT_PER_MINUTE", "60"))
    agent_memory_db: str = os.getenv("AGENT_MEMORY_DB", "data/agent-memory.sqlite3")
    agent_memory_max_entries: int = int(os.getenv("AGENT_MEMORY_MAX_ENTRIES", "20"))
    agent_memory_retention_days: int = int(os.getenv("AGENT_MEMORY_RETENTION_DAYS", "90"))

    def validate(self) -> None:
        """Reject insecure production configuration before serving traffic."""
        if self.require_auth and self.auth_mode == "local" and len(self.jwt_secret) < 32:
            raise ValueError("JWT_SECRET must contain at least 32 characters when auth is enabled")
        if self.require_auth and self.auth_mode == "local" and not (self.admin_password or self.admin_password_hash):
            raise ValueError("API_ADMIN_PASSWORD or API_ADMIN_PASSWORD_HASH is required when auth is enabled")
        if self.require_auth and self.auth_mode == "oidc" and not (self.oidc_issuer and self.oidc_audience):
            raise ValueError("OIDC_ISSUER and OIDC_AUDIENCE are required for OIDC authentication")
        if self.auth_mode not in {"local", "oidc"}:
            raise ValueError("API_AUTH_MODE must be local or oidc")
        if self.provider == "bedrock" and not self.bedrock_region:
            raise ValueError("AWS_REGION is required for the Bedrock provider")
        if self.agent_memory_max_entries < 1 or self.agent_memory_retention_days < 1:
            raise ValueError("Agent memory limits must be positive")
