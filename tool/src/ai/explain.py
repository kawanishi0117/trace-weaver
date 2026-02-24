"""
AiExplainer — YAML DSL Scenario からアウトライン（説明）を生成

Scenario を自然言語のアウトラインに変換する。
LLM クライアントを Protocol で抽象化し、テスト時にはスタブを注入可能にする。
"""

from __future__ import annotations

import io
import logging

from ruamel.yaml import YAML

from ..dsl.schema import Scenario
from .draft import LlmClient
from .prompts import EXPLAIN_SYSTEM_PROMPT, EXPLAIN_USER_TEMPLATE

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# YAML パーサー（モジュール共有）
# ---------------------------------------------------------------------------

_yaml = YAML()
_yaml.preserve_quotes = True


# ---------------------------------------------------------------------------
# 説明用スタブクライアント
# ---------------------------------------------------------------------------

class _ExplainStubLlmClient:
    """説明生成用のスタブ LLM クライアント。

    Scenario のタイトルとステップ数を含む簡易説明を返す。
    """

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Scenario の簡易説明を返す。

        ユーザープロンプトから YAML を抽出し、タイトルを含む説明を生成する。

        Args:
            system_prompt: システムプロンプト（未使用）
            user_prompt: ユーザープロンプト（YAML を含む）

        Returns:
            簡易説明テキスト
        """
        # ユーザープロンプトから YAML を抽出してタイトルを取得
        marker = "シナリオ:\n"
        idx = user_prompt.find(marker)
        yaml_text = user_prompt[idx + len(marker):] if idx >= 0 else ""

        title = "不明なシナリオ"
        try:
            data = _yaml.load(io.StringIO(yaml_text))
            if data and isinstance(data, dict):
                title = data.get("title", title)
        except Exception:
            pass

        return (
            f"# {title}\n\n"
            f"このテストシナリオは「{title}」を検証します。\n\n"
            "## 概要\n"
            "テスト対象のアプリケーションに対して、"
            "一連の操作と検証を実行します。\n"
        )


# モジュールレベルのデフォルトスタブインスタンス
_default_explain_stub = _ExplainStubLlmClient()


# ---------------------------------------------------------------------------
# AiExplainer 本体
# ---------------------------------------------------------------------------

class AiExplainer:
    """YAML DSL Scenario からアウトライン（説明）を生成するエクスプレイナー。

    LLM クライアントを注入可能にし、テスト時にはスタブを使用する。
    """

    def __init__(self, llm_client: LlmClient | None = None) -> None:
        """AiExplainer を初期化する。

        Args:
            llm_client: LLM クライアント。None の場合はデフォルトスタブを使用。
        """
        self._llm: LlmClient = llm_client or _default_explain_stub

    def explain(self, scenario: Scenario) -> str:
        """YAML DSL Scenario からアウトライン（章立てと要点）を自然言語で生成する。

        Args:
            scenario: 説明対象の Scenario

        Returns:
            自然言語のアウトラインテキスト

        Raises:
            ValueError: 説明生成に失敗した場合
        """
        # 1. Scenario を YAML 文字列に変換
        scenario_yaml = self._scenario_to_yaml(scenario)
        logger.info("説明生成を開始: title=%s", scenario.title)

        # 2. プロンプトを構築
        system_prompt = EXPLAIN_SYSTEM_PROMPT
        user_prompt = EXPLAIN_USER_TEMPLATE.format(scenario_yaml=scenario_yaml)

        # 3. LLM にプロンプトを送信
        explanation = self._llm.generate(system_prompt, user_prompt)
        logger.debug("説明テキスト: %d文字", len(explanation))

        if not explanation or not explanation.strip():
            raise ValueError("LLM から空の説明テキストが返されました")

        logger.info("説明生成完了: title=%s", scenario.title)
        return explanation

    def _scenario_to_yaml(self, scenario: Scenario) -> str:
        """Scenario を YAML 文字列に変換する。

        Args:
            scenario: 変換対象の Scenario

        Returns:
            YAML 文字列
        """
        data = scenario.model_dump(mode="python")
        stream = io.StringIO()
        _yaml.dump(data, stream)
        return stream.getvalue()
