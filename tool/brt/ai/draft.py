"""
AiDrafter — 自然言語仕様から YAML DSL Scenario を生成

LLM クライアントを Protocol で抽象化し、テスト時にはスタブを注入可能にする。
デフォルトのスタブクライアントは最小限の有効な YAML DSL を返す。
"""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from ruamel.yaml import YAML

from ..dsl.schema import Scenario
from .prompts import DRAFT_SYSTEM_PROMPT, DRAFT_USER_TEMPLATE

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# YAML パーサー（モジュール共有）
# ---------------------------------------------------------------------------

_yaml = YAML()
_yaml.preserve_quotes = True


# ---------------------------------------------------------------------------
# LLM クライアント Protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class LlmClient(Protocol):
    """LLM クライアントの抽象インターフェース。

    テスト時にスタブやモックを注入するための Protocol 定義。
    """

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """LLM にプロンプトを送信し、テキストレスポンスを返す。

        Args:
            system_prompt: システムプロンプト
            user_prompt: ユーザープロンプト

        Returns:
            LLM のテキストレスポンス
        """
        ...


# ---------------------------------------------------------------------------
# デフォルトスタブクライアント
# ---------------------------------------------------------------------------

class _StubLlmClient:
    """テスト用のスタブ LLM クライアント。

    最小限の有効な YAML DSL を返す。
    """

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """最小限の有効な YAML DSL を返す。

        Args:
            system_prompt: システムプロンプト（未使用）
            user_prompt: ユーザープロンプト（未使用）

        Returns:
            最小限の有効な YAML DSL 文字列
        """
        return (
            "title: サンプルテストシナリオ\n"
            "baseUrl: http://localhost:3000\n"
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
            '  - goto: http://localhost:3000/\n'
            "healing: off\n"
        )


# モジュールレベルのデフォルトスタブインスタンス
_default_stub_client = _StubLlmClient()


# ---------------------------------------------------------------------------
# AiDrafter 本体
# ---------------------------------------------------------------------------

class AiDrafter:
    """自然言語仕様から YAML DSL Scenario を生成するドラフター。

    LLM クライアントを注入可能にし、テスト時にはスタブを使用する。
    """

    def __init__(self, llm_client: LlmClient | None = None) -> None:
        """AiDrafter を初期化する。

        Args:
            llm_client: LLM クライアント。None の場合はデフォルトスタブを使用。
        """
        self._llm: LlmClient = llm_client or _default_stub_client

    def draft(self, spec_text: str) -> Scenario:
        """自然言語仕様から YAML DSL Scenario を生成する。

        Args:
            spec_text: 自然言語のテスト仕様

        Returns:
            生成された Scenario オブジェクト

        Raises:
            ValueError: LLM レスポンスが不正な YAML またはスキーマ検証に失敗した場合
        """
        # 1. プロンプトを構築
        system_prompt = DRAFT_SYSTEM_PROMPT
        user_prompt = self._build_user_prompt(spec_text)
        logger.info("ドラフト生成を開始: spec_text=%d文字", len(spec_text))

        # 2. LLM にプロンプトを送信
        raw_response = self._llm.generate(system_prompt, user_prompt)
        logger.debug("LLM レスポンス: %d文字", len(raw_response))

        # 3. レスポンスを YAML としてパース
        data = self._parse_yaml(raw_response)

        # 4. Pydantic スキーマで検証し Scenario を返す
        return self._validate_scenario(data)

    def _build_user_prompt(self, spec_text: str) -> str:
        """ユーザープロンプトを構築する。

        Args:
            spec_text: 自然言語のテスト仕様

        Returns:
            構築されたユーザープロンプト文字列
        """
        return DRAFT_USER_TEMPLATE.format(spec_text=spec_text)

    def _parse_yaml(self, raw_yaml: str) -> dict:
        """YAML 文字列をパースして辞書に変換する。

        Args:
            raw_yaml: YAML 文字列

        Returns:
            パース結果の辞書

        Raises:
            ValueError: YAML パースに失敗した場合
        """
        import io

        try:
            data = _yaml.load(io.StringIO(raw_yaml))
        except Exception as e:
            logger.error("YAML パースエラー: %s", e)
            raise ValueError(f"LLM レスポンスの YAML パースに失敗しました: {e}") from e

        if data is None:
            raise ValueError("LLM レスポンスが空の YAML です")

        # ruamel.yaml の CommentedMap を通常の dict に変換
        return self._to_plain_dict(data)

    def _validate_scenario(self, data: dict) -> Scenario:
        """辞書データを Pydantic Scenario モデルで検証する。

        Args:
            data: 検証対象の辞書データ

        Returns:
            検証済みの Scenario オブジェクト

        Raises:
            ValueError: スキーマ検証に失敗した場合
        """
        try:
            scenario = Scenario(**data)
        except Exception as e:
            logger.error("スキーマ検証エラー: %s", e)
            raise ValueError(f"Scenario スキーマ検証に失敗しました: {e}") from e

        logger.info("ドラフト生成完了: title=%s", scenario.title)
        return scenario

    @staticmethod
    def _to_plain_dict(data: object) -> object:
        """ruamel.yaml の CommentedMap/CommentedSeq を通常の dict/list に再帰変換する。

        Args:
            data: 変換対象のデータ

        Returns:
            通常の dict/list に変換されたデータ
        """
        if isinstance(data, dict):
            return {key: AiDrafter._to_plain_dict(value) for key, value in data.items()}
        if isinstance(data, list):
            return [AiDrafter._to_plain_dict(item) for item in data]
        return data
