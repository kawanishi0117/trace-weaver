"""
Reporter — テスト実行レポートの生成

ScenarioResult を受け取り、JSON / HTML / JUnit XML 形式のレポートを生成する。

主な機能:
  - generate_json(): JSON レポート（report.json）の生成
  - generate_html(): Jinja2 テンプレートを使用した HTML レポート（report.html）の生成
  - generate_junit_xml(): JUnit XML レポート（junit.xml）の生成（CI 統合用）

要件 9.1: JSON レポート生成
要件 9.2: HTML レポート生成（Jinja2 テンプレート）
要件 9.3: JUnit XML レポート生成（CI 互換）
"""

from __future__ import annotations

import json
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from .runner import ScenarioResult, StepResult

logger = logging.getLogger(__name__)

# テンプレートディレクトリのパス
_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


class Reporter:
    """テスト実行レポートの生成クラス。

    ScenarioResult を受け取り、JSON / HTML / JUnit XML 形式で
    レポートファイルを出力する。
    """

    # -------------------------------------------------------------------
    # JSON レポート
    # -------------------------------------------------------------------

    def generate_json(self, result: ScenarioResult, output_dir: Path) -> Path:
        """JSON レポートを生成する。

        ScenarioResult をシリアライズし、report.json として出力する。
        ステップのサマリー（total, passed, failed, skipped）も含む。

        Args:
            result: シナリオ実行結果
            output_dir: 出力先ディレクトリ

        Returns:
            生成された report.json のパス
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        report_data = self._build_report_dict(result)

        output_path = output_dir / "report.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

        logger.info("JSON レポートを生成しました: %s", output_path)
        return output_path

    # -------------------------------------------------------------------
    # HTML レポート
    # -------------------------------------------------------------------

    def generate_html(self, result: ScenarioResult, output_dir: Path) -> Path:
        """HTML レポートを生成する。

        Jinja2 テンプレート（templates/report.html.j2）を使用して
        スタンドアロン HTML レポートを生成する。

        Args:
            result: シナリオ実行結果
            output_dir: 出力先ディレクトリ

        Returns:
            生成された report.html のパス
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        report_data = self._build_report_dict(result)

        # Jinja2 テンプレートの読み込みとレンダリング
        env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=True,
        )
        template = env.get_template("report.html.j2")
        html_content = template.render(report=report_data)

        output_path = output_dir / "report.html"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info("HTML レポートを生成しました: %s", output_path)
        return output_path

    # -------------------------------------------------------------------
    # JUnit XML レポート
    # -------------------------------------------------------------------

    def generate_junit_xml(self, result: ScenarioResult, output_dir: Path) -> Path:
        """JUnit XML レポートを生成する。

        CI ツール（Jenkins, GitHub Actions 等）と互換性のある
        JUnit XML 形式でレポートを出力する。

        Args:
            result: シナリオ実行結果
            output_dir: 出力先ディレクトリ

        Returns:
            生成された junit.xml のパス
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # ルート要素
        testsuites = ET.Element("testsuites")

        # testsuite 要素
        summary = self._compute_summary(result.steps)
        testsuite = ET.SubElement(testsuites, "testsuite")
        testsuite.set("name", result.scenario_title)
        testsuite.set("tests", str(summary["total"]))
        testsuite.set("failures", str(summary["failed"]))
        testsuite.set("time", f"{result.duration_ms / 1000:.3f}")

        # 各ステップを testcase として追加
        for step in result.steps:
            testcase = ET.SubElement(testsuite, "testcase")
            testcase.set("name", step.step_name)
            testcase.set("classname", result.scenario_title)
            testcase.set("time", f"{step.duration_ms / 1000:.3f}")

            # 失敗ステップには failure 要素を追加
            if step.status == "failed" and step.error:
                failure = ET.SubElement(testcase, "failure")
                failure.set("message", step.error)
                failure.text = step.error

            # スキップステップには skipped 要素を追加
            if step.status == "skipped":
                ET.SubElement(testcase, "skipped")

        # XML ファイルに書き出し
        tree = ET.ElementTree(testsuites)
        output_path = output_dir / "junit.xml"
        ET.indent(tree, space="  ")
        tree.write(
            str(output_path),
            encoding="unicode",
            xml_declaration=True,
        )

        logger.info("JUnit XML レポートを生成しました: %s", output_path)
        return output_path

    # -------------------------------------------------------------------
    # 内部ヘルパー
    # -------------------------------------------------------------------

    def _build_report_dict(self, result: ScenarioResult) -> dict[str, Any]:
        """ScenarioResult をレポート用辞書に変換する。

        Args:
            result: シナリオ実行結果

        Returns:
            レポート用辞書
        """
        steps_data = []
        for step in result.steps:
            step_dict: dict[str, Any] = {
                "step_name": step.step_name,
                "step_type": step.step_type,
                "step_index": step.step_index,
                "status": step.status,
                "duration_ms": step.duration_ms,
                "error": step.error,
                "screenshot_path": self._to_relative_screenshot_path(
                    step.screenshot_path, result.artifacts_dir
                ),
                "section": step.section,
            }
            steps_data.append(step_dict)

        return {
            "title": result.scenario_title,
            "status": result.status,
            "duration_ms": result.duration_ms,
            "started_at": (
                result.started_at.isoformat() if result.started_at else None
            ),
            "finished_at": (
                result.finished_at.isoformat() if result.finished_at else None
            ),
            "steps": steps_data,
            "summary": self._compute_summary(result.steps),
        }

    def _compute_summary(self, steps: list[StepResult]) -> dict[str, int]:
        """ステップリストからサマリーを計算する。

        Args:
            steps: ステップ結果リスト

        Returns:
            total, passed, failed, skipped の辞書
        """
        total = len(steps)
        passed = sum(1 for s in steps if s.status == "passed")
        failed = sum(1 for s in steps if s.status == "failed")
        skipped = sum(1 for s in steps if s.status == "skipped")
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
        }

    def _to_relative_screenshot_path(
        self,
        screenshot_path: Path | None,
        artifacts_dir: Path | None,
    ) -> str | None:
        """スクリーンショットパスを artifacts_dir からの相対パスに変換する。

        Args:
            screenshot_path: スクリーンショットの絶対パス
            artifacts_dir: 成果物ディレクトリ

        Returns:
            相対パス文字列。パスが None の場合は None。
        """
        if screenshot_path is None:
            return None

        if artifacts_dir is not None:
            try:
                # OS に依存しない POSIX パス形式で返す
                return screenshot_path.relative_to(artifacts_dir).as_posix()
            except ValueError:
                # artifacts_dir 配下でない場合はそのまま POSIX 形式で返す
                pass

        return screenshot_path.as_posix()
