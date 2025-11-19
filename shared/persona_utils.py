from __future__ import annotations

from typing import Any, Dict


EXPERTISE_YEARS = {
    "beginner": "1年目くらい",
    "intermediate": "2〜3年目くらい",
    "expert": "5年以上の経験を持つ",
}

ROLE_LABELS = {
    "marketing_manager": "マーケティング担当",
    "marketing_specialist": "マーケティング担当",
    "growth_lead": "グロース担当",
    "business_owner": "経営者・事業責任者",
    "founder": "創業者・事業責任者",
    "engineer": "エンジニア",
    "product_manager": "プロダクトマネージャー",
    "data_analyst": "データ分析担当",
    "sales_manager": "営業マネージャー",
}


def infer_japanese_persona_label(
    persona: Dict[str, Any] | None,
    writer_persona: Dict[str, Any] | None = None,
    *,
    fallback_expertise: str = "intermediate",
) -> str:
    """
    PipelineContext.persona と writer_persona から日本語的な読者属性を推論する。

    例:
        expertise_level: "intermediate" -> "マーケティング担当になって2〜3年目の方"
        role: "marketing_manager" -> "マーケティング担当者"
    """

    persona = persona or {}
    writer_persona = writer_persona or {}

    expertise = str(persona.get("expertise_level") or fallback_expertise or "intermediate").lower()
    years_label = EXPERTISE_YEARS.get(expertise, "")

    role = str(persona.get("role") or persona.get("job_role") or "").lower()
    role_label = ROLE_LABELS.get(role, "")

    # When persona explicitly specifies a custom label, prioritize it.
    custom_label = str(persona.get("label") or persona.get("name") or "").strip()
    if custom_label and len(custom_label) <= 12 and not _looks_like_person_name(custom_label):
        role_label = custom_label

    if not role_label:
        # Use writer persona audience hint if available
        audience_hint = writer_persona.get("audience") if isinstance(writer_persona, dict) else None
        if isinstance(audience_hint, str) and audience_hint.strip():
            role_label = audience_hint.strip()
        else:
            role_label = "担当者"

    if years_label:
        return f"{role_label}になって{years_label}の方"
    return f"{role_label}の方"


def build_intro_persona_clause(persona_label: str) -> str:
    """
    日本のSEO記事標準の冒頭表現を生成。

    例: 「この記事は、マーケティング担当になって2〜3年目くらいの方に向けて書かれています。」
    """
    normalized = persona_label.strip() or "担当者の方"
    return f"この記事は、{normalized}に向けて書かれています。"


def _looks_like_person_name(value: str) -> bool:
    """Detect obvious person names to avoid awkward intros."""
    if not value:
        return False
    kana = any("ァ" <= ch <= "ヶ" for ch in value)
    has_space = " " in value or "　" in value
    # Japanese personal names are typically short and may contain kana/kanji mix.
    return kana or has_space or len(value) <= 4
