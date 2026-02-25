"""
BrowserRecorder — ハイライトなしブラウザ操作記録エンジン

Playwright codegen の代替として、赤いハイライト枠なしで
ブラウザ操作を記録する。ページに JavaScript を注入して
click / fill / press / navigation イベントを捕捉する。

主な機能:
  - ブラウザ起動とページ操作の記録
  - セレクタ情報の自動抽出（testId, role, label, text, css）
  - 記録結果を RecordedAction リストとして返却
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 注入スクリプトのパス
_INJECTED_JS_PATH = Path(__file__).parent / "injected.js"


@dataclass
class RecordedAction:
    """記録された単一のブラウザ操作。

    Attributes:
        action: 操作種別（click, fill, press, goto）
        selector: セレクタ情報の辞書
        value: 入力値（fill の場合）
        key: キー名（press の場合）
        url: 操作時の URL
        timestamp: タイムスタンプ（ミリ秒）
    """

    action: str
    selector: Optional[dict] = None
    value: Optional[str] = None
    key: Optional[str] = None
    url: str = ""
    timestamp: int = 0


class BrowserRecorder:
    """ハイライトなしブラウザ操作記録エンジン。

    Playwright sync API でブラウザを起動し、ページに JavaScript を
    注入してユーザー操作を記録する。codegen と異なり、
    赤いハイライト枠は表示されない。

    使用例::

        recorder = BrowserRecorder()
        actions = recorder.record(
            url="https://example.com",
            channel="chrome",
        )
    """

    def __init__(self) -> None:
        """レコーダーを初期化する。"""
        self._actions: list[RecordedAction] = []
        self._injected_js: str = ""
        self._last_url: str = ""

    def record(
        self,
        url: str,
        channel: str = "chromium",
        viewport: tuple[int, int] = (1280, 720),
    ) -> list[RecordedAction]:
        """ブラウザを起動して操作を記録する。

        ブラウザが閉じられるまで記録を続行する。
        記録中はハイライト枠は表示されない。

        Args:
            url: 記録開始 URL
            channel: ブラウザチャンネル（chromium / chrome / msedge）
            viewport: ビューポートサイズ (幅, 高さ)

        Returns:
            記録された操作のリスト
        """
        from playwright.sync_api import sync_playwright

        self._actions = []
        self._last_url = url

        # 注入スクリプトを読み込み
        self._injected_js = _INJECTED_JS_PATH.read_text(encoding="utf-8")

        # 最初の goto アクションを追加
        self._actions.append(RecordedAction(
            action="goto",
            url=url,
        ))

        with sync_playwright() as pw:
            # ブラウザ起動
            launch_kwargs: dict = {"headless": False}
            if channel != "chromium":
                launch_kwargs["channel"] = channel

            browser = pw.chromium.launch(**launch_kwargs)

            context = browser.new_context(
                viewport={"width": viewport[0], "height": viewport[1]},
            )

            # 新しいページが作成されるたびにスクリプトを注入
            context.on("page", self._setup_page)

            page = context.new_page()
            self._setup_page(page)

            # URL に遷移
            page.goto(url)
            page.wait_for_load_state("domcontentloaded")

            logger.info("記録開始: %s", url)
            logger.info("操作を記録中... ブラウザを閉じると記録が終了します。")

            # ブラウザが閉じられるまで待機
            # context の全ページが閉じられるか、ブラウザ自体が閉じられるまで待つ
            try:
                # ページの close イベントを待機
                page.wait_for_event("close", timeout=0)
            except Exception:
                pass

            # ブラウザを閉じる
            try:
                browser.close()
            except Exception:
                pass

        return self._actions

    def _setup_page(self, page) -> None:
        """ページにイベントリスナーを設定する。

        expose_function でページ側の JavaScript から
        Python 側にアクションデータを送信できるようにする。

        Args:
            page: Playwright の Page オブジェクト
        """
        # Python 側のコールバック関数をページに公開
        try:
            page.expose_function("__brt_on_action", self._on_action)
        except Exception:
            # 既に公開済みの場合は無視
            pass

        # ページ遷移時にスクリプトを再注入
        page.on("load", lambda: self._inject_script(page))

        # 初回注入
        self._inject_script(page)

    def _inject_script(self, page) -> None:
        """ページに記録用 JavaScript を注入する。

        Args:
            page: Playwright の Page オブジェクト
        """
        try:
            page.evaluate(self._injected_js)
        except Exception as exc:
            logger.debug("スクリプト注入をスキップ: %s", exc)

    def _on_action(self, data_json: str) -> None:
        """ページ側から送信されたアクションデータを処理する。

        Args:
            data_json: JSON 形式のアクションデータ
        """
        try:
            data = json.loads(data_json)
        except json.JSONDecodeError:
            logger.warning("不正なアクションデータ: %s", data_json)
            return

        action_type = data.get("action", "")
        current_url = data.get("url", "")

        # ページ遷移の検出: URL が変わったら goto を挿入
        if current_url and current_url != self._last_url:
            # click による遷移の場合は goto を追加しない
            # （click アクション自体が遷移を引き起こす）
            self._last_url = current_url

        action = RecordedAction(
            action=action_type,
            selector=data.get("selector"),
            value=data.get("value"),
            key=data.get("key"),
            url=current_url,
            timestamp=data.get("timestamp", 0),
        )

        self._actions.append(action)
        logger.debug("記録: %s %s", action_type, data.get("selector", {}))
