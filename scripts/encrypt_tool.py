#!/usr/bin/env python3
"""Encrypt/decrypt Newsdash envelopes for local debugging and fixtures.

The passphrase is read from an environment variable (default
``NEWSDASH_PASSPHRASE``), never from argv, so it stays out of shell history
and process listings. Decryption prints to stdout only — never write
decrypted private data into the repo or CI logs.

Subcommands:
    encrypt      --in payload.json --section schedule [--out out.enc.json]
    decrypt      --in schedule.enc.json [--section schedule]
    make-vector  [--out tests/fixtures/crypto-vector.json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from newsdash import crypto

VECTOR_PASSPHRASE = "correct horse battery staple"  # public test constant
VECTOR_SECTION = "vector"
VECTOR_PAYLOAD = {"hello": "world", "zh": "你好，世界", "n": 42}


def _passphrase(env_name: str) -> str:
    value = os.environ.get(env_name, "").strip()
    if not value:
        print(f"::error::environment variable {env_name} is empty", file=sys.stderr)
        sys.exit(1)
    return value


def cmd_encrypt(args) -> None:
    passphrase = _passphrase(args.passphrase_env)
    with open(args.infile, encoding="utf-8") as fh:
        payload = json.load(fh)
    salt = crypto.new_salt()
    key = crypto.derive_key(passphrase, salt)
    envelope = crypto.encrypt_json(payload, args.section, key, salt)
    text = json.dumps(envelope, ensure_ascii=False, indent=1) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        sys.stdout.write(text)


def cmd_decrypt(args) -> None:
    passphrase = _passphrase(args.passphrase_env)
    with open(args.infile, encoding="utf-8") as fh:
        envelope = json.load(fh)
    try:
        payload = crypto.decrypt_json(envelope, passphrase, args.section)
    except crypto.DecryptError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        sys.exit(1)
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=1)
    sys.stdout.write("\n")


def cmd_make_vector(args) -> None:
    salt = crypto.new_salt()
    key = crypto.derive_key(VECTOR_PASSPHRASE, salt)
    envelope = crypto.encrypt_json(VECTOR_PAYLOAD, VECTOR_SECTION, key, salt)
    vector = {
        "_comment": "Cross-language crypto test vector. The passphrase is a "
                    "public constant used only by tests.",
        "passphrase": VECTOR_PASSPHRASE,
        "section": VECTOR_SECTION,
        "payload": VECTOR_PAYLOAD,
        "envelope": envelope,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(vector, ensure_ascii=False, indent=1) + "\n",
                   encoding="utf-8")
    print(f"wrote {out}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    enc = sub.add_parser("encrypt")
    enc.add_argument("--in", dest="infile", required=True)
    enc.add_argument("--section", required=True)
    enc.add_argument("--out")
    enc.add_argument("--passphrase-env", default="NEWSDASH_PASSPHRASE")
    enc.set_defaults(func=cmd_encrypt)

    dec = sub.add_parser("decrypt")
    dec.add_argument("--in", dest="infile", required=True)
    dec.add_argument("--section", default=None)
    dec.add_argument("--passphrase-env", default="NEWSDASH_PASSPHRASE")
    dec.set_defaults(func=cmd_decrypt)

    vec = sub.add_parser("make-vector")
    vec.add_argument("--out", default="tests/fixtures/crypto-vector.json")
    vec.set_defaults(func=cmd_make_vector)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
