#!/bin/bash

# Seed beginner persona templates to Firestore via API
API_URL="https://seo-drafter-api-468719745959.asia-northeast1.run.app"
TOKEN=$(gcloud auth print-identity-token | tr -d '\n')

echo "🌱 Seeding beginner persona templates..."
echo ""

# Template 1: Beginner Information
echo "📝 Creating template: beginner-information"
curl -X POST "${API_URL}/api/persona/templates" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "beginner-information",
    "label": "初心者向け「◯◯とは」記事",
    "description": "初心者が検索する「◯◯とは」クエリに最適化された入門記事テンプレート。定義、手法、メリデメ、始め方、FAQを網羅。",
    "reader": {
      "job_role": "これから学び始める初心者",
      "needs": [
        "基本の意味",
        "具体例",
        "始め方",
        "FAQ"
      ]
    },
    "writer": {
      "name": "わかりやすく教える先生",
      "voice": "やさしく・具体的・専門用語は言い換え付き"
    },
    "extras": {
      "notation_guidelines": "1文60字以内を厳守。専門用語は必ず言い換え＋例を入れる。段落は3〜4文で簡潔に。出典は各セクション末尾に1〜2本のみ。B2B専門用語は避ける。",
      "quality_rubric": "standard",
      "preferred_sources": [
        "https://www.soumu.go.jp/",
        "https://www.meti.go.jp/",
        "https://support.google.com/",
        "https://ja.wikipedia.org/"
      ],
      "reference_media": [
        "ferret（初心者向けマーケティングメディア）",
        "バズ部（SEO・コンテンツマーケティング入門）",
        "Googleアナリティクス公式ヘルプ",
        "基礎から学ぶデジタルマーケティング入門サイト"
      ]
    },
    "heading": {
      "mode": "manual",
      "overrides": [
        "30秒で要点",
        "◯◯の意味をわかりやすく解説",
        "◯◯の主な手法と役割（表で比較）",
        "◯◯のメリット・デメリット",
        "◯◯を始める5ステップ",
        "よくある失敗と対処法",
        "FAQ",
        "まとめ"
      ]
    }
  }'
echo -e "\n"

# Template 2: Beginner How-to
echo "📝 Creating template: beginner-howto"
curl -X POST "${API_URL}/api/persona/templates" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "beginner-howto",
    "label": "初心者向けハウツー記事",
    "description": "初心者向けの実践的なハウツー記事テンプレート。手順、注意点、失敗例、FAQを網羅。",
    "reader": {
      "job_role": "初めて実践する初心者",
      "needs": [
        "簡単な手順",
        "注意すべきポイント",
        "よくある失敗例",
        "すぐに使える具体例"
      ]
    },
    "writer": {
      "name": "実践サポーター",
      "voice": "親切・丁寧・手順を具体的に"
    },
    "extras": {
      "notation_guidelines": "1文60字以内を厳守。手順は番号付きリストで明確に。専門用語は必ず言い換え＋例を入れる。スクリーンショットや図解の挿入箇所を明記。出典は各セクション末尾に1〜2本のみ。",
      "quality_rubric": "standard",
      "preferred_sources": [
        "https://www.soumu.go.jp/",
        "https://www.meti.go.jp/",
        "https://support.google.com/",
        "https://ja.wikipedia.org/"
      ],
      "reference_media": [
        "ferret（初心者向けマーケティングメディア）",
        "バズ部（SEO・コンテンツマーケティング入門）",
        "Googleアナリティクス公式ヘルプ",
        "基礎から学ぶデジタルマーケティング入門サイト"
      ]
    },
    "heading": {
      "mode": "manual",
      "overrides": [
        "30秒で要点（完成イメージ）",
        "始める前に準備するもの",
        "◯◯の手順を5ステップで解説",
        "各ステップの詳細",
        "よくあるつまずきポイントと解決法",
        "FAQ",
        "まとめ（次のステップ）"
      ]
    }
  }'
echo -e "\n"

# Template 3: Beginner Comparison
echo "📝 Creating template: beginner-comparison"
curl -X POST "${API_URL}/api/persona/templates" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "beginner-comparison",
    "label": "初心者向け比較・おすすめ記事",
    "description": "初心者向けの比較・選び方記事テンプレート。比較表、選び方、おすすめランキングを網羅。",
    "reader": {
      "job_role": "選び方がわからない初心者",
      "needs": [
        "わかりやすい比較",
        "選び方のポイント",
        "おすすめランキング",
        "失敗しない選び方"
      ]
    },
    "writer": {
      "name": "選び方アドバイザー",
      "voice": "中立的・わかりやすく・具体的に"
    },
    "extras": {
      "notation_guidelines": "1文60字以内を厳守。比較表を必ず入れる。専門用語は必ず言い換え＋例を入れる。メリット・デメリットを公平に記載。出典は各セクション末尾に1〜2本のみ。",
      "quality_rubric": "standard",
      "preferred_sources": [
        "https://www.soumu.go.jp/",
        "https://www.meti.go.jp/",
        "https://support.google.com/",
        "https://ja.wikipedia.org/"
      ],
      "reference_media": [
        "ferret（初心者向けマーケティングメディア）",
        "バズ部（SEO・コンテンツマーケティング入門）",
        "Googleアナリティクス公式ヘルプ",
        "基礎から学ぶデジタルマーケティング入門サイト"
      ]
    },
    "heading": {
      "mode": "manual",
      "overrides": [
        "30秒で要点（結論：おすすめTOP3）",
        "◯◯を選ぶポイント3つ",
        "おすすめTOP5を比較（表）",
        "各ツールの詳細レビュー",
        "使う人別のおすすめ",
        "FAQ",
        "まとめ（選び方のチェックリスト）"
      ]
    }
  }'
echo -e "\n"

echo "✅ Seeding completed!"
echo "🔗 Check templates at: https://seo-drafter-ui-yxk2eqrkvq-an.a.run.app/persona/templates"
