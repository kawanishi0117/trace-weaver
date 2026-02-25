"""
DslLinter のユニットテスト

各 lint ルールの検出動作、問題なしケース、複数問題の同時検出、
section 内ステップの検査を検証する。

要件 12.1: text セレクタ単体使用 → warning
要件 12.2: any フォールバック未設定 → info
要件 12.3: パスワード系フィールドの secret 未設定 → warning
要件 12.4: lint 結果にステップ名、行番号、重大度を含む
"""

from __future__ import annotations

import pytest

from brt.dsl.linter import DslLinter, LintIssue, LintSeverity
from brt.dsl.schema import Scenario


# ---------------------------------------------------------------------------
# フィクスチャ
# ---------------------------------------------------------------------------

@pytest.fixture
def linter() -> DslLinter:
    """DslLinter インスタンスを提供する。"""
    return DslLinter()


def _make_scenario(steps: list[dict]) -> Scenario:
    """テスト用の最小 Scenario を生成するヘルパー。"""
    return Scenario(
        title="テストシナリオ",
        baseUrl="http://localhost:4200",
        steps=steps,
    )


# ---------------------------------------------------------------------------
# text セレクタ単体使用の検出テスト（要件 12.1）
# ---------------------------------------------------------------------------

class TestTextOnlySelector:
    """_check_text_only_selector ルールのテスト。"""

    def test_text_only_click_detected(self, linter: DslLinter):
        """click ステップで text 単体セレクタが warning として検出されること。"""
        scenario = _make_scenario([
            {"click": {"text": "送信"}, "name": "送信クリック"},
        ])

        issues = linter.lint(scenario)

        text_issues = [i for i in issues if i.rule == "text-only-selector"]
        assert len(text_issues) >= 1
        assert text_issues[0].severity == LintSeverity.WARNING
        assert text_issues[0].step_name == "送信クリック"

    def test_text_only_fill_detected(self, linter: DslLinter):
        """fill ステップで text 単体セレクタが warning として検出されること。"""
        scenario = _make_scenario([
            {"fill": {"text": "ユーザー名"}, "value": "user1", "name": "ユーザー名入力"},
        ])

        issues = linter.lint(scenario)

        text_issues = [i for i in issues if i.rule == "text-only-selector"]
        assert len(text_issues) >= 1
        assert text_issues[0].severity == LintSeverity.WARNING

    def test_css_with_text_not_detected(self, linter: DslLinter):
        """css + text の補助条件使用は text-only-selector として検出されないこと。"""
        scenario = _make_scenario([
            {"click": {"css": ".btn", "text": "送信"}, "name": "送信クリック"},
        ])

        issues = linter.lint(scenario)

        text_issues = [i for i in issues if i.rule == "text-only-selector"]
        assert len(text_issues) == 0

    def test_role_selector_not_detected(self, linter: DslLinter):
        """role セレクタは text-only-selector として検出されないこと。"""
        scenario = _make_scenario([
            {"click": {"role": "button", "name": "送信"}, "name": "送信クリック"},
        ])

        issues = linter.lint(scenario)

        text_issues = [i for i in issues if i.rule == "text-only-selector"]
        assert len(text_issues) == 0

    def test_testid_selector_not_detected(self, linter: DslLinter):
        """testId セレクタは text-only-selector として検出されないこと。"""
        scenario = _make_scenario([
            {"click": {"testId": "submit-btn"}, "name": "送信クリック"},
        ])

        issues = linter.lint(scenario)

        text_issues = [i for i in issues if i.rule == "text-only-selector"]
        assert len(text_issues) == 0


# ---------------------------------------------------------------------------
# any フォールバック未設定の検出テスト（要件 12.2）
# ---------------------------------------------------------------------------

class TestMissingAnyFallback:
    """_check_missing_any_fallback ルールのテスト。"""

    def test_missing_any_fallback_detected(self, linter: DslLinter):
        """any フォールバック未設定が info として検出されること。"""
        scenario = _make_scenario([
            {"click": {"testId": "submit-btn"}, "name": "送信クリック"},
        ])

        issues = linter.lint(scenario)

        any_issues = [i for i in issues if i.rule == "missing-any-fallback"]
        assert len(any_issues) >= 1
        assert any_issues[0].severity == LintSeverity.INFO

    def test_any_fallback_present_not_detected(self, linter: DslLinter):
        """any フォールバックが設定されている場合は検出されないこと。"""
        scenario = _make_scenario([
            {
                "click": {
                    "any": [
                        {"testId": "submit-btn"},
                        {"role": "button", "name": "送信"},
                    ],
                },
                "name": "送信クリック",
            },
        ])

        issues = linter.lint(scenario)

        any_issues = [i for i in issues if i.rule == "missing-any-fallback"]
        assert len(any_issues) == 0

    def test_goto_step_no_any_fallback_issue(self, linter: DslLinter):
        """goto ステップ（セレクタなし）は any フォールバック検出対象外であること。"""
        scenario = _make_scenario([
            {"goto": "http://localhost:4200/login", "name": "ログイン画面"},
        ])

        issues = linter.lint(scenario)

        any_issues = [i for i in issues if i.rule == "missing-any-fallback"]
        assert len(any_issues) == 0


# ---------------------------------------------------------------------------
# パスワード系フィールドの secret 未設定検出テスト（要件 12.3）
# ---------------------------------------------------------------------------

class TestMissingSecret:
    """_check_missing_secret ルールのテスト。"""

    def test_password_field_without_secret_detected(self, linter: DslLinter):
        """パスワードフィールドに secret 未設定が warning として検出されること。"""
        scenario = _make_scenario([
            {"fill": {"label": "パスワード"}, "value": "secret123", "name": "パスワード入力"},
        ])

        issues = linter.lint(scenario)

        secret_issues = [i for i in issues if i.rule == "missing-secret"]
        assert len(secret_issues) >= 1
        assert secret_issues[0].severity == LintSeverity.WARNING

    def test_password_in_name_detected(self, linter: DslLinter):
        """ステップ名に password を含む場合に検出されること。"""
        scenario = _make_scenario([
            {"fill": {"css": "#pass"}, "value": "abc", "name": "fill-password"},
        ])

        issues = linter.lint(scenario)

        secret_issues = [i for i in issues if i.rule == "missing-secret"]
        assert len(secret_issues) >= 1

    def test_password_in_role_name_detected(self, linter: DslLinter):
        """セレクタの name に Password を含む場合に検出されること。"""
        scenario = _make_scenario([
            {
                "fill": {"role": "textbox", "name": "Password"},
                "value": "abc",
                "name": "入力",
            },
        ])

        issues = linter.lint(scenario)

        secret_issues = [i for i in issues if i.rule == "missing-secret"]
        assert len(secret_issues) >= 1

    def test_secret_true_not_detected(self, linter: DslLinter):
        """secret: true が設定されている場合は検出されないこと。"""
        scenario = _make_scenario([
            {
                "fill": {"label": "パスワード"},
                "value": "secret123",
                "name": "パスワード入力",
                "secret": True,
            },
        ])

        issues = linter.lint(scenario)

        secret_issues = [i for i in issues if i.rule == "missing-secret"]
        assert len(secret_issues) == 0

    def test_non_password_field_not_detected(self, linter: DslLinter):
        """パスワード関連でないフィールドは検出されないこと。"""
        scenario = _make_scenario([
            {"fill": {"label": "メールアドレス"}, "value": "test@example.com", "name": "メール入力"},
        ])

        issues = linter.lint(scenario)

        secret_issues = [i for i in issues if i.rule == "missing-secret"]
        assert len(secret_issues) == 0

    def test_token_keyword_detected(self, linter: DslLinter):
        """token キーワードを含むフィールドが検出されること。"""
        scenario = _make_scenario([
            {"fill": {"label": "API Token"}, "value": "abc123", "name": "token入力"},
        ])

        issues = linter.lint(scenario)

        secret_issues = [i for i in issues if i.rule == "missing-secret"]
        assert len(secret_issues) >= 1

    def test_click_step_not_checked_for_secret(self, linter: DslLinter):
        """click ステップは secret チェック対象外であること。"""
        scenario = _make_scenario([
            {"click": {"label": "パスワード表示"}, "name": "パスワード表示クリック"},
        ])

        issues = linter.lint(scenario)

        secret_issues = [i for i in issues if i.rule == "missing-secret"]
        assert len(secret_issues) == 0


# ---------------------------------------------------------------------------
# 問題なしケースのテスト
# ---------------------------------------------------------------------------

class TestNoIssues:
    """問題が検出されない場合のテスト。"""

    def test_empty_steps_returns_empty(self, linter: DslLinter):
        """ステップが空の場合は空リストを返すこと。"""
        scenario = _make_scenario([])

        issues = linter.lint(scenario)

        assert issues == []

    def test_clean_scenario_minimal_issues(self, linter: DslLinter):
        """適切に構成されたシナリオでは重大な問題が検出されないこと。"""
        scenario = _make_scenario([
            {"goto": "http://localhost:4200/login", "name": "ログイン画面"},
            {
                "fill": {
                    "any": [
                        {"testId": "email-input"},
                        {"label": "メールアドレス"},
                    ],
                },
                "value": "test@example.com",
                "name": "メール入力",
            },
            {
                "fill": {
                    "any": [
                        {"testId": "password-input"},
                        {"label": "パスワード"},
                    ],
                },
                "value": "secret123",
                "name": "パスワード入力",
                "secret": True,
            },
        ])

        issues = linter.lint(scenario)

        # warning / error レベルの問題がないこと
        serious_issues = [
            i for i in issues
            if i.severity in (LintSeverity.WARNING, LintSeverity.ERROR)
        ]
        assert len(serious_issues) == 0


# ---------------------------------------------------------------------------
# 複数問題の同時検出テスト
# ---------------------------------------------------------------------------

class TestMultipleIssues:
    """複数の問題が同時に検出されるケースのテスト。"""

    def test_multiple_rules_detected(self, linter: DslLinter):
        """異なるルールの問題が同時に検出されること。"""
        scenario = _make_scenario([
            # text 単体 → text-only-selector + missing-any-fallback
            {"click": {"text": "送信"}, "name": "送信クリック"},
            # パスワード secret 未設定 → missing-secret + missing-any-fallback
            {"fill": {"label": "パスワード"}, "value": "abc", "name": "パスワード入力"},
        ])

        issues = linter.lint(scenario)

        rules = {i.rule for i in issues}
        assert "text-only-selector" in rules
        assert "missing-any-fallback" in rules
        assert "missing-secret" in rules

    def test_multiple_steps_each_detected(self, linter: DslLinter):
        """複数ステップそれぞれで問題が検出されること。"""
        scenario = _make_scenario([
            {"click": {"text": "ボタン1"}, "name": "クリック1"},
            {"click": {"text": "ボタン2"}, "name": "クリック2"},
        ])

        issues = linter.lint(scenario)

        text_issues = [i for i in issues if i.rule == "text-only-selector"]
        assert len(text_issues) == 2


# ---------------------------------------------------------------------------
# section 内ステップの検査テスト
# ---------------------------------------------------------------------------

class TestSectionSteps:
    """section 内のステップも検査対象となることのテスト。"""

    def test_section_steps_are_linted(self, linter: DslLinter):
        """section 内のステップも lint 対象であること。"""
        scenario = _make_scenario([
            {
                "section": "ログインセクション",
                "steps": [
                    {"click": {"text": "ログイン"}, "name": "ログインクリック"},
                ],
            },
        ])

        issues = linter.lint(scenario)

        text_issues = [i for i in issues if i.rule == "text-only-selector"]
        assert len(text_issues) >= 1
        assert text_issues[0].step_name == "ログインクリック"

    def test_nested_section_secret_check(self, linter: DslLinter):
        """section 内の fill ステップでも secret チェックが動作すること。"""
        scenario = _make_scenario([
            {
                "section": "認証セクション",
                "steps": [
                    {
                        "fill": {"label": "パスワード"},
                        "value": "secret",
                        "name": "パスワード入力",
                    },
                ],
            },
        ])

        issues = linter.lint(scenario)

        secret_issues = [i for i in issues if i.rule == "missing-secret"]
        assert len(secret_issues) >= 1


# ---------------------------------------------------------------------------
# LintIssue の出力フォーマットテスト（要件 12.4）
# ---------------------------------------------------------------------------

class TestLintIssueFormat:
    """LintIssue にステップ名、行番号、重大度が含まれることのテスト。"""

    def test_issue_has_step_name(self, linter: DslLinter):
        """LintIssue にステップ名が含まれること。"""
        scenario = _make_scenario([
            {"click": {"text": "送信"}, "name": "送信ボタンクリック"},
        ])

        issues = linter.lint(scenario)

        text_issues = [i for i in issues if i.rule == "text-only-selector"]
        assert len(text_issues) >= 1
        assert text_issues[0].step_name == "送信ボタンクリック"

    def test_issue_has_line_number(self, linter: DslLinter):
        """LintIssue に行番号が含まれること。"""
        scenario = _make_scenario([
            {"goto": "http://localhost", "name": "トップ"},
            {"click": {"text": "送信"}, "name": "送信クリック"},
        ])

        issues = linter.lint(scenario)

        text_issues = [i for i in issues if i.rule == "text-only-selector"]
        assert len(text_issues) >= 1
        # 2番目のステップなので行番号は 2
        assert text_issues[0].line_number == 2

    def test_issue_has_severity(self, linter: DslLinter):
        """LintIssue に重大度が含まれること。"""
        scenario = _make_scenario([
            {"click": {"text": "送信"}, "name": "送信クリック"},
        ])

        issues = linter.lint(scenario)

        for issue in issues:
            assert isinstance(issue.severity, LintSeverity)
            assert issue.severity.value in ("error", "warning", "info")

    def test_issue_has_rule_and_message(self, linter: DslLinter):
        """LintIssue にルール名とメッセージが含まれること。"""
        scenario = _make_scenario([
            {"click": {"text": "送信"}, "name": "送信クリック"},
        ])

        issues = linter.lint(scenario)

        for issue in issues:
            assert issue.rule != ""
            assert issue.message != ""
