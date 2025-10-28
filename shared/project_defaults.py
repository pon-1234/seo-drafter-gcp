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
            voice="共感とロジックを両立させる実務家視点",
            qualities=[
                "抽象と具体を往復しながらストーリーで魅せる",
                "数字と一次情報をもとに説得力を担保する",
                "視覚・聴覚・体感のVAKで読者の想像を喚起する",
            ],
            mission="読者の迷いを解き、行動の背中を押すコンテンツを届ける",
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
                "読者は{reader_name}で、QUESTのフレームを用いた構成を求めています。"
                "H1はQUESTで読者の課題に共感し、H2以降は顧客が得られるベネフィットを"
                "明確に伝える見出しにしてください。各セクションではVAK（視覚・聴覚・体感覚）"
                "の要素を織り交ぜ、臨場感のある表現で読者の想像を促してください。"
                "少なくとも一つ、意外性のある事例または一次情報に基づくデータを織り込み、"
                "平易な一般論に終わらない洞察を示してください。"
            ),
            developer=(
                "出力はMarkdown準拠のテキストで、段落ごとに明確に改行してください。"
                "各セクションの末尾には必ず『顧客便益: 〜』という形式で一文を追加し、"
                "読者が得られる実利を端的に示してください。"
                "統計・引用が必要な場合は指定された優先参照メディアを第一候補とし、"
                "出典を [Source: URL] の形式で明示してください。"
                "可能であればビジュアルイメージを想起できる語彙や聴覚的・身体的な描写を加え、"
                "読者が目の前のシーンを思い浮かべられるようにしてください。"
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
