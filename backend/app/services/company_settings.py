from __future__ import annotations

from copy import deepcopy


def sanitize_company_settings(settings_json: dict | None) -> dict:
    data = deepcopy(settings_json or {})
    google = data.get("integrations", {}).get("google")
    if isinstance(google, dict):
        google.pop("access_token", None)
        google.pop("refresh_token", None)
        google.pop("token_type", None)
        google.pop("id_token", None)
        google.pop("scope", None)
    ats_webhook = data.get("integrations", {}).get("ats_webhook")
    if isinstance(ats_webhook, dict):
        ats_webhook.pop("auth_token", None)
        ats_webhook.pop("signing_secret", None)
    return data
