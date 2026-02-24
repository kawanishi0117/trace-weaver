"""
DSL スキーマ定義 — セレクタモデル

YAML DSL で使用する By セレクタの Pydantic v2 モデルを定義する。
各セレクタは操作対象の要素を特定するための指定方式を表現し、
strict モード（デフォルト: True）により複数要素ヒット時の誤操作を防止する。

要件 4.1: testId, role(+name), label, placeholder, css, text, any のセレクタ種別
要件 4.2: strict: true をデフォルトとし、複数要素ヒット時に即座にエラー
"""

from __future__ import annotations

import re
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# 単一セレクタ定義
# ---------------------------------------------------------------------------

class TestIdSelector(BaseModel):
    """data-testid 属性によるセレクタ。

    最も安定したセレクタ種別。テスト専用属性のため UI 変更の影響を受けにくい。
    """

    testId: str = Field(..., description="data-testid 属性の値")
    strict: bool = Field(default=True, description="複数要素ヒット時にエラーとするか")


class RoleSelector(BaseModel):
    """ARIA ロールによるセレクタ。

    アクセシビリティロール（button, textbox, link 等）で要素を特定する。
    name を併用することで、同一ロールの要素を区別できる。
    exact を True にすると name の完全一致で検索する。
    """

    role: str = Field(..., description="ARIA ロール名（button, textbox, link 等）")
    name: Optional[str] = Field(default=None, description="アクセシブルネーム（補助条件）")
    exact: Optional[bool] = Field(default=None, description="name の完全一致検索（True で部分一致を無効化）")
    strict: bool = Field(default=True, description="複数要素ヒット時にエラーとするか")


class LabelSelector(BaseModel):
    """ラベルテキストによるセレクタ。

    フォーム要素に関連付けられた label 要素のテキストで特定する。
    """

    label: str = Field(..., description="ラベルテキスト")
    strict: bool = Field(default=True, description="複数要素ヒット時にエラーとするか")


class PlaceholderSelector(BaseModel):
    """プレースホルダーテキストによるセレクタ。

    input / textarea 要素の placeholder 属性で特定する。
    """

    placeholder: str = Field(..., description="プレースホルダーテキスト")
    strict: bool = Field(default=True, description="複数要素ヒット時にエラーとするか")


class CssSelector(BaseModel):
    """CSS セレクタによる要素特定。

    汎用的な CSS セレクタ文字列で要素を特定する。
    text を補助条件として併用し、同一セレクタ内の要素を絞り込める。
    """

    css: str = Field(..., description="CSS セレクタ文字列")
    text: Optional[str] = Field(default=None, description="テキスト内容による補助条件")
    strict: bool = Field(default=True, description="複数要素ヒット時にエラーとするか")


class TextSelector(BaseModel):
    """テキスト内容によるセレクタ。

    要素のテキスト内容で特定する。単体使用は不安定なため、
    lint 時に警告が出力される（css + text や role + name の補助条件としての使用を推奨）。
    """

    text: str = Field(..., description="テキスト内容")
    strict: bool = Field(default=True, description="複数要素ヒット時にエラーとするか")


# ---------------------------------------------------------------------------
# フォールバックセレクタ定義
# ---------------------------------------------------------------------------

# AnySelector の候補として使用可能な単一セレクタの Union 型
SingleSelector = Union[
    TestIdSelector,
    RoleSelector,
    LabelSelector,
    PlaceholderSelector,
    CssSelector,
    TextSelector,
]


class AnySelector(BaseModel):
    """フォールバックセレクタ。

    複数のセレクタ候補を上から順に試行し、
    visible かつ strict（1件一致）を満たす最初の候補を採用する。
    全候補が条件を満たさない場合は、試行した全候補と失敗理由を含むエラーを出力する。

    AnySelector 自体には strict フィールドを持たない。
    各候補セレクタが個別に strict を制御する。
    """

    any: list[SingleSelector] = Field(
        ...,
        min_length=1,
        description="セレクタ候補リスト（上から順に試行）",
    )


# ---------------------------------------------------------------------------
# By セレクタ Union 型
# ---------------------------------------------------------------------------

BySelector = Union[
    TestIdSelector,
    RoleSelector,
    LabelSelector,
    PlaceholderSelector,
    CssSelector,
    TextSelector,
    AnySelector,
]
"""全セレクタ種別の Union 型。

ステップモデルの `by` フィールドで使用する。
Pydantic の discriminated union ではなく、
各モデルのフィールド構成で自動判別される。
"""


# ===========================================================================
# ステップモデル定義
#
# 要件 5.1: ナビゲーションステップ（goto, back, reload）
# 要件 5.2: 操作ステップ（click, dblclick, fill, press, check, uncheck, selectOption）
# 要件 5.3: 待機ステップ（waitFor, waitForVisible, waitForHidden, waitForNetworkIdle）
# 要件 5.4: 検証ステップ（expectVisible, expectHidden, expectText, expectUrl）
# 要件 5.5: 取得ステップ（storeText, storeAttr）
# 要件 5.6: デバッグステップ（screenshot, log, dumpDom）
# 要件 5.7: セッションステップ（useStorageState, saveStorageState）
# ===========================================================================


# ---------------------------------------------------------------------------
# ナビゲーションステップ
# ---------------------------------------------------------------------------

class GotoStep(BaseModel):
    """指定 URL へ遷移するステップ。

    ナビゲーション後に waitForLoadState("domcontentloaded") が自動実行される。
    """

    goto: str = Field(..., description="遷移先 URL")
    name: Optional[str] = Field(default=None, description="ステップ名（任意）")


class BackStep(BaseModel):
    """ブラウザの「戻る」操作を実行するステップ。"""

    back: bool = Field(default=True, description="戻る操作のマーカー")
    name: Optional[str] = Field(default=None, description="ステップ名（任意）")


class ReloadStep(BaseModel):
    """ページをリロードするステップ。"""

    reload: bool = Field(default=True, description="リロード操作のマーカー")
    name: Optional[str] = Field(default=None, description="ステップ名（任意）")


# ---------------------------------------------------------------------------
# 操作ステップ
# ---------------------------------------------------------------------------

class ClickStep(BaseModel):
    """要素をクリックするステップ。"""

    click: BySelector = Field(..., description="クリック対象のセレクタ")
    name: Optional[str] = Field(default=None, description="ステップ名（任意）")
    frame: Optional[str] = Field(default=None, description="iframe セレクタ（iframe 内操作時）")


class DblClickStep(BaseModel):
    """要素をダブルクリックするステップ。"""

    dblclick: BySelector = Field(..., description="ダブルクリック対象のセレクタ")
    name: Optional[str] = Field(default=None, description="ステップ名（任意）")
    frame: Optional[str] = Field(default=None, description="iframe セレクタ（iframe 内操作時）")


class FillStep(BaseModel):
    """入力フィールドに値を入力するステップ。

    secret: true を指定すると、ログやレポートで値がマスクされる。
    """

    fill: BySelector = Field(..., description="入力対象のセレクタ")
    value: str = Field(..., description="入力する値")
    name: Optional[str] = Field(default=None, description="ステップ名（任意）")
    secret: bool = Field(default=False, description="秘密値フラグ（true でログマスク）")
    frame: Optional[str] = Field(default=None, description="iframe セレクタ（iframe 内操作時）")


class PressStep(BaseModel):
    """要素に対してキーを押下するステップ。

    key には Playwright のキー名（Enter, Tab, Escape 等）を指定する。
    """

    press: BySelector = Field(..., description="キー押下対象のセレクタ")
    key: str = Field(..., description="押下するキー名（Enter, Tab 等）")
    name: Optional[str] = Field(default=None, description="ステップ名（任意）")
    frame: Optional[str] = Field(default=None, description="iframe セレクタ（iframe 内操作時）")


class CheckStep(BaseModel):
    """チェックボックスをチェック状態にするステップ。"""

    check: BySelector = Field(..., description="チェック対象のセレクタ")
    name: Optional[str] = Field(default=None, description="ステップ名（任意）")
    frame: Optional[str] = Field(default=None, description="iframe セレクタ（iframe 内操作時）")


class UncheckStep(BaseModel):
    """チェックボックスのチェックを外すステップ。"""

    uncheck: BySelector = Field(..., description="チェック解除対象のセレクタ")
    name: Optional[str] = Field(default=None, description="ステップ名（任意）")
    frame: Optional[str] = Field(default=None, description="iframe セレクタ（iframe 内操作時）")


class SelectOptionStep(BaseModel):
    """HTML select 要素からオプションを選択するステップ。"""

    selectOption: BySelector = Field(..., description="セレクト要素のセレクタ")
    value: str = Field(..., description="選択するオプションの値")
    name: Optional[str] = Field(default=None, description="ステップ名（任意）")
    frame: Optional[str] = Field(default=None, description="iframe セレクタ（iframe 内操作時）")


# ---------------------------------------------------------------------------
# 待機ステップ
# ---------------------------------------------------------------------------

class WaitForStep(BaseModel):
    """要素が指定状態になるまで待機するステップ。

    state には "visible", "hidden", "attached", "detached" を指定可能。
    """

    waitFor: BySelector = Field(..., description="待機対象のセレクタ")
    state: str = Field(
        default="visible",
        description="待機する状態（visible, hidden, attached, detached）",
    )
    timeout: Optional[int] = Field(
        default=None, description="タイムアウト（ミリ秒）。None でデフォルト値を使用"
    )
    name: Optional[str] = Field(default=None, description="ステップ名（任意）")


class WaitForVisibleStep(BaseModel):
    """要素が可視状態になるまで待機するステップ。"""

    waitForVisible: BySelector = Field(..., description="待機対象のセレクタ")
    timeout: Optional[int] = Field(
        default=None, description="タイムアウト（ミリ秒）"
    )
    name: Optional[str] = Field(default=None, description="ステップ名（任意）")


class WaitForHiddenStep(BaseModel):
    """要素が非表示状態になるまで待機するステップ。"""

    waitForHidden: BySelector = Field(..., description="待機対象のセレクタ")
    timeout: Optional[int] = Field(
        default=None, description="タイムアウト（ミリ秒）"
    )
    name: Optional[str] = Field(default=None, description="ステップ名（任意）")


class WaitForNetworkIdleStep(BaseModel):
    """ネットワークがアイドル状態になるまで待機するステップ。

    全てのネットワークリクエストが完了するまで待機する。
    """

    waitForNetworkIdle: bool = Field(
        default=True, description="ネットワークアイドル待機のマーカー"
    )
    timeout: Optional[int] = Field(
        default=None, description="タイムアウト（ミリ秒）"
    )
    name: Optional[str] = Field(default=None, description="ステップ名（任意）")


# ---------------------------------------------------------------------------
# 検証ステップ
# ---------------------------------------------------------------------------

class ExpectVisibleStep(BaseModel):
    """要素が可視状態であることを検証するステップ。"""

    expectVisible: BySelector = Field(..., description="検証対象のセレクタ")
    name: Optional[str] = Field(default=None, description="ステップ名（任意）")
    frame: Optional[str] = Field(default=None, description="iframe セレクタ（iframe 内操作時）")


class ExpectHiddenStep(BaseModel):
    """要素が非表示状態であることを検証するステップ。"""

    expectHidden: BySelector = Field(..., description="検証対象のセレクタ")
    name: Optional[str] = Field(default=None, description="ステップ名（任意）")
    frame: Optional[str] = Field(default=None, description="iframe セレクタ（iframe 内操作時）")


class ExpectTextStep(BaseModel):
    """要素が指定テキストを含むことを検証するステップ。"""

    expectText: BySelector = Field(..., description="検証対象のセレクタ")
    text: str = Field(..., description="期待するテキスト内容")
    name: Optional[str] = Field(default=None, description="ステップ名（任意）")
    frame: Optional[str] = Field(default=None, description="iframe セレクタ（iframe 内操作時）")


class ExpectUrlStep(BaseModel):
    """現在の URL が指定パターンに一致することを検証するステップ。"""

    expectUrl: str = Field(..., description="期待する URL（部分一致またはパターン）")
    name: Optional[str] = Field(default=None, description="ステップ名（任意）")


# ---------------------------------------------------------------------------
# 取得ステップ
# ---------------------------------------------------------------------------

class StoreTextStep(BaseModel):
    """要素のテキスト内容を変数に格納するステップ。

    取得した値は vars に格納され、後続ステップで ${vars.X} として参照可能。
    """

    storeText: BySelector = Field(..., description="テキスト取得対象のセレクタ")
    varName: str = Field(..., description="格納先の変数名")
    name: Optional[str] = Field(default=None, description="ステップ名（任意）")


class StoreAttrStep(BaseModel):
    """要素の属性値を変数に格納するステップ。

    取得した値は vars に格納され、後続ステップで ${vars.X} として参照可能。
    """

    storeAttr: BySelector = Field(..., description="属性取得対象のセレクタ")
    attr: str = Field(..., description="取得する属性名")
    varName: str = Field(..., description="格納先の変数名")
    name: Optional[str] = Field(default=None, description="ステップ名（任意）")


# ---------------------------------------------------------------------------
# デバッグステップ
# ---------------------------------------------------------------------------

class ScreenshotStep(BaseModel):
    """スクリーンショットを撮影するステップ。

    name がファイル名の一部として使用される。
    """

    screenshot: bool = Field(default=True, description="スクリーンショット撮影のマーカー")
    name: Optional[str] = Field(default=None, description="ステップ名（ファイル名に使用）")


class LogStep(BaseModel):
    """メッセージをログに出力するステップ。"""

    log: str = Field(..., description="出力するメッセージ")
    name: Optional[str] = Field(default=None, description="ステップ名（任意）")


class DumpDomStep(BaseModel):
    """要素の DOM 構造をダンプするステップ。

    デバッグ用途で、指定要素の HTML 構造をログに出力する。
    """

    dumpDom: BySelector = Field(..., description="DOM ダンプ対象のセレクタ")
    name: Optional[str] = Field(default=None, description="ステップ名（任意）")


# ---------------------------------------------------------------------------
# セッションステップ
# ---------------------------------------------------------------------------

class UseStorageStateStep(BaseModel):
    """保存済みのストレージ状態を復元するステップ。

    クッキーやローカルストレージの状態を JSON ファイルから読み込み、
    ブラウザコンテキストに適用する。ログイン状態の再利用等に使用。
    """

    useStorageState: str = Field(..., description="ストレージ状態ファイルのパス")
    name: Optional[str] = Field(default=None, description="ステップ名（任意）")


class SaveStorageStateStep(BaseModel):
    """現在のストレージ状態を保存するステップ。

    クッキーやローカルストレージの状態を JSON ファイルに保存する。
    後続のシナリオで useStorageState により復元可能。
    """

    saveStorageState: str = Field(..., description="保存先ファイルのパス")
    name: Optional[str] = Field(default=None, description="ステップ名（任意）")


# ===========================================================================
# 高レベルステップモデル定義
#
# 要件 6.1: selectOverlayOption（オーバーレイの開く→候補表示→選択を1ステップで実行）
# 要件 6.3: selectWijmoCombo（Wijmo Combo の候補選択を1ステップで実行）
# 要件 6.4: clickWijmoGridCell（Wijmo Grid の特定セルをクリック）
# 要件 6.6: setDatePicker（日付ピッカーへの日付入力を1ステップで実行）
# 要件 6.7: uploadFile（ファイルアップロードを1ステップで実行）
# 要件 6.8: waitForToast（トースト通知の出現待機を1ステップで実行）
# 要件 6.9: assertNoConsoleError（ブラウザコンソールにエラーがないことを検証）
# 要件 6.10: apiMock / routeStub（API スタブによる E2E テスト安定化）
# ===========================================================================


# ---------------------------------------------------------------------------
# オーバーレイ / コンボ系ステップ
# ---------------------------------------------------------------------------

class SelectOverlayOptionStep(BaseModel):
    """オーバーレイの「開く→候補表示→選択」を1ステップで実行するステップ。

    Angular Material / 汎用オーバーレイのドロップダウン操作に対応する。
    open 要素をクリックし、list 要素の可視化を待ち、
    list 内から optionText に一致する候補を strict に特定してクリックする。
    """

    selectOverlayOption: BySelector = Field(
        ..., description="トリガー要素（open）のセレクタ（互換用エイリアス）",
    )
    open: BySelector = Field(..., description="オーバーレイを開くトリガー要素のセレクタ")
    list: BySelector = Field(..., description="候補リスト要素のセレクタ")
    optionText: str = Field(..., description="選択する候補のテキスト")
    name: Optional[str] = Field(default=None, description="ステップ名（任意）")


class SelectWijmoComboStep(BaseModel):
    """Wijmo ComboBox の候補選択を1ステップで実行するステップ。

    root でコンポーネント境界を指定し、optionText で候補を選択する。
    """

    selectWijmoCombo: BySelector = Field(
        ..., description="Wijmo ComboBox のルート要素セレクタ",
    )
    root: BySelector = Field(..., description="コンポーネント境界のセレクタ")
    optionText: str = Field(..., description="選択する候補のテキスト")
    name: Optional[str] = Field(default=None, description="ステップ名（任意）")


# ---------------------------------------------------------------------------
# Wijmo Grid ステップ
# ---------------------------------------------------------------------------

class WijmoGridRowKey(BaseModel):
    """Wijmo Grid の行を特定するためのキー条件。

    column と equals の組み合わせで、特定の列の値が一致する行を特定する。
    """

    column: str = Field(..., description="行特定に使用する列名")
    equals: str = Field(..., description="一致させる値")


class ClickWijmoGridCellStep(BaseModel):
    """Wijmo FlexGrid の特定セルをクリックするステップ。

    grid でグリッド要素を指定し、rowKey で行を特定、column で列を指定する。
    対象行が仮想スクロールにより画面外にある場合、
    グリッドをスクロールして対象行を探索し、発見後にセルをクリックする。
    """

    clickWijmoGridCell: BySelector = Field(
        ..., description="Wijmo Grid 要素のセレクタ",
    )
    grid: BySelector = Field(..., description="グリッド要素のセレクタ")
    rowKey: WijmoGridRowKey = Field(..., description="行特定条件（column + equals）")
    column: str = Field(..., description="クリック対象の列名")
    name: Optional[str] = Field(default=None, description="ステップ名（任意）")


# ---------------------------------------------------------------------------
# 日付ピッカーステップ
# ---------------------------------------------------------------------------

class SetDatePickerStep(BaseModel):
    """日付ピッカーへの日付入力を1ステップで実行するステップ。

    UI 日付ピッカー全般に対応する。by でピッカー要素を指定し、
    date で入力する日付、format で日付フォーマットを指定する。
    """

    setDatePicker: BySelector = Field(
        ..., description="日付ピッカー要素のセレクタ",
    )
    by: BySelector = Field(..., description="日付ピッカー要素のセレクタ")
    date: str = Field(..., description="入力する日付文字列")
    format: Optional[str] = Field(
        default=None, description="日付フォーマット（例: YYYY-MM-DD）"
    )
    name: Optional[str] = Field(default=None, description="ステップ名（任意）")


# ---------------------------------------------------------------------------
# ファイルアップロードステップ
# ---------------------------------------------------------------------------

class UploadFileStep(BaseModel):
    """ファイルアップロードを1ステップで実行するステップ。

    input[type=file] または UI ボタン経由のファイルアップロードに対応する。
    """

    uploadFile: BySelector = Field(
        ..., description="ファイル入力要素のセレクタ",
    )
    by: BySelector = Field(..., description="ファイル入力要素のセレクタ")
    filePath: str = Field(..., description="アップロードするファイルのパス")
    name: Optional[str] = Field(default=None, description="ステップ名（任意）")


# ---------------------------------------------------------------------------
# トースト通知ステップ
# ---------------------------------------------------------------------------

class WaitForToastStep(BaseModel):
    """トースト通知の出現および消滅を待機するステップ。

    text で通知テキストを指定し、timeout で最大待機時間を設定する。
    """

    waitForToast: str = Field(..., description="待機するトースト通知のテキスト")
    text: str = Field(..., description="トースト通知のテキスト")
    timeout: Optional[int] = Field(
        default=None, description="タイムアウト（ミリ秒）"
    )
    name: Optional[str] = Field(default=None, description="ステップ名（任意）")


# ---------------------------------------------------------------------------
# コンソールエラー検証ステップ
# ---------------------------------------------------------------------------

class AssertNoConsoleErrorStep(BaseModel):
    """ブラウザコンソールにエラーが出力されていないことを検証するステップ。

    テスト実行中にコンソールに出力されたエラーメッセージを検査し、
    エラーが存在する場合はテストを失敗させる。
    """

    assertNoConsoleError: bool = Field(
        default=True, description="コンソールエラー検証のマーカー"
    )
    name: Optional[str] = Field(default=None, description="ステップ名（任意）")


# ---------------------------------------------------------------------------
# API モック / ルートスタブステップ
# ---------------------------------------------------------------------------

class ApiMockResponse(BaseModel):
    """API モックのレスポンス定義。"""

    status: int = Field(default=200, description="HTTP ステータスコード")
    body: Union[str, dict] = Field(..., description="レスポンスボディ（文字列または辞書）")


class ApiMockStep(BaseModel):
    """Playwright route を用いた API モックを1ステップで設定するステップ。

    指定した URL パターンとメソッドに対して、固定レスポンスを返す。
    E2E テストの安定化に使用する。
    """

    apiMock: str = Field(..., description="モック対象の URL パターン")
    url: str = Field(..., description="モック対象の URL パターン")
    method: Optional[str] = Field(
        default=None, description="HTTP メソッド（GET, POST 等）。None で全メソッド対象"
    )
    response: ApiMockResponse = Field(..., description="返却するレスポンス定義")
    name: Optional[str] = Field(default=None, description="ステップ名（任意）")


class RouteStubStep(BaseModel):
    """Playwright route を用いた API スタブを1ステップで設定するステップ。

    指定した URL パターンに対して、カスタムハンドラを適用する。
    apiMock より柔軟なレスポンス制御が可能。
    """

    routeStub: str = Field(..., description="スタブ対象の URL パターン")
    url: str = Field(..., description="スタブ対象の URL パターン")
    handler: str = Field(..., description="ハンドラ関数名またはインライン定義")
    name: Optional[str] = Field(default=None, description="ステップ名（任意）")


# ---------------------------------------------------------------------------
# StepType Union 型
# ---------------------------------------------------------------------------

StepType = Union[
    # ナビゲーション
    GotoStep,
    BackStep,
    ReloadStep,
    # 操作
    ClickStep,
    DblClickStep,
    FillStep,
    PressStep,
    CheckStep,
    UncheckStep,
    SelectOptionStep,
    # 待機
    WaitForStep,
    WaitForVisibleStep,
    WaitForHiddenStep,
    WaitForNetworkIdleStep,
    # 検証
    ExpectVisibleStep,
    ExpectHiddenStep,
    ExpectTextStep,
    ExpectUrlStep,
    # 取得
    StoreTextStep,
    StoreAttrStep,
    # デバッグ
    ScreenshotStep,
    LogStep,
    DumpDomStep,
    # セッション
    UseStorageStateStep,
    SaveStorageStateStep,
    # 高レベル（Overlay / Wijmo / JS生成UI）
    SelectOverlayOptionStep,
    SelectWijmoComboStep,
    ClickWijmoGridCellStep,
    SetDatePickerStep,
    UploadFileStep,
    WaitForToastStep,
    AssertNoConsoleErrorStep,
    ApiMockStep,
    RouteStubStep,
]
"""全ステップ型の Union（標準 + 高レベル）。

Scenario モデルの steps フィールドで使用する。
"""


# ===========================================================================
# Scenario 関連モデル定義
#
# 要件 3.1: title, baseUrl, vars, artifacts, hooks, steps, healing フィールド
# 要件 3.2: ${env.X}, ${vars.X} の変数展開構文サポート
# 要件 3.3: secret: true フラグによる秘密値マスク
# 要件 3.4: artifacts（screenshots, trace, video）の設定
# 要件 3.5: hooks（beforeEachStep, afterEachStep）の定義
# 要件 3.6: section によるステップのグループ化
# ===========================================================================

# 変数展開構文のパターン: ${env.X} または ${vars.X}
_VAR_PATTERN = re.compile(r"\$\{(env|vars)\.[a-zA-Z_][a-zA-Z0-9_]*\}")


# ---------------------------------------------------------------------------
# アーティファクト設定
# ---------------------------------------------------------------------------

class ScreenshotConfig(BaseModel):
    """スクリーンショット撮影の設定。

    mode でステップ前後の撮影タイミングを制御し、
    format と quality で画像品質を指定する。
    """

    mode: Literal["before_each_step", "before_and_after", "none"] = Field(
        default="before_each_step",
        description="撮影モード（before_each_step / before_and_after / none）",
    )
    format: Literal["jpeg", "png"] = Field(
        default="jpeg", description="画像フォーマット"
    )
    quality: int = Field(
        default=70, ge=1, le=100, description="JPEG 品質（1〜100）"
    )


class TraceConfig(BaseModel):
    """Playwright トレースの設定。

    mode で記録タイミングを制御する。on_failure は失敗時のみ保存。
    """

    mode: Literal["on_failure", "always", "none"] = Field(
        default="on_failure",
        description="トレース記録モード（on_failure / always / none）",
    )


class VideoConfig(BaseModel):
    """動画録画の設定。

    mode で録画タイミングを制御する。on_failure は失敗時のみ保存。
    """

    mode: Literal["on_failure", "always", "none"] = Field(
        default="on_failure",
        description="動画録画モード（on_failure / always / none）",
    )


class ArtifactsConfig(BaseModel):
    """テスト実行成果物の設定。

    screenshots, trace, video の各設定をまとめて管理する。
    """

    screenshots: ScreenshotConfig = Field(
        default_factory=ScreenshotConfig,
        description="スクリーンショット設定",
    )
    trace: TraceConfig = Field(
        default_factory=TraceConfig,
        description="トレース設定",
    )
    video: VideoConfig = Field(
        default_factory=VideoConfig,
        description="動画設定",
    )


# ---------------------------------------------------------------------------
# フック設定
# ---------------------------------------------------------------------------

class HooksConfig(BaseModel):
    """ステップ実行前後のフック定義。

    beforeEachStep: 各ステップ実行前に実行するステップ配列
    afterEachStep: 各ステップ実行後に実行するステップ配列
    """

    beforeEachStep: list[dict] = Field(
        default_factory=list,
        description="各ステップ実行前に実行するステップ配列",
    )
    afterEachStep: list[dict] = Field(
        default_factory=list,
        description="各ステップ実行後に実行するステップ配列",
    )


# ---------------------------------------------------------------------------
# セクション定義
# ---------------------------------------------------------------------------

class Section(BaseModel):
    """ステップのグループ化と章立てを表現するセクション。

    複数のステップを論理的にまとめ、テストの意図を章立てで表現する。
    """

    section: str = Field(..., description="セクション名（章タイトル）")
    steps: list[dict] = Field(
        default_factory=list,
        description="セクション内のステップ配列",
    )


# ---------------------------------------------------------------------------
# Scenario 定義
# ---------------------------------------------------------------------------

class Scenario(BaseModel):
    """YAML DSL のルートモデル。1つのテストシナリオを表現する。

    title と baseUrl は必須フィールド。
    vars フィールドでは ${env.X}（環境変数参照）および
    ${vars.X}（シナリオ変数参照）の変数展開構文をサポートする。
    healing フィールドでセレクタ自己修復モードを制御する。
    """

    title: str = Field(..., description="シナリオ名")
    baseUrl: str = Field(..., description="基準 URL")
    vars: dict[str, str] = Field(
        default_factory=dict,
        description="変数定義（${env.X} / ${vars.X} 構文をサポート）",
    )
    artifacts: ArtifactsConfig = Field(
        default_factory=ArtifactsConfig,
        description="成果物設定",
    )
    hooks: HooksConfig = Field(
        default_factory=HooksConfig,
        description="フック定義（beforeEachStep / afterEachStep）",
    )
    steps: list[dict] = Field(
        ..., description="ステップ配列（YAML からの柔軟なパース用に dict 型）"
    )
    healing: Literal["off", "safe"] = Field(
        default="off",
        description="セレクタ自己修復モード（off: 即エラー / safe: 再解決試行）",
    )

    @field_validator("vars")
    @classmethod
    def validate_vars_values(cls, v: dict[str, str]) -> dict[str, str]:
        """vars の値に含まれる変数展開構文をバリデーションする。

        ${env.X} および ${vars.X} パターンのみを許可する。
        不正な構文（例: ${unknown.X}）が含まれる場合はエラーを返す。
        """
        # 不正な変数参照パターン: ${ で始まるが env. / vars. 以外のもの
        _INVALID_VAR_PATTERN = re.compile(
            r"\$\{(?!env\.|vars\.)[^}]*\}"
        )
        for key, value in v.items():
            invalid_matches = _INVALID_VAR_PATTERN.findall(value)
            if invalid_matches:
                raise ValueError(
                    f"vars['{key}'] に不正な変数参照が含まれています: "
                    f"{', '.join(invalid_matches)}。"
                    f"使用可能な構文は ${{env.X}} または ${{vars.X}} です。"
                )
        return v
