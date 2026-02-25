"""
LocatorBuilder テスト — by セレクタ辞書から Playwright Locator への変換

全セレクタ種別（role, testId, label, placeholder, css, text）に対応した
Locator 構築ロジックを検証する。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from brt.mcp.locator_builder import build_locator


# ---------------------------------------------------------------------------
# モック Page の生成ヘルパー
# ---------------------------------------------------------------------------

def _make_mock_page() -> MagicMock:
    """Playwright Page のモックを生成する。"""
    page = MagicMock()
    page.get_by_role.return_value = MagicMock(name="role-locator")
    page.get_by_test_id.return_value = MagicMock(name="testid-locator")
    page.get_by_label.return_value = MagicMock(name="label-locator")
    page.get_by_placeholder.return_value = MagicMock(name="placeholder-locator")
    page.get_by_text.return_value = MagicMock(name="text-locator")
    page.locator.return_value = MagicMock(name="css-locator")
    return page


# ---------------------------------------------------------------------------
# role セレクタのテスト
# ---------------------------------------------------------------------------

class TestBuildLocatorRole:
    """role セレクタの Locator 構築テスト。"""

    def test_role_with_name(self):
        """role + name で get_by_role が呼ばれること。"""
        page = _make_mock_page()
        by = {"role": "button", "name": "Login"}

        result = build_locator(page, by)

        page.get_by_role.assert_called_once_with("button", name="Login")
        assert result == page.get_by_role.return_value

    def test_role_without_name(self):
        """role のみで get_by_role が呼ばれること。"""
        page = _make_mock_page()
        by = {"role": "textbox"}

        result = build_locator(page, by)

        page.get_by_role.assert_called_once_with("textbox")
        assert result == page.get_by_role.return_value

    def test_role_with_exact(self):
        """role + name + exact で get_by_role が呼ばれること。"""
        page = _make_mock_page()
        by = {"role": "link", "name": "Home", "exact": True}

        result = build_locator(page, by)

        page.get_by_role.assert_called_once_with("link", name="Home", exact=True)


# ---------------------------------------------------------------------------
# testId セレクタのテスト
# ---------------------------------------------------------------------------

class TestBuildLocatorTestId:
    """testId セレクタの Locator 構築テスト。"""

    def test_testid_selector(self):
        """testId で get_by_test_id が呼ばれること。"""
        page = _make_mock_page()
        by = {"testId": "login-button"}

        result = build_locator(page, by)

        page.get_by_test_id.assert_called_once_with("login-button")
        assert result == page.get_by_test_id.return_value


# ---------------------------------------------------------------------------
# label セレクタのテスト
# ---------------------------------------------------------------------------

class TestBuildLocatorLabel:
    """label セレクタの Locator 構築テスト。"""

    def test_label_selector(self):
        """label で get_by_label が呼ばれること。"""
        page = _make_mock_page()
        by = {"label": "Email Address"}

        result = build_locator(page, by)

        page.get_by_label.assert_called_once_with("Email Address")
        assert result == page.get_by_label.return_value


# ---------------------------------------------------------------------------
# placeholder セレクタのテスト
# ---------------------------------------------------------------------------

class TestBuildLocatorPlaceholder:
    """placeholder セレクタの Locator 構築テスト。"""

    def test_placeholder_selector(self):
        """placeholder で get_by_placeholder が呼ばれること。"""
        page = _make_mock_page()
        by = {"placeholder": "Enter your email"}

        result = build_locator(page, by)

        page.get_by_placeholder.assert_called_once_with("Enter your email")
        assert result == page.get_by_placeholder.return_value


# ---------------------------------------------------------------------------
# css セレクタのテスト
# ---------------------------------------------------------------------------

class TestBuildLocatorCss:
    """css セレクタの Locator 構築テスト。"""

    def test_css_selector(self):
        """css で page.locator が呼ばれること。"""
        page = _make_mock_page()
        by = {"css": ".btn-primary"}

        result = build_locator(page, by)

        page.locator.assert_called_once_with(".btn-primary")
        assert result == page.locator.return_value

    def test_css_with_text(self):
        """css + text で page.locator(has_text=) が呼ばれること。"""
        page = _make_mock_page()
        by = {"css": ".btn", "text": "Submit"}

        result = build_locator(page, by)

        page.locator.assert_called_once_with(".btn", has_text="Submit")


# ---------------------------------------------------------------------------
# text セレクタのテスト
# ---------------------------------------------------------------------------

class TestBuildLocatorText:
    """text セレクタの Locator 構築テスト。"""

    def test_text_selector(self):
        """text で get_by_text が呼ばれること。"""
        page = _make_mock_page()
        by = {"text": "Welcome"}

        result = build_locator(page, by)

        page.get_by_text.assert_called_once_with("Welcome")
        assert result == page.get_by_text.return_value


# ---------------------------------------------------------------------------
# 不正セレクタのテスト
# ---------------------------------------------------------------------------

class TestBuildLocatorInvalid:
    """不正なセレクタ辞書のエラーハンドリングテスト。"""

    def test_empty_dict_raises(self):
        """空の辞書で ValueError が発生すること。"""
        page = _make_mock_page()
        with pytest.raises(ValueError, match="セレクタ種別を特定できません"):
            build_locator(page, {})

    def test_unknown_keys_raises(self):
        """未知のキーのみで ValueError が発生すること。"""
        page = _make_mock_page()
        with pytest.raises(ValueError, match="セレクタ種別を特定できません"):
            build_locator(page, {"unknown": "value"})
