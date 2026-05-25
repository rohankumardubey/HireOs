from __future__ import annotations

from statistics import mean

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import AnswerScore, Candidate, CandidateJobMatch, Interview, InterviewAnswer, InterviewReport, Job, RecruiterDecision


class CandidateComparisonService:
    def compare(self, db: Session, *, company_id: str, job_id: str, candidate_ids: list[str]) -> dict:
        job = db.execute(select(Job).where(Job.id == job_id, Job.company_id == company_id)).scalar_one_or_none()
        if not job:
            raise ValueError("Job not found")

        candidates = (
            db.execute(
                select(Candidate)
                .options(selectinload(Candidate.skills))
                .where(Candidate.company_id == company_id, Candidate.id.in_(candidate_ids))
            )
            .scalars()
            .all()
        )
        if len(candidates) < 2:
            raise ValueError("Select at least two candidates")

        snapshots = [self._snapshot(db, job, candidate) for candidate in candidates]
        ranked = sorted(snapshots, key=lambda item: item["final_score"], reverse=True)
        winner = ranked[0]
        runner_up = ranked[1]

        answer = (
            f"{winner['candidate'].name} currently leads the comparison for {job.title}, "
            f"with a final weighted score of {winner['final_score']} versus {runner_up['final_score']}."
        )
        summary = (
            f"{winner['candidate'].name} leads on combined must-have coverage and interview evidence. "
            "Use this comparison to guide recruiter review, not to automate a decision."
        )
        recommendation = (
            f"Review {winner['candidate'].name} first with the hiring manager, then keep {runner_up['candidate'].name} in discussion if the role tolerates some missing skills."
        )

        axes = [
            {
                "label": "Must-have coverage",
                "winner_candidate_id": max(ranked, key=lambda item: item["must_have_coverage"])["candidate"].id,
                "description": "Share of required skills covered by the candidate profile.",
            },
            {
                "label": "Interview evidence",
                "winner_candidate_id": max(ranked, key=lambda item: item["interview_score"])["candidate"].id,
                "description": "Average semantic interview score across answered questions.",
            },
            {
                "label": "Risk posture",
                "winner_candidate_id": min(ranked, key=lambda item: item["risk_score"])["candidate"].id,
                "description": "Lower risk means fewer missing must-have skills and fewer review flags.",
            },
        ]

        candidates_payload = [
            {
                "candidate_id": snapshot["candidate"].id,
                "candidate_name": snapshot["candidate"].name,
                "status": snapshot["candidate"].status,
                "current_role": snapshot["candidate"].current_role,
                "years_experience": snapshot["candidate"].years_experience,
                "resume_match_score": snapshot["resume_match_score"],
                "interview_score": snapshot["interview_score"],
                "final_score": snapshot["final_score"],
                "must_have_coverage": snapshot["must_have_coverage"],
                "confidence_score": snapshot["confidence_score"],
                "human_review_required": snapshot["human_review_required"],
                "strengths": snapshot["strengths"],
                "missing_skills": snapshot["missing_skills"],
                "matched_skills": snapshot["matched_skills"],
                "risk_notes": snapshot["risk_notes"],
                "ai_recommendation": snapshot["ai_recommendation"],
                "recruiter_decision": snapshot["recruiter_decision"],
                "report_excerpt": snapshot["report_excerpt"],
            }
            for snapshot in ranked
        ]

        recruiter_questions = [
            f"Is the role optimized for immediate delivery or trainable upside between {winner['candidate'].name} and {runner_up['candidate'].name}?",
            "Do missing skills block advancement, or can stronger interview evidence outweigh them?",
            "Which candidate should receive the next live interview based on current evidence gaps?",
        ]

        return {
            "job_id": job.id,
            "job_title": job.title,
            "summary": summary,
            "recommendation": recommendation,
            "top_candidate_id": winner["candidate"].id,
            "comparison_answer": answer,
            "axes": axes,
            "candidates": candidates_payload,
            "recruiter_questions": recruiter_questions,
            "human_review_note": "Comparison results are decision-support evidence and should be reviewed by a recruiter or hiring manager.",
        }

    def _snapshot(self, db: Session, job: Job, candidate: Candidate) -> dict:
        match = db.execute(
            select(CandidateJobMatch).where(CandidateJobMatch.candidate_id == candidate.id, CandidateJobMatch.job_id == job.id)
        ).scalar_one_or_none()
        interview = db.execute(
            select(Interview).where(Interview.candidate_id == candidate.id, Interview.job_id == job.id).order_by(Interview.created_at.desc())
        ).scalar_one_or_none()
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
        decision = db.execute(
            select(RecruiterDecision)
            .where(RecruiterDecision.candidate_id == candidate.id, RecruiterDecision.job_id == job.id)
            .order_by(RecruiterDecision.created_at.desc())
        ).scalar_one_or_none()
        required = job.jd_analysis.get("required_skills", [])
        matched = match.matched_required_skills if match else []
        missing = match.missing_required_skills if match else []
        coverage = round((len(matched) / max(len(required), 1)) * 100, 2)
        final_score = round(((match.overall_score if match else 0) * 0.55) + (float(interview_score) * 0.45), 2)
        human_review_required = bool((match and match.human_review_required) or (report and report.human_review_required))
        risk_score = len(missing) * 20 + (15 if human_review_required else 0)
        strengths = []
        if matched:
            strengths.append(f"Matches {len(matched)} required skills.")
        if interview_score >= 70:
            strengths.append("Interview evidence shows strong answer quality.")
        if candidate.years_experience >= 5:
            strengths.append("Experience band supports deeper ownership expectations.")
        if not strengths:
            strengths.append("Candidate has baseline relevance but needs more validation.")
        risk_notes = []
        if missing:
            risk_notes.append(f"Missing required skills: {', '.join(missing[:3])}.")
        if human_review_required:
            risk_notes.append("AI output requires explicit human review.")
        if interview_score < 60:
            risk_notes.append("Interview evidence is still weak or incomplete.")
        if not risk_notes:
            risk_notes.append("No major structural risk flags detected in current evidence.")

        return {
            "candidate": candidate,
            "resume_match_score": round((match.overall_score if match else 0), 2),
            "interview_score": round(float(interview_score), 2),
            "final_score": final_score,
            "must_have_coverage": coverage,
            "confidence_score": round((match.confidence_score if match else 0.5) * 100, 2),
            "human_review_required": human_review_required,
            "strengths": strengths,
            "missing_skills": missing,
            "matched_skills": matched,
            "risk_notes": risk_notes,
            "risk_score": risk_score,
            "ai_recommendation": match.match_recommendation if match else "needs_human_review",
            "recruiter_decision": decision.decision if decision else None,
            "report_excerpt": report.recommended_next_step if report else "No interview report yet.",
        }

