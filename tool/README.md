# brt — ブラウザ操作 Record/Replay テストツール

ブラウザ上の操作を記録して、何度でも自動で再実行できるツールです。
Python + Playwright を使っています。

---

## はじめに（初めての方へ）

### 1. インストール

PowerShell を開いて、以下を順番に実行してください。

```powershell
# プロジェクトフォルダに移動
cd tool

# ツール本体をインストール
pip install -e ".[test]"

# ブラウザエンジン（Chromium）をインストール
playwright install chromium
```

> Chrome を使う場合（デフォルト）は、PC に Google Chrome がインストールされていれば OK です。
> 追加のインストールは不要です。

### 2. プロジェクトを初期化する

```powershell
brt init
```

`flows/`、`recordings/`、`artifacts/` フォルダと設定ファイルが作られます。

---

## 基本の使い方（3ステップ）

### ステップ 1: ブラウザ操作を記録する

```powershell
brt record
```

URL の入力を求められるので、記録したいページの URL を入力してください。

```
記録する URL を入力してください: https://example.com
```

Chrome が開くので、テストしたい操作をそのまま行ってください。
ブラウザを閉じると記録が終了し、自動で YAML ファイルに変換されます。

> URL を直接指定することもできます:
> ```powershell
> brt record https://example.com
> ```

### ステップ 2: 記録した操作を確認する

`flows/recording.yaml` が生成されています。中身はこんな感じです:

```yaml
title: Imported from raw_recording.py
baseUrl: https://example.com
steps:
  - goto:
      url: https://example.com
      name: navigate-to-example
  - click:
      by:
        role: link
        name: "詳細を見る"
      name: click-details
```

テキストエディタで自由に編集できます。

### ステップ 3: 記録した操作を再実行する

```powershell
brt run flows/recording.yaml
```

Chrome が開いて、記録した操作が自動で再実行されます。
結果は `artifacts/` フォルダにスクリーンショットやレポートとして保存されます。

---

## よく使うコマンド一覧

| やりたいこと | コマンド |
|---|---|
| 操作を記録する | `brt record` |
| 記録を再実行する | `brt run flows/ファイル名.yaml` |
| YAML の書き方が正しいか確認 | `brt validate flows/ファイル名.yaml` |
| セレクタの問題を検出 | `brt lint flows/ファイル名.yaml` |
| 使えるステップの一覧 | `brt list-steps` |
| HTML レポートを再生成 | `brt report artifacts/run-XXXXXXXX-XXXXXX` |

---

## オプション

### record コマンド

```powershell
# 出力先を指定
brt record https://example.com -o flows/login.yaml

# Chromium を使う（Chrome がない環境向け）
brt record -c chromium

# ハイライト枠なしで記録
brt record --no-highlight

# YAML 変換をスキップ（Python スクリプトのみ出力）
brt record --no-import
```

### run コマンド

```powershell
# ヘッドレス（ブラウザ非表示）で実行
brt run flows/login.yaml --headless

# 複数シナリオを並列実行
brt run flows/login.yaml -w 4
```

---

## AI 支援コマンド

```powershell
# 自然言語からテストシナリオを生成
brt ai draft "ログインしてダッシュボードを確認する" -o flows/login.yaml

# 既存の YAML を改善（セクション追加、命名改善など）
brt ai refine flows/login.yaml -o flows/login_refined.yaml

# YAML の内容を日本語で説明
brt ai explain flows/login.yaml
```

---

## トラブルシューティング

### 「Chrome が見つからない」と言われる

PC に Google Chrome がインストールされているか確認してください。
Chrome がない場合は Chromium を使います:

```powershell
brt record -c chromium
```

### 「playwright が見つからない」と言われる

```powershell
pip install -e ".[test]"
playwright install chromium
```

### 記録した操作が再実行で失敗する

- `flows/` 内の YAML ファイルを開いて、セレクタ（`by:` の部分）を確認してください
- `brt lint flows/ファイル名.yaml` で問題を検出できます
- 画面の読み込みが遅い場合は、`waitForVisible` ステップを追加してみてください
