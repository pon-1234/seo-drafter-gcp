from __future__ import annotations

import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from shared.internal_links import InternalLinkRepository
from shared.persona_utils import build_intro_persona_clause, infer_japanese_persona_label
from shared.project_defaults import get_project_defaults, get_prompt_layers_for_expertise
from shared.style import ABSTRACT_PATTERNS, NG_PHRASES
from .style_rewrite import StructurePreservingStyleRewriter
from ..validators import StructureValidator

# OpenAI Gateway is now local to worker
try:
    from ..services.openai_gateway import OpenAIGateway
except ImportError:
    OpenAIGateway = None  # type: ignore

from ..core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class PipelineContext:
    job_id: str
    draft_id: str
    project_id: str
    prompt_version: str
    primary_keyword: str
    persona: Dict
    intent: str
    article_type: str
    cta: Optional[str]
    heading_mode: str
    heading_overrides: List[str]
    quality_rubric: Optional[str]
    reference_urls: List[str]
    output_format: str
    notation_guidelines: Optional[str]
    word_count_range: Optional[str]
    writer_persona: Dict[str, Any]
    preferred_sources: List[str]
    reference_media: List[str]
    project_template_id: Optional[str]
    prompt_layers: Dict[str, str]
    llm_provider: str
    llm_model: str
    llm_temperature: float
    serp_snapshot: List[Dict[str, Any]]
    serp_gap_topics: List[str]
    expertise_level: str  # "beginner" | "intermediate" | "expert"
    tone: str  # "casual" | "formal"
    keyword_preset: Optional[str] = None  # e.g., "glossary" for 「◯◯とは」 intent


class DraftGenerationPipeline:
    """Encapsulates the deterministic order of the draft generation steps."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.max_workers = max(int(getattr(self.settings, "llm_max_workers", 4) or 4), 1)
        self.ai_gateway = None
        self._active_llm: Dict[str, Any] = {"provider": None, "model": None, "temperature": None}
        self.style_rewriter = StructurePreservingStyleRewriter(None)
        self.structure_validator = StructureValidator()

        if not OpenAIGateway:
            logger.error("OpenAI gateway implementation is not available")
        else:
            try:
                self._configure_gateway()
            except Exception as exc:
                logger.error("LLM initialization failed: %s (type: %s)", str(exc), type(exc).__name__)
                import traceback

                logger.error("Full traceback: %s", traceback.format_exc())

        self.link_repository = InternalLinkRepository()

    def _default_model_for_provider(self, provider: str) -> str:
        if provider == "anthropic" and self.settings.anthropic_model:
            return self.settings.anthropic_model
        return self.settings.openai_model

    def _configure_gateway(self, override: Optional[Dict[str, Any]] = None) -> None:
        provider = (override or {}).get("provider") or self.settings.llm_provider
        provider = str(provider).lower()
        if provider not in {"openai", "anthropic"}:
            raise ValueError(f"Unsupported LLM provider: {provider}")

        model = (override or {}).get("model") or self._default_model_for_provider(provider)
        temperature = float((override or {}).get("temperature") or 0.7)

        if (
            self.ai_gateway
            and self._active_llm["provider"] == provider
            and self._active_llm["model"] == model
            and self._active_llm["temperature"] == temperature
        ):
            return

        if not OpenAIGateway:
            raise RuntimeError("LLM gateway implementation unavailable")

        logger.info("Configuring LLM gateway provider=%s model=%s temperature=%.2f", provider, model, temperature)
        self.ai_gateway = OpenAIGateway(
            api_key=self.settings.openai_api_key,
            model=model,
            search_enabled=True,
            provider=provider,
            anthropic_api_key=self.settings.anthropic_api_key,
        )
        self._active_llm = {"provider": provider, "model": model, "temperature": temperature}
        if self.style_rewriter:
            self.style_rewriter.update_gateway(self.ai_gateway)

    @staticmethod
    def _normalize_serp_snapshot(raw_snapshot: Any) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        if not raw_snapshot:
            return results
        if isinstance(raw_snapshot, dict):
            iterable = [raw_snapshot]
        elif isinstance(raw_snapshot, list):
            iterable = raw_snapshot
        else:
            iterable = []

        for entry in iterable:
            if isinstance(entry, str):
                url = entry.strip()
                if url:
                    results.append({
                        "url": url,
                        "title": url,
                        "summary": "",
                        "key_points": [],
                    })
                continue
            if not isinstance(entry, dict):
                continue
            url = str(entry.get("url") or "").strip()
            title = str(entry.get("title") or "").strip() or url or "SERP Result"
            summary = str(entry.get("summary") or entry.get("description") or "").strip()
            raw_points = entry.get("key_points") or entry.get("topics") or []
            key_points: List[str] = []
            if isinstance(raw_points, str):
                key_points = [item.strip() for item in re.split(r"[,、，\n]+", raw_points) if item.strip()]
            elif isinstance(raw_points, list):
                key_points = [str(item).strip() for item in raw_points if str(item).strip()]
            else:
                key_points = []
            if url and "example.com" in url:
                continue
            results.append({
                "url": url,
                "title": title,
                "summary": summary,
                "key_points": key_points,
            })
        return results

    @staticmethod
    def _derive_serp_gap_topics(
        serp_snapshot: List[Dict[str, Any]],
        primary_keyword: str,
        min_topics: int = 3,
    ) -> List[str]:
        from collections import Counter

        counter: Counter[str] = Counter()
        for result in serp_snapshot:
            for point in result.get("key_points", []):
                normalized = point.strip()
                if normalized:
                    counter[normalized] += 1

        if not counter:
            return []

        unique_candidates = [topic for topic, freq in counter.items() if freq <= 1]
        unique_candidates.sort(key=lambda item: item.lower())

        gaps: List[str] = []
        for topic in unique_candidates:
            if topic not in gaps:
                gaps.append(topic)
            if len(gaps) >= min_topics:
                break

        if len(gaps) < min_topics:
            # supplement with high-signal topics to ensure coverage
            for topic, _freq in counter.most_common():
                if topic not in gaps:
                    gaps.append(topic)
                if len(gaps) >= min_topics:
                    break

        # Ensure primary keyword variations are emphasised
        if primary_keyword and all(primary_keyword not in topic for topic in gaps):
            gaps.insert(0, f"{primary_keyword} の差別化視点")

        # Deduplicate while preserving order
        seen = set()
        ordered: List[str] = []
        for topic in gaps:
            if topic in seen:
                continue
            seen.add(topic)
            ordered.append(topic)
        return ordered[: max(min_topics, 5)]

    def estimate_intent(self, payload: Dict) -> str:
        requested_intent = payload.get("intent")
        if requested_intent:
            logger.info("Job %s intent provided: %s", payload["job_id"], requested_intent)
            return requested_intent
        persona = payload.get("persona", {})
        goals = persona.get("goals", [])
        if any("比較" in goal for goal in goals):
            intent = "comparison"
        elif any("購入" in goal for goal in goals):
            intent = "transaction"
        else:
            intent = "information"
        logger.info("Job %s inferred intent: %s", payload["job_id"], intent)
        return intent

    def generate_outline(
        self,
        context: PipelineContext,
        prompt: Dict,
        *,
        conclusion: Optional[Dict[str, Any]] = None,
    ) -> Dict:
        logger.info(
            "Generating outline for %s using prompt %s (mode=%s)",
            context.job_id,
            context.prompt_version,
            context.heading_mode,
        )
        if context.heading_mode == "manual" and context.heading_overrides:
            outline = self._outline_from_manual(context, prompt)
        else:
            outline = self._outline_from_template(context, prompt)
        reader_note = self._build_reader_note(context)
        if reader_note:
            outline["reader_note"] = reader_note
        if "provisional_title" not in outline and outline.get("title"):
            outline["provisional_title"] = outline["title"]
        if conclusion:
            self._apply_conclusion_to_outline(outline, context, conclusion)
        return outline

    def _build_quest_title(self, primary_keyword: str, context: Optional[PipelineContext] = None) -> str:
        keyword = primary_keyword or "SEO"
        keyword_surface = self._sanitize_keyword_surface(keyword)
        article_type = context.article_type if context else "information"
        expertise = context.expertise_level if context else "intermediate"
        is_glossary = (
            (context and context.keyword_preset == "glossary")
            or self._is_glossary_keyword(primary_keyword, article_type)
        )
        glossary_phrase = f"{keyword_surface}とは" if is_glossary else keyword_surface

        if expertise == "beginner":
            if article_type == "comparison":
                return f"{keyword_surface}の選び方ガイド：初心者向けおすすめと優先順位"
            if is_glossary:
                return f"{glossary_phrase}？基本の考え方と実務での活かし方"
            return f"{keyword_surface}の入門ガイド：基礎から実践まで解説"

        if article_type == "comparison":
            return f"{keyword_surface}の比較ガイド: 選び方と優先順位"

        if is_glossary and article_type == "information":
            return f"{glossary_phrase}？基本と成功プロセスを整理"

        return f"{keyword_surface}の実務ガイド: 結論と成功プロセス"

    def _apply_conclusion_to_outline(
        self,
        outline: Dict,
        context: PipelineContext,
        conclusion: Optional[Dict[str, Any]],
    ) -> None:
        if not conclusion:
            return
        outline["conclusion"] = conclusion
        main_conclusion = str(conclusion.get("main_conclusion") or "").strip()
        if not main_conclusion:
            return
        sections = outline.get("h2")
        if not isinstance(sections, list) or not sections:
            return
        if context.heading_mode != "manual":
            first_heading = str(sections[0].get("text") or "").strip()
            if "結論" not in first_heading and "まとめ" not in first_heading:
                supporting_points = [
                    str(point).strip()
                    for point in conclusion.get("supporting_points", [])[:3]
                    if str(point).strip()
                ]
                first_section_words = sections[0].get("estimated_words") or 260
                outline["h2"] = [
                    {
                        "text": f"結論：{main_conclusion}",
                        "purpose": "Conclusion",
                        "estimated_words": first_section_words,
                        "h3": [
                            {
                                "text": f"根拠{idx+1}: {point}",
                                "purpose": "ConclusionEvidence",
                            }
                            for idx, point in enumerate(supporting_points)
                        ],
                    },
                    *sections,
                ]
                sections = outline["h2"]
        if isinstance(sections, list) and sections:
            sections[0].setdefault("summary_hint", main_conclusion)

    @staticmethod
    def _sanitize_keyword_surface(keyword: str) -> str:
        raw_value = str(keyword or "").replace("\u3000", " ").strip()
        if not raw_value:
            return "SEO"
        cleaned = re.sub(r"(?:\s|　)*(?:とは)+(?:[?？]*)$", "", raw_value).strip()
        if not cleaned:
            fallback = re.sub(r"(?:とは|[?？])+", "", raw_value).strip()
            return fallback or "SEO"
        return cleaned

    @staticmethod
    def _is_glossary_keyword(keyword: str, article_type: str) -> bool:
        """Detect \"◯◯とは\"/glossary-like queries."""
        if article_type != "information":
            return False
        normalized = str(keyword or "").strip()
        return bool(re.search(r"とは[?？]*$", normalized))

    def _infer_keyword_preset(self, primary_keyword: str, article_type: str) -> Optional[str]:
        """Return a preset label based on keyword form."""
        if self._is_glossary_keyword(primary_keyword, article_type):
            return "glossary"
        return None

    @staticmethod
    def _coerce_expertise_level_for_preset(requested: str, preset: Optional[str]) -> str:
        """Balance expertise level for certain presets."""
        if preset == "glossary" and requested == "intermediate":
            return "beginner"
        return requested

    @staticmethod
    def _coerce_word_count_for_preset(word_count_raw: Any, preset: Optional[str]) -> Optional[str]:
        """Provide preset defaults when user has not specified a range."""
        if word_count_raw:
            return str(word_count_raw)
        if preset == "glossary":
            # 6セクション × 600〜800字を目安にしたレンジ
            return "3600-4800"
        return None

    @staticmethod
    def _extract_title_line(raw_text: str) -> str:
        if not raw_text:
            return ""
        for line in raw_text.splitlines():
            cleaned = line.strip()
            if not cleaned:
                continue
            if cleaned.lower().startswith("title:"):
                cleaned = cleaned.split(":", 1)[1].strip()
            cleaned = cleaned.strip("「」\"'“”")
            if cleaned:
                return cleaned
        return raw_text.strip()

    @staticmethod
    def _strip_json_fence(raw_text: str) -> str:
        if not raw_text:
            return ""
        text = raw_text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
            if text.endswith("```"):
                text = text[: -3].strip()
        return text

    def _build_reader_note(self, context: PipelineContext) -> str:
        persona = dict(context.persona) if isinstance(context.persona, dict) else {}
        if "expertise_level" not in persona:
            persona["expertise_level"] = context.expertise_level

        persona_label = infer_japanese_persona_label(persona, context.writer_persona)
        intro_clause = build_intro_persona_clause(persona_label)

        fallback_levels = {
            "beginner": "用語はなんとなく知っていて基礎を整理したい層",
            "intermediate": "施策を体系立てて比較検討したい層",
            "expert": "戦略と実行を同時に見直したい層",
        }
        level_hint = persona.get("reading_level") or fallback_levels.get(
            context.expertise_level, "実務で成果を出したい層"
        )
        goals = [str(goal).strip() for goal in persona.get("goals", []) if str(goal).strip()]
        job_to_be_done = str(persona.get("job_to_be_done") or "").strip()
        if goals:
            detail_clause = f"特に「{goals[0]}」ための考え方と手順を整理しました。"
        elif job_to_be_done:
            detail_clause = f"「{job_to_be_done}」を実現するまでのステップをわかりやすくまとめています。"
        else:
            detail_clause = "実務で迷ったときの判断材料としてご活用ください。"

        return f"{intro_clause}{level_hint}の視点で、{detail_clause}"

    def _outline_from_manual(self, context: PipelineContext, prompt: Dict) -> Dict:
        sections = []
        budget = self._estimate_section_word_budget(context, len(context.heading_overrides) or 1)
        for heading in context.heading_overrides:
            sections.append(
                {
                    "text": heading,
                    "purpose": "Custom",
                    "estimated_words": budget,
                    "h3": [],
                }
            )
        quest_title = self._build_quest_title(prompt["primary_keyword"], context)
        return {
            "title": quest_title,
            "provisional_title": quest_title,
            "h2": sections,
        }

    def _outline_from_template(self, context: PipelineContext, prompt: Dict) -> Dict:
        keyword = prompt["primary_keyword"]
        template_sections = self._article_type_template(
            context.article_type,
            keyword,
            context.expertise_level,
            context.keyword_preset,
        )
        budget = self._estimate_section_word_budget(context, len(template_sections) or 1)
        for section in template_sections:
            section.setdefault("estimated_words", budget)
            for h3 in section.get("h3", []):
                h3.setdefault("estimated_words", max(int(budget / max(len(section.get("h3", [])) or 1, 1)), 120))
        max_gap_topics = 2 if context.keyword_preset == "glossary" else 5
        for gap_topic in context.serp_gap_topics[:max_gap_topics]:
            template_sections.append(
                {
                    "text": f"{gap_topic}の差別化と未カバー情報",
                    "purpose": "Gap",
                    "h3": [
                        {"text": f"{gap_topic}の現状データと根拠", "purpose": "Gap"},
                        {"text": f"{gap_topic}で提示する具体的な打ち手", "purpose": "Gap"},
                    ],
                    "estimated_words": budget,
                }
            )
        quest_title = self._build_quest_title(keyword, context)
        return {
            "title": quest_title,
            "provisional_title": quest_title,
            "h2": template_sections,
        }

    def _article_type_template(
        self,
        article_type: str,
        keyword: str,
        expertise_level: str = "intermediate",
        keyword_preset: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        # Beginner-friendly templates (optimized for "◯◯とは" search intent)
        keyword_surface = self._sanitize_keyword_surface(keyword)
        beginner_information_template = [
            {
                "text": f"リード文：{keyword_surface}とは何かをQUESTで提示（定義を冒頭に置く）",
                "purpose": "Lead",
                "h3": [
                    {"text": "Q/U: 読者の悩みと放置するリスク", "purpose": "LeadQuest"},
                    {"text": f"E/S: {keyword_surface}で得られる価値と記事構成", "purpose": "LeadQuest"},
                    {"text": "T: 読後に実践できる一歩を示す", "purpose": "LeadQuest"},
                ],
            },
            {
                "text": f"{keyword_surface}とは何か（定義と従来マーケとの違い）",
                "purpose": "Definition",
                "h3": [
                    {"text": f"{keyword_surface}の定義を一文で明示", "purpose": "Definition"},
                    {"text": "従来マーケとの違いと役割分担", "purpose": "Difference"},
                    {"text": "向いているケース・向かないケース", "purpose": "FitUnfit"},
                ],
            },
            {
                "text": f"いま{keyword_surface}が重要になっている背景",
                "purpose": "Context",
                "h3": [
                    {"text": "市場環境や顧客行動の変化", "purpose": "MarketShift"},
                    {"text": "法規制・技術トレンド（Cookie/個人情報保護など）", "purpose": "Regulation"},
                    {"text": "オフライン施策との役割分担", "purpose": "OfflineRole"},
                ],
            },
            {
                "text": "主な施策・チャネルの種類と役割",
                "purpose": "Channels",
                "h3": [
                    {"text": "自社サイト/SEO/コンテンツマーケの基礎", "purpose": "OwnedSeo"},
                    {"text": "広告・SNSでの集客と向き不向き", "purpose": "AdsSNS"},
                    {"text": "メール/MA/ウェビナーなど育成施策", "purpose": "Nurture"},
                ],
            },
            {
                "text": "成功させるためのポイント・KPI設計",
                "purpose": "KPI",
                "h3": [
                    {"text": "ファネル別のKPIと計測の考え方", "purpose": "FunnelKPI"},
                    {"text": "組織・体制づくりとリソース配分", "purpose": "Org"},
                    {"text": "ツール活用は代表例のみ挙げ、設定手順は避ける", "purpose": "ToolsLight"},
                ],
            },
            {
                "text": "よくある失敗パターンと対策",
                "purpose": "Risk",
                "h3": [
                    {"text": "チャネルごとの部分最適・計測偏重になりがち", "purpose": "ChannelSilod"},
                    {"text": "ターゲット/メッセージのずれ", "purpose": "MessageMismatch"},
                    {"text": "短期で判断しすぎる/データの読み違い", "purpose": "ShortTerm"},
                ],
            },
            {
                "text": f"まとめと今日から取れる一歩（{keyword_surface}の活かし方）",
                "purpose": "Close",
                "h3": [
                    {"text": "主要ポイントの振り返り", "purpose": "Recap"},
                    {"text": "すぐに試せる1アクションとCTA", "purpose": "Action"},
                ],
            },
        ]

        glossary_information_template = beginner_information_template
        beginner_comparison_template = [
            {
                "text": "30秒で要点：この記事で分かること",
                "purpose": "Summary",
                "h3": [
                    {"text": "おすすめTOP3の結論", "purpose": "Summary"},
                    {"text": "選び方の基準", "purpose": "Quick"},
                ],
            },
            {
                "text": f"{keyword_surface}を選ぶポイントを3軸で解説",
                "purpose": "Introduction",
                "h3": [
                    {"text": "何を基準に選べばいい？", "purpose": "Criteria"},
                    {"text": "初心者が気をつけるべきこと", "purpose": "Caution"},
                ],
            },
            {
                "text": "おすすめTOP3の比較",
                "purpose": "Comparison",
                "h3": [
                    {"text": "1位：これが一番おすすめの理由", "purpose": "Top1"},
                    {"text": "2位・3位：他の選択肢", "purpose": "Top23"},
                ],
            },
            {
                "text": "使う人別のおすすめ",
                "purpose": "Segmentation",
                "h3": [
                    {"text": "初めて使う人向け", "purpose": "Beginner"},
                    {"text": "予算を抑えたい人向け", "purpose": "Budget"},
                ],
            },
            {
                "text": f"まとめ：{keyword_surface}を始めてみよう",
                "purpose": "Close",
                "h3": [
                    {"text": "次にやってみること", "purpose": "NextAction"},
                ],
            },
        ]

        beginner_ranking_template = [
            {
                "text": "30秒で要点：ランキング結果",
                "purpose": "Summary",
                "h3": [
                    {"text": "TOP3のハイライト", "purpose": "Highlight"},
                    {"text": "どうやってランク付けしたの？", "purpose": "Method"},
                ],
            },
            {
                "text": "1位から3位を詳しく紹介",
                "purpose": "Review",
                "h3": [
                    {"text": "第1位：おすすめポイントと特徴", "purpose": "Rank1"},
                    {"text": "第2位・第3位の良いところ", "purpose": "Rank23"},
                ],
            },
            {
                "text": "あなたに合うのはどれ？",
                "purpose": "Segmentation",
                "h3": [
                    {"text": "こんな人には1位がおすすめ", "purpose": "Type1"},
                    {"text": "こんな人には2位・3位がおすすめ", "purpose": "Type23"},
                ],
            },
            {
                "text": "よくある失敗と対策",
                "purpose": "Risk",
                "h3": [
                    {"text": "初心者がつまずきやすいポイント", "purpose": "Mistakes"},
                    {"text": "お得に始める方法", "purpose": "Deals"},
                ],
            },
            {
                "text": "まとめと次のステップ",
                "purpose": "Close",
                "h3": [
                    {"text": "次にやってみること", "purpose": "NextAction"},
                ],
            },
        ]

        # Intermediate/Expert templates (existing)
        information_template = [
            {
                "text": f"結論: {keyword_surface}で実現できる成果と次のアクション",
                "purpose": "Summary",
                "h3": [
                    {"text": "最優先で押さえるべき成功条件", "purpose": "Summary"},
                    {"text": "効果検証に用いる主要指標", "purpose": "Summary"},
                ],
            },
            {
                "text": "背景と課題: なぜいま取り組む必要があるのか",
                "purpose": "Context",
                "h3": [
                    {"text": "読者が直面する具体的な課題シナリオ", "purpose": "Context"},
                    {"text": "関連する市場動向・法規制", "purpose": "Context"},
                ],
            },
            {
                "text": "根拠と仕組み: 成果を支えるメカニズム",
                "purpose": "Mechanism",
                "h3": [
                    {"text": "一次情報・統計で裏付ける効果", "purpose": "Mechanism"},
                    {"text": "仕組み・プロセスの分解と要点", "purpose": "Mechanism"},
                ],
            },
            {
                "text": "実践ステップ: 再現性のある進め方",
                "purpose": "Execution",
                "h3": [
                    {"text": "着手前に整える前提条件", "purpose": "Execution"},
                    {"text": "ステップごとのタスクと注意点", "purpose": "Execution"},
                ],
            },
            {
                "text": "事例と比較: 選択肢ごとの成果と向き・不向き",
                "purpose": "Case",
                "h3": [
                    {"text": "成功事例で確認できた定量的成果", "purpose": "Case"},
                    {"text": "他手法との違いと併用パターン", "purpose": "Case"},
                ],
            },
            {
                "text": "リスクと対策: つまずきポイントの予防策",
                "purpose": "Risk",
                "h3": [
                    {"text": "よくある失敗パターンと兆候", "purpose": "Risk"},
                    {"text": "リカバリーと継続改善のチェックリスト", "purpose": "Risk"},
                ],
            },
            {
                "text": "まとめと次のステップ",
                "purpose": "Close",
                "h3": [
                    {"text": "本記事で押さえた主要論点の整理", "purpose": "Close"},
                    {"text": "今後の検討で確認すべき追加情報", "purpose": "Close"},
                ],
            },
        ]

        comparison_template = [
            {
                "text": f"結論: {keyword}のおすすめと評価サマリー",
                "purpose": "Summary",
                "h3": [
                    {"text": "最優先で検討すべき候補と理由", "purpose": "Summary"},
                    {"text": "評価に用いた基準の概要", "purpose": "Summary"},
                ],
            },
            {
                "text": "評価軸と選定基準",
                "purpose": "Criteria",
                "h3": [
                    {"text": "比較項目（機能・価格・サポート等）", "purpose": "Criteria"},
                    {"text": "用途別に優先すべき指標", "purpose": "Criteria"},
                ],
            },
            {
                "text": "主要候補の比較表と要点",
                "purpose": "Comparison",
                "h3": [
                    {"text": "TOP3製品の特徴と向いているケース", "purpose": "Comparison"},
                    {"text": "定量データで見る強み・弱み", "purpose": "Comparison"},
                ],
            },
            {
                "text": "用途別・規模別の向き不向き",
                "purpose": "Segmentation",
                "h3": [
                    {"text": "小規模チーム／初導入でのポイント", "purpose": "Segmentation"},
                    {"text": "エンタープライズ・高機能ニーズの場合", "purpose": "Segmentation"},
                ],
            },
            {
                "text": "価格・導入難易度・サポート体制",
                "purpose": "Operations",
                "h3": [
                    {"text": "料金体系と総コストの比較", "purpose": "Operations"},
                    {"text": "導入期間・必要リソース・サポート", "purpose": "Operations"},
                ],
            },
            {
                "text": "検討時の注意点と確認項目",
                "purpose": "Risk",
                "h3": [
                    {"text": "想定されるリスクとチェックリスト", "purpose": "Risk"},
                    {"text": "契約前に確認すべき一次情報", "purpose": "Risk"},
                ],
            },
            {
                "text": "まとめと調達に向けた次アクション",
                "purpose": "Close",
                "h3": [
                    {"text": "意思決定を進めるための準備物", "purpose": "Close"},
                    {"text": "出典・比較データの参照先", "purpose": "Close"},
                ],
            },
        ]

        ranking_template = [
            {
                "text": f"結論: {keyword}ランキングのハイライト",
                "purpose": "Summary",
                "h3": [
                    {"text": "評価方法とTOP3の総評", "purpose": "Summary"},
                    {"text": "読者タイプ別のおすすめ候補", "purpose": "Summary"},
                ],
            },
            {
                "text": "ランクインの評価軸とスコア",
                "purpose": "Criteria",
                "h3": [
                    {"text": "主要指標と計測方法", "purpose": "Criteria"},
                    {"text": "データソースと出典", "purpose": "Criteria"},
                ],
            },
            {
                "text": "TOP3の詳細レビュー",
                "purpose": "Review",
                "h3": [
                    {"text": "第1位の概要と導入メリット", "purpose": "Review"},
                    {"text": "第2位・第3位の特徴と適合シーン", "purpose": "Review"},
                ],
            },
            {
                "text": "用途別・業界別のおすすめ",
                "purpose": "Segmentation",
                "h3": [
                    {"text": "コスト重視の選択肢", "purpose": "Segmentation"},
                    {"text": "機能・サポート重視の選択肢", "purpose": "Segmentation"},
                ],
            },
            {
                "text": "導入時の注意点とチェックリスト",
                "purpose": "Risk",
                "h3": [
                    {"text": "よくある失敗ポイント", "purpose": "Risk"},
                    {"text": "契約・運用で確認したい事項", "purpose": "Risk"},
                ],
            },
            {
                "text": "資料・比較表と次アクション",
                "purpose": "Close",
                "h3": [
                    {"text": "ダウンロード資料・出典リンク", "purpose": "Close"},
                    {"text": "社内で検討を進める際のTips", "purpose": "Close"},
                ],
            },
        ]

        closing_template = [
            {
                "text": f"結論: {keyword}導入で得られる成果の再確認",
                "purpose": "Summary",
                "h3": [
                    {"text": "意思決定を後押しする定量的根拠", "purpose": "Summary"},
                    {"text": "導入後のロードマップ概要", "purpose": "Summary"},
                ],
            },
            {
                "text": "導入プロセスと成功条件",
                "purpose": "Execution",
                "h3": [
                    {"text": "短期導入ステップと役割分担", "purpose": "Execution"},
                    {"text": "成功事例から学ぶ運用ポイント", "purpose": "Execution"},
                ],
            },
            {
                "text": "ROIとリスクコントロール",
                "purpose": "Finance",
                "h3": [
                    {"text": "投資対効果を示す数値・試算", "purpose": "Finance"},
                    {"text": "リスクとコンプライアンス対応", "purpose": "Finance"},
                ],
            },
            {
                "text": "クロージング: 契約・導入に向けた次アクション",
                "purpose": "Close",
                "h3": [
                    {"text": "比較検討の最終チェックリスト", "purpose": "Close"},
                    {"text": "社内稟議資料で押さえるべき要素", "purpose": "Close"},
                ],
            },
        ]

        # Select templates based on expertise level
        information_template_to_use = beginner_information_template
        if expertise_level == "beginner":
            information_template_to_use = glossary_information_template if keyword_preset == "glossary" else beginner_information_template
            templates = {
                "information": information_template_to_use,
                "comparison": beginner_comparison_template,
                "ranking": beginner_ranking_template,
                "closing": beginner_information_template,  # Use information template for closing
            }
        else:
            # intermediate and expert use the same structure templates
            templates = {
                "information": information_template,
                "comparison": comparison_template,
                "ranking": ranking_template,
                "closing": closing_template,
            }
            information_template_to_use = information_template
        default_information_template = (
            information_template if expertise_level != "beginner" else information_template_to_use
        )

        resolved = []
        for section in templates.get(article_type, default_information_template):
            resolved.append(
                {
                    "text": section["text"],
                    "purpose": section.get("purpose", "Know"),
                    "h3": [dict(item) for item in section.get("h3", [])],
                }
            )
        return resolved

    def _estimate_section_word_budget(self, context: PipelineContext, section_count: int) -> int:
        if not context.word_count_range:
            return 300
        numbers = [int(num) for num in re.findall(r"\d+", context.word_count_range)]
        if not numbers:
            return 300
        average = sum(numbers) / len(numbers)
        return max(int(average / max(section_count, 1)), 200)

    def generate_draft(self, context: PipelineContext, outline: Dict, citations: List[Dict]) -> Dict:
        logger.info(
            "Generating draft for %s with %d outline sections (max_workers=%d)",
            context.job_id,
            len(outline.get("h2", [])),
            self.max_workers,
        )
        sections: List[Dict[str, Any]] = []
        all_claims: List[Dict[str, Any]] = []

        def build_paragraph(heading_text: str, level: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
            messages = self._build_prompt_messages(heading_text, level, context)
            grounded_result = self._generate_grounded_content(
                messages=messages,
                temperature=context.llm_temperature,
                log_info={
                    "stage": "generate_draft",
                    "heading": heading_text,
                    "level": level,
                    "job_id": context.job_id,
                    "draft_id": context.draft_id,
                },
            )
            claim_id = f"{context.draft_id}-{heading_text}"
            if level == "h2":
                claim_id = f"{context.draft_id}-{level}-{heading_text}"
            source_candidates = grounded_result.get("citations") or citations[:2]
            if not source_candidates and context.reference_urls:
                source_candidates = [{"url": url} for url in context.reference_urls[:2]]
            prioritized_sources = self._prioritize_sources(source_candidates, context.preferred_sources)
            citation_values = [c.get("uri") or c.get("url") or str(c) for c in prioritized_sources]
            raw_text = grounded_result.get("text")
            normalized_text = raw_text.strip() if isinstance(raw_text, str) else ""
            paragraph_text = normalized_text or f"{heading_text} について解説します。"

            paragraph_payload = {
                "heading": heading_text,
                "text": paragraph_text,
                "citations": citation_values,
                "claim_id": claim_id,
            }
            claim_payload = {
                "id": claim_id,
                "text": normalized_text or paragraph_text,
                "citations": grounded_result.get("citations", []),
            }
            return paragraph_payload, claim_payload

        outline_h2 = outline.get("h2", [])
        if not outline_h2:
            logger.warning("Outline missing h2 sections for %s", context.job_id)

        future_map = {}
        h2_paragraphs: Dict[int, List[Tuple[int, Dict[str, Any]]]] = {}
        h2_claims: Dict[int, List[Dict[str, Any]]] = {}

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            for h2_index, h2 in enumerate(outline_h2):
                h3_list = h2.get("h3", [])
                if h3_list:
                    for h3_index, h3 in enumerate(h3_list):
                        future = executor.submit(build_paragraph, h3["text"], "h3")
                        future_map[future] = (h2_index, h3_index)
                else:
                    future = executor.submit(build_paragraph, h2["text"], "h2")
                    future_map[future] = (h2_index, 0)

            for future in as_completed(future_map):
                h2_index, order = future_map[future]
                try:
                    paragraph, claim = future.result()
                except Exception as exc:
                    logger.exception(
                        "Paragraph generation failed for job %s section %s: %s",
                        context.job_id,
                        h2_index,
                        exc,
                    )
                    paragraph = {
                        "heading": outline_h2[h2_index]["text"],
                        "text": "生成に失敗しましたが、要点を後で補完してください。",
                        "citations": [],
                        "claim_id": f"{context.draft_id}-fallback-{h2_index}-{order}",
                    }
                    claim = {
                        "id": paragraph["claim_id"],
                        "text": paragraph["text"],
                        "citations": [],
                    }
                h2_paragraphs.setdefault(h2_index, []).append((order, paragraph))
                h2_claims.setdefault(h2_index, []).append(claim)

        for h2_index, h2 in enumerate(outline_h2):
            paragraph_entries = sorted(h2_paragraphs.get(h2_index, []), key=lambda item: item[0])
            paragraphs = [entry for _order, entry in paragraph_entries]
            if not paragraphs:
                logger.warning("No paragraphs generated for job %s section %s", context.job_id, h2["text"])
            sections.append({"h2": h2["text"], "paragraphs": paragraphs})
            all_claims.extend(h2_claims.get(h2_index, []))

        return {
            "sections": sections,
            "faq": self._generate_faq(context),
            "claims": all_claims,
        }

    def _build_prompt_messages(self, heading: str, level: str, context: PipelineContext) -> List[Dict[str, str]]:
        """Build layered prompt messages (system/developer/user)."""
        # Select prompt layers based on expertise level and project defaults
        expertise_layers = get_prompt_layers_for_expertise(context.expertise_level)

        logger.info(
            "Selecting prompt for expertise_level=%s, tone=%s, heading=%s",
            context.expertise_level,
            context.tone,
            heading
        )

        base_layers = context.prompt_layers if (context.prompt_layers and any(context.prompt_layers.values())) else {}
        prompt_layers = expertise_layers.to_payload()
        if base_layers:
            prompt_layers = self._merge_prompt_layers(base_layers, prompt_layers)
            logger.info("Using merged prompt layers (project defaults + expertise)")
        else:
            logger.info("Using expertise-based prompt layers for level: %s", context.expertise_level)
        prompt_layers = self._augment_layers_for_preset(prompt_layers, context)

        writer = context.writer_persona or {}
        writer_name = writer.get("name") or "シニアSEOライター"
        writer_role = writer.get("role") or "シニアSEO編集者"
        writer_voice = writer.get("voice") or "落ち着いた敬体で簡潔に説明する"
        writer_expertise = writer.get("expertise") or "SEOとB2Bマーケに精通"
        writer_mission = writer.get("mission") or "読者の迷いを解き行動を後押しする"
        raw_qualities = writer.get("qualities") or []
        if isinstance(raw_qualities, list):
            writer_qualities = " / ".join(str(item).strip() for item in raw_qualities if str(item).strip())
        elif isinstance(raw_qualities, str):
            writer_qualities = raw_qualities.strip()
        else:
            writer_qualities = ""
        if not writer_qualities:
            writer_qualities = "抽象→具体への往復 / QUESTやVAKなどのフレームでストーリーを描写"
        persona_payload = dict(context.persona) if isinstance(context.persona, dict) else {}
        if "expertise_level" not in persona_payload:
            persona_payload["expertise_level"] = context.expertise_level
        persona_label = infer_japanese_persona_label(persona_payload, context.writer_persona)
        persona_intro_clause = build_intro_persona_clause(persona_label)

        reader_name = context.persona.get("name") or "読者"
        reader_tone = context.persona.get("tone") or "実務的"

        references = ", ".join(context.reference_urls[:5]) if context.reference_urls else "指定なし"
        preferred_sources = ", ".join(context.preferred_sources[:5]) if context.preferred_sources else "優先指定なし"
        preferred_media = ", ".join(context.reference_media[:5]) if context.reference_media else "優先指定なし"
        notation = context.notation_guidelines or "読みやすい日本語（全角を適切に使用）"
        gap_topics = ", ".join(context.serp_gap_topics[:3]) if context.serp_gap_topics else "差別化指示なし"

        reader_profile = self._render_reader_profile(context.persona, reader_tone)
        section_goal = self._derive_section_goal(heading, context)

        format_payload = {
            "writer_name": writer_name,
            "reader_name": reader_name,
            "heading": heading,
            "level": level.upper(),
            "primary_keyword": context.primary_keyword or heading,
            "reader_profile": reader_profile,
            "writer_role": writer_role,
            "writer_voice": writer_voice,
            "writer_expertise": writer_expertise,
            "writer_mission": writer_mission,
            "writer_qualities": writer_qualities,
            "cta": context.cta or "適切な次のアクションを選べる",
            "references": references,
            "preferred_sources": preferred_sources,
            "preferred_media": preferred_media,
            "notation": notation,
            "article_type": context.article_type,
            "intent": context.intent,
            "section_goal": section_goal,
            "gap_topics": gap_topics,
            "persona_label": persona_label,
            "persona_intro": persona_intro_clause,
        }

        system_template = prompt_layers.get("system", "")
        developer_template = prompt_layers.get("developer", "")
        user_template = prompt_layers.get("user", "")

        system_message = system_template.format_map(format_payload) if system_template else ""
        developer_message = developer_template.format_map(format_payload) if developer_template else ""
        user_message = user_template.format_map(format_payload) if user_template else ""

        return [
            {"role": "system", "content": system_message},
            {"role": "developer", "content": developer_message},
            {"role": "user", "content": user_message},
        ]

    @staticmethod
    def _merge_prompt_layers(base_layers: Dict[str, str], expertise_layers: Dict[str, str]) -> Dict[str, str]:
        """Concatenate project-level and expertise-specific prompt layers."""
        merged: Dict[str, str] = {}
        for key in ("system", "developer", "user"):
            parts = []
            base = base_layers.get(key, "")
            expert = expertise_layers.get(key, "")
            if base and base.strip():
                parts.append(base.strip())
            if expert and expert.strip():
                parts.append(expert.strip())
            merged[key] = "\n\n".join(parts)
        return merged

    def _augment_layers_for_preset(self, layers: Dict[str, str], context: PipelineContext) -> Dict[str, str]:
        """Inject preset-specific writing rules (e.g., glossary/「◯◯とは」)."""
        if context.keyword_preset != "glossary":
            return layers
        additions_system = (
            "この記事は「◯◯とは」クエリ向けの基礎解説です。検索意図は「基礎を理解し、自分の業務にどう関係するかを知りたい」。"
            "計測・広告の深掘りよりも、チャネル全体像・向き不向き・最初の一歩を優先し、Google固有機能名は代表例として軽く触れるだけにします。"
        )
        additions_developer = (
            "【タイトル/H1】主キーワード「{primary_keyword}」をそのまま含める。\n"
            "【リード】QUESTで300〜500字。最初の2〜3文で「{primary_keyword}とは〜である」と定義する。\n"
            "【構成の骨格】リード→「◯◯とは」定義→背景→主な施策/チャネル→成功ポイント・KPI→失敗と対策→まとめ/一歩の順で並べる。\n"
            "【分量と具体性】各H2は600〜800字を目安にし、必ず日本の読者がイメージしやすい具体例・ミニ事例を1つ以上入れる。"
            "専門用語は初出で一文説明し、箇条書きは前後に説明文を置いて唐突に始めない。B2B SaaSの話は「一例」として扱い、全体の説明を優先する。\n"
            "【ツール名の扱い】GA4 / Consent Mode / P-Max などは代表例として触れるだけ。設定手順や細かな機能列挙には踏み込まない。\n"
            "【差別化】渡されたSERPスナップ/差別化トピックを1〜2個本文に織り込み、他社が薄い切り口を補強する。"
        )
        additions_user = (
            "このセクションでは「◯◯とは」記事らしく、全体像を俯瞰してから必要な部分だけを深掘りしてください。"
            "計測・広告に偏らず、チャネル比較や読者の最初の一歩を示すことを優先します。"
        )
        patched = dict(layers)
        patched["system"] = "\n\n".join(filter(None, [layers.get("system", ""), additions_system])).strip()
        patched["developer"] = "\n\n".join(filter(None, [layers.get("developer", ""), additions_developer])).strip()
        patched["user"] = "\n\n".join(filter(None, [layers.get("user", ""), additions_user])).strip()
        return patched

    @staticmethod
    def _render_reader_profile(persona: Dict[str, Any], default_tone: str) -> str:
        name = persona.get("name") or "読者"
        goals = " / ".join(persona.get("goals", [])[:3]) or "意思決定に役立つ情報を得たい"
        pains = " / ".join(persona.get("pain_points", [])[:3]) or "確かな根拠が集まらない"
        tone = persona.get("tone") or default_tone
        return f"{name}（トーン: {tone}） | 目標: {goals} | 課題: {pains}"

    def _derive_section_goal(self, heading: str, context: PipelineContext) -> str:
        persona_name = context.persona.get("name") or "読者"
        mission = context.writer_persona.get("mission") if isinstance(context.writer_persona, dict) else None
        mission_clause = mission or "迷いを解いて行動を後押しする"
        return f"{persona_name}が「{heading}」を理解し、{mission_clause}"

    @staticmethod
    def _scan_phrases(texts: List[str], phrases: List[str]) -> List[str]:
        hits: List[str] = []
        for phrase in phrases:
            for text in texts:
                if phrase and phrase in text:
                    hits.append(phrase)
                    break
        return hits

    @staticmethod
    def _count_hits(text: str, keywords: List[str]) -> int:
        """Count occurrences of keywords in text."""
        count = 0
        for keyword in keywords:
            if not keyword:
                continue
            count += len(re.findall(re.escape(keyword), text))
        return count

    @staticmethod
    def _prioritize_sources(sources: List[Dict[str, Any]], preferred_patterns: List[str]) -> List[Dict[str, Any]]:
        if not sources or not preferred_patterns:
            return list(sources)

        def score(entry: Dict[str, Any]) -> int:
            target = (entry.get("uri") or entry.get("url") or entry.get("title") or "").lower()
            for pattern in preferred_patterns:
                if pattern.lower() in target:
                    return 0
            return 1

        return sorted(sources, key=score)

    def _maybe_apply_style_rewrite(self, draft: Dict, context: PipelineContext) -> Dict[str, Any]:
        diagnostics = {
            "style_rewritten": False,
            "style_rewrite_metrics": None,
            "sections_original": None,
            "sections_rewritten": None,
            "validation_warnings": [],
        }
        if os.getenv("ENABLE_STYLE_REWRITE", "false").lower() != "true":
            return diagnostics
        if not self.style_rewriter or not self.ai_gateway:
            logger.info("Style rewrite requested but AI gateway is not available for job %s", context.job_id)
            return diagnostics

        sections = draft.get("sections")
        if not isinstance(sections, list) or not sections:
            logger.warning("Job %s: skipping style rewrite (no sections)", context.job_id)
            return diagnostics

        paragraph_total = self._count_rewritable_paragraphs(sections)
        if paragraph_total == 0:
            logger.info("Job %s: skipping style rewrite (no paragraphs)", context.job_id)
            return diagnostics

        sample_mode = os.getenv("STYLE_REWRITE_SAMPLE_ONLY", "false").lower() == "true"
        try:
            configured_workers = int(os.getenv("STYLE_REWRITE_MAX_WORKERS", self.max_workers))
        except ValueError:
            configured_workers = self.max_workers
        max_workers = max(1, configured_workers)
        processed_count = min(paragraph_total, 3) if sample_mode else paragraph_total
        save_variants = os.getenv("SAVE_AB_VARIANTS", "false").lower() == "true"
        original_sections = deepcopy(sections) if save_variants else None

        logger.info(
            "Job %s: starting style rewrite (paragraphs=%d, sample=%s, workers=%d)",
            context.job_id,
            processed_count,
            sample_mode,
            max_workers,
        )
        start_time = time.time()
        try:
            rewritten_sections = self.style_rewriter.rewrite_sections(
                sections=sections,
                max_workers=max_workers,
                sample_only=sample_mode,
            )
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.warning("Job %s: style rewrite failed (%s)", context.job_id, exc)
            return diagnostics
        elapsed = time.time() - start_time
        draft["sections"] = rewritten_sections

        diagnostics["style_rewritten"] = True
        diagnostics["style_rewrite_metrics"] = {
            "elapsed_seconds": elapsed,
            "paragraph_count": processed_count,
            "seconds_per_paragraph": elapsed / max(processed_count, 1),
            "total_paragraph_count": paragraph_total,
            "sample_only": sample_mode,
        }
        if save_variants and original_sections is not None:
            diagnostics["sections_original"] = original_sections
            diagnostics["sections_rewritten"] = deepcopy(rewritten_sections)
        logger.info(
            "Job %s: style rewrite completed in %.2fs (%.2fs/paragraph)",
            context.job_id,
            elapsed,
            elapsed / max(processed_count, 1),
        )
        return diagnostics

    @staticmethod
    def _count_rewritable_paragraphs(sections: List[Dict[str, Any]]) -> int:
        count = 0
        for section in sections:
            for paragraph in section.get("paragraphs", []):
                text = str(paragraph.get("text") or "").strip()
                if text:
                    count += 1
        return count

    def _render_markdown_snapshot(self, draft: Dict, outline: Dict, context: PipelineContext) -> str:
        sections = draft.get("sections", []) if isinstance(draft, dict) else []
        lines: List[str] = []
        title = ""
        if isinstance(outline, dict):
            title = str(outline.get("title") or outline.get("provisional_title") or "").strip()
        if not title:
            title = str(draft.get("title") or context.primary_keyword or "生成ドラフト").strip()
        lines.append(f"# {title}")
        reader_note = ""
        if isinstance(outline, dict):
            reader_note = str(outline.get("reader_note") or "").strip()
        if reader_note:
            lines.append(reader_note)
            lines.append("")

        for section in sections:
            h2_title = str(section.get("h2") or section.get("heading") or "").strip()
            if not h2_title:
                continue
            lines.append(f"## {h2_title}")
            for paragraph in section.get("paragraphs", []):
                text = str(paragraph.get("text") or "").strip()
                if text:
                    lines.append(text)
                    lines.append("")

        return "\n".join(lines)

    def _collect_structure_warnings(self, markdown_snapshot: str) -> List[str]:
        if not markdown_snapshot.strip():
            return []

        warnings: List[str] = []
        warnings.extend(self.structure_validator.validate_headings(markdown_snapshot))
        warnings.extend(self.structure_validator.validate_sentence_length(markdown_snapshot))
        warnings.extend(self.structure_validator.check_style_consistency(markdown_snapshot))

        deduped: List[str] = []
        seen = set()
        for warning in warnings:
            if warning and warning not in seen:
                deduped.append(warning)
                seen.add(warning)
        return deduped

    def _generate_editor_checklist(self, warnings: List[str]) -> str:
        template_path = Path(__file__).resolve().parents[3] / "shared" / "prompts" / "editor_checklist.txt"
        try:
            template = template_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            template = "自動検出された警告:\n{{VALIDATION_WARNINGS}}"

        warnings_text = "\n".join(f"- {warning}" for warning in warnings) if warnings else "（特になし）"
        return template.replace("{{VALIDATION_WARNINGS}}", warnings_text)

    def _generate_grounded_content(
        self,
        prompt: Optional[str] = None,
        *,
        messages: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        log_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate content with the configured OpenAI gateway."""
        self._log_prompt_snapshot(prompt=prompt, messages=messages, log_info=log_info)
        if not self.ai_gateway:
            logger.error("AI Gateway not available - cannot generate content")
            raise RuntimeError("AI Gateway is not initialized. Please configure OPENAI_API_KEY or GCP credentials.")

        try:
            result = self.ai_gateway.generate_with_grounding(
                prompt=prompt,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            logger.info("Generated content: %d characters", len(result.get("text", "")))
            return result
        except Exception as e:
            # 失敗時もプロンプトを残す
            try:
                error_info = dict(log_info or {})
                error_info["error"] = str(e)
                self._log_prompt_snapshot(prompt=prompt, messages=messages, log_info=error_info)
            except Exception:
                pass
            logger.error("Content generation failed: %s", e)
            raise

    def _log_prompt_snapshot(
        self,
        prompt: Optional[str],
        messages: Optional[List[Dict[str, str]]],
        log_info: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Optionally log prompt/messages for traceability (controlled via LOG_PROMPTS)."""
        if not getattr(self.settings, "log_prompts", False):
            return
        try:
            level_name = str(getattr(self.settings, "log_prompts_severity", "INFO")).upper()
            severity = getattr(logging, level_name, logging.INFO)
        except Exception:
            severity = logging.INFO
        try:
            max_chars = int(getattr(self.settings, "log_prompts_max_chars", 2000) or 0)
        except Exception:
            max_chars = 2000
        info = log_info or {}
        stage = str(info.get("stage") or "unspecified")
        heading = str(info.get("heading") or "")
        level = str(info.get("level") or "")
        job_id = str(info.get("job_id") or "")
        draft_id = str(info.get("draft_id") or "")
        label = f"stage={stage} heading={heading} level={level} job_id={job_id} draft_id={draft_id}"

        if messages:
            rendered_messages = []
            for entry in messages:
                role = str(entry.get("role") or "unknown")
                content = str(entry.get("content") or "")
                rendered_messages.append(f"{role}: {content}")
            text_blob = "\n---\n".join(rendered_messages)
        else:
            text_blob = str(prompt or "")

        if max_chars > 0 and len(text_blob) > max_chars:
            preview = text_blob[:max_chars]
            truncated = True
        else:
            preview = text_blob
            truncated = False

        logger.log(severity, "PromptSnapshot %s truncated=%s preview=\n%s", label, truncated, preview)

    def _generate_faq(self, context: PipelineContext) -> List[Dict]:
        """Generate FAQ section using the OpenAI gateway."""
        persona_name = context.persona.get("name", "読者")
        pain_points = context.persona.get("pain_points", [])

        faq_items = []
        for pain in pain_points[:3]:
            prompt = f"{persona_name}が抱える「{pain}」という課題に対する解決策を簡潔に説明してください。"
            result = self._generate_grounded_content(
                prompt,
                temperature=context.llm_temperature,
                log_info={
                    "stage": "faq",
                    "heading": f"FAQ: {pain}",
                    "job_id": context.job_id,
                    "draft_id": context.draft_id,
                },
            )
            raw_answer = result.get("text")
            normalized_answer = raw_answer.strip() if isinstance(raw_answer, str) else ""
            answer_text = normalized_answer or "課題に対する実務的な解決策を提示します。"
            faq_items.append({
                "question": pain,
                "answer": answer_text,
                "citations": result.get("citations", []),
            })

        if not faq_items:
            faq_items.append({
                "question": f"{persona_name}が抱える疑問は？",
                "answer": "想定される疑問に対して根拠付きで回答します。",
                "citations": [],
            })

        return faq_items

    def extract_conclusion(self, context: PipelineContext) -> Dict[str, Any]:
        logger.info("Deriving conclusion for job %s", context.job_id)
        keyword_surface = self._sanitize_keyword_surface(context.primary_keyword)
        serp_insights: List[Dict[str, Any]] = []
        for entry in (context.serp_snapshot or [])[:6]:
            serp_insights.append({
                "title": entry.get("title", "")[:120],
                "summary": entry.get("summary", "")[:200],
                "key_points": entry.get("key_points", [])[:4],
                "url": entry.get("url"),
            })
        persona = context.persona or {}
        persona_payload = {
            "name": persona.get("name"),
            "goals": persona.get("goals", [])[:3],
            "pain_points": persona.get("pain_points", [])[:3],
            "job_to_be_done": persona.get("job_to_be_done"),
        }
        payload = {
            "primary_keyword": context.primary_keyword,
            "intent": context.intent,
            "article_type": context.article_type,
            "persona": persona_payload,
            "serp_insights": serp_insights,
            "gap_topics": context.serp_gap_topics[:5],
        }
        prompt = (
            "以下の情報を読み、検索ユーザーの疑問を最も解消する結論を整理してください。"
            "必ず JSON 形式のみで出力し、余計な文章は書かないでください。\n\n"
            "期待するJSON構造:\n"
            "{\n"
            '  "main_conclusion": "検索意図に対する結論",\n'
            '  "supporting_points": ["結論を支える理由", "..."],\n'
            '  "evidence_needed": ["主張を裏付けるデータや事例", "..."],\n'
            '  "differentiation_angle": "競合記事との差別化視点"\n'
            "}\n\n"
            f"入力データ:\n{json.dumps(payload, ensure_ascii=False)}"
        )
        result_payload: Dict[str, Any] = {}
        try:
            result = self._generate_grounded_content(
                prompt,
                temperature=0.35,
                max_tokens=900,
                log_info={
                    "stage": "conclusion",
                    "job_id": context.job_id,
                    "draft_id": context.draft_id,
                },
            )
            raw_text = str(result.get("text") or "").strip()
            normalized = self._strip_json_fence(raw_text)
            parsed = json.loads(normalized)
            if isinstance(parsed, dict):
                result_payload = parsed
        except Exception as exc:
            logger.warning("Job %s: extract_conclusion failed (%s)", context.job_id, exc)

        default_conclusion = {
            "main_conclusion": (
                result_payload.get("main_conclusion")
                or f"{keyword_surface}で成果を出すには、読者のゴールに直結する実務的な優先順位を示すことが不可欠です。"
            ),
            "supporting_points": [],
            "evidence_needed": [],
            "differentiation_angle": result_payload.get("differentiation_angle") or "",
        }

        supporting_points = result_payload.get("supporting_points")
        if isinstance(supporting_points, list) and supporting_points:
            default_conclusion["supporting_points"] = [
                str(point).strip() for point in supporting_points if str(point).strip()
            ]
        else:
            fallback_points = context.serp_gap_topics[:3] or ["最新データと実例で根拠を提示", "施策の優先順位を明示", "失敗パターンと回避策をセットで提示"]
            default_conclusion["supporting_points"] = fallback_points

        evidence = result_payload.get("evidence_needed")
        if isinstance(evidence, list) and evidence:
            default_conclusion["evidence_needed"] = [
                str(item).strip() for item in evidence if str(item).strip()
            ]
        else:
            default_conclusion["evidence_needed"] = [
                "最新の統計データ（国内/業界別）",
                "成功/失敗事例の比較",
            ]

        if not default_conclusion["differentiation_angle"]:
            default_conclusion["differentiation_angle"] = "SERP上位が触れていない読者の実務課題に寄り添う"

        logger.info("Job %s: main conclusion resolved to %s", context.job_id, default_conclusion["main_conclusion"])
        return default_conclusion

    def refine_draft(
        self,
        context: PipelineContext,
        outline: Dict,
        draft: Dict,
        conclusion: Optional[Dict[str, Any]] = None,
    ) -> Dict:
        logger.info("Refining draft for job %s", context.job_id)
        if not isinstance(draft, dict) or "sections" not in draft:
            logger.info("Job %s: skipping refine_draft (missing sections)", context.job_id)
            return draft

        sections = draft.get("sections") or []
        if not sections:
            logger.info("Job %s: skipping refine_draft (empty sections)", context.job_id)
            return draft

        outline_headings = [
            str(section.get("text") or "").strip()
            for section in outline.get("h2", [])
            if str(section.get("text") or "").strip()
        ]

        trimmed_sections: List[Dict[str, Any]] = []
        for section in sections[:10]:
            heading = str(section.get("h2") or section.get("heading") or "").strip()
            trimmed_paragraphs: List[str] = []
            for paragraph in section.get("paragraphs", [])[:3]:
                text = str(paragraph.get("text") or "").strip()
                if text:
                    trimmed_paragraphs.append(text[:500])
            trimmed_sections.append({"heading": heading, "paragraphs": trimmed_paragraphs})

        prompt_payload = {
            "primary_keyword": context.primary_keyword,
            "intent": context.intent,
            "tone": context.tone,
            "outline_headings": outline_headings,
            "sections": trimmed_sections,
            "faq": draft.get("faq", []),
            "claims": draft.get("claims", []),
            "conclusion": conclusion or {},
        }
        prompt_json = json.dumps(prompt_payload, ensure_ascii=False)
        conclusion_clause = ""
        if conclusion and conclusion.get("main_conclusion"):
            conclusion_clause = f"\n- 以下の結論を軸に一貫性を保つこと: {conclusion['main_conclusion']}"
        instruction = (
            "あなたはシニアSEO編集長です。以下のJSONで渡すドラフトを推敲し、"
            "論理構成・重複・専門用語・結論との整合性を整えてください。\n\n"
            "必ず下記のフォーマットでJSONのみを出力してください:\n"
            "{\n"
            '  "sections": [\n'
            '    {"h2": "見出し", "paragraphs": [{"text": "本文", "citations": ["..."]}]}\n'
            "  ],\n"
            '  "faq": [{"question": "...", "answer": "..."}],\n'
            '  "claims": [{"id": "...", "text": "...", "citations": ["..."]}],\n'
            '  "refinement_notes": ["修正内容のメモ"]\n'
            "}\n\n"
            "- 見出し数は必要に応じて微調整しても良いが、情報は削りすぎない\n"
            "- 数値・引用URLは可能な限り保持し、変更した場合は notes に理由を書く\n"
            "- 各 paragraph は具体的で重複のない文章にする\n"
            "- FAQ/claims は要点のみ残し、不要な重複は削除\n"
            "- refinement_notes にはユーザーが後から理解できる粒度で修正理由を列挙\n\n"
            "- 見出しや本文に含まれるテンプレートのラベル（例:「リード文：」「Q/U:」「E/S:」「QUESTで提示」など）は削除または自然な文章に置き換える\n"
            "- Markdownの見出しレベルはH1をタイトルのみに1回だけ使用し、本文中はH2/H3のみを用いる。複数のH1があれば適切にH2/H3へ下げる\n"
            "- 同じ内容を繰り返す段落は統合・削除し、各セクションが指定レンジに収まるよう過剰な部分は簡潔に要約する\n\n"
            f"{conclusion_clause}\n"
            "=== 元ドラフト(JSON) ===\n"
            f"{prompt_json}\n"
            "========================"
        )

        try:
            result = self._generate_grounded_content(
                instruction,
                temperature=max(0.2, min(context.llm_temperature, 0.6)),
                max_tokens=2800,
                log_info={
                    "stage": "refine_draft",
                    "job_id": context.job_id,
                    "draft_id": context.draft_id,
                },
            )
            raw_text = str(result.get("text") or "").strip()
            normalized_text = self._strip_json_fence(raw_text)
            refined_payload = json.loads(normalized_text)
        except Exception as exc:
            logger.warning("Job %s: refine_draft failed (%s)", context.job_id, exc)
            return draft

        if not isinstance(refined_payload, dict):
            logger.warning("Job %s: refine_draft response is not dict", context.job_id)
            return draft

        original_sections: List[Dict[str, Any]] = sections
        updated_sections = refined_payload.get("sections")

        def merge_sections() -> List[Dict[str, Any]]:
            if not isinstance(updated_sections, list) or not updated_sections:
                return original_sections
            merged: List[Dict[str, Any]] = []
            for idx, original in enumerate(original_sections):
                updated = updated_sections[idx] if idx < len(updated_sections) else {}
                new_h2 = str(updated.get("h2") or "").strip()
                merged_section = {
                    "h2": new_h2 or original.get("h2"),
                    "paragraphs": [],
                }
                updated_paragraphs = updated.get("paragraphs") if isinstance(updated, dict) else None
                if isinstance(updated_paragraphs, list) and updated_paragraphs:
                    for p_idx, paragraph in enumerate(updated_paragraphs):
                        base_paragraphs = original.get("paragraphs", [])
                        base = base_paragraphs[p_idx] if p_idx < len(base_paragraphs) else {}
                        text = str(paragraph.get("text") or "").strip() or base.get("text", "")
                        citations = paragraph.get("citations")
                        if not citations and isinstance(base, dict):
                            citations = base.get("citations", [])
                        merged_section["paragraphs"].append({
                            "heading": paragraph.get("heading") or base.get("heading") or merged_section["h2"],
                            "text": text,
                            "citations": citations or [],
                            "claim_id": paragraph.get("claim_id") or base.get("claim_id"),
                        })
                else:
                    merged_section["paragraphs"] = original.get("paragraphs", [])
                merged.append(merged_section)
            if len(updated_sections) > len(original_sections):
                for extra_section in updated_sections[len(original_sections):]:
                    heading = str(extra_section.get("h2") or "").strip() or "追加セクション"
                    extra_paragraphs: List[Dict[str, Any]] = []
                    for paragraph in extra_section.get("paragraphs", []):
                        text = str(paragraph.get("text") or "").strip()
                        if not text:
                            continue
                        extra_paragraphs.append({
                            "heading": paragraph.get("heading") or heading,
                            "text": text,
                            "citations": paragraph.get("citations", []),
                            "claim_id": paragraph.get("claim_id"),
                        })
                    merged.append({"h2": heading, "paragraphs": extra_paragraphs})
            return merged

        refined_sections = merge_sections()

        def normalize_entries(original: List[Dict[str, Any]], updated: Any, required_keys: List[str], *, require_id: bool = False) -> List[Dict[str, Any]]:
            if not isinstance(updated, list) or not updated:
                return original
            sanitized: List[Dict[str, Any]] = []
            for idx, item in enumerate(updated):
                if not isinstance(item, dict):
                    continue
                entry: Dict[str, Any] = {}
                for key in required_keys:
                    value = item.get(key)
                    if isinstance(value, str):
                        entry[key] = value.strip()
                    else:
                        entry[key] = value
                if any(not entry.get(key) for key in required_keys):
                    continue
                if require_id and not entry.get("id"):
                    entry["id"] = f"{context.draft_id}-claim-{len(sanitized)+1}"
                entry["citations"] = item.get("citations", [])
                sanitized.append(entry)
            return sanitized or original

        refined_faq = normalize_entries(draft.get("faq", []), refined_payload.get("faq"), ["question", "answer"])
        refined_claims = normalize_entries(
            draft.get("claims", []),
            refined_payload.get("claims"),
            ["id", "text"],
            require_id=True,
        )

        notes = []
        if isinstance(refined_payload.get("refinement_notes"), list):
            notes = [str(note).strip() for note in refined_payload["refinement_notes"] if str(note).strip()]

        refined_draft = dict(draft)
        refined_draft["sections"] = refined_sections
        refined_draft["faq"] = refined_faq
        refined_draft["claims"] = refined_claims
        if notes:
            refined_draft["refinement_notes"] = notes

        logger.info("Job %s: refine_draft applied %d notes", context.job_id, len(notes))
        return refined_draft

    def finalize_title(
        self,
        context: PipelineContext,
        outline: Dict,
        draft: Dict,
        conclusion: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        provisional_title = str(
            outline.get("provisional_title")
            or outline.get("title")
            or self._build_quest_title(context.primary_keyword, context)
        )
        sections_payload: List[Dict[str, Any]] = []
        if isinstance(draft, dict):
            if "sections" in draft:
                sections_payload = draft.get("sections") or []
            elif isinstance(draft.get("draft"), dict):
                sections_payload = draft["draft"].get("sections", [])

        key_points: List[str] = []
        for section in sections_payload:
            heading = str(section.get("h2") or section.get("heading") or "").strip()
            snippet = ""
            paragraphs = section.get("paragraphs", [])
            if isinstance(paragraphs, list):
                for paragraph in paragraphs:
                    text = str(paragraph.get("text") or "").strip()
                    if text:
                        snippet = re.sub(r"\s+", " ", text)[:200]
                        break
            if heading or snippet:
                fragment = f"{heading}: {snippet}" if heading and snippet else heading or snippet
                fragment = fragment.strip()
                if fragment:
                    key_points.append(fragment)
            if len(key_points) >= 3:
                break

        if not key_points and provisional_title:
            key_points.append(provisional_title)

        refinement_notes: List[str] = []
        if isinstance(draft, dict):
            refinement_notes = draft.get("refinement_notes") or []
            if not refinement_notes and isinstance(draft.get("draft"), dict):
                refinement_notes = draft["draft"].get("refinement_notes") or []
        notes_excerpt = "\n".join(f"- {note}" for note in refinement_notes[:3]) if refinement_notes else ""
        bullet_points = "\n".join(f"- {point}" for point in key_points if point)
        conclusion_line = ""
        support_clause = ""
        if conclusion and conclusion.get("main_conclusion"):
            conclusion_line = f"最終結論: {conclusion['main_conclusion']}\n"
            supporting_points = [
                str(point).strip() for point in conclusion.get("supporting_points", []) if str(point).strip()
            ]
            if supporting_points:
                support_clause = "結論を支える要素:\n" + "\n".join(f"- {point}" for point in supporting_points[:3]) + "\n"
        prompt = (
            "あなたは検索意図と本文を把握したSEO編集長です。"
            "以下の情報から、記事の価値を最も正確かつ魅力的に表す日本語タイトルを1つだけ生成してください。\n\n"
            f"主キーワード: {context.primary_keyword}\n"
            f"仮タイトル: {provisional_title}\n"
            f"{conclusion_line}"
            f"{support_clause}"
            f"記事の要点:\n{bullet_points or '- 要点情報なし'}\n"
            f"推敲メモ:\n{notes_excerpt or '- メモなし'}\n\n"
            "要件:\n"
            "1. 60文字以内\n"
            "2. 読者の課題と結論が一文で伝わる\n"
            "3. キーワードを自然に含め、誇張しすぎない\n\n"
            "出力: 最終タイトルのみを1行で返す。"
        )

        generated_text = ""
        temperature = min(max(context.llm_temperature, 0.1), 0.85)
        try:
            result = self._generate_grounded_content(
                prompt,
                temperature=temperature,
                log_info={
                    "stage": "finalize_title",
                    "job_id": context.job_id,
                    "draft_id": context.draft_id,
                },
            )
            generated_text = result.get("text", "") if isinstance(result, dict) else ""
        except Exception as exc:
            logger.warning("Job %s: finalize_title failed (%s)", context.job_id, exc)

        extracted_title = self._extract_title_line(generated_text) if generated_text else ""
        final_title = extracted_title or provisional_title
        rationale_source = ", ".join(key_points[:2]) if key_points else "outline情報不足"
        return {
            "final_title": final_title,
            "provisional_title": provisional_title,
            "title_variants": [],
            "title_rationale": f"要点: {rationale_source}",
        }

    def generate_meta(self, prompt: Dict, context: PipelineContext, final_title: Optional[str] = None) -> Dict:
        keyword = prompt["primary_keyword"]
        keyword_surface = self._sanitize_keyword_surface(keyword)
        cta = context.cta or "資料請求はこちら"
        preferred_title = (final_title or "").strip()
        default_titles = [f"{keyword_surface} 完全ガイド", f"{keyword_surface} 比較ポイントまとめ"]
        title_options = default_titles.copy()
        if preferred_title:
            title_options = [preferred_title, *[title for title in default_titles if title != preferred_title]]
        description_focus = preferred_title or f"{keyword_surface} の最新情報"
        meta_payload = {
            "title_options": title_options,
            "description_options": [
                f"{description_focus}をわかりやすく解説",
                f"{keyword_surface} の選び方と成功事例",
            ],
            "og": {
                "title": preferred_title or f"{keyword_surface} のベストプラクティス",
                "description": f"{keyword_surface} に関するノウハウを網羅",
            },
            "cta": cta,
            "preferred_output": context.output_format,
        }
        if preferred_title:
            meta_payload["final_title"] = preferred_title
        return meta_payload

    def propose_links(self, prompt: Dict, context: PipelineContext) -> List[Dict]:
        """Propose internal links using BigQuery Vector Search."""
        keyword = prompt["primary_keyword"]
        keyword_surface = self._sanitize_keyword_surface(keyword)
        persona_goals = context.persona.get("goals", [])

        if not self.link_repository or not self.link_repository.is_enabled:
            logger.info("Link repository not available; skipping internal link suggestions")
            return []

        try:
            candidates = self.link_repository.search(keyword, persona_goals, limit=5)
            results = []
            for candidate in candidates:
                results.append({
                    "url": candidate["url"],
                    "title": candidate["title"],
                    "anchor": f"{keyword_surface} と関連する {candidate['title']}",
                    "score": candidate.get("score", 0.0),
                    "snippet": candidate.get("snippet", ""),
                })
            logger.info("Proposed %d internal links for keyword: %s", len(results), keyword)
            return results
        except Exception as e:
            logger.error("Link proposal failed: %s", e)
            return []

    def evaluate_quality(
        self,
        draft: Dict,
        context: PipelineContext,
        outline: Optional[Dict] = None,
        title_result: Optional[Dict[str, Any]] = None,
    ) -> Dict:
        claims_without_citations = [c for c in draft.get("claims", []) if not c.get("citations")]
        duplication_score = 0.08 if context.article_type == "ranking" else 0.12
        sections_payload = draft
        if isinstance(draft, dict) and "sections" not in draft and isinstance(draft.get("draft"), dict):
            sections_payload = draft.get("draft", {})
        sections = sections_payload.get("sections", []) if isinstance(sections_payload, dict) else []
        paragraphs = [p for section in sections for p in section.get("paragraphs", [])]
        has_citations = any(p.get("citations") for p in paragraphs)
        unique_citations = set()
        text_segments: List[str] = []
        for paragraph in paragraphs:
            text = paragraph.get("text", "")
            if isinstance(text, str) and text.strip():
                text_segments.append(text)
            for citation in paragraph.get("citations", []):
                if isinstance(citation, str):
                    unique_citations.add(citation)
                elif isinstance(citation, dict):
                    uri = citation.get("uri") or citation.get("url")
                    if uri:
                        unique_citations.add(uri)

        citation_count = len(unique_citations)
        numeric_facts = sum(len(re.findall(r"\d+[\d,\.]*", text)) for text in text_segments)
        ng_hits = self._scan_phrases(text_segments, NG_PHRASES)
        abstract_hits = self._scan_phrases(text_segments, ABSTRACT_PATTERNS)

        headings: List[str] = []
        for section in sections:
            heading = str(section.get("h2") or section.get("heading") or "").strip()
            if heading:
                headings.append(heading)
        if outline and isinstance(outline, dict):
            for section in outline.get("h2", []):
                heading = str(section.get("text") or "").strip()
                if heading:
                    headings.append(heading)
        title_text = ""
        if isinstance(title_result, dict):
            title_text = str(title_result.get("final_title") or title_result.get("provisional_title") or "").strip()

        writer_rubric = self._score_writer_rubric(
            context=context,
            sections=sections,
            headings=headings,
            title_text=title_text,
            text_segments=text_segments,
            numeric_facts=numeric_facts,
        )
        rubric_summary = writer_rubric.get("summary") or f"{context.quality_rubric or 'writer'} rubric"

        style_flags: List[str] = []
        existing_flags = draft.get("quality", {}).get("style_violations") if isinstance(draft, dict) else []
        if isinstance(existing_flags, list):
            style_flags.extend(str(flag) for flag in existing_flags)
        if duplication_score >= 0.3:
            style_flags.append("content-too-similar")
        if citation_count < 2:
            style_flags.append("insufficient-citations")
        if numeric_facts < 3:
            style_flags.append("insufficient-numeric-evidence")
        style_flags.extend([f"ng_phrase:{phrase}" for phrase in ng_hits])
        style_flags.extend([f"abstract:{phrase}" for phrase in abstract_hits])
        # Deduplicate while preserving order
        seen_flags = set()
        deduped_flags: List[str] = []
        for flag in style_flags:
            if flag not in seen_flags:
                seen_flags.add(flag)
                deduped_flags.append(flag)

        return {
            "similarity": duplication_score,
            "claims": claims_without_citations,
            "style_violations": deduped_flags,
            "is_ymyl": context.article_type in {"information", "comparison"} and not has_citations,
            "rubric": writer_rubric,
            "rubric_summary": rubric_summary,
            "citation_count": citation_count,
            "numeric_facts": numeric_facts,
            "ng_phrases": ng_hits,
            "abstract_phrases": abstract_hits,
        }

    def _score_writer_rubric(
        self,
        context: PipelineContext,
        sections: List[Dict[str, Any]],
        headings: List[str],
        title_text: str,
        text_segments: List[str],
        numeric_facts: int,
    ) -> Dict[str, Any]:
        """Score writer-facing rubric (intent, balance, specificity, structure)."""
        full_text = "\n".join(text_segments)
        first_block = full_text[:400]
        keyword_surface = self._sanitize_keyword_surface(context.primary_keyword)
        is_glossary = context.keyword_preset == "glossary" or self._is_glossary_keyword(
            context.primary_keyword,
            context.article_type,
        )

        has_definition = bool(re.search(r"とは", first_block)) or bool(
            re.search(rf"{re.escape(keyword_surface)}[^。\n]*とは", first_block)
        )
        has_intro = bool(re.search(r"(この記事|本記事|読み終わると|わかること)", first_block))
        has_summary_heading = any("まとめ" in h or "結論" in h for h in headings[-2:]) if headings else False

        foundational_terms = [
            "SEO",
            "コンテンツ",
            "オウンド",
            "SNS",
            "メール",
            "MA",
            "マーケティングオートメーション",
            "チャネル",
            "施策",
            "ファネル",
        ]
        measurement_terms = [
            "GA4",
            "Google広告",
            "広告",
            "計測",
            "トラッキング",
            "タグ",
            "P-Max",
            "PMax",
            "アトリビューション",
            "コンバージョン",
            "BigQuery",
            "DDA",
        ]
        foundation_hits = self._count_hits(full_text, foundational_terms)
        measurement_hits = self._count_hits(full_text, measurement_terms)
        balance_ratio = (foundation_hits + 1) / (measurement_hits + 1)

        section_count = max(len(sections), 1)
        section_example_hits = 0
        for section in sections:
            if any(re.search(r"(例|事例|ケース|例えば)", str(p.get("text", ""))) for p in section.get("paragraphs", [])):
                section_example_hits += 1
        example_ratio = section_example_hits / section_count

        sentences = [s for text in text_segments for s in re.split(r"[。！!？?]", text) if s.strip()]
        avg_sentence_len = sum(len(s) for s in sentences) / len(sentences) if sentences else 0
        desu_count = sum(text.count("です") + text.count("ます") for text in text_segments)
        desu_ratio = desu_count / max(len(sentences), 1)
        bullet_count = sum(
            1 for text in text_segments for line in text.splitlines() if line.strip().startswith(("-", "・", "●", "*"))
        )

        def clamp_score(value: float) -> int:
            return max(1, min(5, int(round(value))))

        intent_score = 3
        if has_definition:
            intent_score += 2
        elif is_glossary:
            intent_score -= 1
        if balance_ratio < 0.6:
            intent_score -= 1
        intent_score = clamp_score(intent_score)

        balance_score = clamp_score(
            3
            + (1 if balance_ratio >= 1 else 0)
            + (1 if foundation_hits >= 4 else 0)
            - (1 if measurement_hits > foundation_hits * 1.8 else 0)
        )

        specificity_score = clamp_score(
            2
            + (2 if example_ratio >= 0.6 else 1 if example_ratio >= 0.3 else 0)
            + (1 if numeric_facts >= 3 else 0)
        )

        title_has_keyword = False
        if title_text:
            title_has_keyword = keyword_surface in title_text or f"{keyword_surface}とは" in title_text
        heading_coverage = sum(
            1
            for key in ("チャネル", "施策", "KPI", "成功", "失敗", "まとめ")
            if any(key in h for h in headings)
        )
        heading_score = clamp_score(
            2
            + (2 if title_has_keyword or not title_text else -1 if is_glossary else 0)
            + (1 if heading_coverage >= 2 else 0)
            + (1 if has_summary_heading else 0)
        )

        opening_score = clamp_score(
            2 + (1 if has_intro else 0) + (1 if has_definition else 0) + (1 if has_summary_heading else 0)
        )

        tone_score = clamp_score(
            3 + (1 if desu_ratio >= 0.25 else -1) + (1 if avg_sentence_len <= 70 else -1)
        )
        if context.tone == "formal" and desu_ratio < 0.2:
            tone_score = clamp_score(tone_score - 1)

        readability_score = clamp_score(
            3 + (1 if avg_sentence_len <= 70 else 0) + (1 if bullet_count <= len(text_segments) else -1)
        )

        scores_numeric = {
            "検索意図・定義明示": intent_score,
            "トピック網羅・バランス": balance_score,
            "具体例・事例の充実": specificity_score,
            "タイトル/見出しの適合": heading_score,
            "冒頭とまとめの明瞭さ": opening_score,
            "トーン・文体": tone_score,
            "読みやすさ": readability_score,
        }
        avg_score = round(sum(scores_numeric.values()) / len(scores_numeric), 1)
        rubric = {key: f"{value}/5" for key, value in scores_numeric.items()}
        rubric["summary"] = (
            f"ライターRubric 平均 {avg_score}/5 "
            f"(intent:{scores_numeric['検索意図・定義明示']}, balance:{scores_numeric['トピック網羅・バランス']}, "
            f"examples:{scores_numeric['具体例・事例の充実']})"
        )
        return rubric

    def bundle_outputs(self, context: PipelineContext, outline: Dict, draft: Dict, meta: Dict, links: List[Dict], quality: Dict) -> Dict:
        metadata = {
            "job_id": context.job_id,
            "draft_id": context.draft_id,
            "prompt_version": context.prompt_version,
            "article_type": context.article_type,
            "output_format": context.output_format,
            "heading_mode": context.heading_mode,
            "primary_keyword": context.primary_keyword,
            "expertise_level": context.expertise_level,
            "tone": context.tone,
        }
        if context.cta:
            metadata["intended_cta"] = context.cta
        if context.quality_rubric:
            metadata["quality_rubric"] = context.quality_rubric
        if context.reference_urls:
            metadata["reference_urls"] = ", ".join(context.reference_urls)
        if context.word_count_range:
            metadata["word_count_range"] = context.word_count_range
        if context.notation_guidelines:
            metadata["notation_guidelines"] = context.notation_guidelines
        if context.writer_persona:
            try:
                metadata["writer_persona"] = json.dumps(context.writer_persona, ensure_ascii=False)
            except TypeError:
                metadata["writer_persona"] = str(context.writer_persona)
        if context.preferred_sources:
            metadata["preferred_sources"] = ", ".join(context.preferred_sources)
        if context.reference_media:
            metadata["reference_media"] = ", ".join(context.reference_media)
        if context.project_template_id:
            metadata["project_template_id"] = context.project_template_id
        if context.serp_gap_topics:
            metadata["serp_gap_topics"] = ", ".join(context.serp_gap_topics)
        if context.keyword_preset:
            metadata["keyword_preset"] = context.keyword_preset
        metadata["llm_provider"] = context.llm_provider
        metadata["llm_model"] = context.llm_model
        metadata["llm_temperature"] = f"{context.llm_temperature:.2f}"

        return {
            "outline": outline,
            "draft": draft,
            "meta": meta,
            "links": links,
            "quality": quality,
            "metadata": metadata,
        }

    def run(self, payload: Dict) -> Dict:
        start_time = time.time()
        job_id = payload["job_id"]
        logger.info("Starting pipeline for job %s", job_id)
        draft_id = payload.get("draft_id") or str(job_id).replace("-", "")[:12]
        llm_override_raw = payload.get("llm")
        if isinstance(llm_override_raw, dict):
            llm_override = dict(llm_override_raw)
        elif isinstance(llm_override_raw, str):
            llm_override = {"model": llm_override_raw}
        else:
            llm_override = {}
        try:
            self._configure_gateway(llm_override)
        except Exception as exc:
            logger.error("Failed to configure LLM provider for job %s: %s", payload["job_id"], exc)
            if not self.ai_gateway:
                fallback_provider = llm_override.get("provider") or self.settings.llm_provider or "openai"
                fallback_model = llm_override.get("model") or self._default_model_for_provider(str(fallback_provider).lower())
                fallback_temperature = float(llm_override.get("temperature") or 0.7)
                self._active_llm = {
                    "provider": str(fallback_provider).lower(),
                    "model": fallback_model,
                    "temperature": fallback_temperature,
                }

        intent = self.estimate_intent(payload)
        heading_directive = payload.get("heading_directive") or {}
        heading_mode = heading_directive.get("mode", "auto")
        heading_overrides: List[str] = heading_directive.get("headings") or []
        if isinstance(heading_overrides, str):
            heading_overrides = [line.strip() for line in heading_overrides.splitlines() if line.strip()]

        reference_urls_raw = payload.get("reference_urls") or []
        if isinstance(reference_urls_raw, str):
            reference_urls = [url.strip() for url in reference_urls_raw.splitlines() if url.strip()]
        else:
            reference_urls = [str(url).strip() for url in reference_urls_raw if str(url).strip()]

        word_range_raw = payload.get("word_count_range")
        if isinstance(word_range_raw, (list, tuple)) and len(word_range_raw) >= 2:
            word_count_range = f"{word_range_raw[0]}-{word_range_raw[1]}"
        else:
            word_count_range = self._coerce_word_count_for_preset(word_range_raw, None)

        project_id = payload.get("project_id") or self.settings.project_id
        project_defaults = get_project_defaults(project_id)
        writer_persona_raw = payload.get("writer_persona") or project_defaults.get("writer_persona") or {}
        writer_persona = dict(writer_persona_raw) if isinstance(writer_persona_raw, dict) else {}
        preferred_sources_raw = payload.get("preferred_sources") or project_defaults.get("preferred_sources", [])
        reference_media_raw = payload.get("reference_media") or project_defaults.get("reference_media", [])
        preferred_sources = [
            str(item).strip() for item in preferred_sources_raw if str(item).strip()
        ]
        reference_media = [
            str(item).strip() for item in reference_media_raw if str(item).strip()
        ]
        prompt_layers = project_defaults.get("prompt_layers", {})
        llm_provider = self._active_llm.get("provider") or self.settings.llm_provider or "openai"
        llm_model = self._active_llm.get("model") or self._default_model_for_provider(llm_provider)
        llm_temperature = float(
            self._active_llm.get("temperature")
            or llm_override.get("temperature")
            or 0.7
        )
        serp_snapshot = self._normalize_serp_snapshot(payload.get("serp_snapshot"))
        serp_gap_topics = self._derive_serp_gap_topics(serp_snapshot, payload.get("primary_keyword", ""))

        # Get expertise_level and tone from payload
        article_type = payload.get("article_type", "information")
        keyword_preset = self._infer_keyword_preset(payload.get("primary_keyword", ""), article_type)
        expertise_level = payload.get("expertise_level", "intermediate")
        expertise_level = self._coerce_expertise_level_for_preset(expertise_level, keyword_preset)
        # Apply preset-specific defaults if word_count_range was not explicitly provided
        if not word_range_raw:
            word_count_range = self._coerce_word_count_for_preset(word_count_range, keyword_preset)
        tone = payload.get("tone", "formal")

        context = PipelineContext(
            job_id=payload["job_id"],
            draft_id=draft_id,
            project_id=project_id,
            prompt_version=payload.get("prompt_version", self.settings.default_prompt_version),
            primary_keyword=payload["primary_keyword"],
            persona=payload.get("persona", {}),
            intent=intent,
            article_type=article_type,
            cta=payload.get("intended_cta"),
            heading_mode=heading_mode,
            heading_overrides=heading_overrides,
            quality_rubric=payload.get("quality_rubric"),
            reference_urls=reference_urls,
            output_format=payload.get("output_format", "html"),
            notation_guidelines=payload.get("notation_guidelines"),
            word_count_range=word_count_range,
            writer_persona=writer_persona,
            preferred_sources=preferred_sources,
            reference_media=reference_media,
            project_template_id=payload.get("project_template_id"),
            prompt_layers=prompt_layers,
            llm_provider=llm_provider,
            llm_model=llm_model,
            llm_temperature=llm_temperature,
            serp_snapshot=serp_snapshot,
            serp_gap_topics=serp_gap_topics,
            expertise_level=expertise_level,
            tone=tone,
            keyword_preset=keyword_preset,
        )
        step_start = time.time()
        conclusion = self.extract_conclusion(context)
        logger.info("Job %s: conclusion extraction took %.2f seconds", job_id, time.time() - step_start)

        step_start = time.time()
        outline = self.generate_outline(context, payload, conclusion=conclusion)
        logger.info("Job %s: outline generation took %.2f seconds", job_id, time.time() - step_start)
        citations: List[Dict[str, Any]] = []
        raw_citations = payload.get("citations") or []
        for item in raw_citations:
            if isinstance(item, dict):
                citations.append(item)
            elif isinstance(item, str):
                citations.append({"url": item})
        if not citations and context.reference_urls:
            citations = [{"url": url} for url in context.reference_urls]
        if not citations:
            citations = [{"url": "https://www.google.com/search?q=" + payload["primary_keyword"]}]
        step_start = time.time()
        draft = self.generate_draft(context, outline, citations)
        logger.info("Job %s: draft generation took %.2f seconds", job_id, time.time() - step_start)

        step_start = time.time()
        draft = self.refine_draft(context, outline, draft, conclusion=conclusion)
        logger.info("Job %s: draft refinement took %.2f seconds", job_id, time.time() - step_start)
        style_diagnostics = self._maybe_apply_style_rewrite(draft, context)
        markdown_snapshot = self._render_markdown_snapshot(draft, outline, context)
        structure_warnings = self._collect_structure_warnings(markdown_snapshot)
        style_diagnostics["validation_warnings"] = structure_warnings
        editor_checklist = self._generate_editor_checklist(structure_warnings)
        style_diagnostics["editor_checklist"] = editor_checklist

        step_start = time.time()
        try:
            title_result = self.finalize_title(context, outline, draft, conclusion=conclusion)
        except Exception as exc:
            logger.exception("Job %s: finalize_title crashed (%s)", job_id, exc)
            fallback_title = outline.get("provisional_title") or outline.get("title") or context.primary_keyword
            title_result = {
                "final_title": fallback_title,
                "provisional_title": fallback_title,
                "title_variants": [],
                "title_rationale": "finalize_title fallback due to exception",
            }
        logger.info("Job %s: finalize_title took %.2f seconds", job_id, time.time() - step_start)

        step_start = time.time()
        meta = self.generate_meta(payload, context, final_title=title_result.get("final_title"))
        logger.info("Job %s: meta generation took %.2f seconds", job_id, time.time() - step_start)

        step_start = time.time()
        links = self.propose_links(payload, context)
        logger.info("Job %s: link proposal took %.2f seconds", job_id, time.time() - step_start)

        step_start = time.time()
        quality = self.evaluate_quality(draft, context, outline=outline, title_result=title_result)
        if style_diagnostics.get("style_rewrite_metrics"):
            quality["style_rewrite_metrics"] = style_diagnostics["style_rewrite_metrics"]
        quality["style_rewritten"] = style_diagnostics.get("style_rewritten", False)
        if structure_warnings:
            quality["validation_warnings"] = structure_warnings
        if editor_checklist:
            quality["editor_checklist"] = editor_checklist
        logger.info("Job %s: quality evaluation took %.2f seconds", job_id, time.time() - step_start)

        bundle = self.bundle_outputs(context, outline, draft, meta, links, quality)
        metadata = bundle.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
            bundle["metadata"] = metadata
        for key in ("provisional_title", "final_title"):
            value = title_result.get(key)
            if value:
                metadata[key] = str(value)
        if style_diagnostics.get("style_rewrite_metrics"):
            bundle["style_rewrite_metrics"] = style_diagnostics["style_rewrite_metrics"]
        bundle["style_rewritten"] = style_diagnostics.get("style_rewritten", False)
        if structure_warnings:
            bundle["validation_warnings"] = structure_warnings
        if style_diagnostics.get("sections_original") and style_diagnostics.get("sections_rewritten"):
            bundle["sections_original"] = style_diagnostics["sections_original"]
            bundle["sections_rewritten"] = style_diagnostics["sections_rewritten"]
        bundle["editor_checklist"] = editor_checklist
        if conclusion:
            main_conclusion = conclusion.get("main_conclusion")
            if main_conclusion:
                metadata["main_conclusion"] = str(main_conclusion)
            supporting_points = [
                str(point).strip() for point in conclusion.get("supporting_points", []) if str(point).strip()
            ]
            if supporting_points:
                metadata["conclusion_points"] = " / ".join(supporting_points[:3])
        total_time = time.time() - start_time
        logger.info("Completed pipeline for job %s in %.2f seconds (%.2f minutes)", job_id, total_time, total_time / 60)
        return bundle


def handle_pubsub_message(event, _context) -> Dict:
    # Expected to be Pub/Sub triggered Cloud Run job
    data = json.loads(event["data"]) if isinstance(event, dict) and "data" in event else event
    pipeline = DraftGenerationPipeline()
    return pipeline.run(data)
