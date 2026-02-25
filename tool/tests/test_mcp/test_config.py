"""
Config テスト — MCP サーバー設定の単体テスト

環境変数・CLI 引数からの設定読み込みを検証する。
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from brt.mcp.config import (
    ServerConfig,
    apply_cli_args,
    build_cli_parser,
    load_config_from_env,
    _parse_bool,
)


# ---------------------------------------------------------------------------
# ServerConfig デフォルト値のテスト
# ---------------------------------------------------------------------------

class TestServerConfigDefaults:
    """ServerConfig のデフォルト値テスト。"""

    def test_default_headed(self):
        """デフォルトで headed=True であること。"""
        config = ServerConfig()
        assert config.headed is True

    def test_default_artifacts_dir(self):
        """デフォルトの artifacts_dir が 'artifacts' であること。"""
        config = ServerConfig()
        assert config.artifacts_dir == "artifacts"

    def test_default_video_mode(self):
        """デフォルトの video_mode が 'on_failure' であること。"""
        config = ServerConfig()
        assert config.video_mode == "on_failure"

    def test_default_trace_mode(self):
        """デフォルトの trace_mode が 'on_failure' であること。"""
        config = ServerConfig()
        assert config.trace_mode == "on_failure"

    def test_default_screenshot_mode(self):
        """デフォルトの screenshot_mode が 'before_each_step' であること。"""
        config = ServerConfig()
        assert config.screenshot_mode == "before_each_step"

    def test_default_viewport(self):
        """デフォルトのビューポートサイズが 1280x720 であること。"""
        config = ServerConfig()
        assert config.viewport_width == 1280
        assert config.viewport_height == 720


# ---------------------------------------------------------------------------
# _parse_bool のテスト
# ---------------------------------------------------------------------------

class TestParseBool:
    """_parse_bool ヘルパーのテスト。"""

    @pytest.mark.parametrize("value", ["true", "True", "TRUE", "1", "yes", "Yes"])
    def test_truthy_values(self, value):
        """真と判定される値。"""
        assert _parse_bool(value) is True

    @pytest.mark.parametrize("value", ["false", "False", "0", "no", "No", ""])
    def test_falsy_values(self, value):
        """偽と判定される値。"""
        assert _parse_bool(value) is False


# ---------------------------------------------------------------------------
# 環境変数からの読み込みテスト
# ---------------------------------------------------------------------------

class TestLoadConfigFromEnv:
    """load_config_from_env() のテスト。"""

    def test_default_without_env(self):
        """環境変数未設定時はデフォルト値が使われること。"""
        with patch.dict(os.environ, {}, clear=True):
            config = load_config_from_env()
        assert config.headed is True
        assert config.video_mode == "on_failure"

    def test_headed_false_from_env(self):
        """BRT_HEADED=false でヘッドレスになること。"""
        with patch.dict(os.environ, {"BRT_HEADED": "false"}):
            config = load_config_from_env()
        assert config.headed is False

    def test_headed_true_from_env(self):
        """BRT_HEADED=true で headed になること。"""
        with patch.dict(os.environ, {"BRT_HEADED": "true"}):
            config = load_config_from_env()
        assert config.headed is True

    def test_artifacts_dir_from_env(self):
        """BRT_ARTIFACTS_DIR で成果物ディレクトリが変わること。"""
        with patch.dict(os.environ, {"BRT_ARTIFACTS_DIR": "output"}):
            config = load_config_from_env()
        assert config.artifacts_dir == "output"

    def test_video_mode_from_env(self):
        """BRT_VIDEO_MODE で動画モードが変わること。"""
        with patch.dict(os.environ, {"BRT_VIDEO_MODE": "always"}):
            config = load_config_from_env()
        assert config.video_mode == "always"

    def test_video_mode_none_from_env(self):
        """BRT_VIDEO_MODE=none で動画無効になること。"""
        with patch.dict(os.environ, {"BRT_VIDEO_MODE": "none"}):
            config = load_config_from_env()
        assert config.video_mode == "none"

    def test_trace_mode_from_env(self):
        """BRT_TRACE_MODE で変更されること。"""
        with patch.dict(os.environ, {"BRT_TRACE_MODE": "always"}):
            config = load_config_from_env()
        assert config.trace_mode == "always"

    def test_screenshot_mode_from_env(self):
        """BRT_SCREENSHOT_MODE で変更されること。"""
        with patch.dict(os.environ, {"BRT_SCREENSHOT_MODE": "none"}):
            config = load_config_from_env()
        assert config.screenshot_mode == "none"

    def test_viewport_from_env(self):
        """BRT_VIEWPORT_WIDTH/HEIGHT で変更されること。"""
        with patch.dict(os.environ, {
            "BRT_VIEWPORT_WIDTH": "1920",
            "BRT_VIEWPORT_HEIGHT": "1080",
        }):
            config = load_config_from_env()
        assert config.viewport_width == 1920
        assert config.viewport_height == 1080

    def test_invalid_viewport_ignored(self):
        """不正なビューポート値はデフォルトが維持されること。"""
        with patch.dict(os.environ, {"BRT_VIEWPORT_WIDTH": "abc"}):
            config = load_config_from_env()
        assert config.viewport_width == 1280

    def test_invalid_video_mode_ignored(self):
        """不正な video_mode はデフォルトが維持されること。"""
        with patch.dict(os.environ, {"BRT_VIDEO_MODE": "invalid"}):
            config = load_config_from_env()
        assert config.video_mode == "on_failure"


# ---------------------------------------------------------------------------
# CLI 引数パーサーのテスト
# ---------------------------------------------------------------------------

class TestCliParser:
    """build_cli_parser() のテスト。"""

    def test_parser_created(self):
        """パーサーが生成できること。"""
        parser = build_cli_parser()
        assert parser is not None

    def test_headless_flag(self):
        """--headless フラグが解析できること。"""
        parser = build_cli_parser()
        args = parser.parse_args(["--headless"])
        assert args.headless is True

    def test_headed_flag(self):
        """--headed フラグが解析できること。"""
        parser = build_cli_parser()
        args = parser.parse_args(["--headed"])
        assert args.headed is True

    def test_video_option(self):
        """--video オプションが解析できること。"""
        parser = build_cli_parser()
        args = parser.parse_args(["--video", "always"])
        assert args.video == "always"

    def test_trace_option(self):
        """--trace オプションが解析できること。"""
        parser = build_cli_parser()
        args = parser.parse_args(["--trace", "none"])
        assert args.trace == "none"

    def test_viewport_option(self):
        """--viewport オプションが解析できること。"""
        parser = build_cli_parser()
        args = parser.parse_args(["--viewport", "1920x1080"])
        assert args.viewport == "1920x1080"

    def test_artifacts_dir_option(self):
        """--artifacts-dir オプションが解析できること。"""
        parser = build_cli_parser()
        args = parser.parse_args(["--artifacts-dir", "output"])
        assert args.artifacts_dir == "output"

    def test_no_args_defaults(self):
        """引数なしでデフォルト値が設定されること。"""
        parser = build_cli_parser()
        args = parser.parse_args([])
        assert args.headless is None
        assert args.headed is None
        assert args.video is None


# ---------------------------------------------------------------------------
# apply_cli_args のテスト
# ---------------------------------------------------------------------------

class TestApplyCliArgs:
    """apply_cli_args() のテスト。"""

    def test_headless_overrides_config(self):
        """--headless が config.headed を False にすること。"""
        config = ServerConfig(headed=True)
        parser = build_cli_parser()
        args = parser.parse_args(["--headless"])
        result = apply_cli_args(config, args)
        assert result.headed is False

    def test_video_overrides_config(self):
        """--video が config.video_mode を上書きすること。"""
        config = ServerConfig(video_mode="on_failure")
        parser = build_cli_parser()
        args = parser.parse_args(["--video", "always"])
        result = apply_cli_args(config, args)
        assert result.video_mode == "always"

    def test_viewport_overrides_config(self):
        """--viewport が config のビューポートを上書きすること。"""
        config = ServerConfig()
        parser = build_cli_parser()
        args = parser.parse_args(["--viewport", "1920x1080"])
        result = apply_cli_args(config, args)
        assert result.viewport_width == 1920
        assert result.viewport_height == 1080

    def test_no_args_preserves_config(self):
        """引数なしで config が変更されないこと。"""
        config = ServerConfig(
            headed=False,
            video_mode="always",
            viewport_width=1920,
        )
        parser = build_cli_parser()
        args = parser.parse_args([])
        result = apply_cli_args(config, args)
        assert result.headed is False
        assert result.video_mode == "always"
        assert result.viewport_width == 1920

    def test_invalid_viewport_format(self):
        """不正な viewport 形式でもエラーにならないこと。"""
        config = ServerConfig()
        parser = build_cli_parser()
        args = parser.parse_args(["--viewport", "invalid"])
        result = apply_cli_args(config, args)
        # デフォルト値が維持される
        assert result.viewport_width == 1280
        assert result.viewport_height == 720


# ---------------------------------------------------------------------------
# CLI > 環境変数 > デフォルト の優先順位テスト
# ---------------------------------------------------------------------------

class TestConfigPrecedence:
    """設定の優先順位テスト。"""

    def test_cli_overrides_env(self):
        """CLI 引数が環境変数より優先されること。"""
        with patch.dict(os.environ, {"BRT_VIDEO_MODE": "none"}):
            config = load_config_from_env()
        assert config.video_mode == "none"

        parser = build_cli_parser()
        args = parser.parse_args(["--video", "always"])
        result = apply_cli_args(config, args)
        assert result.video_mode == "always"

    def test_env_overrides_default(self):
        """環境変数がデフォルト値より優先されること。"""
        with patch.dict(os.environ, {"BRT_HEADED": "false"}):
            config = load_config_from_env()
        assert config.headed is False
