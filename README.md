# healthcare-api-sync

タニタ HealthPlanet の体組成データを Fitbit に自動同期するローカル CLI ツール。

## データフロー

```
タニタ HealthPlanet
   ├─→ 体重    ──→ Fitbit
   └─→ 体脂肪率 ──→ Fitbit
```

> **あすけんへの同期について**  
> あすけんは Fitbit との公式連携機能を持つため、Fitbit にデータを書き込めば自動で反映されます。

## 必要なもの

- Python 3.12 以上
- [uv](https://docs.astral.sh/uv/)（パッケージ管理）
- 各サービスのアカウント
  - [Fitbit](https://www.fitbit.com/)
  - [HealthPlanet（タニタ）](https://www.healthplanet.jp/)

## セットアップ

### 1. 依存パッケージのインストール

```bash
uv sync
```

### 2. API アプリを登録する

#### Fitbit

1. [Fitbit Developer Console](https://dev.fitbit.com/apps) にアクセス
2. 「Register an app」をクリックし、以下を入力

   | 項目 | 値 |
   |---|---|
   | OAuth 2.0 Application Type | **Personal** |
   | Redirect URL | `http://localhost:8080/callback` |

3. 表示された `Client ID` と `Client Secret` を控える

#### HealthPlanet

1. [HealthPlanet API設定](https://www.healthplanet.jp/apis/api.do) にアクセス
2. 「アプリケーション登録」をクリックし、以下を入力

   | 項目 | 値 |
   |---|---|
   | アプリケーションタイプ | **Webアプリケーション** |
   | ホストドメイン | `www.healthplanet.jp` |
   | スコープ | `innerscan` |

3. 表示された `Client ID` と `Client Secret` を控える

### 3. 設定ファイルを作成する

```bash
cp config/config.yaml.example config/config.yaml
```

`config/config.yaml` を編集し、取得した値を記入する。

```yaml
fitbit:
  client_id: "取得したClient ID"
  client_secret: "取得したClient Secret"

healthplanet:
  client_id: "取得したClient ID"
  client_secret: "取得したClient Secret"
```

### 4. 認証する

初回のみ、各サービスの認証を行う。

```bash
uv run python main.py auth fitbit        # ブラウザが開く → Fitbit でログイン・許可
uv run python main.py auth healthplanet  # ブラウザが開く → HealthPlanet でログイン・許可
```

> **HealthPlanet 認証の手順**  
> HealthPlanet は外部コールバック URL を受け付けないため、認証後に表示される  
> `https://www.healthplanet.jp/success.html?code=...` の URL をコピーして  
> ターミナルのエディタにペーストする方式を採用しています。

認証トークンは `config/tokens/` にローカル保存される（git 管理外）。

## 使い方

```bash
# 直近7日分を同期（デフォルト）
uv run python main.py sync

# 特定の日付を同期
uv run python main.py sync --date 2026-04-24

# 直近30日分を同期
uv run python main.py sync --days 30

# 実際には書き込まず、同期済み/未同期を確認する
uv run python main.py sync --dry-run
```

## GitHub Actions で同期する（定期実行 + 手動実行）

同期ワークフロー（`.github/workflows/sync.yml`）は **reusable workflow** として公開している。
実際の実行（毎日 15:00 JST の定期実行と手動実行）は、Secrets とスケジュールを持つ
**自分の private リポジトリ**からこのワークフローを呼び出して行う。

```
このリポジトリ（public）        自分のリポジトリ（private）
  コード + ワークフロー定義  ←──  呼び出しワークフロー + Secrets + schedule
                                  （実行履歴・ログ・キャッシュもこちらに保存）
```

このリポジトリは public のため、ここで実行すると Actions の実行履歴やログ
（実行日時・成否などのメタ情報）が誰でも見られてしまう。個人の運用を private 側に
分離することでそれを避けつつ、コードは公開のまま誰でも使える状態を保っている。

### 初回セットアップ（PC で1回だけ）

ローカルでのセットアップ・認証（上記）を済ませたうえで、以下を行う。

```bash
# 1. 実行用の private リポジトリを作成する
gh repo create <owner>/healthcare-api-sync-runner --private --clone

# 2. 呼び出しワークフローの雛形を配置して push する
mkdir -p healthcare-api-sync-runner/.github/workflows
cp examples/sync-caller.yml healthcare-api-sync-runner/.github/workflows/sync.yml
cd healthcare-api-sync-runner
git add . && git commit -m "同期ワークフローを追加" && git push
cd -

# 3. Secrets を private リポジトリへアップロードする
./scripts/setup_github_secrets.sh --repo <owner>/healthcare-api-sync-runner
```

設定される Secrets:

| Secret | 内容 |
|---|---|
| `CONFIG_YAML` | `config.yaml` の内容 |
| `FITBIT_TOKEN_JSON` | Fitbit トークン（初回シード用） |
| `HEALTHPLANET_TOKEN_JSON` | HealthPlanet トークン（初回シード用） |
| `STATE_PASSPHRASE` | 状態キャッシュ暗号化用パスフレーズ（自動生成） |

セットアップ後、private リポジトリの Actions → sync → Run workflow を
`dry_run` にチェックを入れて実行し、動作確認するとよい。

> **fork して使う場合**
> コードを fork してカスタマイズする場合は、呼び出しワークフローの `uses:` と
> `code_repository` / `code_ref` を自分の fork に向ける（`examples/sync-caller.yml` 内のコメント参照）。

### スマホからの手動キック方法

定期実行を待たずに今すぐ同期したい場合は、
[GitHub モバイルアプリ](https://github.com/mobile)またはブラウザから、以下の手順でキックする。

1. **private リポジトリ**を開き「Actions」タブへ
2. ワークフロー「sync」を選ぶ
3. 「Run workflow」をタップ（日付・日数・ドライランを指定可能）

ブラウザの場合は Actions のページをホーム画面に追加しておくとワンタップで開ける。

### トークンと同期履歴の持ち回り

Fitbit はトークンリフレッシュのたびにリフレッシュトークンが差し替わるため、
実行後の最新トークンと同期履歴 DB を**暗号化して Actions キャッシュ**に保存し、次回実行時に復元する。
キャッシュも Secrets も、実行元である **private リポジトリ側**に保存される。

キャッシュは 7 日間使われないと消える。毎日定期実行しているため通常は失効しないが、
定期実行が止まる等でキャッシュが消えた場合は Secrets のトークンにフォールバックする。
その場合、一度でも CI で同期していると Secrets 側の Fitbit トークンは失効している
（ローテーションのため）。次のどちらかで運用する。

- **（推奨）fine-grained PAT を Secret `GH_PAT` に設定する**
  実行のたびに最新トークンが Secrets に書き戻されるため、期間が空いても自動復旧する。
  [Fine-grained tokens](https://github.com/settings/personal-access-tokens/new) で
  **private リポジトリのみ**・Repository permissions → **Secrets: Read and write** を
  付与して作成し、`gh secret set GH_PAT --repo <owner>/healthcare-api-sync-runner` で登録する
- PAT を設定しない場合、7 日以上間隔が空いて同期が失敗するようになったら、
  ローカルで再認証して `./scripts/setup_github_secrets.sh --repo <owner>/healthcare-api-sync-runner`
  を再実行する

## 注意事項

### GitHub Actions 運用時の注意

- **CI で同期を実行すると、ローカルの Fitbit トークンは失効する**（リフレッシュトークンの
  ローテーションのため）。以後ローカルでも実行したい場合は `uv run python main.py auth fitbit`
  で再認証する。CI とローカルの常時併用は想定せず、どちらか一方を主にする
- 実行を private リポジトリ側に分離しているため、**実行履歴・ログは非公開**になる。
  なおワークフローが public リポジトリで実行された場合に備えて、体重などの数値と
  認証情報のログマスクは維持している
- 同期履歴 DB もキャッシュで持ち回るため、キャッシュが消えると同じデータを再送する
  可能性があるが、同じ計測日時・同じ値の再送のため実害はほぼない
- private リポジトリの Actions は無料枠（個人アカウントは月 2,000 分）を消費するが、
  この同期は1回数分・1日1回のため十分収まる
- GitHub の仕様上、**リポジトリに60日間コミット等の操作がないと定期実行（schedule）が
  自動的に無効化される**。実行用 private リポジトリはコミットがほぼ発生しないため、
  雛形ワークフロー（`examples/sync-caller.yml`）には実行のたびに停止タイマーを
  リセットするキープアライブを組み込んである

### Fitbit Web API の廃止について

Fitbit レガシー Web API は **2026年9月に廃止予定**。  
移行先は [Google Health API](https://developers.google.com/health/migration)。  
廃止後は `src/clients/fitbit_client.py` を差し替えることで対応できる設計にしている。

## ファイル構成

```
healthcare-api-sync/
├── .github/
│   └── workflows/
│       └── sync.yml         # 同期ワークフロー（private リポジトリから呼び出す reusable workflow）
├── config/
│   ├── config.yaml          # 設定ファイル（git 管理外）
│   ├── config.yaml.example  # 設定ファイルのテンプレート
│   └── tokens/              # 認証トークン保存先（git 管理外）
├── examples/
│   └── sync-caller.yml      # private リポジトリに置く呼び出しワークフローの雛形
├── scripts/
│   └── setup_github_secrets.sh  # 実行用リポジトリへの Secrets アップロード
├── src/
│   ├── auth/
│   │   ├── fitbit_auth.py        # Fitbit OAuth 2.0 + PKCE
│   │   └── healthplanet_auth.py  # HealthPlanet OAuth 2.0
│   ├── clients/
│   │   ├── fitbit_client.py        # Fitbit API クライアント
│   │   └── healthplanet_client.py  # HealthPlanet API クライアント
│   ├── config.py   # 設定管理
│   ├── storage.py  # SQLite による二重書き込み防止
│   └── sync.py     # 同期ロジック
├── main.py          # CLI エントリポイント
├── pyproject.toml   # uv プロジェクト設定・依存関係定義
└── uv.lock          # 依存関係のロックファイル
```
