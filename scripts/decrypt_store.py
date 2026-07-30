#!/usr/bin/env python3
"""Decrypt data/transactions.csv.enc back into a plaintext data/transactions.csv
for local use by the scripts, dashboard, or notebook.

The passphrase is read from the FINANCE_PASSPHRASE environment variable if set,
otherwise prompted for interactively (hidden input, never logged or echoed).

Usage:
    python scripts/decrypt_store.py [path/to/transactions.csv.enc] [path/to/output.csv]
"""

import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from finance_tracker import crypto  # noqa: E402

DEFAULT_INPUT = Path(__file__).resolve().parent.parent / "data" / "transactions.csv.enc"


def _read_passphrase() -> str:
    return os.environ.get("FINANCE_PASSPHRASE") or getpass.getpass("Passphrase to decrypt with: ")


def main():
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    if not input_path.exists():
        print(f"{input_path} does not exist.", file=sys.stderr)
        sys.exit(1)

    passphrase = _read_passphrase()
    try:
        out = crypto.decrypt_file(input_path, passphrase, output_path)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    print(f"Decrypted {input_path.name} -> {out}")


if __name__ == "__main__":
    main()
