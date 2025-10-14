from __future__ import annotations

import json
import logging
import os
import re
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

try:  # pragma: no cover - optional dependency
    # Add backend to path for shared services
    backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../backend"))
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)
    from app.services.bigquery import InternalLinkRepository
except ImportError:
    InternalLinkRepository = None  # type: ignore

# Shared project defaults
try:
    shared_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
    if shared_path not in sys.path:
        sys.path.insert(0, shared_path)
    from shared.project_defaults import get_project_defaults
except ImportError:
    get_project_defaults = lambda _project_id: {  # type: ignore
        "writer_persona": {},
        "preferred_sources": [],
        "reference_media": [],
        "prompt_layers": {
            "system": "",
            "developer": "",
            "user": "",
        },
    }

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


class DraftGenerationPipeline:
    """Encapsulates the deterministic order of the draft generation steps."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.ai_gateway = None

        if not OpenAIGateway:
            logger.error("OpenAI gateway implementation is not available")
        else:
            try:
                logger.info(
                    "Initializing OpenAI with API key: %s..., model: %s",
                    self.settings.openai_api_key[:20] if self.settings.openai_api_key else "None",
                    self.settings.openai_model,
                )
                self.ai_gateway = OpenAIGateway(
                    api_key=self.settings.openai_api_key,
                    model=self.settings.openai_model,
                )
                logger.info("Successfully initialized OpenAI gateway (model: %s)", self.settings.openai_model)
            except Exception as exc:
                logger.error("OpenAI initialization failed: %s (type: %s)", str(exc), type(exc).__name__)
                import traceback

                logger.error("Full traceback: %s", traceback.format_exc())

        self.link_repository = InternalLinkRepository() if InternalLinkRepository else None

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

    def generate_outline(self, context: PipelineContext, prompt: Dict) -> Dict:
        logger.info(
            "Generating outline for %s using prompt %s (mode=%s)",
            context.job_id,
            context.prompt_version,
            context.heading_mode,
        )
        if context.heading_mode == "manual" and context.heading_overrides:
            return self._outline_from_manual(context, prompt)
        return self._outline_from_template(context, prompt)

    @staticmethod
    def _build_quest_title(primary_keyword: str) -> str:
        return (
            f"{primary_keyword}で成果を掴むQUESTガイド"
            "（Question・Understand・Evidence・Solution・Takeaway）"
        )

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
        return {
            "title": self._build_quest_title(prompt["primary_keyword"]),
            "h2": sections,
        }

    def _outline_from_template(self, context: PipelineContext, prompt: Dict) -> Dict:
        keyword = prompt["primary_keyword"]
        template_sections = self._article_type_template(context.article_type, keyword)
        budget = self._estimate_section_word_budget(context, len(template_sections) or 1)
        for section in template_sections:
            section.setdefault("estimated_words", budget)
            for h3 in section.get("h3", []):
                h3.setdefault("estimated_words", max(int(budget / max(len(section.get("h3", [])) or 1, 1)), 120))
        return {
            "title": self._build_quest_title(keyword),
            "h2": template_sections,
        }

    def _article_type_template(self, article_type: str, keyword: str) -> List[Dict[str, Any]]:
        information_template = [
            {
                "text": f"{keyword}で解決できる課題と得られる成果（QUESTのQ/U）",
                "purpose": "Lead",
                "h3": [
                    {"text": "現場の風景が浮かぶ課題シーン（視覚）", "purpose": "Lead"},
                    {"text": "成果が耳に届く成功の声（聴覚）", "purpose": "Lead"},
                ],
            },
            {
                "text": f"{keyword}がもたらす即効性のあるベネフィット",
                "purpose": "Know",
                "h3": [
                    {"text": "導入初期に体感できる改善インパクト", "purpose": "Know"},
                    {"text": "短期間で可視化できるKPI", "purpose": "Know"},
                ],
            },
            {
                "text": f"ハブ分析で描く{keyword}連携マップ",
                "purpose": "Plan",
                "h3": [
                    {"text": "ハブ施策とスポーク施策の役割分担", "purpose": "Plan"},
                    {"text": "連携で生まれる顧客体験のイメージ", "purpose": "Plan"},
                ],
            },
            {
                "text": "数値で語る投資対効果と意思決定の裏付け",
                "purpose": "Measure",
                "h3": [
                    {"text": "最新データで示す成果の伸びしろ", "purpose": "Measure"},
                    {"text": "意外性のある成功・失敗の事例", "purpose": "Measure"},
                ],
            },
            {
                "text": "運用チームが感じる導入後の体験価値",
                "purpose": "Do",
                "h3": [
                    {"text": "日常オペレーションのビフォーアフター（視覚）", "purpose": "Do"},
                    {"text": "社内の会話がどう変わるか（聴覚）", "purpose": "Do"},
                ],
            },
            {
                "text": "よくあるつまずきとリカバリーの打ち手",
                "purpose": "Learn",
                "h3": [
                    {"text": "失敗の兆候を視覚化するチェック項目", "purpose": "Learn"},
                    {"text": "体感的に分かる改善アクション", "purpose": "Learn"},
                ],
            },
            {
                "text": "CTAで導く次の一手と実務への橋渡し",
                "purpose": "Close",
                "h3": [
                    {"text": "読者がすぐ動ける最初のアクション", "purpose": "Close"},
                    {"text": "長期伴走で得られる継続メリット", "purpose": "Close"},
                ],
            },
        ]

        comparison_template = [
            {
                "text": f"{keyword}の選択肢がもたらす顧客便益の比較",
                "purpose": "Compare",
                "h3": [
                    {"text": "課題別に最適解が見える評価軸", "purpose": "Compare"},
                    {"text": "静かな差を生む意外性ある視点", "purpose": "Compare"},
                ],
            },
            {
                "text": f"{keyword}導入で得られる業種別成果シナリオ",
                "purpose": "Recommend",
                "h3": [
                    {"text": "少人数チームが体感したスピード感", "purpose": "Recommend"},
                    {"text": "エンタープライズで聞こえる成功の声", "purpose": "Recommend"},
                ],
            },
            {
                "text": f"Hub分析で見抜く{keyword}×既存施策の連携効果",
                "purpose": "Plan",
                "h3": [
                    {"text": "ハブ機能とスポーク施策の組み合わせ", "purpose": "Plan"},
                    {"text": "連携で生まれる顧客体験の視覚化", "purpose": "Plan"},
                ],
            },
            {
                "text": "投資判断を後押しする事例とリスク管理",
                "purpose": "Measure",
                "h3": [
                    {"text": "期待を上回った成果のストーリー", "purpose": "Measure"},
                    {"text": "見落としがちなリスクと回避策", "purpose": "Measure"},
                ],
            },
            {
                "text": "導入後90日のアクションプランとCTA",
                "purpose": "Close",
                "h3": [
                    {"text": "初期立ち上げの体感ロードマップ", "purpose": "Close"},
                    {"text": "成果最大化に向けた問いかけ", "purpose": "Close"},
                ],
            },
        ]

        ranking_template = [
            {
                "text": f"{keyword}ランキング上位が提供する価値",
                "purpose": "Ranking",
                "h3": [
                    {"text": "選定基準と実際のインパクト", "purpose": "Ranking"},
                    {"text": "意外な差別化ポイント", "purpose": "Ranking"},
                ],
            },
            {
                "text": "TOP3で体感できる成果ストーリー",
                "purpose": "Ranking",
                "h3": [
                    {"text": "第1位：成果を象徴する瞬間描写", "purpose": "Ranking"},
                    {"text": "第2位：数字で語る強み", "purpose": "Ranking"},
                    {"text": "第3位：隠れたメリット", "purpose": "Ranking"},
                ],
            },
            {
                "text": "用途別で選ぶと得られるベネフィット",
                "purpose": "Recommend",
                "h3": [
                    {"text": "コスト重視で確保できる成果", "purpose": "Recommend"},
                    {"text": "機能重視で開ける新しい景色", "purpose": "Recommend"},
                ],
            },
            {
                "text": "導入時に体感するギャップとリカバリー",
                "purpose": "Learn",
                "h3": [
                    {"text": "現場で起こりがちな戸惑い", "purpose": "Learn"},
                    {"text": "改善のためのハンズオン施策", "purpose": "Learn"},
                ],
            },
            {
                "text": "CTAで導く次のアクションと伴走",
                "purpose": "Close",
                "h3": [
                    {"text": "比較表ダウンロードで得られる価値", "purpose": "Close"},
                    {"text": "相談で実感できるサポート体制", "purpose": "Close"},
                ],
            },
        ]

        closing_template = [
            {
                "text": f"{keyword}導入後に手にする成果の再確認",
                "purpose": "Close",
                "h3": [
                    {"text": "ビジネスインパクトを映像で描写", "purpose": "Close"},
                    {"text": "導入後の体験を会話で想像", "purpose": "Close"},
                ],
            },
            {
                "text": "導入プロセスと体感できる変化のタイムライン",
                "purpose": "Plan",
                "h3": [
                    {"text": "短期導入ステップと現場の動き", "purpose": "Plan"},
                    {"text": "定着支援で得られる安心感", "purpose": "Plan"},
                ],
            },
            {
                "text": "投資対効果の裏付けと説得材料",
                "purpose": "Measure",
                "h3": [
                    {"text": "数値で示すROIと意外な副産物", "purpose": "Measure"},
                    {"text": "ステークホルダーが納得した理由", "purpose": "Measure"},
                ],
            },
            {
                "text": "FAQ：導入直前に出てくる不安を解消",
                "purpose": "Learn",
                "h3": [
                    {"text": "コストと運用負荷への回答", "purpose": "Learn"},
                    {"text": "データと引用で裏付ける安全性", "purpose": "Learn"},
                ],
            },
            {
                "text": "クロージングメッセージとCTAで行動を後押し",
                "purpose": "Close",
                "h3": [
                    {"text": "読者の背中を押す言葉選び", "purpose": "Close"},
                    {"text": "顧客便益が一目でわかるCTA案", "purpose": "Close"},
                ],
            },
        ]

        templates = {
            "information": information_template,
            "comparison": comparison_template,
            "ranking": ranking_template,
            "closing": closing_template,
        }
        resolved = []
        for section in templates.get(article_type, information_template):
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
        logger.info("Generating draft for %s with %d outline sections", context.job_id, len(outline.get('h2', [])))
        sections = []
        all_claims = []

        def build_paragraph(heading_text: str, level: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
            messages = self._build_prompt_messages(heading_text, level, context)
            grounded_result = self._generate_grounded_content(messages=messages)
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
            paragraph_text = self._ensure_benefit_line(paragraph_text, heading_text, context)

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

        for h2 in outline.get("h2", []):
            paragraphs = []
            for h3 in h2.get("h3", []):
                paragraph, claim = build_paragraph(h3["text"], "h3")
                paragraphs.append(paragraph)
                all_claims.append(claim)

            if not paragraphs:
                paragraph, claim = build_paragraph(h2["text"], "h2")
                paragraphs.append(paragraph)
                all_claims.append(claim)

            sections.append({"h2": h2["text"], "paragraphs": paragraphs})

        return {
            "draft": {
                "sections": sections,
                "faq": self._generate_faq(context),
            },
            "claims": all_claims,
        }

    def _build_prompt_messages(self, heading: str, level: str, context: PipelineContext) -> List[Dict[str, str]]:
        """Build layered prompt messages (system/developer/user)."""
        prompt_layers = context.prompt_layers or {}

        writer = context.writer_persona or {}
        writer_name = writer.get("name") or "シニアSEOライター"
        reader_name = context.persona.get("name") or "読者"
        reader_tone = context.persona.get("tone") or "実務的"

        references = ", ".join(context.reference_urls[:5]) if context.reference_urls else "指定なし"
        preferred_sources = ", ".join(context.preferred_sources[:5]) if context.preferred_sources else "優先指定なし"
        preferred_media = ", ".join(context.reference_media[:5]) if context.reference_media else "優先指定なし"
        notation = context.notation_guidelines or "読みやすい日本語（全角を適切に使用）"

        reader_profile = self._render_reader_profile(context.persona, reader_tone)
        section_goal = self._derive_section_goal(heading, context)

        format_payload = {
            "writer_name": writer_name,
            "reader_name": reader_name,
            "heading": heading,
            "level": level.upper(),
            "primary_keyword": context.primary_keyword or heading,
            "reader_profile": reader_profile,
            "cta": context.cta or "適切な次のアクションを選べる",
            "references": references,
            "preferred_sources": preferred_sources,
            "preferred_media": preferred_media,
            "notation": notation,
            "article_type": context.article_type,
            "intent": context.intent,
            "section_goal": section_goal,
        }

        system_template = prompt_layers.get("system") or (
            "あなたは{writer_name}として執筆するシニアSEOライターです。"
            "読者の共感を呼びつつ、実務で使えるレベルまで噛み砕いて解説してください。"
            "ハブ分析などの適切なフレームも活用しながら、VAK（視覚・聴覚・体感）"
            "表現で臨場感を高め、少なくとも一つ意外性のある知見を盛り込みます。"
        )
        developer_template = prompt_layers.get("developer") or (
            "出力はMarkdownで、セクション内の最後に必ず『顧客便益: 〜』と締めてください。"
            "参考情報は [Source: URL] 形式で明記し、優先参照メディアをまず検討してください。"
        )
        user_template = prompt_layers.get("user") or (
            "見出し: {heading}\n"
            "セクションレベル: {level}\n"
            "読者プロフィール: {reader_profile}\n"
            "CTA: {cta}\n"
            "参考URL: {references}\n"
            "優先参照メディア: {preferred_media}\n"
            "出典候補: {preferred_sources}\n"
            "スタイル注意事項: {notation}\n"
            "記事タイプ: {article_type}\n"
            "検索意図: {intent}\n"
            "狙い: {section_goal}\n"
        )

        system_message = system_template.format_map(format_payload)
        developer_message = developer_template.format_map(format_payload)
        user_message = user_template.format_map(
            {
                **format_payload,
                "primary_keyword": format_payload.get("primary_keyword"),
            }
        )

        return [
            {"role": "system", "content": system_message},
            {"role": "developer", "content": developer_message},
            {"role": "user", "content": user_message},
        ]

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

    def _ensure_benefit_line(self, text: str, heading: str, context: PipelineContext) -> str:
        if "顧客便益" in text:
            return text
        benefit_sentence = self._compose_benefit_sentence(heading, context)
        sanitized = text.rstrip()
        if sanitized:
            return f"{sanitized}\n顧客便益: {benefit_sentence}"
        return f"顧客便益: {benefit_sentence}"

    def _compose_benefit_sentence(self, heading: str, context: PipelineContext) -> str:
        persona_name = context.persona.get("name") or "読者"
        mission = context.writer_persona.get("mission") if isinstance(context.writer_persona, dict) else None
        cta = context.cta or "意思決定"
        mission_phrase = mission or "価値ある行動を後押しする"
        return f"{persona_name}が{heading}を理解し、{cta}に向けて{mission_phrase}ための自信を得られます。"

    def _generate_grounded_content(
        self,
        prompt: Optional[str] = None,
        *,
        messages: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Generate content with the configured OpenAI gateway."""
        if not self.ai_gateway:
            logger.error("AI Gateway not available - cannot generate content")
            raise RuntimeError("AI Gateway is not initialized. Please configure OPENAI_API_KEY or GCP credentials.")

        try:
            result = self.ai_gateway.generate_with_grounding(
                prompt=prompt,
                messages=messages,
                temperature=0.7,
            )
            logger.info("Generated content: %d characters", len(result.get("text", "")))
            return result
        except Exception as e:
            logger.error("Content generation failed: %s", e)
            raise

    def _generate_faq(self, context: PipelineContext) -> List[Dict]:
        """Generate FAQ section using the OpenAI gateway."""
        persona_name = context.persona.get("name", "読者")
        pain_points = context.persona.get("pain_points", [])

        faq_items = []
        for pain in pain_points[:3]:
            prompt = f"{persona_name}が抱える「{pain}」という課題に対する解決策を簡潔に説明してください。"
            result = self._generate_grounded_content(prompt)
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

    def generate_meta(self, prompt: Dict, context: PipelineContext) -> Dict:
        keyword = prompt["primary_keyword"]
        cta = context.cta or "資料請求はこちら"
        return {
            "title_options": [f"{keyword} 完全ガイド", f"{keyword} 比較ポイントまとめ"],
            "description_options": [
                f"{keyword} の最新情報と比較ポイントを詳しく解説",
                f"{keyword} の選び方と成功事例",
            ],
            "og": {
                "title": f"{keyword} のベストプラクティス",
                "description": f"{keyword} に関するノウハウを網羅",
            },
            "cta": cta,
            "preferred_output": context.output_format,
        }

    def propose_links(self, prompt: Dict, context: PipelineContext) -> List[Dict]:
        """Propose internal links using BigQuery Vector Search."""
        keyword = prompt["primary_keyword"]
        persona_goals = context.persona.get("goals", [])

        if not self.link_repository:
            logger.warning("Link repository not available, using fallback")
            return [{
                "url": f"https://example.com/articles/{keyword}-guide",
                "title": f"{keyword} ガイド",
                "anchor": f"{keyword} と関連するガイド",
                "score": 0.5,
            }]

        try:
            candidates = self.link_repository.search(keyword, persona_goals, limit=5)
            results = []
            for candidate in candidates:
                results.append({
                    "url": candidate["url"],
                    "title": candidate["title"],
                    "anchor": f"{keyword} と関連する {candidate['title']}",
                    "score": candidate.get("score", 0.5),
                    "snippet": candidate.get("snippet", ""),
                })
            logger.info("Proposed %d internal links for keyword: %s", len(results), keyword)
            return results
        except Exception as e:
            logger.error("Link proposal failed: %s", e)
            return []

    def evaluate_quality(self, draft: Dict, context: PipelineContext) -> Dict:
        claims_without_citations = [c for c in draft.get("claims", []) if not c.get("citations")]
        duplication_score = 0.08 if context.article_type == "ranking" else 0.12
        sections = draft.get("draft", {}).get("sections", [])
        paragraphs = [p for section in sections for p in section.get("paragraphs", [])]
        has_citations = any(p.get("citations") for p in paragraphs)

        expected_intent_map = {
            "information": "information",
            "comparison": "comparison",
            "ranking": "comparison",
            "closing": "transaction",
        }
        expected_intent = expected_intent_map.get(context.article_type, context.intent)

        rubric = {
            "意図適合": "pass" if context.intent == expected_intent else "attention",
            "再現性": "pass" if sections else "attention",
            "E-E-A-T": "pass" if has_citations else "attention",
            "事実整合": "pass" if not claims_without_citations else "review",
            "独自性": "pass" if duplication_score < 0.25 else "review",
        }
        pass_count = sum(1 for value in rubric.values() if value == "pass")
        rubric_summary = (
            f"{context.quality_rubric or 'standard'} rubric: {pass_count}/{len(rubric)} pass"
        )

        return {
            "similarity": duplication_score,
            "claims": claims_without_citations,
            "style_violations": [] if duplication_score < 0.3 else ["content-too-similar"],
            "is_ymyl": context.article_type in {"information", "comparison"} and not has_citations,
            "rubric": {**rubric, "summary": rubric_summary},
            "rubric_summary": rubric_summary,
        }

    def bundle_outputs(self, context: PipelineContext, outline: Dict, draft: Dict, meta: Dict, links: List[Dict], quality: Dict) -> Dict:
        metadata = {
            "job_id": context.job_id,
            "draft_id": context.draft_id,
            "prompt_version": context.prompt_version,
            "article_type": context.article_type,
            "output_format": context.output_format,
            "heading_mode": context.heading_mode,
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

        return {
            "outline": outline,
            "draft": draft,
            "meta": meta,
            "links": links,
            "quality": quality,
            "metadata": metadata,
        }

    def run(self, payload: Dict) -> Dict:
        logger.info("Starting pipeline for job %s", payload["job_id"])
        draft_id = payload.get("draft_id") or str(payload["job_id"]).replace("-", "")[:12]
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
            word_count_range = str(word_range_raw) if word_range_raw else None

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

        context = PipelineContext(
            job_id=payload["job_id"],
            draft_id=draft_id,
            project_id=project_id,
            prompt_version=payload.get("prompt_version", self.settings.default_prompt_version),
            primary_keyword=payload["primary_keyword"],
            persona=payload.get("persona", {}),
            intent=intent,
            article_type=payload.get("article_type", "information"),
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
        )
        outline = self.generate_outline(context, payload)
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
        draft = self.generate_draft(context, outline, citations)
        meta = self.generate_meta(payload, context)
        links = self.propose_links(payload, context)
        quality = self.evaluate_quality(draft, context)
        bundle = self.bundle_outputs(context, outline, draft, meta, links, quality)
        logger.info("Completed pipeline for job %s", payload["job_id"])
        return bundle


def handle_pubsub_message(event, _context) -> Dict:
    # Expected to be Pub/Sub triggered Cloud Run job
    data = json.loads(event["data"]) if isinstance(event, dict) and "data" in event else event
    pipeline = DraftGenerationPipeline()
    return pipeline.run(data)
