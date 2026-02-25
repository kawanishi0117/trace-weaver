"""
テスト共通フィクスチャ・Hypothesis ストラテジー定義

全テストモジュールで共有するフィクスチャとデータ生成器を提供する。
DSL スキーマモデル（Scenario, TestIdSelector 等）はまだ実装されていない可能性があるため、
ストラテジーはファクトリ関数として定義し、インポートを遅延させている。
"""

import os
import tempfile
from pathlib import Path

import pytest
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# pytest フィクスチャ
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    """一時ディレクトリを提供する pytest フィクスチャ。

    pytest 組み込みの tmp_path を利用し、テスト終了後に自動クリーンアップされる。
    """
    return tmp_path


@pytest.fixture
def sample_scenario_dict() -> dict:
    """サンプルの Scenario 辞書データ。

    YAML DSL の最小構成を辞書形式で返す。
    パーサーやスキーマ検証のテストで使用する。
    """
    return {
        "title": "ログインフローのテスト",
        "baseUrl": "http://localhost:4200",
        "vars": {
            "email": "test@example.com",
            "password": "secret123",
        },
        "artifacts": {
            "screenshots": {"mode": "before_each_step", "format": "jpeg", "quality": 70},
            "trace": {"mode": "on_failure"},
            "video": {"mode": "on_failure"},
        },
        "hooks": {},
        "steps": [
            {"goto": {"url": "${vars.baseUrl}/login", "name": "open-login"}},
            {
                "fill": {
                    "by": {"css": "#email"},
                    "value": "${vars.email}",
                    "name": "fill-email",
                }
            },
            {
                "fill": {
                    "by": {"css": "#password"},
                    "value": "${vars.password}",
                    "name": "fill-password",
                    "secret": True,
                }
            },
            {
                "click": {
                    "by": {"role": "button", "name": "ログイン"},
                    "name": "click-login",
                }
            },
            {
                "expectUrl": {
                    "url": "http://localhost:4200/dashboard",
                    "name": "verify-redirect",
                }
            },
        ],
        "healing": "off",
    }


@pytest.fixture
def sample_yaml_content() -> str:
    """サンプルの YAML DSL 文字列。

    YAML パーサーのテストや、ファイル読み書きのテストで使用する。
    最小構成のログインフローを表現している。
    """
    return """\
title: ログインフローのテスト
baseUrl: http://localhost:4200
vars:
  email: test@example.com
  password: secret123
artifacts:
  screenshots:
    mode: before_each_step
    format: jpeg
    quality: 70
  trace:
    mode: on_failure
  video:
    mode: on_failure
hooks: {}
steps:
  - goto:
      url: "${vars.baseUrl}/login"
      name: open-login
  - fill:
      by:
        css: "#email"
      value: "${vars.email}"
      name: fill-email
  - fill:
      by:
        css: "#password"
      value: "${vars.password}"
      name: fill-password
      secret: true
  - click:
      by:
        role: button
        name: ログイン
      name: click-login
  - expectUrl:
      url: http://localhost:4200/dashboard
      name: verify-redirect
healing: off
"""


# ---------------------------------------------------------------------------
# Hypothesis ストラテジー（ファクトリ関数）
#
# DSL スキーマモデル（Scenario, TestIdSelector 等）がまだ実装されていない
# 可能性があるため、ストラテジーはファクトリ関数として定義する。
# スキーマが実装された後にインポートが解決され、正しく動作する。
# ---------------------------------------------------------------------------

def _import_schema():
    """DSL スキーマモジュールを遅延インポートする。

    Returns:
        schema モジュール。インポートに失敗した場合は None を返す。
    """
    try:
        from brt.dsl import schema
        return schema
    except (ImportError, ModuleNotFoundError):
        return None


# --- セレクタ生成ストラテジー ---

def make_test_id_selector_strategy():
    """TestIdSelector を生成する Hypothesis ストラテジー。"""
    schema = _import_schema()
    if schema is None:
        pytest.skip("brt.dsl.schema が未実装のためスキップ")
    return st.builds(
        schema.TestIdSelector,
        testId=st.text(min_size=1, max_size=50),
    )


def make_role_selector_strategy():
    """RoleSelector を生成する Hypothesis ストラテジー。"""
    schema = _import_schema()
    if schema is None:
        pytest.skip("brt.dsl.schema が未実装のためスキップ")
    return st.builds(
        schema.RoleSelector,
        role=st.sampled_from(["button", "textbox", "link", "checkbox"]),
        name=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
    )


def make_css_selector_strategy():
    """CssSelector を生成する Hypothesis ストラテジー。"""
    schema = _import_schema()
    if schema is None:
        pytest.skip("brt.dsl.schema が未実装のためスキップ")
    return st.builds(
        schema.CssSelector,
        css=st.text(min_size=1, max_size=100),
        text=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
    )


def make_by_selector_strategy():
    """BySelector（TestId / Role / Css のいずれか）を生成する Hypothesis ストラテジー。"""
    return st.one_of(
        make_test_id_selector_strategy(),
        make_role_selector_strategy(),
        make_css_selector_strategy(),
    )


# --- ステップ名生成ストラテジー ---

def make_step_name_strategy():
    """動詞-目的語形式のステップ名を生成する Hypothesis ストラテジー。

    例: "click-button", "fill-email-field"
    """
    return st.from_regex(r"[a-z]+-[a-z]+(-[a-z]+)?", fullmatch=True)


# --- ステップ生成ストラテジー ---

def make_goto_step_strategy():
    """GotoStep 用の辞書を生成する Hypothesis ストラテジー。"""
    return st.fixed_dictionaries({
        "goto": st.fixed_dictionaries({
            "url": st.from_regex(r"https?://[a-z]+\.[a-z]+(/[a-z]*)?", fullmatch=True),
            "name": make_step_name_strategy(),
        }),
    })


def make_click_step_strategy():
    """ClickStep 用の辞書を生成する Hypothesis ストラテジー。"""
    schema = _import_schema()
    if schema is None:
        pytest.skip("brt.dsl.schema が未実装のためスキップ")

    # セレクタを辞書形式で生成
    by_dict = st.one_of(
        st.fixed_dictionaries({"testId": st.text(min_size=1, max_size=50)}),
        st.fixed_dictionaries({
            "role": st.sampled_from(["button", "textbox", "link", "checkbox"]),
            "name": st.text(min_size=1, max_size=50),
        }),
        st.fixed_dictionaries({"css": st.text(min_size=1, max_size=100)}),
    )
    return st.fixed_dictionaries({
        "click": st.fixed_dictionaries({
            "by": by_dict,
            "name": make_step_name_strategy(),
        }),
    })


def make_fill_step_strategy():
    """FillStep 用の辞書を生成する Hypothesis ストラテジー。"""
    by_dict = st.one_of(
        st.fixed_dictionaries({"css": st.text(min_size=1, max_size=100)}),
        st.fixed_dictionaries({"testId": st.text(min_size=1, max_size=50)}),
    )
    return st.fixed_dictionaries({
        "fill": st.fixed_dictionaries({
            "by": by_dict,
            "value": st.text(max_size=100),
            "name": make_step_name_strategy(),
        }),
    })


# --- Scenario 生成ストラテジー ---

def make_scenario_strategy():
    """Scenario を生成する Hypothesis ストラテジー。

    DSL スキーマの Scenario モデルが実装されている場合は Pydantic モデルを、
    未実装の場合は辞書形式で生成する。
    """
    schema = _import_schema()

    # ステップリスト（goto / click / fill のいずれか）
    steps = st.lists(
        st.one_of(make_goto_step_strategy(), make_click_step_strategy(), make_fill_step_strategy()),
        min_size=1,
        max_size=20,
    )

    if schema is not None and hasattr(schema, "Scenario"):
        # Pydantic モデルとして生成
        return st.builds(
            schema.Scenario,
            title=st.text(min_size=1, max_size=100),
            baseUrl=st.from_regex(r"https?://[a-z]+\.[a-z]+", fullmatch=True),
            vars=st.dictionaries(
                st.text(min_size=1, max_size=20),
                st.text(max_size=100),
            ),
            steps=steps,
        )

    # スキーマ未実装時は辞書形式で生成
    return st.fixed_dictionaries({
        "title": st.text(min_size=1, max_size=100),
        "baseUrl": st.from_regex(r"https?://[a-z]+\.[a-z]+", fullmatch=True),
        "vars": st.dictionaries(
            st.text(min_size=1, max_size=20),
            st.text(max_size=100),
        ),
        "steps": steps,
        "healing": st.just("off"),
    })


# --- ストラテジーを pytest フィクスチャとしても公開 ---

@pytest.fixture
def by_selector_st():
    """BySelector ストラテジーをフィクスチャとして提供する。"""
    return make_by_selector_strategy()


@pytest.fixture
def step_name_st():
    """ステップ名ストラテジーをフィクスチャとして提供する。"""
    return make_step_name_strategy()


@pytest.fixture
def scenario_st():
    """Scenario ストラテジーをフィクスチャとして提供する。"""
    return make_scenario_strategy()
