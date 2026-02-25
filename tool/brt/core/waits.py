"""
待機戦略 — Playwright auto-wait の補助

Playwright の auto-wait だけでは不十分なケースの待機戦略を提供する。

主な機能:
  - wait_for_overlay_visible: オーバーレイ要素の可視化待機
  - wait_for_wijmo_grid_row: Wijmo Grid 仮想スクロール内の行探索
  - wait_for_network_settle: ネットワーク安定待機

要件 13.1: auto-wait（Playwright 標準の自動待機）
要件 13.2: overlay 可視化待機（Angular Material 等のオーバーレイ）
要件 13.3: Wijmo Grid 仮想スクロール探索ループ
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Locator, Page

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# オーバーレイ可視化待機
# ---------------------------------------------------------------------------

async def wait_for_overlay_visible(
    page: Page, locator: Locator, timeout: int = 5000
) -> None:
    """オーバーレイ要素が可視になるまで待機する。

    Angular Material のオーバーレイパネルなど、DOM に追加されてから
    アニメーション完了後に可視状態になる要素の待機に使用する。

    ポーリング間隔 100ms で locator.is_visible() を確認し、
    タイムアウトまでに可視にならなければ TimeoutError を送出する。

    Args:
        page: Playwright の Page オブジェクト
        locator: 待機対象の Locator
        timeout: タイムアウト（ミリ秒、デフォルト: 5000）

    Raises:
        TimeoutError: タイムアウト時間内に要素が可視にならなかった場合
    """
    start = time.perf_counter()
    deadline_sec = timeout / 1000.0

    while True:
        elapsed = time.perf_counter() - start
        if elapsed >= deadline_sec:
            raise TimeoutError(
                f"オーバーレイ要素が {timeout}ms 以内に可視になりませんでした"
            )

        try:
            if await locator.is_visible():
                logger.debug(
                    "オーバーレイ要素が可視になりました（%.0fms 経過）",
                    elapsed * 1000,
                )
                return
        except Exception as exc:
            logger.debug("is_visible() チェック中にエラー: %s", exc)

        # ポーリング間隔: 100ms
        await asyncio.sleep(0.1)


# ---------------------------------------------------------------------------
# Wijmo Grid 仮想スクロール行探索
# ---------------------------------------------------------------------------

async def wait_for_wijmo_grid_row(
    page: Page,
    grid_locator: Locator,
    row_key: str,
    column: str,
    timeout: int = 10000,
) -> Locator:
    """Wijmo Grid の仮想スクロール内で指定行を探索する。

    Wijmo FlexGrid は仮想スクロールを使用しており、画面外の行は
    DOM に存在しない。対象行が見つかるまでグリッドをスクロールし、
    各スクロール位置で指定列の値が row_key に一致する行を探索する。

    Args:
        page: Playwright の Page オブジェクト
        grid_locator: Wijmo Grid 要素の Locator
        row_key: 探索対象の行キー値
        column: 行キーを検索する列名
        timeout: タイムアウト（ミリ秒、デフォルト: 10000）

    Returns:
        発見された行の Locator

    Raises:
        TimeoutError: タイムアウト時間内に対象行が見つからなかった場合
    """
    start = time.perf_counter()
    deadline_sec = timeout / 1000.0
    scroll_count = 0

    while True:
        elapsed = time.perf_counter() - start
        if elapsed >= deadline_sec:
            raise TimeoutError(
                f"Wijmo Grid 内で行 '{row_key}'（列: {column}）が "
                f"{timeout}ms 以内に見つかりませんでした"
            )

        # 現在表示されている行からターゲットを探索
        # セルのテキスト内容で行を特定する
        cell_selector = f".wj-cell[wj-part='cells']"
        rows = grid_locator.locator(".wj-row")
        row_count = await rows.count()

        for i in range(row_count):
            row = rows.nth(i)
            # 指定列のセルテキストを確認
            try:
                cell_text = await row.locator(
                    f".wj-cell"
                ).all_text_contents()
                # セルテキスト内に row_key が含まれるか確認
                for text in cell_text:
                    if row_key in text.strip():
                        logger.info(
                            "Wijmo Grid 行を発見: '%s'（%d 回スクロール後）",
                            row_key, scroll_count,
                        )
                        return row
            except Exception:
                continue

        # 行が見つからない場合、グリッドをスクロール
        scroll_count += 1
        logger.debug(
            "行 '%s' が見つかりません。スクロール実行（%d 回目）",
            row_key, scroll_count,
        )

        # グリッド内でスクロールダウン
        await grid_locator.evaluate(
            "el => el.scrollTop += el.clientHeight"
        )
        # スクロール後の描画待機
        await asyncio.sleep(0.2)


# ---------------------------------------------------------------------------
# ネットワーク安定待機
# ---------------------------------------------------------------------------

async def wait_for_network_settle(
    page: Page, timeout: int = 5000
) -> None:
    """ネットワークが安定するまで待機する。

    Playwright の waitForLoadState("networkidle") を使用して、
    進行中のネットワークリクエストが全て完了するまで待機する。

    Args:
        page: Playwright の Page オブジェクト
        timeout: タイムアウト（ミリ秒、デフォルト: 5000）

    Raises:
        TimeoutError: タイムアウト時間内にネットワークが安定しなかった場合
    """
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout)
        logger.debug("ネットワークが安定しました")
    except Exception as exc:
        raise TimeoutError(
            f"ネットワークが {timeout}ms 以内に安定しませんでした: {exc}"
        ) from exc
