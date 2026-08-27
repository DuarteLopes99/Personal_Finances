#!/usr/bin/env python3
"""Encrypt data/transactions.csv into data/transactions.csv.enc (AES-256-GCM),
so the encrypted file — never the plaintext CSV — is what gets committed to git.

The passphrase is read from the FINANCE_PASSPHRASE environment variable if set,
otherwise prompted for interactively (hidden input, never logged or echoed).
Losing the passphrase means losing access to the encrypted file — there is no
recovery mechanism by design.

Usage:
    python3 scripts/encrypt_store.py [path/to/transactions.csv] [path/to/output.enc]
"""

import argparse
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
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", nargs="?", type=Path, default=DEFAULT_INPUT,
                        help="Store to encrypt (default: data/transactions.csv)")
    parser.add_argument("output", nargs="?", type=Path, default=None,
                        help="Where to write the .enc (default: alongside, with .enc appended)")
    args = parser.parse_args()
    input_path, output_path = args.input, args.output

    if not input_path.exists():
        print(f"{input_path} does not exist.", file=sys.stderr)
        sys.exit(1)

    passphrase = _read_passphrase()
    out = crypto.encrypt_file(input_path, passphrase, output_path)
    print(f"Encrypted {input_path.name} -> {out}")
    print("Keep the plaintext CSV out of git (see .gitignore); only the .enc file should be committed.")


if __name__ == "__main__":
    main()
