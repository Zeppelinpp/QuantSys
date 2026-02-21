"""LLM client for Agent with support for multiple providers."""

import time
from typing import AsyncIterator, Dict, List, Optional

from loguru import logger

from quantsys.config import Settings


class LLMClient:
    """Client for LLM API supporting Anthropic and OpenAI-compatible providers."""

    def __init__(self, settings: Settings) -> None:
        """Initialize LLM client.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.client = None
        self.total_tokens_used = 0

        # Determine provider
        self.provider = getattr(settings, "LLM_PROVIDER", "anthropic").lower()

        if self.provider == "anthropic":
            self._init_anthropic()
        elif self.provider == "openai":
            self._init_openai()
        else:
            logger.warning(f"Unknown LLM provider: {self.provider}")

    def _init_anthropic(self) -> None:
        """Initialize Anthropic client."""
        try:
            from anthropic import Anthropic

            api_key = getattr(self.settings, "ANTHROPIC_API_KEY", None)
            if api_key:
                self.client = Anthropic(api_key=api_key)
            else:
                logger.warning("ANTHROPIC_API_KEY not set")
        except ImportError:
            logger.warning("anthropic package not installed")

    def _init_openai(self) -> None:
        """Initialize OpenAI-compatible client."""
        try:
            from openai import OpenAI

            api_key = getattr(self.settings, "OPENAI_API_KEY", None)
            base_url = getattr(self.settings, "OPENAI_BASE_URL", None)

            if api_key:
                client_kwargs = {"api_key": api_key}
                if base_url:
                    client_kwargs["base_url"] = base_url
                self.client = OpenAI(**client_kwargs)
            else:
                logger.warning("OPENAI_API_KEY not set")
        except ImportError:
            logger.warning("openai package not installed")

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

        if self.provider == "anthropic":
            return self._chat_anthropic(messages, system, max_tokens, temperature)
        elif self.provider == "openai":
            return self._chat_openai(messages, system, max_tokens, temperature)
        else:
            raise RuntimeError(f"Unknown provider: {self.provider}")

    def _chat_anthropic(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> str:
        """Chat using Anthropic API."""
        model = getattr(self.settings, "ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

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

    def _chat_openai(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> str:
        """Chat using OpenAI-compatible API."""
        model = getattr(self.settings, "OPENAI_MODEL", "gpt-4")

        # Add system message if provided
        full_messages = list(messages)
        if system:
            full_messages.insert(0, {"role": "system", "content": system})

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=full_messages,
                )

                if response.usage:
                    self.total_tokens_used += response.usage.total_tokens

                return response.choices[0].message.content

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

        if self.provider == "anthropic":
            async for chunk in self._stream_anthropic(messages, system, max_tokens, temperature):
                yield chunk
        elif self.provider == "openai":
            async for chunk in self._stream_openai(messages, system, max_tokens, temperature):
                yield chunk
        else:
            raise RuntimeError(f"Unknown provider: {self.provider}")

    async def _stream_anthropic(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> AsyncIterator[str]:
        """Stream using Anthropic API."""
        model = getattr(self.settings, "ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

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

    async def _stream_openai(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> AsyncIterator[str]:
        """Stream using OpenAI-compatible API."""
        model = getattr(self.settings, "OPENAI_MODEL", "gpt-4")

        full_messages = list(messages)
        if system:
            full_messages.insert(0, {"role": "system", "content": system})

        try:
            response = self.client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=full_messages,
                stream=True,
            )
            for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"LLM stream failed: {e}")
            raise

    def get_token_usage(self) -> int:
        """Get total tokens used."""
        return self.total_tokens_used
