"""
DslParser のユニットテスト

load / dump / validate メソッドの動作を検証する。
YAML ファイルの読み書き、Pydantic モデルとの相互変換、
エラーハンドリングをテストする。

要件 3.7: YAML ファイルのスキーマ検証、違反箇所の報告
要件 3.8: パース-出力ラウンドトリップ特性
"""

from pathlib import Path

import pytest

from brt.dsl.parser import DslParser, DslValidationError
from brt.dsl.schema import Scenario


# ---------------------------------------------------------------------------
# フィクスチャ
# ---------------------------------------------------------------------------

@pytest.fixture
def parser() -> DslParser:
    """DslParser インスタンスを提供する。"""
    return DslParser()


@pytest.fixture
def minimal_yaml_content() -> str:
    """最小構成の有効な YAML DSL 文字列。"""
    return """\
title: テストシナリオ
baseUrl: http://localhost:4200
steps:
  - goto:
      url: /login
      name: open-login
"""


@pytest.fixture
def full_yaml_content() -> str:
    """フル構成の有効な YAML DSL 文字列。"""
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
      url: /login
      name: open-login
  - fill:
      by:
        css: "#email"
      value: "${vars.email}"
      name: fill-email
  - click:
      by:
        role: button
        name: ログイン
      name: click-login
healing: off
"""


# ---------------------------------------------------------------------------
# load() テスト
# ---------------------------------------------------------------------------

class TestDslParserLoad:
    """load() メソッドのテスト。"""

    def test_load_minimal_yaml(
        self, parser: DslParser, tmp_path: Path, minimal_yaml_content: str
    ):
        """最小構成の YAML を正しく読み込めること。"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(minimal_yaml_content, encoding="utf-8")

        scenario = parser.load(yaml_file)

        assert isinstance(scenario, Scenario)
        assert scenario.title == "テストシナリオ"
        assert scenario.baseUrl == "http://localhost:4200"
        assert len(scenario.steps) == 1

    def test_load_full_yaml(
        self, parser: DslParser, tmp_path: Path, full_yaml_content: str
    ):
        """フル構成の YAML を正しく読み込めること。"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(full_yaml_content, encoding="utf-8")

        scenario = parser.load(yaml_file)

        assert scenario.title == "ログインフローのテスト"
        assert scenario.vars["email"] == "test@example.com"
        assert len(scenario.steps) == 3
        assert scenario.healing == "off"

    def test_load_file_not_found(self, parser: DslParser, tmp_path: Path):
        """存在しないファイルで FileNotFoundError が発生すること。"""
        with pytest.raises(FileNotFoundError, match="YAML ファイルが見つかりません"):
            parser.load(tmp_path / "nonexistent.yaml")

    def test_load_invalid_yaml_syntax(self, parser: DslParser, tmp_path: Path):
        """不正な YAML 構文で ValueError が発生すること。"""
        yaml_file = tmp_path / "bad.yaml"
        yaml_file.write_text("title: test\n  invalid: indentation\n", encoding="utf-8")

        with pytest.raises(ValueError, match="YAML 構文エラー"):
            parser.load(yaml_file)

    def test_load_empty_yaml(self, parser: DslParser, tmp_path: Path):
        """空の YAML ファイルで ValueError が発生すること。"""
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("", encoding="utf-8")

        with pytest.raises(ValueError, match="YAML ファイルが空です"):
            parser.load(yaml_file)

    def test_load_missing_required_field(self, parser: DslParser, tmp_path: Path):
        """必須フィールド欠落で ValueError が発生すること。"""
        yaml_file = tmp_path / "missing.yaml"
        # title が欠落
        yaml_file.write_text(
            "baseUrl: http://localhost\nsteps:\n  - goto:\n      url: /\n      name: go\n",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="スキーマ検証エラー"):
            parser.load(yaml_file)

    def test_load_accepts_path_as_string(self, parser: DslParser, tmp_path: Path, minimal_yaml_content: str):
        """文字列パスでも正しく読み込めること。"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(minimal_yaml_content, encoding="utf-8")

        # Path ではなく str を渡す
        scenario = parser.load(str(yaml_file))
        assert isinstance(scenario, Scenario)


# ---------------------------------------------------------------------------
# dump() テスト
# ---------------------------------------------------------------------------

class TestDslParserDump:
    """dump() メソッドのテスト。"""

    def test_dump_creates_yaml_file(self, parser: DslParser, tmp_path: Path):
        """Scenario を YAML ファイルに書き出せること。"""
        scenario = Scenario(
            title="テスト",
            baseUrl="http://localhost:4200",
            steps=[{"goto": {"url": "/", "name": "go-home"}}],
        )
        output_path = tmp_path / "output.yaml"

        parser.dump(scenario, output_path)

        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert "テスト" in content
        assert "http://localhost:4200" in content

    def test_dump_creates_parent_directories(self, parser: DslParser, tmp_path: Path):
        """親ディレクトリが存在しない場合に自動作成されること。"""
        scenario = Scenario(
            title="テスト",
            baseUrl="http://localhost",
            steps=[{"goto": {"url": "/", "name": "go"}}],
        )
        output_path = tmp_path / "sub" / "dir" / "output.yaml"

        parser.dump(scenario, output_path)

        assert output_path.exists()

    def test_dump_roundtrip(self, parser: DslParser, tmp_path: Path):
        """dump → load のラウンドトリップで意味的に等価であること。"""
        original = Scenario(
            title="ラウンドトリップテスト",
            baseUrl="http://localhost:4200",
            vars={"user": "admin"},
            steps=[
                {"goto": {"url": "/login", "name": "open-login"}},
                {"click": {"by": {"role": "button", "name": "送信"}, "name": "click-submit"}},
            ],
            healing="off",
        )
        yaml_file = tmp_path / "roundtrip.yaml"

        # dump → load
        parser.dump(original, yaml_file)
        loaded = parser.load(yaml_file)

        # 意味的等価性の検証
        assert loaded.title == original.title
        assert loaded.baseUrl == original.baseUrl
        assert loaded.vars == original.vars
        assert loaded.steps == original.steps
        assert loaded.healing == original.healing

    def test_dump_with_artifacts_config(self, parser: DslParser, tmp_path: Path):
        """artifacts 設定を含む Scenario のラウンドトリップ。"""
        from brt.dsl.schema import ArtifactsConfig, ScreenshotConfig

        scenario = Scenario(
            title="アーティファクトテスト",
            baseUrl="http://localhost",
            artifacts=ArtifactsConfig(
                screenshots=ScreenshotConfig(mode="before_and_after", format="png", quality=90),
            ),
            steps=[{"goto": {"url": "/", "name": "go"}}],
        )
        yaml_file = tmp_path / "artifacts.yaml"

        parser.dump(scenario, yaml_file)
        loaded = parser.load(yaml_file)

        assert loaded.artifacts.screenshots.mode == "before_and_after"
        assert loaded.artifacts.screenshots.format == "png"
        assert loaded.artifacts.screenshots.quality == 90

    def test_dump_accepts_path_as_string(self, parser: DslParser, tmp_path: Path):
        """文字列パスでも正しく書き出せること。"""
        scenario = Scenario(
            title="テスト",
            baseUrl="http://localhost",
            steps=[{"goto": {"url": "/", "name": "go"}}],
        )
        output_path = tmp_path / "output.yaml"

        parser.dump(scenario, str(output_path))
        assert output_path.exists()


# ---------------------------------------------------------------------------
# validate() テスト
# ---------------------------------------------------------------------------

class TestDslParserValidate:
    """validate() メソッドのテスト。"""

    def test_validate_valid_yaml(
        self, parser: DslParser, tmp_path: Path, minimal_yaml_content: str
    ):
        """有効な YAML でエラーが返らないこと。"""
        yaml_file = tmp_path / "valid.yaml"
        yaml_file.write_text(minimal_yaml_content, encoding="utf-8")

        errors = parser.validate(yaml_file)

        assert errors == []

    def test_validate_file_not_found(self, parser: DslParser, tmp_path: Path):
        """存在しないファイルでエラーが返ること。"""
        errors = parser.validate(tmp_path / "nonexistent.yaml")

        assert len(errors) == 1
        assert "見つかりません" in errors[0].message
        assert errors[0].location == "file"

    def test_validate_invalid_yaml_syntax(self, parser: DslParser, tmp_path: Path):
        """不正な YAML 構文でエラーが返ること。"""
        yaml_file = tmp_path / "bad.yaml"
        yaml_file.write_text("title: test\n  bad: indent\n", encoding="utf-8")

        errors = parser.validate(yaml_file)

        assert len(errors) == 1
        assert "YAML 構文エラー" in errors[0].message
        assert errors[0].location == "yaml"

    def test_validate_empty_yaml(self, parser: DslParser, tmp_path: Path):
        """空の YAML ファイルでエラーが返ること。"""
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("", encoding="utf-8")

        errors = parser.validate(yaml_file)

        assert len(errors) == 1
        assert "空です" in errors[0].message

    def test_validate_missing_title(self, parser: DslParser, tmp_path: Path):
        """title 欠落でスキーマ検証エラーが返ること。"""
        yaml_file = tmp_path / "no_title.yaml"
        yaml_file.write_text(
            "baseUrl: http://localhost\nsteps:\n  - goto:\n      url: /\n      name: go\n",
            encoding="utf-8",
        )

        errors = parser.validate(yaml_file)

        assert len(errors) >= 1
        # title フィールドに関するエラーが含まれること
        assert any("title" in e.location for e in errors)

    def test_validate_missing_base_url(self, parser: DslParser, tmp_path: Path):
        """baseUrl 欠落でスキーマ検証エラーが返ること。"""
        yaml_file = tmp_path / "no_base_url.yaml"
        yaml_file.write_text(
            "title: テスト\nsteps:\n  - goto:\n      url: /\n      name: go\n",
            encoding="utf-8",
        )

        errors = parser.validate(yaml_file)

        assert len(errors) >= 1
        assert any("baseUrl" in e.location for e in errors)

    def test_validate_missing_steps(self, parser: DslParser, tmp_path: Path):
        """steps 欠落でスキーマ検証エラーが返ること。"""
        yaml_file = tmp_path / "no_steps.yaml"
        yaml_file.write_text(
            "title: テスト\nbaseUrl: http://localhost\n",
            encoding="utf-8",
        )

        errors = parser.validate(yaml_file)

        assert len(errors) >= 1
        assert any("steps" in e.location for e in errors)

    def test_validate_invalid_healing_value(self, parser: DslParser, tmp_path: Path):
        """不正な healing 値でスキーマ検証エラーが返ること。"""
        yaml_file = tmp_path / "bad_healing.yaml"
        yaml_file.write_text(
            "title: テスト\nbaseUrl: http://localhost\nsteps:\n  - goto:\n      url: /\n      name: go\nhealing: aggressive\n",
            encoding="utf-8",
        )

        errors = parser.validate(yaml_file)

        assert len(errors) >= 1

    def test_validate_returns_multiple_errors(self, parser: DslParser, tmp_path: Path):
        """複数のフィールド欠落で複数エラーが返ること。"""
        yaml_file = tmp_path / "multi_error.yaml"
        # title, baseUrl, steps すべて欠落
        yaml_file.write_text("healing: off\n", encoding="utf-8")

        errors = parser.validate(yaml_file)

        # title, baseUrl, steps の3つのエラーが返ること
        assert len(errors) >= 3

    def test_validate_yaml_syntax_error_has_line_number(
        self, parser: DslParser, tmp_path: Path
    ):
        """YAML 構文エラーに行番号が含まれること。"""
        yaml_file = tmp_path / "syntax_error.yaml"
        yaml_file.write_text(
            "title: test\nsteps:\n  - goto:\n    url: /\n      bad: indent\n",
            encoding="utf-8",
        )

        errors = parser.validate(yaml_file)

        assert len(errors) == 1
        # 行番号が設定されていること（None でないこと）
        assert errors[0].line is not None
