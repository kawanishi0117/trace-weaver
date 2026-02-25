"""
brt MCP Server パッケージ

AI エージェントがブラウザを操作し、操作を YAML DSL として自動記録する
MCP (Model Context Protocol) サーバーを提供する。

主な構成:
  - server: FastMCP サーバー本体（ライフサイクル管理）
  - tools_basic: 基本操作ツール（navigate, click, fill 等）
  - tools_highlevel: 高レベルステップツール（overlay, wijmo 等）
  - session: ブラウザセッション管理
  - recorder: 操作記録エンジン
  - snapshot: アクセシビリティスナップショット + ref 管理
  - selector_mapper: ref 番号 → brt セレクタ変換
  - locator_builder: by セレクタ辞書 → Playwright Locator 変換
"""

from __future__ import annotations


def create_server(config=None):  # type: ignore[no-untyped-def]
    """brt MCP サーバーを生成する（遅延インポート）。

    `python -m src.mcp.server` 実行時の RuntimeWarning を回避するため、
    server モジュールの import をここで遅延させる。

    Args:
        config: ServerConfig インスタンス（None で環境変数から読み込み）

    Returns:
        設定済みの FastMCP サーバーインスタンス
    """
    from .server import create_server as _create
    return _create(config=config)


__all__ = [
    "create_server",
]
