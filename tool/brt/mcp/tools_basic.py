"""
基本操作ツール — ナビゲーション・操作・状態確認・検証・記録制御

MCP サーバーに登録する基本操作ツールを定義する。
ブラウザ操作を実行し、brt YAML DSL として自動記録する。

主なツール:
  - brt_navigate / brt_back: ナビゲーション
  - brt_click / brt_fill / brt_select / brt_press: 操作
  - brt_snapshot / brt_screenshot: 状態確認
  - brt_assert_visible / brt_assert_text: 検証
  - brt_add_section / brt_save: 記録制御
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastmcp import FastMCP

from .locator_builder import build_locator
from .selector_mapper import SelectorMapper
from .session import BrowserSession
from .snapshot import SnapshotParser

if TYPE_CHECKING:
    from ..core.artifacts import ArtifactsManager

logger = logging.getLogger(__name__)


async def _auto_screenshot(
    session: BrowserSession,
    state: dict[str, Any],
    step_name: str,
) -> None:
    """操作前にスクリーンショットを自動保存する。

    ArtifactsManager が state に設定されている場合のみ実行する。
    エラーが発生しても操作を中断しない。

    Args:
        session: ブラウザセッション
        state: 共有状態辞書
        step_name: ステップ名（ファイル名に使用）
    """
    artifacts: ArtifactsManager | None = state.get("artifacts")
    if artifacts is None:
        return

    page = session.page
    if page is None:
        return

    try:
        idx = state.get("step_index", 0)
        await artifacts.save_screenshot(page, idx, step_name)
        state["step_index"] = idx + 1
    except Exception:
        logger.warning("スクリーンショットの自動保存に失敗しました: %s", step_name)


def register_basic_tools(
    mcp: FastMCP,
    session: BrowserSession,
    state: dict[str, Any],
    snapshot_parser: SnapshotParser,
    selector_mapper: SelectorMapper,
) -> None:
    """基本操作ツールを MCP サーバーに登録する。

    Args:
        mcp: FastMCP サーバーインスタンス
        session: ブラウザセッション
        state: 共有状態辞書（recorder 等）
        snapshot_parser: スナップショットパーサー
        selector_mapper: セレクタマッパー
    """

    # -------------------------------------------------------------------
    # ナビゲーションツール
    # -------------------------------------------------------------------

    @mcp.tool
    async def brt_navigate(url: str) -> str:
        """Navigate to a URL.

        Args:
            url: The URL to navigate to

        Returns:
            Status message with current URL
        """
        page = session.page
        if page is None:
            return "Error: Browser not launched. Call brt_launch first."

        await _auto_screenshot(session, state, "navigate")
        await page.goto(url)
        await page.wait_for_load_state("domcontentloaded")

        rec = state["recorder"]
        if rec is not None:
            rec.add_step("goto", {"url": url})

        return f"Navigated to {url}"

    @mcp.tool
    async def brt_back() -> str:
        """Go back to the previous page.

        Returns:
            Status message
        """
        page = session.page
        if page is None:
            return "Error: Browser not launched. Call brt_launch first."

        await _auto_screenshot(session, state, "back")
        await page.go_back()

        rec = state["recorder"]
        if rec is not None:
            rec.add_step("back", {})

        return "Navigated back"

    # -------------------------------------------------------------------
    # 操作ツール
    # -------------------------------------------------------------------

    @mcp.tool
    async def brt_click(element: str, ref: str) -> str:
        """Click an element on the page.

        Args:
            element: Description of the element (for logging)
            ref: Reference number from brt_snapshot output

        Returns:
            Status message
        """
        page = session.page
        if page is None:
            return "Error: Browser not launched. Call brt_launch first."

        elem = snapshot_parser.get_by_ref(ref)
        if elem is None:
            return f"Error: Element ref [{ref}] not found. Call brt_snapshot first."

        by_selector = selector_mapper.to_by_selector(elem)
        locator = build_locator(page, by_selector)
        await _auto_screenshot(session, state, "click")
        await locator.click()

        rec = state["recorder"]
        if rec is not None:
            rec.add_step("click", {"by": by_selector})

        return f"Clicked [{ref}] {elem.role} \"{elem.name}\""

    @mcp.tool
    async def brt_fill(element: str, ref: str, value: str) -> str:
        """Type text into an input field.

        Args:
            element: Description of the element (for logging)
            ref: Reference number from brt_snapshot output
            value: Text to type

        Returns:
            Status message
        """
        page = session.page
        if page is None:
            return "Error: Browser not launched. Call brt_launch first."

        elem = snapshot_parser.get_by_ref(ref)
        if elem is None:
            return f"Error: Element ref [{ref}] not found. Call brt_snapshot first."

        by_selector = selector_mapper.to_by_selector(elem)
        locator = build_locator(page, by_selector)
        await _auto_screenshot(session, state, "fill")
        await locator.fill(value)

        # secret 判定
        params: dict = {"by": by_selector, "value": value}
        if selector_mapper.is_secret_field(elem):
            params["secret"] = True

        rec = state["recorder"]
        if rec is not None:
            rec.add_step("fill", params)

        return f"Filled [{ref}] {elem.role} \"{elem.name}\" with text"

    @mcp.tool
    async def brt_select(element: str, ref: str, value: str) -> str:
        """Select an option from a dropdown.

        Args:
            element: Description of the element (for logging)
            ref: Reference number from brt_snapshot output
            value: Option value or label to select

        Returns:
            Status message
        """
        page = session.page
        if page is None:
            return "Error: Browser not launched. Call brt_launch first."

        elem = snapshot_parser.get_by_ref(ref)
        if elem is None:
            return f"Error: Element ref [{ref}] not found. Call brt_snapshot first."

        by_selector = selector_mapper.to_by_selector(elem)
        locator = build_locator(page, by_selector)
        await _auto_screenshot(session, state, "select")
        await locator.select_option(value)

        rec = state["recorder"]
        if rec is not None:
            rec.add_step("selectOption", {"by": by_selector, "value": value})

        return f"Selected \"{value}\" in [{ref}] {elem.role} \"{elem.name}\""

    @mcp.tool
    async def brt_press(key: str) -> str:
        """Press a keyboard key.

        Args:
            key: Key name (e.g. 'Enter', 'Tab', 'Escape', 'ArrowDown')

        Returns:
            Status message
        """
        page = session.page
        if page is None:
            return "Error: Browser not launched. Call brt_launch first."

        await _auto_screenshot(session, state, "press")
        await page.keyboard.press(key)

        rec = state["recorder"]
        if rec is not None:
            rec.add_step("press", {"key": key})

        return f"Pressed key: {key}"

    # -------------------------------------------------------------------
    # 状態確認ツール
    # -------------------------------------------------------------------

    @mcp.tool
    async def brt_snapshot() -> str:
        """Capture accessibility snapshot of the current page.

        Returns a list of interactive elements with reference numbers.
        Use these ref numbers with brt_click, brt_fill, etc.

        Returns:
            Formatted list of interactive elements with ref numbers
        """
        page = session.page
        if page is None:
            return "Error: Browser not launched. Call brt_launch first."

        # Playwright の aria_snapshot() でアクセシビリティツリーを取得
        aria_yaml = await page.locator("body").aria_snapshot()

        elements = snapshot_parser.parse(aria_yaml)
        snapshot_parser.set_elements(elements)

        # ページ情報を付加
        current_url = page.url
        title = await page.title()
        header = f"Page: {title}\nURL: {current_url}\n\n"

        return header + snapshot_parser.format_for_ai()

    @mcp.tool
    async def brt_screenshot() -> str:
        """Take a screenshot of the current page.

        Returns:
            Base64 encoded screenshot image (PNG)
        """
        page = session.page
        if page is None:
            return "Error: Browser not launched. Call brt_launch first."

        screenshot_bytes = await page.screenshot(type="png")
        b64 = base64.b64encode(screenshot_bytes).decode("ascii")

        rec = state["recorder"]
        if rec is not None:
            rec.add_step("screenshot", {})

        return f"data:image/png;base64,{b64}"

    # -------------------------------------------------------------------
    # 検証ツール
    # -------------------------------------------------------------------

    @mcp.tool
    async def brt_assert_visible(element: str, ref: str) -> str:
        """Assert that an element is visible on the page.

        Args:
            element: Description of the element
            ref: Reference number from brt_snapshot output

        Returns:
            Status message
        """
        page = session.page
        if page is None:
            return "Error: Browser not launched. Call brt_launch first."

        elem = snapshot_parser.get_by_ref(ref)
        if elem is None:
            return f"Error: Element ref [{ref}] not found. Call brt_snapshot first."

        by_selector = selector_mapper.to_by_selector(elem)
        locator = build_locator(page, by_selector)

        from playwright.async_api import expect
        await expect(locator).to_be_visible()

        rec = state["recorder"]
        if rec is not None:
            rec.add_step("expectVisible", {"by": by_selector})

        return f"Verified visible: [{ref}] {elem.role} \"{elem.name}\""

    @mcp.tool
    async def brt_assert_text(text: str) -> str:
        """Assert that specific text is visible on the page.

        Args:
            text: Text content to verify

        Returns:
            Status message
        """
        page = session.page
        if page is None:
            return "Error: Browser not launched. Call brt_launch first."

        locator = page.get_by_text(text)

        from playwright.async_api import expect
        await expect(locator.first).to_be_visible()

        rec = state["recorder"]
        if rec is not None:
            rec.add_step("expectText", {"text": text})

        return f"Verified text visible: \"{text}\""

    # -------------------------------------------------------------------
    # 記録制御ツール
    # -------------------------------------------------------------------

    @mcp.tool
    async def brt_add_section(name: str) -> str:
        """Add a section divider to the recording.

        Args:
            name: Section name (e.g. 'Login', 'Search', 'Checkout')

        Returns:
            Status message
        """
        rec = state["recorder"]
        if rec is None:
            return "Error: Recording not started. Call brt_launch first."

        rec.add_section(name)
        return f"Added section: {name}"

    @mcp.tool
    async def brt_save(
        output_path: str = "flows/ai-recorded.yaml",
    ) -> str:
        """Save current recording as YAML without closing browser.

        Args:
            output_path: Path to save the YAML file

        Returns:
            Status message with saved file path
        """
        rec = state["recorder"]
        if rec is None:
            return "Error: Recording not started. Call brt_launch first."

        rec.save_yaml(Path(output_path))
        return f"Scenario saved to {output_path} ({rec.step_count} steps)"
