"""
AiDrafter / AiExplainer のユニットテスト

AiDrafter: 自然言語仕様から YAML DSL Scenario を生成する機能を検証する。
AiExplainer: Scenario からアウトライン（説明）を生成する機能を検証する。

テスト方針:
- デフォルトスタブクライアントでの基本動作
- カスタム LLM クライアント注入
- エラーハンドリング（不正 YAML、空レスポンス等）
- プロンプトテンプレートの構築検証
"""

from __future__ import annotations

import pytest

from brt.ai.draft import AiDrafter, LlmClient
from brt.ai.explain import AiExplainer
from brt.ai.prompts import DRAFT_SYSTEM_PROMPT, DRAFT_USER_TEMPLATE
from brt.dsl.schema import Scenario


# ---------------------------------------------------------------------------
# テスト用カスタム LLM クライアント
# ---------------------------------------------------------------------------

class _ValidYamlClient:
    """有効な YAML を返すカスタム LLM クライアント。"""

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        return (
            "title: カスタムテスト\n"
            "baseUrl: http://example.com\n"
            "vars:\n"
            "  user: admin\n"
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
            "  - goto: http://example.com/login\n"
            "  - click:\n"
            "      by:\n"
            "        role: button\n"
            "        name: ログイン\n"
            "healing: off\n"
        )


class _InvalidYamlClient:
    """不正な YAML を返す LLM クライアント。"""

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        return "{{invalid yaml: [unclosed"


class _EmptyResponseClient:
    """空のレスポンスを返す LLM クライアント。"""

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        return ""


class _MissingFieldsClient:
    """必須フィールドが欠けた YAML を返す LLM クライアント。"""

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        # title が欠けている
        return (
            "baseUrl: http://example.com\n"
            "steps:\n"
            "  - goto: http://example.com/\n"
        )


class _PromptCapturingClient:
    """送信されたプロンプトを記録する LLM クライアント。"""

    def __init__(self) -> None:
        self.last_system_prompt: str = ""
        self.last_user_prompt: str = ""

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        self.last_system_prompt = system_prompt
        self.last_user_prompt = user_prompt
        return (
            "title: キャプチャテスト\n"
            "baseUrl: http://localhost\n"
            "vars: {}\n"
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
            "  - goto: http://localhost/\n"
            "healing: off\n"
        )


# ---------------------------------------------------------------------------
# TestAiDrafter
# ---------------------------------------------------------------------------

class TestAiDrafter:
    """AiDrafter のテストクラス。"""

    def test_default_stub_returns_valid_scenario(self) -> None:
        """デフォルトスタブで有効な Scenario が返されること。"""
        drafter = AiDrafter()
        scenario = drafter.draft("ログインフローをテストする")
        assert isinstance(scenario, Scenario)

    def test_scenario_title_not_empty(self) -> None:
        """返された Scenario の title が空でないこと。"""
        drafter = AiDrafter()
        scenario = drafter.draft("ログインフローをテストする")
        assert scenario.title
        assert len(scenario.title) > 0

    def test_scenario_base_url_not_empty(self) -> None:
        """返された Scenario の baseUrl が空でないこと。"""
        drafter = AiDrafter()
        scenario = drafter.draft("ログインフローをテストする")
        assert scenario.baseUrl
        assert len(scenario.baseUrl) > 0

    def test_scenario_steps_not_empty(self) -> None:
        """返された Scenario の steps が空でないこと。"""
        drafter = AiDrafter()
        scenario = drafter.draft("ログインフローをテストする")
        assert len(scenario.steps) > 0

    def test_custom_llm_client_injection(self) -> None:
        """カスタム LLM クライアントを注入できること。"""
        client = _ValidYamlClient()
        drafter = AiDrafter(llm_client=client)
        scenario = drafter.draft("カスタムテスト")
        assert scenario.title == "カスタムテスト"
        assert scenario.baseUrl == "http://example.com"

    def test_invalid_yaml_raises_error(self) -> None:
        """LLM が不正な YAML を返した場合に ValueError が発生すること。"""
        drafter = AiDrafter(llm_client=_InvalidYamlClient())
        with pytest.raises(ValueError, match="YAML パース"):
            drafter.draft("テスト仕様")

    def test_empty_response_raises_error(self) -> None:
        """LLM が空のレスポンスを返した場合に ValueError が発生すること。"""
        drafter = AiDrafter(llm_client=_EmptyResponseClient())
        with pytest.raises(ValueError, match="空の YAML"):
            drafter.draft("テスト仕様")

    def test_missing_fields_raises_error(self) -> None:
        """必須フィールドが欠けた YAML で ValueError が発生すること。"""
        drafter = AiDrafter(llm_client=_MissingFieldsClient())
        with pytest.raises(ValueError, match="スキーマ検証"):
            drafter.draft("テスト仕様")

    def test_prompt_template_built_correctly(self) -> None:
        """プロンプトテンプレートが正しく構築されること。"""
        client = _PromptCapturingClient()
        drafter = AiDrafter(llm_client=client)
        spec = "ユーザーがログインできることを確認する"
        drafter.draft(spec)

        # システムプロンプトが DRAFT_SYSTEM_PROMPT と一致
        assert client.last_system_prompt == DRAFT_SYSTEM_PROMPT
        # ユーザープロンプトに仕様テキストが含まれる
        assert spec in client.last_user_prompt

    def test_custom_client_with_vars(self) -> None:
        """カスタムクライアントで vars を含む Scenario が生成されること。"""
        client = _ValidYamlClient()
        drafter = AiDrafter(llm_client=client)
        scenario = drafter.draft("管理者ログインテスト")
        assert "user" in scenario.vars
        assert scenario.vars["user"] == "admin"

    def test_llm_client_protocol_compliance(self) -> None:
        """LlmClient Protocol に準拠したオブジェクトが受け入れられること。"""
        assert isinstance(_ValidYamlClient(), LlmClient)
        assert isinstance(_PromptCapturingClient(), LlmClient)


# ---------------------------------------------------------------------------
# TestAiExplainer
# ---------------------------------------------------------------------------

class TestAiExplainer:
    """AiExplainer のテストクラス。"""

    @pytest.fixture()
    def sample_scenario(self) -> Scenario:
        """テスト用の Scenario フィクスチャ。"""
        return Scenario(
            title="ログインフローのテスト",
            baseUrl="http://localhost:4200",
            vars={"email": "test@example.com"},
            steps=[
                {"goto": "http://localhost:4200/login"},
                {"fill": {"by": {"css": "#email"}, "value": "test@example.com"}},
                {"click": {"by": {"role": "button", "name": "ログイン"}}},
            ],
        )

    def test_default_stub_returns_explanation(self, sample_scenario: Scenario) -> None:
        """デフォルトスタブで説明テキストが返されること。"""
        explainer = AiExplainer()
        result = explainer.explain(sample_scenario)
        assert isinstance(result, str)

    def test_explanation_not_empty(self, sample_scenario: Scenario) -> None:
        """説明テキストが空でないこと。"""
        explainer = AiExplainer()
        result = explainer.explain(sample_scenario)
        assert len(result.strip()) > 0

    def test_explanation_contains_title(self, sample_scenario: Scenario) -> None:
        """Scenario のタイトルが説明に含まれること。"""
        explainer = AiExplainer()
        result = explainer.explain(sample_scenario)
        assert sample_scenario.title in result

    def test_custom_llm_client_for_explainer(self, sample_scenario: Scenario) -> None:
        """カスタム LLM クライアントを AiExplainer に注入できること。"""

        class _CustomExplainClient:
            def generate(self, system_prompt: str, user_prompt: str) -> str:
                return "カスタム説明: テストシナリオの概要です。"

        explainer = AiExplainer(llm_client=_CustomExplainClient())
        result = explainer.explain(sample_scenario)
        assert "カスタム説明" in result

    def test_empty_explanation_raises_error(self, sample_scenario: Scenario) -> None:
        """LLM が空の説明を返した場合に ValueError が発生すること。"""

        class _EmptyExplainClient:
            def generate(self, system_prompt: str, user_prompt: str) -> str:
                return ""

        explainer = AiExplainer(llm_client=_EmptyExplainClient())
        with pytest.raises(ValueError, match="空の説明"):
            explainer.explain(sample_scenario)
