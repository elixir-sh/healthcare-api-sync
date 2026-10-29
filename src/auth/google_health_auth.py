"""Google Health API 用の Google OAuth 2.0 + PKCE 認証フローを処理するモジュール"""

import base64
import hashlib
import json
import secrets
import time
import webbrowser
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import requests

from src.config import get_token_path, load_config

_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
# 体重・体脂肪率の書き込みに必要な最小スコープ
_SCOPES = "https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.writeonly"
_TOKEN_NAME = "google_health"


def _generate_pkce_pair() -> tuple[str, str]:
    """code_verifier と code_challenge のペアを生成する"""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


class _CallbackHandler(BaseHTTPRequestHandler):
    """OAuth コールバックを受け取るHTTPハンドラ"""

    auth_code: str | None = None
    state: str | None = None
    error: str | None = None

    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        if "code" in params:
            _CallbackHandler.auth_code = params["code"][0]
            _CallbackHandler.state = params.get("state", [None])[0]
            body = "認証成功。このタブを閉じてください。".encode()
        else:
            _CallbackHandler.error = params.get("error", ["unknown"])[0]
            body = "認証エラー。".encode()
        body = b"<html><body><p>" + body + b"</p></body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # 標準ログを抑制


def _wait_for_callback(host: str, port: int, expected_state: str, timeout: int = 180) -> str:
    """ローカルHTTPサーバーでコールバックを待ち受け、認可コードを返す"""
    _CallbackHandler.auth_code = None
    _CallbackHandler.state = None
    _CallbackHandler.error = None
    server = HTTPServer((host, port), _CallbackHandler)
    server.timeout = 1

    try:
        deadline = time.time() + timeout
        while time.time() < deadline:
            server.handle_request()
            if _CallbackHandler.auth_code:
                if _CallbackHandler.state != expected_state:
                    raise RuntimeError("Google 認証エラー: state が一致しません")
                return _CallbackHandler.auth_code
            if _CallbackHandler.error:
                raise RuntimeError(f"Google 認証エラー: {_CallbackHandler.error}")
    finally:
        server.server_close()

    raise TimeoutError("Google 認証がタイムアウトしました")


def _exchange_code_for_token(code: str, verifier: str, config: dict) -> dict:
    """認可コードをアクセストークンに交換する"""
    resp = requests.post(
        _TOKEN_URL,
        data={
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "grant_type": "authorization_code",
            "redirect_uri": config["redirect_uri"],
            "code": code,
            "code_verifier": verifier,
        },
        timeout=30,
    )
    resp.raise_for_status()
    token = resp.json()
    if "refresh_token" not in token:
        raise RuntimeError(
            "リフレッシュトークンが発行されませんでした。"
            "https://myaccount.google.com/connections でアプリのアクセス権を削除してから再認証してください。"
        )
    token["obtained_at"] = datetime.now(UTC).isoformat()
    return token


def _refresh_token(config: dict, token: dict) -> dict:
    """リフレッシュトークンで新しいアクセストークンを取得する"""
    resp = requests.post(
        _TOKEN_URL,
        data={
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "grant_type": "refresh_token",
            "refresh_token": token["refresh_token"],
        },
        timeout=30,
    )
    if resp.status_code == 400 and resp.json().get("error") == "invalid_grant":
        raise RuntimeError(
            "Google のリフレッシュトークンが失効しています。"
            "`python main.py auth google-health` で再認証してください。"
            "(OAuth 同意画面が Testing のままだと7日で失効します)"
        )
    resp.raise_for_status()
    new_token = resp.json()
    # Google はリフレッシュ時に通常 refresh_token を返さないため、既存の値を引き継ぐ
    new_token.setdefault("refresh_token", token["refresh_token"])
    new_token["obtained_at"] = datetime.now(UTC).isoformat()
    return new_token


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


def _is_expired(token: dict) -> bool:
    obtained_at = datetime.fromisoformat(token["obtained_at"])
    expires_in = token.get("expires_in", 3600)
    elapsed = (datetime.now(UTC) - obtained_at).total_seconds()
    # 5分の余裕を持って判定
    return elapsed >= (expires_in - 300)


def authenticate() -> None:
    """ブラウザを開いて Google OAuth フローを実行し、トークンを保存する"""
    cfg = load_config()["google_health"]
    redirect = urlparse(cfg["redirect_uri"])
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
        # リフレッシュトークンを確実に受け取るため、オフラインアクセスと再同意を要求する
        "access_type": "offline",
        "prompt": "consent",
    }
    url = f"{_AUTH_URL}?{urlencode(params)}"
    print("ブラウザで Google 認証ページを開きます...")
    print(f"開かない場合は次の URL をブラウザで開いてください:\n{url}")
    webbrowser.open(url)

    code = _wait_for_callback(redirect.hostname or "localhost", redirect.port or 8080, state)
    token = _exchange_code_for_token(code, verifier, cfg)
    _save_token(token)
    print("Google Health 認証完了。トークンを保存しました。")


def get_access_token() -> str:
    """有効なアクセストークンを返す。期限切れの場合はリフレッシュする"""
    token = _load_token()
    if token is None:
        raise RuntimeError(
            "Google Health 認証が必要です。`python main.py auth google-health` を実行してください。"
        )

    if _is_expired(token):
        cfg = load_config()["google_health"]
        token = _refresh_token(cfg, token)
        _save_token(token)

    return token["access_token"]
