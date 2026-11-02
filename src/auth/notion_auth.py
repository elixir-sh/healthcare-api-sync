"""Notion の OAuth 2.0 認証フローを処理するモジュール

内部インテグレーションを作れないワークスペース(オーナー以外のメンバー)でも書き込めるよう、
公開コネクト(OAuth)でユーザー本人として認証する。
https://developers.notion.com/docs/authorization
"""

import json
import secrets
import webbrowser
from datetime import UTC, datetime
from urllib.parse import urlencode, urlparse

import requests

from src.auth.callback_server import wait_for_callback
from src.config import get_token_path, load_config

_AUTH_URL = "https://api.notion.com/v1/oauth/authorize"
_TOKEN_URL = "https://api.notion.com/v1/oauth/token"
_TOKEN_NAME = "notion"
NOTION_VERSION = "2025-09-03"
_DEFAULT_REDIRECT_URI = "http://localhost:8080/callback"

# トークン応答のうち保存する項目。owner(認証したユーザーの情報)は使わないので保存しない
_SAVED_FIELDS = ("access_token", "refresh_token", "bot_id", "workspace_id", "workspace_name")


def _error_code(resp: requests.Response) -> str | None:
    try:
        return resp.json().get("error")
    except ValueError:
        return None


def _post_token(config: dict, body: dict) -> dict:
    resp = requests.post(
        _TOKEN_URL,
        auth=(config["client_id"], config["client_secret"]),
        headers={"Notion-Version": NOTION_VERSION},
        json=body,
        timeout=30,
    )
    if resp.status_code == 400 and _error_code(resp) == "invalid_grant":
        raise RuntimeError(
            "Notion のトークンが失効しています。`python main.py auth notion` で再認証してください。"
        )
    if not resp.ok:
        raise RuntimeError(f"Notion 認証エラー ({resp.status_code}): {resp.text}")
    data = resp.json()
    token = {k: data.get(k) for k in _SAVED_FIELDS}
    token["obtained_at"] = datetime.now(UTC).isoformat()
    return token


def _save_token(token: dict) -> None:
    path = get_token_path(_TOKEN_NAME)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(token, f, ensure_ascii=False, indent=2)


def _load_token() -> dict | None:
    path = get_token_path(_TOKEN_NAME)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def authenticate() -> None:
    """ブラウザを開いて Notion の OAuth フローを実行し、トークンを保存する"""
    cfg = load_config()["notion"]
    # 既存の config.yaml に notion を書き足した場合に備えて、雛形と同じ値を既定にする
    redirect_uri = cfg.get("redirect_uri") or _DEFAULT_REDIRECT_URI
    redirect = urlparse(redirect_uri)
    state = secrets.token_urlsafe(16)

    params = {
        "client_id": cfg["client_id"],
        "response_type": "code",
        "owner": "user",
        "redirect_uri": redirect_uri,
        "state": state,
    }
    url = f"{_AUTH_URL}?{urlencode(params)}"
    print(
        "ブラウザで Notion 認証ページを開きます。ページの選択では書き込み先のデータベースを選んでください。"
    )
    print(f"開かない場合は次の URL をブラウザで開いてください:\n{url}")
    webbrowser.open(url)

    code = wait_for_callback(
        "Notion", redirect.hostname or "localhost", redirect.port or 8080, state
    )
    token = _post_token(
        cfg,
        {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri},
    )
    _save_token(token)
    print(f"Notion 認証完了({token['workspace_name']})。トークンを保存しました。")


def get_access_token() -> str:
    """保存済みのアクセストークンを返す"""
    token = _load_token()
    if token is None:
        raise RuntimeError(
            "Notion 認証が必要です。`python main.py auth notion` を実行してください。"
        )
    return token["access_token"]


def refresh_access_token() -> str:
    """リフレッシュトークンで新しいアクセストークンを取得し、保存して返す

    Notion はアクセストークンの有効期限を示さないため、API が 401 を返したときだけ呼ぶ。
    更新のたびにリフレッシュトークンも新しくなるので、呼ぶ回数を抑え、応答は必ず保存する。
    """
    token = _load_token()
    if token is None or not token.get("refresh_token"):
        raise RuntimeError(
            "Notion のトークンを更新できません。`python main.py auth notion` で再認証してください。"
        )
    cfg = load_config()["notion"]
    new_token = _post_token(
        cfg, {"grant_type": "refresh_token", "refresh_token": token["refresh_token"]}
    )
    # リフレッシュトークンが返らない場合に備えて、既存の値を引き継ぐ
    if not new_token.get("refresh_token"):
        new_token["refresh_token"] = token["refresh_token"]
    _save_token(new_token)
    return new_token["access_token"]
