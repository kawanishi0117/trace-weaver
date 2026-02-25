"""
Runner — YAML DSL 実行エンジン

Scenario を読み込み、Playwright でブラウザ操作を自動実行する。

主な機能:
  - RunnerConfig: 実行設定（headed/headless, workers, artifacts ディレクトリ）
  - StepResult / ScenarioResult: 実行結果データクラス
  - Runner: シナリオ実行エンジン本体

要件 7.1: RunnerConfig, StepResult, ScenarioResult データクラス
要件 7.2: Browser/Context 生成と環境設定
要件 7.3: goto 後の waitForLoadState("domcontentloaded") 自動実行
要件 7.4: ステップ種別に応じた StepRegistry へのディスパッチ
要件 7.5: beforeEachStep → ステップ本体 → afterEachStep の順序保証
要件 7.6: エラー発生時のスクリーンショット・トレース・動画保存
要件 7.7-7.8: headed/headless オプション
要件 7.9: --workers N による並列実行（asyncio ベース）
要件 7.10-7.11: healing モード（off/safe）の統合
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Optional

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Page, Playwright

    from ..dsl.schema import Scenario, ScreenshotConfig
    from ..steps.registry import StepContext, StepRegistry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 設定・結果データクラス
# ---------------------------------------------------------------------------

@dataclass
class RunnerConfig:
    """Runner の実行設定。

    Attributes:
        headed: ブラウザを表示するか（True: headed, False: headless）
        workers: 並列実行ワーカー数（1 = 逐次実行）
        base_artifacts_dir: 成果物ベースディレクトリ
        slow_mo: 各 Playwright 操作間の遅延（ミリ秒）。iframe リロード等のタイミング問題を緩和する
        step_timeout: 各ステップのタイムアウト（ミリ秒）。0 で無制限
    """

    headed: bool = False
    workers: int = 1
    base_artifacts_dir: Path = field(default_factory=lambda: Path("artifacts"))
    slow_mo: int = 0
    step_timeout: int = 30_000


@dataclass
class StepResult:
    """単一ステップの実行結果。

    Attributes:
        step_name: ステップ名（YAML の name フィールド）
        step_type: ステップ種別（goto, click, fill 等）
        step_index: ステップのインデックス（0始まり）
        status: 実行結果（passed / failed / skipped）
        duration_ms: 実行時間（ミリ秒）
        error: エラーメッセージ（失敗時のみ）
        screenshot_path: エラー時スクリーンショットのパス
        section: 所属セクション名
    """

    step_name: str
    step_type: str
    step_index: int
    status: Literal["passed", "failed", "skipped"] = "passed"
    duration_ms: float = 0.0
    error: Optional[str] = None
    screenshot_path: Optional[Path] = None
    section: Optional[str] = None


@dataclass
class ScenarioResult:
    """シナリオ全体の実行結果。

    Attributes:
        scenario_title: シナリオ名
        status: 全体結果（passed / failed）
        steps: 各ステップの実行結果リスト
        duration_ms: 全体実行時間（ミリ秒）
        artifacts_dir: 成果物ディレクトリ
        started_at: 実行開始日時
        finished_at: 実行終了日時
    """

    scenario_title: str
    status: Literal["passed", "failed"] = "passed"
    steps: list[StepResult] = field(default_factory=list)
    duration_ms: float = 0.0
    artifacts_dir: Optional[Path] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Runner 本体
# ---------------------------------------------------------------------------

class Runner:
    """YAML DSL 実行エンジン。

    Scenario を受け取り、Playwright でブラウザ操作を自動実行する。
    StepRegistry を通じてステップ種別に応じたハンドラへディスパッチする。

    使用例::

        runner = Runner(registry)
        result = await runner.run(scenario, config)
    """

    def __init__(self, registry: StepRegistry) -> None:
        """Runner を初期化する。

        Args:
            registry: ステップハンドラのレジストリ
        """
        self._registry = registry

    # -------------------------------------------------------------------
    # パブリック API
    # -------------------------------------------------------------------

    async def run(self, scenario: Scenario, config: RunnerConfig) -> ScenarioResult:
        """シナリオを実行し、結果を返す。

        Playwright ブラウザを起動し、Context / Page を生成して
        ステップを順次実行する。エラー発生時はスクリーンショットを保存する。

        Args:
            scenario: 実行対象のシナリオ
            config: 実行設定

        Returns:
            シナリオ全体の実行結果
        """
        from playwright.async_api import async_playwright

        result = ScenarioResult(
            scenario_title=scenario.title,
            started_at=datetime.now(),
        )

        # 成果物ディレクトリの準備
        artifacts_dir = config.base_artifacts_dir / _sanitize_title(scenario.title)
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        result.artifacts_dir = artifacts_dir

        start_time = time.perf_counter()

        async with async_playwright() as pw:
            # ブラウザ起動（headed/headless 切り替え）
            # slow_mo: 各操作間に遅延を挿入（iframe リロード等のタイミング問題を緩和）
            browser = await pw.chromium.launch(
                headless=not config.headed,
                slow_mo=config.slow_mo,
            )

            try:
                # Context 生成（viewport, timezone, locale 等の設定反映）
                context = await self._setup_context(browser, scenario)

                # トレース開始（設定に応じて）
                if scenario.artifacts.trace.mode != "none":
                    await context.tracing.start(
                        screenshots=True, snapshots=True
                    )

                page = await context.new_page()

                # 最初のステップが goto でない場合のみ baseUrl へ自動遷移
                first_step_is_goto = (
                    scenario.steps
                    and isinstance(scenario.steps[0], dict)
                    and "goto" in scenario.steps[0]
                )
                if not first_step_is_goto:
                    await page.goto(scenario.baseUrl)
                    await page.wait_for_load_state("domcontentloaded")

                # StepContext の構築
                from ..core.selector import SelectorResolver
                from ..dsl.variables import VariableExpander
                from ..steps.registry import StepContext

                selector_resolver = SelectorResolver(healing=scenario.healing)
                variable_expander = VariableExpander(
                    env={}, vars=dict(scenario.vars)
                )
                step_context = StepContext(
                    selector_resolver=selector_resolver,
                    variable_expander=variable_expander,
                )

                # ステップ実行
                await self._execute_steps(
                    page, scenario, step_context, result, config,
                )

            except Exception as exc:
                result.status = "failed"
                logger.error("シナリオ実行中にエラーが発生しました: %s", exc)
            finally:
                # トレース保存
                if scenario.artifacts.trace.mode != "none":
                    trace_path = artifacts_dir / "trace.zip"
                    try:
                        await context.tracing.stop(path=str(trace_path))
                    except Exception:
                        pass

                await browser.close()

        result.finished_at = datetime.now()
        result.duration_ms = (time.perf_counter() - start_time) * 1000

        return result

    async def run_parallel(
        self,
        scenarios: list[Scenario],
        config: RunnerConfig,
    ) -> list[ScenarioResult]:
        """複数シナリオを並列実行する。

        asyncio.Semaphore で同時実行数を config.workers に制限する。

        Args:
            scenarios: 実行対象のシナリオリスト
            config: 実行設定（workers で並列数を指定）

        Returns:
            各シナリオの実行結果リスト
        """
        semaphore = asyncio.Semaphore(config.workers)

        async def _run_with_semaphore(scenario: Scenario) -> ScenarioResult:
            async with semaphore:
                return await self.run(scenario, config)

        tasks = [_run_with_semaphore(s) for s in scenarios]
        return await asyncio.gather(*tasks)

    # -------------------------------------------------------------------
    # Context 生成
    # -------------------------------------------------------------------

    async def _setup_context(
        self, browser: Browser, scenario: Scenario
    ) -> BrowserContext:
        """Browser Context を生成し、Scenario の設定を反映する。

        viewport, timezone, locale, extra HTTP headers, storageState を
        Scenario の設定に基づいて Context に適用する。

        Args:
            browser: Playwright の Browser オブジェクト
            scenario: 設定元のシナリオ

        Returns:
            設定済みの BrowserContext
        """
        context_options: dict = {}

        # viewport 設定（vars から取得）
        viewport_width = scenario.vars.get("viewportWidth")
        viewport_height = scenario.vars.get("viewportHeight")
        if viewport_width and viewport_height:
            context_options["viewport"] = {
                "width": int(viewport_width),
                "height": int(viewport_height),
            }

        # timezone 設定
        timezone = scenario.vars.get("timezone")
        if timezone:
            context_options["timezone_id"] = timezone

        # locale 設定
        locale = scenario.vars.get("locale")
        if locale:
            context_options["locale"] = locale

        # extra HTTP headers
        headers = scenario.vars.get("extraHeaders")
        if headers:
            # カンマ区切りの "Key:Value" 形式をパース
            parsed_headers: dict[str, str] = {}
            for pair in str(headers).split(","):
                if ":" in pair:
                    k, v = pair.split(":", 1)
                    parsed_headers[k.strip()] = v.strip()
            if parsed_headers:
                context_options["extra_http_headers"] = parsed_headers

        # storageState 設定
        storage_state = scenario.vars.get("storageState")
        if storage_state:
            context_options["storage_state"] = storage_state

        # 動画録画設定
        if scenario.artifacts.video.mode != "none":
            artifacts_dir = Path("artifacts") / _sanitize_title(scenario.title)
            context_options["record_video_dir"] = str(artifacts_dir / "videos")

        return await browser.new_context(**context_options)

    # -------------------------------------------------------------------
    # ステップ実行
    # -------------------------------------------------------------------

    async def _execute_steps(
        self,
        page: Page,
        scenario: Scenario,
        context: StepContext,
        result: ScenarioResult,
        config: RunnerConfig,
        current_section: Optional[str] = None,
    ) -> None:
        """ステップリストを順次実行する。

        section ステップの場合は再帰的にセクション内ステップを実行する。
        各ステップの前後にフックを実行する。

        Args:
            page: Playwright の Page オブジェクト
            scenario: 実行中のシナリオ
            context: ステップ実行コンテキスト
            result: 結果を格納する ScenarioResult
            config: 実行設定（タイムアウト等）
            current_section: 現在のセクション名
        """
        hooks = {
            "before": scenario.hooks.beforeEachStep,
            "after": scenario.hooks.afterEachStep,
        }
        # スクリーンショット設定
        ss_config = scenario.artifacts.screenshots

        for idx, step in enumerate(scenario.steps):
            # section ステップの処理
            if "section" in step:
                section_name = step["section"]
                section_steps = step.get("steps", [])
                logger.info("セクション開始: %s", section_name)

                # セクション内ステップを個別に実行
                for s_idx, s_step in enumerate(section_steps):
                    step_result = await self._execute_single_step(
                        page, s_step, len(result.steps), context, hooks,
                        section=section_name,
                        artifacts_dir=result.artifacts_dir,
                        ss_config=ss_config,
                        step_timeout=config.step_timeout,
                    )
                    result.steps.append(step_result)
                    if step_result.status == "failed":
                        result.status = "failed"
                        return
                continue

            # 通常ステップの実行
            step_result = await self._execute_single_step(
                page, step, idx, context, hooks,
                section=current_section,
                artifacts_dir=result.artifacts_dir,
                ss_config=ss_config,
                step_timeout=config.step_timeout,
            )
            result.steps.append(step_result)

            # 失敗時は後続ステップをスキップ
            if step_result.status == "failed":
                result.status = "failed"
                return

    async def _execute_single_step(
        self,
        page: Page,
        step: dict,
        step_index: int,
        context: StepContext,
        hooks: dict,
        section: Optional[str] = None,
        artifacts_dir: Optional[Path] = None,
        ss_config: Optional[ScreenshotConfig] = None,
        step_timeout: int = 30_000,
    ) -> StepResult:
        """単一ステップを実行する（フック含む）。

        実行順序: beforeEachStep → ステップ本体 → afterEachStep
        ss_config に応じてステップ前後にスクリーンショットを撮影する。
        step_timeout ミリ秒以内に完了しない場合はタイムアウトエラーとする。
        エラー発生時はスクリーンショットを保存し、StepResult.status を "failed" にする。

        Args:
            page: Playwright の Page オブジェクト
            step: ステップ辞書（YAML からパースされた dict）
            step_index: ステップインデックス
            context: ステップ実行コンテキスト
            hooks: フック定義（before / after）
            section: 所属セクション名
            artifacts_dir: 成果物ディレクトリ
            ss_config: スクリーンショット設定
            step_timeout: ステップタイムアウト（ミリ秒）。0 で無制限

        Returns:
            ステップの実行結果
        """
        # ステップ種別と名前を抽出
        step_type, params = _extract_step_type(step)
        step_name = params.get("name", f"{step_type}_{step_index}") if isinstance(params, dict) else f"{step_type}_{step_index}"

        step_result = StepResult(
            step_name=step_name,
            step_type=step_type,
            step_index=step_index,
            section=section,
        )

        # スクリーンショット保存先の決定
        ss_dir = (artifacts_dir / "screenshots") if artifacts_dir else Path("artifacts/screenshots")
        ss_mode = ss_config.mode if ss_config else "none"
        ss_fmt = ss_config.format if ss_config else "jpeg"
        ss_quality = ss_config.quality if ss_config else 70

        start_time = time.perf_counter()

        try:
            # ステップ前スクリーンショット（before_each_step / before_and_after）
            if ss_mode in ("before_each_step", "before_and_after"):
                await self._take_screenshot(
                    page, ss_dir, step_index, step_name,
                    suffix="before", fmt=ss_fmt, quality=ss_quality,
                )

            # beforeEachStep フック実行
            before_steps = hooks.get("before", [])
            if before_steps:
                await self._run_hook_steps(page, before_steps, context)

            # ステップ本体の実行（タイムアウト制御付き）
            if step_timeout > 0:
                timeout_sec = step_timeout / 1000.0
                try:
                    await asyncio.wait_for(
                        self._dispatch_step(page, step_type, params, context),
                        timeout=timeout_sec,
                    )
                except asyncio.TimeoutError:
                    raise TimeoutError(
                        f"ステップ '{step_name}' が {step_timeout}ms 以内に完了しませんでした。"
                        f" --step-timeout オプションで調整できます。"
                    )
            else:
                # タイムアウト無制限
                await self._dispatch_step(page, step_type, params, context)

            # afterEachStep フック実行
            after_steps = hooks.get("after", [])
            if after_steps:
                await self._run_hook_steps(page, after_steps, context)

            # ステップ後スクリーンショット（before_and_after のみ）
            if ss_mode == "before_and_after":
                await self._take_screenshot(
                    page, ss_dir, step_index, step_name,
                    suffix="after", fmt=ss_fmt, quality=ss_quality,
                )

            step_result.status = "passed"

        except Exception as exc:
            step_result.status = "failed"
            step_result.error = str(exc)
            logger.error(
                "ステップ '%s' (index=%d) でエラー: %s",
                step_name, step_index, exc,
            )

            # エラー時のスクリーンショット保存
            try:
                error_path = ss_dir / f"step{step_index:03d}_{step_name}_error.png"
                error_path.parent.mkdir(parents=True, exist_ok=True)
                await page.screenshot(path=str(error_path))
                step_result.screenshot_path = error_path
            except Exception as ss_exc:
                logger.warning("スクリーンショット保存に失敗: %s", ss_exc)

        step_result.duration_ms = (time.perf_counter() - start_time) * 1000
        return step_result

    # -------------------------------------------------------------------
    # スクリーンショット撮影
    # -------------------------------------------------------------------

    async def _take_screenshot(
        self,
        page: Page,
        ss_dir: Path,
        step_index: int,
        step_name: str,
        suffix: str,
        fmt: str = "jpeg",
        quality: int = 70,
    ) -> Path:
        """ステップ前後のスクリーンショットを撮影して保存する。

        Args:
            page: Playwright の Page オブジェクト
            ss_dir: スクリーンショット保存ディレクトリ
            step_index: ステップインデックス
            step_name: ステップ名
            suffix: ファイル名サフィックス（before / after）
            fmt: 画像フォーマット（jpeg / png）
            quality: JPEG 品質（1〜100）

        Returns:
            保存先のパス
        """
        ss_dir.mkdir(parents=True, exist_ok=True)
        ext = "jpg" if fmt == "jpeg" else "png"
        filename = f"step{step_index:03d}_{step_name}_{suffix}.{ext}"
        filepath = ss_dir / filename

        ss_kwargs: dict = {"path": str(filepath)}
        if fmt == "jpeg":
            ss_kwargs["type"] = "jpeg"
            ss_kwargs["quality"] = quality
        else:
            ss_kwargs["type"] = "png"

        await page.screenshot(**ss_kwargs)
        logger.info("スクリーンショット保存: %s", filepath)
        return filepath

    # -------------------------------------------------------------------
    # ステップディスパッチ
    # -------------------------------------------------------------------

    async def _dispatch_step(
        self, page: Page, step_type: str, params: dict | str, context: StepContext
    ) -> None:
        """ステップ種別に応じたハンドラへのディスパッチ。

        goto ステップの場合は遷移後に waitForLoadState("domcontentloaded") を
        自動実行する。その他のステップは StepRegistry から取得したハンドラに委譲する。

        Args:
            page: Playwright の Page オブジェクト
            step_type: ステップ種別（goto, click, fill 等）
            params: ステップパラメータ
            context: ステップ実行コンテキスト

        Raises:
            KeyError: 未登録のステップ種別の場合
        """
        # goto ステップの特別処理
        if step_type == "goto":
            url = params if isinstance(params, str) else params.get("url", params.get("goto", ""))
            logger.info("goto: %s", url)
            await page.goto(url)
            await page.wait_for_load_state("domcontentloaded")
            return

        # StepRegistry からハンドラを取得して実行
        handler = self._registry.get(step_type)
        step_params = params if isinstance(params, dict) else {}
        await handler.execute(page, step_params, context)

    # -------------------------------------------------------------------
    # フック実行
    # -------------------------------------------------------------------

    async def _run_hook_steps(
        self, page: Page, hook_steps: list, context: StepContext
    ) -> None:
        """フックステップを実行する。

        beforeEachStep / afterEachStep で定義されたステップを順次実行する。

        Args:
            page: Playwright の Page オブジェクト
            hook_steps: フックステップのリスト
            context: ステップ実行コンテキスト
        """
        for hook_step in hook_steps:
            hook_type, hook_params = _extract_step_type(hook_step)
            await self._dispatch_step(page, hook_type, hook_params, context)


# ---------------------------------------------------------------------------
# ヘルパー関数
# ---------------------------------------------------------------------------

def _extract_step_type(step: dict) -> tuple[str, dict | str]:
    """ステップ辞書からステップ種別とパラメータを抽出する。

    YAML DSL のステップは { "stepType": params } 形式で定義される。
    最初のキーをステップ種別、その値をパラメータとして返す。

    Args:
        step: ステップ辞書

    Returns:
        (ステップ種別, パラメータ) のタプル

    Raises:
        ValueError: 空のステップ辞書の場合
    """
    if not step:
        raise ValueError("空のステップ辞書です")

    # 最初のキーをステップ種別として使用
    step_type = next(iter(step))
    params = step[step_type]
    return step_type, params


def _sanitize_title(title: str) -> str:
    """シナリオタイトルをファイルシステム安全な文字列に変換する。

    スペースをアンダースコアに、特殊文字を除去する。

    Args:
        title: シナリオタイトル

    Returns:
        サニタイズ済み文字列
    """
    import re
    # 英数字、日本語文字、アンダースコア、ハイフン以外を除去
    sanitized = re.sub(r"[^\w\-]", "_", title)
    return sanitized.strip("_")[:100]  # 最大100文字
