"""データ同期のオーケストレーションロジック"""

from dataclasses import dataclass, field
from datetime import date as Date, timedelta

from src import storage
from src.clients import fitbit_client, healthplanet_client
from src.config import load_config


@dataclass
class SyncResult:
    """1回の同期実行の結果サマリー"""
    date: Date
    skipped: list[str] = field(default_factory=list)
    succeeded: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)


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

        # --- タニタ体重 → Fitbit ---
        if hp and hp.weight_kg is not None:
            _sync_weight_to_fitbit(current, hp.weight_kg, result)
        else:
            result.skipped.append("HealthPlanet→Fitbit 体重（データなし）")

        # --- タニタ体脂肪率 → Fitbit ---
        if hp and hp.body_fat_pct is not None:
            _sync_body_fat_to_fitbit(current, hp.body_fat_pct, result)
        else:
            result.skipped.append("HealthPlanet→Fitbit 体脂肪率（データなし）")

        results.append(result)
        current += timedelta(days=1)

    return results


def _sync_weight_to_fitbit(d: Date, weight_kg: float, result: SyncResult) -> None:
    label = f"HealthPlanet→Fitbit 体重({weight_kg}kg)"
    if storage.is_synced(d, "healthplanet", "fitbit", "weight"):
        result.skipped.append(label)
        return
    try:
        fitbit_client.post_weight(d, weight_kg)
        storage.mark_synced(d, "healthplanet", "fitbit", "weight", weight_kg)
        result.succeeded.append(label)
    except Exception as e:
        result.failed.append((label, str(e)))


def _sync_body_fat_to_fitbit(d: Date, body_fat_pct: float, result: SyncResult) -> None:
    label = f"HealthPlanet→Fitbit 体脂肪率({body_fat_pct}%)"
    if storage.is_synced(d, "healthplanet", "fitbit", "body_fat"):
        result.skipped.append(label)
        return
    try:
        fitbit_client.post_body_fat(d, body_fat_pct)
        storage.mark_synced(d, "healthplanet", "fitbit", "body_fat", body_fat_pct)
        result.succeeded.append(label)
    except Exception as e:
        result.failed.append((label, str(e)))
