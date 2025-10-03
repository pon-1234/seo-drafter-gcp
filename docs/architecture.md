# アーキテクチャ概要

## 全体像

1. **UI (Cloud Run / Next.js)**
   - Brief入力フォームで Firestore にジョブを登録（API 経由）。
   - プロンプト管理、ペルソナスタジオ、プレビュー、品質チェックを 1 UI で完結。
2. **API (Cloud Run / FastAPI)**
   - 認証された UI と Cloud Workflows の双方から利用。
   - Firestore によるジョブ・プロンプト・監査メタデータ管理。
   - DraftStorage (GCS) に生成物を保存し、QualityEngine でスタイル・根拠チェックを付与。
3. **Workflow (Cloud Workflows)**
   - `/api/jobs` → Workflow 実行 → Worker → API `/internal/drafts` の直列処理。
   - 失敗時は Cloud Tasks による遅延リトライを将来的に挿入。
4. **Worker (Cloud Run / FastAPI)**
   - Vertex AI + Google Search Grounding → Draft/FAQ/Meta/リンク案生成。
   - BigQuery Vector Search で内部リンク候補を抽出（スタブ実装）。
   - 品質信号を同梱して API に返却。

## データフロー

```mermaid
graph LR
  UI -->|POST /api/jobs| API
  API -->|ExecutionsClient| Workflow
  Workflow -->|HTTP POST| Worker
  Worker -->|結果| Workflow
  Workflow -->|POST /internal/drafts| API
  API -->|保存| GCS
  API -->|更新| Firestore
  API -->|GET /api/drafts/{id}| UI
```

## Firestore コレクション
- `jobs`: 入力パラメタとステータス、Workflow 実行 ID、seed。
- `prompts`: versioned テンプレート、System/Developer/User 区分。
- `drafts`: GCS パス、品質指標、承認履歴、監査ログ ID。

## 品質ゲート
- Worker が `claims` に citations 付き/無しをマーク。
- API の `QualityEngine` が citations 欠如フラグ・YMYL 判定を `quality.json` に保存。
- UI の `preview` / `quality` ページで重複率・要出典タグを提示。

## 監査ログ
- `POST /api/jobs` 時に使用モデル・seed・プロンプトバージョンを Firestore に保存 (スタブ)。
- Draft 承認時に `POST /api/drafts/{id}/approve` で承認ユーザーとノートを保持。

