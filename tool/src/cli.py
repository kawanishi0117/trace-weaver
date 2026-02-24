"""
CLI エントリポイント — Typer ベースのコマンドラインインターフェース

brt コマンドとして以下のサブコマンドを提供する:
  - init: プロジェクト雛形生成
  - record: Playwright codegen 起動
  - import-flow: Python → YAML DSL 変換
  - run: シナリオ実行
  - validate: スキーマ検証
  - lint: 静的解析
  - report: HTML レポート再生成
  - list-steps: 全ステップ一覧
  - ai draft / ai refine / ai explain: AI Authoring サブコマンド
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import typer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Typer アプリ定義
# ---------------------------------------------------------------------------

app = typer.Typer(
    help=(
        "brt — ブラウザ操作 Record/Replay テストツール\n\n"
        "基本の流れ:\n"
        "  1. brt record          操作を記録（Chrome が開きます）\n"
        "  2. brt run flows/xxx.yaml  記録した操作を再実行\n\n"
        "詳しくは各コマンドに --help を付けてください。"
    ),
    no_args_is_help=True,
)

ai_app = typer.Typer(
    help="AI Authoring サブコマンド",
    no_args_is_help=True,
)
app.add_typer(ai_app, name="ai")


# ---------------------------------------------------------------------------
# init コマンド
# ---------------------------------------------------------------------------

@app.command()
def init(
    project_dir: Path = typer.Argument(
        Path("."), help="プロジェクトディレクトリ（デフォルト: カレント）",
    ),
) -> None:
    """プロジェクト雛形（ディレクトリ構造と設定テンプレート）を生成する。"""
    try:
        # ディレクトリ構造を作成
        dirs = ["flows", "recordings", "artifacts"]
        for d in dirs:
            (project_dir / d).mkdir(parents=True, exist_ok=True)

        # 設定ファイルテンプレートを生成
        config_path = project_dir / "brt.yaml"
        if not config_path.exists():
            config_path.write_text(
                "# brt プロジェクト設定\n"
                "# 詳細は README を参照してください\n"
                "default_base_url: http://localhost:3000\n"
                "artifacts_dir: artifacts\n",
                encoding="utf-8",
            )

        typer.echo(f"プロジェクトを初期化しました: {project_dir.resolve()}")
    except Exception as exc:
        typer.echo(f"エラー: {exc}", err=True)
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# record コマンド
# ---------------------------------------------------------------------------

@app.command()
def record(
    url: Optional[str] = typer.Argument(
        None, help="記録対象の URL（省略時は対話入力）",
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="出力先ファイルパス（.py / .yaml 指定可）",
    ),
    channel: str = typer.Option(
        "chrome", "--channel", "-c",
        help="ブラウザチャンネル (chrome / chromium / msedge)",
    ),
    viewport: str = typer.Option(
        "1280,720", "--viewport", help="ビューポートサイズ (幅,高さ)",
    ),
    no_import: bool = typer.Option(
        False, "--no-import", help="記録のみ行い、YAML 変換をスキップする",
    ),
    with_expects: bool = typer.Option(
        False, "--with-expects", help="変換時に expectVisible を自動挿入する",
    ),
    no_highlight: bool = typer.Option(
        False, "--no-highlight",
        help="ハイライト枠なしで記録する（自前レコーダー使用）",
    ),
) -> None:
    """ブラウザ操作を記録し、YAML DSL に自動変換する。

    URL を省略すると対話的に入力を求めます。
    デフォルトでは Chrome を使用し、記録後に自動で YAML 変換まで行います。
    --no-import を指定すると Python スクリプトのみ出力します。
    --no-highlight を指定すると、赤いハイライト枠なしで記録します。
    """
    # URL が未指定の場合は対話的に入力を求める
    if url is None:
        url = typer.prompt("記録する URL を入力してください")

    import subprocess

    # 使用ブラウザを表示
    browser_name = {"chrome": "Google Chrome", "chromium": "Chromium", "msedge": "Microsoft Edge"}
    typer.echo(f"ブラウザ: {browser_name.get(channel, channel)}")
    typer.echo(f"URL: {url}")
    typer.echo("ブラウザを閉じると記録が終了します。\n")

    # ビューポートサイズをパース
    vp_parts = viewport.split(",")
    vp_width = int(vp_parts[0])
    vp_height = int(vp_parts[1]) if len(vp_parts) > 1 else 720

    # 出力先の決定: .yaml 指定時は .py を中間ファイルとして扱う
    if output is not None:
        if output.suffix in (".yaml", ".yml"):
            yaml_output = output
            py_output = output.with_suffix(".py")
        else:
            py_output = output
            yaml_output = output.with_suffix(".yaml")
    else:
        py_output = Path("recordings") / "raw_recording.py"
        yaml_output = Path("flows") / "recording.yaml"

    py_output.parent.mkdir(parents=True, exist_ok=True)

    if no_highlight:
        # 自前レコーダー: ハイライト枠なしで記録
        _record_no_highlight(
            url, py_output, channel, (vp_width, vp_height),
        )
    else:
        # Playwright codegen を使用（従来動作）
        cmd = [
            "playwright", "codegen",
            "--target", "python",
            f"--viewport-size={viewport}",
        ]

        # chrome / msedge を指定した場合はチャンネルオプションを付与
        if channel != "chromium":
            cmd.extend(["--channel", channel])

        cmd.extend(["--output", str(py_output)])
        cmd.append(url)

        result = subprocess.run(cmd)
        if result.returncode != 0:
            raise typer.Exit(code=result.returncode)

    # 記録ファイルが存在しない場合は終了
    if not py_output.exists():
        typer.echo("記録がキャンセルされました。")
        raise typer.Exit(code=0)

    typer.echo(f"記録完了: {py_output}")

    # --no-import が指定されていなければ自動で YAML 変換
    if not no_import:
        _auto_import_flow(py_output, yaml_output, with_expects)


# ---------------------------------------------------------------------------
# import-flow コマンド
# ---------------------------------------------------------------------------

@app.command("import-flow")
def import_flow(
    python_file: Path = typer.Argument(..., help="変換元の Python ファイル"),
    output: Path = typer.Option(
        ..., "--output", "-o", help="出力先 YAML ファイル",
    ),
    with_expects: bool = typer.Option(
        False, "--with-expects", help="expect 文も変換に含める",
    ),
) -> None:
    """Playwright codegen 出力の Python ファイルを YAML DSL に変換する。"""
    from .dsl.parser import DslParser
    from .importer import Heuristics, Mapper, PyAstParser

    try:
        # Python ファイルを読み込み
        source = python_file.read_text(encoding="utf-8")

        # パイプライン: PyAstParser → Mapper → Heuristics
        parser = PyAstParser()
        raw_actions = parser.parse(source)

        mapper = Mapper()
        steps = mapper.map(raw_actions)

        heuristics = Heuristics(with_expects=with_expects)
        steps = heuristics.apply(steps)

        # Scenario を構築して YAML に書き出し
        scenario_dict = {
            "title": f"Imported from {python_file.name}",
            "baseUrl": _extract_base_url(steps),
            "steps": steps,
        }

        from .dsl.schema import Scenario

        scenario = Scenario(**scenario_dict)
        dsl_parser = DslParser()
        dsl_parser.dump(scenario, output)

        typer.echo(f"変換完了: {output}")
    except Exception as exc:
        typer.echo(f"エラー: {exc}", err=True)
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# run コマンド
# ---------------------------------------------------------------------------

@app.command()
def run(
    yaml_file: Path = typer.Argument(..., help="実行する YAML DSL ファイル"),
    headed: bool = typer.Option(True, "--headed/--headless", help="ブラウザ表示モード（デフォルト: 表示）"),
    workers: int = typer.Option(1, "--workers", "-w", help="並列実行ワーカー数"),
    slow_mo: int = typer.Option(0, "--slow-mo", help="各操作間の遅延（ミリ秒）。iframe 等のタイミング問題を緩和"),
    step_timeout: int = typer.Option(30000, "--step-timeout", help="各ステップのタイムアウト（ミリ秒）。0 で無制限"),
) -> None:
    """YAML DSL シナリオを実行する。デフォルトでブラウザを表示します。"""
    import asyncio

    from .core.runner import Runner, RunnerConfig
    from .dsl.parser import DslParser
    from .steps import create_full_registry

    try:
        # YAML ファイルを読み込み
        parser = DslParser()
        scenario = parser.load(yaml_file)

        # Runner 設定
        config = RunnerConfig(
            headed=headed,
            workers=workers,
            slow_mo=slow_mo,
            step_timeout=step_timeout,
        )

        # レジストリを生成して Runner を初期化
        registry = create_full_registry()
        runner = Runner(registry)

        # シナリオを実行
        result = asyncio.run(runner.run(scenario, config))

        # 結果を表示
        typer.echo(f"シナリオ: {result.scenario_title}")
        typer.echo(f"ステータス: {result.status}")
        typer.echo(f"実行時間: {result.duration_ms:.0f}ms")
        typer.echo(
            f"ステップ: {len(result.steps)} "
            f"(passed={sum(1 for s in result.steps if s.status == 'passed')}, "
            f"failed={sum(1 for s in result.steps if s.status == 'failed')})"
        )

        # スクリーンショット保存先を表示
        if result.artifacts_dir:
            typer.echo(f"成果物: {result.artifacts_dir}")
            ss_dir = result.artifacts_dir / "screenshots"
            if ss_dir.exists():
                ss_files = list(ss_dir.iterdir())
                if ss_files:
                    typer.echo(f"  スクリーンショット: {len(ss_files)} 枚")
            # HTML レポートがあれば表示
            html_report = result.artifacts_dir / "report.html"
            if html_report.exists():
                typer.echo(f"  レポート: {html_report}")

        if result.status == "failed":
            raise typer.Exit(code=1)
    except typer.Exit:
        raise
    except Exception as exc:
        typer.echo(f"エラー: {exc}", err=True)
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# validate コマンド
# ---------------------------------------------------------------------------

@app.command()
def validate(
    yaml_file: Path = typer.Argument(..., help="検証する YAML DSL ファイル"),
) -> None:
    """YAML DSL ファイルのスキーマ検証を行う。"""
    from .dsl.parser import DslParser

    parser = DslParser()
    errors = parser.validate(yaml_file)

    if not errors:
        typer.echo(f"✓ {yaml_file}: スキーマ検証 OK")
    else:
        for err in errors:
            line_info = f" (行 {err.line})" if err.line else ""
            typer.echo(
                f"✗ {err.location}{line_info}: {err.message}",
                err=True,
            )
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# lint コマンド
# ---------------------------------------------------------------------------

@app.command()
def lint(
    yaml_file: Path = typer.Argument(..., help="静的解析する YAML DSL ファイル"),
) -> None:
    """YAML DSL ファイルの静的解析（Lint）を実行する。"""
    from .dsl.linter import DslLinter
    from .dsl.parser import DslParser

    try:
        # YAML を読み込み
        parser = DslParser()
        scenario = parser.load(yaml_file)

        # Lint 実行
        linter = DslLinter()
        issues = linter.lint(scenario)

        if not issues:
            typer.echo(f"✓ {yaml_file}: lint 問題なし")
        else:
            for issue in issues:
                typer.echo(
                    f"[{issue.severity.value}] "
                    f"行 {issue.line_number} ({issue.step_name}): "
                    f"{issue.message}"
                )
            # warning/error がある場合は終了コード 1
            has_errors = any(
                i.severity.value in ("error", "warning") for i in issues
            )
            if has_errors:
                raise typer.Exit(code=1)
    except typer.Exit:
        raise
    except Exception as exc:
        typer.echo(f"エラー: {exc}", err=True)
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# report コマンド
# ---------------------------------------------------------------------------

@app.command()
def report(
    artifacts_dir: Path = typer.Argument(..., help="成果物ディレクトリ"),
) -> None:
    """既存の report.json から HTML レポートを再生成する。"""
    import json

    from .core.reporting import Reporter
    from .core.runner import ScenarioResult, StepResult

    try:
        report_json_path = artifacts_dir / "report.json"
        if not report_json_path.exists():
            typer.echo(
                f"エラー: {report_json_path} が見つかりません", err=True,
            )
            raise typer.Exit(code=1)

        # report.json を読み込み
        with open(report_json_path, "r", encoding="utf-8") as f:
            report_data = json.load(f)

        # ScenarioResult を再構築
        steps = [
            StepResult(
                step_name=s.get("step_name", ""),
                step_type=s.get("step_type", ""),
                step_index=s.get("step_index", 0),
                status=s.get("status", "passed"),
                duration_ms=s.get("duration_ms", 0.0),
                error=s.get("error"),
                section=s.get("section"),
            )
            for s in report_data.get("steps", [])
        ]

        result = ScenarioResult(
            scenario_title=report_data.get("title", ""),
            status=report_data.get("status", "passed"),
            steps=steps,
            duration_ms=report_data.get("duration_ms", 0.0),
            artifacts_dir=artifacts_dir,
        )

        # HTML レポートを生成
        reporter = Reporter()
        html_path = reporter.generate_html(result, artifacts_dir)
        typer.echo(f"HTML レポートを生成しました: {html_path}")
    except typer.Exit:
        raise
    except Exception as exc:
        typer.echo(f"エラー: {exc}", err=True)
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# list-steps コマンド
# ---------------------------------------------------------------------------

@app.command("list-steps")
def list_steps() -> None:
    """登録済み全ステップの一覧を表示する。"""
    from .steps import create_full_registry

    registry = create_full_registry()
    all_steps = registry.list_all()

    # カテゴリごとにグループ化して表示
    categories: dict[str, list] = {}
    for info in all_steps:
        categories.setdefault(info.category, []).append(info)

    for category, steps in sorted(categories.items()):
        typer.echo(f"\n[{category}]")
        for step in steps:
            typer.echo(f"  {step.name:30s} {step.description}")

    typer.echo(f"\n合計: {len(all_steps)} ステップ")


# ---------------------------------------------------------------------------
# AI サブコマンド: draft
# ---------------------------------------------------------------------------

@ai_app.command("draft")
def ai_draft(
    spec: str = typer.Argument(..., help="仕様テキストまたはファイルパス"),
    output: Path = typer.Option(
        ..., "--output", "-o", help="出力先 YAML ファイル",
    ),
) -> None:
    """自然言語仕様から YAML DSL シナリオのドラフトを生成する。"""
    from .ai import AiDrafter
    from .dsl.parser import DslParser

    try:
        # ファイルパスの場合はファイルから読み込み
        spec_path = Path(spec)
        if spec_path.exists() and spec_path.is_file():
            spec_text = spec_path.read_text(encoding="utf-8")
        else:
            spec_text = spec

        # ドラフト生成
        drafter = AiDrafter()
        scenario = drafter.draft(spec_text)

        # YAML に書き出し
        dsl_parser = DslParser()
        dsl_parser.dump(scenario, output)

        typer.echo(f"ドラフトを生成しました: {output}")
    except Exception as exc:
        typer.echo(f"エラー: {exc}", err=True)
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# AI サブコマンド: refine
# ---------------------------------------------------------------------------

@ai_app.command("refine")
def ai_refine(
    yaml_file: Path = typer.Argument(..., help="改善対象の YAML DSL ファイル"),
    output: Path = typer.Option(
        ..., "--output", "-o", help="出力先 YAML ファイル",
    ),
) -> None:
    """既存の YAML DSL シナリオを AI で改善する。"""
    from .ai import AiRefiner
    from .dsl.parser import DslParser

    try:
        # YAML ファイルを読み込み
        parser = DslParser()
        scenario = parser.load(yaml_file)

        # リファイン実行
        refiner = AiRefiner()
        refined = refiner.refine(scenario)

        # 改善結果を YAML に書き出し
        parser.dump(refined, output)

        typer.echo(f"リファイン完了: {output}")
    except Exception as exc:
        typer.echo(f"エラー: {exc}", err=True)
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# AI サブコマンド: explain
# ---------------------------------------------------------------------------

@ai_app.command("explain")
def ai_explain(
    yaml_file: Path = typer.Argument(..., help="説明対象の YAML DSL ファイル"),
) -> None:
    """YAML DSL シナリオの内容を自然言語で説明する。"""
    from .ai import AiExplainer
    from .dsl.parser import DslParser

    try:
        # YAML ファイルを読み込み
        parser = DslParser()
        scenario = parser.load(yaml_file)

        # 説明生成
        explainer = AiExplainer()
        explanation = explainer.explain(scenario)

        typer.echo(explanation)
    except Exception as exc:
        typer.echo(f"エラー: {exc}", err=True)
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# ヘルパー関数
# ---------------------------------------------------------------------------

def _record_no_highlight(
    url: str,
    py_output: Path,
    channel: str,
    viewport: tuple[int, int],
) -> None:
    """ハイライト枠なしで操作を記録し、Python スクリプトに出力する。

    Playwright codegen の代わりに自前レコーダーを使用する。
    赤いハイライト枠は表示されない。

    Args:
        url: 記録開始 URL
        py_output: 出力先 Python ファイル
        channel: ブラウザチャンネル
        viewport: ビューポートサイズ (幅, 高さ)
    """
    from .recorder import BrowserRecorder, ScriptWriter

    recorder = BrowserRecorder()
    typer.echo("記録中... ブラウザを閉じると記録が終了します。")

    actions = recorder.record(
        url=url,
        channel=channel,
        viewport=viewport,
    )

    if len(actions) <= 1:
        # goto のみ（操作なし）の場合
        typer.echo("操作が記録されませんでした。")
        return

    writer = ScriptWriter()
    writer.write(actions, py_output, channel=channel, viewport=viewport)


def _auto_import_flow(
    py_file: Path,
    yaml_output: Path,
    with_expects: bool,
) -> None:
    """記録済み Python ファイルを YAML DSL に自動変換する。

    record コマンドから呼び出される内部ヘルパー。

    Args:
        py_file: 変換元の Python ファイル
        yaml_output: 出力先 YAML ファイル
        with_expects: expectVisible を自動挿入するか
    """
    from .dsl.parser import DslParser
    from .dsl.schema import Scenario
    from .importer import Heuristics, Mapper, PyAstParser

    try:
        source = py_file.read_text(encoding="utf-8")

        # パイプライン: PyAstParser → Mapper → Heuristics
        parser = PyAstParser()
        raw_actions = parser.parse(source)

        mapper = Mapper()
        steps = mapper.map(raw_actions)

        heuristics = Heuristics(with_expects=with_expects)
        steps = heuristics.apply(steps)

        # Scenario を構築して YAML に書き出し
        scenario_dict = {
            "title": f"Imported from {py_file.name}",
            "baseUrl": _extract_base_url(steps),
            "steps": steps,
        }

        scenario = Scenario(**scenario_dict)
        yaml_output.parent.mkdir(parents=True, exist_ok=True)
        dsl_parser = DslParser()
        dsl_parser.dump(scenario, yaml_output)

        typer.echo(f"YAML 変換完了: {yaml_output}")
    except Exception as exc:
        typer.echo(f"YAML 変換エラー: {exc}", err=True)
        typer.echo(
            f"Python ファイルは保存済みです: {py_file}\n"
            f"手動で変換するには: brt import-flow {py_file} -o {yaml_output}",
            err=True,
        )


def _extract_base_url(steps: list[dict]) -> str:
    """ステップリストから baseUrl を推定する。

    最初の goto ステップの URL からベース URL を抽出する。
    見つからない場合はデフォルト値を返す。

    Args:
        steps: ステップ辞書のリスト

    Returns:
        推定された baseUrl
    """
    from urllib.parse import urlparse

    for step in steps:
        if "goto" in step:
            goto_val = step["goto"]
            # goto が dict 形式（{url: ..., name: ...}）の場合
            if isinstance(goto_val, dict):
                url = goto_val.get("url", "")
            else:
                url = str(goto_val)
            if url:
                parsed = urlparse(url)
                return f"{parsed.scheme}://{parsed.netloc}"
    return "http://localhost:3000"
