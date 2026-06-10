from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass
class RedactionSummary:
    sanitized_text: str
    categories: list[str]
    redaction_count: int

    def to_dict(self) -> dict:
        return {
            "redaction_applied": self.redaction_count > 0,
            "redaction_count": self.redaction_count,
            "categories_detected": self.categories,
            "policy_note": (
                "Protected attributes and demographic signals are removed from AI processing. "
                "Recruiters remain responsible for final decisions."
            ),
        }


class FairnessGuard:
    CATEGORY_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
        (
            "age_or_date_of_birth",
            (
                r"\b(?:dob|date of birth)\s*[:\-]?\s*[^\n,;]+",
                r"\bage\s*[:\-]?\s*\d{1,3}\b",
                r"\bborn\s+on\s+[^\n,;]+",
            ),
        ),
        (
            "gender_or_pronouns",
            (
                r"\b(?:he/him|she/her|they/them|male|female|gender)\b",
            ),
        ),
        (
            "marital_status",
            (
                r"\b(?:single|married|divorced|widowed|marital status)\b",
            ),
        ),
        (
            "religion",
            (
                r"\b(?:religion|hindu|muslim|christian|sikh|jain|buddhist)\b",
            ),
        ),
        (
            "caste_or_ethnicity",
            (
                r"\b(?:caste|ethnicity|tribe|scheduled caste|scheduled tribe)\b",
            ),
        ),
        (
            "disability_or_health",
            (
                r"\b(?:disabled|disability|wheelchair|deaf|blind|medical condition|mental health)\b",
            ),
        ),
    )

    def sanitize_text(self, text: str) -> RedactionSummary:
        sanitized = text
        categories: list[str] = []
        redaction_count = 0

        for category, patterns in self.CATEGORY_PATTERNS:
            category_count = 0
            for pattern in patterns:
                sanitized, replacements = re.subn(
                    pattern,
                    f"[redacted:{category}]",
                    sanitized,
                    flags=re.IGNORECASE,
                )
                category_count += replacements
            if category_count:
                categories.append(category)
                redaction_count += category_count

        return RedactionSummary(
            sanitized_text=sanitized,
            categories=categories,
            redaction_count=redaction_count,
        )
