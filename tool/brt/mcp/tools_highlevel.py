"""
高レベルステップツール — Overlay / Wijmo / ネットワーク待機

MCP サーバーに登録する高レベルステップツールを定義する。
既存の steps/ ハンドラと同等の操作を MCP ツールとして提供し、
操作を brt YAML DSL として自動記録する。

主なツール:
  - brt_select_overlay: オーバーレイドロップダウンの選択
  - brt_select_wijmo_combo: Wijmo ComboBox の選択
  - brt_click_wijmo_grid_cell: Wijmo FlexGrid セルのクリック
  - brt_wait_for_network_idle: ネットワークアイドル待機

要件 6.1: selectOverlayOption ステップの MCP ツール化
要件 6.3: selectWijmoCombo ステップの MCP ツール化
要件 6.4: clickWijmoGridCell ステップの MCP ツール化
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastmcp import FastMCP

from .locator_builder import build_locator
from .selector_mapper import SelectorMapper
from .session import BrowserSession
from .snapshot import SnapshotParser
from .tools_basic import _auto_screenshot

logger = logging.getLogger(__name__)

# 仮想スクロール探索の最大試行回数
_MAX_SCROLL_ATTEMPTS = 50


def register_highlevel_tools(
    mcp: FastMCP,
    session: BrowserSession,
    state: dict[str, Any],
    snapshot_parser: SnapshotParser,
    selector_mapper: SelectorMapper,
) -> None:
    """高レベルステップツールを MCP サーバーに登録する。

    Args:
        mcp: FastMCP サーバーインスタンス
        session: ブラウザセッション
        state: 共有状態辞書（recorder 等）
        snapshot_parser: スナップショットパーサー
        selector_mapper: セレクタマッパー
    """

    @mcp.tool
    async def brt_select_overlay(
        element: str,
        open_ref: str,
        list_selector: str,
        option_text: str,
    ) -> str:
        """Select an option from an overlay dropdown (Angular Material, Wijmo, etc.).

        Opens the trigger element, waits for the list to appear,
        then clicks the matching option.

        Args:
            element: Description of the overlay component
            open_ref: Reference number of the trigger element from brt_snapshot
            list_selector: CSS selector for the dropdown list container
            option_text: Text of the option to select

        Returns:
            Status message
        """
        page = session.page
        if page is None:
            return "Error: Browser not launched. Call brt_launch first."

        elem = snapshot_parser.get_by_ref(open_ref)
        if elem is None:
            return f"Error: Element ref [{open_ref}] not found. Call brt_snapshot first."

        # 1. トリガー要素をクリック
        open_by = selector_mapper.to_by_selector(elem)
        open_locator = build_locator(page, open_by)
        await _auto_screenshot(session, state, "selectOverlayOption")
        await open_locator.click()

        # 2. リスト要素の可視化を待機
        list_locator = page.locator(list_selector)
        await list_locator.wait_for(state="visible")

        # 3. optionText に一致する候補を選択
        option_locator = list_locator.get_by_text(option_text, exact=True)
        await option_locator.click()

        # 記録
        rec = state["recorder"]
        if rec is not None:
            rec.add_step("selectOverlayOption", {
                "open": open_by,
                "list": {"css": list_selector},
                "optionText": option_text,
            })

        return f"Selected \"{option_text}\" from overlay [{open_ref}]"

    @mcp.tool
    async def brt_select_wijmo_combo(
        element: str,
        root_ref: str,
        option_text: str,
    ) -> str:
        """Select an option from a Wijmo ComboBox.

        Clicks the combo input, waits for the dropdown, then selects the option.

        Args:
            element: Description of the Wijmo ComboBox
            root_ref: Reference number of the combo root element from brt_snapshot
            option_text: Text of the option to select

        Returns:
            Status message
        """
        page = session.page
        if page is None:
            return "Error: Browser not launched. Call brt_launch first."

        elem = snapshot_parser.get_by_ref(root_ref)
        if elem is None:
            return f"Error: Element ref [{root_ref}] not found. Call brt_snapshot first."

        root_by = selector_mapper.to_by_selector(elem)
        root_locator = build_locator(page, root_by)

        # Wijmo ComboBox の入力フィールドをクリック
        await _auto_screenshot(session, state, "selectWijmoCombo")
        input_locator = root_locator.locator(
            "input.wj-form-control, input[wj-part='input']"
        ).first
        await input_locator.click()

        # ドロップダウンリストの可視化を待機
        dropdown = page.locator(".wj-listbox.wj-content:visible")
        await dropdown.wait_for(state="visible")

        # optionText に一致する候補をクリック
        option = dropdown.get_by_text(option_text, exact=True)
        await option.click()

        # 記録
        rec = state["recorder"]
        if rec is not None:
            rec.add_step("selectWijmoCombo", {
                "root": root_by,
                "optionText": option_text,
            })

        return f"Selected \"{option_text}\" from Wijmo ComboBox [{root_ref}]"

    @mcp.tool
    async def brt_click_wijmo_grid_cell(
        element: str,
        grid_ref: str,
        row_column: str,
        row_value: str,
        target_column: str,
    ) -> str:
        """Click a specific cell in a Wijmo FlexGrid.

        Finds the row by matching a column value, then clicks the target column cell.
        Supports virtual scrolling.

        Args:
            element: Description of the grid
            grid_ref: Reference number of the grid element from brt_snapshot
            row_column: Column name to identify the row
            row_value: Value to match in the row column
            target_column: Column name of the cell to click

        Returns:
            Status message
        """
        page = session.page
        if page is None:
            return "Error: Browser not launched. Call brt_launch first."

        elem = snapshot_parser.get_by_ref(grid_ref)
        if elem is None:
            return f"Error: Element ref [{grid_ref}] not found. Call brt_snapshot first."

        grid_by = selector_mapper.to_by_selector(elem)
        grid_locator = build_locator(page, grid_by)

        # スクリーンショットを自動保存
        await _auto_screenshot(session, state, "clickWijmoGridCell")

        # ヘッダーから列インデックスを取得
        headers = grid_locator.locator(
            ".wj-header .wj-row:first-child .wj-cell"
        )
        header_count = await headers.count()

        key_col_idx = -1
        target_col_idx = -1
        for i in range(header_count):
            text = await headers.nth(i).text_content()
            if text and text.strip() == row_column:
                key_col_idx = i
            if text and text.strip() == target_column:
                target_col_idx = i

        if key_col_idx < 0:
            return f"Error: Column '{row_column}' not found in grid headers."
        if target_col_idx < 0:
            return f"Error: Column '{target_column}' not found in grid headers."

        # 行を探索（仮想スクロール対応）
        body = grid_locator.locator(".wj-cells")
        for _attempt in range(_MAX_SCROLL_ATTEMPTS):
            rows = body.locator(".wj-row")
            row_count = await rows.count()
            for row_idx in range(row_count):
                row = rows.nth(row_idx)
                cells = row.locator(".wj-cell")
                cell_count = await cells.count()
                if key_col_idx < cell_count:
                    cell_text = await cells.nth(key_col_idx).text_content()
                    if cell_text and cell_text.strip() == row_value:
                        if target_col_idx < cell_count:
                            await cells.nth(target_col_idx).click()

                            # 記録
                            rec = state["recorder"]
                            if rec is not None:
                                rec.add_step("clickWijmoGridCell", {
                                    "grid": grid_by,
                                    "rowKey": {
                                        "column": row_column,
                                        "equals": row_value,
                                    },
                                    "column": target_column,
                                })

                            return (
                                f"Clicked cell [{row_column}={row_value}]"
                                f" column '{target_column}'"
                            )

            # スクロールして再探索
            await body.evaluate("el => el.scrollTop += el.clientHeight")

        return (
            f"Error: Row with {row_column}='{row_value}' not found "
            f"after {_MAX_SCROLL_ATTEMPTS} scroll attempts."
        )

    @mcp.tool
    async def brt_wait_for_network_idle() -> str:
        """Wait for all network requests to complete.

        Returns:
            Status message
        """
        page = session.page
        if page is None:
            return "Error: Browser not launched. Call brt_launch first."

        await page.wait_for_load_state("networkidle")

        # 記録
        rec = state["recorder"]
        if rec is not None:
            rec.add_step("waitForNetworkIdle", {})

        return "Network is idle"
