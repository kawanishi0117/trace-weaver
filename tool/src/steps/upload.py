"""
ファイルアップロードステップハンドラ — uploadFile

input[type=file] または UI ボタン経由のファイルアップロードを1ステップで実行する。

要件 6.7: uploadFile ステップの提供
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel

from .builtin import _resolve_selector
from .registry import StepContext, StepInfo

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# パラメータスキーマ
# ---------------------------------------------------------------------------

class UploadFileParams(BaseModel):
    """uploadFile ステップのパラメータ。"""

    by: dict
    filePath: str
    name: str | None = None


# ---------------------------------------------------------------------------
# ハンドラ
# ---------------------------------------------------------------------------

class UploadFileHandler:
    """uploadFile — ファイルアップロードを1ステップで実行。

    実行フロー:
      1. by セレクタでファイル入力要素を特定
      2. input[type=file] の場合は set_input_files() で直接設定
      3. UI ボタンの場合は file chooser イベントを待機してファイルを設定
    """

    async def execute(self, page: Page, params: dict, context: StepContext) -> None:
        by = params["by"]
        file_path = params["filePath"]

        logger.info("uploadFile: by=%s, filePath='%s'", by, file_path)

        # ファイルの存在確認
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"アップロードファイルが見つかりません: {file_path}")

        locator = await _resolve_selector(page, by, context)

        # input[type=file] かどうかを判定
        tag_name = await locator.evaluate("el => el.tagName.toLowerCase()")
        input_type = await locator.evaluate("el => el.type || ''")

        if tag_name == "input" and input_type == "file":
            # input[type=file] の場合は直接ファイルを設定
            await locator.set_input_files(str(path))
        else:
            # UI ボタンの場合は file chooser イベントを待機
            async with page.expect_file_chooser() as fc_info:
                await locator.click()
            file_chooser = await fc_info.value
            await file_chooser.set_files(str(path))

        logger.info("uploadFile: '%s' をアップロードしました", file_path)

    def get_schema(self) -> type[BaseModel]:
        return UploadFileParams


# ---------------------------------------------------------------------------
# レジストリ登録用情報
# ---------------------------------------------------------------------------

UPLOAD_STEP_INFO = StepInfo(
    name="uploadFile",
    description="ファイルアップロードを1ステップで実行",
    category="high-level",
)
