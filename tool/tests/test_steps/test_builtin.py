"""
標準ステップハンドラのテスト

Playwright Page/Locator はモックを使用し、
各ハンドラが正しい Playwright メソッドを呼び出すことを確認する。
高レベルステップハンドラの基本的な構造テストも含む。

注意: pytest-asyncio が古いバージョンのため、asyncio.run() で同期テストとして実行。
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from brt.steps.builtin import (
    ApiMockHandler,
    AssertNoConsoleErrorHandler,
    BackHandler,
    CheckHandler,
    ClickHandler,
    DblClickHandler,
    DumpDomHandler,
    FillHandler,
    GotoHandler,
    LogHandler,
    PressHandler,
    ReloadHandler,
    RouteStubHandler,
    ScrollHandler,
    ScrollIntoViewHandler,
    SelectOptionHandler,
    StoreAttrHandler,
    StoreTextHandler,
    UncheckHandler,
    WaitForHandler,
    WaitForHiddenHandler,
    WaitForNetworkIdleHandler,
    WaitForVisibleHandler,
    create_default_registry,
)
from brt.steps.registry import StepContext, StepHandler


# ---------------------------------------------------------------------------
# ヘルパー: モック生成
# ---------------------------------------------------------------------------

def _make_mock_page():
    """Playwright Page のモックを生成する。"""
    page = AsyncMock()
    page.goto = AsyncMock()
    page.wait_for_load_state = AsyncMock()
    page.go_back = AsyncMock()
    page.reload = AsyncMock()
    page.screenshot = AsyncMock()
    page.route = AsyncMock()
    page.mouse = AsyncMock()
    page.mouse.wheel = AsyncMock()

    # Locator モック
    locator = AsyncMock()
    locator.click = AsyncMock()
    locator.dblclick = AsyncMock()
    locator.fill = AsyncMock()
    locator.press = AsyncMock()
    locator.check = AsyncMock()
    locator.uncheck = AsyncMock()
    locator.select_option = AsyncMock()
    locator.scroll_into_view_if_needed = AsyncMock()
    locator.wait_for = AsyncMock()
    locator.text_content = AsyncMock(return_value="テスト値")
    locator.get_attribute = AsyncMock(return_value="attr-value")
    locator.inner_html = AsyncMock(return_value="<div>test</div>")

    # get_by_test_id 等のメソッドが Locator を返すように設定
    page.get_by_test_id = MagicMock(return_value=locator)
    page.get_by_role = MagicMock(return_value=locator)
    page.get_by_label = MagicMock(return_value=locator)
    page.get_by_placeholder = MagicMock(return_value=locator)
    page.get_by_text = MagicMock(return_value=locator)
    page.locator = MagicMock(return_value=locator)

    # context モック
    context_mock = AsyncMock()
    context_mock.storage_state = AsyncMock()
    context_mock.add_cookies = AsyncMock()
    page.context = context_mock

    return page


def _make_mock_context():
    """StepContext のモックを生成する。"""
    from brt.core.selector import SelectorResolver
    from brt.dsl.variables import VariableExpander

    resolver = SelectorResolver(healing="off")
    expander = VariableExpander(env={}, vars={})

    return StepContext(
        selector_resolver=resolver,
        variable_expander=expander,
        console_errors=[],
    )


# ---------------------------------------------------------------------------
# レジストリ登録テスト
# ---------------------------------------------------------------------------

class TestBuiltinRegistration:
    """標準ステップのレジストリ登録テスト。"""

    def test_create_default_registry_has_all_standard_steps(self):
        """create_default_registry() が全標準ステップを含むこと。"""
        registry = create_default_registry()

        expected_steps = [
            # ナビゲーション
            "goto", "back", "reload",
            # 操作
            "click", "dblclick", "fill", "press", "check", "uncheck", "selectOption", "scroll", "scrollIntoView",
            # 待機
            "waitFor", "waitForVisible", "waitForHidden", "waitForNetworkIdle",
            # 検証
            "expectVisible", "expectHidden", "expectText", "expectUrl",
            # 取得
            "storeText", "storeAttr",
            # デバッグ
            "screenshot", "log", "dumpDom",
            # セッション
            "useStorageState", "saveStorageState",
            # 高レベル補助
            "waitForToast", "assertNoConsoleError", "apiMock", "routeStub",
        ]

        for step_name in expected_steps:
            assert registry.has(step_name), f"ステップ '{step_name}' が未登録です"

    def test_all_handlers_satisfy_protocol(self):
        """全登録ハンドラが StepHandler Protocol を満たすこと。"""
        registry = create_default_registry()

        for name in registry.names:
            handler = registry.get(name)
            assert isinstance(handler, StepHandler), (
                f"ステップ '{name}' のハンドラが StepHandler Protocol を満たしません"
            )

    def test_all_handlers_have_schema(self):
        """全登録ハンドラが get_schema() で Pydantic モデルを返すこと。"""
        registry = create_default_registry()

        for name in registry.names:
            handler = registry.get(name)
            schema = handler.get_schema()
            assert schema is not None, f"ステップ '{name}' の get_schema() が None を返しました"

    def test_list_all_has_info_for_all(self):
        """list_all() が全ステップの StepInfo を返すこと。"""
        registry = create_default_registry()
        all_info = registry.list_all()

        assert len(all_info) == len(registry.names)
        for info in all_info:
            assert info.name != ""
            assert info.description != ""
            assert info.category != ""


# ---------------------------------------------------------------------------
# ナビゲーションハンドラテスト
# ---------------------------------------------------------------------------

class TestNavigationHandlers:
    """ナビゲーション系ハンドラのテスト。"""

    def test_goto_calls_page_goto_and_wait(self):
        """goto が page.goto() と wait_for_load_state() を呼ぶこと。"""
        page = _make_mock_page()
        ctx = _make_mock_context()
        handler = GotoHandler()

        asyncio.run(handler.execute(page, {"url": "http://example.com"}, ctx))

        page.goto.assert_called_once_with("http://example.com")
        page.wait_for_load_state.assert_called_once_with("domcontentloaded")

    def test_back_calls_go_back(self):
        """back が page.go_back() を呼ぶこと。"""
        page = _make_mock_page()
        ctx = _make_mock_context()
        handler = BackHandler()

        asyncio.run(handler.execute(page, {}, ctx))

        page.go_back.assert_called_once()

    def test_reload_calls_reload(self):
        """reload が page.reload() を呼ぶこと。"""
        page = _make_mock_page()
        ctx = _make_mock_context()
        handler = ReloadHandler()

        asyncio.run(handler.execute(page, {}, ctx))

        page.reload.assert_called_once()


# ---------------------------------------------------------------------------
# 操作ハンドラテスト
# ---------------------------------------------------------------------------

class TestActionHandlers:
    """操作系ハンドラのテスト。"""

    def test_click_resolves_selector(self):
        """click がセレクタを解決して locator.click() を呼ぶこと。"""
        page = _make_mock_page()
        ctx = _make_mock_context()
        handler = ClickHandler()

        asyncio.run(handler.execute(page, {"by": {"testId": "btn"}}, ctx))

        page.get_by_test_id.assert_called_once_with("btn")

    def test_dblclick_resolves_selector(self):
        """dblclick がセレクタを解決すること。"""
        page = _make_mock_page()
        ctx = _make_mock_context()
        handler = DblClickHandler()

        asyncio.run(handler.execute(page, {"by": {"testId": "item"}}, ctx))

        page.get_by_test_id.assert_called_once_with("item")

    def test_fill_resolves_css_selector(self):
        """fill が CSS セレクタを解決すること。"""
        page = _make_mock_page()
        ctx = _make_mock_context()
        handler = FillHandler()

        asyncio.run(handler.execute(
            page,
            {"by": {"css": "#email"}, "value": "test@example.com"},
            ctx,
        ))

        page.locator.assert_called_once_with("#email")

    def test_press_resolves_selector(self):
        """press がセレクタを解決すること。"""
        page = _make_mock_page()
        ctx = _make_mock_context()
        handler = PressHandler()

        asyncio.run(handler.execute(
            page,
            {"by": {"testId": "input"}, "key": "Enter"},
            ctx,
        ))

        page.get_by_test_id.assert_called_once_with("input")

    def test_scroll_calls_mouse_wheel(self):
        """scroll が page.mouse.wheel() を呼ぶこと。"""
        page = _make_mock_page()
        ctx = _make_mock_context()
        handler = ScrollHandler()

        asyncio.run(handler.execute(page, {"deltaX": 10, "deltaY": 250}, ctx))

        page.mouse.wheel.assert_called_once_with(10, 250)

    def test_scroll_into_view_resolves_selector(self):
        """scrollIntoView が locator.scroll_into_view_if_needed() を呼ぶこと。"""
        page = _make_mock_page()
        ctx = _make_mock_context()
        handler = ScrollIntoViewHandler()

        asyncio.run(handler.execute(page, {"by": {"testId": "row"}}, ctx))

        page.get_by_test_id.assert_called_once_with("row")

    def test_check_resolves_selector(self):
        """check がセレクタを解決すること。"""
        page = _make_mock_page()
        ctx = _make_mock_context()
        handler = CheckHandler()

        asyncio.run(handler.execute(page, {"by": {"testId": "agree"}}, ctx))

        page.get_by_test_id.assert_called_once_with("agree")

    def test_uncheck_resolves_selector(self):
        """uncheck がセレクタを解決すること。"""
        page = _make_mock_page()
        ctx = _make_mock_context()
        handler = UncheckHandler()

        asyncio.run(handler.execute(page, {"by": {"testId": "opt"}}, ctx))

        page.get_by_test_id.assert_called_once_with("opt")

    def test_select_option_resolves_selector(self):
        """selectOption がセレクタを解決すること。"""
        page = _make_mock_page()
        ctx = _make_mock_context()
        handler = SelectOptionHandler()

        asyncio.run(handler.execute(
            page,
            {"by": {"css": "select#country"}, "value": "JP"},
            ctx,
        ))

        page.locator.assert_called_once_with("select#country")


# ---------------------------------------------------------------------------
# 待機ハンドラテスト
# ---------------------------------------------------------------------------

class TestWaitHandlers:
    """待機系ハンドラのテスト。"""

    def test_wait_for_resolves_selector(self):
        """waitFor がセレクタを解決すること。"""
        page = _make_mock_page()
        ctx = _make_mock_context()
        handler = WaitForHandler()

        asyncio.run(handler.execute(
            page,
            {"by": {"testId": "loader"}, "state": "hidden"},
            ctx,
        ))

        page.get_by_test_id.assert_called_once_with("loader")

    def test_wait_for_visible_resolves_selector(self):
        """waitForVisible がセレクタを解決すること。"""
        page = _make_mock_page()
        ctx = _make_mock_context()
        handler = WaitForVisibleHandler()

        asyncio.run(handler.execute(
            page,
            {"by": {"testId": "content"}},
            ctx,
        ))

        page.get_by_test_id.assert_called_once_with("content")

    def test_wait_for_hidden_resolves_selector(self):
        """waitForHidden がセレクタを解決すること。"""
        page = _make_mock_page()
        ctx = _make_mock_context()
        handler = WaitForHiddenHandler()

        asyncio.run(handler.execute(
            page,
            {"by": {"testId": "spinner"}},
            ctx,
        ))

        page.get_by_test_id.assert_called_once_with("spinner")

    def test_wait_for_network_idle(self):
        """waitForNetworkIdle が wait_for_load_state('networkidle') を呼ぶこと。"""
        page = _make_mock_page()
        ctx = _make_mock_context()
        handler = WaitForNetworkIdleHandler()

        asyncio.run(handler.execute(page, {}, ctx))

        page.wait_for_load_state.assert_called_once_with("networkidle")


# ---------------------------------------------------------------------------
# 取得ハンドラテスト
# ---------------------------------------------------------------------------

class TestRetrievalHandlers:
    """取得系ハンドラのテスト。"""

    def test_store_text_sets_variable(self):
        """storeText が変数に値を格納すること。"""
        page = _make_mock_page()
        ctx = _make_mock_context()
        handler = StoreTextHandler()

        asyncio.run(handler.execute(
            page,
            {"by": {"testId": "price"}, "varName": "itemPrice"},
            ctx,
        ))

        # VariableExpander に値が設定されたことを確認
        assert ctx.variable_expander.vars.get("itemPrice") == "テスト値"

    def test_store_attr_sets_variable(self):
        """storeAttr が変数に属性値を格納すること。"""
        page = _make_mock_page()
        ctx = _make_mock_context()
        handler = StoreAttrHandler()

        asyncio.run(handler.execute(
            page,
            {"by": {"testId": "link"}, "attr": "href", "varName": "linkUrl"},
            ctx,
        ))

        assert ctx.variable_expander.vars.get("linkUrl") == "attr-value"


# ---------------------------------------------------------------------------
# デバッグハンドラテスト
# ---------------------------------------------------------------------------

class TestDebugHandlers:
    """デバッグ系ハンドラのテスト。"""

    def test_log_handler_does_not_raise(self):
        """log ハンドラがエラーなく実行されること。"""
        page = _make_mock_page()
        ctx = _make_mock_context()
        handler = LogHandler()

        asyncio.run(handler.execute(
            page,
            {"message": "テストメッセージ"},
            ctx,
        ))

    def test_dump_dom_resolves_selector(self):
        """dumpDom がセレクタを解決すること。"""
        page = _make_mock_page()
        ctx = _make_mock_context()
        handler = DumpDomHandler()

        asyncio.run(handler.execute(
            page,
            {"by": {"testId": "container"}},
            ctx,
        ))

        page.get_by_test_id.assert_called_once_with("container")


# ---------------------------------------------------------------------------
# 高レベル補助ハンドラテスト
# ---------------------------------------------------------------------------

class TestHighLevelHelperHandlers:
    """高レベル補助ハンドラのテスト。"""

    def test_assert_no_console_error_passes_when_empty(self):
        """assertNoConsoleError がエラーなしの場合に成功すること。"""
        page = _make_mock_page()
        ctx = _make_mock_context()
        ctx.console_errors = []
        handler = AssertNoConsoleErrorHandler()

        asyncio.run(handler.execute(page, {}, ctx))

    def test_assert_no_console_error_fails_when_errors_exist(self):
        """assertNoConsoleError がエラーありの場合に失敗すること。"""
        page = _make_mock_page()
        ctx = _make_mock_context()
        ctx.console_errors = ["TypeError: undefined is not a function"]
        handler = AssertNoConsoleErrorHandler()

        with pytest.raises(AssertionError):
            asyncio.run(handler.execute(page, {}, ctx))

    def test_api_mock_handler_has_schema(self):
        """apiMock ハンドラが正しいスキーマを返すこと。"""
        handler = ApiMockHandler()
        schema = handler.get_schema()
        assert schema is not None

    def test_route_stub_handler_has_schema(self):
        """routeStub ハンドラが正しいスキーマを返すこと。"""
        handler = RouteStubHandler()
        schema = handler.get_schema()
        assert schema is not None


# ---------------------------------------------------------------------------
# 高レベルステップ（別モジュール）の登録テスト
# ---------------------------------------------------------------------------

class TestHighLevelStepRegistration:
    """高レベルステップの登録テスト。"""

    def test_full_registry_has_overlay_step(self):
        """create_full_registry() が selectOverlayOption を含むこと。"""
        from brt.steps import create_full_registry
        registry = create_full_registry()
        assert registry.has("selectOverlayOption")

    def test_full_registry_has_wijmo_combo_step(self):
        """create_full_registry() が selectWijmoCombo を含むこと。"""
        from brt.steps import create_full_registry
        registry = create_full_registry()
        assert registry.has("selectWijmoCombo")

    def test_full_registry_has_wijmo_grid_step(self):
        """create_full_registry() が clickWijmoGridCell を含むこと。"""
        from brt.steps import create_full_registry
        registry = create_full_registry()
        assert registry.has("clickWijmoGridCell")

    def test_full_registry_has_datepicker_step(self):
        """create_full_registry() が setDatePicker を含むこと。"""
        from brt.steps import create_full_registry
        registry = create_full_registry()
        assert registry.has("setDatePicker")

    def test_full_registry_has_upload_step(self):
        """create_full_registry() が uploadFile を含むこと。"""
        from brt.steps import create_full_registry
        registry = create_full_registry()
        assert registry.has("uploadFile")

    def test_full_registry_all_handlers_satisfy_protocol(self):
        """全登録ハンドラが StepHandler Protocol を満たすこと。"""
        from brt.steps import create_full_registry
        registry = create_full_registry()

        for name in registry.names:
            handler = registry.get(name)
            assert isinstance(handler, StepHandler), (
                f"ステップ '{name}' のハンドラが StepHandler Protocol を満たしません"
            )

    def test_full_registry_total_count(self):
        """全レジストリのステップ数が期待値と一致すること。"""
        from brt.steps import create_full_registry
        registry = create_full_registry()

        # 標準 31 + 高レベル 5 = 36
        assert len(registry.names) == 36
