"""
LLM client wrapper for TheReceipts agents.

Provides unified interface for calling different LLM providers (Anthropic, OpenAI)
with proper error handling and timeouts.
"""

import asyncio
from typing import Dict, Any, Optional
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI
from config import settings


class LLMClientError(Exception):
    """Base exception for LLM client errors."""
    pass


class LLMTimeoutError(LLMClientError):
    """Raised when LLM call exceeds timeout."""
    pass


class LLMProviderError(LLMClientError):
    """Raised when LLM provider returns an error."""
    pass


class LLMClient:
    """
    Unified client for calling LLM providers.

    Supports Anthropic and OpenAI APIs with consistent interface.
    """

    def __init__(self):
        """Initialize LLM clients with API keys from settings."""
        self.anthropic_client = None
        self.openai_client = None

        if settings.ANTHROPIC_API_KEY:
            self.anthropic_client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

        if settings.OPENAI_API_KEY:
            self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def call_anthropic(
        self,
        model_name: str,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: int = 300
    ) -> Dict[str, Any]:
        """
        Call Anthropic API (Claude models).

        Args:
            model_name: Model identifier (e.g., "claude-3-opus-20240229")
            system_prompt: System prompt for the model
            user_message: User message to send
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            timeout: Timeout in seconds

        Returns:
            Dict containing:
                - content: Generated text
                - usage: Token usage stats
                - model: Model used

        Raises:
            LLMClientError: If Anthropic client not configured
            LLMTimeoutError: If call exceeds timeout
            LLMProviderError: If provider returns error
        """
        if not self.anthropic_client:
            raise LLMClientError("Anthropic API key not configured")

        try:
            response = await asyncio.wait_for(
                self.anthropic_client.messages.create(
                    model=model_name,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": user_message}
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens
                ),
                timeout=timeout
            )

            return {
                "content": response.content[0].text,
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
                "model": response.model,
            }

        except asyncio.TimeoutError:
            raise LLMTimeoutError(f"Anthropic call exceeded timeout of {timeout}s")
        except Exception as e:
            raise LLMProviderError(f"Anthropic API error: {str(e)}")

    async def call_openai(
        self,
        model_name: str,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: int = 300
    ) -> Dict[str, Any]:
        """
        Call OpenAI API (GPT models).

        Args:
            model_name: Model identifier (e.g., "gpt-4")
            system_prompt: System prompt for the model
            user_message: User message to send
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            timeout: Timeout in seconds

        Returns:
            Dict containing:
                - content: Generated text
                - usage: Token usage stats
                - model: Model used

        Raises:
            LLMClientError: If OpenAI client not configured
            LLMTimeoutError: If call exceeds timeout
            LLMProviderError: If provider returns error
        """
        if not self.openai_client:
            raise LLMClientError("OpenAI API key not configured")

        try:
            response = await asyncio.wait_for(
                self.openai_client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens
                ),
                timeout=timeout
            )

            return {
                "content": response.choices[0].message.content,
                "usage": {
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens,
                },
                "model": response.model,
            }

        except asyncio.TimeoutError:
            raise LLMTimeoutError(f"OpenAI call exceeded timeout of {timeout}s")
        except Exception as e:
            raise LLMProviderError(f"OpenAI API error: {str(e)}")

    async def call(
        self,
        provider: str,
        model_name: str,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Unified interface for calling any LLM provider.

        Args:
            provider: Provider name ("anthropic" or "openai")
            model_name: Model identifier
            system_prompt: System prompt
            user_message: User message
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            timeout: Timeout in seconds (defaults to PIPELINE_TIMEOUT from settings)

        Returns:
            Dict containing response content, usage, and model

        Raises:
            LLMClientError: If provider not supported or not configured
            LLMTimeoutError: If call exceeds timeout
            LLMProviderError: If provider returns error
        """
        if timeout is None:
            timeout = settings.PIPELINE_TIMEOUT

        provider_lower = provider.lower()

        if provider_lower == "anthropic":
            return await self.call_anthropic(
                model_name=model_name,
                system_prompt=system_prompt,
                user_message=user_message,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout
            )
        elif provider_lower == "openai":
            return await self.call_openai(
                model_name=model_name,
                system_prompt=system_prompt,
                user_message=user_message,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout
            )
        else:
            raise LLMClientError(f"Unsupported provider: {provider}")
