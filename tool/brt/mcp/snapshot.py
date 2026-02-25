"""
Snapshot — アクセシビリティスナップショットの解析・ref 管理

Playwright の aria_snapshot() が返す YAML 形式のアクセシビリティツリーを解析し、
各インタラクティブ要素に ref 番号を付与する。
AI エージェントは ref 番号で操作対象を指定できる。

主な機能:
  - ARIA スナップショット YAML の解析
  - インタラクティブ要素の抽出と ref 番号付与
  - ref 番号による要素検索
  - AI 向けフォーマット文字列の生成
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# インタラクティブ要素として抽出するロール一覧
# ---------------------------------------------------------------------------

_INTERACTIVE_ROLES = frozenset({
    "button", "link", "textbox", "checkbox", "radio",
    "combobox", "listbox", "menuitem", "option", "searchbox",
    "slider", "spinbutton", "switch", "tab", "treeitem",
    "heading", "img", "cell", "row", "columnheader",
})


# ---------------------------------------------------------------------------
# SnapshotElement データクラス
# ---------------------------------------------------------------------------

@dataclass
class SnapshotElement:
    """アクセシビリティスナップショットから抽出された要素。

    Attributes:
        ref: AI が操作対象を指定するための参照番号
        role: ARIA ロール（button, textbox, link 等）
        name: アクセシブルネーム
        level: ツリー内のネストレベル
        attributes: 追加属性（level, checked 等）
    """

    ref: str
    role: str
    name: str = ""
    level: int = 0
    attributes: dict[str, str] = field(default_factory=dict)

    def display(self) -> str:
        """AI 向けの表示用文字列を生成する。

        Returns:
            "[ref] role \"name\"" 形式の文字列
        """
        parts = [f"[{self.ref}]", self.role]
        if self.name:
            parts.append(f'"{self.name}"')
        # 属性があれば追加
        for key, val in self.attributes.items():
            parts.append(f"[{key}={val}]")
        return " ".join(parts)


# ---------------------------------------------------------------------------
# ARIA スナップショット行の解析用正規表現
# ---------------------------------------------------------------------------

# "- role \"name\" [attr=val]" 形式の行を解析
_LINE_PATTERN = re.compile(
    r'^(\s*)-\s+'           # インデント + リストマーカー
    r'(\w+)'                # ロール名
    r'(?:\s+"([^"]*)")?'    # オプショナルな名前（ダブルクォート内）
    r'((?:\s+\[\w+=\w+\])*)'  # オプショナルな属性群
    r'\s*:?\s*$'            # 末尾（コロンはネスト開始）
)

# 属性 [key=value] の解析
_ATTR_PATTERN = re.compile(r'\[(\w+)=(\w+)\]')


# ---------------------------------------------------------------------------
# SnapshotParser 本体
# ---------------------------------------------------------------------------

class SnapshotParser:
    """ARIA スナップショットを解析し、ref 番号付き要素リストを管理する。"""

    def __init__(self) -> None:
        """SnapshotParser を初期化する。"""
        self._elements: list[SnapshotElement] = []

    def parse(self, aria_yaml: str) -> list[SnapshotElement]:
        """ARIA スナップショット YAML を解析し、要素リストを返す。

        Args:
            aria_yaml: Playwright aria_snapshot() の出力文字列

        Returns:
            ref 番号付きの SnapshotElement リスト
        """
        if not aria_yaml or not aria_yaml.strip():
            return []

        elements: list[SnapshotElement] = []
        ref_counter = 0

        for line in aria_yaml.splitlines():
            if not line.strip():
                continue

            match = _LINE_PATTERN.match(line)
            if not match:
                continue

            indent = match.group(1) or ""
            role = match.group(2)
            name = match.group(3) or ""
            attr_str = match.group(4) or ""

            # インタラクティブ要素のみ抽出
            if role not in _INTERACTIVE_ROLES:
                continue

            # 属性を解析
            attributes: dict[str, str] = {}
            for attr_match in _ATTR_PATTERN.finditer(attr_str):
                attributes[attr_match.group(1)] = attr_match.group(2)

            # ネストレベルを計算（インデント幅 / 2）
            nest_level = len(indent) // 2

            ref_counter += 1
            elem = SnapshotElement(
                ref=str(ref_counter),
                role=role,
                name=name,
                level=nest_level,
                attributes=attributes,
            )
            elements.append(elem)

        return elements

    def set_elements(self, elements: list[SnapshotElement]) -> None:
        """要素リストを設定する。

        Args:
            elements: 設定する要素リスト
        """
        self._elements = list(elements)

    def get_by_ref(self, ref: str) -> Optional[SnapshotElement]:
        """ref 番号で要素を検索する。

        Args:
            ref: 検索する ref 番号

        Returns:
            見つかった要素。見つからない場合は None
        """
        for elem in self._elements:
            if elem.ref == ref:
                return elem
        return None

    def format_for_ai(self) -> str:
        """AI 向けのフォーマット文字列を生成する。

        Returns:
            全要素の表示用文字列（改行区切り）
        """
        if not self._elements:
            return "(no interactive elements found)"

        lines = [elem.display() for elem in self._elements]
        return "\n".join(lines)
