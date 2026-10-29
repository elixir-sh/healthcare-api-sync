# プライバシーポリシー

healthcare-api-sync は、利用者が自分の環境（PC または自分の GitHub リポジトリの Actions）で動かす個人用の同期ツールである。開発者が運営するサーバーはなく、開発者が利用者のデータを受け取ることはない。

## 扱うデータ

ツールはタニタ HealthPlanet から体重と体脂肪率を読み取り、利用者の Google アカウントの Google Health に書き込む。Google Health に対して要求する権限は、体組成データの書き込み専用スコープ（`googlehealth.health_metrics_and_measurements.writeonly`）だけである。Google Health のデータを読み取ることはない。

## データの保存場所

認証トークンと同期履歴は、利用者の PC の `config/` 配下に保存される。GitHub Actions で動かす場合は、利用者の private リポジトリの Secrets と、暗号化した Actions キャッシュに保存される。どちらも利用者自身が管理する場所であり、第三者には送信しない。

## Google ユーザーデータの取り扱い

Google API から受け取った情報の利用と他のアプリへの転送は、[Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy) の Limited Use 要件を含む規定に従う。

## アクセス権の取り消し

[Google アカウントのサードパーティ接続](https://myaccount.google.com/connections) から、このツールへのアクセス権をいつでも取り消せる。取り消した後は、`config/tokens/` と Actions の Secrets に残ったトークンを削除する。

## 連絡先

問い合わせは [GitHub Issues](https://github.com/elixir-sh/healthcare-api-sync/issues) で受け付ける。
