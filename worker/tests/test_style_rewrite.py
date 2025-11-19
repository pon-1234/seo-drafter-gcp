from app.tasks.style_rewrite import StructurePreservingStyleRewriter
from app.validators import StructureValidator
from shared.persona_utils import infer_japanese_persona_label


class DummyGateway:
    def __init__(self, response_text: str) -> None:
        self.response_text = response_text
        self.calls = 0

    def generate_with_grounding(self, messages, temperature=0.3, max_tokens=1000):
        self.calls += 1
        return {"text": self.response_text, "citations": []}


def test_paragraph_rewrite_preserves_structure():
    sections = [
        {
            "h2": "背景と課題",
            "paragraphs": [
                {"text": "定義の要点は、デジタル上の全接点を俯瞰して最適化する統合プロセスにある。", "citations": ["url1"]},
                {"text": "これは重要である。", "citations": []},
            ],
        }
    ]
    gateway = DummyGateway("わかりやすく整理した結果です。")
    rewriter = StructurePreservingStyleRewriter(gateway)

    rewritten = rewriter.rewrite_sections(sections, max_workers=1)

    assert len(rewritten) == 1
    assert len(rewritten[0]["paragraphs"]) == 2
    assert rewritten[0]["paragraphs"][0]["text"] == "わかりやすく整理した結果です。"
    assert rewritten[0]["paragraphs"][0]["citations"] == ["url1"]
    assert gateway.calls == 2


def test_persona_label_inference():
    persona = {"expertise_level": "intermediate", "role": "marketing_manager"}
    label = infer_japanese_persona_label(persona, {})
    assert "マーケティング担当" in label
    assert "2〜3年目" in label


def test_structure_validator_detects_issues():
    markdown = """
## 背景と課題
施策の中核である。
## 背景と課題
別の文章である。
### 詳細
内容A
## 別の章
### 詳細
内容B
"""
    validator = StructureValidator()
    heading_errors = validator.validate_headings(markdown)
    style_errors = validator.check_style_consistency(markdown)

    assert any("背景と課題" in warning for warning in heading_errors)
    assert any("である調" in warning for warning in style_errors)
