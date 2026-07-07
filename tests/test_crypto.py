import base64
import json
from pathlib import Path

import pytest

from newsdash import crypto

FAST_ITER = 1000  # keep unit tests quick; the vector test uses the real 600k


def _roundtrip(payload, section, passphrase, iterations=FAST_ITER):
    salt = crypto.new_salt()
    key = crypto.derive_key(passphrase, salt, iterations)
    env = crypto.encrypt_json(payload, section, key, salt, iterations)
    return env


def test_roundtrip():
    payload = {"a": 1, "zh": "你好", "nested": {"x": [1, 2, 3]}}
    env = _roundtrip(payload, "schedule", "open sesame")
    assert crypto.decrypt_json(env, "open sesame", "schedule") == payload


def test_wrong_passphrase_fails():
    env = _roundtrip({"a": 1}, "schedule", "right")
    with pytest.raises(crypto.DecryptError):
        crypto.decrypt_json(env, "wrong", "schedule")


def test_section_mismatch_fails():
    env = _roundtrip({"a": 1}, "courses", "pass")
    with pytest.raises(crypto.DecryptError):
        crypto.decrypt_json(env, "pass", "schedule")


def test_tampered_ciphertext_fails():
    env = _roundtrip({"a": 1}, "schedule", "pass")
    raw = bytearray(base64.b64decode(env["ct"]))
    raw[0] ^= 0xFF
    env["ct"] = base64.b64encode(bytes(raw)).decode()
    with pytest.raises(crypto.DecryptError):
        crypto.decrypt_json(env, "pass", "schedule")


def test_nfc_normalization():
    composed = "café"          # é as one codepoint
    decomposed = "café"       # e + combining accent
    env = _roundtrip({"ok": True}, "check", composed)
    assert crypto.decrypt_json(env, decomposed, "check") == {"ok": True}


def test_envelope_shape():
    env = _roundtrip({"a": 1}, "news", "pass")
    assert env["v"] == 1
    assert env["alg"] == "AES-256-GCM"
    assert env["kdf"]["name"] == "PBKDF2" and env["kdf"]["hash"] == "SHA-256"
    assert len(base64.b64decode(env["kdf"]["salt"])) == crypto.SALT_LEN
    assert len(base64.b64decode(env["nonce"])) == crypto.NONCE_LEN
    assert env["aad"] == "newsdash:v1:news"


def test_check_block():
    salt = crypto.new_salt()
    key = crypto.derive_key("pass", salt, FAST_ITER)
    check = crypto.make_check_block(key, salt, FAST_ITER)
    assert check["aad"] == "newsdash:v1:check"
    env = {"v": 1, "alg": crypto.ALG,
           "kdf": crypto.kdf_block(salt, FAST_ITER), **check}
    assert crypto.decrypt_envelope(env, "pass", "check") == crypto.CHECK_PLAINTEXT


def test_committed_vector_decrypts(repo_root):
    vector_path = repo_root / "tests" / "fixtures" / "crypto-vector.json"
    vector = json.loads(Path(vector_path).read_text(encoding="utf-8"))
    payload = crypto.decrypt_json(vector["envelope"], vector["passphrase"],
                                  vector["section"])
    assert payload == vector["payload"]
    assert vector["envelope"]["kdf"]["iterations"] == crypto.PBKDF2_ITERATIONS
