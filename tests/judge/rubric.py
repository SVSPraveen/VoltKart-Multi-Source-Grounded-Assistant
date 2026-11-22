"""tests/judge/rubric.py - Evaluation Rubric Dimensions for Calibrated Judge (V7).

Defines scoring criteria across 6 core dimensions:
1. correctness: Numeric accuracy within 0.01 tolerance, correct entities, expected facts.
2. provenance: Correct document version cited; explicit fallback disclosure when older version answers.
3. citation_sufficiency: Required citations present with verifiable SQL or exact quotes.
4. abstention_honesty: Correct abstention when data is absent, tier is unknown, or web is off.
5. grounding_faithfulness: No hallucinated numbers or fabricated delivery dates/claims.
6. formatting_tone: Professional tone, proper currency notation (₹/INR), clean presentation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DimensionScore:
    name: str
    weight: float
    score: float  # 0.0 to 1.0
    passed: bool
    reason: str


@dataclass
class JudgeVerdict:
    question_id: str
    passed: bool
    overall_score: float  # 0.0 to 1.0
    dimension_scores: dict[str, DimensionScore] = field(default_factory=dict)
    feedback: list[str] = field(default_factory=list)
    raw_response: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "passed": self.passed,
            "overall_score": round(self.overall_score, 3),
            "dimensions": {
                name: {
                    "score": round(dim.score, 3),
                    "passed": dim.passed,
                    "weight": dim.weight,
                    "reason": dim.reason,
                }
                for name, dim in self.dimension_scores.items()
            },
            "feedback": self.feedback,
            "raw_response": self.raw_response,
        }
