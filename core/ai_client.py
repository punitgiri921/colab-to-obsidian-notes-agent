"""
Azure OpenAI client with robust parameter adaptation and rate-limit retries.

Optimized for Azure OpenAI deployments (e.g. gpt-5-mini, gpt-4o, gpt4-1-mini)
with support for high TPM quota, reasoning effort control, and dynamic error backoff.
"""

import os
import time
from typing import Callable, List, Optional

from dotenv import load_dotenv
from openai import AzureOpenAI, RateLimitError


class AzureAIClient:
    """Client for Azure OpenAI note synthesis and section merging."""

    def __init__(self):
        """
        Initialize the Azure OpenAI client.
        Loads credentials from .env file.
        """
        load_dotenv()

        self.endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.api_key = os.getenv("AZURE_OPENAI_KEY")
        self.deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5-mini")
        self.api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
        self.reasoning_effort = os.getenv("AZURE_OPENAI_REASONING_EFFORT", "high")
        self.max_completion_tokens = int(os.getenv("AZURE_OPENAI_MAX_COMPLETION_TOKENS", "32768"))

        missing = []
        if not self.endpoint:
            missing.append("AZURE_OPENAI_ENDPOINT")
        if not self.api_key:
            missing.append("AZURE_OPENAI_KEY")
        if not self.deployment:
            missing.append("AZURE_OPENAI_DEPLOYMENT")

        if missing:
            raise ValueError(
                f"Missing required Azure OpenAI environment variables: {', '.join(missing)}\n"
                f"Please ensure they are defined in your .env file."
            )

        self.client = AzureOpenAI(
            azure_endpoint=self.endpoint,
            api_key=self.api_key,
            api_version=self.api_version,
        )

    def generate_chat_completion(
        self,
        messages: List[dict],
        max_tokens: Optional[int] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        Execute chat completion with automatic parameter fallback and 429 rate-limit retries.
        """
        tokens = max_tokens or self.max_completion_tokens
        kwargs = {"max_completion_tokens": tokens}
        
        # Include reasoning_effort if defined
        if self.reasoning_effort and self.reasoning_effort.lower() in ("low", "medium", "high"):
            kwargs["reasoning_effort"] = self.reasoning_effort.lower()

        max_retries = 6
        base_delay = 5.0

        for attempt in range(max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.deployment,
                    messages=messages,
                    **kwargs,
                )
                break
            except Exception as e:
                err_msg = str(e).lower()

                # Handle 429 rate limits
                is_rate_limit = (
                    "429" in err_msg
                    or "rate_limit" in err_msg
                    or "too_many_requests" in err_msg
                    or isinstance(e, RateLimitError)
                )

                if is_rate_limit:
                    if attempt < max_retries:
                        wait_seconds = base_delay * (1.5 ** attempt)
                        if hasattr(e, "response") and e.response is not None:
                            headers = getattr(e.response, "headers", {})
                            ra = headers.get("retry-after") or headers.get("retry-after-ms")
                            if ra:
                                try:
                                    ra_val = float(ra)
                                    wait_seconds = ra_val / 1000.0 if ra_val > 500 else ra_val
                                except ValueError:
                                    pass
                        wait_seconds = max(5.0, min(wait_seconds, 45.0))
                        msg = (
                            f"Azure TPM rate limit reached (429) — waiting {int(wait_seconds)}s for quota to refresh "
                            f"(attempt {attempt + 1}/{max_retries})..."
                        )
                        if progress_callback:
                            progress_callback(msg)
                        time.sleep(wait_seconds)
                        continue
                    else:
                        raise RuntimeError(
                            f"Azure OpenAI token rate limit (429) exceeded after {max_retries} retries."
                        ) from e

                # Handle parameter incompatibility
                if "reasoning_effort" in err_msg or "unknown parameter" in err_msg:
                    kwargs.pop("reasoning_effort", None)
                    continue

                if "max_completion_tokens" in err_msg:
                    kwargs.pop("reasoning_effort", None)
                    kwargs.pop("max_completion_tokens", None)
                    kwargs["max_tokens"] = tokens
                    continue

                raise

        if not response.choices:
            raise RuntimeError("Azure OpenAI returned no completion choices.")

        choice = response.choices[0]
        content = choice.message.content or ""

        if not content.strip():
            if choice.finish_reason == "length":
                raise RuntimeError(
                    f"The model '{self.deployment}' exhausted its token budget ({tokens} tokens) "
                    f"during reasoning without generating output. Consider increasing AZURE_OPENAI_MAX_COMPLETION_TOKENS."
                )
            raise RuntimeError("Azure OpenAI returned an empty response.")

        return content.strip()
