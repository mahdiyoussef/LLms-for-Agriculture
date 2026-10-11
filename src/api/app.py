"""Secure FastAPI application for the agriculture RAG platform."""

from __future__ import annotations

from collections import defaultdict, deque
import logging
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
import httpx
from fastapi.middleware.cors import CORSMiddleware

from .auth import build_current_user, issue_token, verify_password
from src.agents.agriculture import AgentRequest, build_default_registry
from .guardrails import redact_secrets, validate_question
from .mcp import MCPClient
from .models import (
    AgentInfo,
    AgentRunRequest,
    AgentRunResponse,
    QueryRequest,
    QueryResponse,
    SearchRequest,
    TokenRequest,
    TokenResponse,
)
from .providers import BedrockProvider, LocalProvider
from .settings import APISettings
from .web_search import WebSearchAgent


def create_app(settings: APISettings | None = None, validate_settings: bool = True) -> FastAPI:
    """Create a configured API instance; dependency injection keeps tests isolated."""
    settings = settings or APISettings()
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if validate_settings:
            settings.validate()
        yield

    app = FastAPI(title=settings.api_title, version=settings.api_version, lifespan=lifespan)
    agent_registry = build_default_registry()
    audit_logger = logging.getLogger("agriculture_rag.audit")
    request_windows: dict[str, deque[float]] = defaultdict(deque)

    @app.middleware("http")
    async def request_controls(request, call_next):
        client = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window = request_windows[client]
        while window and now - window[0] >= 60:
            window.popleft()
        if len(window) >= settings.rate_limit_per_minute:
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
        window.append(now)
        response = await call_next(request)
        audit_logger.info("%s %s %s", request.method, request.url.path, response.status_code)
        return response
    if settings.allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.allowed_origins),
            allow_credentials=True,
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type"],
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "provider": settings.provider}

    @app.post("/auth/token", response_model=TokenResponse)
    async def token(request: TokenRequest) -> TokenResponse:
        if settings.auth_mode != "local":
            raise HTTPException(status_code=404, detail="Local token issuance is disabled")
        configured = settings.admin_password_hash
        valid_password = (
            verify_password(request.password, configured)
            if configured
            else request.password == settings.admin_password
        )
        if request.username != settings.admin_username or not valid_password:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return TokenResponse(
            access_token=issue_token(request.username, "admin", settings),
            expires_in=settings.access_token_minutes * 60,
        )

    bearer_dependency = Depends(build_current_user(settings))

    @app.get("/agents", response_model=list[AgentInfo])
    async def agents(user: dict = bearer_dependency) -> list[AgentInfo]:
        return [AgentInfo(name=name) for name in agent_registry.names()]

    @app.post("/agents/{agent_name}/run", response_model=AgentRunResponse)
    async def run_agent(
        agent_name: str,
        request: AgentRunRequest,
        user: dict = bearer_dependency,
    ) -> AgentRunResponse:
        question = validate_question(request.question)
        try:
            result = agent_registry.run(
                agent_name,
                AgentRequest(
                    user_id=str(user.get("sub", "authenticated-user")),
                    farm_id=request.farm_id,
                    question=question,
                    context=request.context,
                ),
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return AgentRunResponse(**result.to_dict())

    @app.post("/query", response_model=QueryResponse)
    async def query(request: QueryRequest, user: dict = bearer_dependency) -> QueryResponse:
        question = validate_question(request.question)
        if request.use_agent or request.agent_name:
            agent_name = request.agent_name or "farm-copilot"
            try:
                result = agent_registry.run(
                    agent_name,
                    AgentRequest(
                        user_id=str(user.get("sub", "authenticated-user")),
                        farm_id="default",
                        question=question,
                        context={},
                    ),
                )
            except KeyError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            return QueryResponse(
                answer=redact_secrets(result.answer),
                provider="agriculture-agent",
                model=result.agent_name,
                sources=[item.source for item in result.evidence],
            )
        if settings.provider == "bedrock":
            provider = BedrockProvider(
                settings.bedrock_region,
                settings.bedrock_model_id,
                settings.request_timeout_seconds,
                settings.bedrock_guardrail_id,
                settings.bedrock_guardrail_version,
            )
            result = provider.generate(question)
        else:
            try:
                from src.main import PrecisionAgricultureRAG
                result = LocalProvider(PrecisionAgricultureRAG()).generate(question)
            except Exception as exc:
                raise HTTPException(status_code=503, detail="Local RAG provider unavailable") from exc
        return QueryResponse(answer=redact_secrets(result.answer), provider=result.provider, model=result.model)

    @app.post("/web/search")
    async def web_search(request: SearchRequest, user: dict = bearer_dependency) -> dict:
        agent = WebSearchAgent(settings.web_search_url, settings.request_timeout_seconds)
        try:
            return {"results": await agent.search(request.query, request.limit)}
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(status_code=502, detail="Web search failed") from exc

    @app.get("/mcp/{server_index}/tools")
    async def mcp_tools(server_index: int, user: dict = bearer_dependency) -> dict:
        if server_index < 0 or server_index >= len(settings.mcp_servers):
            raise HTTPException(status_code=404, detail="MCP server is not configured")
        client = MCPClient(settings.mcp_servers, settings.request_timeout_seconds)
        try:
            return {"tools": await client.list_tools(settings.mcp_servers[server_index])}
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=502, detail="MCP request failed") from exc

    return app


app = create_app(APISettings())
