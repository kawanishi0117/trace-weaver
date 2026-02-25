"""
日付ピッカーステップハンドラ — setDatePicker

UI 日付ピッカーへの日付入力を1ステップで実行する。
入力フィールドをクリアしてから日付文字列を入力する方式。

要件 6.6: setDatePicker ステップの提供
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

class SetDatePickerParams(BaseModel):
    """setDatePicker ステップのパラメータ。"""

    by: dict
    date: str
    format: str | None = None
    name: str | None = None


# ---------------------------------------------------------------------------
# ハンドラ
# ---------------------------------------------------------------------------

class SetDatePickerHandler:
    """setDatePicker — 日付ピッカーへの日付入力を1ステップで実行。

    実行フロー:
      1. by セレクタで日付ピッカーの入力フィールドを特定
      2. 入力フィールドをクリックしてフォーカス
      3. 既存の値をクリア
      4. 日付文字列を入力
      5. Enter キーで確定
    """

    async def execute(self, page: Page, params: dict, context: StepContext) -> None:
        by = params["by"]
        date_str = params["date"]
        date_format = params.get("format")

        logger.info("setDatePicker: by=%s, date='%s', format=%s", by, date_str, date_format)

        # 1. 入力フィールドを特定
        locator = await _resolve_selector(page, by, context)

        # 2. フォーカスしてクリア
        await locator.click()
        await locator.fill("")

        # 3. 日付文字列を入力
        await locator.fill(date_str)

        # 4. Enter キーで確定（日付ピッカーを閉じる）
        await locator.press("Enter")

        logger.info("setDatePicker: '%s' を入力しました", date_str)

    def get_schema(self) -> type[BaseModel]:
        return SetDatePickerParams


# ---------------------------------------------------------------------------
# レジストリ登録用情報
# ---------------------------------------------------------------------------

DATEPICKER_STEP_INFO = StepInfo(
    name="setDatePicker",
    description="日付ピッカーへの日付入力を1ステップで実行",
    category="high-level",
)
