"""
recorder パッケージ — ハイライトなしブラウザ操作記録

Playwright codegen の代替として、赤いハイライト枠なしで
ブラウザ操作を記録し、Python スクリプトとして出力する。

主な機能:
  - BrowserRecorder: ブラウザ操作記録エンジン
  - RecordedAction: 記録されたアクションのデータクラス
  - ScriptWriter: 記録結果を Python スクリプトに変換
"""

from __future__ import annotations

from .recorder import BrowserRecorder, RecordedAction
from .script_writer import ScriptWriter

__all__ = ["BrowserRecorder", "RecordedAction", "ScriptWriter"]
