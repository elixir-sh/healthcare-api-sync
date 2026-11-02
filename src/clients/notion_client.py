"""Notion API クライアント（体重データベースへの書き込み）

データベースは data source を親にしてページを作る（Notion-Version 2025-09-03 以降の方式）。
https://developers.notion.com/reference/post-page
https://developers.notion.com/reference/query-a-data-source
"""

from datetime import date as Date

import requests

from src.config import load_config

_BASE_URL = "https://api.notion.com/v1"
_NOTION_VERSION = "2025-09-03"

# 書き込み先データベースのプロパティ名。作成済みのデータベースに合わせる
_PROP_TITLE = "名前"
_PROP_DATE = "日付"
_PROP_WEIGHT = "体重"
_PROP_BODY_FAT = "体脂肪率"


def _settings() -> tuple[str, str] | None:
    """config.yaml の notion 設定を (token, data_source_id) で返す。未設定なら None"""
    notion = load_config().get("notion") or {}
    token = notion.get("token") or ""
    data_source_id = notion.get("weight_data_source_id") or ""
    if not token and not data_source_id:
        return None
    if not token or not data_source_id:
        # 片方だけの設定は記入漏れとみなし、黙って飛ばさずに失敗として結果に出す
        raise ValueError("config.yaml の notion は token と weight_data_source_id の両方が必要です")
    return token, data_source_id


def is_configured() -> bool:
    """Notion への書き込みが設定されているか（片方だけの設定も True とし、書き込み時に失敗させる）"""
    try:
        return _settings() is not None
    except ValueError:
        return True


def _request(method: str, path: str, token: str, body: dict) -> dict:
    resp = requests.request(
        method,
        f"{_BASE_URL}{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": _NOTION_VERSION,
        },
        json=body,
        timeout=30,
    )
    if not resp.ok:
        raise RuntimeError(f"Notion API エラー ({resp.status_code}): {resp.text}")
    return resp.json()


def _find_page_id(token: str, data_source_id: str, d: Date) -> str | None:
    """測定日が一致するページを探す。同期履歴 DB を失っても二重に作らないために使う"""
    data = _request(
        "POST",
        f"/data_sources/{data_source_id}/query",
        token,
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
    token, data_source_id = settings

    properties: dict = {
        _PROP_TITLE: {"title": [{"text": {"content": d.isoformat()}}]},
        _PROP_DATE: {"date": {"start": d.isoformat()}},
    }
    if weight_kg is not None:
        properties[_PROP_WEIGHT] = {"number": weight_kg}
    if body_fat_pct is not None:
        properties[_PROP_BODY_FAT] = {"number": round(body_fat_pct, 1)}

    page_id = _find_page_id(token, data_source_id, d)
    if page_id:
        _request("PATCH", f"/pages/{page_id}", token, {"properties": properties})
    else:
        _request(
            "POST",
            "/pages",
            token,
            {
                "parent": {"type": "data_source_id", "data_source_id": data_source_id},
                "properties": properties,
            },
        )
