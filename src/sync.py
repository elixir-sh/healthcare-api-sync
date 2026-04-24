"""データ同期のオーケストレーションロジック"""

from dataclasses import dataclass, field
from datetime import date as Date, datetime, timedelta

from src import storage
from src.clients import fitbit_client, healthplanet_client, asken_client
from src.config import load_config


@dataclass
class SyncResult:
    """1回の同期実行の結果サマリー"""
    date: Date
    skipped: list[str] = field(default_factory=list)
    succeeded: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)
    asken_fallback_rows: list[dict] = field(default_factory=list)


def sync_range(date_from: Date, date_to: Date) -> list[SyncResult]:
    """指定期間のデータを同期し、結果一覧を返す"""
    storage.init_db()
    cfg = load_config()
    fallback_dir = cfg["sync"].get("fallback_csv_dir", "./output")

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

        # --- タニタ体重 → あすけん ---
        if hp and hp.weight_kg is not None:
            _sync_weight_to_asken(current, hp.weight_kg, result)
        else:
            result.skipped.append("HealthPlanet→あすけん 体重（データなし）")

        # --- Fitbit消費カロリー → あすけん ---
        _sync_calories_to_asken(current, result)

        # あすけん書き込み失敗分を CSV に保存
        if result.asken_fallback_rows:
            csv_path = asken_client.save_to_csv(result.asken_fallback_rows, fallback_dir)
            result.failed.append(("あすけん フォールバック", f"CSV保存: {csv_path}"))

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


def _sync_weight_to_asken(d: Date, weight_kg: float, result: SyncResult) -> None:
    label = f"HealthPlanet→あすけん 体重({weight_kg}kg)"
    if storage.is_synced(d, "healthplanet", "asken", "weight"):
        result.skipped.append(label)
        return
    try:
        asken_client.post_weight(d, weight_kg)
        storage.mark_synced(d, "healthplanet", "asken", "weight", weight_kg)
        result.succeeded.append(label)
    except Exception as e:
        # UI変更などでPlaywrightが失敗した場合はCSVフォールバック
        result.asken_fallback_rows.append({"date": str(d), "weight_kg": weight_kg, "calories_burned": ""})
        result.failed.append((label, f"Playwright失敗（CSVフォールバック）: {e}"))


def _sync_calories_to_asken(d: Date, result: SyncResult) -> None:
    label = "Fitbit→あすけん 消費カロリー"
    if storage.is_synced(d, "fitbit", "asken", "calories"):
        result.skipped.append(label)
        return
    try:
        calories = fitbit_client.get_calories(d)
        if calories is None:
            result.skipped.append(f"{label}（データなし）")
            return
        label = f"Fitbit→あすけん 消費カロリー({calories}kcal)"
        asken_client.post_calories_burned(d, calories)
        storage.mark_synced(d, "fitbit", "asken", "calories", float(calories))
        result.succeeded.append(label)
    except Exception as e:
        # Fitbit読み取り失敗の場合はカロリーなしでフォールバック行に追加
        result.asken_fallback_rows.append({"date": str(d), "weight_kg": "", "calories_burned": ""})
        result.failed.append((label, str(e)))
