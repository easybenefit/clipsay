from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from langchain_core.language_models.chat_models import BaseChatModel

from backend.clients.legacy.chat_provider import ChatProvider
from backend.clients.base import BaseProvider


def test_chat_provider_create_returns_chat_model():
    with patch("backend.clients.chat_provider.init_chat_model") as mock:
        mock.return_value = MagicMock(spec=BaseChatModel)
        model = ChatProvider.create("gpt-4", "sk-xxx", "https://api.openai.com/v1")
        assert isinstance(model, BaseChatModel)


def test_chat_provider_routes_by_keyword():
    with patch("backend.clients.chat_provider.init_chat_model") as mock:
        mock.return_value = MagicMock(spec=BaseChatModel)
        ChatProvider.create("gpt-4", "sk-xxx", "")
        _, kwargs = mock.call_args
        assert kwargs["model_provider"] == "openai"

        mock.reset_mock()
        ChatProvider.create("gemini-pro", "key", "")
        _, kwargs = mock.call_args
        assert kwargs["model_provider"] == "google_genai"


def test_base_provider_abstract():
    class TestProvider(BaseProvider):
        async def invoke(self, payload):
            return {"ok": True}

    p = TestProvider("test-model", "key", "https://example.com/")
    assert p.model == "test-model"
    assert p.api_key == "key"
    assert not p.base_url.endswith("/")


def test_base_provider_stream_returns_async_gen():
    class TestProvider(BaseProvider):
        async def invoke(self, payload):
            return {"ok": True}

    p = TestProvider("test", "key", "")
    gen = p.stream({})
    assert hasattr(gen, "__aiter__")
