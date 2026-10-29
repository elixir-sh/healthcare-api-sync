# healthcare-api-sync

タニタ HealthPlanet の体組成データを Google Health に自動同期するローカル CLI ツール。

## データフロー

```
タニタ HealthPlanet
   ├─→ 体重    ──→ Google Health
   └─→ 体脂肪率 ──→ Google Health
```

> **あすけんへの同期について**  
> あすけんは Fitbit との公式連携機能で体重を取り込む。Google Health API に書き込んだデータが
> この連携経由であすけんに反映されるかは、移行時点では未確認である。

## 必要なもの

- Python 3.12 以上
- [uv](https://docs.astral.sh/uv/)（パッケージ管理）
- 各サービスのアカウント
  - Google アカウント（Fitbit アカウントを Google アカウントへ移行済みであること）
  - [Google Cloud](https://console.cloud.google.com/) のプロジェクト
  - [HealthPlanet（タニタ）](https://www.healthplanet.jp/)

## セットアップ

### 1. 依存パッケージのインストール

```bash
uv sync
```

### 2. API アプリを登録する

#### Google Health API

1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェクトを作成し、
   「API とサービス」→「ライブラリ」で **Google Health API** を有効にする
2. 「Google Auth Platform」で OAuth 同意画面を作成する

   | 項目 | 値 |
   |---|---|
   | 対象 | 外部 |
   | データアクセス（スコープ） | `.../auth/googlehealth.health_metrics_and_measurements.writeonly` |

3. 「対象」で公開ステータスを **本番環境（In production）に公開** する。
   テスト中（Testing）のままだとリフレッシュトークンが7日で失効し、定期実行が止まる。
   個人利用（100ユーザー未満）なら審査なしで公開でき、認証時に「Google はこのアプリを確認していません」と
   表示されるだけで済む
4. 「クライアント」で OAuth クライアント ID を作成し、以下を入力

   | 項目 | 値 |
   |---|---|
   | アプリケーションの種類 | **ウェブ アプリケーション** |
   | 承認済みのリダイレクト URI | `http://localhost:8080/callback` |

5. 表示された `クライアント ID` と `クライアント シークレット` を控える

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
google_health:
  client_id: "取得したクライアント ID"
  client_secret: "取得したクライアント シークレット"

healthplanet:
  client_id: "取得したClient ID"
  client_secret: "取得したClient Secret"
```

### 4. 認証する

初回のみ、各サービスの認証を行う。

```bash
uv run python main.py auth google-health  # ブラウザが開く → Google でログイン・許可
uv run python main.py auth healthplanet   # ブラウザが開く → HealthPlanet でログイン・許可
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
| `GOOGLE_HEALTH_TOKEN_JSON` | Google Health トークン（初回シード用） |
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

アクセストークンは1時間で切れ、実行のたびにリフレッシュされる。そこで
実行後の最新トークンと同期履歴 DB を**暗号化して Actions キャッシュ**に保存し、次回実行時に復元する。
キャッシュも Secrets も、実行元である **private リポジトリ側**に保存される。

キャッシュは 7 日間使われないと消える。毎日定期実行しているため通常は失効しないが、
定期実行が止まる等でキャッシュが消えた場合は Secrets のトークンにフォールバックする。
Google のリフレッシュトークンはリフレッシュで差し替わらないため、通常は Secrets のトークンで
そのまま復旧できる。ただし Google がトークンを失効させた場合に備えて、次のどちらかで運用する。

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

- CI とローカルの両方で同期すると、それぞれの同期履歴 DB が別になるため、同じデータを
  二重に書き込むことがある。常時併用は想定せず、どちらか一方を主にする
- 実行を private リポジトリ側に分離しているため、**実行履歴・ログは非公開**になる。
  なおワークフローが public リポジトリで実行された場合に備えて、体重などの数値と
  認証情報のログマスクは維持している
- 同期履歴 DB もキャッシュで持ち回る。キャッシュが消えると同じデータを再送し、
  Google Health に同じ計測が二重に記録されることがある
- private リポジトリの Actions は無料枠（個人アカウントは月 2,000 分）を消費するが、
  この同期は1回数分・1日1回のため十分収まる
- GitHub の仕様上、**リポジトリに60日間コミット等の操作がないと定期実行（schedule）が
  自動的に無効化される**。実行用 private リポジトリはコミットがほぼ発生しないため、
  雛形ワークフロー（`examples/sync-caller.yml`）には実行のたびに停止タイマーを
  リセットするキープアライブを組み込んである

### Fitbit Web API からの移行

レガシー Fitbit Web API は 2026-09-30 にサポートを終え、2026-11-02 に停止する
（[移行ガイド](https://developers.google.com/health/migration)）。
Fitbit のトークンは Google Health API に引き継げないため、以前から使っている場合は次の手順で移行する。

1. 上記「Google Health API」の手順で OAuth クライアントを作り、`config.yaml` の `fitbit` を `google_health` に置き換える
2. `uv run python main.py auth google-health` で認証する
3. `./scripts/setup_github_secrets.sh --repo <owner>/healthcare-api-sync-runner` で Secrets を登録し直す。
   private リポジトリの `.github/workflows/sync.yml` は、`examples/sync-caller.yml` に合わせて
   `FITBIT_TOKEN_JSON` を `GOOGLE_HEALTH_TOKEN_JSON` に書き換える
4. 不要になった Secret `FITBIT_TOKEN_JSON` を削除する

Fitbit 経由で同期済みの日は、同期履歴 DB の記録から同期済みとして扱い、再送しない。

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
│   │   ├── google_health_auth.py # Google OAuth 2.0 + PKCE
│   │   └── healthplanet_auth.py  # HealthPlanet OAuth 2.0
│   ├── clients/
│   │   ├── google_health_client.py # Google Health API クライアント
│   │   └── healthplanet_client.py  # HealthPlanet API クライアント
│   ├── config.py   # 設定管理
│   ├── storage.py  # SQLite による二重書き込み防止
│   └── sync.py     # 同期ロジック
├── main.py          # CLI エントリポイント
├── pyproject.toml   # uv プロジェクト設定・依存関係定義
└── uv.lock          # 依存関係のロックファイル
```
