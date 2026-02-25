"""
PyAstParser — Playwright codegen 出力の Python AST 解析

Playwright codegen が生成する Python スクリプトを AST 解析し、
RawAction 中間表現リストに変換する。

主な機能:
  - page.goto(url) パターンの認識
  - page.get_by_role(role, name).click() パターンの認識
  - page.get_by_test_id(id).click() パターンの認識
  - page.locator(css).fill(value) パターンの認識
  - expect(...) パターンの認識
  - 未対応パターンの警告出力とコメント保持

要件 2.1: Python AST を解析し、RawAction 中間表現リストを生成
要件 2.2: page.goto(url) パターンの認識
要件 2.3: page.get_by_role(role, name).click() パターンの認識
要件 2.4: page.get_by_test_id(id).click() パターンの認識
要件 2.5: page.locator(css).fill(value) パターンの認識
要件 2.6: expect(...) パターンの認識
"""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# RawAction データクラス
# ---------------------------------------------------------------------------

@dataclass
class RawAction:
    """Python AST から抽出された操作の中間表現。

    Attributes:
        action_type: 操作種別（"goto", "click", "fill", "expect_visible" 等）
        locator_chain: ロケータチェーン（例: ["get_by_role", "button", "name=Submit"]）
        args: 操作引数（例: {"url": "...", "value": "..."}）
        line_number: 元の Python スクリプトの行番号
        frame_locator: iframe 内操作の場合、iframe のセレクタ文字列（例: "iframe"）
    """

    action_type: str
    locator_chain: list[str] = field(default_factory=list)
    args: dict = field(default_factory=dict)
    line_number: int = 0
    frame_locator: Optional[str] = None


# ---------------------------------------------------------------------------
# ロケータメソッド名の定義
# ---------------------------------------------------------------------------

# Playwright のロケータ生成メソッド
_LOCATOR_METHODS = frozenset({
    "get_by_role",
    "get_by_test_id",
    "get_by_label",
    "get_by_placeholder",
    "get_by_text",
    "locator",
    "nth",
    "filter",
    "first",
    "last",
})

# Playwright のアクションメソッド
_ACTION_METHODS = frozenset({
    "click",
    "dblclick",
    "fill",
    "press",
    "check",
    "uncheck",
    "select_option",
    "scroll_into_view_if_needed",
})

# expect のアサーションメソッド
_EXPECT_METHODS = frozenset({
    "to_be_visible",
    "to_be_hidden",
    "to_have_text",
    "to_have_url",
    "to_contain_text",
})


# ---------------------------------------------------------------------------
# PyAstParser 本体
# ---------------------------------------------------------------------------

class PyAstParser:
    """Playwright codegen 出力の Python AST を解析するパーサー。

    Python ソースコードを AST に変換し、Playwright の操作パターンを
    認識して RawAction 中間表現リストを生成する。
    """

    _current_frame_locator: Optional[str] = None

    def parse(self, source: str) -> list[RawAction]:
        """Python ソースコードを解析し、RawAction リストを返す。

        Args:
            source: Playwright codegen が生成した Python ソースコード

        Returns:
            抽出された RawAction のリスト

        Raises:
            SyntaxError: Python ソースコードの構文エラー
        """
        if not source.strip():
            return []

        # AST にパース（構文エラーはそのまま伝播）
        tree = ast.parse(source)

        actions: list[RawAction] = []

        for node in ast.walk(tree):
            # 式文（Expression Statement）のみを対象
            if not isinstance(node, ast.Expr):
                continue

            expr = node.value

            # expect(...) パターンの処理
            if isinstance(expr, ast.Call) and self._is_expect_call(expr):
                action = self._parse_expect(expr)
                if action is not None:
                    actions.append(action)
                continue

            # page.xxx() パターンの処理
            if isinstance(expr, ast.Call):
                action = self._parse_page_call(expr)
                if action is not None:
                    actions.append(action)
                    continue

                # 未対応パターンの警告
                self._warn_unsupported(expr)

        return actions

    # -------------------------------------------------------------------
    # expect パターンの判定と解析
    # -------------------------------------------------------------------

    def _is_expect_call(self, node: ast.expr) -> bool:
        """ノードが expect(...).to_xxx() パターンかどうかを判定する。

        Args:
            node: AST ノード

        Returns:
            expect パターンの場合 True
        """
        # expect(page.xxx()).to_be_visible() のような形式
        # 構造: Call(func=Attribute(value=Call(func=Name(id='expect'))))
        if not isinstance(node, ast.Call):
            return False

        func = node.func
        if not isinstance(func, ast.Attribute):
            return False

        # func.attr が expect メソッド名かチェック
        if func.attr not in _EXPECT_METHODS:
            return False

        # func.value が expect(...) 呼び出しかチェック
        inner = func.value
        if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name):
            return inner.func.id == "expect"

        return False

    def _parse_expect(self, node: ast.Call) -> Optional[RawAction]:
        """expect(...).to_xxx() パターンを解析する。

        Args:
            node: expect 呼び出しの AST ノード

        Returns:
            RawAction、または解析できない場合は None
        """
        func = node.func
        if not isinstance(func, ast.Attribute):
            return None

        assertion_method = func.attr  # "to_be_visible", "to_have_text" 等

        # expect(...) の内部を取得
        expect_call = func.value
        if not isinstance(expect_call, ast.Call):
            return None

        expect_args = expect_call.args
        if not expect_args:
            return None

        inner_expr = expect_args[0]

        # expect(page).to_have_url("...") パターン
        if isinstance(inner_expr, ast.Name) and inner_expr.id == "page":
            if assertion_method == "to_have_url" and node.args:
                url = self._extract_string(node.args[0])
                return RawAction(
                    action_type="expect_url",
                    locator_chain=[],
                    args={"url": url} if url else {},
                    line_number=node.lineno,
                )
            return None

        # expect(page.get_by_xxx(...)).to_xxx() パターン
        # iframe 対応: _extract_locator_chain 内で _current_frame_locator が設定される
        self._current_frame_locator = None
        locator_chain = self._extract_locator_chain(inner_expr)
        frame_locator = self._current_frame_locator
        if not locator_chain:
            logger.warning(
                "行 %d: expect 内のロケータチェーンを解析できません",
                node.lineno,
            )
            return None

        # アサーション種別に応じた action_type を決定
        action_type = self._expect_method_to_action_type(assertion_method)
        args: dict = {}

        # to_have_text / to_contain_text の場合、期待テキストを取得
        if assertion_method in ("to_have_text", "to_contain_text") and node.args:
            text = self._extract_string(node.args[0])
            if text is not None:
                args["text"] = text

        return RawAction(
            action_type=action_type,
            locator_chain=locator_chain,
            args=args,
            line_number=node.lineno,
            frame_locator=frame_locator,
        )

    def _expect_method_to_action_type(self, method: str) -> str:
        """expect のアサーションメソッド名を action_type に変換する。

        Args:
            method: アサーションメソッド名

        Returns:
            対応する action_type 文字列
        """
        mapping = {
            "to_be_visible": "expect_visible",
            "to_be_hidden": "expect_hidden",
            "to_have_text": "expect_text",
            "to_contain_text": "expect_text",
            "to_have_url": "expect_url",
        }
        return mapping.get(method, f"expect_{method}")

    # -------------------------------------------------------------------
    # page.xxx() パターンの解析
    # -------------------------------------------------------------------

    def _parse_page_call(self, node: ast.Call) -> Optional[RawAction]:
        """page.xxx() 呼び出しパターンを解析する。

        対応パターン:
          - page.goto("url")
          - page.get_by_role("button", name="Submit").click()
          - page.locator("#email").fill("value")
          - 等

        Args:
            node: 関数呼び出しの AST ノード

        Returns:
            RawAction、または解析できない場合は None
        """
        func = node.func

        # page.goto("url") — 直接メソッド呼び出し
        if isinstance(func, ast.Attribute):
            # page.mouse.wheel(dx, dy) パターン
            if func.attr == "wheel" and self._is_page_mouse_ref(func.value):
                return self._parse_mouse_wheel(node)

            # page.goto パターン
            if func.attr == "goto" and self._is_page_ref(func.value):
                return self._parse_goto(node)

            # page.locator(...).action() / page.get_by_xxx(...).action() パターン
            if func.attr in _ACTION_METHODS:
                return self._parse_locator_action(node)

        return None

    def _parse_goto(self, node: ast.Call) -> Optional[RawAction]:
        """page.goto("url") パターンを解析する。

        Args:
            node: goto 呼び出しの AST ノード

        Returns:
            RawAction
        """
        url = None
        if node.args:
            url = self._extract_string(node.args[0])

        return RawAction(
            action_type="goto",
            locator_chain=[],
            args={"url": url} if url else {},
            line_number=node.lineno,
        )

    def _parse_locator_action(self, node: ast.Call) -> Optional[RawAction]:
        """page.get_by_xxx(...).action() パターンを解析する。

        iframe 内操作（content_frame 経由）にも対応する。

        Args:
            node: アクション呼び出しの AST ノード

        Returns:
            RawAction、または解析できない場合は None
        """
        func = node.func
        if not isinstance(func, ast.Attribute):
            return None

        action_method = func.attr  # "click", "fill", "press" 等
        locator_expr = func.value  # page.get_by_xxx(...) 部分

        # frame 情報をリセット
        self._current_frame_locator = None

        # ロケータチェーンを抽出（内部で _current_frame_locator が設定される）
        locator_chain = self._extract_locator_chain(locator_expr)
        if not locator_chain:
            return None

        # action_type を決定
        action_type = self._action_method_to_type(action_method)

        # アクション引数を抽出
        args = self._extract_action_args(action_method, node)

        return RawAction(
            action_type=action_type,
            locator_chain=locator_chain,
            args=args,
            line_number=node.lineno,
            frame_locator=self._current_frame_locator,
        )

    def _action_method_to_type(self, method: str) -> str:
        """アクションメソッド名を action_type に変換する。

        Args:
            method: Playwright のアクションメソッド名

        Returns:
            対応する action_type 文字列
        """
        mapping = {
            "click": "click",
            "dblclick": "dblclick",
            "fill": "fill",
            "press": "press",
            "check": "check",
            "uncheck": "uncheck",
            "select_option": "select_option",
            "scroll_into_view_if_needed": "scroll_into_view",
        }
        return mapping.get(method, method)

    def _extract_action_args(self, method: str, node: ast.Call) -> dict:
        """アクションメソッドの引数を抽出する。

        Args:
            method: アクションメソッド名
            node: 関数呼び出しの AST ノード

        Returns:
            引数の辞書
        """
        args: dict = {}

        if method == "fill" and node.args:
            value = self._extract_string(node.args[0])
            if value is not None:
                args["value"] = value

        elif method == "press" and node.args:
            key = self._extract_string(node.args[0])
            if key is not None:
                args["key"] = key

        elif method == "select_option" and node.args:
            value = self._extract_string(node.args[0])
            if value is not None:
                args["value"] = value

        elif method == "scroll_into_view_if_needed":
            # 引数なし。オプション引数は将来拡張で対応。
            pass

        return args

    def _parse_mouse_wheel(self, node: ast.Call) -> RawAction:
        """page.mouse.wheel(dx, dy) パターンを解析する。"""
        delta_x = 0
        delta_y = 0

        if len(node.args) >= 1:
            x_val = self._extract_number(node.args[0])
            if x_val is not None:
                delta_x = x_val
        if len(node.args) >= 2:
            y_val = self._extract_number(node.args[1])
            if y_val is not None:
                delta_y = y_val

        return RawAction(
            action_type="scroll",
            locator_chain=[],
            args={"deltaX": delta_x, "deltaY": delta_y},
            line_number=node.lineno,
        )

    # -------------------------------------------------------------------
    # ロケータチェーンの抽出
    # -------------------------------------------------------------------

    def _extract_locator_chain(self, node: ast.expr) -> list[str]:
        """AST ノードからロケータチェーンを抽出する。

        page.get_by_role("button", name="Submit") のような式から
        ["get_by_role", "button", "name=Submit"] を生成する。

        チェーンされたロケータ（例: page.locator("#parent").locator("#child")）にも対応。
        iframe 内操作（page.locator("iframe").content_frame.xxx()）にも対応。

        Args:
            node: ロケータ式の AST ノード

        Returns:
            ロケータチェーンのリスト。解析できない場合は空リスト。
        """
        chain: list[str] = []
        self._current_frame_locator = None
        self._collect_locator_chain(node, chain)
        return chain

    def _collect_locator_chain(
        self, node: ast.expr, chain: list[str]
    ) -> bool:
        """ロケータチェーンを再帰的に収集する。

        iframe 内操作（content_frame 経由）にも対応する。

        Args:
            node: 現在の AST ノード
            chain: 収集先のチェーンリスト

        Returns:
            収集に成功した場合 True
        """
        if not isinstance(node, ast.Call):
            return False

        func = node.func
        if not isinstance(func, ast.Attribute):
            return False

        method_name = func.attr

        # ロケータメソッドの場合
        if method_name in _LOCATOR_METHODS:
            # page 参照の確認（直接 or content_frame 経由）
            if self._is_page_ref(func.value):
                # content_frame 経由の場合、frame 情報を保持
                frame_sel = self._extract_frame_locator(func.value)
                if frame_sel is not None:
                    self._current_frame_locator = frame_sel
                # page.get_by_xxx(...) — ベースケース
                self._append_locator_info(method_name, node, chain)
                return True
            elif isinstance(func.value, ast.Call):
                # チェーンされたロケータ: page.locator(...).locator(...)
                parent_ok = self._collect_locator_chain(func.value, chain)
                if parent_ok:
                    self._append_locator_info(method_name, node, chain)
                    return True

        return False

    def _append_locator_info(
        self, method_name: str, node: ast.Call, chain: list[str]
    ) -> None:
        """ロケータメソッドの情報をチェーンに追加する。

        Args:
            method_name: ロケータメソッド名
            node: 関数呼び出しの AST ノード
            chain: 追加先のチェーンリスト
        """
        chain.append(method_name)

        # 位置引数を追加
        for arg in node.args:
            val = self._extract_string(arg)
            if val is not None:
                chain.append(val)

        # キーワード引数を追加（name=..., exact=True 等）
        for kw in node.keywords:
            if kw.arg is not None:
                val = self._extract_literal(kw.value)
                if val is not None:
                    chain.append(f"{kw.arg}={val}")

    # -------------------------------------------------------------------
    # ユーティリティ
    # -------------------------------------------------------------------

    def _is_page_ref(self, node: ast.expr) -> bool:
        """ノードが page 参照（直接 or iframe content_frame 経由）かを判定する。

        以下のパターンを page 参照として認識する:
          - page（直接参照）
          - page.locator("iframe").content_frame（iframe 内操作）

        Args:
            node: AST ノード

        Returns:
            page 参照の場合 True
        """
        # 直接の page 参照
        if isinstance(node, ast.Name) and node.id == "page":
            return True

        # page.locator("iframe").content_frame パターン
        frame_sel = self._extract_frame_locator(node)
        return frame_sel is not None

    def _extract_frame_locator(self, node: ast.expr) -> Optional[str]:
        """content_frame チェーンから iframe セレクタを抽出する。

        page.locator("iframe").content_frame のようなパターンを認識し、
        iframe のセレクタ文字列（例: "iframe"）を返す。

        Args:
            node: AST ノード

        Returns:
            iframe セレクタ文字列。content_frame パターンでない場合は None。
        """
        # node が content_frame プロパティアクセスかチェック
        if not isinstance(node, ast.Attribute):
            return None
        if node.attr != "content_frame":
            return None

        # content_frame の親が page.locator("iframe") かチェック
        parent = node.value
        if not isinstance(parent, ast.Call):
            return None

        func = parent.func
        if not isinstance(func, ast.Attribute):
            return None
        if func.attr != "locator":
            return None

        # locator の親が page かチェック
        if not self._is_page_name(func.value):
            return None

        # locator の引数（iframe セレクタ）を取得
        if parent.args:
            return self._extract_string(parent.args[0])
        return None

    def _is_page_name(self, node: ast.expr) -> bool:
        """ノードが 'page' 変数名への直接参照かを判定する。

        _is_page_ref との違い: こちらは再帰しない（無限ループ防止）。

        Args:
            node: AST ノード

        Returns:
            page 変数名の場合 True
        """
        return isinstance(node, ast.Name) and node.id == "page"

    def _is_page_mouse_ref(self, node: ast.expr) -> bool:
        """node が page.mouse を指す場合に True を返す。"""
        return (
            isinstance(node, ast.Attribute)
            and node.attr == "mouse"
            and isinstance(node.value, ast.Name)
            and node.value.id == "page"
        )

    def _extract_string(self, node: ast.expr) -> Optional[str]:
        """AST ノードから文字列リテラルを抽出する。

        Python 3.8+ の ast.Constant に対応。

        Args:
            node: AST ノード

        Returns:
            文字列値、または文字列リテラルでない場合は None
        """
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        return None

    def _extract_literal(self, node: ast.expr) -> Optional[str]:
        """AST ノードからリテラル値を文字列として抽出する。

        文字列、ブール値、数値に対応する。
        キーワード引数（exact=True 等）をチェーンに含めるために使用。

        Args:
            node: AST ノード

        Returns:
            リテラル値の文字列表現、またはリテラルでない場合は None
        """
        if isinstance(node, ast.Constant):
            if isinstance(node.value, str):
                return node.value
            if isinstance(node.value, bool):
                # Python の True/False をそのまま文字列化
                return str(node.value)
            if isinstance(node.value, (int, float)):
                return str(node.value)
        return None

    def _extract_number(self, node: ast.expr) -> Optional[int]:
        """AST ノードから int/float リテラルを int として抽出する。"""
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return int(node.value)
        return None

    # codegen が生成するブラウザ/コンテキスト終了処理など、
    # 変換不要で無視してよいメソッド名のセット
    _IGNORABLE_METHODS: set[str] = {
        "close", "new_context", "new_page", "launch",
    }

    # codegen のボイラープレートで呼ばれる関数名のセット
    _IGNORABLE_FUNCTIONS: set[str] = {"run", "sync_playwright"}

    def _warn_unsupported(self, node: ast.expr) -> None:
        """未対応パターンの警告を出力する。

        codegen が生成するブラウザ終了処理（.close() 等）や
        ボイラープレート関数呼び出し（run() 等）は
        ユーザーに不要な警告となるため、debug レベルに抑制する。

        Args:
            node: 未対応の AST ノード
        """
        line = getattr(node, "lineno", "?")
        desc = "不明な式"

        if isinstance(node, ast.Call):
            func = node.func

            # obj.method() パターン
            if isinstance(func, ast.Attribute):
                method_name = func.attr
                desc = f".{method_name}()"
                if method_name in self._IGNORABLE_METHODS:
                    logger.debug("行 %s: スキップ（変換不要）: %s", line, desc)
                    return

            # func_name() パターン（run(playwright) 等）
            elif isinstance(func, ast.Name):
                func_name = func.id
                desc = f"{func_name}()"
                if func_name in self._IGNORABLE_FUNCTIONS:
                    logger.debug("行 %s: スキップ（変換不要）: %s", line, desc)
                    return

        logger.warning("行 %s: 未対応の Playwright パターン: %s", line, desc)
