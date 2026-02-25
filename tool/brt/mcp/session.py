"""
Session — ブラウザセッション管理

Playwright ブラウザの起動・終了・状態管理を担当する。
MCP サーバーのライフサイクルに合わせてブラウザインスタンスを保持する。

主な機能:
  - ブラウザの起動（headed/headless 切り替え）
  - Context / Page の生成と管理
  - セッション状態の追跡
  - リソースの安全なクリーンアップ
"""

from __future__ import annotations

import enum
import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Page

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# セッション状態
# ---------------------------------------------------------------------------

class SessionState(enum.Enum):
    """ブラウザセッションの状態。"""

    IDLE = "idle"
    LAUNCHING = "launching"
    ACTIVE = "active"
    CLOSING = "closing"
    CLOSED = "closed"


# ---------------------------------------------------------------------------
# BrowserSession 本体
# ---------------------------------------------------------------------------

class BrowserSession:
    """Playwright ブラウザセッションの管理クラス。

    ブラウザの起動から終了までのライフサイクルを管理し、
    Page オブジェクトへのアクセスを提供する。
    """

    def __init__(self) -> None:
        """BrowserSession を初期化する。"""
        self._state: SessionState = SessionState.IDLE
        self._pw_instance: Optional[object] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    @property
    def state(self) -> SessionState:
        """現在のセッション状態を返す。"""
        return self._state

    @property
    def is_active(self) -> bool:
        """セッションがアクティブかどうかを返す。"""
        return self._state == SessionState.ACTIVE

    @property
    def context(self) -> Optional[BrowserContext]:
        """現在の BrowserContext を返す。非アクティブ時は None。"""
        if not self.is_active:
            return None
        return self._context

    @property
    def page(self) -> Optional[Page]:
        """現在の Page オブジェクトを返す。非アクティブ時は None。"""
        if not self.is_active:
            return None
        return self._page

    async def start_tracing(self) -> None:
        """Playwright トレースの記録を開始する。

        BrowserContext のトレーシング機能を使用して、
        操作のトレースを記録する。

        Raises:
            RuntimeError: セッションがアクティブでない場合
        """
        if not self.is_active or self._context is None:
            raise RuntimeError(
                "アクティブなセッションがありません。"
                "先に launch() を呼んでください。"
            )

        await self._context.tracing.start(
            screenshots=True,
            snapshots=True,
            sources=True,
        )
        logger.info("トレース記録を開始しました")

    async def launch(
        self,
        headed: bool = True,
        viewport_width: int = 1280,
        viewport_height: int = 720,
        record_video_dir: Optional[str] = None,
    ) -> None:
        """ブラウザを起動し、Page を生成する。

        Args:
            headed: True でブラウザウィンドウを表示
            viewport_width: ビューポート幅
            viewport_height: ビューポート高さ
            record_video_dir: 動画録画先ディレクトリ（None で録画しない）

        Raises:
            RuntimeError: 既にアクティブなセッションがある場合
        """
        if self._state == SessionState.ACTIVE:
            raise RuntimeError(
                "既にアクティブなセッションがあります。"
                "先に close() を呼んでください。"
            )

        self._state = SessionState.LAUNCHING
        logger.info("ブラウザを起動しています... (headed=%s)", headed)

        try:
            from playwright.async_api import async_playwright

            pw = await async_playwright().start()
            self._pw_instance = pw

            self._browser = await pw.chromium.launch(
                headless=not headed,
            )

            # BrowserContext のオプション構築
            context_options: dict = {
                "viewport": {"width": viewport_width, "height": viewport_height},
            }
            # 動画録画ディレクトリが指定されている場合は有効化
            if record_video_dir is not None:
                context_options["record_video_dir"] = record_video_dir
                context_options["record_video_size"] = {
                    "width": viewport_width,
                    "height": viewport_height,
                }
                logger.info("動画録画を有効化: %s", record_video_dir)

            self._context = await self._browser.new_context(**context_options)

            self._page = await self._context.new_page()
            self._state = SessionState.ACTIVE
            logger.info("ブラウザを起動しました")

        except Exception:
            self._state = SessionState.IDLE
            logger.exception("ブラウザの起動に失敗しました")
            raise

    async def close(self) -> None:
        """ブラウザを終了し、リソースをクリーンアップする。"""
        if self._state in (SessionState.CLOSED, SessionState.CLOSING):
            return

        self._state = SessionState.CLOSING
        logger.info("ブラウザを終了しています...")

        try:
            if self._browser is not None:
                await self._browser.close()
            if self._pw_instance is not None and hasattr(self._pw_instance, "stop"):
                await self._pw_instance.stop()
        except Exception:
            logger.exception("ブラウザの終了中にエラーが発生しました")
        finally:
            self._browser = None
            self._context = None
            self._page = None
            self._pw_instance = None
            self._state = SessionState.CLOSED
            logger.info("ブラウザを終了しました")
