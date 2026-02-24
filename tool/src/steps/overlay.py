"""
オーバーレイステップハンドラ — selectOverlayOption

Angular Material / 汎用オーバーレイのドロップダウン操作を1ステップで実行する。
open 要素をクリック → list 要素の可視化待機 → optionText に一致する候補を選択。

要件 6.1: selectOverlayOption ステップの提供
要件 6.2: open → list 可視化待機 → optionText 選択の実行フロー
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


# ---------------------------------------------------------------------------
# パラメータスキーマ
# ---------------------------------------------------------------------------

class SelectOverlayOptionParams(BaseModel):
    """selectOverlayOption ステップのパラメータ。"""

    open: dict
    list: dict
    optionText: str
    name: str | None = None


# ---------------------------------------------------------------------------
# ハンドラ
# ---------------------------------------------------------------------------

class SelectOverlayOptionHandler:
    """selectOverlayOption — オーバーレイの開く→候補表示→選択を1ステップで実行。

    実行フロー:
      1. open セレクタで指定されたトリガー要素をクリック
      2. list セレクタで指定された候補リスト要素の可視化を待機
      3. list 内から optionText に一致する候補を strict に特定してクリック
    """

    async def execute(self, page: Page, params: dict, context: StepContext) -> None:
        open_by = params["open"]
        list_by = params["list"]
        option_text = params["optionText"]

        logger.info(
            "selectOverlayOption: open=%s, list=%s, optionText='%s'",
            open_by, list_by, option_text,
        )

        # 1. トリガー要素をクリックしてオーバーレイを開く
        open_locator = await _resolve_selector(page, open_by, context)
        await open_locator.click()

        # 2. 候補リスト要素の可視化を待機
        list_locator = await _resolve_selector(page, list_by, context)
        await list_locator.wait_for(state="visible")

        # 3. optionText に一致する候補を選択
        option_locator = list_locator.get_by_text(option_text, exact=True)
        await option_locator.click()

        logger.info("selectOverlayOption: '%s' を選択しました", option_text)

    def get_schema(self) -> type[BaseModel]:
        return SelectOverlayOptionParams


# ---------------------------------------------------------------------------
# レジストリ登録用情報
# ---------------------------------------------------------------------------

OVERLAY_STEP_INFO = StepInfo(
    name="selectOverlayOption",
    description="オーバーレイの開く→候補表示→選択を1ステップで実行",
    category="high-level",
)
