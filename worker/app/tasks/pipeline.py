from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

try:  # pragma: no cover - optional dependency
    import sys
    import os
    # Add backend to path for shared services
    backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../backend"))
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)
    from app.services.bigquery import InternalLinkRepository
except ImportError:
    InternalLinkRepository = None  # type: ignore

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
            "title": f"{prompt['primary_keyword']}の構成案",
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
            "title": f"{keyword} {context.article_type}ガイド",
            "h2": template_sections,
        }

    def _article_type_template(self, article_type: str, keyword: str) -> List[Dict[str, Any]]:
        information_template = [
            {
                "text": "リード：読むべき理由（QUESTのQ/Uで共感）",
                "purpose": "Lead",
                "h3": [
                    {"text": "読者が抱える課題", "purpose": "Lead"},
                    {"text": "本記事で得られること", "purpose": "Lead"},
                ],
            },
            {
                "text": "まず知るべき要点（結論）",
                "purpose": "Know",
                "h3": [
                    {"text": f"{keyword}の定義", "purpose": "Know"},
                    {"text": "押さえるべき重要ポイント", "purpose": "Know"},
                ],
            },
            {
                "text": "定義と範囲（Owned/Earned/Paid）",
                "purpose": "Know",
                "h3": [
                    {"text": "Owned Media", "purpose": "Know"},
                    {"text": "Earned Media", "purpose": "Know"},
                    {"text": "Paid Media", "purpose": "Know"},
                ],
            },
            {
                "text": "主要チャネルと役割（SEO/広告/メール/ソーシャル 等）",
                "purpose": "Compare",
                "h3": [
                    {"text": "各チャネルの強み", "purpose": "Compare"},
                    {"text": "チャネル連携のポイント", "purpose": "Compare"},
                ],
            },
            {
                "text": "KPIの因数分解（例：売上＝流入×CVR×AOV）",
                "purpose": "Measure",
                "h3": [
                    {"text": "主要KPIと指標", "purpose": "Measure"},
                    {"text": "改善の優先順位付け", "purpose": "Measure"},
                ],
            },
            {
                "text": "計測基盤（GTM/GA/広告タグ/UTM/同意管理）",
                "purpose": "Measure",
                "h3": [
                    {"text": "計測設計の基本", "purpose": "Measure"},
                    {"text": "プライバシー対応", "purpose": "Measure"},
                ],
            },
            {
                "text": "戦略設計（ペルソナ→ジャーニー→優先度）",
                "purpose": "Plan",
                "h3": [
                    {"text": "ターゲットの明確化", "purpose": "Plan"},
                    {"text": "ジャーニーと施策マップ", "purpose": "Plan"},
                ],
            },
            {
                "text": "運用体制（PL/PM/クリエイティブ/アナリスト）",
                "purpose": "Do",
                "h3": [
                    {"text": "必要な役割", "purpose": "Do"},
                    {"text": "連携とワークフロー", "purpose": "Do"},
                ],
            },
            {
                "text": "事例・よくある失敗（手段の目的化/反復不足）",
                "purpose": "Learn",
                "h3": [
                    {"text": "成功事例の要点", "purpose": "Learn"},
                    {"text": "失敗の原因と対策", "purpose": "Learn"},
                ],
            },
            {
                "text": "まとめとCTA（資料DL/相談 等）",
                "purpose": "Close",
                "h3": [
                    {"text": "読者への次アクション", "purpose": "Close"},
                    {"text": "CTAメッセージ案", "purpose": "Close"},
                ],
            },
        ]

        comparison_template = [
            {
                "text": f"{keyword}の主要選択肢一覧",
                "purpose": "Compare",
                "h3": [
                    {"text": "評価軸の整理", "purpose": "Compare"},
                    {"text": "比較表のサマリー", "purpose": "Compare"},
                ],
            },
            {
                "text": "ユーザーニーズ別のおすすめ",
                "purpose": "Recommend",
                "h3": [
                    {"text": "小規模チーム向け", "purpose": "Recommend"},
                    {"text": "エンタープライズ向け", "purpose": "Recommend"},
                ],
            },
            {
                "text": "導入ステップと意思決定のポイント",
                "purpose": "Decision",
                "h3": [
                    {"text": "評価の進め方", "purpose": "Decision"},
                    {"text": "社内合意形成のヒント", "purpose": "Decision"},
                ],
            },
            {
                "text": "成功事例と失敗リスク",
                "purpose": "Learn",
                "h3": [
                    {"text": "成果を出した事例", "purpose": "Learn"},
                    {"text": "失敗を避けるチェックリスト", "purpose": "Learn"},
                ],
            },
            {
                "text": "まとめとCTA",
                "purpose": "Close",
                "h3": [
                    {"text": "意思決定の支援", "purpose": "Close"},
                    {"text": "CTAメッセージ案", "purpose": "Close"},
                ],
            },
        ]

        ranking_template = [
            {
                "text": f"{keyword}ランキング上位の選定基準",
                "purpose": "Ranking",
                "h3": [
                    {"text": "評価基準", "purpose": "Ranking"},
                    {"text": "スコアリング方法", "purpose": "Ranking"},
                ],
            },
            {
                "text": "TOP3 詳細レビュー",
                "purpose": "Ranking",
                "h3": [
                    {"text": "第1位", "purpose": "Ranking"},
                    {"text": "第2位", "purpose": "Ranking"},
                    {"text": "第3位", "purpose": "Ranking"},
                ],
            },
            {
                "text": "用途別のおすすめ",
                "purpose": "Recommend",
                "h3": [
                    {"text": "コスト重視", "purpose": "Recommend"},
                    {"text": "機能重視", "purpose": "Recommend"},
                ],
            },
            {
                "text": "選び方のチェックポイント",
                "purpose": "Decision",
                "h3": [
                    {"text": "導入前に確認したいこと", "purpose": "Decision"},
                    {"text": "比較時の注意点", "purpose": "Decision"},
                ],
            },
            {
                "text": "CTAと次のアクション",
                "purpose": "Close",
                "h3": [
                    {"text": "資料請求・相談の案内", "purpose": "Close"},
                    {"text": "比較表ダウンロード誘導", "purpose": "Close"},
                ],
            },
        ]

        closing_template = [
            {
                "text": f"{keyword}導入で得られる成果の再確認",
                "purpose": "Close",
                "h3": [
                    {"text": "ビジネスインパクト", "purpose": "Close"},
                    {"text": "導入後の体験", "purpose": "Close"},
                ],
            },
            {
                "text": "導入プロセスとスケジュール",
                "purpose": "Plan",
                "h3": [
                    {"text": "短期導入ステップ", "purpose": "Plan"},
                    {"text": "定着支援", "purpose": "Plan"},
                ],
            },
            {
                "text": "投資対効果（ROI）の説得材料",
                "purpose": "Measure",
                "h3": [
                    {"text": "数値で示すメリット", "purpose": "Measure"},
                    {"text": "社内ステークホルダーへの訴求", "purpose": "Measure"},
                ],
            },
            {
                "text": "FAQ：導入検討中によくある懸念",
                "purpose": "Learn",
                "h3": [
                    {"text": "コストに関する懸念", "purpose": "Learn"},
                    {"text": "運用体制に関する懸念", "purpose": "Learn"},
                ],
            },
            {
                "text": "クロージングメッセージとCTA",
                "purpose": "Close",
                "h3": [
                    {"text": "CTAメッセージ案", "purpose": "Close"},
                    {"text": "導入後支援の強調", "purpose": "Close"},
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
            prompt = self._build_section_prompt(heading_text, context)
            grounded_result = self._generate_grounded_content(prompt)
            claim_id = f"{context.draft_id}-{heading_text}"
            if level == "h2":
                claim_id = f"{context.draft_id}-{level}-{heading_text}"
            source_candidates = grounded_result.get("citations") or citations[:2]
            if not source_candidates and context.reference_urls:
                source_candidates = [{"url": url} for url in context.reference_urls[:2]]
            citation_values = [c.get("uri") or c.get("url") or str(c) for c in source_candidates]
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

    def _build_section_prompt(self, heading: str, context: PipelineContext) -> str:
        """Build a prompt for generating a specific section."""
        persona_name = context.persona.get("name", "読者")
        tone = context.persona.get("tone", "実務的")
        references = ", ".join(context.reference_urls[:3]) if context.reference_urls else ""
        notation = context.notation_guidelines or "読みやすい日本語（全角を適切に使用）"
        cta_line = f"CTA: {context.cta}" if context.cta else "CTA: 情報提供後に適切な行動を促す"
        reference_line = f"参考URL: {references}" if references else "参考URL: 必要に応じて公的情報源を検索"
        return (
            f"以下の見出しについて、{persona_name}向けに{tone}なトーンで詳しく解説してください。\n"
            f"記事タイプ: {context.article_type}\n"
            f"見出し: {heading}\n"
            f"検索意図: {context.intent}\n"
            f"{cta_line}\n"
            f"表記ルール: {notation}\n"
            f"{reference_line}\n"
            f"出力形式: {context.output_format}に変換しやすいMarkdownベースの段落で記述\n"
            "必ず信頼できる情報源に基づいて記述し、統計値には出典を付与してください。"
        )

    def _generate_grounded_content(self, prompt: str) -> Dict[str, Any]:
        """Generate content with the configured OpenAI gateway."""
        if not self.ai_gateway:
            logger.error("AI Gateway not available - cannot generate content")
            raise RuntimeError("AI Gateway is not initialized. Please configure OPENAI_API_KEY or GCP credentials.")

        try:
            result = self.ai_gateway.generate_with_grounding(prompt, temperature=0.7)
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

        context = PipelineContext(
            job_id=payload["job_id"],
            draft_id=draft_id,
            project_id=payload["project_id"],
            prompt_version=payload.get("prompt_version", self.settings.default_prompt_version),
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
