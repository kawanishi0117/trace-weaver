"""
SelectorMapper テスト — ref 番号から brt セレクタへの変換

SnapshotElement の role/name/属性情報から、
brt DSL の by セレクタ辞書を生成する機能を検証する。
"""

from __future__ import annotations

import pytest

from brt.mcp.selector_mapper import SelectorMapper
from brt.mcp.snapshot import SnapshotElement


# ---------------------------------------------------------------------------
# SelectorMapper のテスト
# ---------------------------------------------------------------------------

class TestSelectorMapper:
    """SelectorMapper の変換ロジックテスト。"""

    @pytest.fixture
    def mapper(self) -> SelectorMapper:
        return SelectorMapper()

    def test_button_to_role_selector(self, mapper: SelectorMapper):
        """button 要素が role セレクタに変換されること。"""
        elem = SnapshotElement(ref="1", role="button", name="Login")
        by = mapper.to_by_selector(elem)

        assert by == {"role": "button", "name": "Login"}

    def test_textbox_to_role_selector(self, mapper: SelectorMapper):
        """textbox 要素が role セレクタに変換されること。"""
        elem = SnapshotElement(ref="2", role="textbox", name="Email")
        by = mapper.to_by_selector(elem)

        assert by == {"role": "textbox", "name": "Email"}

    def test_link_to_role_selector(self, mapper: SelectorMapper):
        """link 要素が role セレクタに変換されること。"""
        elem = SnapshotElement(ref="3", role="link", name="About Us")
        by = mapper.to_by_selector(elem)

        assert by == {"role": "link", "name": "About Us"}

    def test_checkbox_to_role_selector(self, mapper: SelectorMapper):
        """checkbox 要素が role セレクタに変換されること。"""
        elem = SnapshotElement(ref="4", role="checkbox", name="Remember me")
        by = mapper.to_by_selector(elem)

        assert by == {"role": "checkbox", "name": "Remember me"}

    def test_element_without_name_uses_role_only(self, mapper: SelectorMapper):
        """name なしの要素は role のみのセレクタになること。"""
        elem = SnapshotElement(ref="5", role="button", name="")
        by = mapper.to_by_selector(elem)

        assert by == {"role": "button"}

    def test_heading_includes_level(self, mapper: SelectorMapper):
        """heading 要素に level 属性が含まれること。"""
        elem = SnapshotElement(
            ref="6", role="heading", name="Welcome",
            attributes={"level": "1"},
        )
        by = mapper.to_by_selector(elem)

        assert by["role"] == "heading"
        assert by["name"] == "Welcome"

    def test_combobox_to_role_selector(self, mapper: SelectorMapper):
        """combobox 要素が role セレクタに変換されること。"""
        elem = SnapshotElement(ref="7", role="combobox", name="Country")
        by = mapper.to_by_selector(elem)

        assert by == {"role": "combobox", "name": "Country"}

    def test_detect_secret_field(self, mapper: SelectorMapper):
        """パスワード系フィールドが secret 判定されること。"""
        elem = SnapshotElement(ref="8", role="textbox", name="Password")
        assert mapper.is_secret_field(elem) is True

    def test_non_secret_field(self, mapper: SelectorMapper):
        """通常フィールドが secret 判定されないこと。"""
        elem = SnapshotElement(ref="9", role="textbox", name="Email")
        assert mapper.is_secret_field(elem) is False
