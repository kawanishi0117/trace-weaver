"""
ステップレジストリ — ステップハンドラの登録・検索・一覧

プラグインアーキテクチャにより、標準ステップとカスタムステップを
同一のインターフェースで管理する。

主な構成:
  - StepHandler Protocol: ステップハンドラの共通インターフェース
  - StepContext: ステップ実行時のコンテキスト情報
  - StepInfo: ステップのメタ情報（名前、説明、カテゴリ）
  - StepRegistry: ステップハンドラの登録・検索・一覧

要件 5.8: プラグイン方式でカスタムステップの追加を可能にする
要件 15.1: カスタムステップの登録を受け付け、標準ステップと同一インターフェースで実行
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional, Protocol, runtime_checkable

from pydantic import BaseModel

if TYPE_CHECKING:
    from playwright.async_api import Page

    from ..core.selector import SelectorResolver
    from ..dsl.variables import VariableExpander

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ステップ実行コンテキスト
# ---------------------------------------------------------------------------

@dataclass
class StepContext:
    """ステップ実行時のコンテキスト情報。

    各ステップハンドラの execute() に渡され、
    セレクタ解決・変数展開・成果物管理などの共通機能へのアクセスを提供する。

    Attributes:
        selector_resolver: セレクタを Playwright Locator に変換するリゾルバ
        variable_expander: ${env.X} / ${vars.X} の変数展開エンジン
        artifacts_manager: 成果物管理（スクリーンショット等）。None の場合は成果物なし
        console_errors: ブラウザコンソールに出力されたエラーメッセージのリスト
    """

    selector_resolver: SelectorResolver
    variable_expander: VariableExpander
    artifacts_manager: Optional[object] = None
    console_errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# ステップメタ情報
# ---------------------------------------------------------------------------

@dataclass
class StepInfo:
    """ステップのメタ情報。

    list_all() で返される各ステップの説明情報。
    CLI の list-steps コマンドで一覧表示に使用する。

    Attributes:
        name: ステップ名（YAML DSL で使用するキー名）
        description: ステップの説明文
        category: カテゴリ（navigation, action, wait, validation, retrieval, debug, session, high-level）
    """

    name: str
    description: str
    category: str


# ---------------------------------------------------------------------------
# ステップハンドラ Protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class StepHandler(Protocol):
    """ステップハンドラの共通インターフェース。

    全てのステップハンドラ（標準・高レベル・カスタム）はこの Protocol を満たす必要がある。
    StepRegistry に登録するには execute() と get_schema() の両メソッドを実装すること。
    """

    async def execute(self, page: Page, params: dict, context: StepContext) -> None:
        """ステップを実行する。

        Args:
            page: Playwright の Page オブジェクト
            params: ステップパラメータ辞書（YAML DSL から取得）
            context: ステップ実行コンテキスト
        """
        ...

    def get_schema(self) -> type[BaseModel]:
        """パラメータの Pydantic スキーマクラスを返す。

        validate / lint でパラメータ検証に使用される。

        Returns:
            Pydantic BaseModel のサブクラス
        """
        ...


# ---------------------------------------------------------------------------
# StepRegistry 本体
# ---------------------------------------------------------------------------

class StepRegistry:
    """ステップハンドラの登録・検索・一覧を管理するレジストリ。

    プラグイン方式により、標準ステップとカスタムステップを
    同一のインターフェースで管理する。

    使用例::

        registry = StepRegistry()
        registry.register("click", ClickHandler(), info=StepInfo(...))
        handler = registry.get("click")
        all_steps = registry.list_all()
    """

    def __init__(self) -> None:
        """空のレジストリを初期化する。"""
        self._handlers: dict[str, StepHandler] = {}
        self._info: dict[str, StepInfo] = {}

    def register(
        self,
        name: str,
        handler: StepHandler,
        *,
        info: Optional[StepInfo] = None,
    ) -> None:
        """ステップハンドラを登録する。

        同名のハンドラが既に登録されている場合は上書きする（警告を出力）。

        Args:
            name: ステップ名（YAML DSL で使用するキー名）
            handler: ステップハンドラインスタンス
            info: ステップのメタ情報。None の場合はデフォルト値を使用

        Raises:
            TypeError: handler が StepHandler Protocol を満たさない場合
        """
        # Protocol 準拠チェック
        if not isinstance(handler, StepHandler):
            raise TypeError(
                f"handler は StepHandler Protocol を満たす必要があります: "
                f"{type(handler).__name__}"
            )

        # 既存ハンドラの上書き警告
        if name in self._handlers:
            logger.warning(
                "ステップ '%s' のハンドラを上書きします（既存: %s → 新規: %s）",
                name,
                type(self._handlers[name]).__name__,
                type(handler).__name__,
            )

        self._handlers[name] = handler

        # メタ情報の登録
        if info is not None:
            self._info[name] = info
        elif name not in self._info:
            # デフォルトのメタ情報を生成
            self._info[name] = StepInfo(
                name=name,
                description=f"{name} ステップ",
                category="unknown",
            )

        logger.debug("ステップ '%s' を登録しました: %s", name, type(handler).__name__)

    def get(self, name: str) -> StepHandler:
        """名前でステップハンドラを取得する。

        Args:
            name: ステップ名

        Returns:
            登録済みのステップハンドラ

        Raises:
            KeyError: 指定名のハンドラが未登録の場合
        """
        if name not in self._handlers:
            registered = ", ".join(sorted(self._handlers.keys()))
            raise KeyError(
                f"ステップ '{name}' は登録されていません。"
                f"登録済みステップ: [{registered}]"
            )
        return self._handlers[name]

    def list_all(self) -> list[StepInfo]:
        """登録済み全ステップのメタ情報を返す。

        ステップ名のアルファベット順でソートして返す。

        Returns:
            StepInfo のリスト
        """
        return sorted(self._info.values(), key=lambda s: s.name)

    def has(self, name: str) -> bool:
        """指定名のステップが登録されているかを返す。

        Args:
            name: ステップ名

        Returns:
            登録済みの場合は True
        """
        return name in self._handlers

    @property
    def names(self) -> list[str]:
        """登録済み全ステップ名をソート済みリストで返す。"""
        return sorted(self._handlers.keys())
