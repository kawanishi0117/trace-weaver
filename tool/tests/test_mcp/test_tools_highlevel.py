"""
高レベルステップツール テスト — MCP サーバーの高レベルステップツール

selectOverlayOption, selectWijmoCombo, clickWijmoGridCell の
MCP ツール登録と記録動作を検証する。
"""

from __future__ import annotations

import pytest

from brt.mcp.server import create_server


# ---------------------------------------------------------------------------
# ツール登録テスト
# ---------------------------------------------------------------------------

class TestHighLevelToolRegistration:
    """高レベルステップツールがサーバーに登録されていることを確認する。"""

    @pytest.fixture
    def server(self):
        return create_server()

    @pytest.mark.asyncio
    async def test_has_select_overlay_tool(self, server):
        """brt_select_overlay ツールが登録されていること。"""
        tools = await server.list_tools()
        tool_names = [t.name for t in tools]
        assert "brt_select_overlay" in tool_names

    @pytest.mark.asyncio
    async def test_has_select_wijmo_combo_tool(self, server):
        """brt_select_wijmo_combo ツールが登録されていること。"""
        tools = await server.list_tools()
        tool_names = [t.name for t in tools]
        assert "brt_select_wijmo_combo" in tool_names

    @pytest.mark.asyncio
    async def test_has_click_wijmo_grid_cell_tool(self, server):
        """brt_click_wijmo_grid_cell ツールが登録されていること。"""
        tools = await server.list_tools()
        tool_names = [t.name for t in tools]
        assert "brt_click_wijmo_grid_cell" in tool_names

    @pytest.mark.asyncio
    async def test_has_wait_for_network_idle_tool(self, server):
        """brt_wait_for_network_idle ツールが登録されていること。"""
        tools = await server.list_tools()
        tool_names = [t.name for t in tools]
        assert "brt_wait_for_network_idle" in tool_names

    @pytest.mark.asyncio
    async def test_total_tool_count_with_highlevel(self, server):
        """高レベルツール追加後のツール総数が正しいこと。"""
        tools = await server.list_tools()
        # 14 基本 + 4 高レベル = 18
        assert len(tools) == 18


# ---------------------------------------------------------------------------
# 高レベルステップの記録テスト
# ---------------------------------------------------------------------------

class TestHighLevelRecording:
    """高レベルステップが正しく YAML DSL に記録されることを確認する。"""

    def test_select_overlay_recording(self):
        """selectOverlayOption が正しく記録されること。"""
        from brt.mcp.recorder import Recorder

        rec = Recorder(title="Test", base_url="https://example.com")
        rec.add_step("selectOverlayOption", {
            "open": {"testId": "status-combo"},
            "list": {"css": ".wj-listbox"},
            "optionText": "Active",
        })

        scenario = rec.to_scenario_dict()
        step = scenario["steps"][0]
        assert "selectOverlayOption" in step
        assert step["selectOverlayOption"]["optionText"] == "Active"

    def test_select_wijmo_combo_recording(self):
        """selectWijmoCombo が正しく記録されること。"""
        from brt.mcp.recorder import Recorder

        rec = Recorder(title="Test", base_url="https://example.com")
        rec.add_step("selectWijmoCombo", {
            "root": {"testId": "status-combo"},
            "optionText": "Active",
        })

        scenario = rec.to_scenario_dict()
        step = scenario["steps"][0]
        assert "selectWijmoCombo" in step
        assert step["selectWijmoCombo"]["optionText"] == "Active"

    def test_click_wijmo_grid_cell_recording(self):
        """clickWijmoGridCell が正しく記録されること。"""
        from brt.mcp.recorder import Recorder

        rec = Recorder(title="Test", base_url="https://example.com")
        rec.add_step("clickWijmoGridCell", {
            "grid": {"testId": "orders-grid"},
            "rowKey": {"column": "OrderId", "equals": "12345"},
            "column": "Status",
        })

        scenario = rec.to_scenario_dict()
        step = scenario["steps"][0]
        assert "clickWijmoGridCell" in step
        assert step["clickWijmoGridCell"]["column"] == "Status"
