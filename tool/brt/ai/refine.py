"""
AiRefiner — YAML DSL Scenario の改善

既存の Scenario を LLM に送信し、改善された Scenario を返す。
secret: true フラグの保持を厳密に検証する。
"""

from __future__ import annotations

import io
import logging

from ruamel.yaml import YAML

from ..dsl.schema import Scenario
from .draft import LlmClient, _StubLlmClient
from .prompts import REFINE_SYSTEM_PROMPT, REFINE_USER_TEMPLATE

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# YAML パーサー（モジュール共有）
# ---------------------------------------------------------------------------

_yaml = YAML()
_yaml.preserve_quotes = True


# ---------------------------------------------------------------------------
# リファイン用スタブクライアント
# ---------------------------------------------------------------------------

class _RefineStubLlmClient:
    """リファイン用のスタブ LLM クライアント。

    入力された YAML をそのまま返す（改善なし）。
    テスト時に secret フラグ保持等の検証に使用する。
    """

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """入力された YAML をそのまま返す。

        ユーザープロンプトから YAML 部分を抽出して返す。

        Args:
            system_prompt: システムプロンプト（未使用）
            user_prompt: ユーザープロンプト（YAML を含む）

        Returns:
            抽出された YAML 文字列
        """
        # ユーザープロンプトから「現在のシナリオ:」以降の YAML を抽出
        marker = "現在のシナリオ:\n"
        idx = user_prompt.find(marker)
        if idx >= 0:
            return user_prompt[idx + len(marker):]
        # マーカーが見つからない場合はそのまま返す
        return user_prompt


# モジュールレベルのデフォルトスタブインスタンス
_default_refine_stub = _RefineStubLlmClient()


# ---------------------------------------------------------------------------
# AiRefiner 本体
# ---------------------------------------------------------------------------

class AiRefiner:
    """YAML DSL Scenario を改善するリファイナー。

    LLM クライアントを注入可能にし、テスト時にはスタブを使用する。
    refine 後も secret: true フラグが保持されることを検証する。
    """

    def __init__(self, llm_client: LlmClient | None = None) -> None:
        """AiRefiner を初期化する。

        Args:
            llm_client: LLM クライアント。None の場合はデフォルトスタブを使用。
        """
        self._llm: LlmClient = llm_client or _default_refine_stub

    def refine(self, scenario: Scenario) -> Scenario:
        """YAML DSL Scenario を改善する。

        Args:
            scenario: 改善対象の Scenario

        Returns:
            改善された Scenario オブジェクト

        Raises:
            ValueError: LLM レスポンスが不正、またはsecretフラグが失われた場合
        """
        # 1. Scenario を YAML 文字列に変換
        scenario_yaml = self._scenario_to_yaml(scenario)

        # 2. 改善前の secret フラグ数を記録
        original_secret_count = self._count_secret_flags(scenario)
        logger.info(
            "リファイン開始: title=%s, secret数=%d",
            scenario.title,
            original_secret_count,
        )

        # 3. プロンプトを構築
        system_prompt = REFINE_SYSTEM_PROMPT
        user_prompt = REFINE_USER_TEMPLATE.format(scenario_yaml=scenario_yaml)

        # 4. LLM にプロンプトを送信
        raw_response = self._llm.generate(system_prompt, user_prompt)
        logger.debug("LLM レスポンス: %d文字", len(raw_response))

        # 5. レスポンスを YAML としてパース
        data = self._parse_yaml(raw_response)

        # 6. Pydantic スキーマで検証
        refined = self._validate_scenario(data)

        # 7. secret フラグの保持を検証
        refined_secret_count = self._count_secret_flags(refined)
        if refined_secret_count < original_secret_count:
            raise ValueError(
                f"secret フラグが失われました: "
                f"改善前={original_secret_count}, 改善後={refined_secret_count}"
            )

        logger.info("リファイン完了: title=%s", refined.title)
        return refined

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

    def _parse_yaml(self, raw_yaml: str) -> dict:
        """YAML 文字列をパースして辞書に変換する。

        Args:
            raw_yaml: YAML 文字列

        Returns:
            パース結果の辞書

        Raises:
            ValueError: YAML パースに失敗した場合
        """
        try:
            data = _yaml.load(io.StringIO(raw_yaml))
        except Exception as e:
            logger.error("YAML パースエラー: %s", e)
            raise ValueError(f"LLM レスポンスの YAML パースに失敗しました: {e}") from e

        if data is None:
            raise ValueError("LLM レスポンスが空の YAML です")

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
            return Scenario(**data)
        except Exception as e:
            logger.error("スキーマ検証エラー: %s", e)
            raise ValueError(f"Scenario スキーマ検証に失敗しました: {e}") from e

    @staticmethod
    def _count_secret_flags(scenario: Scenario) -> int:
        """Scenario 内の secret: true フラグの数をカウントする。

        steps 配列内の各ステップ辞書を再帰的に走査し、
        secret: true の出現回数を返す。

        Args:
            scenario: カウント対象の Scenario

        Returns:
            secret: true の数
        """
        count = 0
        for step in scenario.steps:
            count += AiRefiner._count_secret_in_dict(step)
        return count

    @staticmethod
    def _count_secret_in_dict(d: object) -> int:
        """辞書を再帰的に走査し secret: true の数をカウントする。

        Args:
            d: 走査対象のデータ

        Returns:
            secret: true の数
        """
        if isinstance(d, dict):
            count = 0
            for key, value in d.items():
                if key == "secret" and value is True:
                    count += 1
                else:
                    count += AiRefiner._count_secret_in_dict(value)
            return count
        if isinstance(d, list):
            return sum(AiRefiner._count_secret_in_dict(item) for item in d)
        return 0

    @staticmethod
    def _to_plain_dict(data: object) -> object:
        """ruamel.yaml の CommentedMap/CommentedSeq を通常の dict/list に再帰変換する。

        Args:
            data: 変換対象のデータ

        Returns:
            通常の dict/list に変換されたデータ
        """
        if isinstance(data, dict):
            return {key: AiRefiner._to_plain_dict(value) for key, value in data.items()}
        if isinstance(data, list):
            return [AiRefiner._to_plain_dict(item) for item in data]
        return data
