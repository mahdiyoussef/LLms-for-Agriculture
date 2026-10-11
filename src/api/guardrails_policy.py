"""Deployment policy for the API guardrails.

The code-level checks are a deterministic baseline. Production deployments
should additionally enable Amazon Bedrock Guardrails for model-side filtering
and keep this policy as the fail-closed request boundary.
"""

GUARDRAIL_POLICY = {
    "prompt_injection": "block",
    "credential_redaction": "block-and-redact",
    "untrusted_tool_urls": "block",
    "max_question_length": 4000,
    "max_search_results": 10,
}
