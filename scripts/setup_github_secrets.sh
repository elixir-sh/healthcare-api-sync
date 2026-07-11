#!/usr/bin/env bash
# GitHub Actions(スマホからの手動同期)用の Secrets をローカルの設定からアップロードするスクリプト
#
# 前提:
#   - gh CLI でログイン済みであること(gh auth login)
#   - ローカルでセットアップ・認証済みであること(README 参照)
#
# ローカルのトークンを更新した場合(再認証した場合)も、このスクリプトを再実行すればよい。
set -euo pipefail

cd "$(dirname "$0")/.."

require_file() {
  if [ ! -f "$1" ]; then
    echo "エラー: $1 がありません。$2" >&2
    exit 1
  fi
}

require_file config/config.yaml "README のセットアップを先に実施してください"
require_file config/tokens/fitbit_token.json "「uv run python main.py auth fitbit」で認証してください"
require_file config/tokens/healthplanet_token.json "「uv run python main.py auth healthplanet」で認証してください"

repo=$(gh repo view --json nameWithOwner -q .nameWithOwner)
echo "アップロード先: ${repo}"

gh secret set CONFIG_YAML < config/config.yaml
gh secret set FITBIT_TOKEN_JSON < config/tokens/fitbit_token.json
gh secret set HEALTHPLANET_TOKEN_JSON < config/tokens/healthplanet_token.json

# 状態キャッシュ暗号化用のパスフレーズ(既存があれば維持し、キャッシュを無効化しない)
if gh secret list --json name -q '.[].name' | grep -qx STATE_PASSPHRASE; then
  echo "STATE_PASSPHRASE は設定済みのため維持します"
else
  openssl rand -base64 32 | gh secret set STATE_PASSPHRASE
  echo "STATE_PASSPHRASE を生成して設定しました"
fi

echo
echo "完了しました。スマホの GitHub アプリ → Actions → sync → Run workflow で同期をキックできます。"
echo
echo "補足: fine-grained PAT(このリポジトリのみ・Secrets: Read and write)を"
echo "      「gh secret set GH_PAT」で設定すると、実行後の最新トークンが Secrets に"
echo "      書き戻されるため、長期間実行しなくても自動復旧できます(README 参照)。"
