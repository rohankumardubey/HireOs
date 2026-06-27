from __future__ import annotations

from datetime import UTC, datetime
from statistics import mean

from sqlalchemy import func, select
from sqlalchemy.orm import Session

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


ADVANCE_DECISIONS = {"shortlisted", "moved_to_next_round", "hired"}
NEGATIVE_DECISIONS = {"rejected", "archived"}


class ShortlistBriefService:
    def build(self, db: Session, *, company_id: str, job_id: str) -> dict:
        job = db.execute(select(Job).where(Job.id == job_id, Job.company_id == company_id)).scalar_one_or_none()
        if not job:
            raise ValueError("Job not found")

        rows = (
            db.execute(
                select(Candidate, CandidateJobMatch)
                .join(CandidateJobMatch, CandidateJobMatch.candidate_id == Candidate.id)
                .where(
                    Candidate.company_id == company_id,
                    Candidate.is_deleted.is_(False),
                    CandidateJobMatch.job_id == job_id,
                )
            )
            .all()
        )
        snapshots = [self._candidate_snapshot(db, job, candidate, match) for candidate, match in rows]
        snapshots.sort(key=lambda item: (item["final_score"], item["resume_match_score"], item["interview_score"]), reverse=True)

        candidates = []
        for rank, snapshot in enumerate(snapshots, start=1):
            candidates.append(
                {
                    "rank": rank,
                    **snapshot,
                }
            )

        top_candidates = candidates[:3]
        final_scores = [candidate["final_score"] for candidate in candidates]
        human_review_count = sum(1 for candidate in candidates if candidate["human_review_required"])
        advanced_count = sum(1 for candidate in candidates if candidate["recruiter_decision"] in ADVANCE_DECISIONS)
        no_interview_count = sum(1 for candidate in candidates if candidate["interview_status"] == "not_started")

        risk_flags = self._risk_flags(
            total_candidates=len(candidates),
            human_review_count=human_review_count,
            no_interview_count=no_interview_count,
            top_candidates=top_candidates,
        )

        return {
            "job_id": job.id,
            "job_title": job.title,
            "generated_at": datetime.now(UTC),
            "summary": {
                "total_matched_candidates": len(candidates),
                "recommended_shortlist_count": len(top_candidates),
                "human_review_required_count": human_review_count,
                "advanced_decision_count": advanced_count,
                "average_final_score": round(mean(final_scores), 2) if final_scores else 0.0,
                "top_candidate_id": top_candidates[0]["candidate_id"] if top_candidates else None,
            },
            "hiring_manager_summary": self._hiring_manager_summary(job, top_candidates, len(candidates)),
            "candidates": candidates[:5],
            "discussion_questions": self._discussion_questions(job, top_candidates),
            "risk_flags": risk_flags,
            "policy_note": (
                "Shortlist briefs summarize current evidence for recruiter and hiring-manager review. "
                "They are not automated hiring decisions, and candidates with review flags should be discussed before advancement."
            ),
        }

    def _candidate_snapshot(self, db: Session, job: Job, candidate: Candidate, match: CandidateJobMatch) -> dict:
        interview = (
            db.execute(
                select(Interview)
                .where(Interview.candidate_id == candidate.id, Interview.job_id == job.id)
                .order_by(Interview.created_at.desc())
            )
            .scalars()
            .first()
        )
        interview_score = (
            db.scalar(
                select(func.avg(AnswerScore.total_score))
                .join(InterviewAnswer, InterviewAnswer.id == AnswerScore.answer_id)
                .join(Interview, Interview.id == InterviewAnswer.interview_id)
                .where(Interview.candidate_id == candidate.id, Interview.job_id == job.id)
            )
            or 0
        )
        report = None
        if interview:
            report = db.execute(select(InterviewReport).where(InterviewReport.interview_id == interview.id)).scalar_one_or_none()
        decision = (
            db.execute(
                select(RecruiterDecision)
                .where(RecruiterDecision.candidate_id == candidate.id, RecruiterDecision.job_id == job.id)
                .order_by(RecruiterDecision.created_at.desc())
            )
            .scalars()
            .first()
        )

        required_skills = (job.jd_analysis or {}).get("required_skills") or []
        matched_required = list(match.matched_required_skills or [])
        missing_required = list(match.missing_required_skills or [])
        must_have_coverage = round((len(matched_required) / max(len(required_skills), 1)) * 100, 2)
        resume_match_score = round(float(match.overall_score or 0), 2)
        interview_score_value = round(float(interview_score), 2)
        final_score = round((resume_match_score * 0.55) + (interview_score_value * 0.45), 2)
        human_review_required = bool(
            match.human_review_required
            or (report and report.human_review_required)
            or candidate.status == "human_review_required"
        )

        strengths = self._strengths(
            matched_required=matched_required,
            must_have_coverage=must_have_coverage,
            interview_score=interview_score_value,
            decision=decision.decision if decision else None,
            candidate=candidate,
        )
        risks = self._risks(
            missing_required=missing_required,
            human_review_required=human_review_required,
            interview=interview,
            interview_score=interview_score_value,
            decision=decision.decision if decision else None,
        )

        return {
            "candidate_id": candidate.id,
            "candidate_name": candidate.name,
            "candidate_email": candidate.email,
            "status": candidate.status,
            "current_role": candidate.current_role,
            "years_experience": candidate.years_experience,
            "resume_match_score": resume_match_score,
            "interview_score": interview_score_value,
            "final_score": final_score,
            "must_have_coverage": must_have_coverage,
            "confidence_score": round(float(match.confidence_score or 0) * 100, 2),
            "ai_recommendation": match.match_recommendation,
            "recruiter_decision": decision.decision if decision else None,
            "human_review_required": human_review_required,
            "interview_status": interview.status if interview else "not_started",
            "matched_required_skills": matched_required,
            "missing_required_skills": missing_required,
            "strengths": strengths,
            "risks": risks,
            "evidence_summary": self._evidence_summary(
                candidate_name=candidate.name,
                must_have_coverage=must_have_coverage,
                interview_score=interview_score_value,
                missing_required=missing_required,
                human_review_required=human_review_required,
            ),
            "suggested_next_step": self._suggested_next_step(
                final_score=final_score,
                missing_required=missing_required,
                human_review_required=human_review_required,
                decision=decision.decision if decision else None,
                interview=interview,
            ),
            "report_excerpt": report.recommended_next_step if report else "No interview report has been generated yet.",
        }

    def _strengths(
        self,
        *,
        matched_required: list[str],
        must_have_coverage: float,
        interview_score: float,
        decision: str | None,
        candidate: Candidate,
    ) -> list[str]:
        strengths: list[str] = []
        if matched_required:
            strengths.append(f"Covers {len(matched_required)} must-have skills.")
        if must_have_coverage >= 80:
            strengths.append("Strong must-have skill coverage for the role.")
        if interview_score >= 70:
            strengths.append("Interview evidence is strong enough for manager discussion.")
        if decision in ADVANCE_DECISIONS:
            strengths.append("Recruiter already recorded an advance-oriented decision.")
        if candidate.years_experience >= 5:
            strengths.append("Experience level supports higher ownership expectations.")
        return strengths or ["Relevant baseline evidence exists, but the candidate needs more validation."]

    def _risks(
        self,
        *,
        missing_required: list[str],
        human_review_required: bool,
        interview: Interview | None,
        interview_score: float,
        decision: str | None,
    ) -> list[str]:
        risks: list[str] = []
        if missing_required:
            risks.append(f"Missing must-have skills: {', '.join(missing_required[:4])}.")
        if human_review_required:
            risks.append("Requires explicit human review before advancement.")
        if not interview:
            risks.append("Interview has not been invited or started yet.")
        elif interview.status != "completed":
            risks.append("Interview evidence is incomplete.")
        if interview_score and interview_score < 60:
            risks.append("Interview answer score is below the usual discussion threshold.")
        if decision in NEGATIVE_DECISIONS:
            risks.append("Latest recruiter decision is negative.")
        return risks or ["No major shortlist-blocking risk detected from current evidence."]

    def _evidence_summary(
        self,
        *,
        candidate_name: str,
        must_have_coverage: float,
        interview_score: float,
        missing_required: list[str],
        human_review_required: bool,
    ) -> str:
        review_clause = " A human-review flag is active." if human_review_required else ""
        missing_clause = (
            f" Missing skills to discuss: {', '.join(missing_required[:3])}."
            if missing_required
            else " No missing must-have skills are currently recorded."
        )
        return (
            f"{candidate_name} has {must_have_coverage:.0f}% must-have coverage and "
            f"{interview_score:.0f}% average interview evidence.{missing_clause}{review_clause}"
        )

    def _suggested_next_step(
        self,
        *,
        final_score: float,
        missing_required: list[str],
        human_review_required: bool,
        decision: str | None,
        interview: Interview | None,
    ) -> str:
        if decision in ADVANCE_DECISIONS:
            return "Align with the hiring manager on next-round focus areas."
        if decision in NEGATIVE_DECISIONS:
            return "Keep out of the shortlist unless new evidence changes the decision."
        if not interview:
            return "Invite the candidate to interview before making a shortlist recommendation."
        if human_review_required:
            return "Resolve human-review flags and document the recruiter rationale."
        if final_score >= 75 and not missing_required:
            return "Recommend for hiring-manager shortlist review."
        if final_score >= 60:
            return "Discuss as a backup candidate with clear evidence gaps."
        return "Hold until more evidence is available."

    def _hiring_manager_summary(self, job: Job, top_candidates: list[dict], total_candidates: int) -> str:
        if not total_candidates:
            return f"No matched candidates are available yet for {job.title}."
        names = ", ".join(candidate["candidate_name"] for candidate in top_candidates) or "No candidates"
        leader = top_candidates[0] if top_candidates else None
        if not leader:
            return f"No shortlist-ready candidates are available yet for {job.title}."
        return (
            f"For {job.title}, HireOS recommends reviewing {names}. "
            f"{leader['candidate_name']} currently leads with a {leader['final_score']:.0f}% blended evidence score. "
            "Use the brief to discuss must-have coverage, missing skills, interview evidence, and human-review flags."
        )

    def _discussion_questions(self, job: Job, top_candidates: list[dict]) -> list[str]:
        if not top_candidates:
            return [
                f"What evidence is still needed before creating a shortlist for {job.title}?",
                "Which sourcing channels should produce the next candidate batch?",
                "Are the must-have skills too restrictive for the available pipeline?",
            ]

        leader = top_candidates[0]
        questions = [
            f"Does {leader['candidate_name']}'s must-have coverage match what the hiring manager needs in the first 90 days?",
            "Which missing skills are true blockers versus trainable gaps?",
            "Do any human-review flags require calibration before advancement?",
        ]
        if len(top_candidates) > 1:
            questions.append(
                f"What tradeoff matters more between {top_candidates[0]['candidate_name']} and {top_candidates[1]['candidate_name']}: immediate skill coverage or interview evidence?"
            )
        return questions

    def _risk_flags(
        self,
        *,
        total_candidates: int,
        human_review_count: int,
        no_interview_count: int,
        top_candidates: list[dict],
    ) -> list[str]:
        flags: list[str] = []
        if not total_candidates:
            flags.append("No matched candidates are available for this role yet.")
        if human_review_count:
            flags.append(f"{human_review_count} candidate(s) require human review before a final decision.")
        if no_interview_count:
            flags.append(f"{no_interview_count} candidate(s) have not started interview evidence collection.")
        if top_candidates and all(candidate["missing_required_skills"] for candidate in top_candidates):
            flags.append("Every recommended candidate is missing at least one must-have skill.")
        return flags or ["No major shortlist-level risks detected from current evidence."]
