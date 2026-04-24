"""Compatibility layer after static question-bank deprecation."""

from dataclasses import dataclass, field


@dataclass
class Question:
    id: str
    title: str
    difficulty: str
    description: str
    examples: list[dict]
    hints: list[str]
    expected_time: str
    expected_space: str
    follow_ups: list[str]
    tags: list[str] = field(default_factory=list)

    @property
    def example_str(self) -> str:
        if not self.examples:
            return ""
        ex = self.examples[0]
        return f"Input: {ex.get('input', '')}, Output: {ex.get('output', '')}"


class QuestionBank:
    """Static JSON question banks are disabled for hackathon compliance."""

    def __init__(self, *args, **kwargs):
        self._bank: dict[str, list[Question]] = {}

    def get_question(self, topic: str, difficulty: str | None = None) -> Question | None:
        return None

    def get_topics(self) -> list[str]:
        return []

    def count(self, topic: str | None = None) -> int:
        return 0
