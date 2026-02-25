"""
VariableExpander のユニットテスト

変数展開エンジンの動作を検証する。
${env.X} → 環境変数参照、${vars.X} → シナリオ変数参照の展開処理、
未定義変数参照時のエラーハンドリング、ステップ辞書の再帰展開をテストする。

要件 3.2: ${env.X}, ${vars.X} の変数展開構文サポート
"""

import pytest

from brt.dsl.variables import VariableExpander, VariableNotFoundError


# ---------------------------------------------------------------------------
# フィクスチャ
# ---------------------------------------------------------------------------

@pytest.fixture
def expander() -> VariableExpander:
    """基本的な VariableExpander インスタンスを提供する。"""
    return VariableExpander(
        env={"EMAIL": "admin@example.com", "PASSWORD": "secret123", "BASE_URL": "http://localhost:4200"},
        vars={"email": "test@example.com", "name": "テストユーザー"},
    )


@pytest.fixture
def empty_expander() -> VariableExpander:
    """空の辞書で初期化された VariableExpander を提供する。"""
    return VariableExpander(env={}, vars={})


# ---------------------------------------------------------------------------
# expand() テスト — 環境変数展開
# ---------------------------------------------------------------------------

class TestExpandEnv:
    """${env.X} の展開テスト。"""

    def test_expand_single_env_var(self, expander: VariableExpander):
        """単一の環境変数参照が正しく展開されること。"""
        result = expander.expand("${env.EMAIL}")
        assert result == "admin@example.com"

    def test_expand_env_var_in_text(self, expander: VariableExpander):
        """テキスト中の環境変数参照が正しく展開されること。"""
        result = expander.expand("ログイン: ${env.EMAIL}")
        assert result == "ログイン: admin@example.com"

    def test_expand_multiple_env_vars(self, expander: VariableExpander):
        """複数の環境変数参照が正しく展開されること。"""
        result = expander.expand("${env.EMAIL} / ${env.PASSWORD}")
        assert result == "admin@example.com / secret123"

    def test_expand_env_var_with_underscore(self, expander: VariableExpander):
        """アンダースコアを含む環境変数名が展開されること。"""
        result = expander.expand("${env.BASE_URL}/login")
        assert result == "http://localhost:4200/login"

    def test_expand_undefined_env_var_raises(self, expander: VariableExpander):
        """未定義の環境変数参照で VariableNotFoundError が発生すること。"""
        with pytest.raises(VariableNotFoundError) as exc_info:
            expander.expand("${env.UNDEFINED_VAR}")
        assert exc_info.value.namespace == "env"
        assert exc_info.value.var_name == "UNDEFINED_VAR"


# ---------------------------------------------------------------------------
# expand() テスト — シナリオ変数展開
# ---------------------------------------------------------------------------

class TestExpandVars:
    """${vars.X} の展開テスト。"""

    def test_expand_single_vars_ref(self, expander: VariableExpander):
        """単一のシナリオ変数参照が正しく展開されること。"""
        result = expander.expand("${vars.email}")
        assert result == "test@example.com"

    def test_expand_vars_ref_in_text(self, expander: VariableExpander):
        """テキスト中のシナリオ変数参照が正しく展開されること。"""
        result = expander.expand("こんにちは、${vars.name}さん")
        assert result == "こんにちは、テストユーザーさん"

    def test_expand_undefined_vars_ref_raises(self, expander: VariableExpander):
        """未定義のシナリオ変数参照で VariableNotFoundError が発生すること。"""
        with pytest.raises(VariableNotFoundError) as exc_info:
            expander.expand("${vars.undefined}")
        assert exc_info.value.namespace == "vars"
        assert exc_info.value.var_name == "undefined"


# ---------------------------------------------------------------------------
# expand() テスト — 混合・エッジケース
# ---------------------------------------------------------------------------

class TestExpandMixed:
    """env と vars の混合、およびエッジケースのテスト。"""

    def test_expand_mixed_env_and_vars(self, expander: VariableExpander):
        """env と vars の混在参照が正しく展開されること。"""
        result = expander.expand("${env.BASE_URL}/users/${vars.email}")
        assert result == "http://localhost:4200/users/test@example.com"

    def test_expand_no_variables(self, expander: VariableExpander):
        """変数参照を含まないテキストがそのまま返されること。"""
        result = expander.expand("プレーンテキスト")
        assert result == "プレーンテキスト"

    def test_expand_empty_string(self, expander: VariableExpander):
        """空文字列がそのまま返されること。"""
        result = expander.expand("")
        assert result == ""

    def test_expand_preserves_surrounding_text(self, expander: VariableExpander):
        """変数参照の前後のテキストが保持されること。"""
        result = expander.expand("前 ${env.EMAIL} 後")
        assert result == "前 admin@example.com 後"

    def test_no_unresolved_patterns_after_expand(self, expander: VariableExpander):
        """展開後に未解決の ${...} パターンが残らないこと。"""
        result = expander.expand("${env.EMAIL} と ${vars.name}")
        assert "${" not in result


# ---------------------------------------------------------------------------
# set_var() テスト
# ---------------------------------------------------------------------------

class TestSetVar:
    """set_var() メソッドのテスト（storeText / storeAttr 用）。"""

    def test_set_var_and_expand(self, expander: VariableExpander):
        """set_var() で設定した変数が展開可能になること。"""
        expander.set_var("new_value", "動的に設定された値")
        result = expander.expand("${vars.new_value}")
        assert result == "動的に設定された値"

    def test_set_var_overwrites_existing(self, expander: VariableExpander):
        """set_var() で既存の変数を上書きできること。"""
        expander.set_var("email", "updated@example.com")
        result = expander.expand("${vars.email}")
        assert result == "updated@example.com"

    def test_set_var_used_in_subsequent_expand(self, expander: VariableExpander):
        """set_var() で設定した変数が後続の展開で使用できること。"""
        expander.set_var("token", "abc123")
        result = expander.expand("Bearer ${vars.token}")
        assert result == "Bearer abc123"


# ---------------------------------------------------------------------------
# expand_step() テスト
# ---------------------------------------------------------------------------

class TestExpandStep:
    """expand_step() メソッドのテスト（ステップ辞書の再帰展開）。"""

    def test_expand_step_simple(self, expander: VariableExpander):
        """単純なステップ辞書の文字列値が展開されること。"""
        step = {"goto": "${env.BASE_URL}/login", "name": "open-login"}
        result = expander.expand_step(step)
        assert result["goto"] == "http://localhost:4200/login"
        assert result["name"] == "open-login"

    def test_expand_step_nested_dict(self, expander: VariableExpander):
        """ネストされた辞書内の文字列値が展開されること。"""
        step = {
            "fill": {
                "by": {"css": "#email"},
                "value": "${vars.email}",
                "name": "fill-email",
            }
        }
        result = expander.expand_step(step)
        assert result["fill"]["value"] == "test@example.com"
        assert result["fill"]["by"]["css"] == "#email"

    def test_expand_step_preserves_non_string_values(self, expander: VariableExpander):
        """非文字列値（bool, int, None）がそのまま保持されること。"""
        step = {
            "fill": {
                "by": {"css": "#password"},
                "value": "${env.PASSWORD}",
                "secret": True,
                "timeout": 5000,
                "optional": None,
            }
        }
        result = expander.expand_step(step)
        assert result["fill"]["value"] == "secret123"
        assert result["fill"]["secret"] is True
        assert result["fill"]["timeout"] == 5000
        assert result["fill"]["optional"] is None

    def test_expand_step_with_list(self, expander: VariableExpander):
        """リスト内の文字列値が展開されること。"""
        step = {
            "any": [
                {"testId": "${vars.name}"},
                {"css": "#${vars.email}"},
            ]
        }
        result = expander.expand_step(step)
        assert result["any"][0]["testId"] == "テストユーザー"
        assert result["any"][1]["css"] == "#test@example.com"

    def test_expand_step_returns_new_dict(self, expander: VariableExpander):
        """expand_step() が元の辞書を変更せず新しい辞書を返すこと。"""
        original = {"goto": "${env.BASE_URL}/login"}
        result = expander.expand_step(original)
        # 元の辞書は変更されていない
        assert original["goto"] == "${env.BASE_URL}/login"
        assert result["goto"] == "http://localhost:4200/login"

    def test_expand_step_undefined_var_raises(self, expander: VariableExpander):
        """ステップ内の未定義変数参照で VariableNotFoundError が発生すること。"""
        step = {"goto": "${vars.undefined_url}"}
        with pytest.raises(VariableNotFoundError):
            expander.expand_step(step)


# ---------------------------------------------------------------------------
# プロパティアクセステスト
# ---------------------------------------------------------------------------

class TestExpanderProperties:
    """env / vars プロパティのテスト。"""

    def test_env_property_returns_copy(self, expander: VariableExpander):
        """env プロパティが辞書のコピーを返すこと。"""
        env_copy = expander.env
        env_copy["NEW_KEY"] = "new_value"
        # 内部状態は変更されていない
        assert "NEW_KEY" not in expander.env

    def test_vars_property_returns_copy(self, expander: VariableExpander):
        """vars プロパティが辞書のコピーを返すこと。"""
        vars_copy = expander.vars
        vars_copy["new_key"] = "new_value"
        # 内部状態は変更されていない
        assert "new_key" not in expander.vars

    def test_constructor_copies_input_dicts(self):
        """コンストラクタが入力辞書をコピーすること（外部変更の影響を受けない）。"""
        env = {"KEY": "value"}
        vars_dict = {"var": "val"}
        expander = VariableExpander(env=env, vars=vars_dict)

        # 元の辞書を変更
        env["KEY"] = "changed"
        vars_dict["var"] = "changed"

        # expander 内部は変更されていない
        assert expander.expand("${env.KEY}") == "value"
        assert expander.expand("${vars.var}") == "val"


# ---------------------------------------------------------------------------
# VariableNotFoundError テスト
# ---------------------------------------------------------------------------

class TestVariableNotFoundError:
    """VariableNotFoundError 例外のテスト。"""

    def test_error_message_contains_variable_info(self):
        """エラーメッセージに名前空間と変数名が含まれること。"""
        error = VariableNotFoundError("env", "MISSING")
        assert "env" in str(error)
        assert "MISSING" in str(error)
        assert "${env.MISSING}" in str(error)

    def test_error_attributes(self):
        """例外の属性が正しく設定されること。"""
        error = VariableNotFoundError("vars", "unknown")
        assert error.namespace == "vars"
        assert error.var_name == "unknown"
