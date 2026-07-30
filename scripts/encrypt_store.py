#!/usr/bin/env python3
"""Encrypt data/transactions.csv into data/transactions.csv.enc (AES-256-GCM),
so the encrypted file — never the plaintext CSV — is what gets committed to git.

The passphrase is read from the FINANCE_PASSPHRASE environment variable if set,
otherwise prompted for interactively (hidden input, never logged or echoed).
Losing the passphrase means losing access to the encrypted file — there is no
recovery mechanism by design.

Usage:
    python scripts/encrypt_store.py [path/to/transactions.csv] [path/to/output.enc]
"""

import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from finance_tracker import crypto  # noqa: E402

DEFAULT_INPUT = Path(__file__).resolve().parent.parent / "data" / "transactions.csv"


def _read_passphrase() -> str:
    env_value = os.environ.get("FINANCE_PASSPHRASE")
    if env_value:
        return env_value
    passphrase = getpass.getpass("Passphrase to encrypt with: ")
    confirm = getpass.getpass("Confirm passphrase: ")
    if passphrase != confirm:
        print("Passphrases did not match.", file=sys.stderr)
        sys.exit(1)
    if not passphrase:
        print("Passphrase cannot be empty.", file=sys.stderr)
        sys.exit(1)
    return passphrase


def main():
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    if not input_path.exists():
        print(f"{input_path} does not exist.", file=sys.stderr)
        sys.exit(1)

    passphrase = _read_passphrase()
    out = crypto.encrypt_file(input_path, passphrase, output_path)
    print(f"Encrypted {input_path.name} -> {out}")
    print("Keep the plaintext CSV out of git (see .gitignore); only the .enc file should be committed.")


if __name__ == "__main__":
    main()
