"""
Recorder — AI ブラウザ操作の記録エンジン

MCP ツール経由で実行されたブラウザ操作を内部リストに蓄積し、
brt YAML DSL 形式の Scenario 辞書として出力する。

主な機能:
  - 操作ステップの追加（goto, click, fill 等）
  - セクション区切りの追加
  - Scenario 辞書への変換
  - YAML ファイルへの保存
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ruamel.yaml import YAML

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# デフォルトの artifacts 設定
# ---------------------------------------------------------------------------

_DEFAULT_ARTIFACTS: dict[str, Any] = {
    "screenshots": {
        "mode": "before_each_step",
        "format": "jpeg",
        "quality": 70,
    },
    "trace": {"mode": "on_failure"},
    "video": {"mode": "on_failure"},
}


# ---------------------------------------------------------------------------
# RecordedStep データクラス
# ---------------------------------------------------------------------------

@dataclass
class RecordedStep:
    """記録された1ステップの中間表現。

    Attributes:
        step_type: ステップ種別（goto, click, fill, section 等）
        params: ステップパラメータ辞書
        name: ステップ名（省略時は自動生成）
    """

    step_type: str
    params: dict[str, Any] = field(default_factory=dict)
    name: str = ""

    def to_dsl_dict(self) -> dict[str, Any]:
        """brt YAML DSL のステップ辞書形式に変換する。

        Returns:
            DSL ステップ辞書
        """
        # section は特殊形式
        if self.step_type == "section":
            return {"section": self.name}

        # 通常ステップ: params に name を付与
        result = dict(self.params)
        if self.name:
            result["name"] = self.name

        return {self.step_type: result}


# ---------------------------------------------------------------------------
# ステップ名の自動生成
# ---------------------------------------------------------------------------

# ステップ種別ごとの名前生成ルール
_STEP_INDEX_COUNTER: int = 0


def _auto_name(step_type: str, params: dict[str, Any], index: int) -> str:
    """ステップ名を自動生成する。

    Args:
        step_type: ステップ種別
        params: ステップパラメータ
        index: ステップのインデックス（0始まり）

    Returns:
        自動生成されたステップ名
    """
    prefix = f"{index + 1:04d}"

    if step_type == "goto":
        url = params.get("url", "")
        # URL からパス部分を抽出して名前に使用
        path_part = re.sub(r"https?://[^/]+", "", url)
        slug = re.sub(r"[^a-zA-Z0-9]", "-", path_part).strip("-") or "page"
        return f"{prefix}-goto-{slug}"

    # by セレクタから対象要素の情報を取得
    by = params.get("by", {})
    target = by.get("name", by.get("role", "element"))
    # 名前を安全な文字列に変換
    safe_target = re.sub(r"[^a-zA-Z0-9]", "-", str(target)).strip("-").lower()
    if not safe_target:
        safe_target = "element"

    return f"{prefix}-{step_type}-{safe_target}"


# ---------------------------------------------------------------------------
# Recorder 本体
# ---------------------------------------------------------------------------

class Recorder:
    """AI ブラウザ操作の記録エンジン。

    MCP ツール経由の操作を蓄積し、brt YAML DSL として出力する。

    Attributes:
        title: シナリオタイトル
        base_url: ベース URL
    """

    def __init__(self, title: str, base_url: str) -> None:
        """Recorder を初期化する。

        Args:
            title: シナリオタイトル
            base_url: ベース URL
        """
        self.title = title
        self.base_url = base_url
        self._steps: list[RecordedStep] = []

    @property
    def step_count(self) -> int:
        """記録済みステップ数を返す。"""
        return len(self._steps)

    def add_step(
        self,
        step_type: str,
        params: dict[str, Any],
        name: Optional[str] = None,
    ) -> None:
        """操作ステップを追加する。

        Args:
            step_type: ステップ種別（goto, click, fill 等）
            params: ステップパラメータ辞書
            name: ステップ名（省略時は自動生成）
        """
        if not name:
            name = _auto_name(step_type, params, len(self._steps))

        step = RecordedStep(step_type=step_type, params=params, name=name)
        self._steps.append(step)
        logger.info("ステップを記録しました: %s (%s)", step_type, name)

    def add_section(self, section_name: str) -> None:
        """セクション区切りを追加する。

        Args:
            section_name: セクション名
        """
        step = RecordedStep(step_type="section", name=section_name)
        self._steps.append(step)
        logger.info("セクションを追加しました: %s", section_name)

    def to_scenario_dict(self) -> dict[str, Any]:
        """記録内容を brt Scenario 辞書形式で出力する。

        Returns:
            Scenario 辞書（YAML DSL 互換）
        """
        steps = [step.to_dsl_dict() for step in self._steps]

        return {
            "title": self.title,
            "baseUrl": self.base_url,
            "vars": {},
            "artifacts": dict(_DEFAULT_ARTIFACTS),
            "hooks": {},
            "steps": steps,
            "healing": "off",
        }

    def save_yaml(self, path: Path) -> None:
        """記録内容を YAML ファイルとして保存する。

        Args:
            path: 出力先ファイルパス
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        yaml = YAML()
        yaml.default_flow_style = False

        scenario = self.to_scenario_dict()

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(scenario, f)

        logger.info("シナリオを保存しました: %s", path)

    def clear(self) -> None:
        """記録をクリアする。"""
        self._steps.clear()
        logger.info("記録をクリアしました")
