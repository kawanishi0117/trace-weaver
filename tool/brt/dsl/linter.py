"""
DSL Linter — YAML DSL の静的解析

YAML DSL のセレクタ危険度やアンチパターンを検出し、
テスト実行前に品質問題を報告する。

検出ルール:
  - text セレクタ単体使用 → warning（要件 12.1）
  - any フォールバック未設定 → info（要件 12.2）
  - パスワード系フィールドの secret 未設定 → warning（要件 12.3）

各 lint 結果にはステップ名、行番号、重大度（error/warning/info）を含む（要件 12.4）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .schema import Scenario


# ---------------------------------------------------------------------------
# Lint 重大度
# ---------------------------------------------------------------------------

class LintSeverity(Enum):
    """Lint 結果の重大度レベル。"""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


# ---------------------------------------------------------------------------
# Lint 検出結果
# ---------------------------------------------------------------------------

@dataclass
class LintIssue:
    """Lint で検出された問題を表現するデータクラス。

    Attributes:
        step_name: 問題が検出されたステップの名前
        line_number: ステップの行番号（steps 配列内のインデックス + 1）
        severity: 重大度（error / warning / info）
        rule: 適用されたルール名
        message: 問題の説明メッセージ
    """

    step_name: str
    line_number: int
    severity: LintSeverity
    rule: str
    message: str


# ---------------------------------------------------------------------------
# パスワード関連キーワード
# ---------------------------------------------------------------------------

# パスワード系フィールドを検出するためのキーワードパターン（大文字小文字不問）
_PASSWORD_KEYWORDS = re.compile(
    r"(password|パスワード|secret|token|credential|passphrase|pin|暗証)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# DslLinter 本体
# ---------------------------------------------------------------------------

class DslLinter:
    """YAML DSL の静的解析を行う Linter。

    Scenario オブジェクトを受け取り、全 lint ルールを適用して
    検出された問題を LintIssue のリストとして返す。
    """

    def lint(self, scenario: Scenario) -> list[LintIssue]:
        """全 lint ルールを適用し、問題を検出する。

        Scenario の steps 配列（section 内のステップを含む）を走査し、
        各ステップに対して全ルールを適用する。

        Args:
            scenario: 検査対象の Scenario オブジェクト

        Returns:
            検出された LintIssue のリスト（問題なしの場合は空リスト）
        """
        issues: list[LintIssue] = []

        # steps 配列を走査（section 内のステップも展開）
        for line_number, step in self._iter_steps(scenario.steps):
            # 各ルールを適用
            for check in (
                self._check_text_only_selector,
                self._check_missing_any_fallback,
                self._check_missing_secret,
            ):
                issue = check(step, line_number)
                if issue is not None:
                    issues.append(issue)

        return issues

    # -----------------------------------------------------------------
    # Lint ルール
    # -----------------------------------------------------------------

    def _check_text_only_selector(
        self, step: dict, line_number: int
    ) -> Optional[LintIssue]:
        """text セレクタが単体で使用されている場合に warning を出力する。

        css + text や role + name の補助条件としての使用は許可する。
        text キーのみを持つセレクタ辞書を検出対象とする。

        要件 12.1: text セレクタ単体使用 → warning
        """
        selector = self._extract_selector(step)
        if selector is None:
            return None

        # text キーのみを持つセレクタ（strict は除外して判定）
        if self._is_text_only_selector(selector):
            return LintIssue(
                step_name=self._get_step_name(step),
                line_number=line_number,
                severity=LintSeverity.WARNING,
                rule="text-only-selector",
                message=(
                    "text セレクタが単体で使用されています。"
                    "不安定なため、testId / role+name / css+text の使用を推奨します。"
                ),
            )

        return None

    def _check_missing_any_fallback(
        self, step: dict, line_number: int
    ) -> Optional[LintIssue]:
        """any フォールバックが設定されていない場合に info を出力する。

        セレクタを持つステップで、any フォールバックが未設定の場合に
        推奨事項として情報レベルの通知を出力する。

        要件 12.2: any フォールバック未設定 → info
        """
        selector = self._extract_selector(step)
        if selector is None:
            return None

        # any セレクタが設定されている場合はスキップ
        if isinstance(selector, dict) and "any" in selector:
            return None

        return LintIssue(
            step_name=self._get_step_name(step),
            line_number=line_number,
            severity=LintSeverity.INFO,
            rule="missing-any-fallback",
            message=(
                "any フォールバックが設定されていません。"
                "セレクタの安定性向上のため、any による複数候補の指定を推奨します。"
            ),
        )

    def _check_missing_secret(
        self, step: dict, line_number: int
    ) -> Optional[LintIssue]:
        """パスワード系フィールドに secret: true が未設定の場合に warning を出力する。

        fill ステップで、セレクタやステップ名にパスワード関連キーワードが
        含まれているにもかかわらず secret: true が設定されていない場合に警告する。

        要件 12.3: パスワード系フィールドの secret 未設定 → warning
        """
        # fill ステップのみが対象
        if "fill" not in step:
            return None

        fill_data = step["fill"]

        # secret: true が既に設定されている場合はスキップ
        if step.get("secret", False) or (
            isinstance(fill_data, dict) and fill_data.get("secret", False)
        ):
            return None

        # パスワード関連キーワードの検出対象テキストを収集
        texts_to_check = self._collect_password_hint_texts(step)

        # いずれかのテキストにパスワード関連キーワードが含まれるか
        for text in texts_to_check:
            if _PASSWORD_KEYWORDS.search(text):
                return LintIssue(
                    step_name=self._get_step_name(step),
                    line_number=line_number,
                    severity=LintSeverity.WARNING,
                    rule="missing-secret",
                    message=(
                        "パスワード関連のフィールドに secret: true が設定されていません。"
                        "ログやレポートで値がマスクされるよう、secret: true の付与を推奨します。"
                    ),
                )

        return None

    # -----------------------------------------------------------------
    # ヘルパーメソッド
    # -----------------------------------------------------------------

    def _iter_steps(
        self, steps: list[dict], base_line: int = 1
    ) -> list[tuple[int, dict]]:
        """steps 配列を走査し、(行番号, ステップ辞書) のリストを返す。

        section 内のステップも再帰的に展開する。
        行番号は steps 配列内の通し番号（1始まり）。

        Args:
            steps: ステップ配列
            base_line: 行番号のオフセット

        Returns:
            (行番号, ステップ辞書) のタプルリスト
        """
        result: list[tuple[int, dict]] = []
        current_line = base_line

        for step in steps:
            if "section" in step:
                # section 内のステップを再帰的に展開
                inner_steps = step.get("steps", [])
                result.extend(self._iter_steps(inner_steps, current_line))
                current_line += len(inner_steps)
            else:
                result.append((current_line, step))
                current_line += 1

        return result

    def _extract_selector(self, step: dict) -> Optional[dict]:
        """ステップからセレクタ辞書を抽出する。

        セレクタを持つステップ（click, fill, press 等）のセレクタ部分を返す。
        セレクタを持たないステップ（goto, back, log 等）の場合は None を返す。

        Args:
            step: ステップ辞書

        Returns:
            セレクタ辞書、またはセレクタを持たない場合は None
        """
        # セレクタを直接持つステップキー
        # click: {testId: "xxx"} のように、ステップキーの値がセレクタ辞書
        _SELECTOR_STEP_KEYS = (
            "click", "dblclick", "fill", "press",
            "check", "uncheck", "selectOption",
            "waitFor", "waitForVisible", "waitForHidden",
            "expectVisible", "expectHidden", "expectText",
            "storeText", "storeAttr", "dumpDom",
        )

        for key in _SELECTOR_STEP_KEYS:
            if key not in step:
                continue

            value = step[key]

            # ステップキーの値が辞書の場合、それがセレクタ
            # 例: {"click": {"testId": "submit-btn"}}
            if isinstance(value, dict):
                # fill ステップは by フィールドにセレクタを持つ場合がある
                if "by" in value:
                    return value["by"]
                # セレクタキーを直接持つ場合
                if self._looks_like_selector(value):
                    return value

            # ステップキーの値が文字列の場合はセレクタなし
            # 例: {"goto": "http://..."} や {"log": "message"}

        return None

    def _looks_like_selector(self, d: dict) -> bool:
        """辞書がセレクタのように見えるかを判定する。

        セレクタ固有のキー（testId, role, label, placeholder, css, text, any）
        のいずれかを含む場合に True を返す。

        Args:
            d: 判定対象の辞書

        Returns:
            セレクタらしい場合は True
        """
        _SELECTOR_KEYS = {"testId", "role", "label", "placeholder", "css", "text", "any"}
        return bool(_SELECTOR_KEYS & set(d.keys()))

    def _is_text_only_selector(self, selector: dict) -> bool:
        """セレクタが text 単体であるかを判定する。

        text キーのみを持ち（strict は除外）、他のセレクタキーを持たない場合に True。
        css + text のような補助条件としての使用は False を返す。

        Args:
            selector: セレクタ辞書

        Returns:
            text 単体セレクタの場合は True
        """
        # strict を除外したキーセット
        keys = {k for k in selector.keys() if k != "strict"}
        return keys == {"text"}

    def _get_step_name(self, step: dict) -> str:
        """ステップから名前を取得する。

        name フィールドがある場合はその値を返す。
        ない場合はステップの種別キーを返す。

        Args:
            step: ステップ辞書

        Returns:
            ステップ名
        """
        # トップレベルの name フィールド
        if "name" in step:
            return step["name"]

        # ステップ種別キーの値が辞書で name を持つ場合
        for key, value in step.items():
            if isinstance(value, dict) and "name" in value:
                return value["name"]

        # ステップ種別キーをフォールバックとして使用
        for key in step:
            if key not in ("name", "secret", "value", "key"):
                return key

        return "unknown"

    def _collect_password_hint_texts(self, step: dict) -> list[str]:
        """ステップからパスワード関連キーワードの検出対象テキストを収集する。

        ステップ名、セレクタの各フィールド値を収集して返す。

        Args:
            step: ステップ辞書

        Returns:
            検出対象テキストのリスト
        """
        texts: list[str] = []

        # ステップ名
        step_name = self._get_step_name(step)
        texts.append(step_name)

        # fill ステップのセレクタ情報
        fill_data = step.get("fill")
        if isinstance(fill_data, dict):
            # by フィールド内のセレクタ値
            by = fill_data.get("by", fill_data)
            texts.extend(self._extract_selector_texts(by))
        elif isinstance(fill_data, str):
            # fill が文字列の場合（直接テキスト指定）
            texts.append(fill_data)

        # name フィールド
        if "name" in step:
            texts.append(str(step["name"]))

        return texts

    def _extract_selector_texts(self, selector: dict) -> list[str]:
        """セレクタ辞書からテキスト値を抽出する。

        セレクタの各フィールド値（role, name, label, placeholder, text, css 等）
        を文字列として収集する。

        Args:
            selector: セレクタ辞書

        Returns:
            セレクタ内のテキスト値リスト
        """
        texts: list[str] = []

        if not isinstance(selector, dict):
            return texts

        # セレクタの値フィールドを収集
        for key in ("role", "name", "label", "placeholder", "text", "css", "testId"):
            value = selector.get(key)
            if isinstance(value, str):
                texts.append(value)

        return texts
