"""
Snapshot テスト — アクセシビリティスナップショットの解析・ref 管理

Playwright の aria_snapshot() 出力を解析し、
各要素に ref 番号を付与して AI が操作対象を指定できるようにする。
"""

from __future__ import annotations

import pytest

from brt.mcp.snapshot import SnapshotParser, SnapshotElement


# ---------------------------------------------------------------------------
# SnapshotElement のテスト
# ---------------------------------------------------------------------------

class TestSnapshotElement:
    """SnapshotElement データクラスのテスト。"""

    def test_create_element(self):
        """要素を正しく生成できること。"""
        elem = SnapshotElement(
            ref="1",
            role="button",
            name="Login",
            level=0,
        )
        assert elem.ref == "1"
        assert elem.role == "button"
        assert elem.name == "Login"

    def test_display_string(self):
        """表示用文字列が正しく生成されること。"""
        elem = SnapshotElement(ref="3", role="textbox", name="Email")
        assert "[3]" in elem.display()
        assert "textbox" in elem.display()
        assert "Email" in elem.display()

    def test_display_string_without_name(self):
        """name なしの要素も表示できること。"""
        elem = SnapshotElement(ref="5", role="img", name="")
        display = elem.display()
        assert "[5]" in display
        assert "img" in display


# ---------------------------------------------------------------------------
# SnapshotParser のテスト
# ---------------------------------------------------------------------------

class TestSnapshotParser:
    """SnapshotParser の ARIA スナップショット解析テスト。"""

    @pytest.fixture
    def parser(self) -> SnapshotParser:
        return SnapshotParser()

    def test_parse_simple_snapshot(self, parser: SnapshotParser):
        """単純なスナップショットを解析できること。"""
        aria_yaml = (
            "- heading \"todos\" [level=1]\n"
            "- textbox \"What needs to be done?\"\n"
        )
        elements = parser.parse(aria_yaml)

        assert len(elements) >= 2
        # heading と textbox が含まれること
        roles = [e.role for e in elements]
        assert "heading" in roles
        assert "textbox" in roles

    def test_ref_numbers_are_sequential(self, parser: SnapshotParser):
        """ref 番号が連番で付与されること。"""
        aria_yaml = (
            "- button \"Save\"\n"
            "- button \"Cancel\"\n"
            "- link \"Help\"\n"
        )
        elements = parser.parse(aria_yaml)
        refs = [e.ref for e in elements]
        assert refs == ["1", "2", "3"]

    def test_parse_nested_snapshot(self, parser: SnapshotParser):
        """ネストされたスナップショットを解析できること。"""
        aria_yaml = (
            "- navigation:\n"
            "  - link \"Home\"\n"
            "  - link \"About\"\n"
            "- main:\n"
            "  - heading \"Welcome\" [level=1]\n"
            "  - button \"Get Started\"\n"
        )
        elements = parser.parse(aria_yaml)

        # インタラクティブ要素が抽出されること
        roles = [e.role for e in elements]
        assert "link" in roles
        assert "button" in roles

    def test_get_element_by_ref(self, parser: SnapshotParser):
        """ref 番号で要素を取得できること。"""
        aria_yaml = (
            "- button \"Save\"\n"
            "- button \"Cancel\"\n"
        )
        elements = parser.parse(aria_yaml)
        parser.set_elements(elements)

        elem = parser.get_by_ref("1")
        assert elem is not None
        assert elem.name == "Save"

    def test_get_element_by_invalid_ref(self, parser: SnapshotParser):
        """存在しない ref で None が返ること。"""
        parser.set_elements([])
        assert parser.get_by_ref("999") is None

    def test_format_for_ai(self, parser: SnapshotParser):
        """AI 向けのフォーマット文字列を生成できること。"""
        aria_yaml = (
            "- heading \"Login\" [level=1]\n"
            "- textbox \"Email\"\n"
            "- textbox \"Password\"\n"
            "- button \"Sign In\"\n"
        )
        elements = parser.parse(aria_yaml)
        parser.set_elements(elements)

        formatted = parser.format_for_ai()
        assert "[1]" in formatted
        assert "heading" in formatted
        assert "Sign In" in formatted

    def test_parse_empty_snapshot(self, parser: SnapshotParser):
        """空のスナップショットで空リストが返ること。"""
        elements = parser.parse("")
        assert elements == []

    def test_extract_attributes(self, parser: SnapshotParser):
        """属性（level 等）が抽出されること。"""
        aria_yaml = '- heading "Welcome" [level=2]\n'
        elements = parser.parse(aria_yaml)

        assert len(elements) >= 1
        heading = [e for e in elements if e.role == "heading"][0]
        assert heading.attributes.get("level") == "2"
