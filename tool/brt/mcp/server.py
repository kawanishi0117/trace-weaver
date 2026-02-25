"""
brt MCP Server — AI ブラウザ操作 + 自動記録サーバー

FastMCP を使用して、AI エージェントがブラウザを操作し、
操作を brt YAML DSL として自動記録する MCP サーバーを提供する。

ツール定義は以下のモジュールに分離:
  - tools_basic: 基本操作ツール（navigate, click, fill 等）
  - tools_highlevel: 高レベルステップツール（overlay, wijmo 等）

本モジュールはサーバー生成とライフサイクル管理（launch, close）を担当する。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastmcp import FastMCP

from ..core.artifacts import ArtifactsManager
from ..dsl.schema import (
    ArtifactsConfig,
    ScreenshotConfig,
    TraceConfig,
    VideoConfig,
)
from .config import ServerConfig, load_config_from_env
from .recorder import Recorder
from .selector_mapper import SelectorMapper
from .session import BrowserSession
from .snapshot import SnapshotParser
from .tools_basic import register_basic_tools
from .tools_highlevel import register_highlevel_tools

logger = logging.getLogger(__name__)


def create_server(config: Optional[ServerConfig] = None) -> FastMCP:
    """brt MCP サーバーを生成する。

    Args:
        config: サーバー設定。None の場合は環境変数から読み込む。

    Returns:
        設定済みの FastMCP サーバーインスタンス
    """
    if config is None:
        config = load_config_from_env()

    mcp = FastMCP("brt-browser")

    # 共有状態（ツール間で共有）
    session = BrowserSession()
    recorder: Optional[Recorder] = None
    snapshot_parser = SnapshotParser()
    selector_mapper = SelectorMapper()

    # 状態を保持するための可変コンテナ
    state: dict = {
        "recorder": recorder,
        "artifacts": None,       # ArtifactsManager インスタンス
        "step_index": 0,         # スクリーンショット用ステップ番号
        "config": config,        # サーバー設定
        "has_error": False,      # エラー発生フラグ（動画保存判定用）
    }

    # -------------------------------------------------------------------
    # ライフサイクルツール（launch / close）
    # -------------------------------------------------------------------

    @mcp.tool
    async def brt_launch(
        url: str,
        title: str = "AI Recorded Scenario",
        headed: Optional[bool] = None,
        artifacts_dir: Optional[str] = None,
        video_mode: Optional[str] = None,
        trace_mode: Optional[str] = None,
        screenshot_mode: Optional[str] = None,
    ) -> str:
        """Launch browser and start recording.

        Args:
            url: Initial URL to navigate to
            title: Scenario title for the YAML output
            headed: Show browser window. None uses server config.
            artifacts_dir: Directory for artifacts. None uses server config.
            video_mode: Video mode (on_failure/always/none). None uses config.
            trace_mode: Trace mode (on_failure/always/none). None uses config.
            screenshot_mode: Screenshot mode. None uses server config.

        Returns:
            Status message with page info
        """
        # サーバー設定をベースに、ツール引数で上書き
        cfg = state["config"]
        effective_headed = headed if headed is not None else cfg.headed
        effective_artifacts_dir = artifacts_dir or cfg.artifacts_dir
        effective_video = video_mode or cfg.video_mode
        effective_trace = trace_mode or cfg.trace_mode
        effective_screenshot = screenshot_mode or cfg.screenshot_mode

        # ArtifactsConfig を構築
        arts_config = ArtifactsConfig(
            screenshots=ScreenshotConfig(mode=effective_screenshot),
            trace=TraceConfig(mode=effective_trace),
            video=VideoConfig(mode=effective_video),
        )

        # ArtifactsManager を初期化
        artifacts = ArtifactsManager(
            config=arts_config,
            base_dir=Path(effective_artifacts_dir),
        )
        artifacts.create_run_dir()
        state["artifacts"] = artifacts
        state["has_error"] = False

        # 動画録画ディレクトリ（mode が none 以外なら有効化）
        record_video_dir: Optional[str] = None
        if effective_video != "none" and artifacts.run_dir is not None:
            video_dir = artifacts.run_dir / "video"
            record_video_dir = str(video_dir)

        # ブラウザ起動
        await session.launch(
            headed=effective_headed,
            viewport_width=cfg.viewport_width,
            viewport_height=cfg.viewport_height,
            record_video_dir=record_video_dir,
        )

        state["recorder"] = Recorder(title=title, base_url=url)
        state["step_index"] = 0

        # トレース記録を開始
        if effective_trace != "none":
            try:
                await session.start_tracing()
            except Exception:
                logger.warning("トレース記録の開始に失敗しました（続行します）")

        page = session.page
        if page is not None:
            await page.goto(url)
            await page.wait_for_load_state("domcontentloaded")

        # goto ステップを記録
        rec = state["recorder"]
        if rec is not None:
            rec.add_step("goto", {"url": url})

        run_dir = artifacts.run_dir
        settings_info = (
            f"headed={effective_headed}, "
            f"video={effective_video}, "
            f"trace={effective_trace}, "
            f"screenshot={effective_screenshot}"
        )
        return (
            f"Browser launched. Navigated to {url}.\n"
            f"Artifacts: {run_dir}\n"
            f"Settings: {settings_info}"
        )

    @mcp.tool
    async def brt_close(
        output_path: str = "flows/ai-recorded.yaml",
        cleanup_on_success: bool = True,
        has_error: Optional[bool] = None,
    ) -> str:
        """Close browser and save recorded scenario as YAML.

        Args:
            output_path: Path to save the YAML file
            cleanup_on_success: Remove on_failure artifacts on success
            has_error: Override error flag. True keeps on_failure artifacts.

        Returns:
            Status message with saved file path
        """
        rec = state["recorder"]
        if rec is not None:
            rec.save_yaml(Path(output_path))

        # エラーフラグの判定
        error_occurred = (
            has_error if has_error is not None
            else state.get("has_error", False)
        )

        artifacts: Optional[ArtifactsManager] = state.get("artifacts")

        if artifacts is not None:
            # 動画を保存（ページを閉じる前に path を取得）
            page = session.page
            if page is not None:
                try:
                    await artifacts.save_video(page)
                except Exception:
                    logger.warning("動画保存に失敗しました")

            # トレースを保存
            ctx = session.context
            if ctx is not None:
                try:
                    await artifacts.save_trace(ctx)
                except Exception:
                    logger.warning("トレース保存に失敗しました")

            # 成功時クリーンアップ
            if cleanup_on_success and not error_occurred:
                artifacts.cleanup_on_success()

        await session.close()
        state["recorder"] = None
        state["artifacts"] = None
        state["step_index"] = 0
        state["has_error"] = False

        result = f"Browser closed. Scenario saved to {output_path}"
        if error_occurred:
            result += " (error artifacts preserved)"
        return result

    # -------------------------------------------------------------------
    # 基本操作ツール（別ファイルから登録）
    # -------------------------------------------------------------------
    register_basic_tools(
        mcp, session, state, snapshot_parser, selector_mapper,
    )

    # -------------------------------------------------------------------
    # 高レベルステップツール（別ファイルから登録）
    # -------------------------------------------------------------------
    register_highlevel_tools(
        mcp, session, state, snapshot_parser, selector_mapper,
    )

    return mcp


# ---------------------------------------------------------------------------
# エントリポイント（直接実行用）
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from .config import apply_cli_args, build_cli_parser, load_config_from_env

    parser = build_cli_parser()
    args = parser.parse_args()

    srv_config = load_config_from_env()
    srv_config = apply_cli_args(srv_config, args)

    server = create_server(config=srv_config)
    server.run()
