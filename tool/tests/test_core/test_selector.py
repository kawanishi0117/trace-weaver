"""
????????????????

Playwright ? Page / Locator ?????unittest.mock????????????
??????????????

?????:
  - ??????????? Playwright ???????????????
  - strict: true ??????????????
  - any ????????????????????
  - ????????????????????????????
  - healing: off ?????????????
  - healing: safe ????????????
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from src.core.selector import (
    SelectorResolutionError,
    SelectorResolver,
    _describe_selector,
)
from src.dsl.schema import (
    AnySelector,
    CssSelector,
    LabelSelector,
    PlaceholderSelector,
    RoleSelector,
    TestIdSelector,
    TextSelector,
)


# ---------------------------------------------------------------------------
# ????: ??? Page / Locator ???
# ---------------------------------------------------------------------------

def _make_mock_locator(*, count: int = 1, visible: bool = True) -> MagicMock:
    """??? Locator ??????"""
    locator = MagicMock()
    locator.count = AsyncMock(return_value=count)
    locator.is_visible = AsyncMock(return_value=visible)
    return locator


def _make_mock_page(**locator_overrides: MagicMock) -> MagicMock:
    """??? Page ??????

    ? get_by_* / locator ???????????
    count=1, visible=True ? Locator ????
    locator_overrides ?????????????
    """
    default_locator = _make_mock_locator()
    page = MagicMock()
    page.get_by_test_id = MagicMock(
        return_value=locator_overrides.get("get_by_test_id", default_locator)
    )
    page.get_by_role = MagicMock(
        return_value=locator_overrides.get("get_by_role", default_locator)
    )
    page.get_by_label = MagicMock(
        return_value=locator_overrides.get("get_by_label", default_locator)
    )
    page.get_by_placeholder = MagicMock(
        return_value=locator_overrides.get("get_by_placeholder", default_locator)
    )
    page.get_by_text = MagicMock(
        return_value=locator_overrides.get("get_by_text", default_locator)
    )
    page.locator = MagicMock(
        return_value=locator_overrides.get("locator", default_locator)
    )
    return page


# ---------------------------------------------------------------------------
# ???: _resolve_single - ?????????????
# ---------------------------------------------------------------------------

class TestResolveSingle:
    """_resolve_single ?????????"""

    def test_test_id_selector(self) -> None:
        """TestIdSelector ? page.get_by_test_id(testId) ????????????"""
        page = _make_mock_page()
        resolver = SelectorResolver()
        selector = TestIdSelector(testId="submit-btn")

        result = resolver._resolve_single(page, selector)

        page.get_by_test_id.assert_called_once_with("submit-btn")
        assert result == page.get_by_test_id.return_value

    def test_role_selector_with_name(self) -> None:
        """RoleSelector(name ??) ? page.get_by_role(role, name=name) ????????????"""
        page = _make_mock_page()
        resolver = SelectorResolver()
        selector = RoleSelector(role="button", name="????")

        result = resolver._resolve_single(page, selector)

        page.get_by_role.assert_called_once_with("button", name="????")
        assert result == page.get_by_role.return_value

    def test_role_selector_without_name(self) -> None:
        """RoleSelector(name ??) ? page.get_by_role(role) ????????????"""
        page = _make_mock_page()
        resolver = SelectorResolver()
        selector = RoleSelector(role="textbox")

        result = resolver._resolve_single(page, selector)

        page.get_by_role.assert_called_once_with("textbox")
        assert result == page.get_by_role.return_value

    def test_label_selector(self) -> None:
        """LabelSelector ? page.get_by_label(label) ????????????"""
        page = _make_mock_page()
        resolver = SelectorResolver()
        selector = LabelSelector(label="???????")

        result = resolver._resolve_single(page, selector)

        page.get_by_label.assert_called_once_with("???????")
        assert result == page.get_by_label.return_value

    def test_placeholder_selector(self) -> None:
        """PlaceholderSelector ? page.get_by_placeholder ????????????"""
        page = _make_mock_page()
        resolver = SelectorResolver()
        selector = PlaceholderSelector(placeholder="?????")

        result = resolver._resolve_single(page, selector)

        page.get_by_placeholder.assert_called_once_with("?????")
        assert result == page.get_by_placeholder.return_value

    def test_css_selector_without_text(self) -> None:
        """CssSelector(text ??) ? page.locator(css) ????????????"""
        page = _make_mock_page()
        resolver = SelectorResolver()
        selector = CssSelector(css="#email-input")

        result = resolver._resolve_single(page, selector)

        page.locator.assert_called_once_with("#email-input")
        assert result == page.locator.return_value

    def test_css_selector_with_text(self) -> None:
        """CssSelector(text ??) ? page.locator(css, has_text=text) ????????????"""
        page = _make_mock_page()
        resolver = SelectorResolver()
        selector = CssSelector(css=".btn", text="??")

        result = resolver._resolve_single(page, selector)

        page.locator.assert_called_once_with(".btn", has_text="??")
        assert result == page.locator.return_value

    def test_text_selector(self) -> None:
        """TextSelector ? page.get_by_text(text) ????????????"""
        page = _make_mock_page()
        resolver = SelectorResolver()
        selector = TextSelector(text="????")

        result = resolver._resolve_single(page, selector)

        page.get_by_text.assert_called_once_with("????")
        assert result == page.get_by_text.return_value


# ---------------------------------------------------------------------------
# ???: strict ?????????
# ---------------------------------------------------------------------------

class TestStrictDefault:
    """strict: true ???????????????????"""

    def test_test_id_strict_default(self) -> None:
        selector = TestIdSelector(testId="btn")
        assert selector.strict is True

    def test_role_strict_default(self) -> None:
        selector = RoleSelector(role="button")
        assert selector.strict is True

    def test_label_strict_default(self) -> None:
        selector = LabelSelector(label="??")
        assert selector.strict is True

    def test_placeholder_strict_default(self) -> None:
        selector = PlaceholderSelector(placeholder="??")
        assert selector.strict is True

    def test_css_strict_default(self) -> None:
        selector = CssSelector(css=".cls")
        assert selector.strict is True

    def test_text_strict_default(self) -> None:
        selector = TextSelector(text="hello")
        assert selector.strict is True


# ---------------------------------------------------------------------------
# ???: resolve - AnySelector ????????
# ---------------------------------------------------------------------------

class TestResolveAny:
    """any ????????????"""

    def test_any_first_candidate_succeeds(self) -> None:
        """??????????????????????????"""
        first_locator = _make_mock_locator(count=1, visible=True)
        second_locator = _make_mock_locator(count=1, visible=True)

        page = MagicMock()
        page.get_by_test_id = MagicMock(return_value=first_locator)
        page.get_by_role = MagicMock(return_value=second_locator)

        selector = AnySelector(any=[
            TestIdSelector(testId="btn"),
            RoleSelector(role="button", name="??"),
        ])
        resolver = SelectorResolver()

        result = asyncio.run(
            resolver.resolve(page, selector)
        )

        assert result == first_locator
        page.get_by_role.assert_not_called()

    def test_any_second_candidate_succeeds(self) -> None:
        """??????????2??????????"""
        first_locator = _make_mock_locator(count=0, visible=False)
        second_locator = _make_mock_locator(count=1, visible=True)

        page = MagicMock()
        page.get_by_test_id = MagicMock(return_value=first_locator)
        page.get_by_role = MagicMock(return_value=second_locator)

        selector = AnySelector(any=[
            TestIdSelector(testId="missing"),
            RoleSelector(role="button", name="??"),
        ])
        resolver = SelectorResolver()

        result = asyncio.run(
            resolver.resolve(page, selector)
        )

        assert result == second_locator

    def test_any_skips_invisible_candidate(self) -> None:
        """visible=False ??????????????"""
        invisible_locator = _make_mock_locator(count=1, visible=False)
        visible_locator = _make_mock_locator(count=1, visible=True)

        page = MagicMock()
        page.get_by_test_id = MagicMock(return_value=invisible_locator)
        page.get_by_label = MagicMock(return_value=visible_locator)

        selector = AnySelector(any=[
            TestIdSelector(testId="hidden-btn"),
            LabelSelector(label="?????"),
        ])
        resolver = SelectorResolver()

        result = asyncio.run(
            resolver.resolve(page, selector)
        )

        assert result == visible_locator

    def test_any_skips_multiple_hits(self) -> None:
        """strict ?????(?????)??????????????"""
        multi_locator = _make_mock_locator(count=3, visible=True)
        single_locator = _make_mock_locator(count=1, visible=True)

        page = MagicMock()
        page.get_by_text = MagicMock(return_value=multi_locator)
        page.get_by_test_id = MagicMock(return_value=single_locator)

        selector = AnySelector(any=[
            TextSelector(text="??????"),
            TestIdSelector(testId="unique-btn"),
        ])
        resolver = SelectorResolver()

        result = asyncio.run(
            resolver.resolve(page, selector)
        )

        assert result == single_locator

    def test_any_all_candidates_fail(self) -> None:
        """?????????????????????????????????"""
        empty_locator = _make_mock_locator(count=0)

        page = MagicMock()
        page.get_by_test_id = MagicMock(return_value=empty_locator)
        page.get_by_role = MagicMock(return_value=empty_locator)
        page.get_by_label = MagicMock(return_value=empty_locator)

        selector = AnySelector(any=[
            TestIdSelector(testId="btn-a"),
            RoleSelector(role="button", name="??"),
            LabelSelector(label="???"),
        ])
        resolver = SelectorResolver()

        with pytest.raises(SelectorResolutionError) as exc_info:
            asyncio.run(
                resolver.resolve(page, selector)
            )

        error_msg = str(exc_info.value)
        assert "全 3 候補" in error_msg
        assert "testId='btn-a'" in error_msg
        assert "role='button'" in error_msg
        assert "label='???'" in error_msg
        assert "0件ヒット" in error_msg


# ---------------------------------------------------------------------------
# ???: Healing (safe / off ???)
# ---------------------------------------------------------------------------

class TestHealing:
    """healing ????????"""

    def test_healing_off_raises_immediately(self) -> None:
        """healing: off ??????????????????????????"""
        page = MagicMock()
        page.get_by_test_id = MagicMock(side_effect=Exception("??????????"))

        resolver = SelectorResolver(healing="off")
        selector = TestIdSelector(testId="missing")

        with pytest.raises(SelectorResolutionError):
            asyncio.run(
                resolver.resolve(page, selector)
            )

    def test_healing_safe_tries_alternatives(self) -> None:
        """healing: safe ??????????????????????????????"""
        page = MagicMock()
        page.get_by_test_id = MagicMock(side_effect=Exception("??????????"))

        healed_locator = _make_mock_locator(count=1, visible=True)
        page.get_by_role = MagicMock(return_value=healed_locator)
        page.get_by_label = MagicMock(return_value=_make_mock_locator(count=0))

        resolver = SelectorResolver(healing="safe")
        selector = TestIdSelector(testId="submit-btn")

        result = asyncio.run(
            resolver.resolve(page, selector)
        )

        assert result == healed_locator

    def test_healing_safe_all_fail(self) -> None:
        """healing: safe ?????????????????????"""
        page = MagicMock()
        page.get_by_test_id = MagicMock(side_effect=Exception("not found"))
        page.get_by_role = MagicMock(return_value=_make_mock_locator(count=0))
        page.get_by_label = MagicMock(return_value=_make_mock_locator(count=0))

        resolver = SelectorResolver(healing="safe")
        selector = TestIdSelector(testId="missing-btn")

        with pytest.raises(SelectorResolutionError):
            asyncio.run(
                resolver.resolve(page, selector)
            )

    def test_healing_invalid_mode(self) -> None:
        """??? healing ???????????ValueError ????????"""
        with pytest.raises(ValueError, match="healing"):
            SelectorResolver(healing="aggressive")

    def test_healing_safe_with_role_selector(self) -> None:
        """healing: safe ? RoleSelector ????????testId / label ????????????"""
        page = MagicMock()
        page.get_by_role = MagicMock(side_effect=Exception("not found"))

        healed_locator = _make_mock_locator(count=1, visible=True)
        page.get_by_test_id = MagicMock(return_value=healed_locator)
        page.get_by_label = MagicMock(return_value=_make_mock_locator(count=0))

        resolver = SelectorResolver(healing="safe")
        selector = RoleSelector(role="button", name="??")

        result = asyncio.run(
            resolver.resolve(page, selector)
        )

        assert result == healed_locator


# ---------------------------------------------------------------------------
# ???: resolve - ??????????
# ---------------------------------------------------------------------------

class TestResolve:
    """resolve ???????????"""

    def test_resolve_single_selector(self) -> None:
        """??????????????????"""
        page = _make_mock_page()
        resolver = SelectorResolver()
        selector = TestIdSelector(testId="my-btn")

        result = asyncio.run(
            resolver.resolve(page, selector)
        )

        page.get_by_test_id.assert_called_once_with("my-btn")

    def test_resolve_any_selector(self) -> None:
        """AnySelector ? resolve ?????????????????????"""
        locator = _make_mock_locator(count=1, visible=True)
        page = MagicMock()
        page.get_by_test_id = MagicMock(return_value=locator)

        selector = AnySelector(any=[TestIdSelector(testId="btn")])
        resolver = SelectorResolver()

        result = asyncio.run(
            resolver.resolve(page, selector)
        )

        assert result == locator


# ---------------------------------------------------------------------------
# ???: _describe_selector ????
# ---------------------------------------------------------------------------

class TestDescribeSelector:
    """_describe_selector ???????????"""

    def test_describe_test_id(self) -> None:
        assert _describe_selector(TestIdSelector(testId="btn")) == "testId='btn'"

    def test_describe_role_with_name(self) -> None:
        assert _describe_selector(RoleSelector(role="button", name="??")) == \
            "role='button', name='??'"

    def test_describe_role_without_name(self) -> None:
        assert _describe_selector(RoleSelector(role="textbox")) == "role='textbox'"

    def test_describe_label(self) -> None:
        assert _describe_selector(LabelSelector(label="??")) == "label='??'"

    def test_describe_placeholder(self) -> None:
        assert _describe_selector(PlaceholderSelector(placeholder="??")) == \
            "placeholder='??'"

    def test_describe_css_without_text(self) -> None:
        assert _describe_selector(CssSelector(css=".btn")) == "css='.btn'"

    def test_describe_css_with_text(self) -> None:
        assert _describe_selector(CssSelector(css=".btn", text="??")) == \
            "css='.btn', text='??'"

    def test_describe_text(self) -> None:
        assert _describe_selector(TextSelector(text="hello")) == "text='hello'"

    def test_describe_any(self) -> None:
        selector = AnySelector(any=[
            TestIdSelector(testId="a"),
            RoleSelector(role="button"),
        ])
        desc = _describe_selector(selector)
        assert "any=[" in desc
        assert "testId='a'" in desc
        assert "role='button'" in desc
