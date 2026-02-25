"""
統合テスト — 全コンポーネントの結合テスト

CLI → DSL Parser → Runner → StepRegistry → ArtifactsManager → Reporter の
パイプライン全体を通した統合テストを実施する。
実際のブラウザは起動せず、モック/スタブで各コンポーネント間の連携を検証する。

テスト対象フロー:
  1. import パイプライン統合（PyAstParser → Mapper → Heuristics → DslParser）
  2. validate + lint パイプライン統合
  3. AI Authoring パイプライン統合（AiDrafter / AiRefiner / AiExplainer）
  4. Reporter 統合（JSON / HTML / JUnit XML）
  5. ArtifactsManager 統合
  6. StepRegistry 統合
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from brt.ai import AiDrafter, AiExplainer, AiRefiner
from brt.cli import app
from brt.core.artifacts import ArtifactsManager
from brt.core.reporting import Reporter
from brt.core.runner import ScenarioResult, StepResult
from brt.dsl.linter import DslLinter
from brt.dsl.parser import DslParser
from brt.dsl.schema import ArtifactsConfig, Scenario
from brt.importer import Heuristics, Mapper, PyAstParser
from brt.steps import create_full_registry

cli_runner = CliRunner()


# ---------------------------------------------------------------------------
# サンプルデータ定義
# ---------------------------------------------------------------------------

# examples/flows/ ディレクトリのパス
_EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples" / "flows"

# Playwright codegen 風の Python ソース
_PY_CODEGEN_SOURCE = """\
page.goto("http://localhost:3000/login")
page.get_by_role("textbox", name="Email").fill("user@example.com")
page.get_by_role("textbox", name="Password").fill("secret123")
page.get_by_role("button", name="Submit").click()
"""

# 有効な最小 YAML
_VALID_YAML = """\
title: 統合テスト用シナリオ
baseUrl: http://localhost:3000
steps:
  - goto: http://localhost:3000/
healing: off
"""

# 無効な YAML（title が数値）
_INVALID_YAML = """\
title: 123
steps: "not a list"
"""


# ===========================================================================
# フロー1: import パイプライン統合
# ===========================================================================

class TestImportPipeline:
    """PyAstParser → Mapper → Heuristics → DslParser の統合テスト。"""

    def test_python_to_yaml_roundtrip(self, tmp_path: Path) -> None:
        """Python ソースを変換し、YAML に書き出し → 再読み込みで Scenario が有効。"""
        # 1. PyAstParser で Python ソースを解析
        parser = PyAstParser()
        raw_actions = parser.parse(_PY_CODEGEN_SOURCE)
        assert len(raw_actions) > 0, "RawAction が生成されること"

        # 2. Mapper で DSL ステップに変換
        mapper = Mapper()
        steps = mapper.map(raw_actions)
        assert len(steps) > 0, "DSL ステップが生成されること"

        # 3. Heuristics で後処理（名前付与、secret 検出）
        heuristics = Heuristics(with_expects=False)
        steps = heuristics.apply(steps)

        # 4. Scenario を構築して YAML に書き出し
        scenario = Scenario(
            title="インポートテスト",
            baseUrl="http://localhost:3000",
            steps=steps,
        )
        dsl_parser = DslParser()
        yaml_path = tmp_path / "imported.yaml"
        dsl_parser.dump(scenario, yaml_path)
        assert yaml_path.exists(), "YAML ファイルが生成されること"

        # 5. 再読み込みして Scenario が有効であることを確認
        reloaded = dsl_parser.load(yaml_path)
        assert isinstance(reloaded, Scenario)
        assert reloaded.title == "インポートテスト"
        assert len(reloaded.steps) > 0

    def test_import_with_expects_option(self, tmp_path: Path) -> None:
        """--with-expects オプション付きで expect ステップが挿入される。"""
        parser = PyAstParser()
        raw_actions = parser.parse(_PY_CODEGEN_SOURCE)

        mapper = Mapper()
        steps = mapper.map(raw_actions)

        # with_expects=True で expect 補助挿入
        heuristics = Heuristics(with_expects=True)
        steps_with_expects = heuristics.apply(steps)

        # expect 系ステップが挿入されていることを確認
        original_count = len(mapper.map(raw_actions))
        assert len(steps_with_expects) >= original_count

    def test_import_flow_cli_e2e(self, tmp_path: Path) -> None:
        """import-flow CLI コマンドのエンドツーエンドテスト。"""
        # Python ソースファイルを作成
        py_file = tmp_path / "recording.py"
        py_file.write_text(_PY_CODEGEN_SOURCE, encoding="utf-8")
        output_file = tmp_path / "output.yaml"

        # CLI 実行
        result = cli_runner.invoke(app, [
            "import-flow", str(py_file),
            "-o", str(output_file),
        ])
        assert result.exit_code == 0, f"CLI 失敗: {result.output}"
        assert output_file.exists(), "出力 YAML が生成されること"

        # 生成された YAML を DslParser で読み込み
        dsl_parser = DslParser()
        scenario = dsl_parser.load(output_file)
        assert isinstance(scenario, Scenario)
        assert len(scenario.steps) > 0

    def test_secret_detection_in_pipeline(self, tmp_path: Path) -> None:
        """パスワードフィールドの secret 自動検出が機能する。"""
        # パスワード入力を含む Python ソース
        py_source = """\
page.goto("http://localhost:3000/login")
page.get_by_label("Password").fill("my-secret-pass")
"""
        parser = PyAstParser()
        raw_actions = parser.parse(py_source)

        mapper = Mapper()
        steps = mapper.map(raw_actions)

        heuristics = Heuristics()
        steps = heuristics.apply(steps)

        # fill ステップに secret: true が付与されていることを確認
        fill_steps = [s for s in steps if "fill" in s]
        assert len(fill_steps) > 0
        has_secret = any(
            s["fill"].get("secret") is True for s in fill_steps
        )
        assert has_secret, "パスワードフィールドに secret: true が付与されること"


# ===========================================================================
# フロー2: validate + lint パイプライン統合
# ===========================================================================

class TestValidateLintPipeline:
    """validate → lint の順に実行し、結果が一貫していることを確認。"""

    def test_valid_yaml_validate_and_lint(self, tmp_path: Path) -> None:
        """有効な YAML: validate OK + lint 問題なし。"""
        yaml_file = tmp_path / "valid.yaml"
        yaml_file.write_text(_VALID_YAML, encoding="utf-8")

        # validate
        dsl_parser = DslParser()
        errors = dsl_parser.validate(yaml_file)
        assert len(errors) == 0, f"バリデーションエラー: {errors}"

        # lint
        scenario = dsl_parser.load(yaml_file)
        linter = DslLinter()
        issues = linter.lint(scenario)
        # 最小構成なので重大な問題はないはず
        error_issues = [i for i in issues if i.severity.value == "error"]
        assert len(error_issues) == 0, f"lint エラー: {error_issues}"

    def test_invalid_yaml_validate_error(self, tmp_path: Path) -> None:
        """無効な YAML: validate でエラーが検出される。"""
        yaml_file = tmp_path / "invalid.yaml"
        yaml_file.write_text(_INVALID_YAML, encoding="utf-8")

        dsl_parser = DslParser()
        errors = dsl_parser.validate(yaml_file)
        assert len(errors) > 0, "バリデーションエラーが検出されること"

    def test_validate_then_lint_consistency(self, tmp_path: Path) -> None:
        """validate OK の YAML は lint でもエラーにならない。"""
        yaml_content = """\
title: 一貫性テスト
baseUrl: http://localhost:3000
steps:
  - goto: http://localhost:3000/
  - click:
      by:
        testId: submit-btn
      name: 送信ボタンクリック
healing: off
"""
        yaml_file = tmp_path / "consistent.yaml"
        yaml_file.write_text(yaml_content, encoding="utf-8")

        dsl_parser = DslParser()
        errors = dsl_parser.validate(yaml_file)
        assert len(errors) == 0

        scenario = dsl_parser.load(yaml_file)
        linter = DslLinter()
        issues = linter.lint(scenario)
        error_issues = [i for i in issues if i.severity.value == "error"]
        assert len(error_issues) == 0


# ===========================================================================
# フロー3: AI Authoring パイプライン統合
# ===========================================================================

class TestAiAuthoringPipeline:
    """AiDrafter / AiRefiner / AiExplainer の統合テスト。"""

    def test_drafter_dump_load_roundtrip(self, tmp_path: Path) -> None:
        """AiDrafter.draft() → DslParser.dump() → DslParser.load() のラウンドトリップ。"""
        drafter = AiDrafter()
        scenario = drafter.draft("ログインフローをテストする")
        assert isinstance(scenario, Scenario)

        # YAML に書き出し → 再読み込み
        dsl_parser = DslParser()
        yaml_path = tmp_path / "drafted.yaml"
        dsl_parser.dump(scenario, yaml_path)

        reloaded = dsl_parser.load(yaml_path)
        assert reloaded.title == scenario.title
        assert reloaded.baseUrl == scenario.baseUrl
        assert len(reloaded.steps) == len(scenario.steps)

    def test_drafter_lint_no_errors(self) -> None:
        """AiDrafter.draft() → DslLinter.lint() で lint エラーがないことを確認。"""
        drafter = AiDrafter()
        scenario = drafter.draft("ダッシュボード表示テスト")

        linter = DslLinter()
        issues = linter.lint(scenario)
        error_issues = [i for i in issues if i.severity.value == "error"]
        assert len(error_issues) == 0, f"lint エラー: {error_issues}"

    def test_refiner_dump_load_roundtrip(self, tmp_path: Path) -> None:
        """AiRefiner.refine() → DslParser.dump() → DslParser.load() のラウンドトリップ。"""
        # 元の Scenario を作成
        original = Scenario(
            title="リファインテスト",
            baseUrl="http://localhost:3000",
            steps=[
                {"goto": "http://localhost:3000/"},
                {"click": {"by": {"testId": "btn"}, "name": "ボタンクリック"}},
            ],
        )

        refiner = AiRefiner()
        refined = refiner.refine(original)
        assert isinstance(refined, Scenario)

        # YAML に書き出し → 再読み込み
        dsl_parser = DslParser()
        yaml_path = tmp_path / "refined.yaml"
        dsl_parser.dump(refined, yaml_path)

        reloaded = dsl_parser.load(yaml_path)
        assert reloaded.title == refined.title

    def test_explainer_returns_nonempty_string(self) -> None:
        """AiExplainer.explain() が空でない文字列を返すことを確認。"""
        scenario = Scenario(
            title="説明テスト用シナリオ",
            baseUrl="http://localhost:3000",
            steps=[
                {"goto": "http://localhost:3000/login"},
                {"fill": {"by": {"css": "#email"}, "value": "test@example.com"}},
            ],
        )

        explainer = AiExplainer()
        explanation = explainer.explain(scenario)
        assert isinstance(explanation, str)
        assert len(explanation.strip()) > 0, "説明テキストが空でないこと"


# ===========================================================================
# フロー4: Reporter 統合
# ===========================================================================

class TestReporterIntegration:
    """ScenarioResult → Reporter の全形式出力テスト。"""

    @pytest.fixture()
    def scenario_result(self) -> ScenarioResult:
        """テスト用の ScenarioResult を生成する。"""
        return ScenarioResult(
            scenario_title="統合テストシナリオ",
            status="passed",
            steps=[
                StepResult(
                    step_name="goto-login",
                    step_type="goto",
                    step_index=0,
                    status="passed",
                    duration_ms=150.0,
                ),
                StepResult(
                    step_name="fill-email",
                    step_type="fill",
                    step_index=1,
                    status="passed",
                    duration_ms=80.0,
                ),
                StepResult(
                    step_name="click-submit",
                    step_type="click",
                    step_index=2,
                    status="failed",
                    duration_ms=200.0,
                    error="要素が見つかりません: #submit-btn",
                ),
            ],
            duration_ms=430.0,
            started_at=datetime(2024, 6, 15, 10, 0, 0),
            finished_at=datetime(2024, 6, 15, 10, 0, 1),
        )

    def test_all_report_formats_generated(
        self, tmp_path: Path, scenario_result: ScenarioResult,
    ) -> None:
        """JSON / HTML / JUnit XML の全形式が生成されることを確認。"""
        reporter = Reporter()

        # JSON レポート
        json_path = reporter.generate_json(scenario_result, tmp_path)
        assert json_path.exists(), "report.json が生成されること"
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["title"] == "統合テストシナリオ"
        assert data["summary"]["total"] == 3
        assert data["summary"]["passed"] == 2
        assert data["summary"]["failed"] == 1

        # HTML レポート
        html_path = reporter.generate_html(scenario_result, tmp_path)
        assert html_path.exists(), "report.html が生成されること"
        html_content = html_path.read_text(encoding="utf-8")
        assert "統合テストシナリオ" in html_content

        # JUnit XML レポート
        xml_path = reporter.generate_junit_xml(scenario_result, tmp_path)
        assert xml_path.exists(), "junit.xml が生成されること"
        tree = ET.parse(xml_path)
        root = tree.getroot()
        assert root.tag == "testsuites"
        testsuite = root.find("testsuite")
        assert testsuite is not None
        assert testsuite.get("name") == "統合テストシナリオ"
        assert testsuite.get("tests") == "3"
        assert testsuite.get("failures") == "1"


# ===========================================================================
# フロー5: ArtifactsManager 統合
# ===========================================================================

class TestArtifactsManagerIntegration:
    """ArtifactsManager の統合テスト。"""

    def test_create_run_dir_and_save_artifacts(self, tmp_path: Path) -> None:
        """create_run_dir → save_flow_copy → save_env_info が正しく動作する。"""
        config = ArtifactsConfig()
        manager = ArtifactsManager(config=config, base_dir=tmp_path)

        # 1. run_dir 作成
        run_dir = manager.create_run_dir()
        assert run_dir.exists(), "run_dir が作成されること"
        assert (run_dir / "screenshots").exists()
        assert (run_dir / "trace").exists()
        assert (run_dir / "video").exists()
        assert (run_dir / "logs").exists()

        # 2. flow.yaml 保存
        scenario = Scenario(
            title="成果物テスト",
            baseUrl="http://localhost:3000",
            vars={"email": "test@example.com", "password": "secret123"},
            steps=[
                {"goto": "http://localhost:3000/"},
                {
                    "fill": {
                        "by": {"css": "#password"},
                        "value": "secret123",
                        "name": "fill-password",
                        "secret": True,
                    },
                },
            ],
        )
        flow_path = manager.save_flow_copy(scenario)
        assert flow_path.exists(), "flow.yaml が保存されること"
        assert flow_path.name == "flow.yaml"

        # 3. env.json 保存（secret マスク付き）
        env_path = manager.save_env_info(scenario)
        assert env_path.exists(), "env.json が保存されること"
        env_data = json.loads(env_path.read_text(encoding="utf-8"))
        assert env_data["title"] == "成果物テスト"
        # secret 値がマスクされていること
        assert env_data["vars"]["password"] == "***"
        # 非 secret 値はそのまま
        assert env_data["vars"]["email"] == "test@example.com"


# ===========================================================================
# フロー6: StepRegistry 統合
# ===========================================================================

class TestStepRegistryIntegration:
    """create_full_registry() の統合テスト。"""

    def test_full_registry_has_all_steps(self) -> None:
        """create_full_registry() で全ステップが登録されていることを確認。"""
        registry = create_full_registry()
        all_steps = registry.list_all()
        assert len(all_steps) > 0, "ステップが登録されていること"

        # 標準ステップの存在確認
        step_names = [s.name for s in all_steps]
        standard_steps = [
            "click", "fill", "press", "check", "uncheck",
            "expectVisible", "expectHidden", "expectText", "expectUrl",
            "waitFor", "waitForVisible", "waitForHidden",
        ]
        for name in standard_steps:
            assert name in step_names, f"標準ステップ '{name}' が登録されていること"

        # 高レベルステップの存在確認
        high_level_steps = [
            "selectOverlayOption",
            "selectWijmoCombo",
            "clickWijmoGridCell",
            "setDatePicker",
            "uploadFile",
        ]
        for name in high_level_steps:
            assert name in step_names, f"高レベルステップ '{name}' が登録されていること"

    def test_full_registry_step_count(self) -> None:
        """標準ステップ + 高レベルステップの合計数を検証。"""
        registry = create_full_registry()
        all_steps = registry.list_all()
        # 標準ステップ + 高レベルステップで少なくとも 17 以上
        assert len(all_steps) >= 17, (
            f"ステップ合計数が不足: {len(all_steps)} (期待: >= 17)"
        )

    def test_registry_get_returns_handler(self) -> None:
        """registry.get() で取得したハンドラが StepHandler Protocol を満たす。"""
        registry = create_full_registry()
        handler = registry.get("click")
        # execute と get_schema メソッドを持つこと
        assert hasattr(handler, "execute")
        assert hasattr(handler, "get_schema")


# ===========================================================================
# サンプル YAML フロー読み込みテスト
# ===========================================================================

class TestSampleFlowsLoading:
    """examples/flows/ のサンプル YAML が DslParser.load() で正常に読み込めることを検証。"""

    def test_login_flow_loads(self) -> None:
        """login_flow.yaml が正常に読み込めること。"""
        yaml_path = _EXAMPLES_DIR / "login_flow.yaml"
        assert yaml_path.exists(), f"サンプルファイルが存在すること: {yaml_path}"

        dsl_parser = DslParser()
        scenario = dsl_parser.load(yaml_path)
        assert isinstance(scenario, Scenario)
        assert scenario.title == "ログインフローテスト"
        assert scenario.baseUrl == "http://localhost:3000"
        assert len(scenario.steps) == 6

    def test_wijmo_grid_flow_loads(self) -> None:
        """wijmo_grid_flow.yaml が正常に読み込めること。"""
        yaml_path = _EXAMPLES_DIR / "wijmo_grid_flow.yaml"
        assert yaml_path.exists(), f"サンプルファイルが存在すること: {yaml_path}"

        dsl_parser = DslParser()
        scenario = dsl_parser.load(yaml_path)
        assert isinstance(scenario, Scenario)
        assert scenario.title == "Wijmo Grid 操作テスト"
        assert len(scenario.steps) == 4

    def test_overlay_flow_loads(self) -> None:
        """overlay_flow.yaml が正常に読み込めること。"""
        yaml_path = _EXAMPLES_DIR / "overlay_flow.yaml"
        assert yaml_path.exists(), f"サンプルファイルが存在すること: {yaml_path}"

        dsl_parser = DslParser()
        scenario = dsl_parser.load(yaml_path)
        assert isinstance(scenario, Scenario)
        assert scenario.title == "オーバーレイ選択テスト"
        assert len(scenario.steps) == 6

    def test_all_sample_flows_validate(self) -> None:
        """全サンプル YAML が validate でエラーなしであること。"""
        dsl_parser = DslParser()
        flow_files = list(_EXAMPLES_DIR.glob("*.yaml"))
        assert len(flow_files) >= 3, "サンプルファイルが3つ以上存在すること"

        for yaml_path in flow_files:
            errors = dsl_parser.validate(yaml_path)
            assert len(errors) == 0, (
                f"{yaml_path.name} のバリデーションエラー: {errors}"
            )
