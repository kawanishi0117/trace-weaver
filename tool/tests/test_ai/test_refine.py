"""
AiRefiner のユニットテスト

AiRefiner: 既存の YAML DSL Scenario を改善する機能を検証する。

テスト方針:
- デフォルトスタブクライアントでの基本動作
- secret: true フラグの保持（最重要要件）
- カスタム LLM クライアント注入
- エラーハンドリング（不正 YAML、secret 消失等）
- Pydantic スキーマ検証
"""

from __future__ import annotations

import pytest

from brt.ai.refine import AiRefiner
from brt.dsl.schema import Scenario


# ---------------------------------------------------------------------------
# テスト用フィクスチャ
# ---------------------------------------------------------------------------

@pytest.fixture()
def minimal_scenario() -> Scenario:
    """最小構成の Scenario フィクスチャ。"""
    return Scenario(
        title="最小テスト",
        baseUrl="http://localhost:3000",
        steps=[
            {"goto": "http://localhost:3000/"},
        ],
    )


@pytest.fixture()
def scenario_with_secret() -> Scenario:
    """secret: true を含む Scenario フィクスチャ。"""
    return Scenario(
        title="ログインテスト",
        baseUrl="http://localhost:4200",
        vars={"email": "test@example.com", "password": "secret123"},
        steps=[
            {"goto": "http://localhost:4200/login"},
            {"fill": {"by": {"css": "#email"}, "value": "test@example.com"}},
            {
                "fill": {
                    "by": {"css": "#password"},
                    "value": "secret123",
                    "secret": True,
                },
            },
            {"click": {"by": {"role": "button", "name": "ログイン"}}},
        ],
    )


@pytest.fixture()
def scenario_with_multiple_secrets() -> Scenario:
    """複数の secret: true を含む Scenario フィクスチャ。"""
    return Scenario(
        title="複数シークレットテスト",
        baseUrl="http://localhost:4200",
        vars={"user": "admin"},
        steps=[
            {"goto": "http://localhost:4200/login"},
            {
                "fill": {
                    "by": {"css": "#username"},
                    "value": "admin",
                    "secret": True,
                },
            },
            {
                "fill": {
                    "by": {"css": "#password"},
                    "value": "pass123",
                    "secret": True,
                },
            },
            {
                "fill": {
                    "by": {"css": "#api-key"},
                    "value": "key-abc",
                    "secret": True,
                },
            },
            {"click": {"by": {"role": "button", "name": "送信"}}},
        ],
    )


# ---------------------------------------------------------------------------
# テスト用カスタム LLM クライアント
# ---------------------------------------------------------------------------

class _InvalidYamlClient:
    """不正な YAML を返す LLM クライアント。"""

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        return "{{invalid yaml: [unclosed"


class _SecretDroppingClient:
    """secret フラグを削除した YAML を返す LLM クライアント。"""

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        return (
            "title: ログインテスト\n"
            "baseUrl: http://localhost:4200\n"
            "vars:\n"
            "  email: test@example.com\n"
            "  password: secret123\n"
            "artifacts:\n"
            "  screenshots:\n"
            "    mode: before_each_step\n"
            "    format: jpeg\n"
            "    quality: 70\n"
            "  trace:\n"
            "    mode: on_failure\n"
            "  video:\n"
            "    mode: on_failure\n"
            "hooks: {}\n"
            "steps:\n"
            "  - goto: http://localhost:4200/login\n"
            "  - fill:\n"
            "      by:\n"
            "        css: '#email'\n"
            "      value: test@example.com\n"
            "  - fill:\n"
            "      by:\n"
            "        css: '#password'\n"
            "      value: secret123\n"
            # secret: true が意図的に欠落
            "  - click:\n"
            "      by:\n"
            "        role: button\n"
            "        name: ログイン\n"
            "healing: off\n"
        )


class _PassthroughClient:
    """入力をそのまま返すカスタム LLM クライアント。"""

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        marker = "現在のシナリオ:\n"
        idx = user_prompt.find(marker)
        if idx >= 0:
            return user_prompt[idx + len(marker):]
        return user_prompt


# ---------------------------------------------------------------------------
# TestAiRefiner
# ---------------------------------------------------------------------------

class TestAiRefiner:
    """AiRefiner のテストクラス。"""

    def test_default_stub_returns_valid_scenario(
        self, minimal_scenario: Scenario
    ) -> None:
        """デフォルトスタブで有効な Scenario が返されること。"""
        refiner = AiRefiner()
        result = refiner.refine(minimal_scenario)
        assert isinstance(result, Scenario)

    def test_title_preserved_after_refine(
        self, scenario_with_secret: Scenario
    ) -> None:
        """refine 後も title が保持されること。"""
        refiner = AiRefiner()
        result = refiner.refine(scenario_with_secret)
        assert result.title == scenario_with_secret.title

    def test_base_url_preserved_after_refine(
        self, scenario_with_secret: Scenario
    ) -> None:
        """refine 後も baseUrl が保持されること。"""
        refiner = AiRefiner()
        result = refiner.refine(scenario_with_secret)
        assert result.baseUrl == scenario_with_secret.baseUrl

    def test_steps_not_empty_after_refine(
        self, scenario_with_secret: Scenario
    ) -> None:
        """refine 後も steps が空でないこと。"""
        refiner = AiRefiner()
        result = refiner.refine(scenario_with_secret)
        assert len(result.steps) > 0

    def test_single_secret_flag_preserved(
        self, scenario_with_secret: Scenario
    ) -> None:
        """secret: true フラグが保持されること（最重要要件）。"""
        refiner = AiRefiner()
        result = refiner.refine(scenario_with_secret)

        # refine 後のステップ内に secret: true が存在することを確認
        secret_count = self._count_secrets(result)
        assert secret_count >= 1, "secret: true フラグが失われています"

    def test_multiple_secret_flags_all_preserved(
        self, scenario_with_multiple_secrets: Scenario
    ) -> None:
        """複数の secret: true フラグが全て保持されること。"""
        refiner = AiRefiner()
        result = refiner.refine(scenario_with_multiple_secrets)

        original_count = self._count_secrets(scenario_with_multiple_secrets)
        refined_count = self._count_secrets(result)
        assert refined_count >= original_count, (
            f"secret フラグが減少: {original_count} → {refined_count}"
        )

    def test_custom_llm_client_injection(
        self, minimal_scenario: Scenario
    ) -> None:
        """カスタム LLM クライアントを注入できること。"""
        client = _PassthroughClient()
        refiner = AiRefiner(llm_client=client)
        result = refiner.refine(minimal_scenario)
        assert isinstance(result, Scenario)

    def test_invalid_yaml_raises_error(
        self, minimal_scenario: Scenario
    ) -> None:
        """LLM が不正な YAML を返した場合に ValueError が発生すること。"""
        refiner = AiRefiner(llm_client=_InvalidYamlClient())
        with pytest.raises(ValueError, match="YAML パース"):
            refiner.refine(minimal_scenario)

    def test_secret_dropping_detected(
        self, scenario_with_secret: Scenario
    ) -> None:
        """secret フラグが失われた場合に ValueError が発生すること。"""
        refiner = AiRefiner(llm_client=_SecretDroppingClient())
        with pytest.raises(ValueError, match="secret フラグが失われました"):
            refiner.refine(scenario_with_secret)

    def test_refined_scenario_passes_pydantic_validation(
        self, scenario_with_secret: Scenario
    ) -> None:
        """refine 後の Scenario が Pydantic 検証に成功すること。"""
        refiner = AiRefiner()
        result = refiner.refine(scenario_with_secret)
        # Pydantic モデルとして再検証
        revalidated = Scenario(**result.model_dump())
        assert revalidated.title == result.title

    def test_vars_preserved_after_refine(
        self, scenario_with_secret: Scenario
    ) -> None:
        """refine 後も vars が保持されること。"""
        refiner = AiRefiner()
        result = refiner.refine(scenario_with_secret)
        assert "email" in result.vars
        assert "password" in result.vars

    def test_healing_preserved_after_refine(
        self, minimal_scenario: Scenario
    ) -> None:
        """refine 後も healing 設定が保持されること。"""
        refiner = AiRefiner()
        result = refiner.refine(minimal_scenario)
        assert result.healing == minimal_scenario.healing

    # -------------------------------------------------------------------
    # ヘルパーメソッド
    # -------------------------------------------------------------------

    @staticmethod
    def _count_secrets(scenario: Scenario) -> int:
        """Scenario 内の secret: true の数をカウントする。"""
        count = 0
        for step in scenario.steps:
            count += TestAiRefiner._count_in_dict(step)
        return count

    @staticmethod
    def _count_in_dict(d: object) -> int:
        """辞書を再帰的に走査し secret: true をカウントする。"""
        if isinstance(d, dict):
            c = 0
            for key, value in d.items():
                if key == "secret" and value is True:
                    c += 1
                else:
                    c += TestAiRefiner._count_in_dict(value)
            return c
        if isinstance(d, list):
            return sum(TestAiRefiner._count_in_dict(item) for item in d)
        return 0
