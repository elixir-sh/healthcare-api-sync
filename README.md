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

同期は GitHub Actions 上で毎日 15:00（JST）に自動実行される。
あわせて手動実行（workflow_dispatch）にも対応しているため、PC を起動していなくても
スマホから任意のタイミングでキックできる。定期実行と手動実行は同じ concurrency
グループで直列実行されるため、実行タイミングが重なってもトークンリフレッシュが競合しない。

### 初回セットアップ（PC で1回だけ）

ローカルでのセットアップ・認証（上記）を済ませたうえで、Secrets をアップロードする。

```bash
./scripts/setup_github_secrets.sh
```

設定される Secrets:

| Secret | 内容 |
|---|---|
| `CONFIG_YAML` | `config.yaml` の内容 |
| `FITBIT_TOKEN_JSON` | Fitbit トークン（初回シード用） |
| `HEALTHPLANET_TOKEN_JSON` | HealthPlanet トークン（初回シード用） |
| `STATE_PASSPHRASE` | 状態キャッシュ暗号化用パスフレーズ（自動生成） |

### スマホからの手動キック方法

定期実行を待たずに今すぐ同期したい場合は、
[GitHub モバイルアプリ](https://github.com/mobile)またはブラウザから、以下の手順でキックする。

1. このリポジトリを開き「Actions」タブへ
2. ワークフロー「sync」を選ぶ
3. 「Run workflow」をタップ（日付・日数・ドライランを指定可能）

ブラウザの場合は Actions のページをホーム画面に追加しておくとワンタップで開ける。

### トークンと同期履歴の持ち回り

Fitbit はトークンリフレッシュのたびにリフレッシュトークンが差し替わるため、
実行後の最新トークンと同期履歴 DB を**暗号化して Actions キャッシュ**に保存し、次回実行時に復元する。

キャッシュは 7 日間使われないと消える。毎日定期実行しているため通常は失効しないが、
定期実行が止まる等でキャッシュが消えた場合は Secrets のトークンにフォールバックする。
その場合、一度でも CI で同期していると Secrets 側の Fitbit トークンは失効している
（ローテーションのため）。次のどちらかで運用する。

- **（推奨）fine-grained PAT を Secret `GH_PAT` に設定する**
  実行のたびに最新トークンが Secrets に書き戻されるため、期間が空いても自動復旧する。
  [Fine-grained tokens](https://github.com/settings/personal-access-tokens/new) で
  このリポジトリのみ・Repository permissions → **Secrets: Read and write** を付与して作成し、
  `gh secret set GH_PAT` で登録する
- PAT を設定しない場合、7 日以上間隔が空いて同期が失敗するようになったら、
  ローカルで再認証して `./scripts/setup_github_secrets.sh` を再実行する

## 注意事項

### GitHub Actions 運用時の注意

- **CI で同期を実行すると、ローカルの Fitbit トークンは失効する**（リフレッシュトークンの
  ローテーションのため）。以後ローカルでも実行したい場合は `uv run python main.py auth fitbit`
  で再認証する。CI とローカルの常時併用は想定せず、どちらか一方を主にする
- このリポジトリは public のため **Actions のログは誰でも見られる**。
  体重などの数値と認証情報はワークフロー側でマスクしているが、計測日などのメタ情報は
  ログに残る。気になる場合はリポジトリを private にする
- 同期履歴 DB もキャッシュで持ち回るため、キャッシュが消えると同じデータを再送する
  可能性があるが、同じ計測日時・同じ値の再送のため実害はほぼない
- public リポジトリは Actions の実行時間が無料のため、毎日の定期実行によるコストはかからない
- GitHub の仕様上、**リポジトリに60日間コミット等の操作がないと定期実行（schedule）が
  自動的に無効化される**。長期間コードを触らない場合は手動実行で代替するか、
  定期的に何らかのコミットを行う

### Fitbit Web API の廃止について

Fitbit レガシー Web API は **2026年9月に廃止予定**。  
移行先は [Google Health API](https://developers.google.com/health/migration)。  
廃止後は `src/clients/fitbit_client.py` を差し替えることで対応できる設計にしている。

## ファイル構成

```
healthcare-api-sync/
├── .github/
│   └── workflows/
│       └── sync.yml         # 毎日15時の定期実行 + 手動実行に対応した同期ワークフロー
├── config/
│   ├── config.yaml          # 設定ファイル（git 管理外）
│   ├── config.yaml.example  # 設定ファイルのテンプレート
│   └── tokens/              # 認証トークン保存先（git 管理外）
├── scripts/
│   └── setup_github_secrets.sh  # GitHub Actions 用 Secrets のアップロード
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
