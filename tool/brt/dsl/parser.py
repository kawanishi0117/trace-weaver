"""
DSL パーサー — YAML DSL の読み込み・書き出し・検証

ruamel.yaml を使用して YAML ファイルのコメントを保持しつつ、
Pydantic モデルとの相互変換を行う。

要件 3.7: YAML ファイルのスキーマ検証、違反箇所の報告
要件 3.8: パース-出力ラウンドトリップ特性（意味的等価性の保証）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from pydantic import ValidationError as PydanticValidationError
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from .schema import Scenario


# ---------------------------------------------------------------------------
# バリデーションエラー表現
# ---------------------------------------------------------------------------

@dataclass
class DslValidationError:
    """YAML DSL のスキーマ検証で検出されたエラー。

    Attributes:
        message: エラーメッセージ
        location: エラー箇所（フィールドパス等）
        line: YAML ファイル内の行番号（取得可能な場合）
    """

    message: str
    location: str = ""
    line: Optional[int] = None


# ---------------------------------------------------------------------------
# DslParser 本体
# ---------------------------------------------------------------------------

class DslParser:
    """YAML DSL の読み込み・書き出し・検証を担当するパーサー。

    ruamel.yaml を使用してコメント保持付きの YAML 読み書きを行い、
    Pydantic v2 の Scenario モデルとの相互変換を提供する。
    """

    def __init__(self) -> None:
        """ruamel.yaml インスタンスを初期化する。"""
        self._yaml = YAML()
        # ラウンドトリップモード（デフォルト）でコメントを保持
        self._yaml.preserve_quotes = True
        # 出力時のインデント設定
        self._yaml.default_flow_style = False

    # ----- load -----

    def load(self, path: Path) -> Scenario:
        """YAML ファイルを読み込み、Pydantic Scenario モデルに変換する。

        Args:
            path: 読み込む YAML ファイルのパス

        Returns:
            パース済みの Scenario オブジェクト

        Raises:
            FileNotFoundError: ファイルが存在しない場合
            ValueError: YAML 構文エラーまたはスキーマ検証エラーの場合
        """
        path = Path(path)

        # ファイル存在チェック
        if not path.exists():
            raise FileNotFoundError(f"YAML ファイルが見つかりません: {path}")

        # YAML 読み込み
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = self._yaml.load(f)
        except YAMLError as e:
            # 行番号付きエラーメッセージを生成
            line_info = ""
            if hasattr(e, "problem_mark") and e.problem_mark is not None:
                mark = e.problem_mark
                line_info = f" (行 {mark.line + 1}, 列 {mark.column + 1})"
            raise ValueError(
                f"YAML 構文エラー{line_info}: {e}"
            ) from e

        if data is None:
            raise ValueError("YAML ファイルが空です")

        # ruamel.yaml の CommentedMap を通常の dict に変換
        plain_data = self._to_plain_dict(data)

        # Pydantic モデルに変換
        try:
            return Scenario(**plain_data)
        except PydanticValidationError as e:
            raise ValueError(
                f"スキーマ検証エラー: {e}"
            ) from e

    # ----- dump -----

    def dump(self, scenario: Scenario, path: Path) -> None:
        """Pydantic Scenario モデルを YAML ファイルに書き出す。

        model_dump() で辞書に変換し、ruamel.yaml で書き出す。
        コメント保持のため ruamel.yaml のラウンドトリップモードを使用する。

        Args:
            scenario: 書き出す Scenario オブジェクト
            path: 出力先の YAML ファイルパス
        """
        path = Path(path)

        # 親ディレクトリが存在しない場合は作成
        path.parent.mkdir(parents=True, exist_ok=True)

        # Pydantic モデルを辞書に変換
        data = scenario.model_dump(mode="python")

        # YAML ファイルに書き出し
        with open(path, "w", encoding="utf-8") as f:
            self._yaml.dump(data, f)

    # ----- validate -----

    def validate(self, path: Path) -> list[DslValidationError]:
        """YAML ファイルのスキーマ検証を行い、違反箇所を報告する。

        load() を試行し、発生したエラーを DslValidationError のリストとして返す。
        エラーがない場合は空リストを返す。

        Args:
            path: 検証する YAML ファイルのパス

        Returns:
            検出されたバリデーションエラーのリスト
        """
        path = Path(path)
        errors: list[DslValidationError] = []

        # ファイル存在チェック
        if not path.exists():
            errors.append(DslValidationError(
                message=f"YAML ファイルが見つかりません: {path}",
                location="file",
            ))
            return errors

        # YAML 構文チェック
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = self._yaml.load(f)
        except YAMLError as e:
            line = None
            if hasattr(e, "problem_mark") and e.problem_mark is not None:
                line = e.problem_mark.line + 1
            errors.append(DslValidationError(
                message=f"YAML 構文エラー: {e}",
                location="yaml",
                line=line,
            ))
            return errors

        if data is None:
            errors.append(DslValidationError(
                message="YAML ファイルが空です",
                location="file",
            ))
            return errors

        # Pydantic スキーマ検証
        plain_data = self._to_plain_dict(data)
        try:
            Scenario(**plain_data)
        except PydanticValidationError as e:
            for err in e.errors():
                # フィールドパスを文字列に変換
                loc_parts = [str(part) for part in err.get("loc", [])]
                location = " -> ".join(loc_parts) if loc_parts else "unknown"
                errors.append(DslValidationError(
                    message=err.get("msg", "不明なエラー"),
                    location=location,
                ))

        return errors

    # ----- ユーティリティ -----

    def _to_plain_dict(self, data: object) -> object:
        """ruamel.yaml の CommentedMap/CommentedSeq を通常の dict/list に再帰変換する。

        ruamel.yaml はラウンドトリップモードで CommentedMap や CommentedSeq を返すが、
        Pydantic モデルへの変換時には通常の dict/list が必要となる場合がある。

        Args:
            data: 変換対象のデータ

        Returns:
            通常の dict/list に変換されたデータ
        """
        if isinstance(data, dict):
            return {key: self._to_plain_dict(value) for key, value in data.items()}
        if isinstance(data, list):
            return [self._to_plain_dict(item) for item in data]
        return data
