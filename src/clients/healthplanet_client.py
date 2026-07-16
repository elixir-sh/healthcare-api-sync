"""HealthPlanet API クライアント（タニタ体組成計データ取得）"""

from dataclasses import dataclass
from datetime import date as Date, datetime

import requests

from src.auth.healthplanet_auth import get_access_token

_INNERSCAN_URL = "https://www.healthplanet.jp/status/innerscan.json"

# tag 番号の定義（HealthPlanet API ドキュメントより）
_TAG_WEIGHT = "6021"  # 体重 (kg)
_TAG_BODY_FAT = "6022"  # 体脂肪率 (%)
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

    # 計測日時（タグ群が同時に記録された単位）ごとにデータをまとめる
    by_datetime: dict[datetime, dict] = {}
    for item in data.get("data", []):
        # date フォーマット: "202607161047"（秒は含まれない）
        dt = datetime.strptime(item["date"], "%Y%m%d%H%M")
        by_datetime.setdefault(dt, {})[item["tag"]] = float(item["keydata"])

    # 日付ごとに最後（最新）の計測日時を採用し、その計測分のタグ値のみを使う
    # （同日に複数回計測した際、値と時刻が別の計測分から混ざらないようにする）
    latest_dt_by_date: dict[Date, datetime] = {}
    for dt in by_datetime:
        d = dt.date()
        if d not in latest_dt_by_date or dt > latest_dt_by_date[d]:
            latest_dt_by_date[d] = dt

    records = []
    for d in sorted(latest_dt_by_date):
        dt = latest_dt_by_date[d]
        tags = by_datetime[dt]
        records.append(
            InnerscanRecord(
                date=d,
                measured_at=dt,
                weight_kg=tags.get(_TAG_WEIGHT),
                body_fat_pct=tags.get(_TAG_BODY_FAT),
                muscle_mass_kg=tags.get(_TAG_MUSCLE_MASS),
            )
        )
    return records
