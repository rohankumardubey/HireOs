from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.scoring import HiringIntelligenceService

DATASET = ROOT / "data" / "golden_sets" / "interview_eval_questions.csv"
OUTPUT = ROOT / "data" / "golden_sets" / "interview_eval_results.json"


def main() -> None:
    scorer = HiringIntelligenceService()
    rows = []
    with DATASET.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            question = SimpleNamespace(
                expected_concepts=[concept.strip() for concept in row["expected_concepts"].split("|") if concept.strip()]
            )
            strong = scorer.score_answer(question, row["strong_answer"])
            weak = scorer.score_answer(question, row["weak_answer"])
            min_passing = float(row["min_passing_score"])
            rows.append(
                {
                    "role": row["role"],
                    "skill_category": row["skill_category"],
                    "question": row["question"],
                    "strong_score": strong["total_score"],
                    "weak_score": weak["total_score"],
                    "min_passing_score": min_passing,
                    "strong_passes": strong["total_score"] >= min_passing,
                    "weak_passes": weak["total_score"] >= min_passing,
                }
            )
    OUTPUT.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
