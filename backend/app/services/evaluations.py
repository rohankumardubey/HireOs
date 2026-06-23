from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import ROOT_DIR
from app.db.models import EvaluationCaseResult, EvaluationRun
from app.services.scoring import SCORING_POLICY_VERSION, HiringIntelligenceService

DEFAULT_DATASET = ROOT_DIR / "data" / "golden_sets" / "interview_eval_questions.csv"
REQUIRED_COLUMNS = {
    "role",
    "skill_category",
    "question",
    "expected_concepts",
    "strong_answer",
    "weak_answer",
    "min_passing_score",
}


@dataclass
class EvaluationSummary:
    dataset_name: str
    dataset_version: str
    scoring_policy_version: str
    provider: str
    quality_status: str
    total_cases: int
    strong_pass_rate: float
    weak_rejection_rate: float
    average_score_separation: float
    minimum_score_separation: float
    false_negative_count: int
    false_positive_count: int
    regression_count: int
    cases: list[dict]


class EvaluationService:
    def __init__(self, dataset_path: Path = DEFAULT_DATASET) -> None:
        self.dataset_path = dataset_path
        self.scorer = HiringIntelligenceService()

    def evaluate_dataset(self, baseline: EvaluationRun | None = None) -> EvaluationSummary:
        rows = self._load_dataset()
        baseline_cases = {
            result.case_key: result
            for result in (baseline.case_results if baseline else [])
        }
        results: list[dict] = []

        for row in rows:
            expected_concepts = [
                concept.strip()
                for concept in row["expected_concepts"].split("|")
                if concept.strip()
            ]
            question = SimpleNamespace(expected_concepts=expected_concepts)
            strong = self.scorer.score_answer(question, row["strong_answer"])
            weak = self.scorer.score_answer(question, row["weak_answer"])
            min_passing = self._parse_threshold(row["min_passing_score"], row["question"])
            case_key = self._case_key(row)
            strong_passes = strong["total_score"] >= min_passing
            weak_passes = weak["total_score"] >= min_passing
            score_separation = round(strong["total_score"] - weak["total_score"], 2)
            regression_detected, regression_reason = self._detect_regression(
                baseline_cases.get(case_key),
                strong_passes=strong_passes,
                weak_passes=weak_passes,
                score_separation=score_separation,
            )
            results.append(
                {
                    "case_key": case_key,
                    "role": row["role"].strip(),
                    "skill_category": row["skill_category"].strip(),
                    "question": row["question"].strip(),
                    "min_passing_score": min_passing,
                    "strong_score": strong["total_score"],
                    "weak_score": weak["total_score"],
                    "strong_passes": strong_passes,
                    "weak_passes": weak_passes,
                    "score_separation": score_separation,
                    "regression_detected": regression_detected,
                    "regression_reason": regression_reason,
                    "details_json": {
                        "expected_concepts": expected_concepts,
                        "strong": strong,
                        "weak": weak,
                    },
                }
            )

        total = len(results)
        false_negatives = sum(1 for result in results if not result["strong_passes"])
        false_positives = sum(1 for result in results if result["weak_passes"])
        separations = [result["score_separation"] for result in results]
        strong_pass_rate = round(((total - false_negatives) / total) * 100, 2)
        weak_rejection_rate = round(((total - false_positives) / total) * 100, 2)
        regression_count = sum(1 for result in results if result["regression_detected"])

        return EvaluationSummary(
            dataset_name=self.dataset_path.name,
            dataset_version=self._dataset_version(),
            scoring_policy_version=SCORING_POLICY_VERSION,
            provider=self.scorer.llm.provider,
            quality_status=self._quality_status(
                strong_pass_rate=strong_pass_rate,
                weak_rejection_rate=weak_rejection_rate,
                regression_count=regression_count,
            ),
            total_cases=total,
            strong_pass_rate=strong_pass_rate,
            weak_rejection_rate=weak_rejection_rate,
            average_score_separation=round(mean(separations), 2),
            minimum_score_separation=round(min(separations), 2),
            false_negative_count=false_negatives,
            false_positive_count=false_positives,
            regression_count=regression_count,
            cases=results,
        )

    def latest_completed_run(self, db: Session, company_id: str) -> EvaluationRun | None:
        return (
            db.execute(
                select(EvaluationRun)
                .options(selectinload(EvaluationRun.case_results))
                .where(
                    EvaluationRun.company_id == company_id,
                    EvaluationRun.status == "completed",
                )
                .order_by(EvaluationRun.completed_at.desc())
            )
            .scalars()
            .first()
        )

    def persist_results(
        self,
        db: Session,
        *,
        evaluation_run: EvaluationRun,
        summary: EvaluationSummary,
    ) -> None:
        evaluation_run.dataset_name = summary.dataset_name
        evaluation_run.dataset_version = summary.dataset_version
        evaluation_run.scoring_policy_version = summary.scoring_policy_version
        evaluation_run.provider = summary.provider
        evaluation_run.quality_status = summary.quality_status
        evaluation_run.total_cases = summary.total_cases
        evaluation_run.strong_pass_rate = summary.strong_pass_rate
        evaluation_run.weak_rejection_rate = summary.weak_rejection_rate
        evaluation_run.average_score_separation = summary.average_score_separation
        evaluation_run.minimum_score_separation = summary.minimum_score_separation
        evaluation_run.false_negative_count = summary.false_negative_count
        evaluation_run.false_positive_count = summary.false_positive_count
        evaluation_run.regression_count = summary.regression_count

        for result in summary.cases:
            db.add(
                EvaluationCaseResult(
                    evaluation_run_id=evaluation_run.id,
                    **result,
                )
            )

    def _load_dataset(self) -> list[dict[str, str]]:
        if not self.dataset_path.exists():
            raise ValueError(f"Evaluation dataset not found: {self.dataset_path}")

        with self.dataset_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            missing_columns = REQUIRED_COLUMNS - set(reader.fieldnames or [])
            if missing_columns:
                raise ValueError(
                    "Evaluation dataset is missing required columns: "
                    + ", ".join(sorted(missing_columns))
                )
            rows = [dict(row) for row in reader]

        if not rows:
            raise ValueError("Evaluation dataset is empty")

        seen: set[str] = set()
        for row in rows:
            if not row["role"].strip() or not row["question"].strip():
                raise ValueError("Every evaluation case requires a role and question")
            if not row["expected_concepts"].strip():
                raise ValueError(f"Evaluation case has no expected concepts: {row['question']}")
            case_key = self._case_key(row)
            if case_key in seen:
                raise ValueError(f"Duplicate evaluation case: {row['question']}")
            seen.add(case_key)
        return rows

    def _parse_threshold(self, value: str, question: str) -> float:
        try:
            threshold = float(value)
        except ValueError as exc:
            raise ValueError(f"Invalid passing threshold for: {question}") from exc
        if threshold < 0 or threshold > 100:
            raise ValueError(f"Passing threshold must be between 0 and 100 for: {question}")
        return threshold

    def _dataset_version(self) -> str:
        return hashlib.sha256(self.dataset_path.read_bytes()).hexdigest()[:12]

    def _case_key(self, row: dict[str, str]) -> str:
        identity = "|".join(
            [
                row["role"].strip().lower(),
                row["skill_category"].strip().lower(),
                row["question"].strip().lower(),
            ]
        )
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()

    def _detect_regression(
        self,
        baseline: EvaluationCaseResult | None,
        *,
        strong_passes: bool,
        weak_passes: bool,
        score_separation: float,
    ) -> tuple[bool, str | None]:
        if not baseline:
            return False, None
        reasons: list[str] = []
        if baseline.strong_passes and not strong_passes:
            reasons.append("Strong answer changed from pass to fail.")
        if not baseline.weak_passes and weak_passes:
            reasons.append("Weak answer changed from reject to pass.")
        if baseline.score_separation - score_separation >= 5:
            reasons.append("Strong-versus-weak score separation fell by at least 5 points.")
        return bool(reasons), " ".join(reasons) or None

    def _quality_status(
        self,
        *,
        strong_pass_rate: float,
        weak_rejection_rate: float,
        regression_count: int,
    ) -> str:
        if regression_count or weak_rejection_rate < 100 or strong_pass_rate < 60:
            return "failed"
        if strong_pass_rate < 80:
            return "warning"
        return "passed"
