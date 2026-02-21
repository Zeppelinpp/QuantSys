"""LLM client for Agent."""

import time
from typing import AsyncIterator, Dict, List, Optional

from anthropic import Anthropic
from loguru import logger

from quantsys.config import Settings


class LLMClient:
    """Client for LLM API (Claude)."""

    def __init__(self, settings: Settings) -> None:
        """Initialize LLM client.

        Args:
            settings: Application settings with ANTHROPIC_API_KEY
        """
        self.settings = settings
        self.client: Optional[Anthropic] = None
        self.total_tokens_used = 0

        if settings.ANTHROPIC_API_KEY:
            self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        else:
            logger.warning("ANTHROPIC_API_KEY not set, LLM features disabled")

    def is_available(self) -> bool:
        """Check if LLM client is available."""
        return self.client is not None

    def chat(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        max_tokens: int = 4000,
        temperature: float = 0.7,
    ) -> str:
        """Send chat request to LLM.

        Args:
            messages: List of message dicts with 'role' and 'content'
            system: System prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Generated text response
        """
        if not self.client:
            raise RuntimeError("LLM client not available")

        model = self.settings.ANTHROPIC_MODEL

        # Retry with exponential backoff
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system or "",
                    messages=messages,
                )

                # Track token usage
                if response.usage:
                    self.total_tokens_used += response.usage.input_tokens
                    self.total_tokens_used += response.usage.output_tokens

                return response.content[0].text

            except Exception as e:
                logger.error(f"LLM request failed (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise

        raise RuntimeError("All retries failed")

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        max_tokens: int = 4000,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Stream chat response from LLM.

        Args:
            messages: List of message dicts
            system: System prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Yields:
            Text chunks as they arrive
        """
        if not self.client:
            raise RuntimeError("LLM client not available")

        model = self.settings.ANTHROPIC_MODEL

        try:
            with self.client.messages.stream(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system or "",
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    yield text

        except Exception as e:
            logger.error(f"LLM stream failed: {e}")
            raise

    def get_token_usage(self) -> int:
        """Get total tokens used."""
        return self.total_tokens_used
