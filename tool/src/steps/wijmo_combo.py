"""
Wijmo ComboBox ステップハンドラ — selectWijmoCombo

Wijmo ComboBox の候補選択を1ステップで実行する。
root でコンポーネント境界を指定し、optionText で候補を選択。

要件 6.3: selectWijmoCombo ステップの提供
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

class SelectWijmoComboParams(BaseModel):
    """selectWijmoCombo ステップのパラメータ。"""

    root: dict
    optionText: str
    name: str | None = None


# ---------------------------------------------------------------------------
# ハンドラ
# ---------------------------------------------------------------------------

class SelectWijmoComboHandler:
    """selectWijmoCombo — Wijmo ComboBox の候補選択を1ステップで実行。

    実行フロー:
      1. root セレクタでコンポーネント境界を特定
      2. コンボボックスの入力フィールドをクリックしてドロップダウンを開く
      3. ドロップダウンリストの可視化を待機
      4. optionText に一致する候補をクリック
    """

    async def execute(self, page: Page, params: dict, context: StepContext) -> None:
        root_by = params["root"]
        option_text = params["optionText"]

        logger.info(
            "selectWijmoCombo: root=%s, optionText='%s'",
            root_by, option_text,
        )

        # 1. コンポーネント境界を特定
        root_locator = await _resolve_selector(page, root_by, context)

        # 2. Wijmo ComboBox の入力フィールドをクリック
        # Wijmo ComboBox は .wj-input-group 内に input 要素を持つ
        input_locator = root_locator.locator("input.wj-form-control, input[wj-part='input']").first
        await input_locator.click()

        # 3. ドロップダウンリストの可視化を待機
        # Wijmo ComboBox のドロップダウンは .wj-listbox クラスを持つ
        dropdown = page.locator(".wj-listbox.wj-content:visible")
        await dropdown.wait_for(state="visible")

        # 4. optionText に一致する候補をクリック
        option = dropdown.get_by_text(option_text, exact=True)
        await option.click()

        logger.info("selectWijmoCombo: '%s' を選択しました", option_text)

    def get_schema(self) -> type[BaseModel]:
        return SelectWijmoComboParams


# ---------------------------------------------------------------------------
# レジストリ登録用情報
# ---------------------------------------------------------------------------

WIJMO_COMBO_STEP_INFO = StepInfo(
    name="selectWijmoCombo",
    description="Wijmo ComboBox の候補選択を1ステップで実行",
    category="high-level",
)
