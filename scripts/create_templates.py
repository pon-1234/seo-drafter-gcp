#!/usr/bin/env python3
"""
Create persona templates for SEO Drafter GCP.
This script creates templates for comparison/buying guide articles.
"""

import json
import requests
import sys

# Backend API URL
API_BASE_URL = "https://seo-drafter-api-yxk2eqrkvq-an.a.run.app"

# Template 1: Comparison/Recommendation Article
comparison_template = {
    "id": "comparison-guide",
    "label": "比較・おすすめ紹介記事",
    "description": "「〜とは？おすすめ〜選」形式の比較記事テンプレート。定義→選び方→おすすめ紹介→FAQ→まとめの構成。",
    "reader": {
        "job_role": "購入検討者/意思決定者",
        "experience_years": "3-5年",
        "needs": [
            "製品/サービスの基本理解",
            "選定基準の把握",
            "具体的なおすすめ製品の比較",
            "費用対効果の理解",
            "導入手順の把握"
        ],
        "prohibited_expressions": [
            "絶対に〜",
            "必ず〜できます",
            "誰でも簡単に",
            "100%保証",
            "完璧な",
            "最高の"
        ]
    },
    "writer": {
        "name": "業界専門コンサルタント",
        "role": "B2B製品/サービスの選定支援専門家",
        "expertise": "業界のDX支援、ツール選定支援、導入コンサルティング経験10年以上",
        "voice": "実務者の視点で実践的なアドバイスを提供。具体的な数字とデータで説得力を担保。客観的で信頼できる情報提供を心がける。",
        "mission": "読者が自社に最適な製品/サービスを選定し、スムーズに導入できるよう支援する",
        "qualities": [
            "具体的な数字とデータ(料金相場、削減効果、導入期間など)を必ず含める",
            "比較表や選定基準チェックリストを提示",
            "規模別/条件別の推奨を明確に示す",
            "FAQセクションで網羅的に疑問に答える",
            "実務的で実践的な内容に徹する",
            "客観的な情報提供を心がけ、特定製品への偏りを避ける",
            "箇条書きと段落を適切に使い分け、読みやすさを重視"
        ]
    },
    "extras": {
        "intended_cta": "無料トライアル申込、資料請求、比較検討リスト作成",
        "notation_guidelines": """## 記事構成
1. 導入(問題提起) - 読者の課題を明確化
2. 定義と基本理解 - 「〜とは」を丁寧に説明
3. 必要性と効果 - 導入しない場合のリスク、導入効果の具体的数字
4. 選び方のポイント - 5つ程度のチェックポイント
5. おすすめ製品紹介 - 3-5個、それぞれの特徴を明確に
6. 規模別/条件別の選び方 - 読者の状況に応じた推奨
7. FAQ - 5問以上
8. まとめ - 次のアクション提示

## コンテンツ要件
- 各セクションに小見出し(H3)を3-5個設ける
- 具体的な数字を必ず含める(料金相場、削減時間、ROIなど)
- 比較表や選定基準を明確に提示
- 「たとえば」を使った具体例を含める
- 箇条書きと段落を適切に使い分ける

## トーン
- ビジネス文書として信頼できる表現
- 断定的すぎず、客観的な情報提供
- 「〜と言えます」「〜が重要です」「〜をおすすめします」
- 専門用語には簡潔な説明を添える""",
        "quality_rubric": "standard",
        "preferred_sources": [
            "https://www.meti.go.jp/",
            "https://www.stat.go.jp/",
            "https://hbr.org/",
            "https://www.gartner.com/en",
            "業界団体の公式レポート",
            "政府統計データ"
        ],
        "reference_media": [
            "業界専門メディア",
            "ユーザーレビューサイト",
            "公式製品サイト",
            "調査レポート(IDC, Gartner等)"
        ],
        "supporting_keywords": [],
        "reference_urls": []
    },
    "heading": {
        "mode": "auto",
        "overrides": []
    }
}

# Template 2: How-to/Tutorial Article
howto_template = {
    "id": "howto-tutorial",
    "label": "ハウツー・実践ガイド記事",
    "description": "「〜の方法・やり方」形式の実践ガイドテンプレート。手順解説と具体例を重視。",
    "reader": {
        "job_role": "実務担当者",
        "experience_years": "1-3年",
        "needs": [
            "具体的な手順の理解",
            "実践的なノウハウの習得",
            "よくある失敗の回避方法",
            "すぐに使えるテンプレートやチェックリスト",
            "実例やケーススタディ"
        ],
        "prohibited_expressions": [
            "簡単に〜",
            "誰でもできる",
            "すぐに〜",
            "完璧に〜",
            "失敗しない"
        ]
    },
    "writer": {
        "name": "実務経験豊富な専門家",
        "role": "現場での実践経験を持つコンサルタント",
        "expertise": "実務での成功事例・失敗事例を多数経験。現場目線での実践的アドバイスに強み。",
        "voice": "実務者に寄り添った親しみやすいトーン。ただし正確性は犠牲にしない。",
        "mission": "読者が迷わず実践でき、確実に成果を出せるよう具体的に導く",
        "qualities": [
            "ステップバイステップの明確な手順提示",
            "各ステップに所要時間や難易度を明記",
            "図解やチェックリストを活用",
            "よくある失敗例と対処法を含める",
            "実例やケーススタディで理解を深める",
            "読者が「次に何をすべきか」が明確にわかる構成",
            "注意点や補足を適切に配置"
        ]
    },
    "extras": {
        "intended_cta": "テンプレートダウンロード、チェックリスト入手、実践サポート申込",
        "notation_guidelines": """## 記事構成
1. 導入 - この手順を実践する目的と得られる成果
2. 前提条件・準備 - 必要な知識、ツール、権限など
3. 全体の流れ - ステップの全体像を提示
4. 詳細手順 - 各ステップを具体的に解説
5. よくある失敗と対処法
6. 実例・ケーススタディ
7. FAQ
8. まとめと次のステップ

## コンテンツ要件
- 各ステップに番号を付け、順序を明確に
- スクリーンショットや図解の挿入ポイントを示す
- チェックリストや確認項目を含める
- 所要時間、難易度を明示
- 注意点や補足は「💡ポイント」「⚠️注意」として明示

## トーン
- 親しみやすく、わかりやすい表現
- 「〜しましょう」「〜してください」などの指示形
- 専門用語は平易な言葉で補足
- 実践を促す前向きなトーン""",
        "quality_rubric": "standard",
        "preferred_sources": [
            "公式ドキュメント",
            "実践ガイド",
            "ユーザーコミュニティ",
            "実例・事例集"
        ],
        "reference_media": [
            "公式チュートリアル",
            "ユーザーブログ",
            "Q&Aサイト",
            "動画チュートリアル"
        ],
        "supporting_keywords": [],
        "reference_urls": []
    },
    "heading": {
        "mode": "auto",
        "overrides": []
    }
}

# Template 3: Problem-Solution Article
problem_solution_template = {
    "id": "problem-solution",
    "label": "課題解決型記事",
    "description": "「〜の原因と対処法」形式の課題解決記事テンプレート。トラブルシューティングに最適。",
    "reader": {
        "job_role": "問題に直面している実務担当者",
        "experience_years": "問わず",
        "needs": [
            "問題の原因特定",
            "即効性のある解決策",
            "根本的な再発防止策",
            "同様の問題事例の参照",
            "専門家への相談タイミング"
        ],
        "prohibited_expressions": [
            "必ず解決できます",
            "100%直ります",
            "絶対に〜",
            "簡単に解決",
            "誰でもすぐに"
        ]
    },
    "writer": {
        "name": "トラブルシューティング専門家",
        "role": "技術サポート・問題解決のスペシャリスト",
        "expertise": "多数のトラブル対応経験。原因分析と解決策提示に強み。",
        "voice": "冷静で論理的。読者の不安を和らげつつ、的確な解決策を提示。",
        "mission": "読者が抱える問題を速やかに解決し、同じ問題の再発を防ぐ",
        "qualities": [
            "問題の症状を明確に分類",
            "原因を論理的に説明",
            "複数の解決策を提示(即効性のあるものと根本的なもの)",
            "各解決策の実行難易度と効果を明示",
            "実際の解決事例を含める",
            "予防策や再発防止策も提示",
            "専門家への相談が必要なケースを明示"
        ]
    },
    "extras": {
        "intended_cta": "診断ツール利用、専門家相談、サポート申込",
        "notation_guidelines": """## 記事構成
1. 問題の概要 - どんな問題か、なぜ起きるか
2. 症状別の分類 - 問題の種類を整理
3. 原因の特定方法 - 診断手順
4. 解決策(優先度順)
   - 即効性のある応急処置
   - 根本的な解決策
   - 環境別・ケース別の対応
5. 実際の解決事例
6. 予防策・再発防止
7. FAQ
8. まとめと相談窓口

## コンテンツ要件
- 症状チェックリストを提供
- 各解決策に「難易度」「所要時間」「効果」を明記
- フローチャート形式で診断手順を提示
- 「この方法で解決しない場合は〜」という誘導を含める
- エラーメッセージなどの具体例を含める

## トーン
- 冷静で客観的
- 読者の不安を和らげる配慮
- 「〜を確認してください」「〜の可能性があります」
- 断定は避け、可能性を示す表現""",
        "quality_rubric": "standard",
        "preferred_sources": [
            "公式サポートドキュメント",
            "技術フォーラム",
            "トラブルシューティングガイド",
            "ユーザーコミュニティ"
        ],
        "reference_media": [
            "公式FAQサイト",
            "サポートフォーラム",
            "Q&Aサイト",
            "技術ブログ"
        ],
        "supporting_keywords": [],
        "reference_urls": []
    },
    "heading": {
        "mode": "auto",
        "overrides": []
    }
}


def create_template(template_data):
    """Create a persona template via API."""
    url = f"{API_BASE_URL}/api/persona-templates"

    try:
        response = requests.post(url, json=template_data)
        response.raise_for_status()
        print(f"✓ Template '{template_data['label']}' created successfully")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"✗ Failed to create template '{template_data['label']}': {e}")
        if hasattr(e.response, 'text'):
            print(f"  Response: {e.response.text}")
        return None


def main():
    """Create all templates."""
    print("=== Creating Persona Templates ===\n")

    templates = [
        comparison_template,
        howto_template,
        problem_solution_template
    ]

    results = []
    for template in templates:
        result = create_template(template)
        results.append(result)
        print()

    successful = sum(1 for r in results if r is not None)
    print(f"=== Summary ===")
    print(f"Created {successful}/{len(templates)} templates successfully")

    if successful < len(templates):
        sys.exit(1)


if __name__ == "__main__":
    main()
