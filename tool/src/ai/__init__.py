"""
AI Authoring モジュール

自然言語からの YAML DSL 生成・改善・説明を提供する。

- AiDrafter: 自然言語仕様から Scenario を生成
- AiRefiner: 既存 Scenario を改善
- AiExplainer: Scenario のアウトラインを自然言語で生成
- LlmClient: LLM クライアントの Protocol 定義
"""

from .draft import AiDrafter, LlmClient  # noqa: F401
from .explain import AiExplainer  # noqa: F401
from .refine import AiRefiner  # noqa: F401

__all__ = [
    "AiDrafter",
    "AiRefiner",
    "AiExplainer",
    "LlmClient",
]
