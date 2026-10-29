"""Google Health API クライアント

2026年11月に停止したレガシー Fitbit Web API の後継。
https://developers.google.com/health/reference/rest/v4/users.dataTypes.dataPoints/create
"""

from datetime import UTC, datetime, timedelta, timezone

import requests

from src.auth.google_health_auth import get_access_token

_BASE_URL = "https://health.googleapis.com/v4/users/me/dataTypes"
# HealthPlanet の計測日時はタイムゾーン情報を持たない日本時間のため、JST として扱う
_JST = timezone(timedelta(hours=9))


def _headers() -> dict:
    return {"Authorization": f"Bearer {get_access_token()}"}


def _sample_time(measured_at: datetime) -> dict:
    """計測日時を ObservationSampleTime 形式に変換する"""
    if measured_at.tzinfo is None:
        measured_at = measured_at.replace(tzinfo=_JST)
    offset = measured_at.utcoffset() or timedelta(0)
    return {
        "physicalTime": measured_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "utcOffset": f"{int(offset.total_seconds())}s",
    }


def _create_data_point(data_type: str, body: dict) -> None:
    resp = requests.post(
        f"{_BASE_URL}/{data_type}/dataPoints",
        headers=_headers(),
        json=body,
        timeout=30,
    )
    if not resp.ok:
        raise RuntimeError(f"Google Health API エラー ({resp.status_code}): {resp.text}")
    # レスポンスは Operation。HTTP 200 でも処理失敗が error に入る場合がある
    operation = resp.json()
    if "error" in operation:
        raise RuntimeError(f"Google Health API エラー: {operation['error']}")


def post_weight(measured_at: datetime, weight_kg: float) -> None:
    """体重（kg）を Google Health に書き込む"""
    _create_data_point(
        "weight",
        {
            "weight": {
                "sampleTime": _sample_time(measured_at),
                # API はグラム単位
                "weightGrams": round(weight_kg * 1000),
            }
        },
    )


def post_body_fat(measured_at: datetime, body_fat_pct: float) -> None:
    """体脂肪率（%）を Google Health に書き込む"""
    _create_data_point(
        "body-fat",
        {
            "bodyFat": {
                "sampleTime": _sample_time(measured_at),
                "percentage": round(body_fat_pct, 1),
            }
        },
    )
