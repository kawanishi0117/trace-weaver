"""
SelectorMapper — ref 番号から brt セレクタへの変換

SnapshotElement の role/name/属性情報から、
brt DSL の by セレクタ辞書を生成する。

主な機能:
  - SnapshotElement → by セレクタ辞書変換
  - secret フィールドの自動判定
"""

from __future__ import annotations

import logging
import re
from typing import Any

from .snapshot import SnapshotElement

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# secret 判定用キーワード
# ---------------------------------------------------------------------------

_SECRET_KEYWORDS = re.compile(
    r"password|passwd|secret|token|api.?key|credential",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# role セレクタとして使用可能なロール一覧
# ---------------------------------------------------------------------------

_ROLE_SELECTOR_ROLES = frozenset({
    "button", "link", "textbox", "checkbox", "radio",
    "combobox", "listbox", "menuitem", "option", "searchbox",
    "slider", "spinbutton", "switch", "tab", "treeitem",
    "heading", "img", "cell", "row", "columnheader",
})


# ---------------------------------------------------------------------------
# SelectorMapper 本体
# ---------------------------------------------------------------------------

class SelectorMapper:
    """SnapshotElement から brt DSL の by セレクタ辞書を生成する。"""

    def to_by_selector(self, element: SnapshotElement) -> dict[str, Any]:
        """SnapshotElement を brt DSL の by セレクタ辞書に変換する。

        変換ルール:
          - role が _ROLE_SELECTOR_ROLES に含まれる場合は role セレクタ
          - name がある場合は name を付与
          - heading の場合は level 属性は含めない（brt DSL では不要）

        Args:
            element: 変換対象の SnapshotElement

        Returns:
            brt DSL の by セレクタ辞書
        """
        by: dict[str, Any] = {"role": element.role}

        # name がある場合のみ付与
        if element.name:
            by["name"] = element.name

        return by

    def is_secret_field(self, element: SnapshotElement) -> bool:
        """要素がパスワード等の秘密値フィールドかどうかを判定する。

        Args:
            element: 判定対象の SnapshotElement

        Returns:
            秘密値フィールドの場合 True
        """
        # name にパスワード系キーワードが含まれるか
        if element.name and _SECRET_KEYWORDS.search(element.name):
            return True
        return False
