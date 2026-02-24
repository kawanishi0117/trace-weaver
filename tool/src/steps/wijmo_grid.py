"""
Wijmo FlexGrid ステップハンドラ — clickWijmoGridCell

Wijmo FlexGrid の特定セルをクリックする。
仮想スクロール対応: 対象行が画面外にある場合はスクロールして探索。

要件 6.4: clickWijmoGridCell ステップの提供
要件 6.5: 仮想スクロール対応（スクロールして対象行を探索）
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pydantic import BaseModel

from .builtin import _resolve_selector
from .registry import StepContext, StepInfo

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = logging.getLogger(__name__)

# 仮想スクロール探索の最大試行回数
_MAX_SCROLL_ATTEMPTS = 50


# ---------------------------------------------------------------------------
# パラメータスキーマ
# ---------------------------------------------------------------------------

class WijmoGridRowKeyParams(BaseModel):
    """行特定条件。"""
    column: str
    equals: str


class ClickWijmoGridCellParams(BaseModel):
    """clickWijmoGridCell ステップのパラメータ。"""

    grid: dict
    rowKey: WijmoGridRowKeyParams
    column: str
    name: str | None = None


# ---------------------------------------------------------------------------
# ハンドラ
# ---------------------------------------------------------------------------

class ClickWijmoGridCellHandler:
    """clickWijmoGridCell — Wijmo FlexGrid の特定セルをクリック。

    実行フロー:
      1. grid セレクタでグリッド要素を特定
      2. rowKey（column + equals）で対象行を探索
      3. 対象行が仮想スクロールにより画面外の場合、スクロールして探索
      4. 対象行の指定列セルをクリック
    """

    async def execute(self, page: Page, params: dict, context: StepContext) -> None:
        grid_by = params["grid"]
        row_key = params["rowKey"]
        target_column = params["column"]
        key_column = row_key["column"] if isinstance(row_key, dict) else row_key.column
        key_value = row_key["equals"] if isinstance(row_key, dict) else row_key.equals

        logger.info(
            "clickWijmoGridCell: grid=%s, rowKey={%s=%s}, column=%s",
            grid_by, key_column, key_value, target_column,
        )

        # 1. グリッド要素を特定
        grid_locator = await _resolve_selector(page, grid_by, context)

        # 2. ヘッダーから列インデックスを取得
        key_col_idx = await self._find_column_index(grid_locator, key_column)
        target_col_idx = await self._find_column_index(grid_locator, target_column)

        # 3. 対象行を探索（仮想スクロール対応）
        cell = await self._find_cell_with_scroll(
            grid_locator, key_col_idx, key_value, target_col_idx,
        )

        # 4. セルをクリック
        await cell.click()
        logger.info(
            "clickWijmoGridCell: {%s=%s} の '%s' 列セルをクリックしました",
            key_column, key_value, target_column,
        )

    async def _find_column_index(self, grid_locator, column_name: str) -> int:
        """ヘッダーから列名に対応するインデックスを取得する。

        Args:
            grid_locator: グリッドの Locator
            column_name: 列名

        Returns:
            列インデックス（0始まり）

        Raises:
            ValueError: 列名が見つからない場合
        """
        headers = grid_locator.locator(".wj-header .wj-row:first-child .wj-cell")
        count = await headers.count()
        for i in range(count):
            text = await headers.nth(i).text_content()
            if text and text.strip() == column_name:
                return i
        raise ValueError(f"列 '{column_name}' がグリッドヘッダーに見つかりません")

    async def _find_cell_with_scroll(
        self,
        grid_locator,
        key_col_idx: int,
        key_value: str,
        target_col_idx: int,
    ):
        """仮想スクロール対応で対象セルを探索する。

        グリッドの表示行を走査し、key_col_idx 列の値が key_value に一致する行の
        target_col_idx 列セルを返す。見つからない場合はスクロールして再探索。

        Args:
            grid_locator: グリッドの Locator
            key_col_idx: キー列のインデックス
            key_value: キー列の一致条件値
            target_col_idx: クリック対象列のインデックス

        Returns:
            対象セルの Locator

        Raises:
            ValueError: 最大試行回数を超えても対象行が見つからない場合
        """
        body = grid_locator.locator(".wj-cells")

        for attempt in range(_MAX_SCROLL_ATTEMPTS):
            rows = body.locator(".wj-row")
            row_count = await rows.count()

            for row_idx in range(row_count):
                row = rows.nth(row_idx)
                cells = row.locator(".wj-cell")
                cell_count = await cells.count()

                if key_col_idx < cell_count:
                    cell_text = await cells.nth(key_col_idx).text_content()
                    if cell_text and cell_text.strip() == key_value:
                        # 対象行を発見 — target_col_idx のセルを返す
                        if target_col_idx < cell_count:
                            return cells.nth(target_col_idx)

            # 対象行が見つからない — スクロールして再探索
            logger.debug(
                "clickWijmoGridCell: 試行 %d/%d — スクロールして再探索",
                attempt + 1, _MAX_SCROLL_ATTEMPTS,
            )
            await body.evaluate("el => el.scrollTop += el.clientHeight")

        raise ValueError(
            f"グリッド内で行 ({key_value}) が見つかりません "
            f"（{_MAX_SCROLL_ATTEMPTS} 回スクロール後）"
        )

    def get_schema(self) -> type[BaseModel]:
        return ClickWijmoGridCellParams


# ---------------------------------------------------------------------------
# レジストリ登録用情報
# ---------------------------------------------------------------------------

WIJMO_GRID_STEP_INFO = StepInfo(
    name="clickWijmoGridCell",
    description="Wijmo FlexGrid の特定セルをクリック（仮想スクロール対応）",
    category="high-level",
)
