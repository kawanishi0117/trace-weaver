"""
Heuristics のユニットテスト

Mapper が生成した DSL ステップリストに対するヒューリスティック処理を検証する。
テストは最低25個以上作成し、以下のカテゴリをカバーする:
  - auto_name: 各ステップ種別の名前生成
  - auto_name: 名前の文字制限（40文字切り詰め）
  - auto_name: 各セレクタ種別からの target 抽出
  - detect_secret: パスワード関連キーワードの検出
  - detect_secret: 日本語キーワード
  - detect_secret: fill 以外のステップでは False
  - auto_section: goto によるセクション分割
  - auto_section: ステップ数が少ない場合はセクション化しない
  - insert_expects: click 後の expectVisible 挿入
  - insert_expects: 既に expect がある場合は挿入しない
  - insert_expects: with_expects=False の場合は挿入しない
  - apply: 全ヒューリスティックの統合テスト
"""

from __future__ import annotations

import pytest

from src.importer.heuristics import Heuristics


# ---------------------------------------------------------------------------
# フィクスチャ
# ---------------------------------------------------------------------------

@pytest.fixture
def heuristics() -> Heuristics:
    """with_expects=False の Heuristics インスタンスを提供する。"""
    return Heuristics(with_expects=False)


@pytest.fixture
def heuristics_with_expects() -> Heuristics:
    """with_expects=True の Heuristics インスタンスを提供する。"""
    return Heuristics(with_expects=True)


# ===========================================================================
# 1. auto_name: 各ステップ種別の名前生成
# ===========================================================================

class TestAutoNameStepTypes:
    """各ステップ種別に対する auto_name のテスト。"""

    def test_goto_name(self, heuristics: Heuristics) -> None:
        """goto ステップの名前が navigate-to-{path} 形式であること。"""
        step = {"goto": {"url": "https://example.com/login"}}
        name = heuristics.auto_name(step)
        assert name == "navigate-to-login"

    def test_goto_root_path(self, heuristics: Heuristics) -> None:
        """goto でルートパスの場合の名前生成。"""
        step = {"goto": {"url": "https://example.com/"}}
        name = heuristics.auto_name(step)
        assert name == "navigate-to"

    def test_click_name(self, heuristics: Heuristics) -> None:
        """click ステップの名前が click-{target} 形式であること。"""
        step = {"click": {"by": {"role": "button", "name": "Submit"}}}
        name = heuristics.auto_name(step)
        assert name == "click-submit"

    def test_fill_name(self, heuristics: Heuristics) -> None:
        """fill ステップの名前が fill-{target} 形式であること。"""
        step = {"fill": {"by": {"label": "Email"}, "value": "test@example.com"}}
        name = heuristics.auto_name(step)
        assert name == "fill-email"

    def test_press_name(self, heuristics: Heuristics) -> None:
        """press ステップの名前が press-{key} 形式であること。"""
        step = {"press": {"by": {"role": "textbox"}, "key": "Enter"}}
        name = heuristics.auto_name(step)
        assert name == "press-enter"

    def test_check_name(self, heuristics: Heuristics) -> None:
        """check ステップの名前が check-{target} 形式であること。"""
        step = {"check": {"by": {"role": "checkbox", "name": "Agree"}}}
        name = heuristics.auto_name(step)
        assert name == "check-agree"

    def test_uncheck_name(self, heuristics: Heuristics) -> None:
        """uncheck ステップの名前が uncheck-{target} 形式であること。"""
        step = {"uncheck": {"by": {"role": "checkbox", "name": "Newsletter"}}}
        name = heuristics.auto_name(step)
        assert name == "uncheck-newsletter"

    def test_dblclick_name(self, heuristics: Heuristics) -> None:
        """dblclick ステップの名前が dblclick-{target} 形式であること。"""
        step = {"dblclick": {"by": {"role": "cell", "name": "data"}}}
        name = heuristics.auto_name(step)
        assert name == "dblclick-data"

    def test_select_option_name(self, heuristics: Heuristics) -> None:
        """selectOption ステップの名前が select-{target} 形式であること。"""
        step = {"selectOption": {"by": {"role": "combobox"}, "value": "opt1"}}
        name = heuristics.auto_name(step)
        assert name == "select-combobox"

    def test_expect_visible_name(self, heuristics: Heuristics) -> None:
        """expectVisible ステップの名前が expect-visible-{target} 形式であること。"""
        step = {"expectVisible": {"by": {"role": "heading", "name": "Welcome"}}}
        name = heuristics.auto_name(step)
        assert name == "expect-visible-welcome"

    def test_expect_hidden_name(self, heuristics: Heuristics) -> None:
        """expectHidden ステップの名前が expect-hidden-{target} 形式であること。"""
        step = {"expectHidden": {"by": {"role": "dialog"}}}
        name = heuristics.auto_name(step)
        assert name == "expect-hidden-dialog"

    def test_expect_text_name(self, heuristics: Heuristics) -> None:
        """expectText ステップの名前が expect-text-{target} 形式であること。"""
        step = {"expectText": {"by": {"testId": "message"}, "text": "Hello"}}
        name = heuristics.auto_name(step)
        assert name == "expect-text-message"

    def test_expect_url_name(self, heuristics: Heuristics) -> None:
        """expectUrl ステップの名前が expect-url-{path} 形式であること。"""
        step = {"expectUrl": {"url": "https://example.com/dashboard"}}
        name = heuristics.auto_name(step)
        assert name == "expect-url-dashboard"


# ===========================================================================
# 2. auto_name: 名前の文字制限
# ===========================================================================

class TestAutoNameTruncation:
    """名前の文字制限テスト。"""

    def test_long_name_truncated(self, heuristics: Heuristics) -> None:
        """40文字を超える名前が切り詰められること。"""
        step = {"click": {"by": {"testId": "a" * 60}}}
        name = heuristics.auto_name(step)
        assert len(name) <= 40

    def test_truncated_name_no_trailing_hyphen(self, heuristics: Heuristics) -> None:
        """切り詰め後に末尾ハイフンが残らないこと。"""
        step = {"click": {"by": {"testId": "very-long-test-id-name-that-exceeds-limit"}}}
        name = heuristics.auto_name(step)
        assert not name.endswith("-")
        assert len(name) <= 40


# ===========================================================================
# 3. auto_name: 各セレクタ種別からの target 抽出
# ===========================================================================

class TestAutoNameSelectors:
    """各セレクタ種別からの target 抽出テスト。"""

    def test_role_with_name(self, heuristics: Heuristics) -> None:
        """role + name の場合、name が target になること。"""
        step = {"click": {"by": {"role": "button", "name": "Login"}}}
        name = heuristics.auto_name(step)
        assert name == "click-login"

    def test_role_without_name(self, heuristics: Heuristics) -> None:
        """role のみの場合、role 名が target になること。"""
        step = {"click": {"by": {"role": "textbox"}}}
        name = heuristics.auto_name(step)
        assert name == "click-textbox"

    def test_test_id_selector(self, heuristics: Heuristics) -> None:
        """testId セレクタの値が target になること。"""
        step = {"click": {"by": {"testId": "submit-btn"}}}
        name = heuristics.auto_name(step)
        assert name == "click-submit-btn"

    def test_label_selector(self, heuristics: Heuristics) -> None:
        """label セレクタの値が target になること。"""
        step = {"fill": {"by": {"label": "Username"}, "value": "user1"}}
        name = heuristics.auto_name(step)
        assert name == "fill-username"

    def test_placeholder_selector(self, heuristics: Heuristics) -> None:
        """placeholder セレクタの値が target になること。"""
        step = {"fill": {"by": {"placeholder": "Enter email"}, "value": "a@b.com"}}
        name = heuristics.auto_name(step)
        assert name == "fill-enter-email"

    def test_css_selector(self, heuristics: Heuristics) -> None:
        """css セレクタの値が target になること。"""
        step = {"click": {"by": {"css": "#main-btn"}}}
        name = heuristics.auto_name(step)
        assert name == "click-main-btn"

    def test_text_selector(self, heuristics: Heuristics) -> None:
        """text セレクタの値が target になること。"""
        step = {"click": {"by": {"text": "Click me"}}}
        name = heuristics.auto_name(step)
        assert name == "click-click-me"


# ===========================================================================
# 4. detect_secret: パスワード関連キーワードの検出
# ===========================================================================

class TestDetectSecret:
    """パスワード関連キーワードの検出テスト。"""

    def test_password_label(self, heuristics: Heuristics) -> None:
        """label に 'Password' を含む fill ステップで True。"""
        step = {"fill": {"by": {"label": "Password"}, "value": "secret123"}}
        assert heuristics.detect_secret(step) is True

    def test_password_lowercase(self, heuristics: Heuristics) -> None:
        """label に 'password' を含む fill ステップで True。"""
        step = {"fill": {"by": {"label": "password"}, "value": "secret123"}}
        assert heuristics.detect_secret(step) is True

    def test_secret_keyword(self, heuristics: Heuristics) -> None:
        """label に 'secret' を含む fill ステップで True。"""
        step = {"fill": {"by": {"label": "Client Secret"}, "value": "abc"}}
        assert heuristics.detect_secret(step) is True

    def test_token_keyword(self, heuristics: Heuristics) -> None:
        """label に 'Token' を含む fill ステップで True。"""
        step = {"fill": {"by": {"label": "API Token"}, "value": "tok123"}}
        assert heuristics.detect_secret(step) is True

    def test_credential_keyword(self, heuristics: Heuristics) -> None:
        """label に 'Credential' を含む fill ステップで True。"""
        step = {"fill": {"by": {"label": "Credential"}, "value": "cred"}}
        assert heuristics.detect_secret(step) is True

    def test_api_key_keyword(self, heuristics: Heuristics) -> None:
        """placeholder に 'api_key' を含む fill ステップで True。"""
        step = {"fill": {"by": {"placeholder": "Enter api_key"}, "value": "key"}}
        assert heuristics.detect_secret(step) is True

    def test_api_key_camel_case(self, heuristics: Heuristics) -> None:
        """testId に 'apiKey' を含む fill ステップで True。"""
        step = {"fill": {"by": {"testId": "apiKey-input"}, "value": "key"}}
        assert heuristics.detect_secret(step) is True

    def test_japanese_password(self, heuristics: Heuristics) -> None:
        """label に 'パスワード' を含む fill ステップで True。"""
        step = {"fill": {"by": {"label": "パスワード"}, "value": "pass"}}
        assert heuristics.detect_secret(step) is True

    def test_japanese_token(self, heuristics: Heuristics) -> None:
        """label に 'トークン' を含む fill ステップで True。"""
        step = {"fill": {"by": {"label": "アクセストークン"}, "value": "tok"}}
        assert heuristics.detect_secret(step) is True

    def test_non_secret_field(self, heuristics: Heuristics) -> None:
        """パスワード関連でない fill ステップで False。"""
        step = {"fill": {"by": {"label": "Email"}, "value": "test@example.com"}}
        assert heuristics.detect_secret(step) is False

    def test_click_step_not_secret(self, heuristics: Heuristics) -> None:
        """fill 以外のステップ（click）では False。"""
        step = {"click": {"by": {"role": "button", "name": "Password Reset"}}}
        assert heuristics.detect_secret(step) is False

    def test_goto_step_not_secret(self, heuristics: Heuristics) -> None:
        """fill 以外のステップ（goto）では False。"""
        step = {"goto": {"url": "https://example.com/password-reset"}}
        assert heuristics.detect_secret(step) is False

    def test_secret_in_name_field(self, heuristics: Heuristics) -> None:
        """name フィールドに secret キーワードがある場合も検出。"""
        step = {"fill": {"by": {"css": "#field"}, "value": "x", "name": "fill-password"}}
        assert heuristics.detect_secret(step) is True

    def test_already_secret_true(self, heuristics: Heuristics) -> None:
        """secret: true が既にある場合でも detect_secret 自体は True を返す。"""
        step = {"fill": {"by": {"label": "Password"}, "value": "x", "secret": True}}
        # detect_secret はフィールド内容を見るので True
        assert heuristics.detect_secret(step) is True


# ===========================================================================
# 5. auto_section: goto によるセクション分割
# ===========================================================================

class TestAutoSection:
    """auto_section のテスト。"""

    def test_section_split_by_goto(self, heuristics: Heuristics) -> None:
        """異なる URL の goto でセクションが分割されること。"""
        steps = [
            {"goto": {"url": "https://example.com/login"}},
            {"fill": {"by": {"label": "Email"}, "value": "a@b.com"}},
            {"fill": {"by": {"label": "Password"}, "value": "pass"}},
            {"click": {"by": {"role": "button", "name": "Login"}}},
            {"goto": {"url": "https://example.com/dashboard"}},
            {"click": {"by": {"role": "button", "name": "Settings"}}},
        ]
        result = heuristics.auto_section(steps)

        # 2つのセクションに分割される
        assert len(result) == 2
        assert result[0]["section"]["name"] == "ログインページ"
        assert len(result[0]["section"]["steps"]) == 4
        assert result[1]["section"]["name"] == "ダッシュボード"
        assert len(result[1]["section"]["steps"]) == 2

    def test_no_section_for_few_steps(self, heuristics: Heuristics) -> None:
        """ステップ数が5個以下の場合はセクション化しないこと。"""
        steps = [
            {"goto": {"url": "https://example.com/login"}},
            {"fill": {"by": {"label": "Email"}, "value": "a@b.com"}},
            {"goto": {"url": "https://example.com/dashboard"}},
        ]
        result = heuristics.auto_section(steps)

        # セクション化されない（元のリストがそのまま返る）
        assert len(result) == 3
        assert "section" not in result[0]

    def test_single_goto_no_section(self, heuristics: Heuristics) -> None:
        """goto が1つだけの場合はセクション化しないこと。"""
        steps = [
            {"goto": {"url": "https://example.com/login"}},
            {"fill": {"by": {"label": "Email"}, "value": "a@b.com"}},
            {"fill": {"by": {"label": "Password"}, "value": "pass"}},
            {"click": {"by": {"role": "button", "name": "Login"}}},
            {"expectUrl": {"url": "https://example.com/dashboard"}},
            {"expectVisible": {"by": {"role": "heading", "name": "Welcome"}}},
        ]
        result = heuristics.auto_section(steps)

        # goto が1つだけなのでセクション化されない
        assert len(result) == 6
        assert "section" not in result[0]

    def test_unknown_path_section_name(self, heuristics: Heuristics) -> None:
        """未知のパスの場合、パス文字列がセクション名になること。"""
        steps = [
            {"goto": {"url": "https://example.com/custom-page"}},
            {"click": {"by": {"role": "button", "name": "A"}}},
            {"click": {"by": {"role": "button", "name": "B"}}},
            {"goto": {"url": "https://example.com/another-page"}},
            {"click": {"by": {"role": "button", "name": "C"}}},
            {"click": {"by": {"role": "button", "name": "D"}}},
        ]
        result = heuristics.auto_section(steps)

        assert len(result) == 2
        assert result[0]["section"]["name"] == "custom-page"
        assert result[1]["section"]["name"] == "another-page"


# ===========================================================================
# 6. insert_expects: expectVisible 補助挿入
# ===========================================================================

class TestInsertExpects:
    """insert_expects のテスト。"""

    def test_expect_after_button_click(
        self, heuristics_with_expects: Heuristics
    ) -> None:
        """ボタンクリック後に expectVisible が挿入されること。"""
        steps = [
            {"click": {"by": {"role": "button", "name": "Submit"}}},
        ]
        result = heuristics_with_expects.insert_expects(steps)

        assert len(result) == 2
        assert "expectVisible" in result[1]

    def test_no_expect_after_non_button_click(
        self, heuristics_with_expects: Heuristics
    ) -> None:
        """ボタン以外のクリック後には expectVisible が挿入されないこと。"""
        steps = [
            {"click": {"by": {"role": "link", "name": "Home"}}},
        ]
        result = heuristics_with_expects.insert_expects(steps)

        # link クリックでは挿入されない
        assert len(result) == 1

    def test_expect_after_press_enter(
        self, heuristics_with_expects: Heuristics
    ) -> None:
        """press("Enter") 後に expectVisible が挿入されること。"""
        steps = [
            {"press": {"by": {"role": "textbox"}, "key": "Enter"}},
        ]
        result = heuristics_with_expects.insert_expects(steps)

        assert len(result) == 2
        assert "expectVisible" in result[1]

    def test_no_expect_after_press_tab(
        self, heuristics_with_expects: Heuristics
    ) -> None:
        """press("Tab") 後には expectVisible が挿入されないこと。"""
        steps = [
            {"press": {"by": {"role": "textbox"}, "key": "Tab"}},
        ]
        result = heuristics_with_expects.insert_expects(steps)

        assert len(result) == 1

    def test_no_duplicate_expect(
        self, heuristics_with_expects: Heuristics
    ) -> None:
        """既に expect 系ステップが直後にある場合は挿入しないこと。"""
        steps = [
            {"click": {"by": {"role": "button", "name": "Submit"}}},
            {"expectVisible": {"by": {"role": "heading", "name": "Success"}}},
        ]
        result = heuristics_with_expects.insert_expects(steps)

        # 既に expect があるので追加されない
        assert len(result) == 2

    def test_no_insert_when_disabled(self, heuristics: Heuristics) -> None:
        """with_expects=False の場合は挿入しないこと。"""
        steps = [
            {"click": {"by": {"role": "button", "name": "Submit"}}},
        ]
        # apply 経由で確認（insert_expects は呼ばれない）
        result = heuristics.apply(steps)

        # expectVisible が挿入されていないこと
        expect_count = sum(1 for s in result if "expectVisible" in s)
        assert expect_count == 0

    def test_empty_steps(self, heuristics_with_expects: Heuristics) -> None:
        """空リストに対して空リストが返ること。"""
        result = heuristics_with_expects.insert_expects([])
        assert result == []


# ===========================================================================
# 7. apply: 全ヒューリスティックの統合テスト
# ===========================================================================

class TestApplyIntegration:
    """apply メソッドの統合テスト。"""

    def test_full_login_flow(self, heuristics: Heuristics) -> None:
        """ログインフロー全体にヒューリスティックが正しく適用されること。"""
        steps = [
            {"goto": {"url": "https://example.com/login"}},
            {"fill": {"by": {"label": "Email"}, "value": "test@example.com"}},
            {"fill": {"by": {"label": "Password"}, "value": "secret123"}},
            {"click": {"by": {"role": "button", "name": "ログイン"}}},
            {"goto": {"url": "https://example.com/dashboard"}},
            {"expectVisible": {"by": {"role": "heading", "name": "Welcome"}}},
        ]
        result = heuristics.apply(steps)

        # セクション化される（6ステップ > 5）
        assert len(result) == 2
        assert "section" in result[0]
        assert "section" in result[1]

        # ログインセクション
        login_section = result[0]["section"]
        assert login_section["name"] == "ログインページ"
        login_steps = login_section["steps"]

        # name が自動付与されていること
        assert login_steps[0]["goto"].get("name") == "navigate-to-login"
        assert login_steps[1]["fill"].get("name") == "fill-email"
        assert login_steps[2]["fill"].get("name") is not None

        # Password フィールドに secret: true が付与されていること
        assert login_steps[2]["fill"].get("secret") is True

        # Email フィールドには secret がないこと
        assert login_steps[1]["fill"].get("secret") is not True

    def test_apply_with_expects(self, heuristics_with_expects: Heuristics) -> None:
        """with_expects=True で expectVisible が挿入されること。"""
        steps = [
            {"click": {"by": {"role": "button", "name": "Save"}}},
        ]
        result = heuristics_with_expects.apply(steps)

        # ステップ数が少ないのでセクション化はされない
        # click + expectVisible = 2ステップ
        assert len(result) == 2
        assert "expectVisible" in result[1]

    def test_apply_preserves_existing_name(self, heuristics: Heuristics) -> None:
        """既に name がある場合は上書きしないこと。"""
        steps = [
            {"click": {"by": {"role": "button", "name": "Submit"}, "name": "my-custom-name"}},
        ]
        result = heuristics.apply(steps)

        assert result[0]["click"]["name"] == "my-custom-name"

    def test_apply_empty_steps(self, heuristics: Heuristics) -> None:
        """空リストに対して空リストが返ること。"""
        result = heuristics.apply([])
        assert result == []

    def test_apply_secret_not_overwritten(self, heuristics: Heuristics) -> None:
        """既に secret: true がある場合は重複付与しないこと。"""
        steps = [
            {"fill": {"by": {"label": "Password"}, "value": "x", "secret": True}},
        ]
        result = heuristics.apply(steps)

        # secret は True のまま
        fill_step = result[0] if "fill" in result[0] else result[0]
        if "section" in fill_step:
            fill_step = fill_step["section"]["steps"][0]
        assert fill_step["fill"]["secret"] is True
