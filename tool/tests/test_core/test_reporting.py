"""
Reporter のユニットテスト

ScenarioResult / StepResult は実際のデータクラスを使用する。
JSON パースには json モジュール、XML パースには xml.etree.ElementTree を使用する。

テスト対象:
  - generate_json(): JSON レポート生成、構造、サマリー
  - generate_html(): HTML レポート生成、テンプレートレンダリング
  - generate_junit_xml(): JUnit XML レポート生成、CI 互換性
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import pytest

from src.core.reporting import Reporter
from src.core.runner import ScenarioResult, StepResult


# ---------------------------------------------------------------------------
# ヘルパー: テスト用データ生成
# ---------------------------------------------------------------------------

def _make_step(
    *,
    step_name: str = "fill-email",
    step_type: str = "fill",
    step_index: int = 0,
    status: str = "passed",
    duration_ms: float = 123.4,
    error: str | None = None,
    screenshot_path: Path | None = None,
    section: str | None = None,
) -> StepResult:
    """テスト用の StepResult を生成する。"""
    return StepResult(
        step_name=step_name,
        step_type=step_type,
        step_index=step_index,
        status=status,
        duration_ms=duration_ms,
        error=error,
        screenshot_path=screenshot_path,
        section=section,
    )


def _make_result(
    *,
    title: str = "ログインフローのテスト",
    status: str = "passed",
    steps: list[StepResult] | None = None,
    duration_ms: float = 1234.5,
    artifacts_dir: Path | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> ScenarioResult:
    """テスト用の ScenarioResult を生成する。"""
    if steps is None:
        steps = [
            _make_step(step_name="fill-email", step_type="fill", step_index=0),
            _make_step(step_name="fill-password", step_type="fill", step_index=1),
            _make_step(step_name="click-login", step_type="click", step_index=2),
        ]
    if started_at is None:
        started_at = datetime(2024, 3, 15, 10, 30, 45)
    if finished_at is None:
        finished_at = datetime(2024, 3, 15, 10, 31, 0)

    return ScenarioResult(
        scenario_title=title,
        status=status,
        steps=steps,
        duration_ms=duration_ms,
        artifacts_dir=artifacts_dir,
        started_at=started_at,
        finished_at=finished_at,
    )


def _make_mixed_result(tmp_path: Path) -> ScenarioResult:
    """成功・失敗・スキップが混在する ScenarioResult を生成する。"""
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    screenshots_dir = artifacts_dir / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    # ダミーのスクリーンショットファイルを作成
    screenshot_file = screenshots_dir / "0001_before-fill-email.jpg"
    screenshot_file.write_text("dummy")

    steps = [
        _make_step(
            step_name="fill-email",
            step_type="fill",
            step_index=0,
            status="passed",
            duration_ms=100.0,
            screenshot_path=screenshot_file,
            section="ログイン",
        ),
        _make_step(
            step_name="click-login",
            step_type="click",
            step_index=1,
            status="failed",
            duration_ms=200.0,
            error="要素が見つかりません: #login-button",
            section="ログイン",
        ),
        _make_step(
            step_name="verify-redirect",
            step_type="expectUrl",
            step_index=2,
            status="skipped",
            duration_ms=0.0,
        ),
    ]

    return ScenarioResult(
        scenario_title="ログインフローのテスト",
        status="failed",
        steps=steps,
        duration_ms=1500.0,
        artifacts_dir=artifacts_dir,
        started_at=datetime(2024, 3, 15, 10, 30, 45),
        finished_at=datetime(2024, 3, 15, 10, 31, 0),
    )


# ===========================================================================
# テスト: JSON レポート生成
# ===========================================================================

class TestGenerateJson:
    """generate_json のテスト。"""

    def test_report_json_created(self, tmp_path: Path) -> None:
        """report.json が生成されること。"""
        reporter = Reporter()
        result = _make_result()

        output = reporter.generate_json(result, tmp_path)

        assert output.exists()
        assert output.name == "report.json"

    def test_json_title_correct(self, tmp_path: Path) -> None:
        """JSON の title がシナリオ名と一致すること。"""
        reporter = Reporter()
        result = _make_result(title="ダッシュボード表示テスト")

        reporter.generate_json(result, tmp_path)

        data = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
        assert data["title"] == "ダッシュボード表示テスト"

    def test_json_status_correct(self, tmp_path: Path) -> None:
        """JSON の status が正しいこと。"""
        reporter = Reporter()
        result = _make_result(status="failed")

        reporter.generate_json(result, tmp_path)

        data = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
        assert data["status"] == "failed"

    def test_json_steps_length(self, tmp_path: Path) -> None:
        """JSON の steps 配列が正しい長さであること。"""
        reporter = Reporter()
        steps = [
            _make_step(step_index=i, step_name=f"step-{i}")
            for i in range(5)
        ]
        result = _make_result(steps=steps)

        reporter.generate_json(result, tmp_path)

        data = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
        assert len(data["steps"]) == 5

    def test_json_summary_correct(self, tmp_path: Path) -> None:
        """JSON の summary が正しいこと（total, passed, failed, skipped）。"""
        reporter = Reporter()
        result = _make_mixed_result(tmp_path)
        output_dir = tmp_path / "output"

        reporter.generate_json(result, output_dir)

        data = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
        summary = data["summary"]
        assert summary["total"] == 3
        assert summary["passed"] == 1
        assert summary["failed"] == 1
        assert summary["skipped"] == 1

    def test_json_failed_step_error_included(self, tmp_path: Path) -> None:
        """失敗ステップの error が JSON に含まれること。"""
        reporter = Reporter()
        result = _make_mixed_result(tmp_path)
        output_dir = tmp_path / "output"

        reporter.generate_json(result, output_dir)

        data = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
        failed_step = [s for s in data["steps"] if s["status"] == "failed"][0]
        assert failed_step["error"] == "要素が見つかりません: #login-button"

    def test_json_screenshot_path_relative(self, tmp_path: Path) -> None:
        """screenshot_path が artifacts_dir からの相対パスで含まれること。"""
        reporter = Reporter()
        result = _make_mixed_result(tmp_path)
        output_dir = tmp_path / "output"

        reporter.generate_json(result, output_dir)

        data = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
        step_with_screenshot = data["steps"][0]
        # artifacts_dir からの相対パスであること
        assert step_with_screenshot["screenshot_path"] == "screenshots/0001_before-fill-email.jpg"

    def test_json_datetime_iso_format(self, tmp_path: Path) -> None:
        """started_at / finished_at が ISO 8601 形式であること。"""
        reporter = Reporter()
        result = _make_result(
            started_at=datetime(2024, 3, 15, 10, 30, 45),
            finished_at=datetime(2024, 3, 15, 10, 31, 0),
        )

        reporter.generate_json(result, tmp_path)

        data = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
        assert data["started_at"] == "2024-03-15T10:30:45"
        assert data["finished_at"] == "2024-03-15T10:31:00"

    def test_json_duration_ms(self, tmp_path: Path) -> None:
        """JSON の duration_ms が正しいこと。"""
        reporter = Reporter()
        result = _make_result(duration_ms=9876.5)

        reporter.generate_json(result, tmp_path)

        data = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
        assert data["duration_ms"] == 9876.5

    def test_json_step_section_included(self, tmp_path: Path) -> None:
        """ステップの section が JSON に含まれること。"""
        reporter = Reporter()
        result = _make_mixed_result(tmp_path)
        output_dir = tmp_path / "output"

        reporter.generate_json(result, output_dir)

        data = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
        assert data["steps"][0]["section"] == "ログイン"
        assert data["steps"][2]["section"] is None


# ===========================================================================
# テスト: HTML レポート生成
# ===========================================================================

class TestGenerateHtml:
    """generate_html のテスト。"""

    def test_report_html_created(self, tmp_path: Path) -> None:
        """report.html が生成されること。"""
        reporter = Reporter()
        result = _make_result()

        output = reporter.generate_html(result, tmp_path)

        assert output.exists()
        assert output.name == "report.html"

    def test_html_contains_scenario_title(self, tmp_path: Path) -> None:
        """HTML にシナリオタイトルが含まれること。"""
        reporter = Reporter()
        result = _make_result(title="ダッシュボード表示テスト")

        reporter.generate_html(result, tmp_path)

        html = (tmp_path / "report.html").read_text(encoding="utf-8")
        assert "ダッシュボード表示テスト" in html

    def test_html_contains_step_names(self, tmp_path: Path) -> None:
        """HTML にステップ名が含まれること。"""
        reporter = Reporter()
        result = _make_result()

        reporter.generate_html(result, tmp_path)

        html = (tmp_path / "report.html").read_text(encoding="utf-8")
        assert "fill-email" in html
        assert "fill-password" in html
        assert "click-login" in html

    def test_html_contains_error_message(self, tmp_path: Path) -> None:
        """HTML に失敗ステップのエラーメッセージが含まれること。"""
        reporter = Reporter()
        result = _make_mixed_result(tmp_path)
        output_dir = tmp_path / "output"

        reporter.generate_html(result, output_dir)

        html = (output_dir / "report.html").read_text(encoding="utf-8")
        assert "要素が見つかりません" in html

    def test_html_contains_screenshot_link(self, tmp_path: Path) -> None:
        """HTML にスクリーンショットリンクが含まれること。"""
        reporter = Reporter()
        result = _make_mixed_result(tmp_path)
        output_dir = tmp_path / "output"

        reporter.generate_html(result, output_dir)

        html = (output_dir / "report.html").read_text(encoding="utf-8")
        assert "screenshots/0001_before-fill-email.jpg" in html

    def test_html_contains_duration(self, tmp_path: Path) -> None:
        """HTML に実行時間が含まれること。"""
        reporter = Reporter()
        result = _make_result(duration_ms=1234.5)

        reporter.generate_html(result, tmp_path)

        html = (tmp_path / "report.html").read_text(encoding="utf-8")
        assert "1234.5" in html

    def test_html_contains_summary_info(self, tmp_path: Path) -> None:
        """HTML にサマリー情報（合計、成功、失敗、スキップ）が含まれること。"""
        reporter = Reporter()
        result = _make_mixed_result(tmp_path)
        output_dir = tmp_path / "output"

        reporter.generate_html(result, output_dir)

        html = (output_dir / "report.html").read_text(encoding="utf-8")
        # サマリーカードの値が含まれること
        assert "合計" in html
        assert "成功" in html
        assert "失敗" in html
        assert "スキップ" in html

    def test_html_is_standalone(self, tmp_path: Path) -> None:
        """HTML がスタンドアロン（CSS インライン）であること。"""
        reporter = Reporter()
        result = _make_result()

        reporter.generate_html(result, tmp_path)

        html = (tmp_path / "report.html").read_text(encoding="utf-8")
        # <style> タグが含まれること（インライン CSS）
        assert "<style>" in html
        # 外部 CSS リンクがないこと
        assert '<link rel="stylesheet"' not in html

    def test_html_contains_status_badge(self, tmp_path: Path) -> None:
        """HTML にステータスバッジが含まれること。"""
        reporter = Reporter()
        result = _make_result(status="passed")

        reporter.generate_html(result, tmp_path)

        html = (tmp_path / "report.html").read_text(encoding="utf-8")
        assert "status-passed" in html


# ===========================================================================
# テスト: JUnit XML レポート生成
# ===========================================================================

class TestGenerateJunitXml:
    """generate_junit_xml のテスト。"""

    def test_junit_xml_created(self, tmp_path: Path) -> None:
        """junit.xml が生成されること。"""
        reporter = Reporter()
        result = _make_result()

        output = reporter.generate_junit_xml(result, tmp_path)

        assert output.exists()
        assert output.name == "junit.xml"

    def test_xml_is_valid(self, tmp_path: Path) -> None:
        """生成された XML が valid であること。"""
        reporter = Reporter()
        result = _make_result()

        reporter.generate_junit_xml(result, tmp_path)

        # パースが例外なく完了すれば valid
        tree = ET.parse(tmp_path / "junit.xml")
        root = tree.getroot()
        assert root.tag == "testsuites"

    def test_testsuite_name_correct(self, tmp_path: Path) -> None:
        """testsuite の name がシナリオ名と一致すること。"""
        reporter = Reporter()
        result = _make_result(title="ダッシュボード表示テスト")

        reporter.generate_junit_xml(result, tmp_path)

        tree = ET.parse(tmp_path / "junit.xml")
        testsuite = tree.getroot().find("testsuite")
        assert testsuite is not None
        assert testsuite.get("name") == "ダッシュボード表示テスト"

    def test_testsuite_tests_count(self, tmp_path: Path) -> None:
        """testsuite の tests 数が正しいこと。"""
        reporter = Reporter()
        steps = [
            _make_step(step_index=i, step_name=f"step-{i}")
            for i in range(7)
        ]
        result = _make_result(steps=steps)

        reporter.generate_junit_xml(result, tmp_path)

        tree = ET.parse(tmp_path / "junit.xml")
        testsuite = tree.getroot().find("testsuite")
        assert testsuite is not None
        assert testsuite.get("tests") == "7"

    def test_testsuite_failures_count(self, tmp_path: Path) -> None:
        """testsuite の failures 数が正しいこと。"""
        reporter = Reporter()
        result = _make_mixed_result(tmp_path)
        output_dir = tmp_path / "output"

        reporter.generate_junit_xml(result, output_dir)

        tree = ET.parse(output_dir / "junit.xml")
        testsuite = tree.getroot().find("testsuite")
        assert testsuite is not None
        assert testsuite.get("failures") == "1"

    def test_failed_testcase_has_failure_element(self, tmp_path: Path) -> None:
        """失敗 testcase に failure 要素があること。"""
        reporter = Reporter()
        result = _make_mixed_result(tmp_path)
        output_dir = tmp_path / "output"

        reporter.generate_junit_xml(result, output_dir)

        tree = ET.parse(output_dir / "junit.xml")
        testcases = tree.getroot().find("testsuite").findall("testcase")
        # click-login が失敗ステップ
        failed_tc = [tc for tc in testcases if tc.get("name") == "click-login"][0]
        failure = failed_tc.find("failure")
        assert failure is not None
        assert "要素が見つかりません" in failure.get("message", "")

    def test_passed_testcase_no_failure_element(self, tmp_path: Path) -> None:
        """成功 testcase に failure 要素がないこと。"""
        reporter = Reporter()
        result = _make_mixed_result(tmp_path)
        output_dir = tmp_path / "output"

        reporter.generate_junit_xml(result, output_dir)

        tree = ET.parse(output_dir / "junit.xml")
        testcases = tree.getroot().find("testsuite").findall("testcase")
        # fill-email が成功ステップ
        passed_tc = [tc for tc in testcases if tc.get("name") == "fill-email"][0]
        failure = passed_tc.find("failure")
        assert failure is None

    def test_testcase_classname_matches_scenario(self, tmp_path: Path) -> None:
        """testcase の classname がシナリオ名と一致すること。"""
        reporter = Reporter()
        result = _make_result(title="検索機能テスト")

        reporter.generate_junit_xml(result, tmp_path)

        tree = ET.parse(tmp_path / "junit.xml")
        testcases = tree.getroot().find("testsuite").findall("testcase")
        for tc in testcases:
            assert tc.get("classname") == "検索機能テスト"

    def test_testcase_time_attribute(self, tmp_path: Path) -> None:
        """testcase の time 属性が秒単位で正しいこと。"""
        reporter = Reporter()
        steps = [_make_step(duration_ms=456.0)]
        result = _make_result(steps=steps)

        reporter.generate_junit_xml(result, tmp_path)

        tree = ET.parse(tmp_path / "junit.xml")
        testcase = tree.getroot().find("testsuite").find("testcase")
        assert testcase is not None
        assert testcase.get("time") == "0.456"

    def test_testsuite_time_attribute(self, tmp_path: Path) -> None:
        """testsuite の time 属性が全体実行時間（秒）であること。"""
        reporter = Reporter()
        result = _make_result(duration_ms=2500.0)

        reporter.generate_junit_xml(result, tmp_path)

        tree = ET.parse(tmp_path / "junit.xml")
        testsuite = tree.getroot().find("testsuite")
        assert testsuite is not None
        assert testsuite.get("time") == "2.500"

    def test_skipped_testcase_has_skipped_element(self, tmp_path: Path) -> None:
        """スキップ testcase に skipped 要素があること。"""
        reporter = Reporter()
        result = _make_mixed_result(tmp_path)
        output_dir = tmp_path / "output"

        reporter.generate_junit_xml(result, output_dir)

        tree = ET.parse(output_dir / "junit.xml")
        testcases = tree.getroot().find("testsuite").findall("testcase")
        skipped_tc = [tc for tc in testcases if tc.get("name") == "verify-redirect"][0]
        assert skipped_tc.find("skipped") is not None
