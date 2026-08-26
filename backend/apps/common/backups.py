from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


def encrypt_backup(payload: bytes, key: str) -> bytes:
    return Fernet(key.encode()).encrypt(payload)


def decrypt_backup(payload: bytes, key: str) -> bytes:
    try:
        return Fernet(key.encode()).decrypt(payload)
    except InvalidToken as exc:
        raise ValueError("Corrupted backup or incorrect key") from exc
