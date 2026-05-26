from __future__ import annotations

from copy import deepcopy

from app.services.secret_crypto import SecretCryptoService


secret_crypto = SecretCryptoService()


def protect_company_settings(settings_json: dict | None) -> dict:
    data = deepcopy(settings_json or {})
    google = data.get("integrations", {}).get("google")
    if isinstance(google, dict):
        google["access_token"] = secret_crypto.encrypt(google.get("access_token"))
        google["refresh_token"] = secret_crypto.encrypt(google.get("refresh_token"))
    zoom = data.get("integrations", {}).get("zoom")
    if isinstance(zoom, dict):
        zoom["access_token"] = secret_crypto.encrypt(zoom.get("access_token"))
        zoom["refresh_token"] = secret_crypto.encrypt(zoom.get("refresh_token"))
    ats_webhook = data.get("integrations", {}).get("ats_webhook")
    if isinstance(ats_webhook, dict):
        ats_webhook["auth_token"] = secret_crypto.encrypt(ats_webhook.get("auth_token"))
        ats_webhook["signing_secret"] = secret_crypto.encrypt(ats_webhook.get("signing_secret"))
    return data


def sanitize_company_settings(settings_json: dict | None) -> dict:
    data = deepcopy(settings_json or {})
    google = data.get("integrations", {}).get("google")
    if isinstance(google, dict):
        google.pop("access_token", None)
        google.pop("refresh_token", None)
        google.pop("token_type", None)
        google.pop("id_token", None)
        google.pop("scope", None)
    zoom = data.get("integrations", {}).get("zoom")
    if isinstance(zoom, dict):
        zoom.pop("access_token", None)
        zoom.pop("refresh_token", None)
        zoom.pop("token_type", None)
        zoom.pop("scope", None)
    ats_webhook = data.get("integrations", {}).get("ats_webhook")
    if isinstance(ats_webhook, dict):
        ats_webhook.pop("auth_token", None)
        ats_webhook.pop("signing_secret", None)
    return data
