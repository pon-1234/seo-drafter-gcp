from __future__ import annotations

import re
from typing import Dict

ABBREVIATION_EXPANSION: Dict[str, str] = {
    "MMM": "マーケティングミックスモデリング（MMM）",
    "CMP": "同意管理プラットフォーム（CMP）",
    "KPI": "重要業績評価指標（KPI）",
    "KGI": "重要目標達成指標（KGI）",
    "LTV": "顧客生涯価値（LTV）",
    "CRM": "顧客関係管理（CRM）",
}

SLASH_TO_JAPANESE: Dict[str, str] = {
    r"アトリビューション/リフト/MMM": "アトリビューション分析やリフト計測、MMM（マーケティングミックスモデリング）など",
    r"Owned/Earned/Paid": "自社メディアや獲得メディア、有料広告など（Owned/Earned/Paidメディア）",
    r"CMP/Consent Mode v2/拡張コンバージョン": "CMPやConsent Mode v2、拡張コンバージョンなど",
}


def normalize_slash_expressions(text: str) -> str:
    updated = text
    for pattern, replacement in SLASH_TO_JAPANESE.items():
        updated = re.sub(pattern, replacement, updated)
    return updated


def expand_abbreviations(text: str) -> str:
    updated = text
    for short, expanded in ABBREVIATION_EXPANSION.items():
        updated = re.sub(rf"\b{re.escape(short)}\b", expanded, updated, count=1)
    return updated
