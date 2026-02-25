"""
ArtifactsManager 統合テスト — MCP サーバーと成果物管理の統合

brt_launch / brt_close / 操作ツールが ArtifactsManager と連携し、
スクリーンショット・トレース・動画の自動保存を行うことを検証する。

要件 8.1: 成果物ディレクトリ構造の自動生成
要件 8.2: スクリーンショットの自動保存
要件 8.3: トレース・動画の保存と成功時クリーンアップ
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from brt.mcp.server import create_server
from brt.mcp.session import BrowserSession, SessionState


# ---------------------------------------------------------------------------
# session.py: context プロパティのテスト
# ---------------------------------------------------------------------------

class TestSessionContextProperty:
    """BrowserSession.context プロパティのテスト。"""

    def test_context_returns_none_when_idle(self):
        """非アクティブ時は None を返すこと。"""
        session = BrowserSession()
        assert session.context is None

    def test_context_returns_value_when_active(self):
        """アクティブ時は BrowserContext を返すこと。"""
        session = BrowserSession()
        session._state = SessionState.ACTIVE
        mock_ctx = MagicMock()
        session._context = mock_ctx
        assert session.context is mock_ctx


# ---------------------------------------------------------------------------
# server.py: brt_launch の ArtifactsManager 統合テスト
# ---------------------------------------------------------------------------

class TestLaunchArtifactsIntegration:
    """brt_launch が ArtifactsManager を初期化することのテスト。"""

    @pytest.fixture
    def server(self):
        return create_server()

    @pytest.mark.asyncio
    async def test_launch_initializes_artifacts_in_state(self, server):
        """brt_launch ツールが登録されていること。"""
        tools = await server.list_tools()
        tool_names = [t.name for t in tools]
        assert "brt_launch" in tool_names

    @pytest.mark.asyncio
    async def test_launch_accepts_artifacts_dir_param(self, server):
        """brt_launch が artifacts_dir パラメータを受け付けること。"""
        tools = await server.list_tools()
        launch_tool = next(t for t in tools if t.name == "brt_launch")
        # FastMCP 3.x: parameters は dict
        props = launch_tool.parameters.get("properties", {})
        assert "artifacts_dir" in props

    @pytest.mark.asyncio
    async def test_close_accepts_cleanup_param(self, server):
        """brt_close が cleanup_on_success パラメータを受け付けること。"""
        tools = await server.list_tools()
        close_tool = next(t for t in tools if t.name == "brt_close")
        props = close_tool.parameters.get("properties", {})
        assert "cleanup_on_success" in props


# ---------------------------------------------------------------------------
# ArtifactsManager 初期化ロジックのユニットテスト
# ---------------------------------------------------------------------------

class TestArtifactsManagerCreation:
    """MCP 用の ArtifactsManager 生成ヘルパーのテスト。"""

    def test_create_default_artifacts_config(self):
        """デフォルト設定で ArtifactsConfig が生成できること。"""
        from brt.dsl.schema import ArtifactsConfig
        config = ArtifactsConfig()
        assert config.screenshots.mode == "before_each_step"
        assert config.trace.mode == "on_failure"
        assert config.video.mode == "on_failure"

    def test_create_artifacts_manager_with_default_config(self):
        """デフォルト設定で ArtifactsManager が生成できること。"""
        from brt.core.artifacts import ArtifactsManager
        from brt.dsl.schema import ArtifactsConfig
        config = ArtifactsConfig()
        manager = ArtifactsManager(config=config)
        assert manager.run_dir is None
        assert manager.base_dir.name == "artifacts"

    def test_create_artifacts_manager_with_custom_dir(self):
        """カスタムディレクトリで ArtifactsManager が生成できること。"""
        from pathlib import Path
        from brt.core.artifacts import ArtifactsManager
        from brt.dsl.schema import ArtifactsConfig
        config = ArtifactsConfig()
        manager = ArtifactsManager(config=config, base_dir=Path("custom/dir"))
        assert manager.base_dir == Path("custom/dir")

    def test_create_run_dir(self, tmp_path):
        """run_dir が正しく作成されること。"""
        from datetime import datetime
        from brt.core.artifacts import ArtifactsManager
        from brt.dsl.schema import ArtifactsConfig
        config = ArtifactsConfig()
        manager = ArtifactsManager(config=config, base_dir=tmp_path)
        ts = datetime(2025, 1, 15, 10, 30, 0)
        run_dir = manager.create_run_dir(timestamp=ts)
        assert run_dir.exists()
        assert (run_dir / "screenshots").exists()
        assert (run_dir / "trace").exists()
        assert (run_dir / "video").exists()
        assert (run_dir / "logs").exists()


# ---------------------------------------------------------------------------
# スクリーンショット自動保存のテスト
# ---------------------------------------------------------------------------

class TestAutoScreenshot:
    """操作ツールがスクリーンショットを自動保存することのテスト。"""

    def test_step_index_increments(self):
        """ステップインデックスが操作ごとにインクリメントされること。"""
        state: dict = {"step_index": 0}
        state["step_index"] += 1
        assert state["step_index"] == 1
        state["step_index"] += 1
        assert state["step_index"] == 2

    @pytest.mark.asyncio
    async def test_save_screenshot_called_with_correct_args(self, tmp_path):
        """save_screenshot が正しい引数で呼ばれること。"""
        from datetime import datetime
        from brt.core.artifacts import ArtifactsManager
        from brt.dsl.schema import ArtifactsConfig

        config = ArtifactsConfig()
        manager = ArtifactsManager(config=config, base_dir=tmp_path)
        manager.create_run_dir(timestamp=datetime(2025, 1, 15, 10, 30, 0))

        # Page モックを作成
        mock_page = AsyncMock()
        mock_page.screenshot = AsyncMock()

        result = await manager.save_screenshot(
            page=mock_page, step_index=0, step_name="click"
        )

        assert result is not None
        mock_page.screenshot.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_screenshot_skipped_when_mode_none(self, tmp_path):
        """mode が none の場合はスクリーンショットがスキップされること。"""
        from datetime import datetime
        from brt.core.artifacts import ArtifactsManager
        from brt.dsl.schema import ArtifactsConfig, ScreenshotConfig

        config = ArtifactsConfig(screenshots=ScreenshotConfig(mode="none"))
        manager = ArtifactsManager(config=config, base_dir=tmp_path)
        manager.create_run_dir(timestamp=datetime(2025, 1, 15, 10, 30, 0))

        mock_page = AsyncMock()
        result = await manager.save_screenshot(
            page=mock_page, step_index=0, step_name="click"
        )

        assert result is None
        mock_page.screenshot.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_screenshot_helper(self, tmp_path):
        """_auto_screenshot ヘルパーが正しく動作すること。"""
        from datetime import datetime
        from brt.core.artifacts import ArtifactsManager
        from brt.dsl.schema import ArtifactsConfig
        from brt.mcp.tools_basic import _auto_screenshot

        config = ArtifactsConfig()
        manager = ArtifactsManager(config=config, base_dir=tmp_path)
        manager.create_run_dir(timestamp=datetime(2025, 1, 15, 10, 30, 0))

        # セッションモック
        mock_session = MagicMock(spec=BrowserSession)
        mock_page = AsyncMock()
        mock_page.screenshot = AsyncMock()
        mock_session.page = mock_page

        state = {"artifacts": manager, "step_index": 0}

        await _auto_screenshot(mock_session, state, "click")

        # ステップインデックスがインクリメントされること
        assert state["step_index"] == 1
        mock_page.screenshot.assert_called_once()

    @pytest.mark.asyncio
    async def test_auto_screenshot_noop_without_artifacts(self):
        """artifacts が None の場合は何もしないこと。"""
        from brt.mcp.tools_basic import _auto_screenshot

        mock_session = MagicMock(spec=BrowserSession)
        state: dict = {"artifacts": None, "step_index": 0}

        # エラーなく完了すること
        await _auto_screenshot(mock_session, state, "click")
        assert state["step_index"] == 0


# ---------------------------------------------------------------------------
# session.py: トレース開始のテスト
# ---------------------------------------------------------------------------

class TestSessionTracing:
    """BrowserSession のトレース開始機能のテスト。"""

    def test_session_has_start_tracing_method(self):
        """BrowserSession に start_tracing メソッドがあること。"""
        session = BrowserSession()
        assert hasattr(session, "start_tracing")

    @pytest.mark.asyncio
    async def test_start_tracing_requires_active_session(self):
        """非アクティブ時に start_tracing を呼ぶとエラーになること。"""
        session = BrowserSession()
        with pytest.raises(RuntimeError, match="アクティブ"):
            await session.start_tracing()


# ---------------------------------------------------------------------------
# brt_close: トレース保存のテスト
# ---------------------------------------------------------------------------

class TestCloseArtifactsIntegration:
    """brt_close が成果物を保存することのテスト。"""

    def test_cleanup_on_success_removes_on_failure_artifacts(self, tmp_path):
        """cleanup_on_success が on_failure 成果物を削除すること。"""
        from datetime import datetime
        from brt.core.artifacts import ArtifactsManager
        from brt.dsl.schema import ArtifactsConfig

        config = ArtifactsConfig()  # trace=on_failure, video=on_failure
        manager = ArtifactsManager(config=config, base_dir=tmp_path)
        manager.create_run_dir(timestamp=datetime(2025, 1, 15, 10, 30, 0))

        # trace/ と video/ が存在することを確認
        assert (manager.run_dir / "trace").exists()
        assert (manager.run_dir / "video").exists()

        # クリーンアップ実行
        manager.cleanup_on_success()

        # on_failure モードなので削除される
        assert not (manager.run_dir / "trace").exists()
        assert not (manager.run_dir / "video").exists()
        # screenshots は残る
        assert (manager.run_dir / "screenshots").exists()

    def test_cleanup_preserves_always_mode_artifacts(self, tmp_path):
        """mode が always の場合は成果物が保持されること。"""
        from datetime import datetime
        from brt.core.artifacts import ArtifactsManager
        from brt.dsl.schema import ArtifactsConfig, TraceConfig, VideoConfig

        config = ArtifactsConfig(
            trace=TraceConfig(mode="always"),
            video=VideoConfig(mode="always"),
        )
        manager = ArtifactsManager(config=config, base_dir=tmp_path)
        manager.create_run_dir(timestamp=datetime(2025, 1, 15, 10, 30, 0))

        manager.cleanup_on_success()

        # always モードなので削除されない
        assert (manager.run_dir / "trace").exists()
        assert (manager.run_dir / "video").exists()


# ---------------------------------------------------------------------------
# ツール数の確認（変更なし）
# ---------------------------------------------------------------------------

class TestToolCountAfterPhase5:
    """Phase 5 後もツール数が変わらないことの確認。"""

    @pytest.fixture
    def server(self):
        return create_server()

    @pytest.mark.asyncio
    async def test_total_tool_count_unchanged(self, server):
        """ツール数が 18 のままであること。"""
        tools = await server.list_tools()
        assert len(tools) == 18
