"""あすけん Web 自動化クライアント（Playwright）

公式APIが存在しないため、Playwrightでブラウザ操作を自動化する。
UIの変更により動作しなくなる可能性があり、その場合は CSV フォールバックを使用する。
"""

import csv
import json
from datetime import date as Date
from pathlib import Path

from src.config import get_session_path, load_config

_LOGIN_URL = "https://www.asken.jp/login"
_DIARY_URL = "https://www.asken.jp/my/diaries"


def _get_browser_context(playwright):
    """Playwright ブラウザコンテキストを返す（セッションを再利用する）"""
    from playwright.sync_api import sync_playwright

    session_path = get_session_path("asken")
    storage_state = str(session_path) if session_path.exists() else None

    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context(
        storage_state=storage_state,
        viewport={"width": 1280, "height": 800},
        locale="ja-JP",
    )
    return browser, context


def authenticate() -> None:
    """ブラウザを開いてあすけんにログインし、セッションを保存する"""
    from playwright.sync_api import sync_playwright

    cfg = load_config()["asken"]
    session_path = get_session_path("asken")

    with sync_playwright() as p:
        browser, context = _get_browser_context(p)
        page = context.new_page()

        print("あすけんのログインページを開きます...")
        page.goto(_LOGIN_URL)
        page.wait_for_load_state("networkidle")

        # メールアドレスとパスワードが設定されていれば自動入力
        if cfg.get("email") and cfg.get("password"):
            email_input = page.locator('input[type="email"], input[name="email"], input[name="login_id"]').first
            password_input = page.locator('input[type="password"]').first
            if email_input.is_visible():
                email_input.fill(cfg["email"])
            if password_input.is_visible():
                password_input.fill(cfg["password"])
            # ログインボタンをクリック
            submit = page.locator('button[type="submit"], input[type="submit"]').first
            if submit.is_visible():
                submit.click()
                page.wait_for_load_state("networkidle")
        else:
            print("config.yaml に email/password が未設定です。手動でログインしてください。")
            print("ログイン完了後、Enterキーを押してください...")
            input()

        context.storage_state(path=str(session_path))
        browser.close()
    print("あすけん セッションを保存しました。")


def _is_logged_in(page) -> bool:
    """ログイン状態を確認する"""
    return "/login" not in page.url and "/my/" in page.url


def _ensure_logged_in(page, context) -> None:
    """未ログインの場合は例外を発生させる"""
    page.goto(_DIARY_URL)
    page.wait_for_load_state("networkidle")
    if not _is_logged_in(page):
        raise RuntimeError(
            "あすけんのセッションが切れています。`python main.py auth asken` を実行してください。"
        )


def post_weight(target_date: Date, weight_kg: float) -> None:
    """指定日の体重（kg）をあすけんに書き込む"""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser, context = _get_browser_context(p)
        page = context.new_page()
        try:
            _ensure_logged_in(page, context)
            _write_weight(page, target_date, weight_kg)
            # セッションを更新保存
            context.storage_state(path=str(get_session_path("asken")))
        finally:
            browser.close()


def post_calories_burned(target_date: Date, calories: int) -> None:
    """指定日の消費カロリー（kcal）をあすけんに書き込む"""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser, context = _get_browser_context(p)
        page = context.new_page()
        try:
            _ensure_logged_in(page, context)
            _write_calories(page, target_date, calories)
            context.storage_state(path=str(get_session_path("asken")))
        finally:
            browser.close()


def _write_weight(page, target_date: Date, weight_kg: float) -> None:
    """あすけんの日記画面で体重を入力する"""
    date_str = target_date.strftime("%Y-%m-%d")
    diary_url = f"{_DIARY_URL}/{date_str}"
    page.goto(diary_url)
    page.wait_for_load_state("networkidle")

    # 体重入力欄を探す（セレクタはUI変更で壊れる可能性あり）
    weight_input = page.locator(
        'input[name="weight"], input[placeholder*="体重"], input[id*="weight"]'
    ).first

    if not weight_input.is_visible(timeout=5000):
        raise RuntimeError(
            f"あすけんの体重入力欄が見つかりませんでした（{date_str}）。"
            "UIが変更された可能性があります。"
        )

    weight_input.fill(str(round(weight_kg, 1)))

    # 保存ボタンをクリック
    save_btn = page.locator(
        'button:has-text("保存"), button:has-text("登録"), input[value*="保存"], input[value*="登録"]'
    ).first
    if save_btn.is_visible(timeout=3000):
        save_btn.click()
        page.wait_for_load_state("networkidle")


def _write_calories(page, target_date: Date, calories: int) -> None:
    """あすけんの日記画面で消費カロリー（運動）を入力する"""
    date_str = target_date.strftime("%Y-%m-%d")
    diary_url = f"{_DIARY_URL}/{date_str}"
    page.goto(diary_url)
    page.wait_for_load_state("networkidle")

    # 消費カロリー入力欄を探す
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
        'button:has-text("保存"), button:has-text("登録"), input[value*="保存"], input[value*="登録"]'
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
