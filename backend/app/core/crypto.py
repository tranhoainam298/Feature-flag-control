"""Symmetric encryption for sensitive configuration values using AES-256-GCM.

Skill: security-hardening.
Key derivation: SHA-256 of settings.CONFIG_MASTER_KEY to ensure exact 32 bytes.
Nonce: 12 bytes randomly generated per encryption.
Output format: base64(nonce + ciphertext + tag)
"""

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

MASKED_SECRET = "••••••"


def _get_master_key_bytes() -> bytes:
    settings.validate_production_security()
    raw = settings.CONFIG_MASTER_KEY.encode("utf-8")
    if len(raw) == 32:
        return raw
    return hashlib.sha256(raw).digest()


def encrypt_secret(plaintext: str) -> str:
    """Encrypt plaintext string using AES-256-GCM with a fresh 12-byte random nonce."""
    nonce = os.urandom(12)
    aesgcm = AESGCM(_get_master_key_bytes())
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("utf-8")


def decrypt_secret(encrypted_b64: str) -> str:
    """Decrypt base64(nonce + ciphertext + tag) using AES-256-GCM."""
    raw = base64.b64decode(encrypted_b64.encode("utf-8"))
    nonce = raw[:12]
    ciphertext = raw[12:]
    aesgcm = AESGCM(_get_master_key_bytes())
    plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext_bytes.decode("utf-8")
