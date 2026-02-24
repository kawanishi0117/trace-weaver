"""
Heuristics — セクション生成・命名・secret 検出のヒューリスティック

Mapper が生成した DSL ステップリストに対して、以下の後処理を行う:
  - auto_name: 動詞-目的語形式のステップ名自動付与
  - detect_secret: パスワード関連フィールドの検出と secret: true 付与
  - insert_expects: 重要操作後の expectVisible 補助挿入
  - auto_section: URL パスに基づくセクション自動生成

要件 2.7: auto_name() — 動詞-目的語形式のステップ名自動付与
要件 2.8: auto_section() — URL パスやボタン文言に基づくセクション自動生成
要件 2.10: detect_secret() — パスワード関連フィールドの検出と secret: true 付与
要件 2.11: --with-expects オプション — 重要操作後の expectVisible 補助挿入
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ステップ種別 → 動詞プレフィックスのマッピング
# ---------------------------------------------------------------------------

_STEP_VERB_MAP: dict[str, str] = {
    "goto": "navigate-to",
    "click": "click",
    "fill": "fill",
    "press": "press",
    "check": "check",
    "uncheck": "uncheck",
    "dblclick": "dblclick",
    "selectOption": "select",
    "expectVisible": "expect-visible",
    "expectHidden": "expect-hidden",
    "expectText": "expect-text",
    "expectUrl": "expect-url",
}


# ---------------------------------------------------------------------------
# secret 検出キーワード
# ---------------------------------------------------------------------------

_SECRET_KEYWORDS: list[str] = [
    "password", "Password", "パスワード",
    "secret", "Secret",
    "token", "Token", "トークン",
    "credential", "Credential",
    "api_key", "apiKey", "API_KEY",
]

# 大文字小文字を無視した検索用パターン
_SECRET_PATTERN = re.compile(
    "|".join(re.escape(kw) for kw in _SECRET_KEYWORDS),
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# URL パス → セクション名の簡易マッピング
# ---------------------------------------------------------------------------

_PATH_SECTION_MAP: dict[str, str] = {
    "/login": "ログインページ",
    "/signin": "サインインページ",
    "/signup": "サインアップページ",
    "/register": "登録ページ",
    "/dashboard": "ダッシュボード",
    "/settings": "設定ページ",
    "/profile": "プロフィールページ",
    "/home": "ホームページ",
    "/search": "検索ページ",
    "/admin": "管理ページ",
    "/logout": "ログアウト",
    "/": "トップページ",
}

# ステップ名に使える文字（ASCII 英数字とハイフン）
_NAME_MAX_LENGTH = 40
_NAME_SANITIZE_PATTERN = re.compile(r"[^a-zA-Z0-9\-]")


# ---------------------------------------------------------------------------
# ヘルパー関数
# ---------------------------------------------------------------------------

def _get_step_type(step: dict) -> str | None:
    """ステップ dict からステップ種別名を取得する。

    section ステップの場合は None を返す。
    """
    for key in step:
        if key != "section":
            return key
    return None


def _get_step_body(step: dict) -> dict | None:
    """ステップ dict からボディ部分を取得する。"""
    step_type = _get_step_type(step)
    if step_type is None:
        return None
    return step.get(step_type)


def _extract_target_from_by(by: dict) -> str:
    """by セレクタ dict から target 文字列を抽出する。

    優先順位:
      - role: name があれば name、なければ role 名
      - testId, label, placeholder, text, css の値
    """
    if "role" in by:
        # name があればそちらを優先
        if "name" in by:
            return by["name"]
        return by["role"]

    # role 以外のセレクタ
    for key in ("testId", "label", "placeholder", "text", "css"):
        if key in by:
            return by[key]

    return "unknown"


def _sanitize_name(raw_name: str) -> str:
    """ステップ名を ASCII 英数字とハイフンのみに正規化する。

    - 非 ASCII 文字やスペースはハイフンに置換
    - 連続ハイフンは1つにまとめる
    - 先頭・末尾のハイフンを除去
    - 40文字で切り詰める
    """
    # スペースをハイフンに変換
    name = raw_name.replace(" ", "-")
    # 許可されない文字をハイフンに置換
    name = _NAME_SANITIZE_PATTERN.sub("-", name)
    # 連続ハイフンを1つにまとめる
    name = re.sub(r"-{2,}", "-", name)
    # 先頭・末尾のハイフンを除去
    name = name.strip("-")
    # 小文字に統一
    name = name.lower()
    # 長さ制限
    if len(name) > _NAME_MAX_LENGTH:
        name = name[:_NAME_MAX_LENGTH].rstrip("-")
    return name


def _path_to_section_name(url: str) -> str:
    """URL からセクション名を生成する。

    既知のパスはマッピングから取得し、
    未知のパスはパス文字列をそのままセクション名にする。
    """
    try:
        parsed = urlparse(url)
        path = parsed.path.rstrip("/") or "/"
    except Exception:
        return url

    # 既知パスのマッピングを確認
    if path in _PATH_SECTION_MAP:
        return _PATH_SECTION_MAP[path]

    # 未知パスはパス文字列をセクション名にする
    # 先頭の / を除去し、/ を空白に変換
    section_name = path.lstrip("/").replace("/", " ")
    return section_name if section_name else "トップページ"


def _extract_path_from_url(url: str) -> str:
    """URL からパス部分を抽出する。"""
    try:
        parsed = urlparse(url)
        return parsed.path.rstrip("/") or "/"
    except Exception:
        return url


# ---------------------------------------------------------------------------
# Heuristics 本体
# ---------------------------------------------------------------------------

class Heuristics:
    """セクション生成・命名・secret 検出のヒューリスティック。

    Mapper が生成した DSL ステップリストに対して後処理を行い、
    可読性と安全性を向上させる。
    """

    def __init__(self, with_expects: bool = False) -> None:
        """
        Args:
            with_expects: True の場合、重要操作後に expectVisible を補助挿入
        """
        self._with_expects = with_expects

    # -------------------------------------------------------------------
    # メインエントリポイント
    # -------------------------------------------------------------------

    def apply(self, steps: list[dict]) -> list[dict]:
        """全ヒューリスティックを適用する。

        適用順序:
          1. auto_name: 各ステップに name を自動付与
          2. detect_secret: パスワード関連フィールドに secret: true を付与
          3. insert_expects: (with_expects=True の場合) 重要操作後に expectVisible を挿入
          4. auto_section: URL パスに基づくセクション自動生成

        Args:
            steps: Mapper が生成した DSL ステップリスト

        Returns:
            ヒューリスティック適用後のステップリスト
        """
        # 1. ステップ名の自動付与
        for step in steps:
            step_type = _get_step_type(step)
            if step_type is None:
                continue
            body = step[step_type]
            if isinstance(body, dict) and "name" not in body:
                name = self.auto_name(step)
                if name:
                    body["name"] = name

        # 2. secret 検出
        for step in steps:
            step_type = _get_step_type(step)
            if step_type is None:
                continue
            body = step[step_type]
            if isinstance(body, dict) and not body.get("secret"):
                if self.detect_secret(step):
                    body["secret"] = True
                    logger.info("secret 検出: %s", body.get("name", step_type))

        # 3. expect 補助挿入
        if self._with_expects:
            steps = self.insert_expects(steps)

        # 4. セクション自動生成
        steps = self.auto_section(steps)

        return steps

    # -------------------------------------------------------------------
    # auto_name: 動詞-目的語形式のステップ名自動生成
    # -------------------------------------------------------------------

    def auto_name(self, step: dict) -> str:
        """動詞-目的語形式のステップ名を自動生成する。

        ルール:
          - goto: "navigate-to-{path}" (URL のパス部分)
          - click: "click-{target}" (セレクタの値)
          - fill: "fill-{target}" (セレクタの値)
          - press: "press-{key}"
          - check: "check-{target}"
          - uncheck: "uncheck-{target}"
          - dblclick: "dblclick-{target}"
          - selectOption: "select-{target}"
          - expectVisible: "expect-visible-{target}"
          - expectHidden: "expect-hidden-{target}"
          - expectText: "expect-text-{target}"
          - expectUrl: "expect-url-{path}"

        target は by セレクタから抽出:
          - role: name があれば name、なければ role 名
          - testId: testId の値
          - label: label の値
          - placeholder: placeholder の値
          - css: css の値（短縮）
          - text: text の値

        名前は ASCII 英数字とハイフンで構成し、40文字で切り詰める。

        Returns:
            動詞-目的語形式のステップ名
        """
        step_type = _get_step_type(step)
        if step_type is None:
            return ""

        verb = _STEP_VERB_MAP.get(step_type)
        if verb is None:
            return ""

        body = step[step_type]
        if not isinstance(body, dict):
            return ""

        # goto / expectUrl: URL パスから生成
        if step_type in ("goto", "expectUrl"):
            url = body.get("url", "")
            path = _extract_path_from_url(url)
            raw_name = f"{verb}-{path}"
            return _sanitize_name(raw_name)

        # press: キー名から生成
        if step_type == "press":
            key = body.get("key", "unknown")
            raw_name = f"{verb}-{key}"
            return _sanitize_name(raw_name)

        # by セレクタ付きステップ
        by = body.get("by")
        if by and isinstance(by, dict):
            target = _extract_target_from_by(by)
            raw_name = f"{verb}-{target}"
            return _sanitize_name(raw_name)

        return _sanitize_name(verb)

    # -------------------------------------------------------------------
    # detect_secret: パスワード関連フィールドの検出
    # -------------------------------------------------------------------

    def detect_secret(self, step: dict) -> bool:
        """パスワード関連フィールドかどうかを検出する。

        fill ステップのみを対象とし、以下のキーワードを含む場合に True:
          - "password", "Password", "パスワード"
          - "secret", "Secret"
          - "token", "Token", "トークン"
          - "credential", "Credential"
          - "api_key", "apiKey", "API_KEY"

        検出対象:
          - by セレクタの値（label, placeholder, name, testId, css）
          - ステップの name フィールド

        Returns:
            パスワード関連フィールドの場合 True
        """
        step_type = _get_step_type(step)
        if step_type != "fill":
            return False

        body = step.get("fill", {})
        if not isinstance(body, dict):
            return False

        # 検索対象テキストを収集
        texts_to_check: list[str] = []

        # name フィールド
        name = body.get("name")
        if name:
            texts_to_check.append(name)

        # by セレクタの値
        by = body.get("by")
        if by and isinstance(by, dict):
            for key in ("label", "placeholder", "name", "testId", "css"):
                val = by.get(key)
                if val:
                    texts_to_check.append(val)

        # キーワード検索
        for text in texts_to_check:
            if _SECRET_PATTERN.search(text):
                return True

        return False

    # -------------------------------------------------------------------
    # auto_section: URL パスに基づくセクション自動生成
    # -------------------------------------------------------------------

    def auto_section(self, steps: list[dict]) -> list[dict]:
        """URL パスに基づくセクション自動生成。

        goto ステップの URL パスが変わるたびに新しいセクションを開始する。
        セクション名は URL パスから生成（例: "/login" → "ログインページ"）。

        ただし、ステップ数が少ない場合（5個以下）はセクション化しない。

        Returns:
            セクション化されたステップリスト（section ステップを含む）
        """
        # ステップ数が少ない場合はセクション化しない
        if len(steps) <= 5:
            return steps

        # goto ステップの位置とパスを収集
        goto_indices: list[tuple[int, str]] = []
        for i, step in enumerate(steps):
            if "goto" in step:
                body = step["goto"]
                url = body.get("url", "")
                path = _extract_path_from_url(url)
                goto_indices.append((i, path))

        # goto が1つ以下ならセクション化不要
        if len(goto_indices) <= 1:
            return steps

        # 重複パスを除去（連続する同じパスはスキップ）
        unique_gotos: list[tuple[int, str]] = []
        prev_path = None
        for idx, path in goto_indices:
            if path != prev_path:
                unique_gotos.append((idx, path))
                prev_path = path

        # セクションが1つしかない場合はセクション化不要
        if len(unique_gotos) <= 1:
            return steps

        # セクション化
        result: list[dict] = []
        for section_idx, (start_idx, path) in enumerate(unique_gotos):
            # 次のセクションの開始位置を決定
            if section_idx + 1 < len(unique_gotos):
                end_idx = unique_gotos[section_idx + 1][0]
            else:
                end_idx = len(steps)

            section_name = _path_to_section_name(
                steps[start_idx]["goto"].get("url", "")
            )
            section_steps = steps[start_idx:end_idx]

            result.append({
                "section": {
                    "name": section_name,
                    "steps": section_steps,
                },
            })

        # goto より前のステップがある場合は先頭に追加
        if unique_gotos and unique_gotos[0][0] > 0:
            prefix_steps = steps[:unique_gotos[0][0]]
            result = prefix_steps + result

        return result

    # -------------------------------------------------------------------
    # insert_expects: 重要操作後の expectVisible 補助挿入
    # -------------------------------------------------------------------

    def insert_expects(self, steps: list[dict]) -> list[dict]:
        """重要操作後に expectVisible を補助挿入する。

        以下の操作の後に expectVisible を挿入:
          - click（ボタンクリック後）
          - fill + press("Enter")（フォーム送信後）

        ただし、既に expect 系ステップが直後にある場合は挿入しない。

        Returns:
            expect 補助挿入後のステップリスト
        """
        if not steps:
            return steps

        result: list[dict] = []
        i = 0
        while i < len(steps):
            step = steps[i]
            result.append(step)

            # 次のステップが expect 系かどうかを確認
            next_step = steps[i + 1] if i + 1 < len(steps) else None
            next_is_expect = False
            if next_step:
                next_type = _get_step_type(next_step)
                if next_type and next_type.startswith("expect"):
                    next_is_expect = True

            if not next_is_expect:
                expect_step = self._maybe_create_expect(step, steps, i)
                if expect_step:
                    result.append(expect_step)

            i += 1

        return result

    def _maybe_create_expect(
        self, step: dict, steps: list[dict], index: int
    ) -> dict | None:
        """ステップに対して expectVisible を生成すべきか判定し、生成する。

        Args:
            step: 現在のステップ
            steps: 全ステップリスト
            index: 現在のステップのインデックス

        Returns:
            expectVisible ステップ dict。挿入不要の場合は None。
        """
        step_type = _get_step_type(step)

        # click（ボタン）の後に expectVisible を挿入
        if step_type == "click":
            body = step["click"]
            by = body.get("by", {})
            # ボタンクリックの場合のみ
            if by.get("role") == "button":
                target = _extract_target_from_by(by)
                name = _sanitize_name(f"expect-visible-after-{target}")
                return {
                    "expectVisible": {
                        "by": by.copy(),
                        "name": name,
                    },
                }

        # press("Enter") の後に expectVisible を挿入
        # （直前が fill ステップの場合 = フォーム送信パターン）
        if step_type == "press":
            body = step["press"]
            if body.get("key") == "Enter":
                by = body.get("by", {})
                if by:
                    target = _extract_target_from_by(by)
                    name = _sanitize_name(f"expect-visible-after-{target}")
                    return {
                        "expectVisible": {
                            "by": by.copy(),
                            "name": name,
                        },
                    }

        return None
