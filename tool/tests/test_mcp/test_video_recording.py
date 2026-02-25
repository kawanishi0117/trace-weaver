"""
動画録画テスト — MCP サーバーの動画録画機能

session.py の record_video_dir 対応と、
server.py の brt_launch/brt_close での動画保存を検証する。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from brt.mcp.config import ServerConfig
from brt.mcp.server import create_server
from brt.mcp.session import BrowserSession, SessionState


# ---------------------------------------------------------------------------
# session.py: record_video_dir パラメータのテスト
# ---------------------------------------------------------------------------

class TestSessionVideoRecording:
    """BrowserSession の動画録画パラメータテスト。"""

    @pytest.mark.asyncio
    async def test_launch_with_video_dir(self):
        """record_video_dir を指定して起動できること。"""
        session = BrowserSession()

        mock_pw = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        mock_pw.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        mock_async_pw_cm = AsyncMock()
        mock_async_pw_cm.start = AsyncMock(return_value=mock_pw)

        with patch(
            "playwright.async_api.async_playwright",
            return_value=mock_async_pw_cm,
        ):
            await session.launch(
                headed=False,
                record_video_dir="/tmp/videos",
            )

        assert session.state == SessionState.ACTIVE

        # new_context に record_video_dir が渡されていること
        call_kwargs = mock_browser.new_context.call_args[1]
        assert call_kwargs["record_video_dir"] == "/tmp/videos"
        assert "record_video_size" in call_kwargs

    @pytest.mark.asyncio
    async def test_launch_without_video_dir(self):
        """record_video_dir=None で録画なしで起動できること。"""
        session = BrowserSession()

        mock_pw = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        mock_pw.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        mock_async_pw_cm = AsyncMock()
        mock_async_pw_cm.start = AsyncMock(return_value=mock_pw)

        with patch(
            "playwright.async_api.async_playwright",
            return_value=mock_async_pw_cm,
        ):
            await session.launch(headed=False)

        # new_context に record_video_dir が渡されていないこと
        call_kwargs = mock_browser.new_context.call_args[1]
        assert "record_video_dir" not in call_kwargs


# ---------------------------------------------------------------------------
# server.py: brt_launch の動画設定テスト
# ---------------------------------------------------------------------------

class TestLaunchVideoConfig:
    """brt_launch の動画設定パラメータテスト。"""

    @pytest.fixture
    def server(self):
        return create_server()

    @pytest.mark.asyncio
    async def test_launch_has_video_mode_param(self, server):
        """brt_launch が video_mode パラメータを受け付けること。"""
        tools = await server.list_tools()
        launch_tool = next(t for t in tools if t.name == "brt_launch")
        props = launch_tool.parameters.get("properties", {})
        assert "video_mode" in props

    @pytest.mark.asyncio
    async def test_launch_has_trace_mode_param(self, server):
        """brt_launch が trace_mode パラメータを受け付けること。"""
        tools = await server.list_tools()
        launch_tool = next(t for t in tools if t.name == "brt_launch")
        props = launch_tool.parameters.get("properties", {})
        assert "trace_mode" in props

    @pytest.mark.asyncio
    async def test_launch_has_screenshot_mode_param(self, server):
        """brt_launch が screenshot_mode パラメータを受け付けること。"""
        tools = await server.list_tools()
        launch_tool = next(t for t in tools if t.name == "brt_launch")
        props = launch_tool.parameters.get("properties", {})
        assert "screenshot_mode" in props


# ---------------------------------------------------------------------------
# server.py: brt_close の has_error パラメータテスト
# ---------------------------------------------------------------------------

class TestCloseErrorFlag:
    """brt_close の has_error パラメータテスト。"""

    @pytest.fixture
    def server(self):
        return create_server()

    @pytest.mark.asyncio
    async def test_close_has_error_param(self, server):
        """brt_close が has_error パラメータを受け付けること。"""
        tools = await server.list_tools()
        close_tool = next(t for t in tools if t.name == "brt_close")
        props = close_tool.parameters.get("properties", {})
        assert "has_error" in props


# ---------------------------------------------------------------------------
# ServerConfig → create_server 統合テスト
# ---------------------------------------------------------------------------

class TestServerWithConfig:
    """ServerConfig を渡してサーバーを生成するテスト。"""

    def test_create_server_with_custom_config(self):
        """カスタム設定でサーバーが生成できること。"""
        config = ServerConfig(
            headed=False,
            video_mode="always",
            artifacts_dir="custom_output",
        )
        server = create_server(config=config)
        assert server is not None
        assert server.name == "brt-browser"

    def test_create_server_with_default_config(self):
        """デフォルト設定でサーバーが生成できること。"""
        server = create_server()
        assert server is not None

    @pytest.mark.asyncio
    async def test_tool_count_unchanged_with_config(self):
        """設定を渡してもツール数が変わらないこと。"""
        config = ServerConfig(headed=False, video_mode="always")
        server = create_server(config=config)
        tools = await server.list_tools()
        assert len(tools) == 18
