#!/data/data/com.termux/files/usr/bin/bash
# Termux上でsyncを実行するラッパー。cronおよびTermux:Widgetから呼ばれる。

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_FILE="$HOME/logs/healthcare_sync.log"
MAX_LINES=1000

mkdir -p "$HOME/logs"

# ログローテーション（超過したら空にする）
if [ -f "$LOG_FILE" ] && [ "$(wc -l < "$LOG_FILE")" -ge "$MAX_LINES" ]; then
    : > "$LOG_FILE"
fi

echo "--- $(date '+%Y-%m-%d %H:%M:%S') ---" >> "$LOG_FILE"

cd "$REPO_DIR" && python main.py sync >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

# termux-api がインストールされていればトースト通知
if command -v termux-toast &>/dev/null; then
    if [ "$EXIT_CODE" -eq 0 ]; then
        termux-toast "HealthSync: 同期完了"
    else
        termux-toast "HealthSync: 同期失敗（ログを確認してください）"
    fi
fi

exit "$EXIT_CODE"
