"""
Mapper — RawAction 中間表現を YAML DSL ステップに変換

PyAstParser が生成した RawAction リストを受け取り、
YAML DSL のステップリスト（dict のリスト）に変換する。

主な機能:
  - action_type → DSL ステップ名のマッピング
  - locator_chain → by セレクタ dict への変換
  - locator 文字列の正規化（css= プレフィックス除去等）

要件 2.2: page.goto(url) → goto ステップ
要件 2.3: page.get_by_role(role, name).click() → click ステップ
要件 2.4: page.get_by_test_id(id).click() → click ステップ
要件 2.5: page.locator(css).fill(value) → fill ステップ
要件 2.6: expect(...) → expect 系ステップ
要件 2.9: locator 文字列の正規化
"""

from __future__ import annotations

import logging
from typing import Optional

from .py_ast_parser import RawAction

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# action_type → DSL ステップ名マッピング
# ---------------------------------------------------------------------------

_ACTION_TYPE_TO_DSL: dict[str, str] = {
    "goto": "goto",
    "click": "click",
    "dblclick": "dblclick",
    "fill": "fill",
    "press": "press",
    "check": "check",
    "uncheck": "uncheck",
    "select_option": "selectOption",
    "expect_visible": "expectVisible",
    "expect_hidden": "expectHidden",
    "expect_text": "expectText",
    "expect_url": "expectUrl",
}


# ---------------------------------------------------------------------------
# locator_chain メソッド名 → by セレクタキーのマッピング
# ---------------------------------------------------------------------------

_LOCATOR_METHOD_TO_KEY: dict[str, str] = {
    "get_by_role": "role",
    "get_by_test_id": "testId",
    "get_by_label": "label",
    "get_by_placeholder": "placeholder",
    "get_by_text": "text",
    "locator": "css",
}


# ---------------------------------------------------------------------------
# locator 正規化
# ---------------------------------------------------------------------------

def normalize_locator(value: str) -> str:
    """locator 文字列を正規化する。

    - ``css=`` プレフィックスがある場合は除去する
    - 正規化は冪等（2回適用しても結果が同じ）

    Args:
        value: 正規化対象の locator 文字列

    Returns:
        正規化済みの locator 文字列
    """
    if value.startswith("css="):
        return value[len("css="):]
    return value


# ---------------------------------------------------------------------------
# locator_chain → by セレクタ dict 変換
# ---------------------------------------------------------------------------

def _build_by_selector(locator_chain: list[str]) -> Optional[dict]:
    """locator_chain を by セレクタ dict に変換する。

    変換ルール:
      - ["get_by_role", "button", "name=Submit"]
        → {"role": "button", "name": "Submit"}
      - ["get_by_test_id", "login-btn"]
        → {"testId": "login-btn"}
      - ["get_by_label", "Email"]
        → {"label": "Email"}
      - ["get_by_placeholder", "Search"]
        → {"placeholder": "Search"}
      - ["get_by_text", "Submit"]
        → {"text": "Submit"}
      - ["locator", "#email"]
        → {"css": "#email"}

    Args:
        locator_chain: PyAstParser が生成したロケータチェーン

    Returns:
        by セレクタ dict。変換できない場合は None。
    """
    if not locator_chain:
        return None

    method = locator_chain[0]
    key = _LOCATOR_METHOD_TO_KEY.get(method)
    if key is None:
        logger.warning("未対応のロケータメソッド: %s", method)
        return None

    by: dict = {}

    if method == "get_by_role":
        # ["get_by_role", "button", "name=Submit", "exact=True"]
        # → {"role": "button", "name": "Submit", "exact": true}
        if len(locator_chain) < 2:
            logger.warning("get_by_role にロール名がありません: %s", locator_chain)
            return None
        by["role"] = locator_chain[1]
        # キーワード引数（name=..., exact=True 等）を処理
        for item in locator_chain[2:]:
            if "=" in item:
                kw_key, kw_value = item.split("=", 1)
                # ブール値の変換
                if kw_value == "True":
                    by[kw_key] = True
                elif kw_value == "False":
                    by[kw_key] = False
                else:
                    by[kw_key] = kw_value
    elif method == "locator":
        # ["locator", "#email"] → {"css": "#email"}（正規化付き）
        if len(locator_chain) < 2:
            logger.warning("locator にセレクタ文字列がありません: %s", locator_chain)
            return None
        by["css"] = normalize_locator(locator_chain[1])
    else:
        # get_by_test_id, get_by_label, get_by_placeholder, get_by_text
        if len(locator_chain) < 2:
            logger.warning("%s に値がありません: %s", method, locator_chain)
            return None
        by[key] = locator_chain[1]

    return by


# ---------------------------------------------------------------------------
# Mapper 本体
# ---------------------------------------------------------------------------

class Mapper:
    """RawAction リストを YAML DSL ステップリストに変換するマッパー。

    PyAstParser が生成した RawAction 中間表現を受け取り、
    YAML DSL で使用する dict 形式のステップリストに変換する。
    """

    def map(self, raw_actions: list[RawAction]) -> list[dict]:
        """RawAction リストを DSL ステップリストに変換する。

        Args:
            raw_actions: PyAstParser が生成した RawAction のリスト

        Returns:
            DSL ステップの dict リスト
        """
        steps: list[dict] = []
        for action in raw_actions:
            step = self._map_single(action)
            if step is not None:
                steps.append(step)
        return steps

    def _map_single(self, action: RawAction) -> Optional[dict]:
        """単一の RawAction を DSL ステップ dict に変換する。

        Args:
            action: 変換対象の RawAction

        Returns:
            DSL ステップ dict。変換できない場合は None。
        """
        dsl_name = _ACTION_TYPE_TO_DSL.get(action.action_type)
        if dsl_name is None:
            logger.warning(
                "行 %d: 未知の action_type: %s",
                action.line_number,
                action.action_type,
            )
            return None

        # goto ステップ — URL のみ
        if dsl_name == "goto":
            return self._map_goto(action)

        # expectUrl ステップ — URL のみ（ロケータなし）
        if dsl_name == "expectUrl":
            return self._map_expect_url(action)

        # ロケータ付きステップ
        return self._map_locator_step(dsl_name, action)

    # -------------------------------------------------------------------
    # 個別マッピング
    # -------------------------------------------------------------------

    def _map_goto(self, action: RawAction) -> dict:
        """goto アクションを DSL ステップに変換する。

        Args:
            action: goto の RawAction

        Returns:
            {"goto": {"url": "..."}}
        """
        body: dict = {}
        url = action.args.get("url")
        if url is not None:
            body["url"] = url
        return {"goto": body}

    def _map_expect_url(self, action: RawAction) -> dict:
        """expectUrl アクションを DSL ステップに変換する。

        Args:
            action: expect_url の RawAction

        Returns:
            {"expectUrl": {"url": "..."}}
        """
        body: dict = {}
        url = action.args.get("url")
        if url is not None:
            body["url"] = url
        return {"expectUrl": body}

    def _map_locator_step(self, dsl_name: str, action: RawAction) -> Optional[dict]:
        """ロケータ付きアクションを DSL ステップに変換する。

        Args:
            dsl_name: DSL ステップ名
            action: 変換対象の RawAction

        Returns:
            DSL ステップ dict。ロケータ変換に失敗した場合は None。
        """
        by = _build_by_selector(action.locator_chain)
        if by is None:
            logger.warning(
                "行 %d: ロケータチェーンを変換できません: %s",
                action.line_number,
                action.locator_chain,
            )
            return None

        body: dict = {"by": by}

        # iframe 内操作の場合、frame フィールドを追加
        if action.frame_locator is not None:
            body["frame"] = action.frame_locator

        # アクション固有の引数を追加
        if dsl_name == "fill":
            value = action.args.get("value")
            if value is not None:
                body["value"] = value

        elif dsl_name == "press":
            key = action.args.get("key")
            if key is not None:
                body["key"] = key

        elif dsl_name == "selectOption":
            value = action.args.get("value")
            if value is not None:
                body["value"] = value

        elif dsl_name == "expectText":
            text = action.args.get("text")
            if text is not None:
                body["text"] = text

        return {dsl_name: body}
