"""AES-256-GCM envelope encryption, WebCrypto-compatible by construction.

Envelope format (one JSON object per ``*.enc.json`` file)::

    { "v": 1, "alg": "AES-256-GCM",
      "kdf": { "name": "PBKDF2", "hash": "SHA-256",
               "iterations": 600000, "salt": "<b64 16B>" },
      "aad": "newsdash:v1:<section_id>",
      "nonce": "<b64 12B>",
      "ct": "<b64 ciphertext||16B GCM tag>" }

Contract pinned by tests/test_crypto_webcrypto.mjs (Node WebCrypto decrypts a
vector produced here). Do not change parameters without bumping ``v`` and
updating docs/DATA_CONTRACT.md, assets/js/crypto.js, and the tests together.

The passphrase is NFC-normalized on both sides so CJK and composed-accent
passphrases derive the same key across platforms.
"""

from __future__ import annotations

import base64
import json
import os
import unicodedata

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ENVELOPE_VERSION = 1
ALG = "AES-256-GCM"
KDF_NAME = "PBKDF2"
KDF_HASH = "SHA-256"
PBKDF2_ITERATIONS = 600_000
SALT_LEN = 16
NONCE_LEN = 12
KEY_LEN = 32

AAD_PREFIX = "newsdash:v1:"
CHECK_SECTION = "check"
CHECK_PLAINTEXT = b"newsdash:ok"


class DecryptError(Exception):
    """Wrong passphrase, tampered ciphertext, or mismatched section AAD."""


def _b64e(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _b64d(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


def _aad(section_id: str) -> bytes:
    return (AAD_PREFIX + section_id).encode("utf-8")


def new_salt() -> bytes:
    return os.urandom(SALT_LEN)


def derive_key(passphrase: str, salt: bytes, iterations: int = PBKDF2_ITERATIONS) -> bytes:
    normalized = unicodedata.normalize("NFC", passphrase).encode("utf-8")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=KEY_LEN, salt=salt, iterations=iterations
    )
    return kdf.derive(normalized)


def kdf_block(salt: bytes, iterations: int = PBKDF2_ITERATIONS) -> dict:
    return {
        "name": KDF_NAME,
        "hash": KDF_HASH,
        "iterations": iterations,
        "salt": _b64e(salt),
    }


def encrypt_bytes(
    plaintext: bytes,
    section_id: str,
    key: bytes,
    salt: bytes,
    iterations: int = PBKDF2_ITERATIONS,
) -> dict:
    nonce = os.urandom(NONCE_LEN)
    ct = AESGCM(key).encrypt(nonce, plaintext, _aad(section_id))
    return {
        "v": ENVELOPE_VERSION,
        "alg": ALG,
        "kdf": kdf_block(salt, iterations),
        "aad": AAD_PREFIX + section_id,
        "nonce": _b64e(nonce),
        "ct": _b64e(ct),
    }


def encrypt_json(
    payload,
    section_id: str,
    key: bytes,
    salt: bytes,
    iterations: int = PBKDF2_ITERATIONS,
) -> dict:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return encrypt_bytes(raw, section_id, key, salt, iterations)


def make_check_block(key: bytes, salt: bytes, iterations: int = PBKDF2_ITERATIONS) -> dict:
    """The manifest's fast passphrase probe: tiny, constant plaintext."""
    env = encrypt_bytes(CHECK_PLAINTEXT, CHECK_SECTION, key, salt, iterations)
    return {"aad": env["aad"], "nonce": env["nonce"], "ct": env["ct"]}


def decrypt_envelope(env: dict, passphrase: str, section_id: str | None = None) -> bytes:
    aad = env.get("aad", "")
    if not aad.startswith(AAD_PREFIX):
        raise DecryptError(f"unexpected aad {aad!r}")
    if section_id is not None and aad != AAD_PREFIX + section_id:
        raise DecryptError(f"section mismatch: envelope is {aad!r}")
    kdf = env["kdf"]
    if kdf.get("name") != KDF_NAME or kdf.get("hash") != KDF_HASH:
        raise DecryptError("unsupported KDF parameters")
    key = derive_key(passphrase, _b64d(kdf["salt"]), int(kdf["iterations"]))
    try:
        return AESGCM(key).decrypt(
            _b64d(env["nonce"]), _b64d(env["ct"]), aad.encode("utf-8")
        )
    except Exception as exc:  # cryptography raises InvalidTag
        raise DecryptError("decryption failed (wrong passphrase or tampered data)") from exc


def decrypt_json(env: dict, passphrase: str, section_id: str | None = None):
    return json.loads(decrypt_envelope(env, passphrase, section_id).decode("utf-8"))
