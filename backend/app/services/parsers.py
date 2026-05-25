from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path

from docx import Document
from pypdf import PdfReader

SKILL_LEXICON = [
    "python",
    "java",
    "sql",
    "postgresql",
    "fastapi",
    "django",
    "flask",
    "kafka",
    "spark",
    "airflow",
    "docker",
    "kubernetes",
    "redis",
    "aws",
    "gcp",
    "azure",
    "terraform",
    "snowflake",
    "dbt",
    "react",
    "next.js",
    "typescript",
    "product strategy",
    "roadmapping",
    "stakeholder management",
    "customer support",
    "leadership",
    "machine learning",
    "llm",
    "pytorch",
    "tensorflow",
    "etl",
    "data modeling",
]


def extract_text_from_upload(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if suffix == ".docx":
        document = Document(BytesIO(content))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)
    return content.decode("utf-8", errors="ignore")


def parse_resume_text(text: str) -> dict:
    lowered = text.lower()
    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
    phone_match = re.search(r"(\+?\d[\d\-\s]{8,}\d)", text)
    skills = sorted({skill for skill in SKILL_LEXICON if skill in lowered})
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    name = lines[0] if lines else "Unknown Candidate"
    role = next((line for line in lines[1:8] if len(line.split()) <= 7), "Professional")
    summary = " ".join(lines[:4])[:500]
    education = next((line for line in lines if "university" in line.lower() or "bachelor" in line.lower()), "")
    experience_match = re.findall(r"(\d+)\+?\s+years", lowered)
    years = float(max(experience_match, default="0"))
    return {
        "name": name,
        "email": email_match.group(0) if email_match else "",
        "phone": phone_match.group(0) if phone_match else "",
        "skills": skills,
        "work_experience": lines[4:12],
        "education": education,
        "projects": [line for line in lines if "project" in line.lower()][:3],
        "total_years_experience": years,
        "role_title": role,
        "summary": summary,
    }


def parse_job_description(text: str) -> dict:
    lowered = text.lower()
    required = sorted({skill for skill in SKILL_LEXICON if skill in lowered})
    preferred = [skill for skill in required if skill in {"aws", "docker", "kubernetes", "leadership", "llm"}]
    responsibilities = [line.strip("- ").strip() for line in text.splitlines() if line.strip().startswith("-")][:6]
    seniority = "senior" if "senior" in lowered or "lead" in lowered else "mid"
    focus_areas = required[:4] or ["communication", "problem solving"]
    return {
        "required_skills": required,
        "preferred_skills": preferred,
        "responsibilities": responsibilities,
        "seniority_level": seniority,
        "interview_focus_areas": focus_areas,
    }

