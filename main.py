"""健康データ集約・同期ツール CLI エントリポイント"""

import sys

if sys.version_info < (3, 10):
    print(f"エラー: Python 3.10以上が必要です（現在: {sys.version}）")
    sys.exit(1)

from datetime import date as Date, datetime, timedelta

import click

from src.config import load_config


@click.group()
def cli():
    """健康データ集約・同期ツール

    タニタ HealthPlanet の体重データを Fitbit に同期します。
    """


@cli.group()
def auth():
    """各サービスの認証を行います"""


@auth.command("fitbit")
def auth_fitbit():
    """Fitbit OAuth 2.0 認証（ブラウザが開きます）"""
    from src.auth.fitbit_auth import authenticate
    authenticate()


@auth.command("healthplanet")
def auth_healthplanet():
    """HealthPlanet OAuth 2.0 認証（ブラウザが開きます）"""
    from src.auth.healthplanet_auth import authenticate
    authenticate()


@cli.command()
@click.option(
    "--date",
    "target_date",
    default=None,
    help="同期する日付（YYYY-MM-DD形式）。省略すると直近N日分を同期します。",
)
@click.option(
    "--days",
    default=None,
    type=int,
    help="直近何日分を同期するか（省略時はconfig.yamlの設定値を使用）。",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="実際には書き込まずに何が同期されるかを表示します。",
)
def sync(target_date: str | None, days: int | None, dry_run: bool):
    """健康データを同期します"""
    from src.sync import sync_range

    cfg = load_config()
    default_days = cfg["sync"].get("default_days", 7)

    if target_date:
        try:
            d = datetime.strptime(target_date, "%Y-%m-%d").date()
        except ValueError:
            click.echo(f"エラー: 日付の形式が正しくありません（YYYY-MM-DD）: {target_date}", err=True)
            sys.exit(1)
        date_from = date_to = d
    else:
        n = days if days is not None else default_days
        date_to = Date.today()
        date_from = date_to - timedelta(days=n - 1)

    click.echo(f"同期期間: {date_from} 〜 {date_to}")

    if dry_run:
        click.echo("（ドライラン: 実際の書き込みは行いません）")
        from src import storage
        storage.init_db()
        current = date_from
        while current <= date_to:
            click.echo(f"\n📅 {current}")
            checks = [
                ("HealthPlanet→Fitbit 体重", "healthplanet", "fitbit", "weight"),
                ("HealthPlanet→Fitbit 体脂肪率", "healthplanet", "fitbit", "body_fat"),
            ]
            for label, src, dst, dtype in checks:
                status = "✅ 同期済み" if storage.is_synced(current, src, dst, dtype) else "⬜ 未同期"
                click.echo(f"  {status}  {label}")
            current += timedelta(days=1)
        return

    results = sync_range(date_from, date_to)
    _print_results(results)


def _print_results(results) -> None:
    total_ok = sum(len(r.succeeded) for r in results)
    total_skip = sum(len(r.skipped) for r in results)
    total_fail = sum(len(r.failed) for r in results)

    for r in results:
        if not (r.succeeded or r.failed):
            continue  # スキップのみの日は省略
        click.echo(f"\n📅 {r.date}")
        for s in r.succeeded:
            click.echo(f"  ✅ {s}")
        for label, reason in r.failed:
            click.echo(f"  ❌ {label}: {reason}")

    click.echo(f"\n--- 同期完了 ---")
    click.echo(f"成功: {total_ok}件  スキップ: {total_skip}件  失敗: {total_fail}件")

    if total_fail > 0:
        sys.exit(1)


if __name__ == "__main__":
    cli()
