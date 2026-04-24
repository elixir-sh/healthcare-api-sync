"""設定ファイルの読み書きを管理するモジュール"""

import os
import yaml
from pathlib import Path

# プロジェクトルートからの相対パス
_PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_PATH = _PROJECT_ROOT / "config" / "config.yaml"
TOKEN_DIR = _PROJECT_ROOT / "config" / "tokens"


def load_config() -> dict:
    """config.yaml を読み込む"""
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"設定ファイルが見つかりません: {CONFIG_PATH}")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_token_path(service: str) -> Path:
    """サービス名に対応するトークンファイルのパスを返す"""
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    return TOKEN_DIR / f"{service}_token.json"


def get_session_path(service: str) -> Path:
    """Playwright セッション保存先のパスを返す"""
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    return TOKEN_DIR / f"{service}_session.json"


def get_browser_profile_dir(service: str) -> Path:
    """Playwright 永続ブラウザプロファイルのディレクトリを返す"""
    profile_dir = TOKEN_DIR / f"{service}_browser_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    return profile_dir
