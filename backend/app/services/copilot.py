from __future__ import annotations

from statistics import mean

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    AnswerScore,
    Candidate,
    CandidateJobMatch,
    Interview,
    InterviewAnswer,
    InterviewReport,
    Job,
    RecruiterDecision,
)


class RecruiterCopilotService:
    def answer_query(
        self,
        db: Session,
        *,
        company_id: str,
        query: str,
        job_id: str | None = None,
        candidate_ids: list[str] | None = None,
    ) -> dict:
        normalized = query.lower().strip()
        job = self._resolve_job(db, company_id=company_id, job_id=job_id)
        candidates = self._resolve_candidates(
            db,
            company_id=company_id,
            candidate_ids=candidate_ids,
            query=normalized,
            job_id=job.id if job else None,
        )

        if ("compare" in normalized or "above" in normalized or "vs" in normalized) and len(candidates) >= 2:
            return self._compare_candidates(db, job, candidates[:2])
        if "missing" in normalized and ("strong" in normalized or "filter" in normalized or "show me" in normalized):
            return self._filter_candidates(db, job, candidates, normalized)
        if "summary" in normalized or "shortlist" in normalized or "hiring manager" in normalized:
            return self._shortlist_summary(db, job, candidates)
        if "why" in normalized or "evidence" in normalized or "score" in normalized:
            return self._why_score(db, job, candidates[:1])
        return self._next_actions(db, job, candidates)

    def _resolve_job(self, db: Session, *, company_id: str, job_id: str | None) -> Job | None:
        if job_id:
            return db.execute(select(Job).where(Job.id == job_id, Job.company_id == company_id)).scalar_one_or_none()
        return db.execute(
            select(Job).where(Job.company_id == company_id, Job.status == "open").order_by(Job.created_at.desc())
        ).scalar_one_or_none()

    def _resolve_candidates(
        self,
        db: Session,
        *,
        company_id: str,
        candidate_ids: list[str] | None,
        query: str,
        job_id: str | None,
    ) -> list[Candidate]:
        if candidate_ids:
            return (
                db.execute(
                    select(Candidate)
                    .options(selectinload(Candidate.skills))
                    .where(Candidate.company_id == company_id, Candidate.id.in_(candidate_ids))
                )
                .scalars()
                .all()
            )

        candidates = (
            db.execute(
                select(Candidate)
                .options(selectinload(Candidate.skills))
                .where(Candidate.company_id == company_id)
                .order_by(Candidate.created_at.desc())
            )
            .scalars()
            .all()
        )
        mentioned = [candidate for candidate in candidates if candidate.name.lower() in query]
        if mentioned:
            return mentioned
        if job_id:
            matched_ids = (
                db.execute(
                    select(CandidateJobMatch.candidate_id)
                    .where(CandidateJobMatch.job_id == job_id)
                    .order_by(CandidateJobMatch.overall_score.desc())
                )
                .scalars()
                .all()
            )
            if matched_ids:
                lookup = {candidate.id: candidate for candidate in candidates}
                return [lookup[candidate_id] for candidate_id in matched_ids if candidate_id in lookup]
        return candidates[:5]

    def _candidate_snapshot(self, db: Session, job: Job | None, candidate: Candidate) -> dict:
        match = None
        if job:
            match = db.execute(
                select(CandidateJobMatch).where(CandidateJobMatch.candidate_id == candidate.id, CandidateJobMatch.job_id == job.id)
            ).scalar_one_or_none()
        interview_query = select(Interview).where(Interview.candidate_id == candidate.id)
        if job:
            interview_query = interview_query.where(Interview.job_id == job.id)
        interview = db.execute(interview_query.order_by(Interview.created_at.desc())).scalar_one_or_none()
        avg_score_query = (
            select(func.avg(AnswerScore.total_score))
            .join(InterviewAnswer, InterviewAnswer.id == AnswerScore.answer_id)
            .join(Interview, Interview.id == InterviewAnswer.interview_id)
            .where(Interview.candidate_id == candidate.id)
        )
        if job:
            avg_score_query = avg_score_query.where(Interview.job_id == job.id)
        avg_score = db.scalar(avg_score_query) or 0
        report = None
        if interview:
            report = db.execute(select(InterviewReport).where(InterviewReport.interview_id == interview.id)).scalar_one_or_none()
        decision_query = select(RecruiterDecision).where(RecruiterDecision.candidate_id == candidate.id)
        if job:
            decision_query = decision_query.where(RecruiterDecision.job_id == job.id)
        decision = db.execute(decision_query.order_by(RecruiterDecision.created_at.desc())).scalar_one_or_none()
        return {
            "candidate": candidate,
            "match": match,
            "avg_interview_score": round(float(avg_score), 2),
            "report": report,
            "decision": decision,
        }

    def _compare_candidates(self, db: Session, job: Job | None, candidates: list[Candidate]) -> dict:
        left = self._candidate_snapshot(db, job, candidates[0])
        right = self._candidate_snapshot(db, job, candidates[1])
        left_final = (left["match"].overall_score if left["match"] else 0) * 0.55 + left["avg_interview_score"] * 0.45
        right_final = (right["match"].overall_score if right["match"] else 0) * 0.55 + right["avg_interview_score"] * 0.45
        winner = left if left_final >= right_final else right
        loser = right if winner is left else left
        winner_candidate = winner["candidate"]
        loser_candidate = loser["candidate"]
        answer = (
            f"{winner_candidate.name} is currently stronger than {loser_candidate.name} for "
            f"{job.title if job else 'the selected role'} based on combined resume alignment and interview evidence."
        )
        evidence = [
            {
                "label": winner_candidate.name,
                "resume_match": round((winner["match"].overall_score if winner["match"] else 0), 2),
                "interview_score": winner["avg_interview_score"],
                "missing_skills": winner["match"].missing_required_skills[:4] if winner["match"] else [],
            },
            {
                "label": loser_candidate.name,
                "resume_match": round((loser["match"].overall_score if loser["match"] else 0), 2),
                "interview_score": loser["avg_interview_score"],
                "missing_skills": loser["match"].missing_required_skills[:4] if loser["match"] else [],
            },
        ]
        return {
            "answer": answer,
            "recommendation": f"Prioritize {winner_candidate.name} for recruiter review, but keep {loser_candidate.name} visible if missing-skill coverage is close.",
            "follow_up_questions": [
                f"Do you want a hiring-manager summary for {winner_candidate.name}?",
                f"Should I isolate candidates with fewer missing skills than {loser_candidate.name}?",
            ],
            "action_items": [
                f"Review the missing required skills for {loser_candidate.name}.",
                f"Confirm whether interview depth or must-have skill coverage matters more for {job.title if job else 'this role'}.",
            ],
            "evidence": evidence,
            "human_review_note": "Candidate comparison is advisory and should be reviewed by a recruiter before any decision.",
        }

    def _extract_skill_filters(self, query: str) -> tuple[str | None, str | None]:
        missing_skill = None
        strong_skill = None
        tokens = query.replace(",", " ").split()
        if "missing" in tokens:
            index = tokens.index("missing")
            if index + 1 < len(tokens):
                missing_skill = tokens[index + 1]
        if "strong" in tokens and "in" in tokens:
            index = tokens.index("in")
            if index + 1 < len(tokens):
                strong_skill = tokens[index + 1]
        return missing_skill, strong_skill

    def _filter_candidates(self, db: Session, job: Job | None, candidates: list[Candidate], query: str) -> dict:
        missing_skill, strong_skill = self._extract_skill_filters(query)
        matches = []
        for candidate in candidates:
            snapshot = self._candidate_snapshot(db, job, candidate)
            missing = {skill.lower() for skill in (snapshot["match"].missing_required_skills if snapshot["match"] else [])}
            strengths = {skill.name.lower() for skill in candidate.skills}
            if missing_skill and missing_skill.lower() not in missing:
                continue
            if strong_skill and strong_skill.lower() not in strengths:
                continue
            matches.append(snapshot)
        answer = (
            f"Found {len(matches)} candidates matching the current filter for "
            f"{job.title if job else 'the selected role'}."
        )
        return {
            "answer": answer,
            "recommendation": "Use these candidates as a focused manual review queue rather than an automatic reject list.",
            "follow_up_questions": [
                "Should I summarize the strongest candidates from this filtered set?",
                "Do you want to compare these candidates against the top-ranked shortlist?",
            ],
            "action_items": [
                "Check whether the missing skill is genuinely must-have or trainable.",
                "Verify if strong adjacent skills compensate for the gap.",
            ],
            "evidence": [
                {
                    "label": snapshot["candidate"].name,
                    "resume_match": round((snapshot["match"].overall_score if snapshot["match"] else 0), 2),
                    "interview_score": snapshot["avg_interview_score"],
                    "missing_skills": snapshot["match"].missing_required_skills[:4] if snapshot["match"] else [],
                    "strength_skills": [skill.name for skill in snapshot["candidate"].skills[:5]],
                }
                for snapshot in matches[:5]
            ],
            "human_review_note": "Filtered candidate lists should guide recruiter attention, not silently narrow the funnel.",
        }

    def _shortlist_summary(self, db: Session, job: Job | None, candidates: list[Candidate]) -> dict:
        snapshots = [self._candidate_snapshot(db, job, candidate) for candidate in candidates[:5]]
        ranked = sorted(
            snapshots,
            key=lambda snapshot: ((snapshot["match"].overall_score if snapshot["match"] else 0) * 0.55) + snapshot["avg_interview_score"] * 0.45,
            reverse=True,
        )
        average_match = round(mean([(item["match"].overall_score if item["match"] else 0) for item in ranked]), 2) if ranked else 0
        answer = (
            f"Shortlist summary for {job.title if job else 'the selected role'}: "
            f"{len(ranked)} candidates in scope, average resume-match score {average_match}, "
            "with recruiter review still needed on low-confidence cases."
        )
        return {
            "answer": answer,
            "recommendation": "Share the top two or three candidates with the hiring manager together with their evidence-backed strengths and missing-skill risks.",
            "follow_up_questions": [
                "Should I draft a hiring-manager note from this shortlist?",
                "Do you want only candidates without critical missing skills?",
            ],
            "action_items": [
                "Review candidates that have strong interview performance but weaker must-have skill coverage.",
                "Capture recruiter notes before forwarding to the hiring manager.",
            ],
            "evidence": [
                {
                    "label": snapshot["candidate"].name,
                    "resume_match": round((snapshot["match"].overall_score if snapshot["match"] else 0), 2),
                    "interview_score": snapshot["avg_interview_score"],
                    "ai_recommendation": snapshot["match"].match_recommendation if snapshot["match"] else "needs_human_review",
                    "report_excerpt": (snapshot["report"].recommended_next_step if snapshot["report"] else "No interview report yet."),
                }
                for snapshot in ranked[:5]
            ],
            "human_review_note": "Hiring-manager summaries should include recruiter context and not rely only on AI rankings.",
        }

    def _why_score(self, db: Session, job: Job | None, candidates: list[Candidate]) -> dict:
        if not candidates:
            return self._next_actions(db, job, candidates)
        snapshot = self._candidate_snapshot(db, job, candidates[0])
        candidate = snapshot["candidate"]
        match = snapshot["match"]
        report = snapshot["report"]
        answer = (
            f"{candidate.name}'s current score is driven by "
            f"{round((match.overall_score if match else 0), 2)} resume-match points and "
            f"{snapshot['avg_interview_score']} interview points, with explanation stored for recruiter review."
        )
        return {
            "answer": answer,
            "recommendation": "Review the missing concepts and missing required skills before deciding whether to advance or hold.",
            "follow_up_questions": [
                f"Do you want me to compare {candidate.name} with another candidate?",
                f"Should I draft a recruiter summary for {candidate.name}?",
            ],
            "action_items": [
                "Inspect the AI explanation before making a final recruiter decision.",
                "Check whether low score drivers are must-have skill gaps or interview communication gaps.",
            ],
            "evidence": [
                {
                    "label": candidate.name,
                    "resume_match": round((match.overall_score if match else 0), 2),
                    "missing_skills": match.missing_required_skills[:5] if match else [],
                    "match_explanation": match.explanation if match else "No match explanation stored.",
                    "report_excerpt": report.recommended_next_step if report else "No interview report yet.",
                }
            ],
            "human_review_note": "Scores should be interpreted with their explanation and confidence, not as a standalone pass/fail output.",
        }

    def _next_actions(self, db: Session, job: Job | None, candidates: list[Candidate]) -> dict:
        snapshots = [self._candidate_snapshot(db, job, candidate) for candidate in candidates[:5]]
        review_count = sum(
            1
            for snapshot in snapshots
            if (snapshot["match"] and snapshot["match"].human_review_required)
            or (snapshot["report"] and snapshot["report"].human_review_required)
        )
        answer = (
            f"For {job.title if job else 'the current hiring queue'}, the most useful next step is to review "
            f"{review_count} low-confidence or human-review-required candidates before advancing the shortlist."
        )
        return {
            "answer": answer,
            "recommendation": "Focus first on candidates with high alignment but unresolved gaps, then prepare hiring-manager-ready summaries for the best two or three.",
            "follow_up_questions": [
                "Would you like a shortlist summary?",
                "Do you want to compare the top two candidates?",
            ],
            "action_items": [
                "Review candidates marked as human review required.",
                "Confirm whether any missing required skills are acceptable trade-offs.",
                "Create a hiring-manager note for the strongest candidates.",
            ],
            "evidence": [
                {
                    "label": snapshot["candidate"].name,
                    "resume_match": round((snapshot["match"].overall_score if snapshot["match"] else 0), 2),
                    "interview_score": snapshot["avg_interview_score"],
                    "human_review_required": bool(
                        (snapshot["match"] and snapshot["match"].human_review_required)
                        or (snapshot["report"] and snapshot["report"].human_review_required)
                    ),
                }
                for snapshot in snapshots[:5]
            ],
            "human_review_note": "The copilot recommends review order and evidence, but final decisions stay with the recruiter.",
        }

