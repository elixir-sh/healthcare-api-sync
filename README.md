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

- Python 3.10 以上
- 各サービスのアカウント
  - [Fitbit](https://www.fitbit.com/)
  - [HealthPlanet（タニタ）](https://www.healthplanet.jp/)

## セットアップ

### 1. 依存パッケージのインストール

```bash
python3 -m pip install -r requirements.txt
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
python3 main.py auth fitbit        # ブラウザが開く → Fitbit でログイン・許可
python3 main.py auth healthplanet  # ブラウザが開く → HealthPlanet でログイン・許可
```

> **HealthPlanet 認証の手順**  
> HealthPlanet は外部コールバック URL を受け付けないため、認証後に表示される  
> `https://www.healthplanet.jp/success.html?code=...` の URL をコピーして  
> ターミナルのエディタにペーストする方式を採用しています。

認証トークンは `config/tokens/` にローカル保存される（git 管理外）。

## 使い方

```bash
# 直近7日分を同期（デフォルト）
python3 main.py sync

# 特定の日付を同期
python3 main.py sync --date 2026-04-24

# 直近30日分を同期
python3 main.py sync --days 30

# 実際には書き込まず、同期済み/未同期を確認する
python3 main.py sync --dry-run
```

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
├── main.py          # CLI エントリポイント
└── requirements.txt
```
