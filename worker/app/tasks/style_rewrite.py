from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from shared.terminology import expand_abbreviations, normalize_slash_expressions

logger = logging.getLogger(__name__)


class StructurePreservingStyleRewriter:
    """
    JSON構造（sections/paragraphs/citations）を保持したまま paragraph をリライトする。
    """

    def __init__(self, ai_gateway: Optional[Any]) -> None:
        self.ai_gateway = ai_gateway
        self.prompt_template = self._load_prompt_template()

    def update_gateway(self, ai_gateway: Optional[Any]) -> None:
        """Refresh gateway when LLM configuration changes."""
        self.ai_gateway = ai_gateway

    def _load_prompt_template(self) -> str:
        template_path = Path(__file__).resolve().parents[3] / "shared" / "prompts" / "paragraph_style_rewrite.txt"
        if template_path.exists():
            return template_path.read_text(encoding="utf-8")

        logger.warning("paragraph_style_rewrite.txt not found. Falling back to inline template.")
        return (
            "あなたは日本人のBtoBマーケティング経験者です。以下の段落を自然な敬体で書き直してください。\n"
            "- 1文を60〜80字以内\n"
            "- である調を禁止\n"
            "- 記号の多用を避ける\n\n"
            "{{PARAGRAPH_TEXT}}\n"
        )

    def rewrite_sections(
        self,
        sections: List[Dict[str, Any]],
        *,
        max_workers: int = 4,
        sample_only: bool = False,
    ) -> List[Dict[str, Any]]:
        if not sections:
            return sections

        paragraph_tasks: List[Tuple[Tuple[int, int], str]] = []
        for sec_idx, section in enumerate(sections):
            for para_idx, paragraph in enumerate(section.get("paragraphs", [])):
                original_text = str(paragraph.get("text") or "").strip()
                if original_text:
                    paragraph_tasks.append(((sec_idx, para_idx), original_text))

        if not paragraph_tasks:
            return sections

        if sample_only:
            paragraph_tasks = paragraph_tasks[:3]
            logger.info("Sample mode enabled: rewriting first %d paragraphs", len(paragraph_tasks))

        rewritten_map: Dict[Tuple[int, int], str] = {}
        worker_count = max(1, int(max_workers or 1))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_to_data = {
                executor.submit(self._rewrite_paragraph, original_text): (key, original_text)
                for key, original_text in paragraph_tasks
            }

            for future in as_completed(future_to_data):
                key, original_text = future_to_data[future]
                try:
                    rewritten_text = future.result()
                    rewritten_map[key] = rewritten_text
                except Exception as exc:  # pragma: no cover - defensive
                    logger.warning("Paragraph rewrite failed for %s: %s", key, exc)
                    rewritten_map[key] = original_text

        updated_sections: List[Dict[str, Any]] = []
        for sec_idx, section in enumerate(sections):
            new_section = dict(section)
            new_paragraphs = []
            for para_idx, paragraph in enumerate(section.get("paragraphs", [])):
                replacement = rewritten_map.get((sec_idx, para_idx))
                if replacement:
                    new_paragraph = dict(paragraph)
                    new_paragraph["text"] = replacement
                else:
                    new_paragraph = paragraph
                new_paragraphs.append(new_paragraph)
            new_section["paragraphs"] = new_paragraphs
            updated_sections.append(new_section)

        logger.info("Rewrote %d paragraphs across %d sections", len(rewritten_map), len(updated_sections))
        return updated_sections

    def _rewrite_paragraph(self, text: str) -> str:
        """Rewrite a single paragraph using the configured gateway."""
        if not text or not self.ai_gateway:
            return text

        prepared_text = apply_basic_style_fixes(text)
        prompt = self.prompt_template.replace("{{PARAGRAPH_TEXT}}", prepared_text)
        try:
            result = self.ai_gateway.generate_with_grounding(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1000,
            )
        except Exception as exc:
            logger.error("LLM call failed during paragraph rewrite: %s", exc)
            return text

        rewritten = str(result.get("text") or "").strip()
        return rewritten if rewritten else text


def apply_basic_style_fixes(text: str) -> str:
    """軽量な正規表現ベースの補正。"""
    if not text:
        return text

    updated = normalize_slash_expressions(text)
    updated = expand_abbreviations(updated)
    updated = re.sub(
        r"([ぁ-んァ-ヶ一-龥A-Za-z0-9]+/[ぁ-んァ-ヶ一-龥A-Za-z0-9]+/[ぁ-んァ-ヶ一-龥A-Za-z0-9]+)",
        _replace_slash_sequence,
        updated,
    )
    updated = re.sub(r"である。", "です。", updated)
    updated = re.sub(r"にある。", "にあります。", updated)
    return updated


def _replace_slash_sequence(match: re.Match) -> str:
    tokens = match.group(0).split("/")
    if not tokens:
        return match.group(0)
    if len(tokens) == 2:
        return f"{tokens[0]}や{tokens[1]}など"
    *head, last = tokens
    return f"{'や'.join(head)}、{last}など"
