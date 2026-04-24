"""あすけん Web 自動化クライアント（Playwright）

公式APIが存在しないため、Playwrightでブラウザ操作を自動化する。
launch_persistent_context() でブラウザプロファイルをディスクに永続化することで、
通常のブラウザと同様にセッションが維持される。
UIの変更により動作しなくなる可能性があり、その場合は CSV フォールバックを使用する。
"""

import csv
from datetime import date as Date
from pathlib import Path

from src.config import get_browser_profile_dir

_LOGIN_URL = "https://www.asken.jp/login"
_DIARY_URL = "https://www.asken.jp/my/diaries"


def _launch(playwright, headless: bool = False):
    """永続プロファイルでブラウザコンテキストを起動する"""
    profile_dir = get_browser_profile_dir("asken")
    context = playwright.chromium.launch_persistent_context(
        user_data_dir=str(profile_dir),
        headless=headless,
        viewport={"width": 1280, "height": 800},
        locale="ja-JP",
    )
    return context


def _is_logged_in(page) -> bool:
    """ログイン状態を確認する"""
    return "/login" not in page.url


def authenticate() -> None:
    """ブラウザを開いてあすけんにログインし、プロファイルを永続化する"""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        context = _launch(p, headless=False)
        page = context.new_page()

        print("あすけんのログインページを開きます...")
        print("ブラウザでログインし、完了したらここでEnterを押してください...")
        page.goto(_LOGIN_URL)
        input()

        if _is_logged_in(page):
            print("あすけん ログイン成功。プロファイルを保存しました。")
        else:
            context.close()
            raise RuntimeError("ログインに失敗しました。ブラウザでログインしてからEnterを押してください。")

        context.close()


def _ensure_logged_in(page, context) -> None:
    """ログイン済みか確認し、未ログインなら例外を発生させる"""
    page.goto(_DIARY_URL)
    page.wait_for_load_state("networkidle")
    if not _is_logged_in(page):
        raise RuntimeError(
            "あすけんのログインが必要です。`python main.py auth asken` を実行してください。"
        )


def post_weight(target_date: Date, weight_kg: float) -> None:
    """指定日の体重（kg）をあすけんに書き込む"""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        context = _launch(p, headless=False)
        page = context.new_page()
        try:
            _ensure_logged_in(page, context)
            _write_weight(page, target_date, weight_kg)
        finally:
            context.close()


def post_calories_burned(target_date: Date, calories: int) -> None:
    """指定日の消費カロリー（kcal）をあすけんに書き込む"""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        context = _launch(p, headless=False)
        page = context.new_page()
        try:
            _ensure_logged_in(page, context)
            _write_calories(page, target_date, calories)
        finally:
            context.close()


def _write_weight(page, target_date: Date, weight_kg: float) -> None:
    """あすけんの日記画面で体重を入力する"""
    date_str = target_date.strftime("%Y-%m-%d")
    page.goto(f"{_DIARY_URL}/{date_str}")
    page.wait_for_load_state("networkidle")

    weight_input = page.locator(
        'input[name="weight"], input[placeholder*="体重"], input[id*="weight"]'
    ).first

    if not weight_input.is_visible(timeout=5000):
        raise RuntimeError(
            f"あすけんの体重入力欄が見つかりませんでした（{date_str}）。"
            "UIが変更された可能性があります。"
        )

    weight_input.fill(str(round(weight_kg, 1)))

    save_btn = page.locator(
        'button:has-text("保存"), button:has-text("登録"), '
        'input[value*="保存"], input[value*="登録"]'
    ).first
    if save_btn.is_visible(timeout=3000):
        save_btn.click()
        page.wait_for_load_state("networkidle")


def _write_calories(page, target_date: Date, calories: int) -> None:
    """あすけんの日記画面で消費カロリーを入力する"""
    date_str = target_date.strftime("%Y-%m-%d")
    page.goto(f"{_DIARY_URL}/{date_str}")
    page.wait_for_load_state("networkidle")

    cal_input = page.locator(
        'input[name*="calorie"], input[name*="exercise"], '
        'input[placeholder*="消費"], input[placeholder*="カロリー"]'
    ).first

    if not cal_input.is_visible(timeout=5000):
        raise RuntimeError(
            f"あすけんの消費カロリー入力欄が見つかりませんでした（{date_str}）。"
            "UIが変更された可能性があります。"
        )

    cal_input.fill(str(calories))

    save_btn = page.locator(
        'button:has-text("保存"), button:has-text("登録"), '
        'input[value*="保存"], input[value*="登録"]'
    ).first
    if save_btn.is_visible(timeout=3000):
        save_btn.click()
        page.wait_for_load_state("networkidle")


def save_to_csv(records: list[dict], output_dir: str) -> Path:
    """あすけんへの書き込み失敗時のフォールバック：CSVに出力する"""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / "asken_fallback.csv"

    fieldnames = ["date", "weight_kg", "calories_burned"]
    write_header = not csv_path.exists()

    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        for r in records:
            writer.writerow(r)

    return csv_path
