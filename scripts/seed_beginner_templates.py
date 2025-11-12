#!/usr/bin/env python3
"""Seed beginner persona templates to Firestore."""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.services.firestore import get_firestore_repository
from app.models import PersonaTemplateCreate, ReaderPersonaTemplate, WriterPersonaTemplate, PersonaTemplateExtras, PersonaTemplateHeading, HeadingMode


def seed_beginner_templates():
    """Seed beginner persona templates."""
    store = get_firestore_repository()

    templates = [
        # 1. Beginner Information Template
        PersonaTemplateCreate(
            id="beginner-information",
            label="初心者向け「◯◯とは」記事",
            description="初心者が検索する「◯◯とは」クエリに最適化された入門記事テンプレート。定義、手法、メリデメ、始め方、FAQを網羅。",
            reader=ReaderPersonaTemplate(
                job_role="これから学び始める初心者",
                needs=[
                    "基本の意味",
                    "具体例",
                    "始め方",
                    "FAQ"
                ]
            ),
            writer=WriterPersonaTemplate(
                name="わかりやすく教える先生",
                voice="やさしく・具体的・専門用語は言い換え付き"
            ),
            extras=PersonaTemplateExtras(
                notation_guidelines="1文60字以内を厳守。専門用語は必ず言い換え＋例を入れる。段落は3〜4文で簡潔に。出典は各セクション末尾に1〜2本のみ。B2B専門用語は避ける。",
                quality_rubric="standard",
                preferred_sources=[
                    "https://www.soumu.go.jp/",
                    "https://www.meti.go.jp/",
                    "https://support.google.com/",
                    "https://ja.wikipedia.org/"
                ],
                reference_media=[
                    "ferret（初心者向けマーケティングメディア）",
                    "バズ部（SEO・コンテンツマーケティング入門）",
                    "Googleアナリティクス公式ヘルプ",
                    "基礎から学ぶデジタルマーケティング入門サイト"
                ]
            ),
            heading=PersonaTemplateHeading(
                mode=HeadingMode.manual,
                overrides=[
                    "30秒で要点",
                    "◯◯の意味をわかりやすく解説",
                    "◯◯の主な手法と役割（表で比較）",
                    "◯◯のメリット・デメリット",
                    "◯◯を始める5ステップ",
                    "よくある失敗と対処法",
                    "FAQ",
                    "まとめ"
                ]
            )
        ),

        # 2. Beginner How-to Template
        PersonaTemplateCreate(
            id="beginner-howto",
            label="初心者向けハウツー記事",
            description="初心者向けの実践的なハウツー記事テンプレート。手順、注意点、失敗例、FAQを網羅。",
            reader=ReaderPersonaTemplate(
                job_role="初めて実践する初心者",
                needs=[
                    "簡単な手順",
                    "注意すべきポイント",
                    "よくある失敗例",
                    "すぐに使える具体例"
                ]
            ),
            writer=WriterPersonaTemplate(
                name="実践サポーター",
                voice="親切・丁寧・手順を具体的に"
            ),
            extras=PersonaTemplateExtras(
                notation_guidelines="1文60字以内を厳守。手順は番号付きリストで明確に。専門用語は必ず言い換え＋例を入れる。スクリーンショットや図解の挿入箇所を明記。出典は各セクション末尾に1〜2本のみ。",
                quality_rubric="standard",
                preferred_sources=[
                    "https://www.soumu.go.jp/",
                    "https://www.meti.go.jp/",
                    "https://support.google.com/",
                    "https://ja.wikipedia.org/"
                ],
                reference_media=[
                    "ferret（初心者向けマーケティングメディア）",
                    "バズ部（SEO・コンテンツマーケティング入門）",
                    "Googleアナリティクス公式ヘルプ",
                    "基礎から学ぶデジタルマーケティング入門サイト"
                ]
            ),
            heading=PersonaTemplateHeading(
                mode=HeadingMode.manual,
                overrides=[
                    "30秒で要点（完成イメージ）",
                    "始める前に準備するもの",
                    "◯◯の手順を5ステップで解説",
                    "各ステップの詳細",
                    "よくあるつまずきポイントと解決法",
                    "FAQ",
                    "まとめ（次のステップ）"
                ]
            )
        ),

        # 3. Beginner Comparison Template
        PersonaTemplateCreate(
            id="beginner-comparison",
            label="初心者向け比較・おすすめ記事",
            description="初心者向けの比較・選び方記事テンプレート。比較表、選び方、おすすめランキングを網羅。",
            reader=ReaderPersonaTemplate(
                job_role="選び方がわからない初心者",
                needs=[
                    "わかりやすい比較",
                    "選び方のポイント",
                    "おすすめランキング",
                    "失敗しない選び方"
                ]
            ),
            writer=WriterPersonaTemplate(
                name="選び方アドバイザー",
                voice="中立的・わかりやすく・具体的に"
            ),
            extras=PersonaTemplateExtras(
                notation_guidelines="1文60字以内を厳守。比較表を必ず入れる。専門用語は必ず言い換え＋例を入れる。メリット・デメリットを公平に記載。出典は各セクション末尾に1〜2本のみ。",
                quality_rubric="standard",
                preferred_sources=[
                    "https://www.soumu.go.jp/",
                    "https://www.meti.go.jp/",
                    "https://support.google.com/",
                    "https://ja.wikipedia.org/"
                ],
                reference_media=[
                    "ferret（初心者向けマーケティングメディア）",
                    "バズ部（SEO・コンテンツマーケティング入門）",
                    "Googleアナリティクス公式ヘルプ",
                    "基礎から学ぶデジタルマーケティング入門サイト"
                ]
            ),
            heading=PersonaTemplateHeading(
                mode=HeadingMode.manual,
                overrides=[
                    "30秒で要点（結論：おすすめTOP3）",
                    "◯◯を選ぶポイント3つ",
                    "おすすめTOP5を比較（表）",
                    "各ツールの詳細レビュー",
                    "使う人別のおすすめ",
                    "FAQ",
                    "まとめ（選び方のチェックリスト）"
                ]
            )
        )
    ]

    for template in templates:
        try:
            # Check if template already exists
            existing_templates = store.list_persona_templates()
            if any(t.id == template.id for t in existing_templates):
                print(f"⚠️  Template '{template.id}' already exists. Skipping...")
                continue

            # Create template
            created = store.create_persona_template(template)
            print(f"✅ Created template: {created.id} - {created.label}")
        except Exception as e:
            print(f"❌ Failed to create template '{template.id}': {e}")

    print("\n🎉 Seeding completed!")


if __name__ == "__main__":
    seed_beginner_templates()
