#!/bin/bash
# Termux環境のセットアップスクリプト。
# リポジトリのルートで実行すること: bash setup_termux.sh

set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== パッケージのインストール ==="
pkg update -y
pkg install -y python git cronie

echo ""
echo "=== Python依存ライブラリのインストール ==="
python -m pip install -r "$REPO_DIR/requirements.txt"

echo ""
echo "=== Termux:Boot 設定（起動時にcrondを自動起動）==="
mkdir -p ~/.termux/boot
cat > ~/.termux/boot/start_crond.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
crond
EOF
chmod +x ~/.termux/boot/start_crond.sh

echo ""
echo "=== cron ジョブの登録（毎日12時に自動同期）==="
SYNC_SCRIPT="$REPO_DIR/scripts/termux_sync.sh"
chmod +x "$SYNC_SCRIPT"
CRON_JOB="0 12 * * * bash \"$SYNC_SCRIPT\""

# 同じジョブが既に登録されていなければ追加
if ! crontab -l 2>/dev/null | grep -qF "$SYNC_SCRIPT"; then
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    echo "登録しました: $CRON_JOB"
else
    echo "既に登録済みです。スキップします。"
fi

echo ""
echo "=== Termux:Widget 用ショートカット（オプション）==="
SHORTCUT_DIR="$HOME/.shortcuts"
mkdir -p "$SHORTCUT_DIR"
cat > "$SHORTCUT_DIR/HealthSync" << EOF
#!/data/data/com.termux/files/usr/bin/bash
bash "$SYNC_SCRIPT"
EOF
chmod +x "$SHORTCUT_DIR/HealthSync"
echo "作成しました: $SHORTCUT_DIR/HealthSync"
echo "（Termux:Widget アプリを使う場合はホーム画面にウィジェットを追加してください）"

echo ""
echo "=== セットアップ完了 ==="
echo ""
echo "次のステップ:"
echo "  1. 認証を行う（初回のみ）:"
echo "     python main.py auth fitbit"
echo "     python main.py auth healthplanet"
echo "  2. 動作確認:"
echo "     bash scripts/termux_sync.sh"
echo ""
echo "【注意】Termux:Boot アプリをインストールしないと端末再起動後に crond が起動しません。"
echo "  F-Droid からインストールしてください: https://f-droid.org/"
