# デプロイ手順

このドキュメントでは、SEO Drafter GCP システムの完全なデプロイ手順を説明します。

## 前提条件

- Google Cloud SDK (`gcloud`) がインストールされていること
- Docker がインストールされていること
- Terraform がインストールされていること (v1.5以上)
- GCPプロジェクトへの適切な権限があること

## プロジェクト情報

- **プロジェクトID**: `seo-drafter-gcp`
- **プロジェクト番号**: `468719745959`
- **リージョン**: `asia-northeast1`

## Step 1: 初期セットアップ

### 1.1 GCP APIとサービスアカウントの設定

```bash
# スクリプトを実行してGCPリソースを初期化
./scripts/setup-gcp.sh
```

このスクリプトは以下を実行します:
- 必要なGCP APIの有効化
- サービスアカウントの作成
- IAM権限の付与
- GCSバケットの作成
- Firestoreデータベースの作成
- BigQueryデータセットの作成
- Pub/Subトピックの作成
- Cloud Tasksキューの作成
- Artifact Registryリポジトリの作成

### 1.2 Terraformでインフラをプロビジョニング

```bash
cd terraform

# Terraformを初期化
terraform init

# 実行計画を確認
terraform plan

# インフラをデプロイ
terraform apply
```

Terraformは以下をデプロイします:
- BigQueryテーブル (article_embeddings, articles)
- Cloud Workflows定義
- Pub/Subトピック
- Cloud Tasksキュー
- サービスアカウントとIAMバインディング

## Step 2: BigQuery Embedding Modelの作成

```bash
# BigQueryで埋め込みモデルを作成
bq query --use_legacy_sql=false '
CREATE OR REPLACE MODEL `seo-drafter-gcp.seo_drafter.embedding_model`
OPTIONS(
  model_type="CLOUD_AI_TEXT_EMBEDDING_MODEL_V1",
  endpoint="textembedding-gecko@003"
);
'
```

## Step 3: 環境変数の設定

各サービスの `.env.example` をコピーして `.env` を作成し、必要に応じて編集します:

```bash
# Backend
cp backend/.env.example backend/.env

# Worker
cp worker/.env.example worker/.env

# UI
cp ui/.env.example ui/.env
```

## Step 4: サービスのデプロイ

### 4.1 全サービスを一括デプロイ

```bash
./scripts/deploy.sh
```

### 4.2 個別サービスのデプロイ

```bash
# Backendのみ
./scripts/deploy.sh --services backend

# Workerのみ
./scripts/deploy.sh --services worker

# UIのみ
./scripts/deploy.sh --services ui

# ビルドをスキップして既存イメージでデプロイ
./scripts/deploy.sh --skip-build
```

## Step 5: Cloud Workflowsの環境変数更新

デプロイ後、Cloud WorkflowsにWorkerとBackendのURLを設定します:

```bash
# デプロイされたサービスのURLを取得
WORKER_URL=$(gcloud run services describe seo-drafter-worker --region=asia-northeast1 --format='value(status.url)')
BACKEND_URL=$(gcloud run services describe seo-drafter-api --region=asia-northeast1 --format='value(status.url)')

# Workflowsを再デプロイ (環境変数を設定)
gcloud workflows deploy draft-generation \
  --source=workflows/draft_generation.yaml \
  --location=asia-northeast1 \
  --service-account=seo-drafter-workflow@seo-drafter-gcp.iam.gserviceaccount.com
```

## Step 6: 動作確認

### 6.1 ヘルスチェック

```bash
# Backend API
curl https://seo-drafter-api-XXX.run.app/healthz

# Worker
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  https://seo-drafter-worker-XXX.run.app/healthz
```

### 6.2 統合テスト

```bash
# Backend テスト
cd backend
pip install -r requirements.txt
pytest tests/

# Worker テスト
cd worker
pip install -r requirements.txt
pytest tests/
```

### 6.3 エンドツーエンドテスト

```bash
# ジョブ作成
BACKEND_URL="https://seo-drafter-api-XXX.run.app"

curl -X POST "$BACKEND_URL/api/jobs" \
  -H "Content-Type: application/json" \
  -d '{
    "primary_keyword": "SEO対策",
    "supporting_keywords": ["コンテンツ", "戦略"],
    "intent": "information",
    "word_count_range": [1000, 2000]
  }'
```

## トラブルシューティング

### サービスアカウント権限エラー

```bash
# サービスアカウントに追加の権限を付与
gcloud projects add-iam-policy-binding seo-drafter-gcp \
  --member="serviceAccount:seo-drafter-api@seo-drafter-gcp.iam.gserviceaccount.com" \
  --role="roles/ROLE_NAME"
```

### Cloud Run デプロイエラー

```bash
# ログを確認
gcloud run services logs read seo-drafter-api --region=asia-northeast1 --limit=50
```

### BigQuery Vector Search エラー

```bash
# データセットとテーブルの確認
bq ls seo_drafter
bq show seo_drafter.article_embeddings
```

## ローカル開発

### Backend API

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
```

### Worker

```bash
cd worker
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8090
```

### UI

```bash
cd ui
npm install
npm run dev
```

## 継続的デプロイ (CI/CD)

Cloud Buildを使用した自動デプロイの設定:

```bash
# Cloud Build トリガーを作成
gcloud builds triggers create github \
  --repo-name=seo-drafter-gcp \
  --repo-owner=YOUR_ORG \
  --branch-pattern="^main$" \
  --build-config=cloudbuild.yaml
```

## コスト最適化

- Cloud Runの最小インスタンス数を0に設定 (デフォルト)
- GCSライフサイクルポリシーで古いドラフトを自動削除 (90日)
- BigQueryのパーティショニングとクラスタリングを活用
- Vertex AI呼び出しのキャッシュを実装

## セキュリティ

- Cloud Runサービスは認証必須 (UIとAPI以外)
- サービスアカウントは最小権限の原則に従う
- Secret Managerでシークレットを管理
- VPC Service Controlsでデータ保護 (オプション)

## モニタリング

```bash
# Cloud Monitoringダッシュボード作成
# Cloud Error Reportingで自動エラー検出
# Cloud Loggingでログ集約
```

アラートの設定:
- Cloud Runのエラー率が5%を超えた場合
- BigQueryクエリのレイテンシが10秒を超えた場合
- Vertex AI API呼び出しの失敗率が高い場合

## 次のステップ

1. カスタムドメインの設定
2. CDNの有効化 (Cloud CDN)
3. WAFの設定 (Cloud Armor)
4. 自動スケーリングポリシーの調整
5. バックアップとディザスタリカバリの設定
