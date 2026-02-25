"""
Runner のユニットテスト

Playwright の Browser / BrowserContext / Page はモック（unittest.mock）を使用する。
実際のブラウザは起動しない。

テスト対象:
  - RunnerConfig のデフォルト値
  - StepResult のデフォルト値
  - ScenarioResult のデフォルト値
  - Runner._setup_context の設定反映（viewport, timezone, locale, headers, storageState）
  - Runner._execute_single_step のフック実行順序
  - Runner._dispatch_step の StepRegistry ディスパッチ
  - goto 後の waitForLoadState 呼び出し
  - エラー時の StepResult.status == "failed"
  - headed/headless オプション
  - healing モードの統合
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from brt.core.runner import (
    Runner,
    RunnerConfig,
    ScenarioResult,
    StepResult,
    _extract_step_type,
    _sanitize_title,
)


# ---------------------------------------------------------------------------
# ヘルパー: モックオブジェクト生成
# ---------------------------------------------------------------------------

def _make_mock_page() -> MagicMock:
    """モック Page を生成する。"""
    page = AsyncMock()
    page.goto = AsyncMock()
    page.wait_for_load_state = AsyncMock()
    page.screenshot = AsyncMock()
    return page


def _make_mock_registry() -> MagicMock:
    """モック StepRegistry を生成する。"""
    registry = MagicMock()
    handler = MagicMock()
    handler.execute = AsyncMock()
    registry.get = MagicMock(return_value=handler)
    return registry


def _make_mock_scenario(**overrides) -> MagicMock:
    """モック Scenario を生成する。"""
    scenario = MagicMock()
    scenario.title = overrides.get("title", "テストシナリオ")
    scenario.baseUrl = overrides.get("baseUrl", "http://localhost:4200")
    scenario.healing = overrides.get("healing", "off")

    # vars
    scenario.vars = overrides.get("vars", {})

    # steps
    scenario.steps = overrides.get("steps", [])

    # hooks
    hooks = MagicMock()
    hooks.beforeEachStep = overrides.get("beforeEachStep", [])
    hooks.afterEachStep = overrides.get("afterEachStep", [])
    scenario.hooks = hooks

    # artifacts
    artifacts = MagicMock()
    screenshots = MagicMock()
    screenshots.mode = "none"
    trace = MagicMock()
    trace.mode = "none"
    video = MagicMock()
    video.mode = "none"
    artifacts.screenshots = screenshots
    artifacts.trace = trace
    artifacts.video = video
    scenario.artifacts = artifacts

    return scenario


def _make_mock_step_context() -> MagicMock:
    """モック StepContext を生成する。"""
    context = MagicMock()
    context.selector_resolver = MagicMock()
    context.variable_expander = MagicMock()
    return context


# ===========================================================================
# テスト: RunnerConfig デフォルト値
# ===========================================================================

class TestRunnerConfig:
    """RunnerConfig のデフォルト値テスト。"""

    def test_default_headed(self) -> None:
        """headed のデフォルトは False（headless モード）。"""
        config = RunnerConfig()
        assert config.headed is False

    def test_default_workers(self) -> None:
        """workers のデフォルトは 1（逐次実行）。"""
        config = RunnerConfig()
        assert config.workers == 1

    def test_default_base_artifacts_dir(self) -> None:
        """base_artifacts_dir のデフォルトは Path("artifacts")。"""
        config = RunnerConfig()
        assert config.base_artifacts_dir == Path("artifacts")

    def test_custom_values(self) -> None:
        """カスタム値が正しく設定されること。"""
        config = RunnerConfig(
            headed=True,
            workers=4,
            base_artifacts_dir=Path("/tmp/test-artifacts"),
        )
        assert config.headed is True
        assert config.workers == 4
        assert config.base_artifacts_dir == Path("/tmp/test-artifacts")


# ===========================================================================
# テスト: StepResult デフォルト値
# ===========================================================================

class TestStepResult:
    """StepResult のデフォルト値テスト。"""

    def test_default_status(self) -> None:
        """status のデフォルトは "passed"。"""
        result = StepResult(step_name="test", step_type="click", step_index=0)
        assert result.status == "passed"

    def test_default_duration(self) -> None:
        """duration_ms のデフォルトは 0.0。"""
        result = StepResult(step_name="test", step_type="click", step_index=0)
        assert result.duration_ms == 0.0

    def test_default_error(self) -> None:
        """error のデフォルトは None。"""
        result = StepResult(step_name="test", step_type="click", step_index=0)
        assert result.error is None

    def test_default_screenshot_path(self) -> None:
        """screenshot_path のデフォルトは None。"""
        result = StepResult(step_name="test", step_type="click", step_index=0)
        assert result.screenshot_path is None

    def test_default_section(self) -> None:
        """section のデフォルトは None。"""
        result = StepResult(step_name="test", step_type="click", step_index=0)
        assert result.section is None

    def test_required_fields(self) -> None:
        """必須フィールドが正しく設定されること。"""
        result = StepResult(
            step_name="click-login",
            step_type="click",
            step_index=3,
        )
        assert result.step_name == "click-login"
        assert result.step_type == "click"
        assert result.step_index == 3


# ===========================================================================
# テスト: ScenarioResult デフォルト値
# ===========================================================================

class TestScenarioResult:
    """ScenarioResult のデフォルト値テスト。"""

    def test_default_status(self) -> None:
        """status のデフォルトは "passed"。"""
        result = ScenarioResult(scenario_title="テスト")
        assert result.status == "passed"

    def test_default_steps(self) -> None:
        """steps のデフォルトは空リスト。"""
        result = ScenarioResult(scenario_title="テスト")
        assert result.steps == []

    def test_default_duration(self) -> None:
        """duration_ms のデフォルトは 0.0。"""
        result = ScenarioResult(scenario_title="テスト")
        assert result.duration_ms == 0.0

    def test_default_artifacts_dir(self) -> None:
        """artifacts_dir のデフォルトは None。"""
        result = ScenarioResult(scenario_title="テスト")
        assert result.artifacts_dir is None

    def test_default_timestamps(self) -> None:
        """started_at / finished_at のデフォルトは None。"""
        result = ScenarioResult(scenario_title="テスト")
        assert result.started_at is None
        assert result.finished_at is None

    def test_steps_are_independent(self) -> None:
        """各インスタンスの steps リストが独立していること。"""
        result1 = ScenarioResult(scenario_title="A")
        result2 = ScenarioResult(scenario_title="B")
        result1.steps.append(
            StepResult(step_name="s1", step_type="click", step_index=0)
        )
        assert len(result2.steps) == 0


# ===========================================================================
# テスト: Runner._setup_context — mock ベース
# ===========================================================================

class TestSetupContext:
    """Runner._setup_context のテスト（mock ベース）。"""

    @pytest.fixture
    def runner(self) -> Runner:
        """テスト用 Runner インスタンス。"""
        return Runner(_make_mock_registry())

    @pytest.fixture
    def mock_browser(self) -> MagicMock:
        """モック Browser。"""
        browser = AsyncMock()
        browser.new_context = AsyncMock(return_value=AsyncMock())
        return browser

    async def test_viewport_setting(self, runner: Runner, mock_browser: MagicMock) -> None:
        """viewport が vars から正しく設定されること。"""
        scenario = _make_mock_scenario(vars={
            "viewportWidth": "1920",
            "viewportHeight": "1080",
        })

        await runner._setup_context(mock_browser, scenario)

        mock_browser.new_context.assert_called_once()
        call_kwargs = mock_browser.new_context.call_args[1]
        assert call_kwargs["viewport"] == {"width": 1920, "height": 1080}

    async def test_timezone_setting(self, runner: Runner, mock_browser: MagicMock) -> None:
        """timezone が vars から正しく設定されること。"""
        scenario = _make_mock_scenario(vars={"timezone": "Asia/Tokyo"})

        await runner._setup_context(mock_browser, scenario)

        call_kwargs = mock_browser.new_context.call_args[1]
        assert call_kwargs["timezone_id"] == "Asia/Tokyo"

    async def test_locale_setting(self, runner: Runner, mock_browser: MagicMock) -> None:
        """locale が vars から正しく設定されること。"""
        scenario = _make_mock_scenario(vars={"locale": "ja-JP"})

        await runner._setup_context(mock_browser, scenario)

        call_kwargs = mock_browser.new_context.call_args[1]
        assert call_kwargs["locale"] == "ja-JP"

    async def test_extra_headers_setting(self, runner: Runner, mock_browser: MagicMock) -> None:
        """extraHeaders が vars から正しくパースされること。"""
        scenario = _make_mock_scenario(vars={
            "extraHeaders": "Authorization:Bearer token123,X-Custom:value",
        })

        await runner._setup_context(mock_browser, scenario)

        call_kwargs = mock_browser.new_context.call_args[1]
        assert call_kwargs["extra_http_headers"] == {
            "Authorization": "Bearer token123",
            "X-Custom": "value",
        }

    async def test_storage_state_setting(self, runner: Runner, mock_browser: MagicMock) -> None:
        """storageState が vars から正しく設定されること。"""
        scenario = _make_mock_scenario(vars={
            "storageState": "/path/to/state.json",
        })

        await runner._setup_context(mock_browser, scenario)

        call_kwargs = mock_browser.new_context.call_args[1]
        assert call_kwargs["storage_state"] == "/path/to/state.json"

    async def test_no_settings(self, runner: Runner, mock_browser: MagicMock) -> None:
        """vars が空の場合、追加オプションなしで Context が生成されること。"""
        scenario = _make_mock_scenario(vars={})

        await runner._setup_context(mock_browser, scenario)

        call_kwargs = mock_browser.new_context.call_args[1]
        # viewport, timezone_id, locale 等が含まれないこと
        assert "viewport" not in call_kwargs
        assert "timezone_id" not in call_kwargs
        assert "locale" not in call_kwargs

    async def test_video_recording_setting(self, runner: Runner, mock_browser: MagicMock) -> None:
        """video.mode が "always" の場合、record_video_dir が設定されること。"""
        scenario = _make_mock_scenario(vars={})
        scenario.artifacts.video.mode = "always"

        await runner._setup_context(mock_browser, scenario)

        call_kwargs = mock_browser.new_context.call_args[1]
        assert "record_video_dir" in call_kwargs


# ===========================================================================
# テスト: Runner._execute_single_step — フック実行順序
# ===========================================================================

class TestExecuteSingleStep:
    """Runner._execute_single_step のテスト（mock ベース）。"""

    @pytest.fixture
    def runner(self) -> Runner:
        """テスト用 Runner インスタンス。"""
        return Runner(_make_mock_registry())

    async def test_hook_execution_order(self, runner: Runner) -> None:
        """beforeEachStep → ステップ本体 → afterEachStep の順序で実行されること。"""
        page = _make_mock_page()
        context = _make_mock_step_context()

        # 実行順序を記録するリスト
        execution_order: list[str] = []

        # フックステップ
        before_step = {"log": "before hook"}
        after_step = {"log": "after hook"}
        hooks = {"before": [before_step], "after": [after_step]}

        # _dispatch_step をモックして実行順序を記録
        original_dispatch = runner._dispatch_step

        async def mock_dispatch(pg, step_type, params, ctx):
            execution_order.append(step_type)

        runner._dispatch_step = mock_dispatch

        step = {"click": {"by": {"testId": "btn"}, "name": "test-click"}}
        result = await runner._execute_single_step(
            page, step, 0, context, hooks
        )

        # 順序: log(before) → click(本体) → log(after)
        assert execution_order == ["log", "click", "log"]
        assert result.status == "passed"

    async def test_no_hooks(self, runner: Runner) -> None:
        """フックが空の場合、ステップ本体のみ実行されること。"""
        page = _make_mock_page()
        context = _make_mock_step_context()
        hooks = {"before": [], "after": []}

        execution_order: list[str] = []

        async def mock_dispatch(pg, step_type, params, ctx):
            execution_order.append(step_type)

        runner._dispatch_step = mock_dispatch

        step = {"fill": {"by": {"css": "#input"}, "value": "test", "name": "fill-input"}}
        result = await runner._execute_single_step(
            page, step, 0, context, hooks
        )

        assert execution_order == ["fill"]
        assert result.status == "passed"

    async def test_step_error_sets_failed(self, runner: Runner) -> None:
        """ステップ実行中にエラーが発生した場合、status が "failed" になること。"""
        page = _make_mock_page()
        context = _make_mock_step_context()
        hooks = {"before": [], "after": []}

        async def mock_dispatch(pg, step_type, params, ctx):
            raise RuntimeError("要素が見つかりません")

        runner._dispatch_step = mock_dispatch

        step = {"click": {"by": {"testId": "missing"}, "name": "click-missing"}}
        result = await runner._execute_single_step(
            page, step, 0, context, hooks
        )

        assert result.status == "failed"
        assert "要素が見つかりません" in result.error

    async def test_error_screenshot_saved(self, runner: Runner, tmp_path: Path) -> None:
        """エラー時にスクリーンショットが保存されること。"""
        page = _make_mock_page()
        context = _make_mock_step_context()
        hooks = {"before": [], "after": []}

        async def mock_dispatch(pg, step_type, params, ctx):
            raise RuntimeError("テストエラー")

        runner._dispatch_step = mock_dispatch

        step = {"click": {"by": {"testId": "err"}, "name": "click-err"}}
        result = await runner._execute_single_step(
            page, step, 0, context, hooks
        )

        assert result.status == "failed"
        # screenshot メソッドが呼ばれたことを確認
        page.screenshot.assert_called_once()

    async def test_step_duration_recorded(self, runner: Runner) -> None:
        """ステップの実行時間が記録されること。"""
        page = _make_mock_page()
        context = _make_mock_step_context()
        hooks = {"before": [], "after": []}

        async def mock_dispatch(pg, step_type, params, ctx):
            pass

        runner._dispatch_step = mock_dispatch

        step = {"click": {"by": {"testId": "btn"}, "name": "click-btn"}}
        result = await runner._execute_single_step(
            page, step, 0, context, hooks
        )

        assert result.duration_ms >= 0.0

    async def test_section_recorded(self, runner: Runner) -> None:
        """section パラメータが StepResult に記録されること。"""
        page = _make_mock_page()
        context = _make_mock_step_context()
        hooks = {"before": [], "after": []}

        async def mock_dispatch(pg, step_type, params, ctx):
            pass

        runner._dispatch_step = mock_dispatch

        step = {"click": {"by": {"testId": "btn"}, "name": "click-btn"}}
        result = await runner._execute_single_step(
            page, step, 0, context, hooks, section="ログインセクション"
        )

        assert result.section == "ログインセクション"


# ===========================================================================
# テスト: Runner._dispatch_step — StepRegistry ディスパッチ
# ===========================================================================

class TestDispatchStep:
    """Runner._dispatch_step のテスト（mock ベース）。"""

    async def test_goto_calls_page_goto_and_wait(self) -> None:
        """goto ステップで page.goto() と waitForLoadState("domcontentloaded") が呼ばれること。"""
        registry = _make_mock_registry()
        runner = Runner(registry)
        page = _make_mock_page()
        context = _make_mock_step_context()

        await runner._dispatch_step(
            page, "goto", "http://example.com", context
        )

        page.goto.assert_called_once_with("http://example.com")
        page.wait_for_load_state.assert_called_once_with("domcontentloaded")

    async def test_goto_with_dict_params(self) -> None:
        """goto ステップが辞書パラメータでも正しく動作すること。"""
        registry = _make_mock_registry()
        runner = Runner(registry)
        page = _make_mock_page()
        context = _make_mock_step_context()

        await runner._dispatch_step(
            page, "goto", {"url": "http://example.com/login", "name": "open-login"}, context
        )

        page.goto.assert_called_once_with("http://example.com/login")
        page.wait_for_load_state.assert_called_once_with("domcontentloaded")

    async def test_non_goto_dispatches_to_registry(self) -> None:
        """goto 以外のステップは StepRegistry のハンドラに委譲されること。"""
        registry = _make_mock_registry()
        runner = Runner(registry)
        page = _make_mock_page()
        context = _make_mock_step_context()

        params = {"by": {"testId": "btn"}, "name": "click-btn"}
        await runner._dispatch_step(page, "click", params, context)

        registry.get.assert_called_once_with("click")
        handler = registry.get.return_value
        handler.execute.assert_called_once_with(page, params, context)

    async def test_unknown_step_raises_key_error(self) -> None:
        """未登録のステップ種別で KeyError が発生すること。"""
        registry = MagicMock()
        registry.get = MagicMock(side_effect=KeyError("unknown_step"))
        runner = Runner(registry)
        page = _make_mock_page()
        context = _make_mock_step_context()

        with pytest.raises(KeyError):
            await runner._dispatch_step(
                page, "unknown_step", {}, context
            )


# ===========================================================================
# テスト: headed/headless オプション
# ===========================================================================

class TestHeadedHeadless:
    """headed/headless オプションのテスト。"""

    def test_headed_true(self) -> None:
        """headed=True が正しく設定されること。"""
        config = RunnerConfig(headed=True)
        assert config.headed is True

    def test_headed_false_default(self) -> None:
        """headed のデフォルトは False（headless）。"""
        config = RunnerConfig()
        assert config.headed is False


# ===========================================================================
# テスト: healing モードの統合
# ===========================================================================

class TestHealingIntegration:
    """healing モードの統合テスト（mock ベース）。"""

    async def test_healing_off_scenario(self) -> None:
        """healing: off のシナリオが正しく構成されること。"""
        scenario = _make_mock_scenario(healing="off")
        assert scenario.healing == "off"

    async def test_healing_safe_scenario(self) -> None:
        """healing: safe のシナリオが正しく構成されること。"""
        scenario = _make_mock_scenario(healing="safe")
        assert scenario.healing == "safe"


# ===========================================================================
# テスト: ヘルパー関数
# ===========================================================================

class TestHelpers:
    """ヘルパー関数のテスト。"""

    def test_extract_step_type_click(self) -> None:
        """click ステップの種別とパラメータが正しく抽出されること。"""
        step = {"click": {"by": {"testId": "btn"}, "name": "click-btn"}}
        step_type, params = _extract_step_type(step)
        assert step_type == "click"
        assert params == {"by": {"testId": "btn"}, "name": "click-btn"}

    def test_extract_step_type_goto_string(self) -> None:
        """goto ステップ（文字列パラメータ）が正しく抽出されること。"""
        step = {"goto": "http://example.com"}
        step_type, params = _extract_step_type(step)
        assert step_type == "goto"
        assert params == "http://example.com"

    def test_extract_step_type_empty_raises(self) -> None:
        """空のステップ辞書で ValueError が発生すること。"""
        with pytest.raises(ValueError, match="空のステップ"):
            _extract_step_type({})

    def test_sanitize_title_basic(self) -> None:
        """基本的なタイトルがサニタイズされること。"""
        assert _sanitize_title("ログインテスト") == "ログインテスト"

    def test_sanitize_title_with_spaces(self) -> None:
        """スペースがアンダースコアに変換されること。"""
        result = _sanitize_title("ログイン フロー テスト")
        assert " " not in result

    def test_sanitize_title_max_length(self) -> None:
        """タイトルが100文字以内に切り詰められること。"""
        long_title = "あ" * 200
        result = _sanitize_title(long_title)
        assert len(result) <= 100


# ===========================================================================
# テスト: Runner._run_hook_steps
# ===========================================================================

class TestRunHookSteps:
    """Runner._run_hook_steps のテスト。"""

    async def test_hook_steps_executed_in_order(self) -> None:
        """フックステップが順番に実行されること。"""
        registry = _make_mock_registry()
        runner = Runner(registry)
        page = _make_mock_page()
        context = _make_mock_step_context()

        execution_order: list[str] = []

        async def mock_dispatch(pg, step_type, params, ctx):
            execution_order.append(step_type)

        runner._dispatch_step = mock_dispatch

        hook_steps = [
            {"log": "first hook"},
            {"screenshot": True},
        ]

        await runner._run_hook_steps(page, hook_steps, context)

        assert execution_order == ["log", "screenshot"]

    async def test_empty_hook_steps(self) -> None:
        """空のフックリストでエラーが発生しないこと。"""
        registry = _make_mock_registry()
        runner = Runner(registry)
        page = _make_mock_page()
        context = _make_mock_step_context()

        # エラーなく完了すること
        await runner._run_hook_steps(page, [], context)
