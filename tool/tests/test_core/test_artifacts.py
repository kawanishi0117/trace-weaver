"""
ArtifactsManager のユニットテスト

Playwright の Page, BrowserContext はモック（unittest.mock.AsyncMock）を使用する。
Scenario は実際の Pydantic モデルを使用する。

テスト対象:
  - create_run_dir(): ディレクトリ作成、命名規則、サブディレクトリ
  - save_screenshot(): ファイル名形式、ゼロ埋め、サニタイズ、mode=none スキップ
  - save_flow_copy(): YAML 保存、ラウンドトリップ等価性
  - save_env_info(): JSON 保存、秘密値マスク
  - cleanup_on_success(): on_failure 成果物削除、always モード保持
  - mask_secrets(): 秘密値マスク処理
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest
from ruamel.yaml import YAML

from brt.core.artifacts import ArtifactsManager, _sanitize_step_name, mask_secrets
from brt.dsl.schema import (
    ArtifactsConfig,
    HooksConfig,
    Scenario,
    ScreenshotConfig,
    TraceConfig,
    VideoConfig,
)


# ---------------------------------------------------------------------------
# ヘルパー: テスト用 Scenario 生成
# ---------------------------------------------------------------------------

def _make_scenario(**overrides) -> Scenario:
    """テスト用の Scenario を生成する。"""
    defaults = {
        "title": "テストシナリオ",
        "baseUrl": "http://localhost:4200",
        "vars": {"email": "test@example.com", "password": "secret123"},
        "artifacts": ArtifactsConfig(
            screenshots=ScreenshotConfig(mode="before_each_step", format="jpeg", quality=70),
            trace=TraceConfig(mode="on_failure"),
            video=VideoConfig(mode="on_failure"),
        ),
        "hooks": HooksConfig(),
        "steps": [
            {"goto": "http://localhost:4200/login"},
            {
                "fill": {
                    "by": {"css": "#email"},
                    "value": "test@example.com",
                    "name": "fill-email",
                }
            },
            {
                "fill": {
                    "by": {"css": "#password"},
                    "value": "secret123",
                    "name": "fill-password",
                    "secret": True,
                }
            },
            {
                "click": {
                    "by": {"role": "button", "name": "ログイン"},
                    "name": "click-login",
                }
            },
        ],
        "healing": "off",
    }
    defaults.update(overrides)
    return Scenario(**defaults)


def _make_artifacts_config(**overrides) -> ArtifactsConfig:
    """テスト用の ArtifactsConfig を生成する。"""
    defaults = {
        "screenshots": ScreenshotConfig(mode="before_each_step", format="jpeg", quality=70),
        "trace": TraceConfig(mode="on_failure"),
        "video": VideoConfig(mode="on_failure"),
    }
    defaults.update(overrides)
    return ArtifactsConfig(**defaults)


def _make_mock_page() -> AsyncMock:
    """モック Page を生成する。"""
    page = AsyncMock()
    page.screenshot = AsyncMock()
    # video プロパティのモック
    video = AsyncMock()
    video.path = AsyncMock(return_value="/tmp/video.webm")
    page.video = video
    return page


def _make_mock_context() -> AsyncMock:
    """モック BrowserContext を生成する。"""
    context = AsyncMock()
    context.tracing = AsyncMock()
    context.tracing.stop = AsyncMock()
    return context


# ===========================================================================
# テスト: ArtifactsManager 初期化・ディレクトリ作成
# ===========================================================================

class TestArtifactsManagerInit:
    """ArtifactsManager の初期化とディレクトリ作成テスト。"""

    def test_create_run_dir_creates_directory(self, tmp_path: Path) -> None:
        """create_run_dir でディレクトリが作成されること。"""
        config = _make_artifacts_config()
        manager = ArtifactsManager(config=config, base_dir=tmp_path)

        run_dir = manager.create_run_dir()

        assert run_dir.exists()
        assert run_dir.is_dir()

    def test_run_dir_name_format(self, tmp_path: Path) -> None:
        """ディレクトリ名が run-YYYYMMDD-HHMMSS 形式であること。"""
        config = _make_artifacts_config()
        manager = ArtifactsManager(config=config, base_dir=tmp_path)
        ts = datetime(2024, 3, 15, 10, 30, 45)

        run_dir = manager.create_run_dir(timestamp=ts)

        assert run_dir.name == "run-20240315-103045"

    def test_subdirectories_created(self, tmp_path: Path) -> None:
        """screenshots/, trace/, video/, logs/ サブディレクトリが作成されること。"""
        config = _make_artifacts_config()
        manager = ArtifactsManager(config=config, base_dir=tmp_path)

        run_dir = manager.create_run_dir()

        assert (run_dir / "screenshots").exists()
        assert (run_dir / "trace").exists()
        assert (run_dir / "video").exists()
        assert (run_dir / "logs").exists()

    def test_run_dir_stored_on_instance(self, tmp_path: Path) -> None:
        """create_run_dir 後に run_dir がインスタンスに保存されること。"""
        config = _make_artifacts_config()
        manager = ArtifactsManager(config=config, base_dir=tmp_path)

        assert manager.run_dir is None
        run_dir = manager.create_run_dir()
        assert manager.run_dir == run_dir

    def test_create_run_dir_with_custom_timestamp(self, tmp_path: Path) -> None:
        """カスタムタイムスタンプでディレクトリが作成されること。"""
        config = _make_artifacts_config()
        manager = ArtifactsManager(config=config, base_dir=tmp_path)
        ts = datetime(2025, 12, 31, 23, 59, 59)

        run_dir = manager.create_run_dir(timestamp=ts)

        assert run_dir.name == "run-20251231-235959"


# ===========================================================================
# テスト: スクリーンショット保存
# ===========================================================================

class TestSaveScreenshot:
    """save_screenshot のテスト。"""

    async def test_filename_format(self, tmp_path: Path) -> None:
        """ファイル名が NNNN_before-<step-name>.jpg 形式であること。"""
        config = _make_artifacts_config()
        manager = ArtifactsManager(config=config, base_dir=tmp_path)
        manager.create_run_dir()
        page = _make_mock_page()

        result = await manager.save_screenshot(page, 1, "fill-email")

        assert result is not None
        assert result.name == "0001_before-fill-email.jpg"

    async def test_step_index_zero_padded(self, tmp_path: Path) -> None:
        """step_index が4桁ゼロ埋めであること。"""
        config = _make_artifacts_config()
        manager = ArtifactsManager(config=config, base_dir=tmp_path)
        manager.create_run_dir()
        page = _make_mock_page()

        result = await manager.save_screenshot(page, 42, "click-button")

        assert result is not None
        assert result.name.startswith("0042_")

    async def test_step_name_sanitized(self, tmp_path: Path) -> None:
        """ステップ名の特殊文字がサニタイズされること。"""
        config = _make_artifacts_config()
        manager = ArtifactsManager(config=config, base_dir=tmp_path)
        manager.create_run_dir()
        page = _make_mock_page()

        result = await manager.save_screenshot(page, 1, "fill email/password")

        assert result is not None
        # 特殊文字がハイフンに置換されていること
        assert "/" not in result.name
        assert " " not in result.name

    async def test_mode_none_skips(self, tmp_path: Path) -> None:
        """mode が "none" の場合はスキップされること。"""
        config = _make_artifacts_config(
            screenshots=ScreenshotConfig(mode="none"),
        )
        manager = ArtifactsManager(config=config, base_dir=tmp_path)
        manager.create_run_dir()
        page = _make_mock_page()

        result = await manager.save_screenshot(page, 1, "fill-email")

        assert result is None
        page.screenshot.assert_not_called()

    async def test_screenshot_saved_in_screenshots_dir(self, tmp_path: Path) -> None:
        """スクリーンショットが screenshots/ ディレクトリに保存されること。"""
        config = _make_artifacts_config()
        manager = ArtifactsManager(config=config, base_dir=tmp_path)
        manager.create_run_dir()
        page = _make_mock_page()

        result = await manager.save_screenshot(page, 1, "fill-email")

        assert result is not None
        assert result.parent.name == "screenshots"

    async def test_page_screenshot_called_with_jpeg_options(self, tmp_path: Path) -> None:
        """JPEG モードで page.screenshot が正しいオプションで呼ばれること。"""
        config = _make_artifacts_config(
            screenshots=ScreenshotConfig(mode="before_each_step", format="jpeg", quality=80),
        )
        manager = ArtifactsManager(config=config, base_dir=tmp_path)
        manager.create_run_dir()
        page = _make_mock_page()

        await manager.save_screenshot(page, 1, "test-step")

        page.screenshot.assert_called_once()
        call_kwargs = page.screenshot.call_args[1]
        assert call_kwargs["type"] == "jpeg"
        assert call_kwargs["quality"] == 80

    async def test_png_format(self, tmp_path: Path) -> None:
        """PNG フォーマットでスクリーンショットが保存されること。"""
        config = _make_artifacts_config(
            screenshots=ScreenshotConfig(mode="before_each_step", format="png"),
        )
        manager = ArtifactsManager(config=config, base_dir=tmp_path)
        manager.create_run_dir()
        page = _make_mock_page()

        result = await manager.save_screenshot(page, 1, "test-step")

        assert result is not None
        assert result.name.endswith(".png")
        call_kwargs = page.screenshot.call_args[1]
        assert call_kwargs["type"] == "png"


# ===========================================================================
# テスト: YAML DSL コピー保存
# ===========================================================================

class TestSaveFlowCopy:
    """save_flow_copy のテスト。"""

    def test_flow_yaml_saved(self, tmp_path: Path) -> None:
        """flow.yaml が保存されること。"""
        config = _make_artifacts_config()
        manager = ArtifactsManager(config=config, base_dir=tmp_path)
        manager.create_run_dir()
        scenario = _make_scenario()

        result = manager.save_flow_copy(scenario)

        assert result.exists()
        assert result.name == "flow.yaml"

    def test_flow_yaml_roundtrip(self, tmp_path: Path) -> None:
        """パースした結果が元の Scenario と等価であること。"""
        config = _make_artifacts_config()
        manager = ArtifactsManager(config=config, base_dir=tmp_path)
        manager.create_run_dir()
        scenario = _make_scenario()

        flow_path = manager.save_flow_copy(scenario)

        # 保存された YAML を読み込んで比較
        yaml = YAML()
        with open(flow_path, "r", encoding="utf-8") as f:
            loaded_data = yaml.load(f)

        # 元の Scenario と比較
        original_data = scenario.model_dump(mode="python")
        assert loaded_data["title"] == original_data["title"]
        assert loaded_data["baseUrl"] == original_data["baseUrl"]
        assert loaded_data["vars"] == original_data["vars"]
        assert loaded_data["healing"] == original_data["healing"]

    def test_flow_yaml_in_run_dir(self, tmp_path: Path) -> None:
        """flow.yaml が run_dir 直下に保存されること。"""
        config = _make_artifacts_config()
        manager = ArtifactsManager(config=config, base_dir=tmp_path)
        run_dir = manager.create_run_dir()
        scenario = _make_scenario()

        result = manager.save_flow_copy(scenario)

        assert result.parent == run_dir


# ===========================================================================
# テスト: 環境情報保存
# ===========================================================================

class TestSaveEnvInfo:
    """save_env_info のテスト。"""

    def test_env_json_saved(self, tmp_path: Path) -> None:
        """env.json が保存されること。"""
        config = _make_artifacts_config()
        manager = ArtifactsManager(config=config, base_dir=tmp_path)
        manager.create_run_dir()
        scenario = _make_scenario()

        result = manager.save_env_info(scenario)

        assert result.exists()
        assert result.name == "env.json"

    def test_secret_values_masked(self, tmp_path: Path) -> None:
        """secret 値がマスクされていること。"""
        config = _make_artifacts_config()
        manager = ArtifactsManager(config=config, base_dir=tmp_path)
        manager.create_run_dir()
        # password が secret: true の fill ステップの value と一致
        scenario = _make_scenario(
            vars={"email": "test@example.com", "password": "secret123"},
        )

        result = manager.save_env_info(scenario)

        with open(result, "r", encoding="utf-8") as f:
            env_data = json.load(f)

        # secret123 は secret: true の fill ステップの value なのでマスクされる
        assert env_data["vars"]["password"] == "***"

    def test_non_secret_values_preserved(self, tmp_path: Path) -> None:
        """非 secret 値はそのまま保存されること。"""
        config = _make_artifacts_config()
        manager = ArtifactsManager(config=config, base_dir=tmp_path)
        manager.create_run_dir()
        scenario = _make_scenario()

        result = manager.save_env_info(scenario)

        with open(result, "r", encoding="utf-8") as f:
            env_data = json.load(f)

        # email は secret ではないのでそのまま
        assert env_data["vars"]["email"] == "test@example.com"

    def test_env_json_contains_metadata(self, tmp_path: Path) -> None:
        """env.json にメタデータ（title, baseUrl 等）が含まれること。"""
        config = _make_artifacts_config()
        manager = ArtifactsManager(config=config, base_dir=tmp_path)
        manager.create_run_dir()
        scenario = _make_scenario()

        result = manager.save_env_info(scenario)

        with open(result, "r", encoding="utf-8") as f:
            env_data = json.load(f)

        assert env_data["title"] == "テストシナリオ"
        assert env_data["baseUrl"] == "http://localhost:4200"
        assert "python_version" in env_data
        assert "platform" in env_data
        assert "timestamp" in env_data


# ===========================================================================
# テスト: 成功時クリーンアップ
# ===========================================================================

class TestCleanupOnSuccess:
    """cleanup_on_success のテスト。"""

    def test_on_failure_trace_deleted(self, tmp_path: Path) -> None:
        """trace モードが on_failure の場合、成功時にトレースが削除されること。"""
        config = _make_artifacts_config(
            trace=TraceConfig(mode="on_failure"),
        )
        manager = ArtifactsManager(config=config, base_dir=tmp_path)
        manager.create_run_dir()

        # trace ディレクトリにダミーファイルを作成
        trace_dir = manager.run_dir / "trace"
        (trace_dir / "trace.zip").write_bytes(b"dummy")

        manager.cleanup_on_success()

        assert not trace_dir.exists()

    def test_on_failure_video_deleted(self, tmp_path: Path) -> None:
        """video モードが on_failure の場合、成功時に動画が削除されること。"""
        config = _make_artifacts_config(
            video=VideoConfig(mode="on_failure"),
        )
        manager = ArtifactsManager(config=config, base_dir=tmp_path)
        manager.create_run_dir()

        # video ディレクトリにダミーファイルを作成
        video_dir = manager.run_dir / "video"
        (video_dir / "test.webm").write_bytes(b"dummy")

        manager.cleanup_on_success()

        assert not video_dir.exists()

    def test_always_mode_trace_not_deleted(self, tmp_path: Path) -> None:
        """trace モードが always の場合、成功時にトレースが削除されないこと。"""
        config = _make_artifacts_config(
            trace=TraceConfig(mode="always"),
        )
        manager = ArtifactsManager(config=config, base_dir=tmp_path)
        manager.create_run_dir()

        # trace ディレクトリにダミーファイルを作成
        trace_dir = manager.run_dir / "trace"
        (trace_dir / "trace.zip").write_bytes(b"dummy")

        manager.cleanup_on_success()

        assert trace_dir.exists()
        assert (trace_dir / "trace.zip").exists()

    def test_always_mode_video_not_deleted(self, tmp_path: Path) -> None:
        """video モードが always の場合、成功時に動画が削除されないこと。"""
        config = _make_artifacts_config(
            video=VideoConfig(mode="always"),
        )
        manager = ArtifactsManager(config=config, base_dir=tmp_path)
        manager.create_run_dir()

        # video ディレクトリにダミーファイルを作成
        video_dir = manager.run_dir / "video"
        (video_dir / "test.webm").write_bytes(b"dummy")

        manager.cleanup_on_success()

        assert video_dir.exists()
        assert (video_dir / "test.webm").exists()

    def test_none_mode_no_cleanup(self, tmp_path: Path) -> None:
        """mode が none の場合、クリーンアップが行われないこと。"""
        config = _make_artifacts_config(
            trace=TraceConfig(mode="none"),
            video=VideoConfig(mode="none"),
        )
        manager = ArtifactsManager(config=config, base_dir=tmp_path)
        manager.create_run_dir()

        # ディレクトリは存在するが中身は空
        manager.cleanup_on_success()

        # trace/ と video/ ディレクトリは残っている（空のまま）
        assert (manager.run_dir / "trace").exists()
        assert (manager.run_dir / "video").exists()


# ===========================================================================
# テスト: 秘密値マスク処理
# ===========================================================================

class TestMaskSecrets:
    """mask_secrets のテスト。"""

    def test_secret_fill_value_masked(self) -> None:
        """secret: true の fill ステップの値がマスクされること。"""
        scenario = _make_scenario()

        result = mask_secrets(scenario, "パスワードは secret123 です")

        assert "secret123" not in result
        assert "***" in result

    def test_non_secret_fill_value_not_masked(self) -> None:
        """secret: false の fill ステップの値はマスクされないこと。"""
        scenario = _make_scenario()

        result = mask_secrets(scenario, "メールは test@example.com です")

        # email の fill ステップは secret: false なのでマスクされない
        assert "test@example.com" in result

    def test_multiple_secrets_all_masked(self) -> None:
        """複数の secret 値が全てマスクされること。"""
        scenario = _make_scenario(
            steps=[
                {
                    "fill": {
                        "by": {"css": "#password"},
                        "value": "pass1",
                        "name": "fill-pass1",
                        "secret": True,
                    }
                },
                {
                    "fill": {
                        "by": {"css": "#token"},
                        "value": "token-abc",
                        "name": "fill-token",
                        "secret": True,
                    }
                },
            ],
        )

        result = mask_secrets(scenario, "pass1 と token-abc を使用")

        assert "pass1" not in result
        assert "token-abc" not in result
        assert result.count("***") == 2

    def test_text_without_secrets_unchanged(self) -> None:
        """秘密値を含まないテキストは変更されないこと。"""
        scenario = _make_scenario()

        original = "これは通常のテキストです"
        result = mask_secrets(scenario, original)

        assert result == original

    def test_secret_value_in_middle_of_text(self) -> None:
        """テキスト中の秘密値が全て *** に置換されること。"""
        scenario = _make_scenario()

        result = mask_secrets(scenario, "値=secret123, 再度=secret123")

        assert "secret123" not in result
        # 2箇所とも置換される
        assert result == "値=***, 再度=***"


# ===========================================================================
# テスト: ステップ名サニタイズ
# ===========================================================================

class TestSanitizeStepName:
    """_sanitize_step_name のテスト。"""

    def test_basic_name(self) -> None:
        """基本的なステップ名がそのまま返されること。"""
        assert _sanitize_step_name("fill-email") == "fill-email"

    def test_special_chars_replaced(self) -> None:
        """特殊文字がハイフンに置換されること。"""
        result = _sanitize_step_name("fill email/password")
        assert " " not in result
        assert "/" not in result

    def test_consecutive_hyphens_collapsed(self) -> None:
        """連続するハイフンが1つにまとめられること。"""
        result = _sanitize_step_name("fill---email")
        assert "---" not in result

    def test_leading_trailing_hyphens_stripped(self) -> None:
        """先頭・末尾のハイフンが除去されること。"""
        result = _sanitize_step_name("-fill-email-")
        assert not result.startswith("-")
        assert not result.endswith("-")


# ===========================================================================
# テスト: トレース保存
# ===========================================================================

class TestSaveTrace:
    """save_trace のテスト。"""

    async def test_trace_saved(self, tmp_path: Path) -> None:
        """トレースが trace/trace.zip に保存されること。"""
        config = _make_artifacts_config(
            trace=TraceConfig(mode="always"),
        )
        manager = ArtifactsManager(config=config, base_dir=tmp_path)
        manager.create_run_dir()
        context = _make_mock_context()

        result = await manager.save_trace(context)

        assert result is not None
        assert result.name == "trace.zip"
        assert result.parent.name == "trace"
        context.tracing.stop.assert_called_once()

    async def test_trace_mode_none_skips(self, tmp_path: Path) -> None:
        """trace モードが none の場合はスキップされること。"""
        config = _make_artifacts_config(
            trace=TraceConfig(mode="none"),
        )
        manager = ArtifactsManager(config=config, base_dir=tmp_path)
        manager.create_run_dir()
        context = _make_mock_context()

        result = await manager.save_trace(context)

        assert result is None
        context.tracing.stop.assert_not_called()
