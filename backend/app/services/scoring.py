from __future__ import annotations

import html
import re
from statistics import mean

from sqlalchemy.orm import Session

from app.db.models import AnswerScore, Candidate, CandidateJobMatch, Interview, InterviewQuestion, Job
from app.services.ai import LLMGateway
from app.services.fairness_guard import FairnessGuard
from app.services.parsers import parse_job_description


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9\s]", " ", text.lower())


class HiringIntelligenceService:
    def __init__(self) -> None:
        self.llm = LLMGateway()
        self.fairness_guard = FairnessGuard()

    def analyze_job(self, job: Job) -> dict:
        fallback = parse_job_description(job.job_description)
        prompt = (
            "Extract required_skills, preferred_skills, responsibilities, seniority_level, "
            f"and interview_focus_areas from this job description:\n{job.job_description}"
        )
        return self.llm.generate_json(prompt, lambda: fallback)

    def match_candidate(self, candidate: Candidate, job: Job) -> dict:
        required = job.jd_analysis.get("required_skills", [])
        preferred = job.jd_analysis.get("preferred_skills", [])
        candidate_skills = {skill.name.lower() for skill in candidate.skills}
        matched_required = [skill for skill in required if skill.lower() in candidate_skills]
        missing_required = [skill for skill in required if skill.lower() not in candidate_skills]
        matched_preferred = [skill for skill in preferred if skill.lower() in candidate_skills]
        experience_fit = min(1.0, candidate.years_experience / 6 if candidate.years_experience else 0.35)
        required_score = (len(matched_required) / max(len(required), 1)) * 70
        preferred_score = (len(matched_preferred) / max(len(preferred), 1)) * 10 if preferred else 5
        total = round(required_score + preferred_score + (experience_fit * 20), 2)
        confidence = 0.92 if len(required) > 2 else 0.72
        red_flags = []
        if missing_required:
            red_flags.append("Missing one or more must-have skills.")
        if candidate.years_experience < 2 and "senior" in job.jd_analysis.get("seniority_level", ""):
            red_flags.append("Experience band may be below the current role target.")
        if total >= 80:
            recommendation = "strong_match"
        elif total >= 65:
            recommendation = "potential_match"
        elif total >= 45:
            recommendation = "needs_human_review"
        else:
            recommendation = "weak_match"
        explanation = (
            f"{candidate.name} matches {len(matched_required)}/{max(len(required), 1)} required skills for "
            f"{job.title}. Experience fit is assessed at {round(experience_fit * 100)}%. "
            "Protected attributes were excluded from AI processing. This is a decision-support score and still requires recruiter review."
        )
        return {
            "overall_score": total,
            "match_recommendation": recommendation,
            "matched_required_skills": matched_required,
            "missing_required_skills": missing_required,
            "matched_preferred_skills": matched_preferred,
            "red_flags": red_flags,
            "explanation": explanation,
            "confidence_score": round(confidence, 2),
            "human_review_required": True,
        }

    def generate_interview_plan(self, candidate: Candidate, job: Job, interview_type: str) -> list[dict]:
        focus_skills = job.jd_analysis.get("interview_focus_areas") or [skill.name for skill in job.skills[:4]]
        if not focus_skills:
            focus_skills = ["communication", "problem solving"]
        questions: list[dict] = [
            {
                "question_order": 1,
                "question_text": f"Walk me through your background and why you are a fit for the {job.title} role.",
                "skill_category": "communication",
                "difficulty": "easy",
                "expected_concepts": ["relevant experience", "motivation", "impact"],
                "scoring_rubric": {"clarity": 0.4, "relevance": 0.4, "structure": 0.2},
                "follow_up_strategy": "Probe for measurable outcomes if the answer stays high-level.",
            }
        ]
        for index, skill in enumerate(focus_skills[:4], start=2):
            questions.append(
                {
                    "question_order": index,
                    "question_text": f"Explain how you have used {skill} in a production environment.",
                    "skill_category": skill,
                    "difficulty": "medium" if index < 4 else "hard",
                    "expected_concepts": [skill, "trade-offs", "scale", "results"],
                    "scoring_rubric": {"correctness": 0.35, "depth": 0.35, "communication": 0.3},
                    "follow_up_strategy": f"If {skill} usage is shallow, ask for failure modes and operational trade-offs.",
                }
            )
        questions.append(
            {
                "question_order": len(questions) + 1,
                "question_text": "Describe a time you handled ambiguity or stakeholder pressure during hiring-related work.",
                "skill_category": "behavioral",
                "difficulty": "medium",
                "expected_concepts": ["ownership", "communication", "decision making"],
                "scoring_rubric": {"leadership": 0.4, "communication": 0.3, "reflection": 0.3},
                "follow_up_strategy": "Ask how they would improve the approach next time if reflection is weak.",
            }
        )
        questions.append(
            {
                "question_order": len(questions) + 1,
                "question_text": f"What questions do you have about the {job.title} opportunity?",
                "skill_category": "closing",
                "difficulty": "easy",
                "expected_concepts": ["curiosity", "role understanding"],
                "scoring_rubric": {"engagement": 0.5, "communication": 0.5},
                "follow_up_strategy": "No follow-up needed.",
            }
        )
        return questions

    def score_answer(self, question: InterviewQuestion, answer_text: str) -> dict:
        redaction_summary = self.fairness_guard.sanitize_text(answer_text)
        safe_answer_text = redaction_summary.sanitized_text.strip() or answer_text
        normalized = normalize(safe_answer_text)
        expected = [normalize(concept) for concept in question.expected_concepts]
        matched = [concept for concept in question.expected_concepts if normalize(concept) in normalized]
        missing = [concept for concept in question.expected_concepts if concept not in matched]
        coverage = len(matched) / max(len(question.expected_concepts), 1)
        word_count = max(len(safe_answer_text.split()), 1)
        depth = min(word_count / 80, 1.0)
        clarity = 0.85 if "." in safe_answer_text or "," in safe_answer_text else 0.65
        communication = min((word_count / 50), 1.0) * 0.7 + 0.3
        total = round(((coverage * 0.55) + (depth * 0.25) + (clarity * 0.1) + (communication * 0.1)) * 100, 2)
        strengths = []
        weaknesses = []
        if matched:
            strengths.append(f"Covered {len(matched)} expected concepts including {matched[0]}.")
        if depth > 0.7:
            strengths.append("Provided enough detail to assess trade-offs and experience.")
        if missing:
            weaknesses.append(f"Missing concepts: {', '.join(missing[:3])}.")
        if word_count < 30:
            weaknesses.append("Answer is concise and may need deeper examples.")
        follow_up = None
        if missing:
            follow_up = f"Can you expand on {missing[0]} and explain how it affected the outcome?"
        explanation = (
            f"Score is based on concept coverage ({len(matched)}/{max(len(question.expected_concepts), 1)}), "
            f"depth of explanation, and communication quality. Protected attributes are excluded."
        )
        if redaction_summary.redaction_count:
            explanation += (
                f" Bias guard removed {redaction_summary.redaction_count} demographic reference"
                f"{'s' if redaction_summary.redaction_count != 1 else ''} before scoring."
            )
        return {
            "total_score": total,
            "skill_score": round(coverage * 100, 2),
            "clarity_score": round(clarity * 100, 2),
            "communication_score": round(communication * 100, 2),
            "confidence_score": round(min(0.95, 0.55 + coverage * 0.4), 2),
            "matched_concepts": matched,
            "missing_concepts": missing,
            "strengths": strengths or ["Relevant answer with acceptable structure."],
            "weaknesses": weaknesses or ["No major gaps detected."],
            "suggested_follow_up": follow_up,
            "human_review_required": total < 65 or bool(missing),
            "explanation": explanation,
        }

    def build_report(
        self,
        interview: Interview,
        candidate: Candidate,
        job: Job,
        match_result: CandidateJobMatch | None,
        scores: list[AnswerScore],
    ) -> dict:
        avg_score = round(mean([score.total_score for score in scores]), 2) if scores else 0.0
        strengths = [item for score in scores for item in score.strengths][:5]
        weaknesses = [item for score in scores for item in score.weaknesses if item != "No major gaps detected."][:5]
        next_step = "Move to next round" if avg_score >= 70 else "Hold for recruiter review"
        match_score = match_result.overall_score if match_result else 0
        report_md = f"""# HireOS AI Interview Report

## Candidate Overview
- Candidate: {candidate.name}
- Role: {job.title}
- Interview Type: {interview.interview_type}
- Resume Match Score: {match_score}
- Interview Score: {avg_score}

## AI Recommendation
- Recommendation: {match_result.match_recommendation if match_result else 'needs_human_review'}
- Human Review Required: Yes
- Confidence: {match_result.confidence_score if match_result else 0.6}

## Strengths
{chr(10).join(f"- {item}" for item in strengths[:5] or ['Relevant baseline alignment detected.'])}

## Gaps
{chr(10).join(f"- {item}" for item in weaknesses[:5] or ['No critical gaps flagged by heuristics.'])}

## Compliance Note
AI-generated scores are decision-support signals and should be reviewed by a human recruiter.
Protected attributes are redacted from AI resume and answer processing before scoring or matching.
"""
        report_html = "<html><body><pre>" + html.escape(report_md) + "</pre></body></html>"
        return {
            "report_markdown": report_md,
            "report_html": report_html,
            "recommended_next_step": next_step,
            "human_review_required": True,
            "audit_trail": [
                {"step": "resume_match", "score": match_score},
                {"step": "interview_score", "score": avg_score},
                {"step": "human_review_required", "value": True},
            ],
        }
