"""AES-256-GCM secret handling for credentials at rest.

Mirrors the model app's guarantee: secrets are stored encrypted with a
per-account master key, never echoed back, never stored in plain text.
"""
from __future__ import annotations

import base64
import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def generate_master_key() -> str:
    """Return a fresh base64-encoded 32-byte key (for RCA_MASTER_KEY)."""
    return base64.b64encode(os.urandom(32)).decode()


def load_master_key(settings) -> str:  # noqa: ANN001
    """Master key from RCA_MASTER_KEY env, else a persisted per-install key."""
    if getattr(settings, "rca_master_key", ""):
        return settings.rca_master_key
    keyfile = Path(__file__).resolve().parents[2] / "instance" / ".master_key"
    keyfile.parent.mkdir(exist_ok=True)
    if keyfile.exists():
        return keyfile.read_text().strip()
    key = generate_master_key()
    keyfile.write_text(key)
    return key


def _load_key(master_key_b64: str) -> bytes:
    key = base64.b64decode(master_key_b64)
    if len(key) != 32:
        raise ValueError("RCA_MASTER_KEY must decode to 32 bytes (AES-256).")
    return key


def encrypt(plaintext: str, master_key_b64: str) -> str:
    """Encrypt a secret. Output = base64(nonce || ciphertext)."""
    key = _load_key(master_key_b64)
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ct).decode()


def decrypt(token_b64: str, master_key_b64: str) -> str:
    """Reverse of :func:`encrypt`."""
    key = _load_key(master_key_b64)
    raw = base64.b64decode(token_b64)
    nonce, ct = raw[:12], raw[12:]
    return AESGCM(key).decrypt(nonce, ct, None).decode()
