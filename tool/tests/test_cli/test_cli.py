"""
CLI テスト — typer.testing.CliRunner を使用した CLI コマンドのテスト

実際のブラウザ起動や LLM 呼び出しは行わず、モック/スタブで代替する。
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# ヘルパー: サンプル YAML コンテンツ
# ---------------------------------------------------------------------------

VALID_YAML = """\
title: テストシナリオ
baseUrl: http://localhost:3000
steps:
  - goto: http://localhost:3000/
healing: off
"""

INVALID_YAML = """\
title: 123
steps: "not a list"
"""

MALFORMED_YAML = """\
title: テスト
  invalid_indent: true
"""


# ===========================================================================
# 1. init コマンド
# ===========================================================================

class TestInitCommand:
    """init コマンドのテスト。"""

    def test_init_creates_directories(self, tmp_path: Path) -> None:
        """ディレクトリ構造（flows/, recordings/, artifacts/）が生成される。"""
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 0
        assert (tmp_path / "flows").is_dir()
        assert (tmp_path / "recordings").is_dir()
        assert (tmp_path / "artifacts").is_dir()

    def test_init_creates_config_template(self, tmp_path: Path) -> None:
        """設定ファイルテンプレート（brt.yaml）が生成される。"""
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 0
        config_path = tmp_path / "brt.yaml"
        assert config_path.exists()
        content = config_path.read_text(encoding="utf-8")
        assert "default_base_url" in content

    def test_init_does_not_overwrite_existing_config(self, tmp_path: Path) -> None:
        """既存の brt.yaml を上書きしない。"""
        config_path = tmp_path / "brt.yaml"
        config_path.write_text("custom: true", encoding="utf-8")

        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 0
        assert config_path.read_text(encoding="utf-8") == "custom: true"

    def test_init_default_current_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """引数なしでカレントディレクトリに初期化する。"""
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 0
        assert (tmp_path / "flows").is_dir()

    def test_init_output_message(self, tmp_path: Path) -> None:
        """初期化完了メッセージが出力される。"""
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 0
        assert "プロジェクトを初期化しました" in result.output


# ===========================================================================
# 2. validate コマンド
# ===========================================================================

class TestValidateCommand:
    """validate コマンドのテスト。"""

    def test_validate_valid_yaml(self, tmp_path: Path) -> None:
        """有効な YAML で成功（終了コード 0）。"""
        yaml_file = tmp_path / "valid.yaml"
        yaml_file.write_text(VALID_YAML, encoding="utf-8")

        result = runner.invoke(app, ["validate", str(yaml_file)])
        assert result.exit_code == 0
        assert "スキーマ検証 OK" in result.output

    def test_validate_invalid_yaml_schema(self, tmp_path: Path) -> None:
        """スキーマ違反の YAML で失敗（終了コード 1）。"""
        yaml_file = tmp_path / "invalid.yaml"
        yaml_file.write_text(INVALID_YAML, encoding="utf-8")

        result = runner.invoke(app, ["validate", str(yaml_file)])
        assert result.exit_code == 1

    def test_validate_nonexistent_file(self, tmp_path: Path) -> None:
        """存在しないファイルで失敗（終了コード 1）。"""
        result = runner.invoke(app, ["validate", str(tmp_path / "missing.yaml")])
        assert result.exit_code == 1

    def test_validate_malformed_yaml(self, tmp_path: Path) -> None:
        """構文エラーの YAML で失敗（終了コード 1）。"""
        yaml_file = tmp_path / "malformed.yaml"
        yaml_file.write_text(MALFORMED_YAML, encoding="utf-8")

        result = runner.invoke(app, ["validate", str(yaml_file)])
        assert result.exit_code == 1


# ===========================================================================
# 3. lint コマンド
# ===========================================================================

class TestLintCommand:
    """lint コマンドのテスト。"""

    def test_lint_clean_yaml(self, tmp_path: Path) -> None:
        """lint 問題のない YAML で成功。"""
        yaml_content = """\
title: クリーンなシナリオ
baseUrl: http://localhost:3000
steps:
  - goto: http://localhost:3000/
healing: off
"""
        yaml_file = tmp_path / "clean.yaml"
        yaml_file.write_text(yaml_content, encoding="utf-8")

        result = runner.invoke(app, ["lint", str(yaml_file)])
        assert result.exit_code == 0
        assert "lint 問題なし" in result.output

    def test_lint_with_issues(self, tmp_path: Path) -> None:
        """lint 問題がある YAML で結果が出力される。"""
        # text セレクタ単体使用 → warning が出るはず
        yaml_content = """\
title: Lint テスト
baseUrl: http://localhost:3000
steps:
  - click:
      text: ログイン
healing: off
"""
        yaml_file = tmp_path / "lint_issues.yaml"
        yaml_file.write_text(yaml_content, encoding="utf-8")

        result = runner.invoke(app, ["lint", str(yaml_file)])
        # warning/info が出力されることを確認
        assert "warning" in result.output or "info" in result.output

    def test_lint_invalid_file(self, tmp_path: Path) -> None:
        """存在しないファイルで失敗。"""
        result = runner.invoke(app, ["lint", str(tmp_path / "missing.yaml")])
        assert result.exit_code == 1


# ===========================================================================
# 4. list-steps コマンド
# ===========================================================================

class TestListStepsCommand:
    """list-steps コマンドのテスト。"""

    def test_list_steps_output(self) -> None:
        """ステップ一覧が出力される。"""
        result = runner.invoke(app, ["list-steps"])
        assert result.exit_code == 0
        assert "合計:" in result.output

    def test_list_steps_contains_builtin(self) -> None:
        """組み込みステップ（click, fill 等）が含まれる。"""
        result = runner.invoke(app, ["list-steps"])
        assert result.exit_code == 0
        assert "click" in result.output
        assert "fill" in result.output

    def test_list_steps_contains_high_level(self) -> None:
        """高レベルステップ（selectOverlayOption 等）が含まれる。"""
        result = runner.invoke(app, ["list-steps"])
        assert result.exit_code == 0
        assert "selectOverlayOption" in result.output


# ===========================================================================
# 5. import-flow コマンド
# ===========================================================================

class TestImportFlowCommand:
    """import-flow コマンドのテスト。"""

    def test_import_flow_basic(self, tmp_path: Path) -> None:
        """Python → YAML 変換が動作する。"""
        # 最小限の Playwright codegen 出力
        py_source = """\
page.goto("http://localhost:3000/login")
page.get_by_role("textbox", name="Email").fill("test@example.com")
page.get_by_role("button", name="Submit").click()
"""
        py_file = tmp_path / "recording.py"
        py_file.write_text(py_source, encoding="utf-8")
        output_file = tmp_path / "output.yaml"

        result = runner.invoke(app, [
            "import-flow", str(py_file),
            "-o", str(output_file),
        ])
        assert result.exit_code == 0
        assert output_file.exists()
        assert "変換完了" in result.output

    def test_import_flow_nonexistent_file(self, tmp_path: Path) -> None:
        """存在しないファイルで失敗。"""
        output_file = tmp_path / "output.yaml"
        result = runner.invoke(app, [
            "import-flow", str(tmp_path / "missing.py"),
            "-o", str(output_file),
        ])
        assert result.exit_code == 1

    def test_import_flow_with_expects(self, tmp_path: Path) -> None:
        """--with-expects オプションが動作する。"""
        py_source = """\
page.goto("http://localhost:3000/")
page.get_by_role("button", name="Submit").click()
"""
        py_file = tmp_path / "recording.py"
        py_file.write_text(py_source, encoding="utf-8")
        output_file = tmp_path / "output.yaml"

        result = runner.invoke(app, [
            "import-flow", str(py_file),
            "-o", str(output_file),
            "--with-expects",
        ])
        assert result.exit_code == 0
        assert output_file.exists()


# ===========================================================================
# 6. record コマンド
# ===========================================================================

class TestRecordCommand:
    """record コマンドのテスト（subprocess をモック）。"""

    @patch("subprocess.run")
    def test_record_basic(self, mock_run: MagicMock) -> None:
        """基本的な record コマンドが subprocess を呼ぶ。"""
        mock_run.return_value = MagicMock(returncode=0)

        result = runner.invoke(app, ["record", "http://localhost:3000"])
        assert result.exit_code == 0
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "playwright" in cmd
        assert "codegen" in cmd
        assert "http://localhost:3000" in cmd

    @patch("subprocess.run")
    def test_record_with_output(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """--output オプションが subprocess に渡される。"""
        mock_run.return_value = MagicMock(returncode=0)
        output_file = tmp_path / "recordings" / "raw.py"

        result = runner.invoke(app, [
            "record", "http://localhost:3000",
            "--output", str(output_file),
        ])
        assert result.exit_code == 0
        cmd = mock_run.call_args[0][0]
        assert "--output" in cmd
        assert str(output_file) in cmd

    @patch("subprocess.run")
    def test_record_failure_propagates_exit_code(self, mock_run: MagicMock) -> None:
        """subprocess の失敗が終了コードに反映される。"""
        mock_run.return_value = MagicMock(returncode=1)

        result = runner.invoke(app, ["record", "http://localhost:3000"])
        assert result.exit_code == 1


# ===========================================================================
# 7. run コマンド
# ===========================================================================

class TestRunCommand:
    """run コマンドのテスト（Runner をモック）。"""

    def test_run_success(self, tmp_path: Path) -> None:
        """成功するシナリオ実行で終了コード 0。"""
        yaml_file = tmp_path / "scenario.yaml"
        yaml_file.write_text(VALID_YAML, encoding="utf-8")

        from src.core.runner import ScenarioResult

        mock_result = ScenarioResult(
            scenario_title="テストシナリオ",
            status="passed",
            duration_ms=100.0,
        )

        # 遅延インポート先のモジュールをモック
        with patch("src.steps.create_full_registry") as mock_registry, \
             patch("src.core.runner.Runner") as MockRunner:
            mock_runner_instance = MockRunner.return_value

            async def mock_run(*args, **kwargs):
                return mock_result

            mock_runner_instance.run = mock_run

            result = runner.invoke(app, ["run", str(yaml_file)])
            assert result.exit_code == 0
            assert "passed" in result.output

    def test_run_failure(self, tmp_path: Path) -> None:
        """失敗するシナリオ実行で終了コード 1。"""
        yaml_file = tmp_path / "scenario.yaml"
        yaml_file.write_text(VALID_YAML, encoding="utf-8")

        from src.core.runner import ScenarioResult

        mock_result = ScenarioResult(
            scenario_title="テストシナリオ",
            status="failed",
            duration_ms=100.0,
        )

        with patch("src.steps.create_full_registry") as mock_registry, \
             patch("src.core.runner.Runner") as MockRunner:
            mock_runner_instance = MockRunner.return_value

            async def mock_run(*args, **kwargs):
                return mock_result

            mock_runner_instance.run = mock_run

            result = runner.invoke(app, ["run", str(yaml_file)])
            assert result.exit_code == 1

    def test_run_nonexistent_file(self, tmp_path: Path) -> None:
        """存在しないファイルで失敗。"""
        result = runner.invoke(app, ["run", str(tmp_path / "missing.yaml")])
        assert result.exit_code == 1


# ===========================================================================
# 8. report コマンド
# ===========================================================================

class TestReportCommand:
    """report コマンドのテスト。"""

    def test_report_generates_html(self, tmp_path: Path) -> None:
        """report.json から HTML レポートが再生成される。"""
        # report.json を作成
        report_data = {
            "title": "テストシナリオ",
            "status": "passed",
            "duration_ms": 1234.5,
            "started_at": "2024-01-01T00:00:00",
            "finished_at": "2024-01-01T00:00:01",
            "steps": [
                {
                    "step_name": "goto",
                    "step_type": "goto",
                    "step_index": 0,
                    "status": "passed",
                    "duration_ms": 100.0,
                    "error": None,
                    "section": None,
                },
            ],
            "summary": {"total": 1, "passed": 1, "failed": 0, "skipped": 0},
        }
        report_json = tmp_path / "report.json"
        report_json.write_text(
            json.dumps(report_data, ensure_ascii=False), encoding="utf-8",
        )

        result = runner.invoke(app, ["report", str(tmp_path)])
        assert result.exit_code == 0
        assert "HTML レポートを生成しました" in result.output
        assert (tmp_path / "report.html").exists()

    def test_report_missing_json(self, tmp_path: Path) -> None:
        """report.json が存在しない場合に失敗。"""
        result = runner.invoke(app, ["report", str(tmp_path)])
        assert result.exit_code == 1
        assert "見つかりません" in result.output


# ===========================================================================
# 9. AI サブコマンド: draft
# ===========================================================================

class TestAiDraftCommand:
    """ai draft コマンドのテスト。"""

    def test_ai_draft_from_text(self, tmp_path: Path) -> None:
        """テキスト仕様からドラフトが生成される。"""
        output_file = tmp_path / "draft.yaml"

        result = runner.invoke(app, [
            "ai", "draft",
            "ログインページのテスト",
            "-o", str(output_file),
        ])
        assert result.exit_code == 0
        assert output_file.exists()
        assert "ドラフトを生成しました" in result.output

    def test_ai_draft_from_file(self, tmp_path: Path) -> None:
        """ファイルから仕様を読み込んでドラフトが生成される。"""
        spec_file = tmp_path / "spec.txt"
        spec_file.write_text("ログインフローのテスト仕様", encoding="utf-8")
        output_file = tmp_path / "draft.yaml"

        result = runner.invoke(app, [
            "ai", "draft",
            str(spec_file),
            "-o", str(output_file),
        ])
        assert result.exit_code == 0
        assert output_file.exists()


# ===========================================================================
# 10. AI サブコマンド: refine
# ===========================================================================

class TestAiRefineCommand:
    """ai refine コマンドのテスト。"""

    def test_ai_refine_basic(self, tmp_path: Path) -> None:
        """リファイン処理が動作する。"""
        yaml_file = tmp_path / "scenario.yaml"
        yaml_file.write_text(VALID_YAML, encoding="utf-8")
        output_file = tmp_path / "refined.yaml"

        result = runner.invoke(app, [
            "ai", "refine",
            str(yaml_file),
            "-o", str(output_file),
        ])
        assert result.exit_code == 0
        assert output_file.exists()
        assert "リファイン完了" in result.output

    def test_ai_refine_nonexistent_file(self, tmp_path: Path) -> None:
        """存在しないファイルで失敗。"""
        output_file = tmp_path / "refined.yaml"
        result = runner.invoke(app, [
            "ai", "refine",
            str(tmp_path / "missing.yaml"),
            "-o", str(output_file),
        ])
        assert result.exit_code == 1


# ===========================================================================
# 11. AI サブコマンド: explain
# ===========================================================================

class TestAiExplainCommand:
    """ai explain コマンドのテスト。"""

    def test_ai_explain_basic(self, tmp_path: Path) -> None:
        """説明生成が動作する。"""
        yaml_file = tmp_path / "scenario.yaml"
        yaml_file.write_text(VALID_YAML, encoding="utf-8")

        result = runner.invoke(app, [
            "ai", "explain",
            str(yaml_file),
        ])
        assert result.exit_code == 0
        # スタブクライアントが返す説明テキストが出力される
        assert "テストシナリオ" in result.output or "シナリオ" in result.output

    def test_ai_explain_nonexistent_file(self, tmp_path: Path) -> None:
        """存在しないファイルで失敗。"""
        result = runner.invoke(app, [
            "ai", "explain",
            str(tmp_path / "missing.yaml"),
        ])
        assert result.exit_code == 1


# ===========================================================================
# 12. 終了コードのテスト
# ===========================================================================

class TestExitCodes:
    """終了コードの統一テスト。"""

    def test_success_exit_code_zero(self, tmp_path: Path) -> None:
        """成功時は終了コード 0。"""
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 0

    def test_failure_exit_code_one_validate(self, tmp_path: Path) -> None:
        """validate 失敗時は終了コード 1。"""
        yaml_file = tmp_path / "bad.yaml"
        yaml_file.write_text(INVALID_YAML, encoding="utf-8")
        result = runner.invoke(app, ["validate", str(yaml_file)])
        assert result.exit_code == 1

    def test_failure_exit_code_one_missing_file(self, tmp_path: Path) -> None:
        """存在しないファイル指定時は終了コード 1。"""
        result = runner.invoke(app, ["validate", str(tmp_path / "nope.yaml")])
        assert result.exit_code == 1

    @patch("subprocess.run")
    def test_record_exit_code_propagation(self, mock_run: MagicMock) -> None:
        """record コマンドは subprocess の終了コードを伝播する。"""
        mock_run.return_value = MagicMock(returncode=2)
        result = runner.invoke(app, ["record", "http://example.com"])
        assert result.exit_code == 2


# ===========================================================================
# 13. エラー出力のテスト
# ===========================================================================

class TestErrorOutput:
    """エラーメッセージの出力テスト。"""

    def test_validate_error_to_stderr(self, tmp_path: Path) -> None:
        """validate のエラーメッセージが出力される。"""
        yaml_file = tmp_path / "bad.yaml"
        yaml_file.write_text(INVALID_YAML, encoding="utf-8")
        result = runner.invoke(app, ["validate", str(yaml_file)])
        assert result.exit_code == 1
        # エラーメッセージが出力に含まれる（CliRunner は stdout/stderr を混合）
        assert result.output  # 何らかの出力がある

    def test_lint_error_on_missing_file(self, tmp_path: Path) -> None:
        """lint で存在しないファイルを指定するとエラーメッセージが出力される。"""
        result = runner.invoke(app, ["lint", str(tmp_path / "missing.yaml")])
        assert result.exit_code == 1
        assert "エラー" in result.output


# ===========================================================================
# 14. ヘルパー関数のテスト
# ===========================================================================

class TestHelpers:
    """ヘルパー関数のテスト。"""

    def test_extract_base_url_from_goto(self) -> None:
        """goto ステップから baseUrl を抽出する。"""
        from src.cli import _extract_base_url

        steps = [{"goto": "http://localhost:3000/login"}]
        assert _extract_base_url(steps) == "http://localhost:3000"

    def test_extract_base_url_default(self) -> None:
        """goto がない場合はデフォルト値を返す。"""
        from src.cli import _extract_base_url

        steps = [{"click": {"testId": "btn"}}]
        assert _extract_base_url(steps) == "http://localhost:3000"

    def test_extract_base_url_with_path(self) -> None:
        """パス付き URL からホスト部分のみ抽出する。"""
        from src.cli import _extract_base_url

        steps = [{"goto": "https://example.com/app/dashboard"}]
        assert _extract_base_url(steps) == "https://example.com"
