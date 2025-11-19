from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import List


class StructureValidator:
    """Detect structural issues that make drafts feel machine-generated."""

    @staticmethod
    def validate_headings(markdown: str) -> List[str]:
        """Check for repeated headings and awkward hierarchy."""
        if not markdown:
            return []

        warnings: List[str] = []
        h2_pattern = re.compile(r"^##\s+(.+)$", re.MULTILINE)
        h2_headings = [heading.strip() for heading in h2_pattern.findall(markdown) if heading.strip()]
        h2_counts = Counter(h2_headings)
        for heading, count in h2_counts.items():
            if count > 1:
                warnings.append(f"H2が重複しています: 「{heading}」が{count}回出現")

        current_h2 = None
        h3_parent_map = defaultdict(set)
        h3_pattern = re.compile(r"^###\s+(.+)$")
        for line in markdown.splitlines():
            line = line.rstrip()
            if not line:
                continue
            h2_match = h2_pattern.match(line)
            if h2_match:
                current_h2 = h2_match.group(1).strip()
                continue
            h3_match = h3_pattern.match(line)
            if h3_match:
                heading = h3_match.group(1).strip()
                if heading:
                    h3_parent_map[heading].add(current_h2 or "__root__")

        for heading, parents in h3_parent_map.items():
            if len(parents) > 1:
                warnings.append(f"H3「{heading}」が複数のH2配下で使われています: {', '.join(parents)}")

        return warnings

    @staticmethod
    def validate_sentence_length(markdown: str, max_length: int = 80) -> List[str]:
        """Ensure each sentence stays within the desired limit."""
        if not markdown:
            return []

        sentences = re.split(r"[。！？\n]", markdown)
        warnings: List[str] = []

        for idx, sentence in enumerate(sentences, 1):
            cleaned = re.sub(r"[#>*_`\\[\\]\\(\\)]", "", sentence).strip()
            if len(cleaned) > max_length:
                snippet = cleaned[:50] + ("…" if len(cleaned) > 50 else "")
                warnings.append(f"文{idx}が{len(cleaned)}文字です（推奨: {max_length}文字以内）: {snippet}")

        return warnings

    @staticmethod
    def check_style_consistency(markdown: str) -> List[str]:
        """Detect 'である調' drift inside otherwise polite copy."""
        if not markdown:
            return []

        patterns = [
            r"[^。！？\s]{2,}である。",
            r"[^。！？\s]{2,}にある。",
            r"[^。！？\s]{2,}が中核である。",
        ]
        warnings: List[str] = []
        for pattern in patterns:
            matches = re.findall(pattern, markdown)
            if matches:
                warnings.append(f"「である調」が検出されました: {', '.join(matches[:3])}")

        return warnings
