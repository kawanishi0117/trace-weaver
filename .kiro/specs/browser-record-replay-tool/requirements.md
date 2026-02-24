# 要件定義書

## はじめに

本ドキュメントは、ブラウザ操作 Record/Replay テストツールの要件を定義する。本ツールは Python + Playwright codegen を基盤とし、ユーザーが行ったブラウザ操作を記録し、YAML DSL に変換した上で繰り返し自動実行する仕組みを提供する。主な運用対象は Angular（SPA）であり、JS生成UI（ドロップダウン、オーバーレイ）や Wijmo（Combo/Grid 等）でも安定して動作することを最優先とする。記録結果は「人間が読める」「手書きで簡単に編集できる」「全体の流れが把握できる」ことを重視する。

## 用語集

- **Tool**: 本プロジェクトで構築するブラウザ操作 Record/Replay テストツール全体
- **Recorder**: Playwright `codegen` を利用してブラウザ操作を Python スクリプトとして記録するコンポーネント（外部依存）
- **Importer**: Recorder が生成した Python スクリプトを Python AST で解析し、YAML DSL に変換するコンポーネント
- **Runner**: YAML DSL を読み込み、Playwright を用いてブラウザ操作を自動実行するコンポーネント
- **Step_Library**: 標準ステップおよび高レベルステップ（Wijmo/Overlay 等）を提供するモジュール群
- **AI_Authoring**: 自然言語から YAML DSL を生成・整形・説明するコンポーネント
- **YAML_DSL**: 本ツール独自のテストシナリオ記述フォーマット（YAML ベース）
- **Scenario**: YAML DSL で記述された1つのテストシナリオファイル
- **Step**: Scenario 内の1つの操作単位（click, fill, expectVisible 等）
- **Section**: 複数の Step をグループ化し、テストの意図を章立てで表現する単位
- **By_Selector**: Step 内で操作対象の要素を特定するためのセレクタ指定（testId, role+name, label, placeholder, css, text, any）
- **Any_Fallback**: 複数のセレクタ候補を上から順に試行し、visible かつ strict（1件一致）を満たすものを採用するフォールバック機構
- **Strict_Mode**: セレクタが複数要素にヒットした場合に即座に失敗とするモード（デフォルト ON）
- **Artifact**: テスト実行時に生成される成果物（スクリーンショット、トレース、動画、ログ、レポート）
- **Overlay**: Angular Material / Wijmo / 汎用の JS 生成によるドロップダウンやポップアップ UI
- **Wijmo_Combo**: Wijmo ライブラリのコンボボックスコンポーネント
- **Wijmo_Grid**: Wijmo ライブラリのグリッドコンポーネント（仮想スクロール対応）
- **StorageState**: ブラウザのクッキーやローカルストレージの状態を保存・復元するための Playwright 機能
- **CLI**: 本ツールのコマンドラインインターフェース（Typer ベース）
- **Healing**: セレクタが一致しない場合に代替セレクタで自動修復を試みる機能（off/safe モード）

## 要件

### 要件 1: ブラウザ操作の記録

**ユーザーストーリー:** テスト作成者として、ブラウザ上の操作を記録したい。手動でテストスクリプトを一から書く手間を省くためである。

#### 受け入れ基準

1. WHEN テスト作成者が CLI の `record` コマンドに URL を指定して実行した場合、THE Recorder SHALL Playwright codegen を Python ターゲットで起動し、Playwright 管理下のブラウザを開く
2. WHEN 記録セッションが終了した場合、THE Recorder SHALL 生成された Python スクリプトを `recordings/` ディレクトリに `raw_<識別名>.py` として保存する
3. WHEN 記録中にユーザーがブラウザ操作（クリック、入力、ナビゲーション等）を行った場合、THE Recorder SHALL 各操作を Playwright codegen の標準形式で Python スクリプトに記録する

### 要件 2: Python スクリプトから YAML DSL への変換（Import）

**ユーザーストーリー:** テスト作成者として、codegen が生成した Python スクリプトを読みやすい YAML DSL に変換したい。テストシナリオの可読性と編集性を確保するためである。

#### 受け入れ基準

1. WHEN テスト作成者が CLI の `import` コマンドに Python スクリプトのパスを指定した場合、THE Importer SHALL Python AST を用いてスクリプトを解析し、YAML DSL ファイルを生成する
2. WHEN Importer が `page.goto(url)` を検出した場合、THE Importer SHALL `goto` ステップに変換する
3. WHEN Importer が `page.get_by_role(role, name=name).click()` を検出した場合、THE Importer SHALL `click` ステップ（by: role+name 形式）に変換する
4. WHEN Importer が `page.get_by_test_id(id).click()` を検出した場合、THE Importer SHALL `click` ステップ（by: testId 形式）に変換する
5. WHEN Importer が `page.locator(selector).fill(value)` を検出した場合、THE Importer SHALL `fill` ステップ（by: css 形式）に変換する
6. WHEN Importer が `expect(...)` 呼び出しを検出した場合、THE Importer SHALL 対応する検証ステップ（expectVisible / expectText 等）に変換する
7. THE Importer SHALL 各ステップに動詞-目的語の短い形式で `name` を自動付与する
8. THE Importer SHALL 連続する類似操作（URL パスやボタン文言に基づく）をヒューリスティックにグループ化し、`section` を自動生成する
9. THE Importer SHALL locator 文字列を正規化し、`css=` プレフィックス等の差異を吸収する
10. WHEN Importer がパスワード関連のフィールド（role/name に "password" を含む等）を検出した場合、THE Importer SHALL 該当ステップに `secret: true` を付与し、警告を出力する
11. WHEN `--with-expects` オプションが指定された場合、THE Importer SHALL 重要操作後に `expectVisible` ステップを補助的に挿入する
12. FOR ALL 有効な Python スクリプト入力に対して、import して生成された YAML DSL を Runner で実行した結果は、元の Python スクリプトを直接実行した結果と同等の操作を再現する（ラウンドトリップ特性）

### 要件 3: YAML DSL スキーマと構造

**ユーザーストーリー:** テスト作成者として、明確に定義された YAML DSL でテストシナリオを記述したい。スキーマに基づく検証で記述ミスを早期に検出するためである。

#### 受け入れ基準

1. THE YAML_DSL SHALL 最上位に `title`（シナリオ名）、`baseUrl`（基準URL）、`vars`（変数定義）、`artifacts`（成果物設定）、`hooks`（フック定義）、`steps`（ステップ配列）のフィールドを持つ
2. THE YAML_DSL SHALL `vars` フィールドで `${env.X}`（環境変数参照）および `${vars.X}`（シナリオ変数参照）の変数展開構文をサポートする
3. THE YAML_DSL SHALL `secret: true` フラグにより秘密値を指定でき、ログおよびレポートで該当値をマスクする
4. THE YAML_DSL SHALL `artifacts` フィールドで screenshots（mode: before_each_step / before_and_after / none）、trace（mode: on_failure / always / none）、video（mode: on_failure / always / none）の設定を持つ
5. THE YAML_DSL SHALL `hooks` フィールドで `beforeEachStep` および `afterEachStep` にステップ配列を定義できる
6. THE YAML_DSL SHALL `steps` 配列内で `section` 要素によりステップのグループ化と章立てを表現できる
7. WHEN CLI の `validate` コマンドが YAML ファイルに対して実行された場合、THE Tool SHALL Pydantic スキーマに基づき構造を検証し、違反箇所を報告する
8. FOR ALL 有効な YAML DSL ファイルに対して、YAML をパースしてから再度 YAML に出力した結果は、元のファイルと意味的に等価である（パース-出力ラウンドトリップ特性）

### 要件 4: By セレクタ仕様

**ユーザーストーリー:** テスト作成者として、柔軟かつ安定したセレクタ指定方式を使いたい。SPA や JS 生成 UI でもテストが壊れにくくするためである。

#### 受け入れ基準

1. THE By_Selector SHALL `testId`、`role`（+ `name`）、`label`、`placeholder`、`css`、`text`（補助）、`any`（フォールバック）のセレクタ種別をサポートする
2. THE By_Selector SHALL `strict: true` をデフォルトとし、セレクタが複数要素にヒットした場合に即座にエラーとする
3. WHEN `any` セレクタが指定された場合、THE Runner SHALL 候補リストを上から順に試行し、visible かつ strict（1件一致）を満たす最初の候補を採用する
4. WHEN `any` セレクタの全候補が条件を満たさなかった場合、THE Runner SHALL 試行した全候補とその失敗理由を含むエラーメッセージを出力する
5. WHEN `text` が単体で指定された場合、THE Tool SHALL lint 時に警告を出力する（`css + text` や `role + name` の補助条件としての使用は許可する）

### 要件 5: 標準ステップライブラリ

**ユーザーストーリー:** テスト作成者として、一般的なブラウザ操作を1行のステップで記述したい。テストシナリオの記述を簡潔に保つためである。

#### 受け入れ基準

1. THE Step_Library SHALL ナビゲーションステップとして `goto`、`back`、`reload` を提供する
2. THE Step_Library SHALL 操作ステップとして `click`、`dblclick`、`fill`、`press`、`check`、`uncheck`、`selectOption`（HTML select 用）を提供する
3. THE Step_Library SHALL 待機/同期ステップとして `waitFor`、`waitForVisible`、`waitForHidden`、`waitForNetworkIdle` を提供する
4. THE Step_Library SHALL 検証ステップとして `expectVisible`、`expectHidden`、`expectText`、`expectUrl` を提供する
5. THE Step_Library SHALL 取得ステップとして `storeText`（vars へ格納）、`storeAttr` を提供する
6. THE Step_Library SHALL デバッグステップとして `screenshot`、`log`、`dumpDom` を提供する
7. THE Step_Library SHALL セッションステップとして `useStorageState`、`saveStorageState` を提供する
8. THE Step_Library SHALL プラグイン方式でカスタムステップの追加を可能にする


### 要件 6: 高レベルステップ（Overlay / Wijmo / JS生成UI 対応）

**ユーザーストーリー:** テスト作成者として、Angular Material / Wijmo / 汎用オーバーレイなどの JS 生成 UI を1ステップで操作したい。複雑な UI コンポーネントの操作を安定かつ簡潔に記述するためである。

#### 受け入れ基準

1. THE Step_Library SHALL `selectOverlayOption` ステップを提供し、open（トリガー要素）、list（候補リスト要素）、optionText（選択テキスト）を指定して、オーバーレイの「開く→候補表示→選択」を1ステップで実行する
2. WHEN `selectOverlayOption` が実行された場合、THE Runner SHALL open 要素をクリックし、list 要素の可視化を待ち、list 内から optionText に一致する候補を strict に特定してクリックする
3. THE Step_Library SHALL `selectWijmoCombo` ステップを提供し、root（コンポーネント境界）と optionText を指定して、Wijmo Combo の候補選択を1ステップで実行する
4. THE Step_Library SHALL `clickWijmoGridCell` ステップを提供し、grid（グリッド要素）、rowKey（行特定条件: column + equals）、column（列名）を指定して、Wijmo Grid の特定セルをクリックする
5. WHEN `clickWijmoGridCell` が実行され、対象行が仮想スクロールにより画面外にある場合、THE Runner SHALL グリッドをスクロールして対象行を探索し、発見後にセルをクリックする
6. THE Step_Library SHALL `setDatePicker` ステップを提供し、UI 日付ピッカーへの日付入力を1ステップで実行する
7. THE Step_Library SHALL `uploadFile` ステップを提供し、input[type=file] または UI ボタン経由のファイルアップロードを1ステップで実行する
8. THE Step_Library SHALL `waitForToast` ステップを提供し、トースト通知の出現および消滅の待機を1ステップで実行する
9. THE Step_Library SHALL `assertNoConsoleError` ステップを提供し、ブラウザコンソールにエラーが出力されていないことを検証する
10. THE Step_Library SHALL `apiMock` および `routeStub` ステップを提供し、Playwright route を用いた API スタブによる E2E テスト安定化を1ステップで実行する

### 要件 7: Runner（実行エンジン）

**ユーザーストーリー:** テスト作成者として、YAML DSL で記述したシナリオを安定して自動実行したい。Angular SPA の描画揺らぎに影響されず、確実にテストを再現するためである。

#### 受け入れ基準

1. WHEN CLI の `run` コマンドが YAML ファイルに対して実行された場合、THE Runner SHALL 以下のライフサイクルで実行する: config 読込 → Browser/Context 生成 → trace 開始 → ステップループ → 成果物管理 → レポート生成
2. THE Runner SHALL 実行環境（viewport、timezone、locale、headers、storageState）を Scenario 設定に基づき固定する
3. WHEN `goto` ステップが実行された場合、THE Runner SHALL ナビゲーション後に `waitForLoadState("domcontentloaded")` を標準で実行する
4. THE Runner SHALL Playwright locator の auto-wait 機能を活用し、要素の操作可能状態を自動的に待機する
5. THE Runner SHALL 各ステップ実行前に `beforeEachStep` フックを実行し、各ステップ実行後に `afterEachStep` フックを実行する
6. WHEN ステップ実行中にエラーが発生した場合、THE Runner SHALL エラー発生時点のスクリーンショット、トレース、動画を保存し、失敗ステップの情報（ステップ名、セレクタ、エラーメッセージ）をレポートに記録する
7. WHEN `--headed` オプションが指定された場合、THE Runner SHALL ブラウザを表示モードで起動する
8. WHEN `--headless` オプションが指定された場合、THE Runner SHALL ブラウザを非表示モードで起動する
9. WHEN `--workers N` オプションが指定された場合、THE Runner SHALL 最大 N 個のシナリオを並列実行する
10. WHERE `healing: safe` が Scenario に設定されている場合、THE Runner SHALL セレクタ不一致時に any 候補の別セレクタおよび testId/role/name/label の範囲で再解決を試みる
11. WHERE `healing: off` が Scenario に設定されている場合、THE Runner SHALL セレクタ不一致時に即座にエラーとする（DOM 近傍探索による推測クリックは実行しない）

### 要件 8: アーティファクト管理

**ユーザーストーリー:** テスト作成者として、テスト実行の成果物（スクリーンショット、トレース、動画、ログ）を体系的に管理したい。失敗時に「どこで何が起きたか」を即時に追跡するためである。

#### 受け入れ基準

1. THE Runner SHALL 各ステップ実行前にスクリーンショットを撮影し、`artifacts/run-YYYYMMDD-HHMMSS/screenshots/` ディレクトリに `NNNN_before-<step-name>.jpg` 形式で保存する（デフォルト: before_each_step モード）
2. THE Runner SHALL スクリーンショットのデフォルト形式を JPEG（quality: 70）とする
3. WHEN テスト実行が失敗した場合、THE Runner SHALL Playwright トレースを `artifacts/run-YYYYMMDD-HHMMSS/trace/trace.zip` として保存する（デフォルト: on_failure モード）
4. WHEN テスト実行が失敗した場合、THE Runner SHALL 動画を `artifacts/run-YYYYMMDD-HHMMSS/video/` ディレクトリに保存する（デフォルト: on_failure モード）
5. WHEN テスト実行が成功した場合かつ動画モードが `on_failure` の場合、THE Runner SHALL 録画された動画ファイルを削除する
6. THE Runner SHALL 実行ログを `artifacts/run-YYYYMMDD-HHMMSS/logs/runner.log` に出力する
7. THE Runner SHALL ブラウザコンソールログを `artifacts/run-YYYYMMDD-HHMMSS/logs/console.log` に出力する
8. THE Runner SHALL 実行に使用した YAML DSL のコピーを `artifacts/run-YYYYMMDD-HHMMSS/flow.yaml` として保存する
9. THE Runner SHALL 実行環境情報（秘密値はマスク済み）を `artifacts/run-YYYYMMDD-HHMMSS/env.json` として保存する

### 要件 9: レポート生成

**ユーザーストーリー:** テスト作成者として、テスト実行結果を複数形式のレポートで確認したい。CI パイプラインとの統合および人間による結果確認を両立するためである。

#### 受け入れ基準

1. WHEN テスト実行が完了した場合、THE Runner SHALL JSON 形式のレポートを `artifacts/run-YYYYMMDD-HHMMSS/report.json` として生成する
2. WHEN テスト実行が完了した場合、THE Runner SHALL HTML 形式のレポート（Jinja2 テンプレート使用）を `artifacts/run-YYYYMMDD-HHMMSS/report.html` として生成する
3. THE Runner SHALL HTML レポートに各ステップのスクリーンショットへのリンク、失敗ステップの詳細情報、実行時間を含める
4. WHEN テスト実行が完了した場合、THE Runner SHALL JUnit XML 形式のレポートを生成する（CI 統合用）
5. WHEN テスト実行が成功した場合、THE CLI SHALL 終了コード 0 を返す
6. WHEN テスト実行が失敗した場合、THE CLI SHALL 終了コード 1 を返す
7. WHEN CLI の `report` コマンドが既存のアーティファクトディレクトリに対して実行された場合、THE Tool SHALL HTML レポートを再生成する

### 要件 10: CLI インターフェース

**ユーザーストーリー:** テスト作成者として、統一された CLI でツールの全機能にアクセスしたい。記録・変換・実行・検証・レポートの一連のワークフローを効率的に行うためである。

#### 受け入れ基準

1. THE CLI SHALL `init` コマンドを提供し、プロジェクト雛形（ディレクトリ構造、設定ファイルテンプレート）を生成する
2. THE CLI SHALL `record <url>` コマンドを提供し、指定 URL に対して Playwright codegen を起動する
3. THE CLI SHALL `import <python-file> -o <yaml-file>` コマンドを提供し、Python スクリプトを YAML DSL に変換する
4. THE CLI SHALL `run <yaml-file>` コマンドを提供し、`--headed`、`--headless`、`--workers N` オプションをサポートする
5. THE CLI SHALL `validate <yaml-file>` コマンドを提供し、YAML DSL のスキーマ検証結果を出力する
6. THE CLI SHALL `lint <yaml-file>` コマンドを提供し、セレクタ危険度やアンチパターンを検出して警告を出力する
7. THE CLI SHALL `report <artifacts-dir>` コマンドを提供し、HTML レポートを再生成する
8. THE CLI SHALL `list-steps` コマンドを提供し、利用可能な全ステップ（標準 + 高レベル）の一覧を出力する

### 要件 11: AI Authoring

**ユーザーストーリー:** テスト作成者として、自然言語からテストシナリオを生成・整形したい。テスト作成の効率を向上させるためである。

#### 受け入れ基準

1. THE CLI SHALL `ai draft` コマンドを提供し、自然言語の仕様記述から YAML DSL スキーマに準拠した Scenario を生成する
2. THE CLI SHALL `ai refine` コマンドを提供し、import 後の YAML DSL に対して section 付与、命名改善、expect 補強、重複整理を実行する
3. THE CLI SHALL `ai explain` コマンドを提供し、YAML DSL からアウトライン（章立てと要点）を自然言語で生成する
4. WHEN AI Authoring が YAML DSL を生成または変更した場合、THE AI_Authoring SHALL 出力を Pydantic スキーマで検証し、不正な構造を出力しない
5. WHEN AI Authoring が `secret: true` フラグ付きのステップを処理した場合、THE AI_Authoring SHALL secret フラグを保持し、ログやレポートで秘密値をマスクする
6. WHEN AI Authoring の出力に禁止パターン（text 単体セレクタ等）が含まれる場合、THE AI_Authoring SHALL lint で警告を出力する

### 要件 12: Lint（静的解析）

**ユーザーストーリー:** テスト作成者として、YAML DSL の品質問題を実行前に検出したい。不安定なセレクタやアンチパターンによるテスト失敗を未然に防ぐためである。

#### 受け入れ基準

1. WHEN `text` セレクタが単体で使用されている場合、THE Tool SHALL 警告を出力する
2. WHEN セレクタに `any` フォールバックが設定されていない場合、THE Tool SHALL 情報レベルの通知を出力する（推奨事項として）
3. WHEN `secret: true` が付与されるべきフィールド（パスワード等）に付与されていない場合、THE Tool SHALL 警告を出力する
4. THE Tool SHALL lint 結果をステップ名、行番号、重大度（error / warning / info）と共に出力する

### 要件 13: 非機能要件 - 安定性

**ユーザーストーリー:** テスト作成者として、SPA・オーバーレイ・仮想スクロールを含むアプリケーションでもテストが安定して動作することを期待する。テスト結果の信頼性を確保するためである。

#### 受け入れ基準

1. THE Runner SHALL Playwright の auto-wait 機能と expect ベースの検証を組み合わせ、SPA の描画揺らぎに対応する
2. THE Runner SHALL Overlay 系ステップの内部で候補リストの可視化待機（expectVisible 相当）を自動的に実行する
3. WHEN Wijmo Grid の仮想スクロールにより対象行が画面外にある場合、THE Runner SHALL スクロール操作を繰り返して対象行を探索する
4. THE Runner SHALL strict モードをデフォルトで有効にし、セレクタが複数要素にヒットした場合に誤操作を防止する

### 要件 14: 非機能要件 - 再現性

**ユーザーストーリー:** テスト作成者として、テスト実行環境を固定し、同一条件で繰り返し実行したい。テスト結果の再現性を保証するためである。

#### 受け入れ基準

1. THE Runner SHALL viewport サイズ、timezone、locale を Scenario 設定に基づき固定する
2. THE Runner SHALL storageState の保存・復元により、ログイン状態等のセッション情報を再利用可能にする
3. THE Runner SHALL カスタム HTTP ヘッダーを Scenario 設定に基づき Context に付与する

### 要件 15: 非機能要件 - 拡張性

**ユーザーストーリー:** テスト作成者として、カスタムステップを追加して本ツールの機能を拡張したい。プロジェクト固有の UI コンポーネントに対応するためである。

#### 受け入れ基準

1. THE Step_Library SHALL プラグイン方式でカスタムステップの登録を受け付け、標準ステップと同一のインターフェースで実行する
2. WHEN カスタムステップが登録された場合、THE CLI の `list-steps` コマンド SHALL 登録されたカスタムステップを一覧に含める
3. THE Tool SHALL カスタムステップの YAML DSL スキーマ定義を Pydantic モデルとして提供し、validate / lint の対象に含める
