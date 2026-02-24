"""
ステップライブラリモジュール

標準ステップ、高レベルステップ（Overlay/Wijmo 等）、プラグイン機構を提供する。

主要エクスポート:
  - StepRegistry: ステップハンドラの登録・検索・一覧
  - StepHandler: ステップハンドラの共通 Protocol
  - StepContext: ステップ実行コンテキスト
  - StepInfo: ステップのメタ情報
  - create_default_registry: 全ステップ登録済みレジストリの生成
"""

from .registry import StepContext, StepHandler, StepInfo, StepRegistry

__all__ = [
    "StepContext",
    "StepHandler",
    "StepInfo",
    "StepRegistry",
    "create_full_registry",
]


def create_full_registry() -> StepRegistry:
    """標準ステップ + 高レベルステップが全て登録された StepRegistry を生成する。

    Returns:
        全ステップが登録された StepRegistry
    """
    from .builtin import create_default_registry
    from .datepicker import DATEPICKER_STEP_INFO, SetDatePickerHandler
    from .overlay import OVERLAY_STEP_INFO, SelectOverlayOptionHandler
    from .upload import UPLOAD_STEP_INFO, UploadFileHandler
    from .wijmo_combo import WIJMO_COMBO_STEP_INFO, SelectWijmoComboHandler
    from .wijmo_grid import WIJMO_GRID_STEP_INFO, ClickWijmoGridCellHandler

    # 標準ステップが登録済みのレジストリを取得
    registry = create_default_registry()

    # 高レベルステップを追加登録
    registry.register(
        "selectOverlayOption",
        SelectOverlayOptionHandler(),
        info=OVERLAY_STEP_INFO,
    )
    registry.register(
        "selectWijmoCombo",
        SelectWijmoComboHandler(),
        info=WIJMO_COMBO_STEP_INFO,
    )
    registry.register(
        "clickWijmoGridCell",
        ClickWijmoGridCellHandler(),
        info=WIJMO_GRID_STEP_INFO,
    )
    registry.register(
        "setDatePicker",
        SetDatePickerHandler(),
        info=DATEPICKER_STEP_INFO,
    )
    registry.register(
        "uploadFile",
        UploadFileHandler(),
        info=UPLOAD_STEP_INFO,
    )

    return registry
