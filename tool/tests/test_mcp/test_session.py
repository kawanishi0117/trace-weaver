"""
Session テスト — ブラウザセッション管理の単体テスト

Playwright ブラウザの起動・終了・状態管理を検証する。
実際のブラウザ起動はモックで代替し、ロジックのみテストする。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from brt.mcp.session import BrowserSession, SessionState


# ---------------------------------------------------------------------------
# SessionState のテスト
# ---------------------------------------------------------------------------

class TestSessionState:
    """SessionState 列挙型のテスト。"""

    def test_initial_state(self):
        """初期状態が IDLE であること。"""
        assert SessionState.IDLE.value == "idle"

    def test_all_states_exist(self):
        """全状態が定義されていること。"""
        states = {s.value for s in SessionState}
        assert states == {"idle", "launching", "active", "closing", "closed"}


# ---------------------------------------------------------------------------
# BrowserSession のテスト
# ---------------------------------------------------------------------------

class TestBrowserSession:
    """BrowserSession のライフサイクル管理テスト。"""

    def test_initial_state_is_idle(self):
        """初期状態が IDLE であること。"""
        session = BrowserSession()
        assert session.state == SessionState.IDLE

    def test_is_active_when_idle(self):
        """IDLE 状態では is_active が False であること。"""
        session = BrowserSession()
        assert session.is_active is False

    @pytest.mark.asyncio
    async def test_launch_changes_state(self):
        """launch() で状態が ACTIVE に変わること。"""
        session = BrowserSession()

        # Playwright をモック
        mock_pw = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        mock_pw.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        # async_playwright() は session.launch() 内でローカルインポートされる
        mock_async_pw_cm = AsyncMock()
        mock_async_pw_cm.start = AsyncMock(return_value=mock_pw)

        with patch(
            "playwright.async_api.async_playwright",
            return_value=mock_async_pw_cm,
        ):
            await session.launch(headed=False)

        assert session.state == SessionState.ACTIVE
        assert session.is_active is True

    @pytest.mark.asyncio
    async def test_close_changes_state(self):
        """close() で状態が CLOSED に変わること。"""
        session = BrowserSession()

        # 直接内部状態を設定してテスト
        session._state = SessionState.ACTIVE
        mock_browser = AsyncMock()
        mock_pw_instance = AsyncMock()
        session._browser = mock_browser
        session._pw_instance = mock_pw_instance

        await session.close()

        assert session.state == SessionState.CLOSED

    @pytest.mark.asyncio
    async def test_close_idle_session_is_noop(self):
        """IDLE 状態の close() はエラーにならないこと。"""
        session = BrowserSession()
        await session.close()  # 例外が発生しないこと
        assert session.state == SessionState.CLOSED

    def test_get_page_when_not_active(self):
        """非アクティブ時に page 取得で None が返ること。"""
        session = BrowserSession()
        assert session.page is None
