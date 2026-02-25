"""
MCP サーバー設定 — 環境変数・CLI 引数からの設定読み込み

環境変数または CLI 引数で MCP サーバーの動作を制御する。
CLI 引数 > 環境変数 > デフォルト値 の優先順位で適用される。

環境変数一覧:
  BRT_HEADED        : ブラウザ表示モード（true/false, デフォルト: true）
  BRT_ARTIFACTS_DIR : 成果物ディレクトリ（デフォルト: artifacts）
  BRT_VIDEO_MODE    : 動画録画モード（on_failure/always/none, デフォルト: on_failure）
  BRT_TRACE_MODE    : トレースモード（on_failure/always/none, デフォルト: on_failure）
  BRT_SCREENSHOT_MODE: スクリーンショットモード（before_each_step/none, デフォルト: before_each_step）
  BRT_VIEWPORT_WIDTH : ビューポート幅（デフォルト: 1280）
  BRT_VIEWPORT_HEIGHT: ビューポート高さ（デフォルト: 720）
"""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 環境変数キー定数
# ---------------------------------------------------------------------------

_ENV_HEADED = "BRT_HEADED"
_ENV_ARTIFACTS_DIR = "BRT_ARTIFACTS_DIR"
_ENV_VIDEO_MODE = "BRT_VIDEO_MODE"
_ENV_TRACE_MODE = "BRT_TRACE_MODE"
_ENV_SCREENSHOT_MODE = "BRT_SCREENSHOT_MODE"
_ENV_VIEWPORT_WIDTH = "BRT_VIEWPORT_WIDTH"
_ENV_VIEWPORT_HEIGHT = "BRT_VIEWPORT_HEIGHT"


# ---------------------------------------------------------------------------
# 設定データクラス
# ---------------------------------------------------------------------------

@dataclass
class ServerConfig:
    """MCP サーバーの実行時設定。

    Attributes:
        headed: ブラウザ表示モード（True=表示, False=ヘッドレス）
        artifacts_dir: 成果物ディレクトリパス
        video_mode: 動画録画モード
        trace_mode: トレースモード
        screenshot_mode: スクリーンショットモード
        viewport_width: ビューポート幅
        viewport_height: ビューポート高さ
    """

    headed: bool = True
    artifacts_dir: str = "artifacts"
    video_mode: Literal["on_failure", "always", "none"] = "on_failure"
    trace_mode: Literal["on_failure", "always", "none"] = "on_failure"
    screenshot_mode: Literal["before_each_step", "before_and_after", "none"] = "before_each_step"
    viewport_width: int = 1280
    viewport_height: int = 720


# ---------------------------------------------------------------------------
# 環境変数からの読み込み
# ---------------------------------------------------------------------------

def _parse_bool(value: str) -> bool:
    """文字列を bool に変換する。

    Args:
        value: "true", "1", "yes" → True、それ以外 → False

    Returns:
        変換結果
    """
    return value.lower() in ("true", "1", "yes")


def load_config_from_env() -> ServerConfig:
    """環境変数から ServerConfig を生成する。

    設定されていない環境変数はデフォルト値を使用する。

    Returns:
        環境変数から読み込んだ設定
    """
    config = ServerConfig()

    if _ENV_HEADED in os.environ:
        config.headed = _parse_bool(os.environ[_ENV_HEADED])

    if _ENV_ARTIFACTS_DIR in os.environ:
        config.artifacts_dir = os.environ[_ENV_ARTIFACTS_DIR]

    if _ENV_VIDEO_MODE in os.environ:
        val = os.environ[_ENV_VIDEO_MODE]
        if val in ("on_failure", "always", "none"):
            config.video_mode = val  # type: ignore[assignment]

    if _ENV_TRACE_MODE in os.environ:
        val = os.environ[_ENV_TRACE_MODE]
        if val in ("on_failure", "always", "none"):
            config.trace_mode = val  # type: ignore[assignment]

    if _ENV_SCREENSHOT_MODE in os.environ:
        val = os.environ[_ENV_SCREENSHOT_MODE]
        if val in ("before_each_step", "before_and_after", "none"):
            config.screenshot_mode = val  # type: ignore[assignment]

    if _ENV_VIEWPORT_WIDTH in os.environ:
        try:
            config.viewport_width = int(os.environ[_ENV_VIEWPORT_WIDTH])
        except ValueError:
            logger.warning("BRT_VIEWPORT_WIDTH の値が不正です: %s", os.environ[_ENV_VIEWPORT_WIDTH])

    if _ENV_VIEWPORT_HEIGHT in os.environ:
        try:
            config.viewport_height = int(os.environ[_ENV_VIEWPORT_HEIGHT])
        except ValueError:
            logger.warning("BRT_VIEWPORT_HEIGHT の値が不正です: %s", os.environ[_ENV_VIEWPORT_HEIGHT])

    logger.info("設定を読み込みました: %s", config)
    return config


def build_cli_parser():
    """CLI 引数パーサーを構築する。

    Returns:
        argparse.ArgumentParser インスタンス
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="brt MCP Server - AI browser automation with recording",
    )
    parser.add_argument(
        "--headless", action="store_true", default=None,
        help="Run browser in headless mode (default: headed)",
    )
    parser.add_argument(
        "--headed", action="store_true", default=None,
        help="Run browser in headed mode (default)",
    )
    parser.add_argument(
        "--artifacts-dir", type=str, default=None,
        help="Artifacts output directory (default: artifacts)",
    )
    parser.add_argument(
        "--video", type=str, default=None,
        choices=["on_failure", "always", "none"],
        help="Video recording mode (default: on_failure)",
    )
    parser.add_argument(
        "--trace", type=str, default=None,
        choices=["on_failure", "always", "none"],
        help="Trace recording mode (default: on_failure)",
    )
    parser.add_argument(
        "--screenshot", type=str, default=None,
        choices=["before_each_step", "before_and_after", "none"],
        help="Screenshot mode (default: before_each_step)",
    )
    parser.add_argument(
        "--viewport", type=str, default=None,
        help="Viewport size as WIDTHxHEIGHT (e.g. 1920x1080)",
    )
    return parser


def apply_cli_args(config: ServerConfig, args: Any) -> ServerConfig:
    """CLI 引数を ServerConfig に適用する。

    CLI 引数が指定されている場合のみ上書きする。

    Args:
        config: ベースとなる設定（環境変数から読み込み済み）
        args: argparse の解析結果

    Returns:
        CLI 引数が適用された設定
    """
    # headed / headless
    if getattr(args, "headless", None):
        config.headed = False
    elif getattr(args, "headed", None):
        config.headed = True

    artifacts_dir = getattr(args, "artifacts_dir", None)
    if artifacts_dir is not None:
        config.artifacts_dir = artifacts_dir

    video = getattr(args, "video", None)
    if video is not None:
        config.video_mode = video

    trace = getattr(args, "trace", None)
    if trace is not None:
        config.trace_mode = trace

    screenshot = getattr(args, "screenshot", None)
    if screenshot is not None:
        config.screenshot_mode = screenshot

    viewport_str = getattr(args, "viewport", None)
    if viewport_str is not None:
        try:
            w, h = str(viewport_str).split("x")
            config.viewport_width = int(w)
            config.viewport_height = int(h)
        except (ValueError, AttributeError):
            logger.warning("--viewport の形式が不正です: %s (WIDTHxHEIGHT)", viewport_str)

    return config
