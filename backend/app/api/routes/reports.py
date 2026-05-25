from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import InterviewReport
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.schemas import ReportRead

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("", response_model=list[ReportRead])
def list_reports(current_user=Depends(get_current_user), db: Session = Depends(get_db)) -> list[ReportRead]:
    reports = db.execute(select(InterviewReport).order_by(InterviewReport.created_at.desc())).scalars().all()
    return [ReportRead.model_validate(report) for report in reports]


@router.get("/{report_id}", response_model=ReportRead)
def get_report(report_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)) -> ReportRead:
    report = db.get(InterviewReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return ReportRead.model_validate(report)


@router.get("/{report_id}/download")
def download_report(
    report_id: str,
    format: str = "html",
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = db.get(InterviewReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if format == "markdown":
        return PlainTextResponse(report.report_markdown, media_type="text/markdown")
    return HTMLResponse(report.report_html)
