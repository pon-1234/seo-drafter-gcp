# SEO Drafter GCP

Google Cloud を用いて SEO 記事の調査〜構成〜草案生成を自動化する MVP の実装スケルトン。Cloud Run (UI/API/Worker)・Cloud Workflows・Firestore・Cloud Storage・BigQuery・OpenAI を中心に構成しています。

## モノレポ構成

```
backend/   # Cloud Run (FastAPI) - API / 内部エンドポイント / Firestore + GCS 連携
worker/    # Cloud Run (FastAPI) - Draft パイプライン処理 / PubSub トリガ
ui/        # Cloud Run (Next.js) - Brief 入力・プロンプト管理・ペルソナ・プレビュー UI
workflows/ # Cloud Workflows 定義 (ドラフト生成パイプライン)
shared/    # 共有ユーティリティ配置予定
```

## バックエンド (FastAPI)
- `POST /api/jobs` で UI からジョブを作成し、Cloud Workflows の実行をトリガー。
- `POST /api/prompts` / `GET /api/prompts/{id}` でテンプレートをバージョン管理。
- `POST /api/persona/derive` で OpenAI を経由したペルソナ自動生成。
- `POST /internal/drafts` は Workflow → Worker → API の内部連携用エンドポイント。生成物を GCS に保存し、品質判定を実施し、Firestore のステータスを更新。
- `GET /api/drafts/{id}`, `POST /api/drafts/{id}/approve` で UI からプレビュー/承認操作。

GCP ライブラリが利用できないローカル環境ではインメモリ実装にフォールバックするため、`GCP_PROJECT` や `DRAFTS_BUCKET` を未設定でも動作します。

### 起動

```
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
```

## Worker (Draft Generation Pipeline)
- `POST /run-pipeline` で Cloud Workflows から呼び出される想定。
- 意図推定 → アウトライン生成 → 本文ドラフト生成 → FAQ/Meta/リンク案 → 品質評価までをシングルプロセスで実行する雛形を実装。
- 将来的には各ステップを Cloud Tasks 分割し、BigQuery Vector Search / 外部検索連携を組み込みます。

### 起動

```
cd worker
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8090
```

## UI (Next.js)
- Brief 入力フォーム・プロンプト管理・ペルソナ編集・生成プレビュー・品質チェックページを実装済み。
- `NEXT_PUBLIC_API_BASE_URL` でバックエンド URL を指定。

```
cd ui
npm install
npm run dev
```

## Cloud Workflows
`workflows/draft_generation.yaml` は Cloud Workflows から Worker → Backend を直列で呼び出す最小構成。OIDC 認証で Cloud Run サービスを保護することを想定。

## デプロイ

### クイックスタート

```bash
# 1. 初期セットアップ (API有効化、サービスアカウント作成など)
./scripts/setup-gcp.sh

# 2. Terraformでインフラをプロビジョニング
cd terraform
terraform init
terraform apply

# 3. サービスをデプロイ
cd ..
./scripts/deploy.sh
```

詳細なデプロイ手順は [DEPLOYMENT.md](./DEPLOYMENT.md) を参照してください。

### 個別デプロイ

```bash
# Backendのみ
./scripts/deploy.sh --services backend

# Workerのみ
./scripts/deploy.sh --services worker

# UIのみ
./scripts/deploy.sh --services ui
```

## Firestore ドキュメント例

```
projects/{pid}/jobs/{jobId}
projects/{pid}/prompts/{promptId}
projects/{pid}/drafts/{draftId}
```

- `job` ドキュメントには `status`, `prompt_version`, `workflow_execution_id`, `seed` を保存。
- `prompt` ドキュメントは `versions.{version}` に System/Developer/User をフラットに保存。
- `draft` ドキュメントは GCS パス・品質指標・監査ログ ID を保持。

## 実装済み機能

### OpenAI ドラフト生成
- `backend/app/services/openai_gateway.py` / `worker/app/services/openai_gateway.py` で OpenAI のチャット補完 API を利用
- `worker/app/tasks/pipeline.py` は Grounding 風のプロンプト設計と後処理で引用情報を抽出

### BigQuery Vector Search
- `backend/app/services/bigquery.py` で記事の埋め込みベクトル検索
- 内部リンク候補の自動提案機能
- UIプレビューページで内部リンク候補を表示

### Infrastructure as Code
- Terraform による GCS、BigQuery、Pub/Sub、Cloud Tasks、Cloud Workflows の管理
- サービスアカウントと IAM 権限の自動設定
- `terraform/` ディレクトリに完全な IaC 定義

### テスト
- Backend API の統合テスト (`backend/tests/test_api_integration.py`)
- BigQuery サービスの単体テスト (`backend/tests/test_bigquery.py`)
- Worker パイプラインのエンドツーエンドテスト (`worker/tests/test_pipeline.py`)

## 今後の拡張ポイント
- Cloud Tasks / PubSub を用いた段階的リトライ機能の実装
- Secret Manager で API キーやスタイルガイド辞書を安全に管理
- Cloud Monitoring / Error Reporting のアラート設定
- CI/CD パイプラインの構築 (Cloud Build)
- カスタムドメインと CDN の設定

## 開発メモ
- FastAPI / Next.js / Worker いずれもローカル動作時はダミークライアントで代替し、GCP SDK が未インストールでも破綻しないよう調整。
- JSON 出力の一貫性を確保するため `Default Prompt Version` と `seed` を env で固定。
- YMYL 自動判定や要出典タグは `worker/app/tasks/pipeline.py` → `QualityEngine` の流れでマーキング。
