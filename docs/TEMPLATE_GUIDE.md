# テンプレート使用ガイド

SEO Drafter GCP で高品質な記事を生成するためのテンプレートガイドです。

## 登録済みテンプレート

### 1. 比較・おすすめ紹介記事 (`comparison-guide`)

**適した記事タイプ:**
- 「〜とは？おすすめ〜選」形式
- 製品/サービスの比較記事
- 選び方ガイド + 具体的な推奨

**記事構成:**
1. 導入(問題提起)
2. 定義と基本理解
3. 必要性と効果
4. 選び方のポイント(5つ程度)
5. おすすめ製品紹介(3-5個)
6. 規模別/条件別の選び方
7. FAQ(5問以上)
8. まとめ

**特徴:**
- 具体的な数字とデータ(料金相場、削減効果など)を含む
- 比較表や選定基準チェックリストを提示
- 規模別/条件別の推奨を明確に示す
- 客観的で信頼できる情報提供

**使用例:**
```
主キーワード: サイトコントローラーとは
専門性レベル: intermediate
トーン: formal
プロジェクトテンプレート: comparison-guide
```

---

### 2. ハウツー・実践ガイド記事 (`howto-tutorial`)

**適した記事タイプ:**
- 「〜の方法・やり方」形式
- 手順解説記事
- チュートリアル

**記事構成:**
1. 導入(目的と成果)
2. 前提条件・準備
3. 全体の流れ
4. 詳細手順(ステップバイステップ)
5. よくある失敗と対処法
6. 実例・ケーススタディ
7. FAQ
8. まとめと次のステップ

**特徴:**
- ステップバイステップの明確な手順
- 各ステップに所要時間や難易度を明記
- チェックリストや確認項目を含む
- よくある失敗例と対処法を提示
- 実践を促す前向きなトーン

**使用例:**
```
主キーワード: Googleアナリティクス 設定方法
専門性レベル: beginner
トーン: casual
プロジェクトテンプレート: howto-tutorial
```

---

### 3. 課題解決型記事 (`problem-solution`)

**適した記事タイプ:**
- 「〜の原因と対処法」形式
- トラブルシューティング記事
- 問題解決ガイド

**記事構成:**
1. 問題の概要
2. 症状別の分類
3. 原因の特定方法
4. 解決策(優先度順)
   - 即効性のある応急処置
   - 根本的な解決策
   - 環境別・ケース別の対応
5. 実際の解決事例
6. 予防策・再発防止
7. FAQ
8. まとめと相談窓口

**特徴:**
- 症状チェックリストを提供
- 各解決策に「難易度」「所要時間」「効果」を明記
- フローチャート形式で診断手順を提示
- 冷静で論理的なトーン
- 読者の不安を和らげる配慮

**使用例:**
```
主キーワード: サイト 表示速度 遅い 原因
専門性レベル: intermediate
トーン: formal
プロジェクトテンプレート: problem-solution
```

---

## UI での使い方

### Brief 入力ページで使用する場合

1. **基本設定**
   - 主キーワード: 記事のメインキーワードを入力
   - 記事タイプ: information / comparison / ranking から選択
   - 専門性レベル: beginner / intermediate / expert から選択
   - トーン: casual / formal から選択

2. **テンプレート選択**
   - 「プロジェクトテンプレート」ドロップダウンから適切なテンプレートを選択
   - テンプレートを選択すると、Reader/Writer Persona、Notation Guidelines が自動設定されます

3. **追加のカスタマイズ(任意)**
   - 参考URL: 特定のサイトを参考にしたい場合に追加
   - 禁則表現: テンプレートのデフォルトに加えて追加したい場合

### Persona Studio ページで確認・編集する場合

1. https://seo-drafter-ui-yxk2eqrkvq-an.a.run.app/persona/templates にアクセス
2. 登録済みテンプレート一覧が表示されます
3. 各テンプレートの詳細確認、編集、削除が可能です

---

## テンプレートのカスタマイズ

既存のテンプレートをベースに、独自のテンプレートを作成できます。

### API経由でのテンプレート作成

```bash
curl -X POST https://seo-drafter-api-yxk2eqrkvq-an.a.run.app/api/persona/templates \
  -H "Content-Type: application/json" \
  -d @your-template.json
```

### テンプレートJSON構造

```json
{
  "id": "your-template-id",
  "label": "テンプレート表示名",
  "description": "テンプレートの説明",
  "reader": {
    "job_role": "読者の職種",
    "experience_years": "経験年数",
    "needs": ["ニーズ1", "ニーズ2"],
    "prohibited_expressions": ["禁則表現1", "禁則表現2"]
  },
  "writer": {
    "name": "ライター名",
    "role": "役割",
    "expertise": "専門性の説明",
    "voice": "文体・トーンの説明",
    "mission": "ミッション",
    "qualities": ["特性1", "特性2"]
  },
  "extras": {
    "intended_cta": "想定CTA",
    "notation_guidelines": "記事構成とコンテンツ要件の詳細",
    "quality_rubric": "standard",
    "preferred_sources": ["推奨情報源1", "推奨情報源2"],
    "reference_media": ["参考メディア1", "参考メディア2"],
    "supporting_keywords": [],
    "reference_urls": []
  },
  "heading": {
    "mode": "auto",
    "overrides": []
  }
}
```

---

## ベストプラクティス

### 1. テンプレート選択のポイント

- **比較・おすすめ紹介記事**: 製品選定を支援する記事に最適。複数の選択肢を提示し、読者の状況に応じた推奨を示す。
- **ハウツー・実践ガイド記事**: 具体的な手順を教える記事に最適。読者が実践できるよう明確な手順を提示。
- **課題解決型記事**: トラブルや問題に対処する記事に最適。原因分析と解決策を論理的に提示。

### 2. 専門性レベルとトーンの組み合わせ

| 専門性 | トーン | 適した記事例 |
|---|---|---|
| beginner | casual | 初心者向けハウツー記事 |
| beginner | formal | 初心者向けビジネスガイド |
| intermediate | formal | **比較・選び方記事(推奨)** |
| expert | formal | 専門家向け技術解説 |

### 3. 高品質な記事を生成するコツ

1. **テンプレートは出発点**: テンプレートをベースに、必要に応じてカスタマイズ
2. **参考URLを追加**: 具体的な製品や事例を参照したい場合は参考URLを指定
3. **禁則表現を調整**: 業界や記事の性質に応じて禁則表現を追加
4. **Writer Persona の調整**: 特定のトーンや視点が必要な場合は Writer Persona をカスタマイズ

---

## トラブルシューティング

### 記事の品質が期待と異なる場合

1. **専門性レベルを調整**: beginner → intermediate または intermediate → expert
2. **Notation Guidelines を確認**: テンプレートの記事構成指示を確認し、必要に応じて追加
3. **参考URLを追加**: 理想的な記事の例を参考URLとして指定

### テンプレートが見つからない場合

```bash
# テンプレート一覧を確認
curl https://seo-drafter-api-yxk2eqrkvq-an.a.run.app/api/persona/templates

# 再度テンプレートを登録
cd /path/to/seo-drafter-gcp
python3 scripts/create_templates.py
```

---

## 参考リンク

- [SEO Drafter UI](https://seo-drafter-ui-yxk2eqrkvq-an.a.run.app)
- [Brief 入力ページ](https://seo-drafter-ui-yxk2eqrkvq-an.a.run.app/brief)
- [Persona Studio](https://seo-drafter-ui-yxk2eqrkvq-an.a.run.app/persona/templates)
- [Backend API](https://seo-drafter-api-yxk2eqrkvq-an.a.run.app)
