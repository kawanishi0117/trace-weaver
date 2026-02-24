"""
Scenario 関連モデルのユニットテスト

ScreenshotConfig, TraceConfig, VideoConfig, ArtifactsConfig,
HooksConfig, Section, Scenario モデルの動作を検証する。

要件 3.1: title, baseUrl, vars, artifacts, hooks, steps, healing
要件 3.2: ${env.X}, ${vars.X} の変数展開構文バリデーション
要件 3.3: secret: true フラグ
要件 3.4: artifacts 設定
要件 3.5: hooks 設定
要件 3.6: section によるステップのグループ化
"""

import pytest
from pydantic import ValidationError

from src.dsl.schema import (
    ArtifactsConfig,
    HooksConfig,
    Scenario,
    ScreenshotConfig,
    Section,
    TraceConfig,
    VideoConfig,
)


# ---------------------------------------------------------------------------
# ScreenshotConfig テスト
# ---------------------------------------------------------------------------

class TestScreenshotConfig:
    """ScreenshotConfig モデルのテスト。"""

    def test_default_values(self):
        """デフォルト値が正しく設定されること。"""
        config = ScreenshotConfig()
        assert config.mode == "before_each_step"
        assert config.format == "jpeg"
        assert config.quality == 70

    def test_custom_values(self):
        """カスタム値が正しく設定されること。"""
        config = ScreenshotConfig(mode="before_and_after", format="png", quality=90)
        assert config.mode == "before_and_after"
        assert config.format == "png"
        assert config.quality == 90

    def test_none_mode(self):
        """mode: none が設定可能であること。"""
        config = ScreenshotConfig(mode="none")
        assert config.mode == "none"

    def test_invalid_mode_rejected(self):
        """不正な mode 値が拒否されること。"""
        with pytest.raises(ValidationError):
            ScreenshotConfig(mode="invalid")

    def test_quality_min_boundary(self):
        """quality の最小値（1）が受け入れられること。"""
        config = ScreenshotConfig(quality=1)
        assert config.quality == 1

    def test_quality_max_boundary(self):
        """quality の最大値（100）が受け入れられること。"""
        config = ScreenshotConfig(quality=100)
        assert config.quality == 100

    def test_quality_below_min_rejected(self):
        """quality が 0 以下の場合に拒否されること。"""
        with pytest.raises(ValidationError):
            ScreenshotConfig(quality=0)

    def test_quality_above_max_rejected(self):
        """quality が 100 超の場合に拒否されること。"""
        with pytest.raises(ValidationError):
            ScreenshotConfig(quality=101)


# ---------------------------------------------------------------------------
# TraceConfig テスト
# ---------------------------------------------------------------------------

class TestTraceConfig:
    """TraceConfig モデルのテスト。"""

    def test_default_mode(self):
        """デフォルトで on_failure モードであること。"""
        config = TraceConfig()
        assert config.mode == "on_failure"

    def test_always_mode(self):
        """always モードが設定可能であること。"""
        config = TraceConfig(mode="always")
        assert config.mode == "always"

    def test_none_mode(self):
        """none モードが設定可能であること。"""
        config = TraceConfig(mode="none")
        assert config.mode == "none"

    def test_invalid_mode_rejected(self):
        """不正な mode 値が拒否されること。"""
        with pytest.raises(ValidationError):
            TraceConfig(mode="invalid")


# ---------------------------------------------------------------------------
# VideoConfig テスト
# ---------------------------------------------------------------------------

class TestVideoConfig:
    """VideoConfig モデルのテスト。"""

    def test_default_mode(self):
        """デフォルトで on_failure モードであること。"""
        config = VideoConfig()
        assert config.mode == "on_failure"

    def test_always_mode(self):
        """always モードが設定可能であること。"""
        config = VideoConfig(mode="always")
        assert config.mode == "always"

    def test_invalid_mode_rejected(self):
        """不正な mode 値が拒否されること。"""
        with pytest.raises(ValidationError):
            VideoConfig(mode="invalid")


# ---------------------------------------------------------------------------
# ArtifactsConfig テスト
# ---------------------------------------------------------------------------

class TestArtifactsConfig:
    """ArtifactsConfig モデルのテスト。"""

    def test_default_values(self):
        """デフォルト値で全サブ設定が初期化されること。"""
        config = ArtifactsConfig()
        assert config.screenshots.mode == "before_each_step"
        assert config.trace.mode == "on_failure"
        assert config.video.mode == "on_failure"

    def test_custom_screenshots(self):
        """カスタムスクリーンショット設定が反映されること。"""
        config = ArtifactsConfig(
            screenshots=ScreenshotConfig(mode="none", format="png", quality=50)
        )
        assert config.screenshots.mode == "none"
        assert config.screenshots.format == "png"
        assert config.screenshots.quality == 50


# ---------------------------------------------------------------------------
# HooksConfig テスト
# ---------------------------------------------------------------------------

class TestHooksConfig:
    """HooksConfig モデルのテスト。"""

    def test_default_empty_hooks(self):
        """デフォルトで空のフック配列が設定されること。"""
        config = HooksConfig()
        assert config.beforeEachStep == []
        assert config.afterEachStep == []

    def test_hooks_with_steps(self):
        """フックにステップ配列を設定できること。"""
        config = HooksConfig(
            beforeEachStep=[{"screenshot": True, "name": "before-shot"}],
            afterEachStep=[{"log": "step done", "name": "after-log"}],
        )
        assert len(config.beforeEachStep) == 1
        assert len(config.afterEachStep) == 1
        assert config.beforeEachStep[0]["name"] == "before-shot"


# ---------------------------------------------------------------------------
# Section テスト
# ---------------------------------------------------------------------------

class TestSection:
    """Section モデルのテスト。"""

    def test_section_creation(self):
        """セクションが正しく作成されること。"""
        section = Section(
            section="ログイン操作",
            steps=[
                {"fill": {"by": {"css": "#email"}, "value": "test@example.com"}},
                {"click": {"by": {"role": "button", "name": "ログイン"}}},
            ],
        )
        assert section.section == "ログイン操作"
        assert len(section.steps) == 2

    def test_section_empty_steps(self):
        """空のステップ配列でセクションが作成可能であること。"""
        section = Section(section="空セクション")
        assert section.section == "空セクション"
        assert section.steps == []

    def test_section_requires_name(self):
        """section 名が必須であること。"""
        with pytest.raises(ValidationError):
            Section(steps=[])


# ---------------------------------------------------------------------------
# Scenario テスト
# ---------------------------------------------------------------------------

class TestScenario:
    """Scenario モデルのテスト。"""

    def test_minimal_scenario(self):
        """最小構成の Scenario が作成可能であること。"""
        scenario = Scenario(
            title="テストシナリオ",
            baseUrl="http://localhost:4200",
            steps=[{"goto": "http://localhost:4200/login"}],
        )
        assert scenario.title == "テストシナリオ"
        assert scenario.baseUrl == "http://localhost:4200"
        assert scenario.vars == {}
        assert scenario.healing == "off"
        assert len(scenario.steps) == 1

    def test_full_scenario(self):
        """全フィールドを指定した Scenario が作成可能であること。"""
        scenario = Scenario(
            title="フルシナリオ",
            baseUrl="http://localhost:4200",
            vars={"email": "test@example.com", "password": "${env.PASSWORD}"},
            artifacts=ArtifactsConfig(
                screenshots=ScreenshotConfig(mode="before_and_after"),
                trace=TraceConfig(mode="always"),
                video=VideoConfig(mode="always"),
            ),
            hooks=HooksConfig(
                beforeEachStep=[{"screenshot": True}],
                afterEachStep=[{"log": "done"}],
            ),
            steps=[
                {"goto": "http://localhost:4200/login"},
                {"fill": {"by": {"css": "#email"}, "value": "${vars.email}"}},
            ],
            healing="safe",
        )
        assert scenario.title == "フルシナリオ"
        assert scenario.vars["password"] == "${env.PASSWORD}"
        assert scenario.artifacts.screenshots.mode == "before_and_after"
        assert scenario.artifacts.trace.mode == "always"
        assert len(scenario.hooks.beforeEachStep) == 1
        assert scenario.healing == "safe"

    def test_title_required(self):
        """title が必須であること。"""
        with pytest.raises(ValidationError):
            Scenario(
                baseUrl="http://localhost:4200",
                steps=[{"goto": "/"}],
            )

    def test_base_url_required(self):
        """baseUrl が必須であること。"""
        with pytest.raises(ValidationError):
            Scenario(
                title="テスト",
                steps=[{"goto": "/"}],
            )

    def test_steps_required(self):
        """steps が必須であること。"""
        with pytest.raises(ValidationError):
            Scenario(
                title="テスト",
                baseUrl="http://localhost:4200",
            )

    def test_healing_off_default(self):
        """healing のデフォルト値が off であること。"""
        scenario = Scenario(
            title="テスト",
            baseUrl="http://localhost:4200",
            steps=[{"goto": "/"}],
        )
        assert scenario.healing == "off"

    def test_healing_safe(self):
        """healing: safe が設定可能であること。"""
        scenario = Scenario(
            title="テスト",
            baseUrl="http://localhost:4200",
            steps=[{"goto": "/"}],
            healing="safe",
        )
        assert scenario.healing == "safe"

    def test_healing_invalid_rejected(self):
        """不正な healing 値が拒否されること。"""
        with pytest.raises(ValidationError):
            Scenario(
                title="テスト",
                baseUrl="http://localhost:4200",
                steps=[{"goto": "/"}],
                healing="aggressive",
            )

    def test_default_artifacts(self):
        """デフォルトの artifacts 設定が正しいこと。"""
        scenario = Scenario(
            title="テスト",
            baseUrl="http://localhost:4200",
            steps=[{"goto": "/"}],
        )
        assert scenario.artifacts.screenshots.mode == "before_each_step"
        assert scenario.artifacts.screenshots.format == "jpeg"
        assert scenario.artifacts.screenshots.quality == 70
        assert scenario.artifacts.trace.mode == "on_failure"
        assert scenario.artifacts.video.mode == "on_failure"

    def test_default_hooks(self):
        """デフォルトの hooks が空であること。"""
        scenario = Scenario(
            title="テスト",
            baseUrl="http://localhost:4200",
            steps=[{"goto": "/"}],
        )
        assert scenario.hooks.beforeEachStep == []
        assert scenario.hooks.afterEachStep == []


# ---------------------------------------------------------------------------
# vars 変数展開バリデーションテスト
# ---------------------------------------------------------------------------

class TestScenarioVarsValidation:
    """Scenario.vars の変数展開構文バリデーションテスト。"""

    def test_env_var_reference_accepted(self):
        """${env.X} 構文が受け入れられること。"""
        scenario = Scenario(
            title="テスト",
            baseUrl="http://localhost:4200",
            vars={"password": "${env.PASSWORD}"},
            steps=[{"goto": "/"}],
        )
        assert scenario.vars["password"] == "${env.PASSWORD}"

    def test_vars_var_reference_accepted(self):
        """${vars.X} 構文が受け入れられること。"""
        scenario = Scenario(
            title="テスト",
            baseUrl="http://localhost:4200",
            vars={"greeting": "${vars.name} さん"},
            steps=[{"goto": "/"}],
        )
        assert scenario.vars["greeting"] == "${vars.name} さん"

    def test_mixed_references_accepted(self):
        """${env.X} と ${vars.X} の混在が受け入れられること。"""
        scenario = Scenario(
            title="テスト",
            baseUrl="http://localhost:4200",
            vars={
                "url": "${env.BASE_URL}/api/${vars.endpoint}",
            },
            steps=[{"goto": "/"}],
        )
        assert "${env.BASE_URL}" in scenario.vars["url"]
        assert "${vars.endpoint}" in scenario.vars["url"]

    def test_plain_text_accepted(self):
        """変数参照を含まないプレーンテキストが受け入れられること。"""
        scenario = Scenario(
            title="テスト",
            baseUrl="http://localhost:4200",
            vars={"email": "test@example.com"},
            steps=[{"goto": "/"}],
        )
        assert scenario.vars["email"] == "test@example.com"

    def test_invalid_var_namespace_rejected(self):
        """不正な名前空間（env / vars 以外）が拒否されること。"""
        with pytest.raises(ValidationError, match="不正な変数参照"):
            Scenario(
                title="テスト",
                baseUrl="http://localhost:4200",
                vars={"bad": "${unknown.VALUE}"},
                steps=[{"goto": "/"}],
            )

    def test_invalid_sys_namespace_rejected(self):
        """${sys.X} のような不正な名前空間が拒否されること。"""
        with pytest.raises(ValidationError, match="不正な変数参照"):
            Scenario(
                title="テスト",
                baseUrl="http://localhost:4200",
                vars={"bad": "${sys.PATH}"},
                steps=[{"goto": "/"}],
            )

    def test_empty_vars_accepted(self):
        """空の vars が受け入れられること。"""
        scenario = Scenario(
            title="テスト",
            baseUrl="http://localhost:4200",
            vars={},
            steps=[{"goto": "/"}],
        )
        assert scenario.vars == {}

    def test_env_var_with_underscore_accepted(self):
        """アンダースコアを含む環境変数名が受け入れられること。"""
        scenario = Scenario(
            title="テスト",
            baseUrl="http://localhost:4200",
            vars={"db": "${env.DB_HOST_NAME}"},
            steps=[{"goto": "/"}],
        )
        assert scenario.vars["db"] == "${env.DB_HOST_NAME}"
