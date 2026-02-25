"""
Recorder テスト — 操作記録エンジンの単体テスト

操作を内部リストに蓄積し、YAML DSL 形式で出力する機能を検証する。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from brt.mcp.recorder import Recorder, RecordedStep


# ---------------------------------------------------------------------------
# RecordedStep データクラスのテスト
# ---------------------------------------------------------------------------

class TestRecordedStep:
    """RecordedStep の生成と辞書変換のテスト。"""

    def test_create_goto_step(self):
        """goto ステップを正しく生成できること。"""
        step = RecordedStep(
            step_type="goto",
            params={"url": "https://example.com"},
            name="navigate-to-example",
        )
        assert step.step_type == "goto"
        assert step.params["url"] == "https://example.com"
        assert step.name == "navigate-to-example"

    def test_to_dsl_dict_goto(self):
        """goto ステップが DSL 辞書形式に変換できること。"""
        step = RecordedStep(
            step_type="goto",
            params={"url": "https://example.com"},
            name="navigate-to-example",
        )
        dsl = step.to_dsl_dict()
        assert dsl == {
            "goto": {
                "url": "https://example.com",
                "name": "navigate-to-example",
            }
        }

    def test_to_dsl_dict_click_with_by(self):
        """click ステップが by セレクタ付きで DSL 辞書に変換できること。"""
        step = RecordedStep(
            step_type="click",
            params={"by": {"role": "button", "name": "Login"}},
            name="click-login",
        )
        dsl = step.to_dsl_dict()
        assert dsl == {
            "click": {
                "by": {"role": "button", "name": "Login"},
                "name": "click-login",
            }
        }

    def test_to_dsl_dict_fill_with_secret(self):
        """fill ステップが secret フラグ付きで変換できること。"""
        step = RecordedStep(
            step_type="fill",
            params={
                "by": {"role": "textbox", "name": "Password"},
                "value": "secret123",
                "secret": True,
            },
            name="fill-password",
        )
        dsl = step.to_dsl_dict()
        assert dsl["fill"]["secret"] is True

    def test_to_dsl_dict_section(self):
        """section ステップが正しく変換できること。"""
        step = RecordedStep(step_type="section", params={}, name="Login")
        dsl = step.to_dsl_dict()
        assert dsl == {"section": "Login"}


# ---------------------------------------------------------------------------
# Recorder 本体のテスト
# ---------------------------------------------------------------------------

class TestRecorder:
    """Recorder の操作記録・出力機能のテスト。"""

    @pytest.fixture
    def recorder(self) -> Recorder:
        """空の Recorder インスタンスを生成する。"""
        return Recorder(
            title="Test Scenario",
            base_url="https://example.com",
        )

    def test_initial_state(self, recorder: Recorder):
        """初期状態でステップが空であること。"""
        assert recorder.step_count == 0
        assert recorder.title == "Test Scenario"
        assert recorder.base_url == "https://example.com"

    def test_add_step(self, recorder: Recorder):
        """ステップを追加できること。"""
        recorder.add_step("goto", {"url": "https://example.com"}, "nav")
        assert recorder.step_count == 1

    def test_add_multiple_steps(self, recorder: Recorder):
        """複数ステップを順序通り追加できること。"""
        recorder.add_step("goto", {"url": "https://example.com"}, "nav")
        recorder.add_step("click", {"by": {"role": "button", "name": "OK"}}, "click-ok")
        assert recorder.step_count == 2

    def test_add_section(self, recorder: Recorder):
        """セクション区切りを追加できること。"""
        recorder.add_section("Login Flow")
        assert recorder.step_count == 1

    def test_to_scenario_dict(self, recorder: Recorder):
        """Scenario 辞書形式で出力できること。"""
        recorder.add_section("Navigation")
        recorder.add_step("goto", {"url": "https://example.com"}, "nav")
        recorder.add_step(
            "click",
            {"by": {"role": "link", "name": "About"}},
            "click-about",
        )

        scenario = recorder.to_scenario_dict()

        assert scenario["title"] == "Test Scenario"
        assert scenario["baseUrl"] == "https://example.com"
        assert len(scenario["steps"]) == 3
        assert scenario["steps"][0] == {"section": "Navigation"}
        assert "goto" in scenario["steps"][1]
        assert "click" in scenario["steps"][2]

    def test_to_scenario_dict_has_artifacts(self, recorder: Recorder):
        """出力に artifacts 設定が含まれること。"""
        recorder.add_step("goto", {"url": "/"}, "nav")
        scenario = recorder.to_scenario_dict()

        assert "artifacts" in scenario
        assert scenario["artifacts"]["screenshots"]["mode"] == "before_each_step"

    def test_save_yaml(self, recorder: Recorder, tmp_path: Path):
        """YAML ファイルとして保存できること。"""
        recorder.add_step("goto", {"url": "https://example.com"}, "nav")
        output_path = tmp_path / "test.yaml"

        recorder.save_yaml(output_path)

        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert "Test Scenario" in content
        assert "goto" in content

    def test_clear(self, recorder: Recorder):
        """記録をクリアできること。"""
        recorder.add_step("goto", {"url": "/"}, "nav")
        assert recorder.step_count == 1

        recorder.clear()
        assert recorder.step_count == 0

    def test_auto_name_generation(self):
        """name 省略時に自動生成されること。"""
        recorder = Recorder(title="Test", base_url="https://example.com")
        recorder.add_step("goto", {"url": "https://example.com"})
        recorder.add_step("click", {"by": {"role": "button", "name": "OK"}})

        scenario = recorder.to_scenario_dict()
        # 自動生成された name が存在すること
        for step_dict in scenario["steps"]:
            for key, val in step_dict.items():
                if isinstance(val, dict) and "name" in val:
                    assert val["name"] != ""
