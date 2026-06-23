from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.evaluations import EvaluationService

DATASET = ROOT / "data" / "golden_sets" / "interview_eval_questions.csv"
OUTPUT = ROOT / "data" / "golden_sets" / "interview_eval_results.json"


def main() -> None:
    summary = EvaluationService(DATASET).evaluate_dataset()
    rows = [
        {
            key: value
            for key, value in result.items()
            if key not in {"details_json", "case_key", "regression_detected", "regression_reason"}
        }
        for result in summary.cases
    ]
    OUTPUT.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT}")
    print(
        f"Quality: {summary.quality_status}; strong pass rate: {summary.strong_pass_rate}%; "
        f"weak rejection rate: {summary.weak_rejection_rate}%"
    )


if __name__ == "__main__":
    main()
