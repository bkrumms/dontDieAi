"""Symmetric encryption for at-rest user JWTs.

Key comes from env var DD_BOT_SECRET_KEY (Fernet-format: 32-byte url-safe
base64). Generate one with `python -m dd_agent.secrets`.
"""
from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken


class SecretsError(Exception):
    pass


def _key() -> bytes:
    raw = os.getenv("DD_BOT_SECRET_KEY", "").strip()
    if not raw:
        raise SecretsError(
            "DD_BOT_SECRET_KEY is not set. Generate one with "
            "`python -m dd_agent.secrets` and put it in .env."
        )
    return raw.encode("ascii")


def encrypt(plaintext: str) -> str:
    return Fernet(_key()).encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt(ciphertext: str) -> str:
    try:
        return Fernet(_key()).decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except InvalidToken as e:
        raise SecretsError("ciphertext could not be decrypted (wrong key?)") from e


def generate_key() -> str:
    return Fernet.generate_key().decode("ascii")


if __name__ == "__main__":
    print(generate_key())
