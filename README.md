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

## Androidスマホからの実行

[Termux](https://termux.dev/) を使うことで、Android スマホ上で Python を動かして自動実行できます。

### 必要なアプリ（F-Droid からインストール）

> **注意:** Google Play 版の Termux は長期間更新されておらず、Termux:Boot との互換性がありません。  
> 必ず [F-Droid](https://f-droid.org/) からインストールしてください。

| アプリ | 用途 |
|---|---|
| [Termux](https://f-droid.org/packages/com.termux/) | Linux 端末エミュレータ（必須） |
| [Termux:Boot](https://f-droid.org/packages/com.termux.boot/) | 端末再起動時に crond を自動起動（必須） |
| [Termux:Widget](https://f-droid.org/packages/com.termux.widget/) | ホーム画面ウィジェットから手動実行（任意） |
| [Termux:API](https://f-droid.org/packages/com.termux.api/) | 同期完了をトースト通知で受け取る（任意） |

### セットアップ手順

#### 1. リポジトリを clone

```bash
git clone https://github.com/elixir-sh/healthcare-api-sync.git
cd healthcare-api-sync
```

#### 2. セットアップスクリプトを実行

```bash
bash setup_termux.sh
```

以下が自動で設定されます。

- 必要パッケージのインストール（Python・cronie）
- 毎日 12 時に自動同期する cron ジョブの登録
- 端末起動時に crond を自動起動する Termux:Boot スクリプトの配置
- Termux:Widget 用ショートカットの配置（`~/.shortcuts/HealthSync`）

#### 3. 認証する

PC で認証済みのトークンを Termux に転送するか、Termux 上で直接認証します。

```bash
python main.py auth fitbit        # ブラウザが開く → Fitbit でログイン・許可
python main.py auth healthplanet  # URL をコピーして貼り付け → HealthPlanet 認証
```

> **HealthPlanet の認証について**  
> HealthPlanet はコールバック URL を受け付けないため、スマホ上での認証は操作が煩雑です。  
> PC 上で認証してから `config/tokens/` のファイルを Termux に転送する方が楽です。

#### 4. 動作確認

```bash
bash scripts/termux_sync.sh
```

ログは `~/logs/healthcare_sync.log` に記録されます。

#### 5. （オプション）ホーム画面から手動実行

Termux:Widget をインストールしてホーム画面にウィジェットを追加すると、  
**HealthSync** ショートカットが表示されワンタップで同期を実行できます。

## 注意事項

### Fitbit Web API の廃止について

Fitbit レガシー Web API は **2026年9月に廃止予定**。  
移行先は [Google Health API](https://developers.google.com/health/migration)。  
廃止後は `src/clients/fitbit_client.py` を差し替えることで対応できる設計にしている。

## ファイル構成

```
healthcare-api-sync/
├── config/
│   ├── config.yaml          # 設定ファイル（git 管理外）
│   ├── config.yaml.example  # 設定ファイルのテンプレート
│   └── tokens/              # 認証トークン保存先（git 管理外）
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
├── scripts/
│   └── termux_sync.sh  # Termux 用同期ラッパー（cron・Widget から呼ばれる）
├── setup_termux.sh  # Termux 環境セットアップスクリプト
├── main.py          # CLI エントリポイント
├── pyproject.toml   # uv プロジェクト設定・依存関係定義
└── uv.lock          # 依存関係のロックファイル
```
