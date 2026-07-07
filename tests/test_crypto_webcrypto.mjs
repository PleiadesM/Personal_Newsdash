// Cross-language proof: Node's WebCrypto decrypts a Python-encrypted vector.
// This pins the envelope format the browser (assets/js/crypto.js) relies on.
// Run: node tests/test_crypto_webcrypto.mjs
import { readFileSync } from "node:fs";
import { webcrypto } from "node:crypto";
import assert from "node:assert/strict";

const subtle = webcrypto.subtle;
const vec = JSON.parse(
  readFileSync(new URL("./fixtures/crypto-vector.json", import.meta.url), "utf8"),
);
const env = vec.envelope;
const b64d = (s) => Uint8Array.from(Buffer.from(s, "base64"));
const te = new TextEncoder();

assert.equal(env.alg, "AES-256-GCM");
assert.equal(env.kdf.name, "PBKDF2");
assert.equal(env.kdf.hash, "SHA-256");

const keyMaterial = await subtle.importKey(
  "raw", te.encode(vec.passphrase.normalize("NFC")),
  { name: "PBKDF2" }, false, ["deriveKey"],
);
const key = await subtle.deriveKey(
  { name: "PBKDF2", salt: b64d(env.kdf.salt),
    iterations: env.kdf.iterations, hash: "SHA-256" },
  keyMaterial, { name: "AES-GCM", length: 256 }, false, ["decrypt"],
);
const plaintext = await subtle.decrypt(
  { name: "AES-GCM", iv: b64d(env.nonce),
    additionalData: te.encode(`newsdash:v1:${vec.section}`) },
  key, b64d(env.ct),
);
const obj = JSON.parse(new TextDecoder().decode(plaintext));
assert.deepEqual(obj, vec.payload);
console.log("webcrypto cross-decrypt OK");
