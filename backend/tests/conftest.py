from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_chat_provider():
    with patch("backend.clients.chat_provider.init_chat_model") as mock:
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def anyio_backend():
    return "asyncio"
