"""
PyAstParser のユニットテスト

Playwright codegen が生成する各種 Python パターンの認識を検証する。
テストは最低20個以上作成し、以下のカテゴリをカバーする:
  - goto パターン
  - click パターン（role, testId, text, label, placeholder）
  - fill パターン（locator, label, placeholder）
  - press パターン
  - check / uncheck パターン
  - dblclick パターン
  - select_option パターン
  - expect 系パターン（visible, text, url）
  - 未対応パターンの警告
  - 空ソースコード / 構文エラー
  - 複数アクションの連続パース
  - locator チェーンの正確性
"""

from __future__ import annotations

import logging

import pytest

from src.importer.py_ast_parser import PyAstParser, RawAction


# ---------------------------------------------------------------------------
# フィクスチャ
# ---------------------------------------------------------------------------

@pytest.fixture
def parser() -> PyAstParser:
    """PyAstParser インスタンスを提供する。"""
    return PyAstParser()


# ===========================================================================
# 1. goto パターン
# ===========================================================================

class TestGotoPattern:
    """page.goto() パターンの認識テスト。"""

    def test_goto_simple_url(self, parser: PyAstParser) -> None:
        """シンプルな goto パターンを認識できること。"""
        source = 'page.goto("https://example.com")'
        actions = parser.parse(source)

        assert len(actions) == 1
        assert actions[0].action_type == "goto"
        assert actions[0].args["url"] == "https://example.com"
        assert actions[0].locator_chain == []

    def test_goto_with_path(self, parser: PyAstParser) -> None:
        """パス付き URL の goto パターンを認識できること。"""
        source = 'page.goto("https://example.com/login?redirect=/dashboard")'
        actions = parser.parse(source)

        assert len(actions) == 1
        assert actions[0].action_type == "goto"
        assert actions[0].args["url"] == "https://example.com/login?redirect=/dashboard"

    def test_goto_line_number(self, parser: PyAstParser) -> None:
        """goto の行番号が正しく記録されること。"""
        source = """\
# コメント行
page.goto("https://example.com")
"""
        actions = parser.parse(source)

        assert len(actions) == 1
        assert actions[0].line_number == 2


# ===========================================================================
# 2. click パターン
# ===========================================================================

class TestClickPattern:
    """click パターンの認識テスト。"""

    def test_click_by_role_with_name(self, parser: PyAstParser) -> None:
        """get_by_role + name + click パターンを認識できること。"""
        source = 'page.get_by_role("button", name="Submit").click()'
        actions = parser.parse(source)

        assert len(actions) == 1
        action = actions[0]
        assert action.action_type == "click"
        assert "get_by_role" in action.locator_chain
        assert "button" in action.locator_chain
        assert "name=Submit" in action.locator_chain

    def test_click_by_role_without_name(self, parser: PyAstParser) -> None:
        """get_by_role（name なし）+ click パターンを認識できること。"""
        source = 'page.get_by_role("textbox").click()'
        actions = parser.parse(source)

        assert len(actions) == 1
        action = actions[0]
        assert action.action_type == "click"
        assert action.locator_chain == ["get_by_role", "textbox"]

    def test_click_by_test_id(self, parser: PyAstParser) -> None:
        """get_by_test_id + click パターンを認識できること。"""
        source = 'page.get_by_test_id("login-btn").click()'
        actions = parser.parse(source)

        assert len(actions) == 1
        action = actions[0]
        assert action.action_type == "click"
        assert action.locator_chain == ["get_by_test_id", "login-btn"]

    def test_click_by_text(self, parser: PyAstParser) -> None:
        """get_by_text + click パターンを認識できること。"""
        source = 'page.get_by_text("Submit").click()'
        actions = parser.parse(source)

        assert len(actions) == 1
        action = actions[0]
        assert action.action_type == "click"
        assert action.locator_chain == ["get_by_text", "Submit"]

    def test_click_by_label(self, parser: PyAstParser) -> None:
        """get_by_label + click パターンを認識できること。"""
        source = 'page.get_by_label("Accept terms").click()'
        actions = parser.parse(source)

        assert len(actions) == 1
        action = actions[0]
        assert action.action_type == "click"
        assert action.locator_chain == ["get_by_label", "Accept terms"]

    def test_click_by_placeholder(self, parser: PyAstParser) -> None:
        """get_by_placeholder + click パターンを認識できること。"""
        source = 'page.get_by_placeholder("Search...").click()'
        actions = parser.parse(source)

        assert len(actions) == 1
        action = actions[0]
        assert action.action_type == "click"
        assert action.locator_chain == ["get_by_placeholder", "Search..."]


# ===========================================================================
# 3. fill パターン
# ===========================================================================

class TestFillPattern:
    """fill パターンの認識テスト。"""

    def test_fill_by_locator_css(self, parser: PyAstParser) -> None:
        """locator(css) + fill パターンを認識できること。"""
        source = 'page.locator("#email").fill("test@example.com")'
        actions = parser.parse(source)

        assert len(actions) == 1
        action = actions[0]
        assert action.action_type == "fill"
        assert action.locator_chain == ["locator", "#email"]
        assert action.args["value"] == "test@example.com"

    def test_fill_by_label(self, parser: PyAstParser) -> None:
        """get_by_label + fill パターンを認識できること。"""
        source = 'page.get_by_label("Email").fill("test@example.com")'
        actions = parser.parse(source)

        assert len(actions) == 1
        action = actions[0]
        assert action.action_type == "fill"
        assert action.locator_chain == ["get_by_label", "Email"]
        assert action.args["value"] == "test@example.com"

    def test_fill_by_placeholder(self, parser: PyAstParser) -> None:
        """get_by_placeholder + fill パターンを認識できること。"""
        source = 'page.get_by_placeholder("Enter email").fill("test@example.com")'
        actions = parser.parse(source)

        assert len(actions) == 1
        action = actions[0]
        assert action.action_type == "fill"
        assert action.locator_chain == ["get_by_placeholder", "Enter email"]
        assert action.args["value"] == "test@example.com"

    def test_fill_by_role(self, parser: PyAstParser) -> None:
        """get_by_role + fill パターンを認識できること。"""
        source = 'page.get_by_role("textbox", name="Email").fill("user@test.com")'
        actions = parser.parse(source)

        assert len(actions) == 1
        action = actions[0]
        assert action.action_type == "fill"
        assert "get_by_role" in action.locator_chain
        assert "textbox" in action.locator_chain
        assert "name=Email" in action.locator_chain
        assert action.args["value"] == "user@test.com"


# ===========================================================================
# 4. press パターン
# ===========================================================================

class TestPressPattern:
    """press パターンの認識テスト。"""

    def test_press_enter(self, parser: PyAstParser) -> None:
        """get_by_role + press("Enter") パターンを認識できること。"""
        source = 'page.get_by_role("textbox").press("Enter")'
        actions = parser.parse(source)

        assert len(actions) == 1
        action = actions[0]
        assert action.action_type == "press"
        assert action.args["key"] == "Enter"

    def test_press_tab(self, parser: PyAstParser) -> None:
        """press("Tab") パターンを認識できること。"""
        source = 'page.get_by_role("textbox", name="Name").press("Tab")'
        actions = parser.parse(source)

        assert len(actions) == 1
        assert actions[0].action_type == "press"
        assert actions[0].args["key"] == "Tab"


# ===========================================================================
# 5. check / uncheck パターン
# ===========================================================================

class TestCheckPattern:
    """check / uncheck パターンの認識テスト。"""

    def test_check(self, parser: PyAstParser) -> None:
        """get_by_role("checkbox") + check パターンを認識できること。"""
        source = 'page.get_by_role("checkbox", name="Agree").check()'
        actions = parser.parse(source)

        assert len(actions) == 1
        action = actions[0]
        assert action.action_type == "check"
        assert "get_by_role" in action.locator_chain
        assert "checkbox" in action.locator_chain
        assert "name=Agree" in action.locator_chain

    def test_uncheck(self, parser: PyAstParser) -> None:
        """uncheck パターンを認識できること。"""
        source = 'page.get_by_role("checkbox", name="Newsletter").uncheck()'
        actions = parser.parse(source)

        assert len(actions) == 1
        assert actions[0].action_type == "uncheck"


# ===========================================================================
# 6. dblclick パターン
# ===========================================================================

class TestDblclickPattern:
    """dblclick パターンの認識テスト。"""

    def test_dblclick(self, parser: PyAstParser) -> None:
        """get_by_role + dblclick パターンを認識できること。"""
        source = 'page.get_by_role("cell", name="data").dblclick()'
        actions = parser.parse(source)

        assert len(actions) == 1
        action = actions[0]
        assert action.action_type == "dblclick"
        assert "get_by_role" in action.locator_chain
        assert "cell" in action.locator_chain
        assert "name=data" in action.locator_chain


# ===========================================================================
# 7. select_option パターン
# ===========================================================================

class TestSelectOptionPattern:
    """select_option パターンの認識テスト。"""

    def test_select_option(self, parser: PyAstParser) -> None:
        """get_by_role("combobox") + select_option パターンを認識できること。"""
        source = 'page.get_by_role("combobox").select_option("value")'
        actions = parser.parse(source)

        assert len(actions) == 1
        action = actions[0]
        assert action.action_type == "select_option"
        assert action.args["value"] == "value"


# ===========================================================================
# 8. expect 系パターン
# ===========================================================================

class TestExpectPattern:
    """expect パターンの認識テスト。"""

    def test_expect_visible(self, parser: PyAstParser) -> None:
        """expect(...).to_be_visible() パターンを認識できること。"""
        source = 'expect(page.get_by_role("heading", name="Welcome")).to_be_visible()'
        actions = parser.parse(source)

        assert len(actions) == 1
        action = actions[0]
        assert action.action_type == "expect_visible"
        assert "get_by_role" in action.locator_chain
        assert "heading" in action.locator_chain
        assert "name=Welcome" in action.locator_chain

    def test_expect_have_text(self, parser: PyAstParser) -> None:
        """expect(...).to_have_text("...") パターンを認識できること。"""
        source = 'expect(page.get_by_test_id("message")).to_have_text("Hello")'
        actions = parser.parse(source)

        assert len(actions) == 1
        action = actions[0]
        assert action.action_type == "expect_text"
        assert action.locator_chain == ["get_by_test_id", "message"]
        assert action.args["text"] == "Hello"

    def test_expect_have_url(self, parser: PyAstParser) -> None:
        """expect(page).to_have_url("...") パターンを認識できること。"""
        source = 'expect(page).to_have_url("https://example.com/dashboard")'
        actions = parser.parse(source)

        assert len(actions) == 1
        action = actions[0]
        assert action.action_type == "expect_url"
        assert action.args["url"] == "https://example.com/dashboard"
        assert action.locator_chain == []

    def test_expect_hidden(self, parser: PyAstParser) -> None:
        """expect(...).to_be_hidden() パターンを認識できること。"""
        source = 'expect(page.get_by_role("dialog")).to_be_hidden()'
        actions = parser.parse(source)

        assert len(actions) == 1
        action = actions[0]
        assert action.action_type == "expect_hidden"

    def test_expect_contain_text(self, parser: PyAstParser) -> None:
        """expect(...).to_contain_text("...") パターンを認識できること。"""
        source = 'expect(page.get_by_test_id("status")).to_contain_text("Success")'
        actions = parser.parse(source)

        assert len(actions) == 1
        action = actions[0]
        assert action.action_type == "expect_text"
        assert action.args["text"] == "Success"


# ===========================================================================
# 9. エッジケース
# ===========================================================================

class TestEdgeCases:
    """エッジケースのテスト。"""

    def test_empty_source(self, parser: PyAstParser) -> None:
        """空のソースコードで空リストが返ること。"""
        actions = parser.parse("")
        assert actions == []

    def test_whitespace_only_source(self, parser: PyAstParser) -> None:
        """空白のみのソースコードで空リストが返ること。"""
        actions = parser.parse("   \n\n  \t  ")
        assert actions == []

    def test_syntax_error(self, parser: PyAstParser) -> None:
        """構文エラーのソースコードで SyntaxError が発生すること。"""
        with pytest.raises(SyntaxError):
            parser.parse("def broken(")

    def test_no_playwright_code(self, parser: PyAstParser) -> None:
        """Playwright 以外のコードでは空リストが返ること。"""
        source = """\
x = 1 + 2
print("hello")
result = [i for i in range(10)]
"""
        actions = parser.parse(source)
        assert actions == []

    def test_unsupported_pattern_warning(
        self, parser: PyAstParser, caplog: pytest.LogCaptureFixture
    ) -> None:
        """未対応パターンで警告が出力されること。"""
        # page.some_unknown_method() は未対応
        source = 'page.some_unknown_method("arg")'
        with caplog.at_level(logging.WARNING):
            actions = parser.parse(source)

        # 未対応パターンなのでアクションは生成されない
        assert actions == []
        # 警告ログが出力されていること
        assert any("未対応" in record.message for record in caplog.records)


# ===========================================================================
# 10. 複数アクションの連続パース
# ===========================================================================

class TestMultipleActions:
    """複数アクションの連続パースのテスト。"""

    def test_login_flow(self, parser: PyAstParser) -> None:
        """ログインフロー全体を正しくパースできること。"""
        source = """\
page.goto("https://example.com/login")
page.get_by_label("Email").fill("test@example.com")
page.get_by_label("Password").fill("secret123")
page.get_by_role("button", name="ログイン").click()
expect(page).to_have_url("https://example.com/dashboard")
"""
        actions = parser.parse(source)

        assert len(actions) == 5
        assert actions[0].action_type == "goto"
        assert actions[1].action_type == "fill"
        assert actions[1].args["value"] == "test@example.com"
        assert actions[2].action_type == "fill"
        assert actions[2].args["value"] == "secret123"
        assert actions[3].action_type == "click"
        assert actions[4].action_type == "expect_url"

    def test_action_order_preserved(self, parser: PyAstParser) -> None:
        """アクションの順序が保持されること。"""
        source = """\
page.goto("https://example.com")
page.get_by_role("button", name="A").click()
page.get_by_role("button", name="B").click()
page.get_by_role("button", name="C").click()
"""
        actions = parser.parse(source)

        assert len(actions) == 4
        assert actions[0].action_type == "goto"
        # クリック順序の確認
        assert "name=A" in actions[1].locator_chain
        assert "name=B" in actions[2].locator_chain
        assert "name=C" in actions[3].locator_chain

    def test_line_numbers_sequential(self, parser: PyAstParser) -> None:
        """行番号が順序通りに記録されること。"""
        source = """\
page.goto("https://example.com")
page.get_by_role("button", name="OK").click()
expect(page.get_by_role("heading", name="Done")).to_be_visible()
"""
        actions = parser.parse(source)

        assert len(actions) == 3
        # 行番号が昇順であること
        for i in range(len(actions) - 1):
            assert actions[i].line_number < actions[i + 1].line_number


# ===========================================================================
# 11. locator チェーンの正確性
# ===========================================================================

class TestLocatorChainAccuracy:
    """locator チェーンの正確性テスト。"""

    def test_role_with_name_chain(self, parser: PyAstParser) -> None:
        """get_by_role + name のチェーンが正確であること。"""
        source = 'page.get_by_role("link", name="Home").click()'
        actions = parser.parse(source)

        assert actions[0].locator_chain == ["get_by_role", "link", "name=Home"]

    def test_test_id_chain(self, parser: PyAstParser) -> None:
        """get_by_test_id のチェーンが正確であること。"""
        source = 'page.get_by_test_id("submit-form").click()'
        actions = parser.parse(source)

        assert actions[0].locator_chain == ["get_by_test_id", "submit-form"]

    def test_locator_css_chain(self, parser: PyAstParser) -> None:
        """locator(css) のチェーンが正確であること。"""
        source = 'page.locator("div.container > input").fill("value")'
        actions = parser.parse(source)

        assert actions[0].locator_chain == ["locator", "div.container > input"]

    def test_get_by_label_chain(self, parser: PyAstParser) -> None:
        """get_by_label のチェーンが正確であること。"""
        source = 'page.get_by_label("Username").fill("admin")'
        actions = parser.parse(source)

        assert actions[0].locator_chain == ["get_by_label", "Username"]

    def test_expect_locator_chain(self, parser: PyAstParser) -> None:
        """expect 内のロケータチェーンが正確であること。"""
        source = 'expect(page.get_by_role("alert", name="Error")).to_be_visible()'
        actions = parser.parse(source)

        assert actions[0].locator_chain == ["get_by_role", "alert", "name=Error"]


# ===========================================================================
# 12. 実際の codegen 出力に近いテスト
# ===========================================================================

class TestRealisticCodegen:
    """Playwright codegen が実際に生成するコードに近いパターンのテスト。"""

    def test_full_codegen_script(self, parser: PyAstParser) -> None:
        """codegen が生成する完全なスクリプト形式をパースできること。

        関数定義やインポート文は無視し、page.xxx() のみを抽出する。
        """
        source = """\
import re
from playwright.sync_api import Playwright, expect

def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://example.com/")
    page.get_by_role("link", name="Sign In").click()
    page.get_by_label("Email address").fill("user@test.com")
    page.get_by_label("Password").fill("password123")
    page.get_by_role("button", name="Sign in").click()
    expect(page.get_by_role("heading", name="Dashboard")).to_be_visible()
    context.close()
    browser.close()
"""
        actions = parser.parse(source)

        # page.goto, click, fill, fill, click, expect の 6 アクション
        assert len(actions) == 6
        assert actions[0].action_type == "goto"
        assert actions[1].action_type == "click"
        assert actions[2].action_type == "fill"
        assert actions[3].action_type == "fill"
        assert actions[4].action_type == "click"
        assert actions[5].action_type == "expect_visible"

    def test_japanese_text_in_selectors(self, parser: PyAstParser) -> None:
        """日本語テキストを含むセレクタを正しく認識できること。"""
        source = """\
page.get_by_role("button", name="ログイン").click()
page.get_by_text("ようこそ").click()
expect(page.get_by_role("heading", name="ダッシュボード")).to_be_visible()
"""
        actions = parser.parse(source)

        assert len(actions) == 3
        assert "name=ログイン" in actions[0].locator_chain
        assert "ようこそ" in actions[1].locator_chain
        assert "name=ダッシュボード" in actions[2].locator_chain


# ===========================================================================
# 13. scroll 系パターン
# ===========================================================================

class TestScrollPattern:
    """scroll 系パターンの認識テスト。"""

    def test_mouse_wheel(self, parser: PyAstParser) -> None:
        """page.mouse.wheel(dx, dy) を scroll として認識できること。"""
        source = 'page.mouse.wheel(0, 1200)'
        actions = parser.parse(source)

        assert len(actions) == 1
        assert actions[0].action_type == "scroll"
        assert actions[0].args == {"deltaX": 0, "deltaY": 1200}

    def test_scroll_into_view_if_needed(self, parser: PyAstParser) -> None:
        """locator.scroll_into_view_if_needed() を認識できること。"""
        source = 'page.get_by_test_id("target").scroll_into_view_if_needed()'
        actions = parser.parse(source)

        assert len(actions) == 1
        assert actions[0].action_type == "scroll_into_view"
        assert actions[0].locator_chain == ["get_by_test_id", "target"]
