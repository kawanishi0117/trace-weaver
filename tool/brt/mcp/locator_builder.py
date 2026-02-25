"""
LocatorBuilder — by セレクタ辞書から Playwright Locator への変換

MCP ツールが受け取る by セレクタ辞書（role, testId, label, placeholder, css, text）を
Playwright の Locator オブジェクトに変換する。

主な機能:
  - 全セレクタ種別の判定と Locator 構築
  - role + name + exact の組み合わせ対応
  - css + text の補助条件対応

要件 4.1: testId, role(+name), label, placeholder, css, text のセレクタ種別
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# セレクタ種別の判定キー（優先順位順）
# ---------------------------------------------------------------------------

_SELECTOR_KEYS = ("testId", "role", "label", "placeholder", "css", "text")


# ---------------------------------------------------------------------------
# パブリック API
# ---------------------------------------------------------------------------

def build_locator(page: object, by: dict[str, Any]) -> object:
    """by セレクタ辞書から Playwright Locator を構築する。

    セレクタ種別の判定は以下の優先順位で行う:
      1. testId → get_by_test_id
      2. role → get_by_role（name, exact はオプション）
      3. label → get_by_label
      4. placeholder → get_by_placeholder
      5. css → locator（text は has_text として付与）
      6. text → get_by_text

    Args:
        page: Playwright Page オブジェクト
        by: brt DSL の by セレクタ辞書

    Returns:
        Playwright Locator オブジェクト

    Raises:
        ValueError: セレクタ種別を特定できない場合
    """
    # testId セレクタ
    if "testId" in by:
        return page.get_by_test_id(by["testId"])

    # role セレクタ
    if "role" in by:
        kwargs: dict[str, Any] = {}
        if "name" in by:
            kwargs["name"] = by["name"]
        if "exact" in by:
            kwargs["exact"] = by["exact"]
        return page.get_by_role(by["role"], **kwargs)

    # label セレクタ
    if "label" in by:
        return page.get_by_label(by["label"])

    # placeholder セレクタ
    if "placeholder" in by:
        return page.get_by_placeholder(by["placeholder"])

    # css セレクタ（text 補助条件あり）
    if "css" in by:
        if "text" in by:
            return page.locator(by["css"], has_text=by["text"])
        return page.locator(by["css"])

    # text セレクタ
    if "text" in by:
        return page.get_by_text(by["text"])

    # 該当なし
    raise ValueError(
        f"セレクタ種別を特定できません。"
        f"使用可能なキー: {', '.join(_SELECTOR_KEYS)}。"
        f"受け取ったキー: {', '.join(by.keys()) or '(空)'}。"
    )
