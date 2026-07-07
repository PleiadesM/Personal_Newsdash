// WebCrypto side of the envelope contract in docs/DATA_CONTRACT.md.
// Pinned against the Python encryptor by tests/test_crypto_webcrypto.mjs.
// Never persist the passphrase; the derived key bytes may be stored only
// behind the explicit "remember on this device" opt-in.

const te = new TextEncoder();
const td = new TextDecoder();

export const AAD_PREFIX = "newsdash:v1:";
export const CHECK_PLAINTEXT = "newsdash:ok";

export function b64decode(s) {
  return Uint8Array.from(atob(s), (c) => c.charCodeAt(0));
}

export function b64encode(bytes) {
  let out = "";
  for (const b of new Uint8Array(bytes)) out += String.fromCharCode(b);
  return btoa(out);
}

export async function deriveKeyBytes(passphrase, kdf) {
  const material = await crypto.subtle.importKey(
    "raw", te.encode(passphrase.normalize("NFC")),
    { name: "PBKDF2" }, false, ["deriveBits"],
  );
  return crypto.subtle.deriveBits(
    { name: "PBKDF2", salt: b64decode(kdf.salt),
      iterations: kdf.iterations, hash: "SHA-256" },
    material, 256,
  );
}

export async function importKeyBytes(bytes) {
  return crypto.subtle.importKey(
    "raw", bytes, { name: "AES-GCM" }, false, ["decrypt"],
  );
}

async function decryptRaw(key, sectionId, nonceB64, ctB64) {
  return crypto.subtle.decrypt(
    { name: "AES-GCM", iv: b64decode(nonceB64),
      additionalData: te.encode(AAD_PREFIX + sectionId) },
    key, b64decode(ctB64),
  );
}

// Returns true iff the key decrypts the manifest's check block.
export async function verifyCheck(manifestCrypto, key) {
  try {
    const pt = await decryptRaw(key, "check",
      manifestCrypto.check.nonce, manifestCrypto.check.ct);
    return td.decode(pt) === CHECK_PLAINTEXT;
  } catch {
    return false;
  }
}

// Decrypt one *.enc.json envelope into its JSON payload.
export async function decryptEnvelope(envelope, key, sectionId) {
  const pt = await decryptRaw(key, sectionId, envelope.nonce, envelope.ct);
  return JSON.parse(td.decode(pt));
}
