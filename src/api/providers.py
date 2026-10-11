"""LLM provider adapters for local Ollama and AWS Bedrock."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Generation:
    """Provider-independent generated answer."""

    answer: str
    model: str
    provider: str


class BedrockProvider:
    """Minimal Bedrock Runtime adapter for Anthropic-compatible models."""

    def __init__(
        self,
        region: str,
        model_id: str,
        timeout: float = 20,
        guardrail_id: str = "",
        guardrail_version: str = "DRAFT",
    ):
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:
            raise RuntimeError("boto3 is required for the Bedrock provider") from exc
        self.model_id = model_id
        self.guardrail_id = guardrail_id
        self.guardrail_version = guardrail_version
        self.client = boto3.client(
            "bedrock-runtime",
            region_name=region,
            config=Config(read_timeout=timeout, retries={"max_attempts": 2}),
        )

    def generate(self, prompt: str, system_prompt: str = "") -> Generation:
        kwargs: dict[str, Any] = {
            "modelId": self.model_id,
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {"maxTokens": 1024, "temperature": 0.2},
        }
        if system_prompt:
            kwargs["system"] = [{"text": system_prompt}]
        if self.guardrail_id:
            kwargs["guardrailConfig"] = {
                "guardrailIdentifier": self.guardrail_id,
                "guardrailVersion": self.guardrail_version,
                "trace": "disabled",
            }
        response = self.client.converse(**kwargs)
        text = "".join(item.get("text", "") for item in response["output"]["message"]["content"])
        return Generation(text, self.model_id, "bedrock")


class LocalProvider:
    """Adapter around the existing RAG pipeline."""

    def __init__(self, rag_system: Any):
        self.rag_system = rag_system

    def generate(self, prompt: str, system_prompt: str = "") -> Generation:
        result = self.rag_system.query(prompt)
        answer = result.get("answer", str(result)) if isinstance(result, dict) else str(result)
        return Generation(answer, "configured-local", "local")
