"""
ArtifactsManager — テスト実行成果物の管理

テスト実行時に生成される成果物（スクリーンショット、トレース、動画、ログ等）の
保存・管理・クリーンアップを担当する。

主な機能:
  - create_run_dir(): 実行ディレクトリの作成
  - save_screenshot(): ステップ前後のスクリーンショット保存
  - save_trace(): Playwright トレースの保存
  - save_video(): 動画の保存
  - save_flow_copy(): YAML DSL コピーの保存
  - save_env_info(): 環境情報（秘密値マスク済み）の保存
  - cleanup_on_success(): 成功時の on_failure 成果物削除
  - mask_secrets(): 秘密値のマスク処理

要件 8.1: 成果物ディレクトリ構造の自動生成
要件 8.2: スクリーンショットの自動保存（JPEG/PNG）
要件 8.3: トレース・動画の保存と成功時クリーンアップ
要件 8.4: secret: true フラグ付き値のマスク処理
"""

from __future__ import annotations

import json
import logging
import platform
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ruamel.yaml import YAML

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext, Page

    from ..dsl.schema import ArtifactsConfig, Scenario

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ステップ名サニタイズ用パターン
# ---------------------------------------------------------------------------

_UNSAFE_CHARS = re.compile(r"[^\w\-]")
"""ファイル名に使用できない文字を検出する正規表現。"""


# ---------------------------------------------------------------------------
# ArtifactsManager 本体
# ---------------------------------------------------------------------------

@dataclass
class ArtifactsManager:
    """テスト実行成果物の管理クラス。

    実行ディレクトリの作成、スクリーンショット・トレース・動画の保存、
    YAML DSL コピーの保存、環境情報の保存、成功時のクリーンアップを担当する。

    Attributes:
        config: アーティファクト設定（ScreenshotConfig, TraceConfig, VideoConfig）
        base_dir: 成果物ベースディレクトリ（デフォルト: artifacts/）
        run_dir: 実行ディレクトリ（create_run_dir() で設定される）
    """

    config: ArtifactsConfig
    base_dir: Path = field(default_factory=lambda: Path("artifacts"))
    run_dir: Path | None = field(default=None, init=False)

    # ----- ディレクトリ作成 -----

    def create_run_dir(self, timestamp: datetime | None = None) -> Path:
        """実行ディレクトリを作成する。

        artifacts/run-YYYYMMDD-HHMMSS/ 形式のディレクトリを作成し、
        screenshots/, trace/, video/, logs/ サブディレクトリも同時に作成する。

        Args:
            timestamp: ディレクトリ名に使用するタイムスタンプ。
                       None の場合は現在時刻を使用。

        Returns:
            作成された実行ディレクトリのパス
        """
        if timestamp is None:
            timestamp = datetime.now()

        dir_name = f"run-{timestamp.strftime('%Y%m%d-%H%M%S')}"
        self.run_dir = self.base_dir / dir_name

        # メインディレクトリとサブディレクトリを作成
        subdirs = ["screenshots", "trace", "video", "logs"]
        for subdir in subdirs:
            (self.run_dir / subdir).mkdir(parents=True, exist_ok=True)

        logger.info("実行ディレクトリを作成しました: %s", self.run_dir)
        return self.run_dir

    # ----- スクリーンショット保存 -----

    async def save_screenshot(
        self,
        page: Page,
        step_index: int,
        step_name: str,
    ) -> Path | None:
        """ステップ前のスクリーンショットを保存する。

        ファイル名は NNNN_before-<step-name>.jpg 形式。
        step_index は4桁ゼロ埋め、step_name はサニタイズされる。

        Args:
            page: Playwright の Page オブジェクト
            step_index: ステップインデックス（0始まり）
            step_name: ステップ名

        Returns:
            保存されたスクリーンショットのパス。mode が "none" の場合は None。
        """
        # mode が "none" の場合はスキップ
        if self.config.screenshots.mode == "none":
            logger.debug("スクリーンショットモードが none のためスキップ")
            return None

        if self.run_dir is None:
            raise RuntimeError("run_dir が未設定です。create_run_dir() を先に呼び出してください。")

        # ファイル名を生成
        sanitized_name = _sanitize_step_name(step_name)
        ext = self.config.screenshots.format  # "jpeg" or "png"
        # JPEG の場合は拡張子を .jpg にする
        file_ext = "jpg" if ext == "jpeg" else ext
        filename = f"{step_index:04d}_before-{sanitized_name}.{file_ext}"
        filepath = self.run_dir / "screenshots" / filename

        # スクリーンショットを保存
        screenshot_options: dict[str, Any] = {"path": str(filepath)}
        if ext == "jpeg":
            screenshot_options["type"] = "jpeg"
            screenshot_options["quality"] = self.config.screenshots.quality
        else:
            screenshot_options["type"] = "png"

        await page.screenshot(**screenshot_options)
        logger.info("スクリーンショットを保存しました: %s", filepath)
        return filepath

    # ----- トレース保存 -----

    async def save_trace(self, context: BrowserContext) -> Path | None:
        """Playwright トレースを保存する。

        trace/trace.zip に保存する。

        Args:
            context: Playwright の BrowserContext オブジェクト

        Returns:
            保存されたトレースファイルのパス。mode が "none" の場合は None。
        """
        if self.config.trace.mode == "none":
            logger.debug("トレースモードが none のためスキップ")
            return None

        if self.run_dir is None:
            raise RuntimeError("run_dir が未設定です。create_run_dir() を先に呼び出してください。")

        trace_path = self.run_dir / "trace" / "trace.zip"
        await context.tracing.stop(path=str(trace_path))
        logger.info("トレースを保存しました: %s", trace_path)
        return trace_path

    # ----- 動画保存 -----

    async def save_video(self, page: Page) -> Path | None:
        """動画を video/ ディレクトリに保存する。

        Playwright の page.video を使用して動画ファイルを取得し、
        video/ ディレクトリにコピーする。

        Args:
            page: Playwright の Page オブジェクト

        Returns:
            保存された動画ファイルのパス。mode が "none" の場合は None。
        """
        if self.config.video.mode == "none":
            logger.debug("動画モードが none のためスキップ")
            return None

        if self.run_dir is None:
            raise RuntimeError("run_dir が未設定です。create_run_dir() を先に呼び出してください。")

        video = page.video
        if video is None:
            logger.warning("動画が記録されていません")
            return None

        # Playwright が生成した動画ファイルのパスを取得
        source_path = await video.path()
        if source_path is None:
            logger.warning("動画ファイルのパスを取得できません")
            return None

        # video/ ディレクトリにコピー
        source = Path(source_path)
        dest = self.run_dir / "video" / source.name
        shutil.copy2(str(source), str(dest))
        logger.info("動画を保存しました: %s", dest)
        return dest

    # ----- YAML DSL コピー保存 -----

    def save_flow_copy(self, scenario: Scenario) -> Path:
        """実行に使用した YAML DSL のコピーを flow.yaml に保存する。

        ruamel.yaml を使用して Scenario モデルを YAML 形式で書き出す。

        Args:
            scenario: 保存対象の Scenario オブジェクト

        Returns:
            保存された flow.yaml のパス
        """
        if self.run_dir is None:
            raise RuntimeError("run_dir が未設定です。create_run_dir() を先に呼び出してください。")

        flow_path = self.run_dir / "flow.yaml"
        yaml = YAML()
        yaml.default_flow_style = False

        # Pydantic モデルを辞書に変換して YAML 出力
        data = scenario.model_dump(mode="python")
        with open(flow_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f)

        logger.info("YAML DSL コピーを保存しました: %s", flow_path)
        return flow_path

    # ----- 環境情報保存 -----

    def save_env_info(self, scenario: Scenario) -> Path:
        """環境情報を env.json に保存する。

        秘密値（secret: true のステップの value）はマスクされる。

        Args:
            scenario: 環境情報の取得元 Scenario オブジェクト

        Returns:
            保存された env.json のパス
        """
        if self.run_dir is None:
            raise RuntimeError("run_dir が未設定です。create_run_dir() を先に呼び出してください。")

        # 秘密値を収集
        secret_values = _collect_secret_values(scenario)

        # vars のマスク処理
        masked_vars = {}
        for key, value in scenario.vars.items():
            if value in secret_values:
                masked_vars[key] = "***"
            else:
                masked_vars[key] = value

        env_info = {
            "title": scenario.title,
            "baseUrl": scenario.baseUrl,
            "vars": masked_vars,
            "healing": scenario.healing,
            "python_version": sys.version,
            "platform": platform.platform(),
            "timestamp": datetime.now().isoformat(),
        }

        env_path = self.run_dir / "env.json"
        with open(env_path, "w", encoding="utf-8") as f:
            json.dump(env_info, f, ensure_ascii=False, indent=2)

        logger.info("環境情報を保存しました: %s", env_path)
        return env_path

    # ----- 成功時クリーンアップ -----

    def cleanup_on_success(self) -> None:
        """成功時に on_failure 成果物（動画、トレース）を削除する。

        trace.mode が "on_failure" の場合、trace/ ディレクトリを削除する。
        video.mode が "on_failure" の場合、video/ ディレクトリを削除する。
        "always" モードの場合は削除しない。
        """
        if self.run_dir is None:
            logger.warning("run_dir が未設定のためクリーンアップをスキップ")
            return

        # トレースのクリーンアップ
        if self.config.trace.mode == "on_failure":
            trace_dir = self.run_dir / "trace"
            if trace_dir.exists():
                shutil.rmtree(trace_dir)
                logger.info("成功時クリーンアップ: trace/ を削除しました")

        # 動画のクリーンアップ
        if self.config.video.mode == "on_failure":
            video_dir = self.run_dir / "video"
            if video_dir.exists():
                shutil.rmtree(video_dir)
                logger.info("成功時クリーンアップ: video/ を削除しました")


# ---------------------------------------------------------------------------
# 秘密値マスク処理
# ---------------------------------------------------------------------------

def mask_secrets(scenario: Scenario, text: str) -> str:
    """テキスト中の秘密値を *** にマスクする。

    Scenario の steps を走査し、fill ステップで secret: true のものの
    value フィールドの値をテキスト中から検出して *** に置換する。

    Args:
        scenario: 秘密値の検出元 Scenario オブジェクト
        text: マスク対象のテキスト

    Returns:
        秘密値がマスクされたテキスト
    """
    secret_values = _collect_secret_values(scenario)

    result = text
    for secret_val in secret_values:
        if secret_val:  # 空文字列はスキップ
            result = result.replace(secret_val, "***")

    return result


# ---------------------------------------------------------------------------
# ヘルパー関数
# ---------------------------------------------------------------------------

def _collect_secret_values(scenario: Scenario) -> set[str]:
    """Scenario から秘密値（secret: true の fill ステップの value）を収集する。

    Args:
        scenario: 走査対象の Scenario オブジェクト

    Returns:
        秘密値の集合
    """
    secret_values: set[str] = set()

    for step in scenario.steps:
        if not isinstance(step, dict):
            continue
        # fill ステップの検出
        fill_data = step.get("fill")
        if fill_data is None:
            continue
        if not isinstance(fill_data, dict):
            continue
        # secret: true の場合に value を収集
        if fill_data.get("secret", False):
            value = fill_data.get("value", "")
            if value:
                secret_values.add(value)

    return secret_values


def _sanitize_step_name(name: str) -> str:
    """ステップ名をファイル名に安全な文字列に変換する。

    英数字、ハイフン、アンダースコア以外の文字をハイフンに置換し、
    連続するハイフンを1つにまとめる。

    Args:
        name: サニタイズ対象のステップ名

    Returns:
        サニタイズ済みのステップ名
    """
    sanitized = _UNSAFE_CHARS.sub("-", name)
    # 連続するハイフンを1つにまとめる
    sanitized = re.sub(r"-+", "-", sanitized)
    # 先頭・末尾のハイフンを除去
    return sanitized.strip("-")
