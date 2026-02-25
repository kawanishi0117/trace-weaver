"""
Mapper のユニットテスト

RawAction 中間表現から YAML DSL ステップへの変換を検証する。
テストは最低20個以上作成し、以下のカテゴリをカバーする:
  - 各 action_type の変換テスト（goto, click, fill, press, check, uncheck,
    dblclick, selectOption, expect 系）
  - 各 locator_chain パターンの by セレクタ変換テスト
  - locator 正規化テスト（css= プレフィックス除去、冪等性）
  - 空リスト入力テスト
  - 複数アクションの連続変換テスト
  - 未知の action_type の処理テスト
"""

from __future__ import annotations

import logging

import pytest

from src.importer.mapper import Mapper, normalize_locator
from src.importer.py_ast_parser import RawAction


# ---------------------------------------------------------------------------
# フィクスチャ
# ---------------------------------------------------------------------------

@pytest.fixture
def mapper() -> Mapper:
    """Mapper インスタンスを提供する。"""
    return Mapper()


# ===========================================================================
# 1. goto ステップの変換
# ===========================================================================

class TestGotoMapping:
    """goto アクションの変換テスト。"""

    def test_goto_simple(self, mapper: Mapper) -> None:
        """goto アクションが正しく変換されること。"""
        raw = RawAction(
            action_type="goto",
            locator_chain=[],
            args={"url": "https://example.com"},
            line_number=1,
        )
        result = mapper.map([raw])

        assert len(result) == 1
        assert result[0] == {"goto": {"url": "https://example.com"}}

    def test_goto_without_url(self, mapper: Mapper) -> None:
        """URL なしの goto でも空 dict が生成されること。"""
        raw = RawAction(action_type="goto", locator_chain=[], args={}, line_number=1)
        result = mapper.map([raw])

        assert len(result) == 1
        assert result[0] == {"goto": {}}


# ===========================================================================
# 2. click ステップの変換
# ===========================================================================

class TestClickMapping:
    """click アクションの変換テスト。"""

    def test_click_by_role_with_name(self, mapper: Mapper) -> None:
        """role + name の click が正しく変換されること。"""
        raw = RawAction(
            action_type="click",
            locator_chain=["get_by_role", "button", "name=Submit"],
            args={},
            line_number=1,
        )
        result = mapper.map([raw])

        assert result[0] == {"click": {"by": {"role": "button", "name": "Submit"}}}

    def test_click_by_role_without_name(self, mapper: Mapper) -> None:
        """role のみの click が正しく変換されること。"""
        raw = RawAction(
            action_type="click",
            locator_chain=["get_by_role", "textbox"],
            args={},
            line_number=1,
        )
        result = mapper.map([raw])

        assert result[0] == {"click": {"by": {"role": "textbox"}}}

    def test_click_by_test_id(self, mapper: Mapper) -> None:
        """testId の click が正しく変換されること。"""
        raw = RawAction(
            action_type="click",
            locator_chain=["get_by_test_id", "login-btn"],
            args={},
            line_number=1,
        )
        result = mapper.map([raw])

        assert result[0] == {"click": {"by": {"testId": "login-btn"}}}

    def test_click_by_text(self, mapper: Mapper) -> None:
        """text の click が正しく変換されること。"""
        raw = RawAction(
            action_type="click",
            locator_chain=["get_by_text", "Submit"],
            args={},
            line_number=1,
        )
        result = mapper.map([raw])

        assert result[0] == {"click": {"by": {"text": "Submit"}}}

    def test_click_by_label(self, mapper: Mapper) -> None:
        """label の click が正しく変換されること。"""
        raw = RawAction(
            action_type="click",
            locator_chain=["get_by_label", "Accept terms"],
            args={},
            line_number=1,
        )
        result = mapper.map([raw])

        assert result[0] == {"click": {"by": {"label": "Accept terms"}}}

    def test_click_by_placeholder(self, mapper: Mapper) -> None:
        """placeholder の click が正しく変換されること。"""
        raw = RawAction(
            action_type="click",
            locator_chain=["get_by_placeholder", "Search..."],
            args={},
            line_number=1,
        )
        result = mapper.map([raw])

        assert result[0] == {"click": {"by": {"placeholder": "Search..."}}}

    def test_click_by_css(self, mapper: Mapper) -> None:
        """CSS セレクタの click が正しく変換されること。"""
        raw = RawAction(
            action_type="click",
            locator_chain=["locator", "#email"],
            args={},
            line_number=1,
        )
        result = mapper.map([raw])

        assert result[0] == {"click": {"by": {"css": "#email"}}}


# ===========================================================================
# 3. fill ステップの変換
# ===========================================================================

class TestFillMapping:
    """fill アクションの変換テスト。"""

    def test_fill_by_label(self, mapper: Mapper) -> None:
        """label + fill が正しく変換されること。"""
        raw = RawAction(
            action_type="fill",
            locator_chain=["get_by_label", "Email"],
            args={"value": "test@example.com"},
            line_number=1,
        )
        result = mapper.map([raw])

        assert result[0] == {
            "fill": {"by": {"label": "Email"}, "value": "test@example.com"},
        }

    def test_fill_by_css(self, mapper: Mapper) -> None:
        """CSS セレクタ + fill が正しく変換されること。"""
        raw = RawAction(
            action_type="fill",
            locator_chain=["locator", "#email"],
            args={"value": "test@example.com"},
            line_number=1,
        )
        result = mapper.map([raw])

        assert result[0] == {
            "fill": {"by": {"css": "#email"}, "value": "test@example.com"},
        }

    def test_fill_by_placeholder(self, mapper: Mapper) -> None:
        """placeholder + fill が正しく変換されること。"""
        raw = RawAction(
            action_type="fill",
            locator_chain=["get_by_placeholder", "Enter email"],
            args={"value": "user@test.com"},
            line_number=1,
        )
        result = mapper.map([raw])

        assert result[0] == {
            "fill": {"by": {"placeholder": "Enter email"}, "value": "user@test.com"},
        }


# ===========================================================================
# 4. press ステップの変換
# ===========================================================================

class TestPressMapping:
    """press アクションの変換テスト。"""

    def test_press_enter(self, mapper: Mapper) -> None:
        """press("Enter") が正しく変換されること。"""
        raw = RawAction(
            action_type="press",
            locator_chain=["get_by_role", "textbox"],
            args={"key": "Enter"},
            line_number=1,
        )
        result = mapper.map([raw])

        assert result[0] == {
            "press": {"by": {"role": "textbox"}, "key": "Enter"},
        }


# ===========================================================================
# 5. check / uncheck ステップの変換
# ===========================================================================

class TestCheckMapping:
    """check / uncheck アクションの変換テスト。"""

    def test_check(self, mapper: Mapper) -> None:
        """check が正しく変換されること。"""
        raw = RawAction(
            action_type="check",
            locator_chain=["get_by_role", "checkbox", "name=Agree"],
            args={},
            line_number=1,
        )
        result = mapper.map([raw])

        assert result[0] == {
            "check": {"by": {"role": "checkbox", "name": "Agree"}},
        }

    def test_uncheck(self, mapper: Mapper) -> None:
        """uncheck が正しく変換されること。"""
        raw = RawAction(
            action_type="uncheck",
            locator_chain=["get_by_role", "checkbox", "name=Newsletter"],
            args={},
            line_number=1,
        )
        result = mapper.map([raw])

        assert result[0] == {
            "uncheck": {"by": {"role": "checkbox", "name": "Newsletter"}},
        }


# ===========================================================================
# 6. dblclick ステップの変換
# ===========================================================================

class TestDblclickMapping:
    """dblclick アクションの変換テスト。"""

    def test_dblclick(self, mapper: Mapper) -> None:
        """dblclick が正しく変換されること。"""
        raw = RawAction(
            action_type="dblclick",
            locator_chain=["get_by_role", "cell", "name=data"],
            args={},
            line_number=1,
        )
        result = mapper.map([raw])

        assert result[0] == {
            "dblclick": {"by": {"role": "cell", "name": "data"}},
        }


# ===========================================================================
# 7. selectOption ステップの変換
# ===========================================================================

class TestSelectOptionMapping:
    """selectOption アクションの変換テスト。"""

    def test_select_option(self, mapper: Mapper) -> None:
        """select_option が selectOption に正しく変換されること。"""
        raw = RawAction(
            action_type="select_option",
            locator_chain=["get_by_role", "combobox"],
            args={"value": "option1"},
            line_number=1,
        )
        result = mapper.map([raw])

        assert result[0] == {
            "selectOption": {"by": {"role": "combobox"}, "value": "option1"},
        }


# ===========================================================================
# 8. expect 系ステップの変換
# ===========================================================================

class TestExpectMapping:
    """expect 系アクションの変換テスト。"""

    def test_expect_visible(self, mapper: Mapper) -> None:
        """expect_visible が expectVisible に正しく変換されること。"""
        raw = RawAction(
            action_type="expect_visible",
            locator_chain=["get_by_role", "heading", "name=Welcome"],
            args={},
            line_number=1,
        )
        result = mapper.map([raw])

        assert result[0] == {
            "expectVisible": {"by": {"role": "heading", "name": "Welcome"}},
        }

    def test_expect_hidden(self, mapper: Mapper) -> None:
        """expect_hidden が expectHidden に正しく変換されること。"""
        raw = RawAction(
            action_type="expect_hidden",
            locator_chain=["get_by_role", "dialog"],
            args={},
            line_number=1,
        )
        result = mapper.map([raw])

        assert result[0] == {
            "expectHidden": {"by": {"role": "dialog"}},
        }

    def test_expect_text(self, mapper: Mapper) -> None:
        """expect_text が expectText に正しく変換されること。"""
        raw = RawAction(
            action_type="expect_text",
            locator_chain=["get_by_test_id", "message"],
            args={"text": "Hello"},
            line_number=1,
        )
        result = mapper.map([raw])

        assert result[0] == {
            "expectText": {"by": {"testId": "message"}, "text": "Hello"},
        }

    def test_expect_url(self, mapper: Mapper) -> None:
        """expect_url が expectUrl に正しく変換されること。"""
        raw = RawAction(
            action_type="expect_url",
            locator_chain=[],
            args={"url": "https://example.com/dashboard"},
            line_number=1,
        )
        result = mapper.map([raw])

        assert result[0] == {
            "expectUrl": {"url": "https://example.com/dashboard"},
        }


# ===========================================================================
# 9. locator 正規化テスト
# ===========================================================================

class TestNormalizeLocator:
    """locator 文字列の正規化テスト。"""

    def test_css_prefix_removal(self) -> None:
        """css= プレフィックスが除去されること。"""
        assert normalize_locator("css=#email") == "#email"

    def test_css_prefix_with_complex_selector(self) -> None:
        """複雑な CSS セレクタでも css= プレフィックスが除去されること。"""
        assert normalize_locator("css=div.container > input") == "div.container > input"

    def test_no_prefix(self) -> None:
        """プレフィックスなしの場合はそのまま返ること。"""
        assert normalize_locator("#email") == "#email"

    def test_idempotent_single(self) -> None:
        """正規化が冪等であること（1回適用と2回適用で同じ結果）。"""
        original = "css=#email"
        once = normalize_locator(original)
        twice = normalize_locator(once)
        assert once == twice

    def test_idempotent_no_prefix(self) -> None:
        """プレフィックスなしの場合も冪等であること。"""
        original = "div.container"
        once = normalize_locator(original)
        twice = normalize_locator(once)
        assert once == twice

    def test_css_prefix_in_fill_step(self, mapper: Mapper) -> None:
        """fill ステップ内で css= プレフィックスが正規化されること。"""
        raw = RawAction(
            action_type="fill",
            locator_chain=["locator", "css=#email"],
            args={"value": "test@example.com"},
            line_number=1,
        )
        result = mapper.map([raw])

        # css= プレフィックスが除去されていること
        assert result[0] == {
            "fill": {"by": {"css": "#email"}, "value": "test@example.com"},
        }


# ===========================================================================
# 10. エッジケース
# ===========================================================================

class TestEdgeCases:
    """エッジケースのテスト。"""

    def test_empty_list(self, mapper: Mapper) -> None:
        """空リスト入力で空リストが返ること。"""
        result = mapper.map([])
        assert result == []

    def test_unknown_action_type(
        self, mapper: Mapper, caplog: pytest.LogCaptureFixture
    ) -> None:
        """未知の action_type で警告が出力され、スキップされること。"""
        raw = RawAction(
            action_type="unknown_action",
            locator_chain=["get_by_role", "button"],
            args={},
            line_number=42,
        )
        with caplog.at_level(logging.WARNING):
            result = mapper.map([raw])

        assert result == []
        assert any("未知の action_type" in r.message for r in caplog.records)

    def test_empty_locator_chain_for_click(
        self, mapper: Mapper, caplog: pytest.LogCaptureFixture
    ) -> None:
        """ロケータが必要なステップで locator_chain が空の場合スキップされること。"""
        raw = RawAction(
            action_type="click",
            locator_chain=[],
            args={},
            line_number=10,
        )
        with caplog.at_level(logging.WARNING):
            result = mapper.map([raw])

        assert result == []


# ===========================================================================
# 11. 複数アクションの連続変換
# ===========================================================================

class TestMultipleActions:
    """複数アクションの連続変換テスト。"""

    def test_login_flow(self, mapper: Mapper) -> None:
        """ログインフロー全体が正しく変換されること。"""
        raw_actions = [
            RawAction(
                action_type="goto",
                locator_chain=[],
                args={"url": "https://example.com/login"},
                line_number=1,
            ),
            RawAction(
                action_type="fill",
                locator_chain=["get_by_label", "Email"],
                args={"value": "test@example.com"},
                line_number=2,
            ),
            RawAction(
                action_type="fill",
                locator_chain=["get_by_label", "Password"],
                args={"value": "secret123"},
                line_number=3,
            ),
            RawAction(
                action_type="click",
                locator_chain=["get_by_role", "button", "name=ログイン"],
                args={},
                line_number=4,
            ),
            RawAction(
                action_type="expect_url",
                locator_chain=[],
                args={"url": "https://example.com/dashboard"},
                line_number=5,
            ),
        ]
        result = mapper.map(raw_actions)

        assert len(result) == 5
        assert result[0] == {"goto": {"url": "https://example.com/login"}}
        assert result[1] == {
            "fill": {"by": {"label": "Email"}, "value": "test@example.com"},
        }
        assert result[2] == {
            "fill": {"by": {"label": "Password"}, "value": "secret123"},
        }
        assert result[3] == {
            "click": {"by": {"role": "button", "name": "ログイン"}},
        }
        assert result[4] == {
            "expectUrl": {"url": "https://example.com/dashboard"},
        }

    def test_order_preserved(self, mapper: Mapper) -> None:
        """変換後のステップ順序が入力順序と一致すること。"""
        raw_actions = [
            RawAction(
                action_type="click",
                locator_chain=["get_by_role", "button", "name=A"],
                args={},
                line_number=1,
            ),
            RawAction(
                action_type="click",
                locator_chain=["get_by_role", "button", "name=B"],
                args={},
                line_number=2,
            ),
            RawAction(
                action_type="click",
                locator_chain=["get_by_role", "button", "name=C"],
                args={},
                line_number=3,
            ),
        ]
        result = mapper.map(raw_actions)

        assert len(result) == 3
        assert result[0]["click"]["by"]["name"] == "A"
        assert result[1]["click"]["by"]["name"] == "B"
        assert result[2]["click"]["by"]["name"] == "C"

    def test_unknown_actions_skipped_in_sequence(self, mapper: Mapper) -> None:
        """連続変換中に未知のアクションがスキップされ、他は正常に変換されること。"""
        raw_actions = [
            RawAction(
                action_type="goto",
                locator_chain=[],
                args={"url": "https://example.com"},
                line_number=1,
            ),
            RawAction(
                action_type="unknown_type",
                locator_chain=[],
                args={},
                line_number=2,
            ),
            RawAction(
                action_type="click",
                locator_chain=["get_by_role", "button", "name=OK"],
                args={},
                line_number=3,
            ),
        ]
        result = mapper.map(raw_actions)

        # 未知のアクションはスキップされ、2件のみ
        assert len(result) == 2
        assert result[0] == {"goto": {"url": "https://example.com"}}
        assert result[1] == {"click": {"by": {"role": "button", "name": "OK"}}}


# ===========================================================================
# 12. 日本語テキストの変換
# ===========================================================================

class TestJapaneseText:
    """日本語テキストを含むアクションの変換テスト。"""

    def test_japanese_role_name(self, mapper: Mapper) -> None:
        """日本語の name を含む role セレクタが正しく変換されること。"""
        raw = RawAction(
            action_type="click",
            locator_chain=["get_by_role", "button", "name=送信"],
            args={},
            line_number=1,
        )
        result = mapper.map([raw])

        assert result[0] == {"click": {"by": {"role": "button", "name": "送信"}}}

    def test_japanese_text_selector(self, mapper: Mapper) -> None:
        """日本語の text セレクタが正しく変換されること。"""
        raw = RawAction(
            action_type="click",
            locator_chain=["get_by_text", "ようこそ"],
            args={},
            line_number=1,
        )
        result = mapper.map([raw])

        assert result[0] == {"click": {"by": {"text": "ようこそ"}}}


# ===========================================================================
# 12. scroll ステップの変換
# ===========================================================================

class TestScrollMapping:
    """scroll / scrollIntoView の変換テスト。"""

    def test_scroll_from_mouse_wheel(self, mapper: Mapper) -> None:
        raw = RawAction(
            action_type="scroll",
            locator_chain=[],
            args={"deltaX": 0, "deltaY": 900},
            line_number=1,
        )
        result = mapper.map([raw])
        assert result[0] == {"scroll": {"deltaX": 0, "deltaY": 900}}

    def test_scroll_into_view(self, mapper: Mapper) -> None:
        raw = RawAction(
            action_type="scroll_into_view",
            locator_chain=["get_by_test_id", "grid-row-200"],
            args={},
            line_number=1,
        )
        result = mapper.map([raw])
        assert result[0] == {"scrollIntoView": {"by": {"testId": "grid-row-200"}}}
