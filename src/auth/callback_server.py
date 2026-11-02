"""OAuth の認可コードをローカル HTTP サーバーで受け取るモジュール"""

import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse


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


def wait_for_callback(
    service: str, host: str, port: int, expected_state: str, timeout: int = 180
) -> str:
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
                    raise RuntimeError(f"{service} 認証エラー: state が一致しません")
                return _CallbackHandler.auth_code
            if _CallbackHandler.error:
                raise RuntimeError(f"{service} 認証エラー: {_CallbackHandler.error}")
    finally:
        server.server_close()

    raise TimeoutError(f"{service} 認証がタイムアウトしました")
