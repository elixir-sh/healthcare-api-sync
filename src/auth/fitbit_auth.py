"""Fitbit OAuth 2.0 + PKCE 認証フローを処理するモジュール"""

import base64
import hashlib
import json
import os
import secrets
import threading
import time
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import requests

from src.config import get_token_path, load_config

_AUTH_URL = "https://www.fitbit.com/oauth2/authorize"
_TOKEN_URL = "https://api.fitbit.com/oauth2/token"
_SCOPES = "activity weight"


def _generate_pkce_pair() -> tuple[str, str]:
    """code_verifier と code_challenge のペアを生成する"""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


class _CallbackHandler(BaseHTTPRequestHandler):
    """OAuth コールバックを受け取るHTTPハンドラ"""

    auth_code: str | None = None
    error: str | None = None

    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        if "code" in params:
            _CallbackHandler.auth_code = params["code"][0]
            body = "認証成功。このタブを閉じてください。".encode("utf-8")
            body = b"<html><body><p>" + body + b"</p></body></html>"
        else:
            _CallbackHandler.error = params.get("error", ["unknown"])[0]
            body = "認証エラー。".encode("utf-8")
            body = b"<html><body><p>" + body + b"</p></body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # 標準ログを抑制


def _wait_for_callback(port: int, timeout: int = 120) -> str:
    """ローカルHTTPサーバーでコールバックを待ち受け、認可コードを返す"""
    _CallbackHandler.auth_code = None
    _CallbackHandler.error = None
    server = HTTPServer(("localhost", port), _CallbackHandler)
    server.timeout = 1

    deadline = time.time() + timeout
    while time.time() < deadline:
        server.handle_request()
        if _CallbackHandler.auth_code:
            server.server_close()
            return _CallbackHandler.auth_code
        if _CallbackHandler.error:
            server.server_close()
            raise RuntimeError(f"Fitbit 認証エラー: {_CallbackHandler.error}")

    server.server_close()
    raise TimeoutError("Fitbit 認証がタイムアウトしました")


def _exchange_code_for_token(
    code: str, verifier: str, config: dict
) -> dict:
    """認可コードをアクセストークンに交換する"""
    port = int(urlparse(config["redirect_uri"]).port or 8080)
    resp = requests.post(
        _TOKEN_URL,
        data={
            "client_id": config["client_id"],
            "grant_type": "authorization_code",
            "redirect_uri": config["redirect_uri"],
            "code": code,
            "code_verifier": verifier,
        },
        auth=(config["client_id"], config["client_secret"]),
        timeout=30,
    )
    resp.raise_for_status()
    token = resp.json()
    token["obtained_at"] = datetime.now(timezone.utc).isoformat()
    return token


def _refresh_token(config: dict, token: dict) -> dict:
    """リフレッシュトークンで新しいアクセストークンを取得する"""
    resp = requests.post(
        _TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": token["refresh_token"],
        },
        auth=(config["client_id"], config["client_secret"]),
        timeout=30,
    )
    resp.raise_for_status()
    new_token = resp.json()
    new_token["obtained_at"] = datetime.now(timezone.utc).isoformat()
    return new_token


def _save_token(token: dict) -> None:
    path = get_token_path("fitbit")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(token, f, ensure_ascii=False, indent=2)


def _load_token() -> dict | None:
    path = get_token_path("fitbit")
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _is_expired(token: dict) -> bool:
    obtained_at = datetime.fromisoformat(token["obtained_at"])
    expires_in = token.get("expires_in", 3600)
    elapsed = (datetime.now(timezone.utc) - obtained_at).total_seconds()
    # 5分の余裕を持って判定
    return elapsed >= (expires_in - 300)


def authenticate() -> None:
    """ブラウザを開いてFitbit OAuthフローを実行し、トークンを保存する"""
    cfg = load_config()["fitbit"]
    port = int(urlparse(cfg["redirect_uri"]).port or 8080)
    verifier, challenge = _generate_pkce_pair()
    state = secrets.token_urlsafe(16)

    params = {
        "client_id": cfg["client_id"],
        "response_type": "code",
        "scope": _SCOPES,
        "redirect_uri": cfg["redirect_uri"],
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
    }
    url = f"{_AUTH_URL}?{urlencode(params)}"
    print(f"ブラウザで Fitbit 認証ページを開きます...")
    webbrowser.open(url)

    code = _wait_for_callback(port)
    token = _exchange_code_for_token(code, verifier, cfg)
    _save_token(token)
    print("Fitbit 認証完了。トークンを保存しました。")


def get_access_token() -> str:
    """有効なアクセストークンを返す。期限切れの場合はリフレッシュする"""
    token = _load_token()
    if token is None:
        raise RuntimeError("Fitbit 認証が必要です。`python main.py auth fitbit` を実行してください。")

    if _is_expired(token):
        cfg = load_config()["fitbit"]
        token = _refresh_token(cfg, token)
        _save_token(token)

    return token["access_token"]
