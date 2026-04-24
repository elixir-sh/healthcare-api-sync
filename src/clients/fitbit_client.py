"""Fitbit Web API クライアント

NOTE: レガシーFitbit Web APIは2026年9月廃止予定。
移行先: Google Health API (https://developers.google.com/health/migration)
移行時は本ファイルを差し替えるだけで対応できるよう、インターフェースを統一している。
"""

from datetime import date as Date

import requests

from src.auth.fitbit_auth import get_access_token

_BASE_URL = "https://api.fitbit.com"


def _headers() -> dict:
    return {"Authorization": f"Bearer {get_access_token()}"}


def get_calories(target_date: Date) -> int | None:
    """指定日の総消費カロリー（kcal）を取得する。データがない場合は None を返す"""
    date_str = target_date.strftime("%Y-%m-%d")
    resp = requests.get(
        f"{_BASE_URL}/1/user/-/activities/date/{date_str}.json",
        headers=_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    calories_out = data.get("summary", {}).get("caloriesOut")
    if calories_out is None or calories_out == 0:
        return None
    return int(calories_out)


def post_weight(target_date: Date, weight_kg: float) -> None:
    """指定日の体重（kg）を Fitbit に書き込む"""
    resp = requests.post(
        f"{_BASE_URL}/1/user/-/body/log/weight.json",
        headers=_headers(),
        data={
            "weight": round(weight_kg, 2),
            "date": target_date.strftime("%Y-%m-%d"),
        },
        timeout=30,
    )
    resp.raise_for_status()
