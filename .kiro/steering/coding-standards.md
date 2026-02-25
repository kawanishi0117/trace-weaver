---
inclusion: always
---

# コーディング規約 — brt プロジェクト

## 言語・環境

- Python 3.10+、型ヒント必須（`from __future__ import annotations` を各ファイル先頭に記載）
- 文字コード: UTF-8
- 実行環境: Windows 11、PowerShell

## ファイル構成

- `tool/brt/` 配下にソースコード、`tool/tests/` 配下にテストコードを配置
- モジュール分割: `core/`, `dsl/`, `steps/`, `importer/`, `ai/`, `templates/`
- 1ファイルが長くなりすぎないよう適切に分割する（目安: 300行以下）
- 各ディレクトリに `__init__.py` を配置し、公開 API を `__all__` で明示する

## docstring・コメント

- 全モジュール先頭に日本語の概要 docstring を記載（目的、主な機能、対応要件番号）
- 全クラス・関数に Google スタイルの docstring を記載（Args, Returns, Raises）
- 要件トレーサビリティ: 対応する要件番号をモジュール docstring またはクラス docstring にコメントで記載
  - 例: `要件 4.1: testId, role(+name), label, placeholder, css, text, any のセレクタ種別`
- インラインコメントは日本語で、処理の意図を説明する

## 命名規則

- クラス名: PascalCase（例: `SelectorResolver`, `StepRegistry`）
- 関数・メソッド名: snake_case（例: `auto_name`, `detect_secret`）
- プライベートメソッド: `_` プレフィックス（例: `_resolve_single`, `_extract_step_type`）
- 定数: UPPER_SNAKE_CASE（例: `_SECRET_KEYWORDS`, `_PATH_SECTION_MAP`）
- モジュールレベル定数はファイル上部にまとめて定義する

## 型定義

- Pydantic v2 の `BaseModel` でスキーマを定義
- `Field(...)` で description を必ず記載
- Union 型は `Union[...]` で定義し、docstring で用途を説明
- Protocol は `@runtime_checkable` を付与
- `TYPE_CHECKING` ガードで循環インポートを回避

## エラーハンドリング

- 具体的な例外型を使用（`ValueError`, `KeyError`, `FileNotFoundError` 等）
- エラーメッセージは日本語で、原因と対処法を含める
- CLI コマンドでは `typer.Exit(code=1)` で終了コードを制御

## ログ

- `logging.getLogger(__name__)` でモジュールごとのロガーを取得
- ログメッセージは日本語で記載

## 依存ライブラリ

- Playwright (Python): ブラウザ自動化
- Pydantic v2: スキーマ定義・検証
- ruamel.yaml: コメント保持付き YAML 読み書き
- Typer: CLI
- Jinja2: HTML レポートテンプレート
- pytest + hypothesis: テスト
