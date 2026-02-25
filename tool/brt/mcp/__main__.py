"""
brt MCP Server CLI エントリポイント

python -m src.mcp で MCP サーバーを起動する。
CLI 引数と環境変数でサーバー設定を制御できる。

使用例:
  python -m src.mcp                          # デフォルト設定で起動
  python -m src.mcp --headless               # ヘッドレスモード
  python -m src.mcp --video always           # 常に動画録画
  python -m src.mcp --viewport 1920x1080     # ビューポートサイズ指定

環境変数:
  BRT_HEADED=false                           # ヘッドレスモード
  BRT_VIDEO_MODE=always                      # 常に動画録画
  BRT_ARTIFACTS_DIR=output                   # 成果物ディレクトリ変更
"""

from __future__ import annotations

from .config import apply_cli_args, build_cli_parser, load_config_from_env
from .server import create_server

# 環境変数 → CLI 引数の順で設定を構築
_config = load_config_from_env()
_parser = build_cli_parser()
_args = _parser.parse_args()
_config = apply_cli_args(_config, _args)

# サーバー生成・起動
server = create_server(config=_config)
server.run()
