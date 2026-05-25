from __future__ import annotations

from pathlib import Path
from random import choice, randint

from sqlalchemy import select

from app.core.security import get_password_hash
from app.db.models import Candidate, CandidateJobMatch, CandidateSkill, Company, CompanyMembership, Interview, InterviewQuestion, InterviewReport, Job, JobSkill, User
from app.db.session import SessionLocal, init_db
from app.services.scoring import HiringIntelligenceService

DEMO_PASSWORD = "Demo@123"

JOBS = [
    (
        "Data Engineer",
        "Build Kafka, Spark, and lakehouse pipelines for hiring analytics. Requires Python, SQL, Airflow, Kafka, and data modeling.",
        ["python", "sql", "kafka", "airflow", "data modeling"],
        ["spark", "aws", "dbt"],
    ),
    (
        "Backend Engineer",
        "Own FastAPI services, PostgreSQL design, caching, and scalable APIs. Requires Python, FastAPI, PostgreSQL, Docker, and Redis.",
        ["python", "fastapi", "postgresql", "docker", "redis"],
        ["kubernetes", "aws"],
    ),
    (
        "ML Engineer",
        "Deploy applied machine learning systems and LLM features. Requires Python, machine learning, PyTorch, SQL, and cloud ops.",
        ["python", "machine learning", "pytorch", "sql", "aws"],
        ["llm", "kubernetes"],
    ),
    (
        "Product Manager",
        "Lead roadmap, stakeholder alignment, and recruiting workflow improvements. Requires product strategy, roadmapping, and communication.",
        ["product strategy", "roadmapping", "stakeholder management"],
        ["leadership", "analytics"],
    ),
    (
        "Customer Support Lead",
        "Scale a global support operation with coaching, quality, and process design. Requires customer support, leadership, and communication.",
        ["customer support", "leadership", "communication"],
        ["analytics", "process improvement"],
    ),
]

CANDIDATES = [
    ("Aarav Patel", ["python", "sql", "kafka", "airflow", "docker"], 5),
    ("Mia Chen", ["python", "fastapi", "postgresql", "redis"], 4),
    ("Nina Singh", ["machine learning", "python", "pytorch", "sql"], 3),
    ("Ravi Nair", ["product strategy", "roadmapping", "stakeholder management"], 6),
    ("Elena Torres", ["customer support", "leadership", "communication"], 7),
]


def main() -> None:
    init_db()
    db = SessionLocal()
    if db.execute(select(Company).where(Company.slug == "hireos-demo")).scalar_one_or_none():
        print("Seed data already exists.")
        return
    company = Company(name="HireOS Demo", slug="hireos-demo", industry="HR Tech", size_band="51-200")
    admin = User(full_name="Priya Admin", email="admin@hireos.ai", hashed_password=get_password_hash(DEMO_PASSWORD))
    recruiter1 = User(full_name="Rohan Recruiter", email="recruiter1@hireos.ai", hashed_password=get_password_hash(DEMO_PASSWORD))
    recruiter2 = User(full_name="Sana Recruiter", email="recruiter2@hireos.ai", hashed_password=get_password_hash(DEMO_PASSWORD))
    manager = User(full_name="Mila Manager", email="manager@hireos.ai", hashed_password=get_password_hash(DEMO_PASSWORD))
    db.add_all([company, admin, recruiter1, recruiter2, manager])
    db.flush()
    db.add_all(
        [
            CompanyMembership(company_id=company.id, user_id=admin.id, role="admin"),
            CompanyMembership(company_id=company.id, user_id=recruiter1.id, role="recruiter"),
            CompanyMembership(company_id=company.id, user_id=recruiter2.id, role="recruiter"),
            CompanyMembership(company_id=company.id, user_id=manager.id, role="hiring_manager"),
        ]
    )
    ai = HiringIntelligenceService()
    jobs: list[Job] = []
    for title, description, required, preferred in JOBS:
        job = Job(
            company_id=company.id,
            created_by_id=recruiter1.id,
            title=title,
            department="Talent",
            location="Hybrid",
            work_mode="hybrid",
            experience_range="3-8 years",
            employment_type="full-time",
            salary_range="$90k-$160k",
            status="open",
            job_description=description,
        )
        db.add(job)
        db.flush()
        for skill in required:
            db.add(JobSkill(job_id=job.id, name=skill, category="required", weight=1.0))
        for skill in preferred:
            db.add(JobSkill(job_id=job.id, name=skill, category="preferred", weight=0.6))
        job.jd_analysis = ai.analyze_job(job)
        jobs.append(job)
    db.flush()
    expanded_candidates: list[Candidate] = []
    for index in range(20):
        base_name, base_skills, years = CANDIDATES[index % len(CANDIDATES)]
        candidate = Candidate(
            company_id=company.id,
            owner_id=recruiter1.id,
            name=f"{base_name} {index + 1}",
            email=f"candidate{index + 1}@hireos.ai",
            location=choice(["Bengaluru", "Remote", "London", "New York"]),
            years_experience=float(years + randint(0, 2)),
            current_role=choice(["Engineer", "Analyst", "Lead", "Manager"]),
            education="B.Tech in Computer Science",
            profile_summary=f"{base_name} has experience in {', '.join(base_skills[:3])} and hiring-oriented systems.",
            parsed_profile={"skills": base_skills},
            status="resume_screened",
        )
        db.add(candidate)
        db.flush()
        for skill in base_skills:
            db.add(CandidateSkill(candidate_id=candidate.id, name=skill))
        expanded_candidates.append(candidate)
    db.flush()
    for index, candidate in enumerate(expanded_candidates):
        job = jobs[index % len(jobs)]
        match = CandidateJobMatch(candidate_id=candidate.id, job_id=job.id, explanation="")
        for field, value in ai.match_candidate(candidate, job).items():
            setattr(match, field, value)
        db.add(match)
        if index < 8:
            interview = Interview(
                company_id=company.id,
                candidate_id=candidate.id,
                job_id=job.id,
                invited_by_id=recruiter2.id,
                interview_type="Technical screening",
                mode="text",
                status="completed",
                consent_given=True,
                current_question_index=5,
                summary_json={"average_score": 74 + (index % 12), "questions_answered": 5},
            )
            db.add(interview)
            db.flush()
            for question in ai.generate_interview_plan(candidate, job, "Technical screening")[:5]:
                db.add(InterviewQuestion(interview_id=interview.id, **question))
            db.add(
                InterviewReport(
                    interview_id=interview.id,
                    report_markdown=f"# Demo report for {candidate.name}\n\nAI recommends recruiter review.",
                    report_html=f"<html><body><h1>Demo report for {candidate.name}</h1><p>AI recommends recruiter review.</p></body></html>",
                    recommended_next_step="Move to next round" if index % 2 == 0 else "Hold for review",
                    human_review_required=True,
                    audit_trail=[{"seeded": True}],
                )
            )
    db.commit()
    print("Seeded demo data.")
    print("Recruiter login: recruiter1@hireos.ai / Demo@123")
    print("Admin login: admin@hireos.ai / Demo@123")


if __name__ == "__main__":
    main()

