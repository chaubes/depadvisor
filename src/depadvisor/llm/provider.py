"""
LLM Provider Factory.

This module creates the appropriate LLM client based on the
user's configuration. Supports Ollama (local/remote) and OpenAI (cloud).
"""

import os

from langchain_core.language_models import BaseChatModel

DEFAULT_OLLAMA_URL = "http://localhost:11434"


def create_llm(provider_string: str) -> BaseChatModel:
    """
    Create an LLM instance from a provider string.

    Args:
        provider_string: Format "provider/model", e.g.:
            - "ollama/qwen3:8b"
            - "openai/gpt-4o-mini"

    Returns:
        A LangChain chat model instance
    """
    parts = provider_string.split("/", 1)
    if len(parts) != 2:
        raise ValueError(
            f"Invalid LLM provider string: '{provider_string}'. "
            f"Expected format: 'provider/model' (e.g., 'ollama/qwen3:8b')"
        )

    provider, model = parts

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        base_url = os.environ.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA_URL)
        return ChatOllama(
            model=model,
            base_url=base_url,
            temperature=0.1,
            format="json",
        )
    elif provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            temperature=0.1,
            model_kwargs={"response_format": {"type": "json_object"}},
        )
    else:
        raise ValueError(f"Unsupported LLM provider: '{provider}'")
