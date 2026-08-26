from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class CredentialCipher:
    """Local secret envelope; the master key is never stored in PostgreSQL."""

    def __init__(self) -> None:
        key = settings.EXTERNAL_CREDENTIALS_KEY
        if not key:
            raise ImproperlyConfigured("EXTERNAL_CREDENTIALS_KEY is required to store secrets")
        self._fernet = Fernet(key.encode())

    def encrypt(self, plaintext: str) -> bytes:
        return self._fernet.encrypt(plaintext.encode())

    def decrypt(self, ciphertext: bytes) -> str:
        try:
            return self._fernet.decrypt(ciphertext).decode()
        except InvalidToken as exc:
            raise ValueError("The credential could not be decrypted") from exc
