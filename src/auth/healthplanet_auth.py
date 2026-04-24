"""HealthPlanet OAuth 2.0 認証フローを処理するモジュール

HealthPlanet の OAuth は外部コールバックURLを受け付けないため、
redirect_uri に HealthPlanet 自身のページを使い、
認証後のリダイレクト先URLをユーザーに手動でペーストしてもらう方式を採用する。
"""

import json
import webbrowser
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlencode, urlparse

import requests

from src.config import get_token_path, load_config

_AUTH_URL = "https://www.healthplanet.jp/oauth/auth"
_TOKEN_URL = "https://www.healthplanet.jp/oauth/token"
_SCOPES = "innerscan"


def _exchange_code_for_token(code: str, config: dict) -> dict:
    resp = requests.post(
        _TOKEN_URL,
        data={
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "redirect_uri": config["redirect_uri"],
            "code": code,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    resp.raise_for_status()
    token = resp.json()
    token["obtained_at"] = datetime.now(timezone.utc).isoformat()
    return token


def _refresh_token(config: dict, token: dict) -> dict:
    resp = requests.post(
        _TOKEN_URL,
        data={
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "redirect_uri": config["redirect_uri"],
            "refresh_token": token["refresh_token"],
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    resp.raise_for_status()
    new_token = resp.json()
    new_token["obtained_at"] = datetime.now(timezone.utc).isoformat()
    return new_token


def _save_token(token: dict) -> None:
    path = get_token_path("healthplanet")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(token, f, ensure_ascii=False, indent=2)


def _load_token() -> dict | None:
    path = get_token_path("healthplanet")
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _is_expired(token: dict) -> bool:
    obtained_at = datetime.fromisoformat(token["obtained_at"])
    expires_in = token.get("expires_in", 3600)
    elapsed = (datetime.now(timezone.utc) - obtained_at).total_seconds()
    return elapsed >= (expires_in - 300)


def _extract_code_from_url(pasted_url: str) -> str:
    """ユーザーがペーストしたURLから認証コードを抽出する"""
    pasted_url = pasted_url.strip()
    params = parse_qs(urlparse(pasted_url).query)
    if "code" not in params:
        raise ValueError(f"URLにcodeが含まれていません: {pasted_url}")
    return params["code"][0]


def authenticate() -> None:
    """ブラウザを開いて HealthPlanet OAuthフローを実行し、トークンを保存する。

    HealthPlanet は外部コールバックURLを受け付けないため、
    認証後のリダイレクト先URLをユーザーにエディタでペーストしてもらう。
    """
    import click

    cfg = load_config()["healthplanet"]

    base = urlencode({
        "client_id": cfg["client_id"],
        "response_type": "code",
        "scope": _SCOPES,
    })
    url = f"{_AUTH_URL}?{base}&redirect_uri={cfg['redirect_uri']}"

    print("ブラウザで HealthPlanet 認証ページを開きます...")
    webbrowser.open(url)
    print()
    print("【手順】")
    print("  1. ブラウザでログイン・アプリ連携を許可してください")
    print(f"  2. リダイレクト後のURL（{cfg['redirect_uri']}?code=...）をコピーしてください")
    print("  3. Enterを押すとエディタが開くので、URLをペーストして保存・終了してください")
    print()
    input("準備ができたらEnterを押してください...")

    # エディタでURLをペーストしてもらう（編集しやすい）
    template = (
        "# リダイレクト後のURLをこのファイルにペーストして保存・終了してください\n"
        "# （# で始まる行は無視されます）\n"
        "\n"
    )
    result = click.edit(template)
    if not result:
        raise RuntimeError("URLが入力されませんでした。")

    # コメント行・空行を除いた最初の行をURLとして使用
    pasted = next(
        (line.strip() for line in result.splitlines()
         if line.strip() and not line.strip().startswith("#")),
        "",
    )
    if not pasted:
        raise RuntimeError("URLが入力されませんでした。")

    code = _extract_code_from_url(pasted)
    token = _exchange_code_for_token(code, cfg)
    _save_token(token)
    print("HealthPlanet 認証完了。トークンを保存しました。")


def get_access_token() -> str:
    """有効なアクセストークンを返す。期限切れの場合はリフレッシュする"""
    token = _load_token()
    if token is None:
        raise RuntimeError(
            "HealthPlanet 認証が必要です。`python main.py auth healthplanet` を実行してください。"
        )

    if _is_expired(token):
        cfg = load_config()["healthplanet"]
        token = _refresh_token(cfg, token)
        _save_token(token)

    return token["access_token"]
