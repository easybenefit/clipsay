from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from langchain_core.language_models.chat_models import BaseChatModel

from backend.clients.base import BaseProvider


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
