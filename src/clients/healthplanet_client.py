"""HealthPlanet API クライアント（タニタ体組成計データ取得）"""

from dataclasses import dataclass
from datetime import date as Date, datetime

import requests

from src.auth.healthplanet_auth import get_access_token

_INNERSCAN_URL = "https://www.healthplanet.jp/status/innerscan.json"

# tag 番号の定義（HealthPlanet API ドキュメントより）
_TAG_WEIGHT = "6021"       # 体重 (kg)
_TAG_BODY_FAT = "6022"     # 体脂肪率 (%)
_TAG_MUSCLE_MASS = "6023"  # 筋肉量 (kg)


@dataclass
class InnerscanRecord:
    date: Date
    measured_at: datetime  # 計測日時（同日複数回の場合は最後の計測時刻）
    weight_kg: float | None
    body_fat_pct: float | None
    muscle_mass_kg: float | None


def get_innerscan(date_from: Date, date_to: Date) -> list[InnerscanRecord]:
    """指定期間の体組成データを取得する（最大3ヶ月分）

    同一日に複数回計測がある場合は最後の計測値を使用する。
    """
    resp = requests.get(
        _INNERSCAN_URL,
        params={
            "access_token": get_access_token(),
            "date": 1,  # 計測日時で取得
            # date は時刻を持たないため、from は日の始まり・to は日の終わりに固定する
            "from": date_from.strftime("%Y%m%d") + "000000",
            "to": date_to.strftime("%Y%m%d") + "235959",
            "tag": ",".join([_TAG_WEIGHT, _TAG_BODY_FAT, _TAG_MUSCLE_MASS]),
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    # 日付ごとにデータをまとめる（同一日は後勝ち・最新時刻を記録）
    by_date: dict[Date, dict] = {}
    by_date_dt: dict[Date, datetime] = {}
    for item in data.get("data", []):
        # date フォーマット: "20240101120000"
        dt = datetime.strptime(item["date"], "%Y%m%d%H%M%S")
        d = dt.date()
        if d not in by_date:
            by_date[d] = {}
            by_date_dt[d] = dt
        by_date[d][item["tag"]] = float(item["keydata"])
        if dt > by_date_dt[d]:
            by_date_dt[d] = dt

    records = []
    for d in sorted(by_date):
        tags = by_date[d]
        records.append(
            InnerscanRecord(
                date=d,
                measured_at=by_date_dt[d],
                weight_kg=tags.get(_TAG_WEIGHT),
                body_fat_pct=tags.get(_TAG_BODY_FAT),
                muscle_mass_kg=tags.get(_TAG_MUSCLE_MASS),
            )
        )
    return records
