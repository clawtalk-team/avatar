"""LLM client factory — selects Bedrock, Anthropic direct, or OpenRouter."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    text: str
    output_tokens: int


class LLMClient:
    """Unified interface for calling Claude across different providers."""

    def __init__(self, provider: str, client: Any, model: str):
        self.provider = provider
        self._client = client
        self.model = model

    def generate(self, system: str, prompt: str, max_tokens: int = 4096) -> LLMResponse:
        if self.provider == "bedrock":
            return self._call_bedrock(system, prompt, max_tokens)
        elif self.provider == "openrouter":
            return self._call_openrouter(system, prompt, max_tokens)
        else:
            return self._call_anthropic(system, prompt, max_tokens)

    def _call_bedrock(self, system: str, prompt: str, max_tokens: int) -> LLMResponse:
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        })
        resp = self._client.invoke_model(modelId=self.model, body=body)
        result = json.loads(resp["body"].read())
        return LLMResponse(
            text=result["content"][0]["text"].strip(),
            output_tokens=result["usage"]["output_tokens"],
        )

    def _call_openrouter(self, system: str, prompt: str, max_tokens: int) -> LLMResponse:
        response = self._client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        return LLMResponse(
            text=response.choices[0].message.content.strip(),
            output_tokens=response.usage.completion_tokens,
        )

    def _call_anthropic(self, system: str, prompt: str, max_tokens: int) -> LLMResponse:
        message = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return LLMResponse(
            text=message.content[0].text.strip(),
            output_tokens=message.usage.output_tokens,
        )


def get_llm_client(model: str = "claude-opus-4-6") -> LLMClient:
    """Create an LLM client using the best available credentials.

    Priority: AWS Bedrock → Anthropic direct → OpenRouter.
    """
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
    bedrock_region = os.environ.get(
        "AWS_BEDROCK_REGION",
        os.environ.get("AWS_DEFAULT_REGION", "ap-southeast-2"),
    )

    # Try Bedrock first (if boto3 available and no direct API key)
    if not anthropic_key:
        try:
            import boto3
            sts = boto3.client("sts", region_name=bedrock_region)
            sts.get_caller_identity()
            bedrock_client = boto3.client("bedrock-runtime", region_name=bedrock_region)

            region_prefix = "au" if bedrock_region.startswith("ap-southeast-2") else "us"
            if "." in model and not model.startswith(("au.", "us.", "global.")):
                bedrock_model = f"{region_prefix}.{model}"
            elif "." not in model:
                bedrock_model = f"{region_prefix}.anthropic.{model}-v1"
            else:
                bedrock_model = model

            log.info("Using Bedrock: %s (%s)", bedrock_model, bedrock_region)
            return LLMClient("bedrock", bedrock_client, bedrock_model)
        except Exception:
            pass

    # Try Anthropic direct
    if anthropic_key:
        import anthropic
        client = anthropic.Anthropic(api_key=anthropic_key)
        log.info("Using Anthropic direct: %s", model)
        return LLMClient("anthropic", client, model)

    # Try OpenRouter
    if openrouter_key:
        try:
            import openai
            client = openai.OpenAI(api_key=openrouter_key, base_url="https://openrouter.ai/api/v1")
            or_model = f"anthropic/{model}" if "/" not in model else model
            log.info("Using OpenRouter: %s", or_model)
            return LLMClient("openrouter", client, or_model)
        except ImportError:
            pass

    raise RuntimeError(
        "No credentials found. Set ANTHROPIC_API_KEY, configure AWS for Bedrock, "
        "or set OPENROUTER_API_KEY (with openai package)."
    )
