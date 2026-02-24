"""
待機戦略のユニットテスト

Playwright の Page / Locator はモック（unittest.mock）を使用する。
実際のブラウザは起動しない。

テスト対象:
  - wait_for_overlay_visible: オーバーレイ可視化待機
  - wait_for_wijmo_grid_row: Wijmo Grid 仮想スクロール行探索
  - wait_for_network_settle: ネットワーク安定待機
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.waits import (
    wait_for_network_settle,
    wait_for_overlay_visible,
    wait_for_wijmo_grid_row,
)


# ---------------------------------------------------------------------------
# ヘルパー: モックオブジェクト生成
# ---------------------------------------------------------------------------

def _make_mock_page() -> MagicMock:
    """モック Page を生成する。"""
    page = AsyncMock()
    page.wait_for_load_state = AsyncMock()
    return page


def _make_mock_locator(*, visible: bool = False) -> MagicMock:
    """モック Locator を生成する。

    Args:
        visible: is_visible() の戻り値
    """
    locator = AsyncMock()
    locator.is_visible = AsyncMock(return_value=visible)
    return locator


# ===========================================================================
# テスト: wait_for_overlay_visible
# ===========================================================================

class TestWaitForOverlayVisible:
    """wait_for_overlay_visible のテスト（mock ベース）。"""

    async def test_immediately_visible(self) -> None:
        """要素が即座に可視の場合、すぐに返ること。"""
        page = _make_mock_page()
        locator = _make_mock_locator(visible=True)

        # タイムアウトなしで完了すること
        await wait_for_overlay_visible(page, locator, timeout=5000)

        locator.is_visible.assert_called()

    async def test_becomes_visible_after_delay(self) -> None:
        """要素が遅延後に可視になる場合、待機して返ること。"""
        page = _make_mock_page()
        locator = AsyncMock()

        # 最初の2回は False、3回目で True を返す
        call_count = 0

        async def mock_is_visible():
            nonlocal call_count
            call_count += 1
            return call_count >= 3

        locator.is_visible = mock_is_visible

        await wait_for_overlay_visible(page, locator, timeout=5000)

        assert call_count >= 3

    async def test_timeout_raises(self) -> None:
        """タイムアウト時間内に可視にならない場合、TimeoutError が発生すること。"""
        page = _make_mock_page()
        locator = _make_mock_locator(visible=False)

        with pytest.raises(TimeoutError, match="可視になりませんでした"):
            await wait_for_overlay_visible(page, locator, timeout=200)

    async def test_is_visible_exception_handled(self) -> None:
        """is_visible() が例外を投げても、ポーリングが継続すること。"""
        page = _make_mock_page()
        locator = AsyncMock()

        call_count = 0

        async def mock_is_visible():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("一時的なエラー")
            return True

        locator.is_visible = mock_is_visible

        await wait_for_overlay_visible(page, locator, timeout=5000)

        assert call_count >= 2

    async def test_custom_timeout(self) -> None:
        """カスタムタイムアウト値が適用されること。"""
        page = _make_mock_page()
        locator = _make_mock_locator(visible=False)

        # 非常に短いタイムアウトで即座に TimeoutError
        with pytest.raises(TimeoutError):
            await wait_for_overlay_visible(page, locator, timeout=50)


# ===========================================================================
# テスト: wait_for_wijmo_grid_row
# ===========================================================================

class TestWaitForWijmoGridRow:
    """wait_for_wijmo_grid_row のテスト（mock ベース）。"""

    async def test_row_found_immediately(self) -> None:
        """対象行が即座に見つかる場合、その行の Locator を返すこと。"""
        page = _make_mock_page()

        # グリッド内の行モック
        row_mock = AsyncMock()
        row_locator = AsyncMock()
        row_locator.all_text_contents = AsyncMock(return_value=["注文001", "商品A"])

        row_mock.locator = MagicMock(return_value=row_locator)

        rows_mock = AsyncMock()
        rows_mock.count = AsyncMock(return_value=1)
        rows_mock.nth = MagicMock(return_value=row_mock)

        grid_locator = AsyncMock()
        grid_locator.locator = MagicMock(return_value=rows_mock)
        grid_locator.evaluate = AsyncMock()

        result = await wait_for_wijmo_grid_row(
            page, grid_locator, row_key="注文001", column="注文番号", timeout=5000
        )

        assert result == row_mock

    async def test_row_not_found_timeout(self) -> None:
        """対象行が見つからない場合、TimeoutError が発生すること。"""
        page = _make_mock_page()

        # 行が0件のグリッド
        rows_mock = AsyncMock()
        rows_mock.count = AsyncMock(return_value=0)

        grid_locator = AsyncMock()
        grid_locator.locator = MagicMock(return_value=rows_mock)
        grid_locator.evaluate = AsyncMock()

        with pytest.raises(TimeoutError, match="見つかりませんでした"):
            await wait_for_wijmo_grid_row(
                page, grid_locator, row_key="存在しない行",
                column="ID", timeout=300
            )

    async def test_row_found_after_scroll(self) -> None:
        """スクロール後に対象行が見つかる場合。"""
        page = _make_mock_page()

        scroll_count = 0

        # 最初は行が見つからず、スクロール後に見つかる
        row_mock = AsyncMock()
        row_locator = AsyncMock()

        async def mock_all_text_contents():
            nonlocal scroll_count
            if scroll_count < 1:
                return ["別の行"]
            return ["ターゲット行"]

        row_locator.all_text_contents = mock_all_text_contents
        row_mock.locator = MagicMock(return_value=row_locator)

        rows_mock = AsyncMock()
        rows_mock.count = AsyncMock(return_value=1)
        rows_mock.nth = MagicMock(return_value=row_mock)

        grid_locator = AsyncMock()
        grid_locator.locator = MagicMock(return_value=rows_mock)

        async def mock_evaluate(script):
            nonlocal scroll_count
            scroll_count += 1

        grid_locator.evaluate = mock_evaluate

        result = await wait_for_wijmo_grid_row(
            page, grid_locator, row_key="ターゲット行",
            column="名前", timeout=5000
        )

        assert result == row_mock
        assert scroll_count >= 1

    async def test_custom_timeout(self) -> None:
        """カスタムタイムアウト値が適用されること。"""
        page = _make_mock_page()

        rows_mock = AsyncMock()
        rows_mock.count = AsyncMock(return_value=0)

        grid_locator = AsyncMock()
        grid_locator.locator = MagicMock(return_value=rows_mock)
        grid_locator.evaluate = AsyncMock()

        with pytest.raises(TimeoutError):
            await wait_for_wijmo_grid_row(
                page, grid_locator, row_key="missing",
                column="col", timeout=100
            )


# ===========================================================================
# テスト: wait_for_network_settle
# ===========================================================================

class TestWaitForNetworkSettle:
    """wait_for_network_settle のテスト（mock ベース）。"""

    async def test_network_settles_immediately(self) -> None:
        """ネットワークが即座に安定する場合、正常に返ること。"""
        page = _make_mock_page()

        await wait_for_network_settle(page, timeout=5000)

        page.wait_for_load_state.assert_called_once_with(
            "networkidle", timeout=5000
        )

    async def test_network_timeout_raises(self) -> None:
        """ネットワークがタイムアウトした場合、TimeoutError が発生すること。"""
        page = _make_mock_page()
        page.wait_for_load_state = AsyncMock(
            side_effect=Exception("Timeout 5000ms exceeded")
        )

        with pytest.raises(TimeoutError, match="安定しませんでした"):
            await wait_for_network_settle(page, timeout=5000)

    async def test_custom_timeout_passed(self) -> None:
        """カスタムタイムアウト値が Playwright に渡されること。"""
        page = _make_mock_page()

        await wait_for_network_settle(page, timeout=10000)

        page.wait_for_load_state.assert_called_once_with(
            "networkidle", timeout=10000
        )

    async def test_default_timeout(self) -> None:
        """デフォルトタイムアウト（5000ms）が使用されること。"""
        page = _make_mock_page()

        await wait_for_network_settle(page)

        page.wait_for_load_state.assert_called_once_with(
            "networkidle", timeout=5000
        )
