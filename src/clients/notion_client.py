"""Notion API クライアント（体重データベースへの書き込み）

データベースは data source を親にしてページを作る（Notion-Version 2025-09-03 以降の方式）。
https://developers.notion.com/reference/post-page
https://developers.notion.com/reference/query-a-data-source
"""

from dataclasses import dataclass
from datetime import date as Date

import requests

from src.auth import notion_auth
from src.config import load_config

_BASE_URL = "https://api.notion.com/v1"

# 書き込み先データベースのプロパティ名。作成済みのデータベースに合わせる
_PROP_TITLE = "名前"
_PROP_DATE = "日付"
_PROP_WEIGHT = "体重"
_PROP_BODY_FAT = "体脂肪率"


@dataclass
class _Settings:
    data_source_id: str
    # 内部インテグレーションのトークン。空なら OAuth で保存したトークンを使う
    static_token: str


def _settings() -> _Settings | None:
    """config.yaml の notion 設定を返す。Notion を使わない設定なら None"""
    notion = load_config().get("notion") or {}
    token = notion.get("token") or ""
    client_id = notion.get("client_id") or ""
    client_secret = notion.get("client_secret") or ""
    data_source_id = notion.get("weight_data_source_id") or ""
    if not (token or client_id or client_secret or data_source_id):
        return None
    # 一部だけの設定は記入漏れとみなし、黙って飛ばさずに失敗として結果に出す
    if not data_source_id:
        raise ValueError("config.yaml の notion.weight_data_source_id が空です")
    if not token and not (client_id and client_secret):
        raise ValueError(
            "config.yaml の notion は token か、OAuth 用の client_id と client_secret が必要です"
        )
    return _Settings(data_source_id=data_source_id, static_token=token)


def is_configured() -> bool:
    """Notion への書き込みが設定されているか（一部だけの設定も True とし、書き込み時に失敗させる）"""
    try:
        return _settings() is not None
    except ValueError:
        return True


def _send(method: str, path: str, token: str, body: dict) -> requests.Response:
    return requests.request(
        method,
        f"{_BASE_URL}{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": notion_auth.NOTION_VERSION,
        },
        json=body,
        timeout=30,
    )


def _request(method: str, path: str, settings: _Settings, body: dict) -> dict:
    if settings.static_token:
        resp = _send(method, path, settings.static_token, body)
    else:
        resp = _send(method, path, notion_auth.get_access_token(), body)
        # OAuth のトークンは期限が示されないため、401 を受けたときだけ更新して1回やり直す
        if resp.status_code == 401:
            resp = _send(method, path, notion_auth.refresh_access_token(), body)
    if not resp.ok:
        raise RuntimeError(f"Notion API エラー ({resp.status_code}): {resp.text}")
    return resp.json()


def _find_page_id(settings: _Settings, d: Date) -> str | None:
    """測定日が一致するページを探す。同期履歴 DB を失っても二重に作らないために使う"""
    data = _request(
        "POST",
        f"/data_sources/{settings.data_source_id}/query",
        settings,
        {
            "filter": {"property": _PROP_DATE, "date": {"equals": d.isoformat()}},
            "page_size": 1,
        },
    )
    results = data.get("results", [])
    return results[0]["id"] if results else None


def upsert_body_composition(d: Date, weight_kg: float | None, body_fat_pct: float | None) -> None:
    """測定日のページに体重と体脂肪率を書き込む。同じ日のページがあれば更新する"""
    settings = _settings()
    if settings is None:
        raise ValueError("config.yaml に notion の設定がありません")
    properties: dict = {
        _PROP_TITLE: {"title": [{"text": {"content": d.isoformat()}}]},
        _PROP_DATE: {"date": {"start": d.isoformat()}},
    }
    if weight_kg is not None:
        properties[_PROP_WEIGHT] = {"number": weight_kg}
    if body_fat_pct is not None:
        properties[_PROP_BODY_FAT] = {"number": round(body_fat_pct, 1)}

    page_id = _find_page_id(settings, d)
    if page_id:
        _request("PATCH", f"/pages/{page_id}", settings, {"properties": properties})
    else:
        _request(
            "POST",
            "/pages",
            settings,
            {
                "parent": {"type": "data_source_id", "data_source_id": settings.data_source_id},
                "properties": properties,
            },
        )
