"""
セレクタリゾルバ — By セレクタを Playwright Locator に変換・解決

YAML DSL の By セレクタ（testId, role, label, placeholder, css, text, any）を
Playwright の Locator オブジェクトに変換する。

主な機能:
  - 単一セレクタの解決（_resolve_single）
  - any フォールバック: 候補リストを上から順に試行（_resolve_any）
  - Healing（safe モード）: セレクタ不一致時の自己修復（_try_healing）
  - strict: true をデフォルトで適用

要件 4.1: testId, role(+name), label, placeholder, css, text, any のセレクタ種別
要件 4.2: strict: true をデフォルトとし、複数要素ヒット時に即座にエラー
要件 4.3: any フォールバック — 上から順に試行し、visible かつ strict を満たす候補を採用
要件 4.4: any 全候補失敗時のエラーメッセージ（全候補情報と失敗理由を含む）
要件 7.10: healing: safe — セレクタ不一致時に再解決を試行
要件 7.11: healing: off — セレクタ不一致時に即座にエラー
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from ..dsl.schema import (
    AnySelector,
    BySelector,
    CssSelector,
    LabelSelector,
    PlaceholderSelector,
    RoleSelector,
    SingleSelector,
    TestIdSelector,
    TextSelector,
)

if TYPE_CHECKING:
    from playwright.async_api import FrameLocator, Locator, Page

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# エラー定義
# ---------------------------------------------------------------------------

class SelectorResolutionError(Exception):
    """セレクタ解決に失敗した場合のエラー。"""


# ---------------------------------------------------------------------------
# any フォールバック失敗時の候補情報
# ---------------------------------------------------------------------------

@dataclass
class CandidateFailure:
    """any フォールバックで失敗した候補の情報。

    Attributes:
        index: 候補リスト内のインデックス（0始まり）
        selector_desc: セレクタの説明文字列
        reason: 失敗理由
    """

    index: int
    selector_desc: str
    reason: str


# ---------------------------------------------------------------------------
# SelectorResolver 本体
# ---------------------------------------------------------------------------

class SelectorResolver:
    """By セレクタを Playwright Locator に変換・解決する。

    healing モードに応じてセレクタ不一致時の動作を切り替える:
      - off: 即座にエラー（デフォルト）
      - safe: testId / role / name / label の範囲で再解決を試行
    """

    def __init__(self, healing: str = "off") -> None:
        """SelectorResolver を初期化する。

        Args:
            healing: セレクタ自己修復モード（"off" または "safe"）
        """
        if healing not in ("off", "safe"):
            raise ValueError(f"healing は 'off' または 'safe' を指定してください: {healing}")
        self._healing = healing


    # -------------------------------------------------------------------
    # パブリック API
    # -------------------------------------------------------------------

    async def resolve(self, page: Page, by: BySelector, frame: Optional[str] = None) -> Locator:
        """セレクタを解決し、Playwright Locator を返す。

        AnySelector の場合はフォールバック処理を行い、
        それ以外は単一セレクタとして解決する。
        frame が指定されている場合は iframe 内で解決する。

        Args:
            page: Playwright の Page オブジェクト
            by: 解決対象の BySelector
            frame: iframe セレクタ（iframe 内操作時）

        Returns:
            解決された Playwright Locator

        Raises:
            SelectorResolutionError: セレクタ解決に失敗した場合
        """
        # iframe 内操作の場合、content_frame を取得して target とする
        # iframe がリロードされている可能性があるため、読み込み完了を待機する
        target = page
        if frame is not None:
            frame_locator = page.frame_locator(frame)
            # iframe 内の body が attached になるまで待機（リロード対策）
            try:
                await frame_locator.locator("body").wait_for(
                    state="attached", timeout=10_000,
                )
            except Exception:
                logger.warning(
                    "iframe '%s' の読み込み待機がタイムアウトしました。続行します。",
                    frame,
                )
            target = frame_locator

        if isinstance(by, AnySelector):
            return await self._resolve_any(target, by.any)

        # 単一セレクタの解決
        try:
            return self._resolve_single(target, by)
        except Exception as exc:
            # healing: safe の場合は再解決を試行
            if self._healing == "safe":
                logger.info(
                    "セレクタ解決に失敗しました。healing: safe モードで再解決を試行します: %s",
                    exc,
                )
                healed = await self._try_healing(target, by)
                if healed is not None:
                    return healed
            raise SelectorResolutionError(
                f"セレクタの解決に失敗しました: {_describe_selector(by)} — {exc}"
            ) from exc

    # -------------------------------------------------------------------
    # 単一セレクタの解決
    # -------------------------------------------------------------------

    def _resolve_single(self, page: Page | FrameLocator, selector: SingleSelector) -> Locator:
        """単一セレクタを Playwright Locator に変換する。

        セレクタ種別に応じて対応する Playwright メソッドを呼び出す。
        strict フィールドが True（デフォルト）の場合、Locator に strict オプションを適用する。

        Args:
            page: Playwright の Page オブジェクト
            selector: 解決対象の単一セレクタ

        Returns:
            Playwright Locator

        Raises:
            SelectorResolutionError: 未知のセレクタ種別の場合
        """
        if isinstance(selector, TestIdSelector):
            # data-testid 属性によるセレクタ
            return page.get_by_test_id(selector.testId)

        if isinstance(selector, RoleSelector):
            # ARIA ロールによるセレクタ（name, exact は補助条件）
            kwargs: dict = {}
            if selector.name is not None:
                kwargs["name"] = selector.name
            if selector.exact is not None:
                kwargs["exact"] = selector.exact
            return page.get_by_role(selector.role, **kwargs)

        if isinstance(selector, LabelSelector):
            # ラベルテキストによるセレクタ
            return page.get_by_label(selector.label)

        if isinstance(selector, PlaceholderSelector):
            # プレースホルダーテキストによるセレクタ
            return page.get_by_placeholder(selector.placeholder)

        if isinstance(selector, CssSelector):
            # CSS セレクタ（text 補助条件あり）
            if selector.text is not None:
                return page.locator(selector.css, has_text=selector.text)
            return page.locator(selector.css)

        if isinstance(selector, TextSelector):
            # テキスト内容によるセレクタ
            return page.get_by_text(selector.text)

        raise SelectorResolutionError(
            f"未知のセレクタ種別です: {type(selector).__name__}"
        )


    # -------------------------------------------------------------------
    # any フォールバック
    # -------------------------------------------------------------------

    async def _resolve_any(
        self, page: Page | FrameLocator, candidates: list[SingleSelector]
    ) -> Locator:
        """any フォールバック: 候補リストを上から順に試行する。

        各候補について Locator を生成し、visible かつ strict（1件一致）を
        満たす最初の候補を採用する。条件を満たした時点で後続候補は試行しない。

        全候補が条件を満たさなかった場合は、試行した全候補のセレクタ情報と
        各候補の失敗理由を含むエラーメッセージを出力する。

        Args:
            page: Playwright の Page オブジェクト
            candidates: セレクタ候補リスト（上から順に試行）

        Returns:
            条件を満たした最初の候補の Locator

        Raises:
            SelectorResolutionError: 全候補が条件を満たさなかった場合
        """
        failures: list[CandidateFailure] = []

        for idx, candidate in enumerate(candidates):
            desc = _describe_selector(candidate)
            try:
                locator = self._resolve_single(page, candidate)

                # visible かつ strict（1件一致）を確認
                count = await locator.count()
                if count == 0:
                    failures.append(CandidateFailure(
                        index=idx,
                        selector_desc=desc,
                        reason="要素が見つかりません（0件ヒット）",
                    ))
                    continue

                if count > 1:
                    failures.append(CandidateFailure(
                        index=idx,
                        selector_desc=desc,
                        reason=f"strict モード違反: {count} 件の要素がヒットしました",
                    ))
                    continue

                # 1件ヒット — visible かどうかを確認
                if not await locator.is_visible():
                    failures.append(CandidateFailure(
                        index=idx,
                        selector_desc=desc,
                        reason="要素は存在しますが非表示です",
                    ))
                    continue

                # 条件を満たした — この候補を採用
                logger.debug(
                    "any フォールバック: 候補 %d (%s) が条件を満たしました", idx, desc
                )
                return locator

            except SelectorResolutionError:
                # _resolve_single が未知のセレクタ種別で失敗した場合
                failures.append(CandidateFailure(
                    index=idx,
                    selector_desc=desc,
                    reason="セレクタの解決に失敗しました",
                ))
            except Exception as exc:  # noqa: BLE001
                failures.append(CandidateFailure(
                    index=idx,
                    selector_desc=desc,
                    reason=str(exc),
                ))

        # 全候補が失敗 — 詳細なエラーメッセージを生成
        details = "\n".join(
            f"  [{f.index}] {f.selector_desc}: {f.reason}"
            for f in failures
        )
        raise SelectorResolutionError(
            f"any フォールバック: 全 {len(candidates)} 候補が条件を満たしませんでした。\n"
            f"試行結果:\n{details}"
        )


    # -------------------------------------------------------------------
    # Healing（safe モード）
    # -------------------------------------------------------------------

    async def _try_healing(
        self, page: Page | FrameLocator, original: BySelector
    ) -> Optional[Locator]:
        """safe モード時のセレクタ自己修復を試行する。

        元のセレクタが失敗した場合に、testId / role / name / label の範囲で
        代替セレクタによる再解決を試みる。

        healing: off の場合はこのメソッドは呼ばれない（resolve 側で制御）。

        Args:
            page: Playwright の Page オブジェクト
            original: 元の（失敗した）BySelector

        Returns:
            再解決に成功した場合は Locator、失敗した場合は None
        """
        if self._healing != "safe":
            # healing: off の場合は即座に None を返す（呼び出し元でエラーにする）
            return None

        # 元のセレクタから healing 候補を生成
        healing_candidates = self._build_healing_candidates(original)

        if not healing_candidates:
            logger.debug("healing 候補が生成できませんでした: %s", _describe_selector(original))
            return None

        # 候補を順に試行
        for candidate in healing_candidates:
            try:
                locator = self._resolve_single(page, candidate)
                count = await locator.count()
                if count == 1 and await locator.is_visible():
                    logger.info(
                        "healing 成功: %s → %s",
                        _describe_selector(original),
                        _describe_selector(candidate),
                    )
                    return locator
            except Exception:  # noqa: BLE001
                continue

        logger.debug(
            "healing: 全候補が失敗しました（元セレクタ: %s）", _describe_selector(original)
        )
        return None

    # -------------------------------------------------------------------
    # Healing 候補の生成
    # -------------------------------------------------------------------

    def _build_healing_candidates(
        self, original: BySelector
    ) -> list[SingleSelector]:
        """元のセレクタから healing 用の代替候補リストを生成する。

        testId / role(+name) / label の範囲で、元のセレクタとは異なる
        種別の候補を生成する。元のセレクタと同じ種別は除外する。

        Args:
            original: 元の BySelector

        Returns:
            healing 候補の SingleSelector リスト
        """
        candidates: list[SingleSelector] = []

        # 元のセレクタから情報を抽出
        if isinstance(original, TestIdSelector):
            # testId が失敗 → role / label で試行
            candidates.append(RoleSelector(role="button", name=original.testId))
            candidates.append(LabelSelector(label=original.testId))
        elif isinstance(original, RoleSelector):
            # role が失敗 → testId / label で試行
            if original.name:
                candidates.append(TestIdSelector(testId=original.name))
                candidates.append(LabelSelector(label=original.name))
        elif isinstance(original, LabelSelector):
            # label が失敗 → testId / role で試行
            candidates.append(TestIdSelector(testId=original.label))
            candidates.append(RoleSelector(role="textbox", name=original.label))
        elif isinstance(original, CssSelector):
            # css が失敗 → text 補助条件があれば text / label で試行
            if original.text:
                candidates.append(TextSelector(text=original.text))
                candidates.append(LabelSelector(label=original.text))
        elif isinstance(original, TextSelector):
            # text が失敗 → label で試行
            candidates.append(LabelSelector(label=original.text))
        elif isinstance(original, PlaceholderSelector):
            # placeholder が失敗 → label / testId で試行
            candidates.append(LabelSelector(label=original.placeholder))
            candidates.append(TestIdSelector(testId=original.placeholder))

        return candidates


# ---------------------------------------------------------------------------
# ヘルパー関数
# ---------------------------------------------------------------------------

def _describe_selector(selector: BySelector | SingleSelector) -> str:
    """セレクタの人間可読な説明文字列を生成する。

    エラーメッセージやログで使用する。

    Args:
        selector: 説明対象のセレクタ

    Returns:
        セレクタの説明文字列
    """
    if isinstance(selector, TestIdSelector):
        return f"testId='{selector.testId}'"
    if isinstance(selector, RoleSelector):
        if selector.name:
            return f"role='{selector.role}', name='{selector.name}'"
        return f"role='{selector.role}'"
    if isinstance(selector, LabelSelector):
        return f"label='{selector.label}'"
    if isinstance(selector, PlaceholderSelector):
        return f"placeholder='{selector.placeholder}'"
    if isinstance(selector, CssSelector):
        if selector.text:
            return f"css='{selector.css}', text='{selector.text}'"
        return f"css='{selector.css}'"
    if isinstance(selector, TextSelector):
        return f"text='{selector.text}'"
    if isinstance(selector, AnySelector):
        inner = ", ".join(_describe_selector(c) for c in selector.any)
        return f"any=[{inner}]"
    return f"unknown({type(selector).__name__})"
