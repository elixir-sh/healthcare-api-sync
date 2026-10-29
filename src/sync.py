"""データ同期のオーケストレーションロジック"""

from dataclasses import dataclass, field
from datetime import date as Date
from datetime import datetime, timedelta

from src import storage
from src.clients import google_health_client, healthplanet_client

_SOURCE = "healthplanet"
_DESTINATION = "google_health"
# 移行前に Fitbit Web API 経由で書き込んだ記録。Google Health 上の同じデータなので再送しない
_LEGACY_DESTINATION = "fitbit"


@dataclass
class SyncResult:
    """1回の同期実行の結果サマリー"""
    date: Date
    skipped: list[str] = field(default_factory=list)
    succeeded: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)


def is_synced(d: Date, data_type: str) -> bool:
    """移行前の Fitbit 経由の記録も含めて、同期済みか判定する"""
    return storage.is_synced(d, _SOURCE, _DESTINATION, data_type) or storage.is_synced(
        d, _SOURCE, _LEGACY_DESTINATION, data_type
    )


def sync_range(date_from: Date, date_to: Date) -> list[SyncResult]:
    """指定期間のデータを同期し、結果一覧を返す"""
    storage.init_db()

    # HealthPlanet から期間内の体組成データを一括取得
    hp_records = healthplanet_client.get_innerscan(date_from, date_to)
    hp_by_date = {r.date: r for r in hp_records}

    results: list[SyncResult] = []

    current = date_from
    while current <= date_to:
        result = SyncResult(date=current)
        hp = hp_by_date.get(current)

        # --- タニタ体重 → Google Health ---
        if hp and hp.weight_kg is not None:
            _sync_weight(current, hp.weight_kg, hp.measured_at, result)
        else:
            result.skipped.append("HealthPlanet→Google Health 体重（データなし）")

        # --- タニタ体脂肪率 → Google Health ---
        if hp and hp.body_fat_pct is not None:
            _sync_body_fat(current, hp.body_fat_pct, hp.measured_at, result)
        else:
            result.skipped.append("HealthPlanet→Google Health 体脂肪率（データなし）")

        results.append(result)
        current += timedelta(days=1)

    return results


def _sync_weight(d: Date, weight_kg: float, measured_at: datetime, result: SyncResult) -> None:
    label = f"HealthPlanet→Google Health 体重({weight_kg}kg)"
    if is_synced(d, "weight"):
        result.skipped.append(label)
        return
    try:
        google_health_client.post_weight(measured_at, weight_kg)
        storage.mark_synced(d, _SOURCE, _DESTINATION, "weight", weight_kg)
        result.succeeded.append(label)
    except Exception as e:  # noqa: BLE001 1項目の失敗で他の項目の同期を止めず、結果に記録する
        result.failed.append((label, str(e)))


def _sync_body_fat(d: Date, body_fat_pct: float, measured_at: datetime, result: SyncResult) -> None:
    label = f"HealthPlanet→Google Health 体脂肪率({body_fat_pct}%)"
    if is_synced(d, "body_fat"):
        result.skipped.append(label)
        return
    try:
        google_health_client.post_body_fat(measured_at, body_fat_pct)
        storage.mark_synced(d, _SOURCE, _DESTINATION, "body_fat", body_fat_pct)
        result.succeeded.append(label)
    except Exception as e:  # noqa: BLE001 1項目の失敗で他の項目の同期を止めず、結果に記録する
        result.failed.append((label, str(e)))
