"""
ScriptWriter — 記録結果を Python スクリプトに変換

BrowserRecorder が記録した RecordedAction リストを
Playwright codegen 互換の Python スクリプトに変換する。
既存の import-flow パイプライン（PyAstParser → Mapper → Heuristics）
でそのまま YAML に変換できる形式で出力する。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .recorder import RecordedAction

logger = logging.getLogger(__name__)


class ScriptWriter:
    """記録結果を Python スクリプトに変換するライター。

    RecordedAction リストを Playwright codegen 互換の
    Python スクリプト形式に変換して出力する。

    使用例::

        writer = ScriptWriter()
        writer.write(actions, Path("output.py"))
    """

    def write(
        self,
        actions: list[RecordedAction],
        output_path: Path,
        channel: str = "chromium",
        viewport: tuple[int, int] = (1280, 720),
    ) -> None:
        """記録結果を Python スクリプトとして出力する。

        Args:
            actions: 記録されたアクションのリスト
            output_path: 出力先ファイルパス
            channel: ブラウザチャンネル
            viewport: ビューポートサイズ
        """
        lines = self._build_script(actions, channel, viewport)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Python script written: %s", output_path)

    def _build_script(
        self,
        actions: list[RecordedAction],
        channel: str,
        viewport: tuple[int, int],
    ) -> list[str]:
        """Python スクリプトの行リストを構築する。

        Args:
            actions: 記録されたアクションのリスト
            channel: ブラウザチャンネル
            viewport: ビューポートサイズ

        Returns:
            スクリプトの行リスト
        """
        lines: list[str] = []

        # ヘッダー（codegen 互換）
        lines.append("import re")
        lines.append(
            "from playwright.sync_api import Playwright, "
            "sync_playwright, expect"
        )
        lines.append("")
        lines.append("")
        lines.append("def run(playwright: Playwright) -> None:")

        # ブラウザ起動
        channel_arg = (
            f'channel="{channel}", ' if channel != "chromium" else ""
        )
        lines.append(
            f"    browser = playwright.chromium.launch("
            f"{channel_arg}headless=False)"
        )
        lines.append(
            f'    context = browser.new_context('
            f'viewport={{"width":{viewport[0]},"height":{viewport[1]}}})'
        )
        lines.append("    page = context.new_page()")

        # アクションを変換
        for action in actions:
            line = self._action_to_line(action)
            if line:
                lines.append(f"    {line}")

        # フッター（codegen 互換）
        lines.append("    page.close()")
        lines.append("")
        lines.append("    # ---------------------")
        lines.append("    context.close()")
        lines.append("    browser.close()")
        lines.append("")
        lines.append("")
        lines.append("with sync_playwright() as playwright:")
        lines.append("    run(playwright)")
        lines.append("")

        return lines

    def _action_to_line(self, action: RecordedAction) -> str:
        """単一アクションを Python コード行に変換する。

        Args:
            action: 記録されたアクション

        Returns:
            Python コード行（空文字列の場合はスキップ）
        """
        if action.action == "goto":
            url = action.url
            if url:
                return f'page.goto("{_escape_string(url)}")'
            return ""

        if action.action == "scroll":
            dx = int((action.selector or {}).get("deltaX", 0) if action.selector else 0)
            dy = int((action.selector or {}).get("deltaY", 0) if action.selector else 0)
            return f"page.mouse.wheel({dx}, {dy})"

        selector = action.selector
        if not selector:
            return ""

        locator = self._selector_to_locator(selector)
        if not locator:
            return ""

        if action.action == "click":
            return f"{locator}.click()"

        if action.action == "scrollIntoView":
            return f"{locator}.scroll_into_view_if_needed()"

        if action.action == "fill":
            value = _escape_string(action.value or "")
            return f'{locator}.fill("{value}")'

        if action.action == "press":
            key = action.key or ""
            return f'{locator}.press("{key}")'

        return ""

    def _selector_to_locator(self, selector: dict) -> str:
        """セレクタ辞書を Playwright locator コードに変換する。

        Args:
            selector: セレクタ情報の辞書

        Returns:
            Playwright locator コード文字列
        """
        sel_type = selector.get("type", "")
        value = selector.get("value", "")

        if sel_type == "testId":
            return f'page.get_by_test_id("{_escape_string(value)}")'

        if sel_type == "role":
            role = selector.get("role", "")
            name = selector.get("name")
            if name:
                escaped_name = _escape_string(name)
                return (
                    f'page.get_by_role("{role}", '
                    f'name="{escaped_name}", exact=True)'
                )
            return f'page.get_by_role("{role}")'

        if sel_type == "label":
            return f'page.get_by_label("{_escape_string(value)}")'

        if sel_type == "placeholder":
            return (
                f'page.get_by_placeholder("{_escape_string(value)}")'
            )

        if sel_type == "text":
            return f'page.get_by_text("{_escape_string(value)}")'

        if sel_type == "css":
            return f'page.locator("{_escape_string(value)}")'

        return ""


def _escape_string(s: str) -> str:
    """Python 文字列リテラル用にエスケープする。

    Args:
        s: エスケープ対象の文字列

    Returns:
        エスケープ済み文字列
    """
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
