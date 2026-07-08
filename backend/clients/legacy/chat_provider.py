from __future__ import annotations

import os
from typing import Any, Optional
from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel


class ChatProvider:
    _ROUTING: dict[str, Optional[str]] = {
        "agnes": "openai",
        "gpt": "openai",
        "gemini": "google_genai",
        "claude": "anthropic",
    }

    _ENV_KEY_MAP: dict[str, str] = {
        "openai": "OPENAI_API_KEY",
        "google_genai": "GOOGLE_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }

    _OPENAI_COMPATIBLE = {None, "openai"}

    @classmethod
    def create(cls, model: str, api_key: str, base_url: str) -> BaseChatModel:
        model_lower = model.lower()
        model_provider: str | None = None
        for key, provider in cls._ROUTING.items():
            if key in model_lower:
                model_provider = provider
                break

        resolved_key = api_key or os.environ.get(cls._ENV_KEY_MAP.get(model_provider or "", ""), "")

        kwargs: dict[str, Any] = {"model": model}
        if resolved_key:
            kwargs["api_key"] = resolved_key
        if model_provider is not None:
            kwargs["model_provider"] = model_provider
        if model_provider in cls._OPENAI_COMPATIBLE and base_url:
            kwargs["base_url"] = base_url

        return init_chat_model(**kwargs)
