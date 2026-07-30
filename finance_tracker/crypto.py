"""Passphrase-based encryption for the centralized transactions store, so the
CSV can be safely committed to a git repo (or otherwise shared/backed up)
without exposing raw transaction data.

Format (all fields concatenated, no separators):
    salt (16 bytes) || nonce (12 bytes) || ciphertext+tag (AES-256-GCM)

AES-256-GCM's authentication tag is appended to the ciphertext by both this
module and the Web Crypto API used in dashboard/index.html, and both derive
the key the same way (PBKDF2-HMAC-SHA256, same iteration count) — so a file
encrypted by one side decrypts cleanly on the other.
"""

import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

SALT_SIZE = 16
NONCE_SIZE = 12
KDF_ITERATIONS = 200_000
KEY_SIZE = 32  # AES-256


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=KEY_SIZE, salt=salt, iterations=KDF_ITERATIONS)
    return kdf.derive(passphrase.encode("utf-8"))


def encrypt_bytes(plaintext: bytes, passphrase: str) -> bytes:
    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    key = _derive_key(passphrase, salt)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
    return salt + nonce + ciphertext


def decrypt_bytes(blob: bytes, passphrase: str) -> bytes:
    if len(blob) < SALT_SIZE + NONCE_SIZE:
        raise ValueError("Encrypted data is too short to contain a salt and nonce.")
    salt, nonce, ciphertext = blob[:SALT_SIZE], blob[SALT_SIZE:SALT_SIZE + NONCE_SIZE], blob[SALT_SIZE + NONCE_SIZE:]
    key = _derive_key(passphrase, salt)
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, None)
    except Exception as e:
        raise ValueError("Decryption failed — wrong passphrase, or the file is corrupted.") from e


def encrypt_file(path, passphrase: str, output_path=None):
    from pathlib import Path
    path = Path(path)
    output_path = Path(output_path) if output_path else path.with_suffix(path.suffix + ".enc")
    output_path.write_bytes(encrypt_bytes(path.read_bytes(), passphrase))
    return output_path


def decrypt_file(path, passphrase: str, output_path=None):
    from pathlib import Path
    path = Path(path)
    if output_path is None:
        output_path = path.with_suffix("") if path.suffix == ".enc" else path.with_suffix(path.suffix + ".dec")
    output_path = Path(output_path)
    output_path.write_bytes(decrypt_bytes(path.read_bytes(), passphrase))
    return output_path
