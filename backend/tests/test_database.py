from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock, AsyncMock


@pytest.mark.asyncio
async def test_create_project_row():
    mock_conn = AsyncMock()
    mock_cursor = AsyncMock()
    mock_cursor.lastrowid = 1
    mock_cursor.fetchone = AsyncMock(return_value={
        "id": 1, "name": "test", "language": "zh",
    })
    mock_conn.execute = AsyncMock(return_value=mock_cursor)
    mock_conn.__aenter__.return_value = mock_conn

    with patch("backend.db._get_connection", return_value=mock_conn):
        from backend.db import create_project_row
        result = await create_project_row("test", "zh")
        assert result["id"] == 1
        assert result["name"] == "test"


@pytest.mark.asyncio
async def test_list_projects_empty():
    mock_conn = AsyncMock()
    mock_cursor = AsyncMock()
    mock_cursor.fetchall = AsyncMock(return_value=[])
    mock_conn.execute = AsyncMock(return_value=mock_cursor)
    mock_conn.__aenter__.return_value = mock_conn

    with patch("backend.db._get_connection", return_value=mock_conn):
        from backend.db import list_project_rows
        result = await list_project_rows()
        assert result == []


@pytest.mark.asyncio
async def test_list_projects_returns_rows():
    mock_conn = AsyncMock()
    mock_cursor = AsyncMock()
    mock_cursor.fetchall = AsyncMock(return_value=[
        {"id": 1, "name": "p1", "language": "zh"},
    ])
    mock_conn.execute = AsyncMock(return_value=mock_cursor)
    mock_conn.__aenter__.return_value = mock_conn

    with patch("backend.db._get_connection", return_value=mock_conn):
        from backend.db import list_project_rows
        result = await list_project_rows()
        assert len(result) == 1
        assert result[0]["name"] == "p1"
