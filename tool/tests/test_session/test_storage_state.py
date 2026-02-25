"""
????????useStorageState / saveStorageState???????

saveStorageState ?????????????
useStorageState ???????????????????????????

?????:
  - SaveStorageStateHandler: ??????????
  - UseStorageStateHandler: ??????????
  - ????????: ?? ? ????????
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from brt.steps.builtin import (
    SaveStorageStateHandler,
    UseStorageStateHandler,
)
from brt.steps.registry import StepContext


# ---------------------------------------------------------------------------
# ????: ?????
# ---------------------------------------------------------------------------

def _make_context() -> StepContext:
    """????? StepContext ??????"""
    ctx = MagicMock(spec=StepContext)
    ctx.selector_resolver = MagicMock()
    ctx.variable_expander = MagicMock()
    ctx.console_errors = []
    return ctx


def _make_page_with_storage(storage_data: dict) -> AsyncMock:
    """????????????????? Page ??????"""
    page = AsyncMock()
    context = AsyncMock()

    async def mock_storage_state(path: str | None = None) -> dict:
        if path is not None:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(storage_data, f, ensure_ascii=False)
        return storage_data

    context.storage_state = mock_storage_state
    context.add_cookies = AsyncMock()
    page.context = context
    return page


# ===========================================================================
# ???: SaveStorageStateHandler
# ===========================================================================

class TestSaveStorageState:
    """saveStorageState ?????????"""

    def test_save_creates_file(self, tmp_path: Path) -> None:
        """????????????????????"""
        handler = SaveStorageStateHandler()
        storage_data = {
            "cookies": [{"name": "session", "value": "abc123", "domain": "localhost"}],
            "origins": [],
        }
        page = _make_page_with_storage(storage_data)
        ctx = _make_context()
        save_path = tmp_path / "state.json"

        asyncio.run(
            handler.execute(page, {"path": str(save_path)}, ctx)
        )

        assert save_path.exists()

    def test_save_writes_valid_json(self, tmp_path: Path) -> None:
        """????????????? JSON ??????"""
        handler = SaveStorageStateHandler()
        storage_data = {
            "cookies": [{"name": "token", "value": "xyz", "domain": "example.com"}],
            "origins": [],
        }
        page = _make_page_with_storage(storage_data)
        ctx = _make_context()
        save_path = tmp_path / "state.json"

        asyncio.run(
            handler.execute(page, {"path": str(save_path)}, ctx)
        )

        with open(save_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert "cookies" in loaded

    def test_save_creates_parent_dirs(self, tmp_path: Path) -> None:
        """??????????????????????????"""
        handler = SaveStorageStateHandler()
        storage_data: dict = {"cookies": [], "origins": []}
        page = _make_page_with_storage(storage_data)
        ctx = _make_context()
        save_path = tmp_path / "nested" / "deep" / "state.json"

        asyncio.run(
            handler.execute(page, {"path": str(save_path)}, ctx)
        )

        assert save_path.exists()

    def test_save_preserves_cookie_data(self, tmp_path: Path) -> None:
        """???????????????????"""
        handler = SaveStorageStateHandler()
        cookies = [
            {"name": "session_id", "value": "s123", "domain": "app.example.com"},
            {"name": "csrf", "value": "token456", "domain": "app.example.com"},
        ]
        storage_data = {"cookies": cookies, "origins": []}
        page = _make_page_with_storage(storage_data)
        ctx = _make_context()
        save_path = tmp_path / "state.json"

        asyncio.run(
            handler.execute(page, {"path": str(save_path)}, ctx)
        )

        with open(save_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert len(loaded["cookies"]) == 2
        assert loaded["cookies"][0]["name"] == "session_id"
        assert loaded["cookies"][1]["value"] == "token456"


# ===========================================================================
# ???: UseStorageStateHandler
# ===========================================================================

class TestUseStorageState:
    """useStorageState ?????????"""

    def test_load_applies_cookies(self, tmp_path: Path) -> None:
        """?????????????????????????"""
        handler = UseStorageStateHandler()
        state_path = tmp_path / "state.json"
        cookies = [{"name": "session", "value": "abc", "domain": "localhost"}]
        state_path.write_text(
            json.dumps({"cookies": cookies, "origins": []}),
            encoding="utf-8",
        )

        page = AsyncMock()
        page.context = AsyncMock()
        page.context.add_cookies = AsyncMock()
        ctx = _make_context()

        asyncio.run(
            handler.execute(page, {"path": str(state_path)}, ctx)
        )

        page.context.add_cookies.assert_called_once_with(cookies)

    def test_load_file_not_found_raises(self, tmp_path: Path) -> None:
        """????????????????? FileNotFoundError ????????"""
        handler = UseStorageStateHandler()
        page = AsyncMock()
        ctx = _make_context()
        missing_path = tmp_path / "nonexistent.json"

        with pytest.raises(FileNotFoundError):
            asyncio.run(
                handler.execute(page, {"path": str(missing_path)}, ctx)
            )

    def test_load_multiple_cookies(self, tmp_path: Path) -> None:
        """??????????????????"""
        handler = UseStorageStateHandler()
        state_path = tmp_path / "state.json"
        cookies = [
            {"name": "a", "value": "1", "domain": "localhost"},
            {"name": "b", "value": "2", "domain": "localhost"},
            {"name": "c", "value": "3", "domain": "localhost"},
        ]
        state_path.write_text(
            json.dumps({"cookies": cookies, "origins": []}),
            encoding="utf-8",
        )

        page = AsyncMock()
        page.context = AsyncMock()
        page.context.add_cookies = AsyncMock()
        ctx = _make_context()

        asyncio.run(
            handler.execute(page, {"path": str(state_path)}, ctx)
        )

        page.context.add_cookies.assert_called_once_with(cookies)

    def test_load_empty_cookies(self, tmp_path: Path) -> None:
        """??????????????????????"""
        handler = UseStorageStateHandler()
        state_path = tmp_path / "state.json"
        state_path.write_text(
            json.dumps({"cookies": [], "origins": []}),
            encoding="utf-8",
        )

        page = AsyncMock()
        page.context = AsyncMock()
        page.context.add_cookies = AsyncMock()
        ctx = _make_context()

        asyncio.run(
            handler.execute(page, {"path": str(state_path)}, ctx)
        )

        page.context.add_cookies.assert_called_once_with([])


# ===========================================================================
# ???: ??????????? ? ???
# ===========================================================================

class TestStorageStateRoundTrip:
    """saveStorageState -> useStorageState ?????????????"""

    def test_roundtrip_preserves_cookies(self, tmp_path: Path) -> None:
        """?? ? ???????????????????"""
        save_handler = SaveStorageStateHandler()
        load_handler = UseStorageStateHandler()
        state_path = tmp_path / "roundtrip.json"

        # ????????????
        original_cookies = [
            {"name": "auth", "value": "token-xyz", "domain": "app.test"},
            {"name": "pref", "value": "dark", "domain": "app.test"},
        ]
        storage_data = {"cookies": original_cookies, "origins": []}

        # ??
        save_page = _make_page_with_storage(storage_data)
        ctx = _make_context()
        asyncio.run(
            save_handler.execute(save_page, {"path": str(state_path)}, ctx)
        )

        # ??
        load_page = AsyncMock()
        load_page.context = AsyncMock()
        load_page.context.add_cookies = AsyncMock()
        asyncio.run(
            load_handler.execute(load_page, {"path": str(state_path)}, ctx)
        )

        # ???????????????????
        loaded_cookies = load_page.context.add_cookies.call_args[0][0]
        assert len(loaded_cookies) == 2
        assert loaded_cookies[0]["name"] == "auth"
        assert loaded_cookies[0]["value"] == "token-xyz"
        assert loaded_cookies[1]["name"] == "pref"
        assert loaded_cookies[1]["value"] == "dark"

    def test_roundtrip_empty_state(self, tmp_path: Path) -> None:
        """???????????????????????????"""
        save_handler = SaveStorageStateHandler()
        load_handler = UseStorageStateHandler()
        state_path = tmp_path / "empty.json"

        storage_data: dict = {"cookies": [], "origins": []}

        # ??
        save_page = _make_page_with_storage(storage_data)
        ctx = _make_context()
        asyncio.run(
            save_handler.execute(save_page, {"path": str(state_path)}, ctx)
        )

        # ??
        load_page = AsyncMock()
        load_page.context = AsyncMock()
        load_page.context.add_cookies = AsyncMock()
        asyncio.run(
            load_handler.execute(load_page, {"path": str(state_path)}, ctx)
        )

        load_page.context.add_cookies.assert_called_once_with([])
