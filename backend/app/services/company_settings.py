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
    return data
