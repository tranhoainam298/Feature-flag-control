"""Unit tests for AES-256-GCM secret encryption and decryption."""

from app.core.crypto import MASKED_SECRET, decrypt_secret, encrypt_secret


def test_encrypt_decrypt_roundtrip():
    secret = "super-secret-password-123!@#"
    encrypted = encrypt_secret(secret)

    # Ciphertext must not equal plaintext
    assert encrypted != secret
    # Multiple encryptions of same plaintext produce different ciphertexts (different nonces)
    encrypted2 = encrypt_secret(secret)
    assert encrypted != encrypted2

    # Decryption recovers the exact plaintext
    decrypted = decrypt_secret(encrypted)
    assert decrypted == secret

    decrypted2 = decrypt_secret(encrypted2)
    assert decrypted2 == secret


def test_empty_string_roundtrip():
    secret = ""
    encrypted = encrypt_secret(secret)
    assert decrypt_secret(encrypted) == ""


def test_unicode_roundtrip():
    secret = "mật_khẩu_bí_mật_🔑_123"
    encrypted = encrypt_secret(secret)
    assert decrypt_secret(encrypted) == secret


def test_masked_secret_constant():
    assert MASKED_SECRET == "••••••"
    assert len(MASKED_SECRET) == 6
