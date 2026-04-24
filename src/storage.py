"""SQLite を使って同期済みレコードを管理し、二重書き込みを防止するモジュール"""

import sqlite3
from pathlib import Path
from datetime import date as Date

_DB_PATH = Path(__file__).parent.parent / "config" / "sync_history.db"


def _get_conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """テーブルを初期化する（存在しない場合のみ作成）"""
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sync_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                source TEXT NOT NULL,
                destination TEXT NOT NULL,
                data_type TEXT NOT NULL,
                value REAL NOT NULL,
                synced_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                UNIQUE(date, source, destination, data_type)
            )
        """)


def is_synced(
    record_date: Date,
    source: str,
    destination: str,
    data_type: str,
) -> bool:
    """指定の組み合わせが既に同期済みか確認する"""
    with _get_conn() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM sync_history
            WHERE date=? AND source=? AND destination=? AND data_type=?
            """,
            (str(record_date), source, destination, data_type),
        ).fetchone()
        return row is not None


def mark_synced(
    record_date: Date,
    source: str,
    destination: str,
    data_type: str,
    value: float,
) -> None:
    """同期済みとして記録する（重複時は無視）"""
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO sync_history (date, source, destination, data_type, value)
            VALUES (?, ?, ?, ?, ?)
            """,
            (str(record_date), source, destination, data_type, value),
        )
