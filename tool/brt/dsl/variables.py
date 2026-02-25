"""
変数展開エンジン — ${env.X} / ${vars.X} の遅延評価展開

ステップ実行時にテキスト内の変数参照を展開する。
パース時には展開せず、Runner がステップを実行する直前に呼び出す（遅延評価）。

サポートする構文:
  - ${env.X}  → 環境変数辞書から値を取得
  - ${vars.X} → シナリオ変数辞書から値を取得

未定義変数参照時は VariableNotFoundError を送出する。
展開後に未解決の ${...} パターンが残らないことを保証する。

要件 3.2: ${env.X}, ${vars.X} の変数展開構文サポート
"""

from __future__ import annotations

import re
from typing import Any


# ---------------------------------------------------------------------------
# 変数参照パターン
# ---------------------------------------------------------------------------

# ${env.X} または ${vars.X} にマッチする正規表現
_VAR_PATTERN = re.compile(r"\$\{(env|vars)\.([a-zA-Z_][a-zA-Z0-9_]*)\}")

# 展開後に残っている未解決の ${...} パターンを検出する正規表現
_UNRESOLVED_PATTERN = re.compile(r"\$\{[^}]+\}")


# ---------------------------------------------------------------------------
# カスタム例外
# ---------------------------------------------------------------------------

class VariableNotFoundError(Exception):
    """未定義の変数が参照された場合に送出される例外。

    Attributes:
        namespace: 変数の名前空間（"env" または "vars"）
        var_name: 参照された変数名
    """

    def __init__(self, namespace: str, var_name: str) -> None:
        self.namespace = namespace
        self.var_name = var_name
        super().__init__(
            f"未定義の変数が参照されました: ${{{namespace}.{var_name}}}"
        )


# ---------------------------------------------------------------------------
# VariableExpander 本体
# ---------------------------------------------------------------------------

class VariableExpander:
    """テキスト内の変数参照を展開するエンジン。

    コンストラクタで環境変数辞書とシナリオ変数辞書を受け取り、
    expand() でテキスト内の ${env.X} / ${vars.X} を対応する値に置換する。

    遅延評価: expand() はステップ実行時に呼ばれる想定であり、
    パース時には展開しない。storeText / storeAttr で取得した値は
    set_var() で vars に格納し、後続ステップで参照可能にする。
    """

    def __init__(self, env: dict[str, str], vars: dict[str, str]) -> None:
        """変数展開エンジンを初期化する。

        Args:
            env: 環境変数辞書（os.environ 相当。テスタビリティのため直接渡す）
            vars: シナリオ変数辞書（Scenario.vars の初期値）
        """
        self._env: dict[str, str] = dict(env)
        self._vars: dict[str, str] = dict(vars)

    # ----- 公開メソッド -----

    def expand(self, text: str) -> str:
        """テキスト内の変数参照を展開する。

        ${env.X} は環境変数辞書から、${vars.X} はシナリオ変数辞書から
        対応する値を取得して置換する。

        展開後に未解決の ${...} パターンが残っていないことを検証し、
        残っている場合は VariableNotFoundError を送出する。

        Args:
            text: 展開対象のテキスト

        Returns:
            変数参照が展開されたテキスト

        Raises:
            VariableNotFoundError: 未定義の変数が参照された場合
        """
        result = _VAR_PATTERN.sub(self._replace_match, text)

        # 展開後に未解決パターンが残っていないことを保証
        unresolved = _UNRESOLVED_PATTERN.search(result)
        if unresolved:
            # 未解決パターンから名前空間と変数名を抽出して報告
            raw = unresolved.group()
            raise VariableNotFoundError("unknown", raw)

        return result

    def expand_step(self, step: dict) -> dict:
        """ステップ辞書内の全文字列値を再帰的に展開する。

        辞書のキーは展開せず、値のみを展開する。
        ネストされた辞書やリストも再帰的に処理する。

        Args:
            step: 展開対象のステップ辞書

        Returns:
            変数参照が展開されたステップ辞書（新しい辞書を返す）

        Raises:
            VariableNotFoundError: 未定義の変数が参照された場合
        """
        return self._expand_value(step)

    def set_var(self, name: str, value: str) -> None:
        """シナリオ変数を動的に設定する。

        storeText / storeAttr で取得した値を vars に格納し、
        後続ステップで ${vars.X} として参照可能にする。

        Args:
            name: 変数名
            value: 変数の値
        """
        self._vars[name] = value

    # ----- プロパティ（テスト・デバッグ用） -----

    @property
    def env(self) -> dict[str, str]:
        """環境変数辞書の読み取り専用コピーを返す。"""
        return dict(self._env)

    @property
    def vars(self) -> dict[str, str]:
        """シナリオ変数辞書の読み取り専用コピーを返す。"""
        return dict(self._vars)

    # ----- 内部メソッド -----

    def _replace_match(self, match: re.Match) -> str:
        """正規表現マッチから変数値を取得して返す。

        Args:
            match: _VAR_PATTERN にマッチした結果

        Returns:
            変数の値

        Raises:
            VariableNotFoundError: 変数が未定義の場合
        """
        namespace = match.group(1)  # "env" or "vars"
        var_name = match.group(2)   # 変数名

        if namespace == "env":
            if var_name not in self._env:
                raise VariableNotFoundError("env", var_name)
            return self._env[var_name]

        if namespace == "vars":
            if var_name not in self._vars:
                raise VariableNotFoundError("vars", var_name)
            return self._vars[var_name]

        # ここには到達しないはず（正規表現で env|vars に限定済み）
        raise VariableNotFoundError(namespace, var_name)

    def _expand_value(self, value: Any) -> Any:
        """値を再帰的に展開する。

        - str: expand() で変数参照を展開
        - dict: 各値を再帰的に展開（キーは展開しない）
        - list: 各要素を再帰的に展開
        - その他: そのまま返す

        Args:
            value: 展開対象の値

        Returns:
            展開後の値
        """
        if isinstance(value, str):
            return self.expand(value)
        if isinstance(value, dict):
            return {k: self._expand_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._expand_value(item) for item in value]
        # int, float, bool, None 等はそのまま返す
        return value
