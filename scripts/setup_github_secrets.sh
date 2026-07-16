#!/usr/bin/env bash
# GitHub Actions 同期用の Secrets をローカルの設定からアップロードするスクリプト
#
# 使い方:
#   ./scripts/setup_github_secrets.sh --repo <owner>/<name>
#     --repo: アップロード先リポジトリ(同期を実行する private リポジトリ)。
#             省略時はカレントリポジトリ(このリポジトリ)に設定する
#
# 前提:
#   - gh CLI でログイン済みであること(gh auth login)
#   - ローカルでセットアップ・認証済みであること(README 参照)
#
# ローカルのトークンを更新した場合(再認証した場合)も、このスクリプトを再実行すればよい。
set -euo pipefail

cd "$(dirname "$0")/.."

repo=""
while [ $# -gt 0 ]; do
  case "$1" in
    --repo)
      repo="${2:?エラー: --repo にはリポジトリ(owner/name)を指定してください}"
      shift 2
      ;;
    *)
      echo "エラー: 不明な引数です: $1" >&2
      echo "使い方: $0 [--repo <owner>/<name>]" >&2
      exit 1
      ;;
  esac
done

require_file() {
  if [ ! -f "$1" ]; then
    echo "エラー: $1 がありません。$2" >&2
    exit 1
  fi
}

require_file config/config.yaml "README のセットアップを先に実施してください"
require_file config/tokens/fitbit_token.json "「uv run python main.py auth fitbit」で認証してください"
require_file config/tokens/healthplanet_token.json "「uv run python main.py auth healthplanet」で認証してください"

if [ -z "$repo" ]; then
  repo=$(gh repo view --json nameWithOwner -q .nameWithOwner)
fi
echo "アップロード先: ${repo}"

gh secret set CONFIG_YAML --repo "$repo" < config/config.yaml
gh secret set FITBIT_TOKEN_JSON --repo "$repo" < config/tokens/fitbit_token.json
gh secret set HEALTHPLANET_TOKEN_JSON --repo "$repo" < config/tokens/healthplanet_token.json

# 状態キャッシュ暗号化用のパスフレーズ(既存があれば維持し、キャッシュを無効化しない)
# 一覧取得の失敗時はここで止める(誤って再生成すると既存キャッシュを読めなくするため)
existing_secrets=$(gh secret list --repo "$repo" --json name -q '.[].name')
if grep -qx STATE_PASSPHRASE <<< "$existing_secrets"; then
  echo "STATE_PASSPHRASE は設定済みのため維持します"
else
  openssl rand -base64 32 | gh secret set STATE_PASSPHRASE --repo "$repo"
  echo "STATE_PASSPHRASE を生成して設定しました"
fi

echo
echo "完了しました。${repo} の Actions → sync → Run workflow で同期をキックできます。"
echo
echo "補足: fine-grained PAT(${repo} のみ・Secrets: Read and write)を"
echo "      「gh secret set GH_PAT --repo ${repo}」で設定すると、実行後の最新トークンが"
echo "      Secrets に書き戻されるため、長期間実行しなくても自動復旧できます(README 参照)。"
