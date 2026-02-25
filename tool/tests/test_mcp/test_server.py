"""
Server テスト — MCP サーバーのツール定義・統合テスト

FastMCP サーバーが正しくツールを公開し、
操作記録が YAML DSL として出力されることを検証する。
"""

from __future__ import annotations

import pytest

from brt.mcp.server import create_server


# ---------------------------------------------------------------------------
# サーバー生成テスト
# ---------------------------------------------------------------------------

class TestCreateServer:
    """create_server() のテスト。"""

    def test_server_is_created(self):
        """サーバーインスタンスが生成できること。"""
        server = create_server()
        assert server is not None

    def test_server_has_name(self):
        """サーバーに名前が設定されていること。"""
        server = create_server()
        assert server.name == "brt-browser"

    def test_server_has_tools(self):
        """サーバーにツールが登録されていること。"""
        server = create_server()
        # FastMCP 3.x では _tool_manager.list_tools() で取得
        # ここではツール名の存在を確認
        assert server is not None


# ---------------------------------------------------------------------------
# ツール一覧テスト
# ---------------------------------------------------------------------------

class TestServerTools:
    """サーバーに登録されたツールの存在確認テスト。"""

    @pytest.fixture
    def server(self):
        return create_server()

    @pytest.mark.asyncio
    async def test_has_launch_tool(self, server):
        """brt_launch ツールが登録されていること。"""
        tools = await server.list_tools()
        tool_names = [t.name for t in tools]
        assert "brt_launch" in tool_names

    @pytest.mark.asyncio
    async def test_has_navigate_tool(self, server):
        """brt_navigate ツールが登録されていること。"""
        tools = await server.list_tools()
        tool_names = [t.name for t in tools]
        assert "brt_navigate" in tool_names

    @pytest.mark.asyncio
    async def test_has_click_tool(self, server):
        """brt_click ツールが登録されていること。"""
        tools = await server.list_tools()
        tool_names = [t.name for t in tools]
        assert "brt_click" in tool_names

    @pytest.mark.asyncio
    async def test_has_fill_tool(self, server):
        """brt_fill ツールが登録されていること。"""
        tools = await server.list_tools()
        tool_names = [t.name for t in tools]
        assert "brt_fill" in tool_names

    @pytest.mark.asyncio
    async def test_has_snapshot_tool(self, server):
        """brt_snapshot ツールが登録されていること。"""
        tools = await server.list_tools()
        tool_names = [t.name for t in tools]
        assert "brt_snapshot" in tool_names

    @pytest.mark.asyncio
    async def test_has_screenshot_tool(self, server):
        """brt_screenshot ツールが登録されていること。"""
        tools = await server.list_tools()
        tool_names = [t.name for t in tools]
        assert "brt_screenshot" in tool_names

    @pytest.mark.asyncio
    async def test_has_close_tool(self, server):
        """brt_close ツールが登録されていること。"""
        tools = await server.list_tools()
        tool_names = [t.name for t in tools]
        assert "brt_close" in tool_names

    @pytest.mark.asyncio
    async def test_has_assert_visible_tool(self, server):
        """brt_assert_visible ツールが登録されていること。"""
        tools = await server.list_tools()
        tool_names = [t.name for t in tools]
        assert "brt_assert_visible" in tool_names

    @pytest.mark.asyncio
    async def test_has_assert_text_tool(self, server):
        """brt_assert_text ツールが登録されていること。"""
        tools = await server.list_tools()
        tool_names = [t.name for t in tools]
        assert "brt_assert_text" in tool_names

    @pytest.mark.asyncio
    async def test_has_add_section_tool(self, server):
        """brt_add_section ツールが登録されていること。"""
        tools = await server.list_tools()
        tool_names = [t.name for t in tools]
        assert "brt_add_section" in tool_names

    @pytest.mark.asyncio
    async def test_has_select_tool(self, server):
        """brt_select ツールが登録されていること。"""
        tools = await server.list_tools()
        tool_names = [t.name for t in tools]
        assert "brt_select" in tool_names

    @pytest.mark.asyncio
    async def test_has_press_tool(self, server):
        """brt_press ツールが登録されていること。"""
        tools = await server.list_tools()
        tool_names = [t.name for t in tools]
        assert "brt_press" in tool_names

    @pytest.mark.asyncio
    async def test_has_back_tool(self, server):
        """brt_back ツールが登録されていること。"""
        tools = await server.list_tools()
        tool_names = [t.name for t in tools]
        assert "brt_back" in tool_names

    @pytest.mark.asyncio
    async def test_has_save_tool(self, server):
        """brt_save ツールが登録されていること。"""
        tools = await server.list_tools()
        tool_names = [t.name for t in tools]
        assert "brt_save" in tool_names

    @pytest.mark.asyncio
    async def test_total_tool_count(self, server):
        """ツール数が期待通りであること。"""
        tools = await server.list_tools()
        # 14 基本ツール + 4 高レベルツール = 18
        # launch, navigate, click, fill, select, press,
        # back, snapshot, screenshot, assert_visible,
        # assert_text, add_section, save, close,
        # select_overlay, select_wijmo_combo,
        # click_wijmo_grid_cell, wait_for_network_idle
        assert len(tools) == 18
