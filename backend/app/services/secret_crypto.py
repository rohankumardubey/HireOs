from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class SecretCryptoService:
    prefix = "enc:v1:"

    def __init__(self) -> None:
        key_material = settings.field_encryption_key or settings.jwt_secret
        digest = hashlib.sha256(key_material.encode("utf-8")).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(digest))

    def encrypt(self, value: str | None) -> str | None:
        if not value:
            return value
        if self.is_encrypted(value):
            return value
        token = self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")
        return f"{self.prefix}{token}"

    def decrypt(self, value: str | None) -> str | None:
        if not value:
            return value
        if not self.is_encrypted(value):
            return value
        token = value[len(self.prefix) :]
        try:
            return self._fernet.decrypt(token.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("Stored provider secret could not be decrypted. Verify FIELD_ENCRYPTION_KEY/JWT_SECRET consistency.") from exc

    def is_encrypted(self, value: str | None) -> bool:
        return bool(value and value.startswith(self.prefix))
