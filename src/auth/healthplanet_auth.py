"""HealthPlanet OAuth 2.0 認証フローを処理するモジュール"""

import json
import secrets
import time
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import requests

from src.config import get_token_path, load_config

_AUTH_URL = "https://www.healthplanet.jp/oauth/auth"
_TOKEN_URL = "https://www.healthplanet.jp/oauth/token"
_SCOPES = "innerscan"


class _CallbackHandler(BaseHTTPRequestHandler):
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
        pass


def _wait_for_callback(port: int, timeout: int = 120) -> str:
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
            raise RuntimeError(f"HealthPlanet 認証エラー: {_CallbackHandler.error}")

    server.server_close()
    raise TimeoutError("HealthPlanet 認証がタイムアウトしました")


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


def authenticate() -> None:
    """ブラウザを開いて HealthPlanet OAuthフローを実行し、トークンを保存する"""
    cfg = load_config()["healthplanet"]
    port = int(urlparse(cfg["redirect_uri"]).port or 8080)
    state = secrets.token_urlsafe(16)

    params = {
        "client_id": cfg["client_id"],
        "response_type": "code",
        "scope": _SCOPES,
        "redirect_uri": cfg["redirect_uri"],
        "state": state,
    }
    url = f"{_AUTH_URL}?{urlencode(params)}"
    print("ブラウザで HealthPlanet 認証ページを開きます...")
    webbrowser.open(url)

    code = _wait_for_callback(port)
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
