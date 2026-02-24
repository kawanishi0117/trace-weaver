"""
StepRegistry のテスト

StepRegistry の register / get / list_all の動作確認、
未登録ステップの KeyError、Protocol 準拠チェックを検証する。
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from src.steps.registry import StepContext, StepHandler, StepInfo, StepRegistry


# ---------------------------------------------------------------------------
# テスト用ダミーハンドラ
# ---------------------------------------------------------------------------

class DummyParams(BaseModel):
    """テスト用パラメータスキーマ。"""
    value: str = ""


class DummyHandler:
    """StepHandler Protocol を満たすテスト用ハンドラ。"""

    async def execute(self, page, params: dict, context: StepContext) -> None:
        pass

    def get_schema(self) -> type[BaseModel]:
        return DummyParams


class AnotherDummyHandler:
    """上書きテスト用の別ハンドラ。"""

    async def execute(self, page, params: dict, context: StepContext) -> None:
        pass

    def get_schema(self) -> type[BaseModel]:
        return DummyParams


class InvalidHandler:
    """StepHandler Protocol を満たさないハンドラ（execute がない）。"""

    def get_schema(self) -> type[BaseModel]:
        return DummyParams


# ---------------------------------------------------------------------------
# register / get テスト
# ---------------------------------------------------------------------------

class TestStepRegistryRegisterGet:
    """register() と get() の基本動作テスト。"""

    def test_register_and_get(self):
        """登録したハンドラを get() で取得できること。"""
        registry = StepRegistry()
        handler = DummyHandler()
        registry.register("test-step", handler)

        result = registry.get("test-step")
        assert result is handler

    def test_get_unregistered_raises_key_error(self):
        """未登録のステップ名で get() すると KeyError が発生すること。"""
        registry = StepRegistry()

        with pytest.raises(KeyError):
            registry.get("nonexistent")

    def test_register_with_info(self):
        """StepInfo 付きで登録し、list_all() に反映されること。"""
        registry = StepRegistry()
        info = StepInfo(name="my-step", description="テスト用ステップ", category="test")
        registry.register("my-step", DummyHandler(), info=info)

        all_steps = registry.list_all()
        assert len(all_steps) == 1
        assert all_steps[0].name == "my-step"
        assert all_steps[0].description == "テスト用ステップ"
        assert all_steps[0].category == "test"

    def test_register_without_info_uses_default(self):
        """StepInfo なしで登録するとデフォルトのメタ情報が生成されること。"""
        registry = StepRegistry()
        registry.register("auto-info", DummyHandler())

        all_steps = registry.list_all()
        assert len(all_steps) == 1
        assert all_steps[0].name == "auto-info"
        assert all_steps[0].category == "unknown"

    def test_register_overwrite(self):
        """同名のハンドラを上書き登録できること。"""
        registry = StepRegistry()
        handler1 = DummyHandler()
        handler2 = AnotherDummyHandler()

        registry.register("overwrite-step", handler1)
        registry.register("overwrite-step", handler2)

        result = registry.get("overwrite-step")
        assert result is handler2

    def test_register_invalid_handler_raises_type_error(self):
        """StepHandler Protocol を満たさないハンドラで TypeError が発生すること。"""
        registry = StepRegistry()

        with pytest.raises(TypeError, match="StepHandler Protocol"):
            registry.register("invalid", InvalidHandler())


# ---------------------------------------------------------------------------
# list_all テスト
# ---------------------------------------------------------------------------

class TestStepRegistryListAll:
    """list_all() の動作テスト。"""

    def test_list_all_empty(self):
        """空のレジストリで list_all() が空リストを返すこと。"""
        registry = StepRegistry()
        assert registry.list_all() == []

    def test_list_all_sorted(self):
        """list_all() がステップ名のアルファベット順でソートされること。"""
        registry = StepRegistry()
        registry.register("zebra", DummyHandler(), info=StepInfo("zebra", "Z", "test"))
        registry.register("alpha", DummyHandler(), info=StepInfo("alpha", "A", "test"))
        registry.register("middle", DummyHandler(), info=StepInfo("middle", "M", "test"))

        names = [s.name for s in registry.list_all()]
        assert names == ["alpha", "middle", "zebra"]

    def test_list_all_count(self):
        """登録数と list_all() の件数が一致すること。"""
        registry = StepRegistry()
        for i in range(5):
            registry.register(f"step-{i}", DummyHandler())

        assert len(registry.list_all()) == 5


# ---------------------------------------------------------------------------
# has / names テスト
# ---------------------------------------------------------------------------

class TestStepRegistryHasNames:
    """has() と names プロパティのテスト。"""

    def test_has_registered(self):
        """登録済みステップに対して has() が True を返すこと。"""
        registry = StepRegistry()
        registry.register("exists", DummyHandler())
        assert registry.has("exists") is True

    def test_has_unregistered(self):
        """未登録ステップに対して has() が False を返すこと。"""
        registry = StepRegistry()
        assert registry.has("missing") is False

    def test_names_sorted(self):
        """names プロパティがソート済みリストを返すこと。"""
        registry = StepRegistry()
        registry.register("c", DummyHandler())
        registry.register("a", DummyHandler())
        registry.register("b", DummyHandler())

        assert registry.names == ["a", "b", "c"]


# ---------------------------------------------------------------------------
# StepHandler Protocol チェック
# ---------------------------------------------------------------------------

class TestStepHandlerProtocol:
    """StepHandler Protocol の runtime_checkable テスト。"""

    def test_dummy_handler_is_step_handler(self):
        """DummyHandler が StepHandler Protocol を満たすこと。"""
        handler = DummyHandler()
        assert isinstance(handler, StepHandler)

    def test_invalid_handler_is_not_step_handler(self):
        """InvalidHandler が StepHandler Protocol を満たさないこと。"""
        handler = InvalidHandler()
        assert not isinstance(handler, StepHandler)
