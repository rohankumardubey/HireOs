from __future__ import annotations

from datetime import datetime
from urllib.parse import quote, urlencode


class InterviewInviteLinkBuilder:
    def build(
        self,
        *,
        mode: str,
        meeting_provider: str,
        schedule_type: str,
        scheduled_at: datetime | None,
        meeting_join_url: str | None,
        candidate_name: str,
        candidate_email: str,
        job_title: str,
        candidate_portal_url: str,
    ) -> dict:
        normalized_provider = meeting_provider.lower()
        normalized_mode = mode.lower()
        normalized_schedule = schedule_type.lower()
        schedule_label = "Scheduled" if normalized_schedule == "scheduled" else "Ad hoc"
        scheduled_label = (
            scheduled_at.strftime("%Y-%m-%d %H:%M") if scheduled_at else "Starts as soon as the recruiter opens it"
        )

        if normalized_mode == "video":
            if not meeting_join_url:
                raise ValueError("Video interviews require a real meeting join URL")

            provider_label = "Zoom" if normalized_provider == "zoom" else "Google Meet"
            subject = f"HireOS live video interview for {job_title}"
            email_body = (
                f"Hi {candidate_name},\n\n"
                f"You have been invited to a live {provider_label} interview for the {job_title} role.\n\n"
                f"Interview format: {schedule_label}\n"
                f"Scheduled time: {scheduled_label}\n"
                f"Join link: {meeting_join_url}\n\n"
                "Please use the join link above when it is time to meet the recruiter.\n\n"
                "Best,\nHireOS AI Recruiting"
            )
            mailto_query = urlencode(
                {
                    "subject": subject,
                    "body": email_body,
                },
                quote_via=quote,
            )
            return {
                "meeting_provider": normalized_provider,
                "meeting_provider_label": provider_label,
                "candidate_email": candidate_email,
                "candidate_portal_url": candidate_portal_url,
                "candidate_join_url": meeting_join_url,
                "meeting_setup_url": meeting_join_url,
                "email_compose_url": f"mailto:{quote(candidate_email)}?{mailto_query}",
                "share_message": email_body,
                "meeting_note": (
                    f"This is a live {provider_label} interview link. Share the join URL directly with the candidate."
                ),
                "schedule_type": normalized_schedule,
                "schedule_label": schedule_label,
                "scheduled_at": scheduled_at,
            }

        subject = f"HireOS AI interview invitation for {job_title}"
        email_body = (
            f"Hi {candidate_name},\n\n"
            f"You have been invited to the HireOS AI interview flow for the {job_title} role.\n\n"
            f"Candidate interview link: {candidate_portal_url}\n"
        )

        if normalized_provider == "zoom":
            meeting_setup_url = "https://zoom.us/meeting/schedule"
            provider_label = "Zoom"
            meeting_note = (
                "This opens Zoom's scheduling flow. After scheduling, share the generated Zoom join link with the candidate."
            )
            email_body += (
                "Zoom scheduling link for the recruiter: https://zoom.us/meeting/schedule\n"
                "Once the Zoom meeting is created, the recruiter will share the final Zoom join link with you.\n\n"
            )
        else:
            calendar_params = urlencode(
                {
                    "action": "TEMPLATE",
                    "text": f"HireOS AI interview - {job_title}",
                    "details": (
                        f"Candidate portal link: {candidate_portal_url}\n\n"
                        "Recruiter note: AI-generated interview scores are decision-support signals and should be reviewed by a human recruiter."
                    ),
                    "add": candidate_email,
                },
                quote_via=quote,
            )
            meeting_setup_url = f"https://calendar.google.com/calendar/render?{calendar_params}"
            provider_label = "Google Meet"
            meeting_note = (
                "This opens a Google Calendar event draft with the candidate prefilled as a guest. Saving the event can add Google Meet for supported Google Calendar accounts."
            )
            email_body += (
                f"Google Calendar event draft: {meeting_setup_url}\n"
                "The recruiter can save that event and send the calendar invite to you.\n\n"
            )

        email_body += (
            "Please reply if you need a different time or accommodation.\n\n"
            "Best,\nHireOS AI Recruiting"
        )

        mailto_query = urlencode(
            {
                "subject": subject,
                "body": email_body,
            },
            quote_via=quote,
        )

        return {
            "meeting_provider": normalized_provider,
            "meeting_provider_label": provider_label,
            "candidate_email": candidate_email,
            "candidate_portal_url": candidate_portal_url,
            "candidate_join_url": candidate_portal_url,
            "meeting_setup_url": meeting_setup_url,
            "email_compose_url": f"mailto:{quote(candidate_email)}?{mailto_query}",
            "share_message": email_body,
            "meeting_note": meeting_note,
            "schedule_type": "async",
            "schedule_label": "Async AI interview",
            "scheduled_at": None,
        }
