"""Project-level default configurations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class WriterPersonaDefaults:
    name: str
    role: str
    expertise: str
    voice: str
    qualities: List[str]
    mission: str

    def to_payload(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "role": self.role,
            "expertise": self.expertise,
            "voice": self.voice,
            "qualities": self.qualities,
            "mission": self.mission,
        }


@dataclass(frozen=True)
class PromptLayerDefaults:
    system: str
    developer: str
    user: str

    def to_payload(self) -> Dict[str, str]:
        return {
            "system": self.system,
            "developer": self.developer,
            "user": self.user,
        }


@dataclass(frozen=True)
class ProjectDefaults:
    project_id: str
    writer_persona: WriterPersonaDefaults
    preferred_sources: List[str]
    reference_media: List[str]
    prompt_layers: PromptLayerDefaults

    def to_payload(self) -> Dict[str, Any]:
        return {
            "writer_persona": self.writer_persona.to_payload(),
            "preferred_sources": list(self.preferred_sources),
            "reference_media": list(self.reference_media),
            "prompt_layers": self.prompt_layers.to_payload(),
        }


_PROJECT_DEFAULTS: Dict[str, ProjectDefaults] = {
    "seo-drafter-gcp": ProjectDefaults(
        project_id="seo-drafter-gcp",
        writer_persona=WriterPersonaDefaults(
            name="井上あかり",
            role="B2B SaaSのシニアコンテンツストラテジスト",
            expertise=("B2Bマーケティングの戦略立案と"
                       "データドリブンなSEO改善施策に精通"),
            voice="落ち着いた敬体で事実を積み上げる実務家視点",
            qualities=[
                "抽象的な表現は手順・数値・事例へ言い換える",
                "統計データと一次情報を根拠に論理を組み立てる",
                "誇張・比喩・擬人化は避け、中立的なトーンを維持する",
            ],
            mission="読者が根拠を持って次のアクションを決められる状態をつくる",
        ),
        preferred_sources=[
            "https://www.meti.go.jp/",
            "https://www.stat.go.jp/",
            "https://thinkwithgoogle.com/",
            "https://www.gartner.com/en",
            "https://hbr.org/",
        ],
        reference_media=[
            "HubSpotブログ",
            "Think with Google",
            "日経クロストレンド",
            "海外調査レポート（Gartner, McKinsey等）",
        ],
        prompt_layers=PromptLayerDefaults(
            system=(
                "あなたは{writer_name}として執筆するシニアSEOライターです。"
                "断定的・誇張的な表現や比喩、擬人化、あいまいな言い回しを避け、検証可能な事実に基づいて記述してください。"
                "主張を行う際は一次情報・公的統計・業界レポートなど信頼できる出典を明示し、複数の根拠を提示します。"
                "日本語は敬体で簡潔にまとめ、段落内は論点→根拠→示唆の順で構成してください。"
                "固有名詞や数値は最新情報かつ正式名称を用い、出典が確認できない情報は記載しないでください。"
            ),
            developer=(
                "出力はMarkdown準拠のテキストで、段落ごとに改行し見出し階層を保ってください。"
                "各段落には最低1つの具体的な根拠（数値・事例・手順）を含め、根拠の出典を [Source: URL] 形式で記載します。"
                "誇張語（例: 計り知れない、魔法のような、圧倒的 等）や主観的な推測は使用しません。"
                "出典リンクは2件以上、具体的な数値・事例は合計3点以上提示してください。"
                "差別化トピックや未カバー領域が指定されている場合は、それらを見出し・本文に明示的に盛り込みます。"
            ),
            user=(
                "見出し: {heading}\n"
                "セクションレベル: {level}\n"
                "主キーワード: {primary_keyword}\n"
                "読者プロフィール: {reader_profile}\n"
                "CTA: {cta}\n"
                "参考URL: {references}\n"
                "優先参照メディア: {preferred_media}\n"
                "出典候補: {preferred_sources}\n"
                "スタイル注意事項: {notation}\n"
                "記事タイプ: {article_type}\n"
                "検索意図: {intent}\n"
                "差別化すべきトピック: {gap_topics}\n"
                "このセクションで伝えたい狙い: {section_goal}\n"
            ),
        ),
    )
}


def get_project_defaults(project_id: Optional[str]) -> Dict[str, Any]:
    """Return defaults for the requested project, or the first registered defaults."""
    if project_id and project_id in _PROJECT_DEFAULTS:
        return _PROJECT_DEFAULTS[project_id].to_payload()
    if _PROJECT_DEFAULTS:
        # Return the first defaults to keep behaviour deterministic in local dev.
        return next(iter(_PROJECT_DEFAULTS.values())).to_payload()
    return {
        "writer_persona": {},
        "preferred_sources": [],
        "reference_media": [],
        "prompt_layers": {
            "system": "",
            "developer": "",
            "user": "",
        },
    }
