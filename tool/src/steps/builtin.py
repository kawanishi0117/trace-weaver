"""
標準ステップハンドラ — 25種の基本ブラウザ操作

YAML DSL の標準ステップを Playwright API 呼び出しに変換する。
各ハンドラは StepHandler Protocol を満たし、StepRegistry に登録される。

カテゴリ:
  - ナビゲーション: goto, back, reload
  - 操作: click, dblclick, fill, press, check, uncheck, selectOption
  - 待機: waitFor, waitForVisible, waitForHidden, waitForNetworkIdle
  - 検証: expectVisible, expectHidden, expectText, expectUrl
  - 取得: storeText, storeAttr
  - デバッグ: screenshot, log, dumpDom
  - セッション: useStorageState, saveStorageState
  - 高レベル補助: waitForToast, assertNoConsoleError, apiMock, routeStub

要件 5.1〜5.7: 標準ステップライブラリ
要件 6.8〜6.10: waitForToast, assertNoConsoleError, apiMock, routeStub
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel

from .registry import StepContext, StepHandler, StepInfo, StepRegistry

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = logging.getLogger(__name__)


# ===========================================================================
# パラメータスキーマ定義
# ===========================================================================

# --- ナビゲーション ---

class GotoParams(BaseModel):
    """goto ステップのパラメータ。"""
    url: str
    name: str | None = None


class BackParams(BaseModel):
    """back ステップのパラメータ。"""
    name: str | None = None


class ReloadParams(BaseModel):
    """reload ステップのパラメータ。"""
    name: str | None = None


# --- 操作 ---

class ClickParams(BaseModel):
    """click ステップのパラメータ。"""
    by: dict
    name: str | None = None


class DblClickParams(BaseModel):
    """dblclick ステップのパラメータ。"""
    by: dict
    name: str | None = None


class FillParams(BaseModel):
    """fill ステップのパラメータ。"""
    by: dict
    value: str
    name: str | None = None
    secret: bool = False


class PressParams(BaseModel):
    """press ステップのパラメータ。"""
    by: dict
    key: str
    name: str | None = None


class CheckParams(BaseModel):
    """check ステップのパラメータ。"""
    by: dict
    name: str | None = None


class UncheckParams(BaseModel):
    """uncheck ステップのパラメータ。"""
    by: dict
    name: str | None = None


class SelectOptionParams(BaseModel):
    """selectOption ステップのパラメータ。"""
    by: dict
    value: str
    name: str | None = None


class ScrollParams(BaseModel):
    """scroll ステップのパラメータ。"""
    deltaX: int = 0
    deltaY: int = 0
    name: str | None = None


class ScrollIntoViewParams(BaseModel):
    """scrollIntoView ステップのパラメータ。"""
    by: dict
    frame: str | None = None
    name: str | None = None


# --- 待機 ---

class WaitForParams(BaseModel):
    """waitFor ステップのパラメータ。"""
    by: dict
    state: str = "visible"
    timeout: int | None = None
    name: str | None = None


class WaitForVisibleParams(BaseModel):
    """waitForVisible ステップのパラメータ。"""
    by: dict
    timeout: int | None = None
    name: str | None = None


class WaitForHiddenParams(BaseModel):
    """waitForHidden ステップのパラメータ。"""
    by: dict
    timeout: int | None = None
    name: str | None = None


class WaitForNetworkIdleParams(BaseModel):
    """waitForNetworkIdle ステップのパラメータ。"""
    timeout: int | None = None
    name: str | None = None


# --- 検証 ---

class ExpectVisibleParams(BaseModel):
    """expectVisible ステップのパラメータ。"""
    by: dict
    name: str | None = None


class ExpectHiddenParams(BaseModel):
    """expectHidden ステップのパラメータ。"""
    by: dict
    name: str | None = None


class ExpectTextParams(BaseModel):
    """expectText ステップのパラメータ。"""
    by: dict
    text: str
    name: str | None = None


class ExpectUrlParams(BaseModel):
    """expectUrl ステップのパラメータ。"""
    url: str
    name: str | None = None


# --- 取得 ---

class StoreTextParams(BaseModel):
    """storeText ステップのパラメータ。"""
    by: dict
    varName: str
    name: str | None = None


class StoreAttrParams(BaseModel):
    """storeAttr ステップのパラメータ。"""
    by: dict
    attr: str
    varName: str
    name: str | None = None


# --- デバッグ ---

class ScreenshotParams(BaseModel):
    """screenshot ステップのパラメータ。"""
    name: str | None = None


class LogParams(BaseModel):
    """log ステップのパラメータ。"""
    message: str
    name: str | None = None


class DumpDomParams(BaseModel):
    """dumpDom ステップのパラメータ。"""
    by: dict
    name: str | None = None


# --- セッション ---

class UseStorageStateParams(BaseModel):
    """useStorageState ステップのパラメータ。"""
    path: str
    name: str | None = None


class SaveStorageStateParams(BaseModel):
    """saveStorageState ステップのパラメータ。"""
    path: str
    name: str | None = None


# --- 高レベル補助 ---

class WaitForToastParams(BaseModel):
    """waitForToast ステップのパラメータ。"""
    text: str
    timeout: int | None = None
    name: str | None = None


class AssertNoConsoleErrorParams(BaseModel):
    """assertNoConsoleError ステップのパラメータ。"""
    name: str | None = None


class ApiMockResponseParams(BaseModel):
    """apiMock レスポンス定義。"""
    status: int = 200
    body: str | dict = ""


class ApiMockParams(BaseModel):
    """apiMock ステップのパラメータ。"""
    url: str
    method: str | None = None
    response: ApiMockResponseParams
    name: str | None = None


class RouteStubParams(BaseModel):
    """routeStub ステップのパラメータ。"""
    url: str
    handler: str
    name: str | None = None


# ===========================================================================
# セレクタ解決ヘルパー
# ===========================================================================

async def _resolve_selector(page: Page, by: dict, context: StepContext, frame: Optional[str] = None):
    """セレクタ辞書を Playwright Locator に変換するヘルパー。

    context.selector_resolver を使用してセレクタを解決する。
    frame が指定されている場合は iframe 内で解決する。

    Args:
        page: Playwright Page
        by: セレクタ辞書（YAML DSL の by フィールド）
        context: ステップ実行コンテキスト
        frame: iframe セレクタ（iframe 内操作時）

    Returns:
        Playwright Locator
    """
    from ..dsl.schema import (
        AnySelector,
        CssSelector,
        LabelSelector,
        PlaceholderSelector,
        RoleSelector,
        TestIdSelector,
        TextSelector,
    )

    # 辞書からセレクタモデルに変換
    if "any" in by:
        selector = AnySelector(**by)
    elif "testId" in by:
        selector = TestIdSelector(**by)
    elif "role" in by:
        selector = RoleSelector(**by)
    elif "label" in by:
        selector = LabelSelector(**by)
    elif "placeholder" in by:
        selector = PlaceholderSelector(**by)
    elif "css" in by:
        selector = CssSelector(**by)
    elif "text" in by:
        selector = TextSelector(**by)
    else:
        raise ValueError(f"未知のセレクタ形式です: {by}")

    return await context.selector_resolver.resolve(page, selector, frame=frame)


# ===========================================================================
# ナビゲーションハンドラ
# ===========================================================================

class GotoHandler:
    """goto ステップ — 指定 URL へ遷移（waitForLoadState 付き）。"""

    async def execute(self, page: Page, params: dict, context: StepContext) -> None:
        url = params.get("url", params.get("goto", ""))
        logger.info("goto: %s", url)
        await page.goto(url)
        await page.wait_for_load_state("domcontentloaded")

    def get_schema(self) -> type[BaseModel]:
        return GotoParams


class BackHandler:
    """back ステップ — ブラウザの「戻る」操作。"""

    async def execute(self, page: Page, params: dict, context: StepContext) -> None:
        logger.info("back")
        await page.go_back()

    def get_schema(self) -> type[BaseModel]:
        return BackParams


class ReloadHandler:
    """reload ステップ — ページリロード。"""

    async def execute(self, page: Page, params: dict, context: StepContext) -> None:
        logger.info("reload")
        await page.reload()

    def get_schema(self) -> type[BaseModel]:
        return ReloadParams


# ===========================================================================
# 操作ハンドラ
# ===========================================================================


async def _prepare_locator_for_action(locator) -> None:
    """操作前に locator を安定化する。"""
    try:
        await locator.scroll_into_view_if_needed(timeout=5_000)
    except Exception:
        # 画面外でもクリック可能なケースがあるため失敗時は継続する。
        pass


class ClickHandler:
    """click ステップ — 要素をクリック。"""

    async def execute(self, page: Page, params: dict, context: StepContext) -> None:
        by = params.get("by", params)
        frame = params.get("frame")
        locator = await _resolve_selector(page, by, context, frame=frame)
        logger.info("click: %s", by)
        await _prepare_locator_for_action(locator)
        await locator.click()

    def get_schema(self) -> type[BaseModel]:
        return ClickParams


class DblClickHandler:
    """dblclick ステップ — 要素をダブルクリック。"""

    async def execute(self, page: Page, params: dict, context: StepContext) -> None:
        by = params.get("by", params)
        frame = params.get("frame")
        locator = await _resolve_selector(page, by, context, frame=frame)
        logger.info("dblclick: %s", by)
        await _prepare_locator_for_action(locator)
        await locator.dblclick()

    def get_schema(self) -> type[BaseModel]:
        return DblClickParams


class FillHandler:
    """fill ステップ — 入力フィールドに値を入力。"""

    async def execute(self, page: Page, params: dict, context: StepContext) -> None:
        by = params.get("by", params)
        value = params.get("value", "")
        secret = params.get("secret", False)
        frame = params.get("frame")
        locator = await _resolve_selector(page, by, context, frame=frame)
        display_value = "***" if secret else value
        logger.info("fill: %s → %s", by, display_value)
        await _prepare_locator_for_action(locator)
        await locator.fill(value)

    def get_schema(self) -> type[BaseModel]:
        return FillParams


class PressHandler:
    """press ステップ — 要素に対してキーを押下。"""

    async def execute(self, page: Page, params: dict, context: StepContext) -> None:
        by = params.get("by", params)
        key = params["key"]
        frame = params.get("frame")
        locator = await _resolve_selector(page, by, context, frame=frame)
        logger.info("press: %s → %s", by, key)
        await _prepare_locator_for_action(locator)
        await locator.press(key)

    def get_schema(self) -> type[BaseModel]:
        return PressParams


class CheckHandler:
    """check ステップ — チェックボックスをチェック状態にする。"""

    async def execute(self, page: Page, params: dict, context: StepContext) -> None:
        by = params.get("by", params)
        frame = params.get("frame")
        locator = await _resolve_selector(page, by, context, frame=frame)
        logger.info("check: %s", by)
        await _prepare_locator_for_action(locator)
        await locator.check()

    def get_schema(self) -> type[BaseModel]:
        return CheckParams


class UncheckHandler:
    """uncheck ステップ — チェックボックスのチェックを外す。"""

    async def execute(self, page: Page, params: dict, context: StepContext) -> None:
        by = params.get("by", params)
        frame = params.get("frame")
        locator = await _resolve_selector(page, by, context, frame=frame)
        logger.info("uncheck: %s", by)
        await _prepare_locator_for_action(locator)
        await locator.uncheck()

    def get_schema(self) -> type[BaseModel]:
        return UncheckParams


class SelectOptionHandler:
    """selectOption ステップ — HTML select からオプションを選択。"""

    async def execute(self, page: Page, params: dict, context: StepContext) -> None:
        by = params.get("by", params)
        value = params["value"]
        frame = params.get("frame")
        locator = await _resolve_selector(page, by, context, frame=frame)
        logger.info("selectOption: %s → %s", by, value)
        await _prepare_locator_for_action(locator)
        await locator.select_option(value)

    def get_schema(self) -> type[BaseModel]:
        return SelectOptionParams


class ScrollHandler:
    """scroll ステップ — マウスホイール相当のスクロールを実行。"""

    async def execute(self, page: Page, params: dict, context: StepContext) -> None:
        dx = int(params.get("deltaX", 0))
        dy = int(params.get("deltaY", 0))
        logger.info("scroll: deltaX=%s deltaY=%s", dx, dy)
        await page.mouse.wheel(dx, dy)

    def get_schema(self) -> type[BaseModel]:
        return ScrollParams


class ScrollIntoViewHandler:
    """scrollIntoView ステップ — 要素が表示領域に入るまでスクロール。"""

    async def execute(self, page: Page, params: dict, context: StepContext) -> None:
        by = params.get("by", params)
        frame = params.get("frame")
        locator = await _resolve_selector(page, by, context, frame=frame)
        logger.info("scrollIntoView: %s", by)
        await locator.scroll_into_view_if_needed()

    def get_schema(self) -> type[BaseModel]:
        return ScrollIntoViewParams


# ===========================================================================
# 待機ハンドラ
# ===========================================================================

class WaitForHandler:
    """waitFor ステップ — 要素が指定状態になるまで待機。"""

    async def execute(self, page: Page, params: dict, context: StepContext) -> None:
        by = params.get("by", params)
        state = params.get("state", "visible")
        timeout = params.get("timeout")
        frame = params.get("frame")
        locator = await _resolve_selector(page, by, context, frame=frame)
        logger.info("waitFor: %s (state=%s)", by, state)
        kwargs: dict = {"state": state}
        if timeout is not None:
            kwargs["timeout"] = timeout
        await locator.wait_for(**kwargs)

    def get_schema(self) -> type[BaseModel]:
        return WaitForParams


class WaitForVisibleHandler:
    """waitForVisible ステップ — 要素が可視状態になるまで待機。"""

    async def execute(self, page: Page, params: dict, context: StepContext) -> None:
        by = params.get("by", params)
        timeout = params.get("timeout")
        frame = params.get("frame")
        locator = await _resolve_selector(page, by, context, frame=frame)
        logger.info("waitForVisible: %s", by)
        kwargs: dict = {"state": "visible"}
        if timeout is not None:
            kwargs["timeout"] = timeout
        await locator.wait_for(**kwargs)

    def get_schema(self) -> type[BaseModel]:
        return WaitForVisibleParams


class WaitForHiddenHandler:
    """waitForHidden ステップ — 要素が非表示状態になるまで待機。"""

    async def execute(self, page: Page, params: dict, context: StepContext) -> None:
        by = params.get("by", params)
        timeout = params.get("timeout")
        frame = params.get("frame")
        locator = await _resolve_selector(page, by, context, frame=frame)
        logger.info("waitForHidden: %s", by)
        kwargs: dict = {"state": "hidden"}
        if timeout is not None:
            kwargs["timeout"] = timeout
        await locator.wait_for(**kwargs)

    def get_schema(self) -> type[BaseModel]:
        return WaitForHiddenParams


class WaitForNetworkIdleHandler:
    """waitForNetworkIdle ステップ — ネットワークアイドル待機。"""

    async def execute(self, page: Page, params: dict, context: StepContext) -> None:
        timeout = params.get("timeout")
        logger.info("waitForNetworkIdle")
        kwargs: dict = {}
        if timeout is not None:
            kwargs["timeout"] = timeout
        await page.wait_for_load_state("networkidle", **kwargs)

    def get_schema(self) -> type[BaseModel]:
        return WaitForNetworkIdleParams


# ===========================================================================
# 検証ハンドラ
# ===========================================================================

class ExpectVisibleHandler:
    """expectVisible ステップ — 要素が可視状態であることを検証。"""

    async def execute(self, page: Page, params: dict, context: StepContext) -> None:
        by = params.get("by", params)
        frame = params.get("frame")
        locator = await _resolve_selector(page, by, context, frame=frame)
        logger.info("expectVisible: %s", by)
        from playwright.async_api import expect
        await expect(locator).to_be_visible()

    def get_schema(self) -> type[BaseModel]:
        return ExpectVisibleParams


class ExpectHiddenHandler:
    """expectHidden ステップ — 要素が非表示状態であることを検証。"""

    async def execute(self, page: Page, params: dict, context: StepContext) -> None:
        by = params.get("by", params)
        frame = params.get("frame")
        locator = await _resolve_selector(page, by, context, frame=frame)
        logger.info("expectHidden: %s", by)
        from playwright.async_api import expect
        await expect(locator).to_be_hidden()

    def get_schema(self) -> type[BaseModel]:
        return ExpectHiddenParams


class ExpectTextHandler:
    """expectText ステップ — 要素が指定テキストを含むことを検証。"""

    async def execute(self, page: Page, params: dict, context: StepContext) -> None:
        by = params.get("by", params)
        text = params["text"]
        frame = params.get("frame")
        locator = await _resolve_selector(page, by, context, frame=frame)
        logger.info("expectText: %s → '%s'", by, text)
        from playwright.async_api import expect
        await expect(locator).to_contain_text(text)

    def get_schema(self) -> type[BaseModel]:
        return ExpectTextParams


class ExpectUrlHandler:
    """expectUrl ステップ — 現在の URL が指定パターンに一致することを検証。"""

    async def execute(self, page: Page, params: dict, context: StepContext) -> None:
        import re as re_mod
        url_pattern = params["url"]
        logger.info("expectUrl: %s", url_pattern)
        from playwright.async_api import expect
        await expect(page).to_have_url(re_mod.compile(url_pattern))

    def get_schema(self) -> type[BaseModel]:
        return ExpectUrlParams


# ===========================================================================
# 取得ハンドラ
# ===========================================================================

class StoreTextHandler:
    """storeText ステップ — 要素のテキストを変数に格納。"""

    async def execute(self, page: Page, params: dict, context: StepContext) -> None:
        by = params.get("by", params)
        var_name = params["varName"]
        frame = params.get("frame")
        locator = await _resolve_selector(page, by, context, frame=frame)
        text = await locator.text_content() or ""
        logger.info("storeText: %s → vars.%s = '%s'", by, var_name, text)
        context.variable_expander.set_var(var_name, text)

    def get_schema(self) -> type[BaseModel]:
        return StoreTextParams


class StoreAttrHandler:
    """storeAttr ステップ — 要素の属性値を変数に格納。"""

    async def execute(self, page: Page, params: dict, context: StepContext) -> None:
        by = params.get("by", params)
        attr = params["attr"]
        var_name = params["varName"]
        frame = params.get("frame")
        locator = await _resolve_selector(page, by, context, frame=frame)
        value = await locator.get_attribute(attr) or ""
        logger.info("storeAttr: %s[%s] → vars.%s = '%s'", by, attr, var_name, value)
        context.variable_expander.set_var(var_name, value)

    def get_schema(self) -> type[BaseModel]:
        return StoreAttrParams


# ===========================================================================
# デバッグハンドラ
# ===========================================================================

class ScreenshotHandler:
    """screenshot ステップ — スクリーンショットを撮影。"""

    async def execute(self, page: Page, params: dict, context: StepContext) -> None:
        name = params.get("name", "screenshot")
        logger.info("screenshot: %s", name)
        # ArtifactsManager が利用可能な場合はそちらに委譲
        if context.artifacts_manager is not None and hasattr(context.artifacts_manager, "save_screenshot"):
            await context.artifacts_manager.save_screenshot(page, 0, name)
        else:
            # フォールバック: 一時ファイルに保存
            await page.screenshot(path=f"{name}.png")

    def get_schema(self) -> type[BaseModel]:
        return ScreenshotParams


class LogHandler:
    """log ステップ — メッセージをログに出力。"""

    async def execute(self, page: Page, params: dict, context: StepContext) -> None:
        message = params.get("message", params.get("log", ""))
        logger.info("log: %s", message)

    def get_schema(self) -> type[BaseModel]:
        return LogParams


class DumpDomHandler:
    """dumpDom ステップ — 要素の DOM 構造をダンプ。"""

    async def execute(self, page: Page, params: dict, context: StepContext) -> None:
        by = params.get("by", params)
        frame = params.get("frame")
        locator = await _resolve_selector(page, by, context, frame=frame)
        html = await locator.inner_html()
        logger.info("dumpDom: %s\n%s", by, html)

    def get_schema(self) -> type[BaseModel]:
        return DumpDomParams


# ===========================================================================
# セッションハンドラ
# ===========================================================================

class UseStorageStateHandler:
    """useStorageState ステップ — 保存済みストレージ状態を復元。"""

    async def execute(self, page: Page, params: dict, context: StepContext) -> None:
        path = params.get("path", params.get("useStorageState", ""))
        logger.info("useStorageState: %s", path)
        # ストレージ状態ファイルを読み込み、コンテキストに適用
        storage_path = Path(path)
        if not storage_path.exists():
            raise FileNotFoundError(f"ストレージ状態ファイルが見つかりません: {path}")
        with open(storage_path, "r", encoding="utf-8") as f:
            state = json.load(f)
        # クッキーを追加
        browser_context = page.context
        if "cookies" in state:
            await browser_context.add_cookies(state["cookies"])

    def get_schema(self) -> type[BaseModel]:
        return UseStorageStateParams


class SaveStorageStateHandler:
    """saveStorageState ステップ — 現在のストレージ状態を保存。"""

    async def execute(self, page: Page, params: dict, context: StepContext) -> None:
        path = params.get("path", params.get("saveStorageState", ""))
        logger.info("saveStorageState: %s", path)
        storage_path = Path(path)
        storage_path.parent.mkdir(parents=True, exist_ok=True)
        await page.context.storage_state(path=str(storage_path))

    def get_schema(self) -> type[BaseModel]:
        return SaveStorageStateParams


# ===========================================================================
# 高レベル補助ハンドラ（builtin に含めるもの）
# ===========================================================================

class WaitForToastHandler:
    """waitForToast ステップ — トースト通知の出現・消滅を待機。"""

    async def execute(self, page: Page, params: dict, context: StepContext) -> None:
        text = params["text"]
        timeout = params.get("timeout")
        logger.info("waitForToast: '%s'", text)
        # トースト要素を探索（一般的なトースト CSS セレクタ）
        toast_locator = page.get_by_text(text)
        kwargs: dict = {"state": "visible"}
        if timeout is not None:
            kwargs["timeout"] = timeout
        # トーストの出現を待機
        await toast_locator.wait_for(**kwargs)
        # トーストの消滅を待機
        kwargs["state"] = "hidden"
        await toast_locator.wait_for(**kwargs)

    def get_schema(self) -> type[BaseModel]:
        return WaitForToastParams


class AssertNoConsoleErrorHandler:
    """assertNoConsoleError ステップ — コンソールエラーがないことを検証。"""

    async def execute(self, page: Page, params: dict, context: StepContext) -> None:
        logger.info("assertNoConsoleError")
        if context.console_errors:
            errors_text = "\n".join(context.console_errors)
            raise AssertionError(
                f"ブラウザコンソールに {len(context.console_errors)} 件のエラーが検出されました:\n"
                f"{errors_text}"
            )

    def get_schema(self) -> type[BaseModel]:
        return AssertNoConsoleErrorParams


class ApiMockHandler:
    """apiMock ステップ — Playwright route による API モック設定。"""

    async def execute(self, page: Page, params: dict, context: StepContext) -> None:
        url = params["url"]
        method = params.get("method")
        response = params["response"]
        status = response.get("status", 200) if isinstance(response, dict) else 200
        body = response.get("body", "") if isinstance(response, dict) else ""
        logger.info("apiMock: %s %s → status=%d", method or "*", url, status)

        async def handle_route(route):
            # メソッドフィルタ
            if method and route.request.method.upper() != method.upper():
                await route.fallback()
                return
            # モックレスポンスを返す
            resp_body = json.dumps(body) if isinstance(body, dict) else str(body)
            await route.fulfill(
                status=status,
                content_type="application/json",
                body=resp_body,
            )

        await page.route(url, handle_route)

    def get_schema(self) -> type[BaseModel]:
        return ApiMockParams


class RouteStubHandler:
    """routeStub ステップ — Playwright route による API スタブ設定。"""

    async def execute(self, page: Page, params: dict, context: StepContext) -> None:
        url = params["url"]
        handler_name = params["handler"]
        logger.info("routeStub: %s → handler=%s", url, handler_name)

        async def handle_route(route):
            # ハンドラ名に基づく処理（将来的にはプラグインから解決）
            await route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"stub": handler_name}),
            )

        await page.route(url, handle_route)

    def get_schema(self) -> type[BaseModel]:
        return RouteStubParams


# ===========================================================================
# レジストリ登録
# ===========================================================================

# 全標準ステップのハンドラとメタ情報の定義
_BUILTIN_STEPS: list[tuple[str, StepHandler, StepInfo]] = [
    # ナビゲーション
    ("goto", GotoHandler(), StepInfo("goto", "指定 URL へ遷移（waitForLoadState 付き）", "navigation")),
    ("back", BackHandler(), StepInfo("back", "ブラウザの「戻る」操作", "navigation")),
    ("reload", ReloadHandler(), StepInfo("reload", "ページリロード", "navigation")),
    # 操作
    ("click", ClickHandler(), StepInfo("click", "要素をクリック", "action")),
    ("dblclick", DblClickHandler(), StepInfo("dblclick", "要素をダブルクリック", "action")),
    ("fill", FillHandler(), StepInfo("fill", "入力フィールドに値を入力", "action")),
    ("press", PressHandler(), StepInfo("press", "要素に対してキーを押下", "action")),
    ("check", CheckHandler(), StepInfo("check", "チェックボックスをチェック", "action")),
    ("uncheck", UncheckHandler(), StepInfo("uncheck", "チェックボックスのチェックを外す", "action")),
    ("selectOption", SelectOptionHandler(), StepInfo("selectOption", "HTML select からオプションを選択", "action")),
    ("scroll", ScrollHandler(), StepInfo("scroll", "マウスホイール相当のスクロールを実行", "action")),
    ("scrollIntoView", ScrollIntoViewHandler(), StepInfo("scrollIntoView", "要素が表示領域に入るまでスクロール", "action")),
    # 待機
    ("waitFor", WaitForHandler(), StepInfo("waitFor", "要素が指定状態になるまで待機", "wait")),
    ("waitForVisible", WaitForVisibleHandler(), StepInfo("waitForVisible", "要素が可視状態になるまで待機", "wait")),
    ("waitForHidden", WaitForHiddenHandler(), StepInfo("waitForHidden", "要素が非表示状態になるまで待機", "wait")),
    ("waitForNetworkIdle", WaitForNetworkIdleHandler(), StepInfo("waitForNetworkIdle", "ネットワークアイドル待機", "wait")),
    # 検証
    ("expectVisible", ExpectVisibleHandler(), StepInfo("expectVisible", "要素が可視状態であることを検証", "validation")),
    ("expectHidden", ExpectHiddenHandler(), StepInfo("expectHidden", "要素が非表示状態であることを検証", "validation")),
    ("expectText", ExpectTextHandler(), StepInfo("expectText", "要素が指定テキストを含むことを検証", "validation")),
    ("expectUrl", ExpectUrlHandler(), StepInfo("expectUrl", "URL が指定パターンに一致することを検証", "validation")),
    # 取得
    ("storeText", StoreTextHandler(), StepInfo("storeText", "要素のテキストを変数に格納", "retrieval")),
    ("storeAttr", StoreAttrHandler(), StepInfo("storeAttr", "要素の属性値を変数に格納", "retrieval")),
    # デバッグ
    ("screenshot", ScreenshotHandler(), StepInfo("screenshot", "スクリーンショットを撮影", "debug")),
    ("log", LogHandler(), StepInfo("log", "メッセージをログに出力", "debug")),
    ("dumpDom", DumpDomHandler(), StepInfo("dumpDom", "要素の DOM 構造をダンプ", "debug")),
    # セッション
    ("useStorageState", UseStorageStateHandler(), StepInfo("useStorageState", "保存済みストレージ状態を復元", "session")),
    ("saveStorageState", SaveStorageStateHandler(), StepInfo("saveStorageState", "現在のストレージ状態を保存", "session")),
    # 高レベル補助
    ("waitForToast", WaitForToastHandler(), StepInfo("waitForToast", "トースト通知の出現・消滅を待機", "high-level")),
    ("assertNoConsoleError", AssertNoConsoleErrorHandler(), StepInfo("assertNoConsoleError", "コンソールエラーがないことを検証", "high-level")),
    ("apiMock", ApiMockHandler(), StepInfo("apiMock", "Playwright route による API モック設定", "high-level")),
    ("routeStub", RouteStubHandler(), StepInfo("routeStub", "Playwright route による API スタブ設定", "high-level")),
]


def register_builtin_steps(registry: StepRegistry) -> None:
    """全標準ステップハンドラをレジストリに登録する。

    Args:
        registry: 登録先の StepRegistry
    """
    for name, handler, info in _BUILTIN_STEPS:
        registry.register(name, handler, info=info)
    logger.debug("標準ステップ %d 種を登録しました", len(_BUILTIN_STEPS))


def create_default_registry() -> StepRegistry:
    """標準ステップが登録済みの StepRegistry を生成する。

    Returns:
        全標準ステップが登録された StepRegistry
    """
    registry = StepRegistry()
    register_builtin_steps(registry)
    return registry
