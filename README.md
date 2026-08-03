# personal_finances

An end-to-end personal finance pipeline: a centralized, encryptable
`data/transactions.csv`, a small Python library to load and categorize new
monthly bank exports into it, an HTML dashboard to visualize it (and ingest
new files directly in the browser), and a notebook that walks through the
whole process.

## Quick reference

```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# One-time seed from an existing Excel tracker (Expenses/Income sheets)
python3 scripts/seed_from_template.py path/to/your_tracker.xlsx

# Ingest new monthly bank export(s) — one or several at once
python3 scripts/ingest_monthly.py path/to/new_export.xlsx
python3 scripts/ingest_monthly.py nov.xlsx dec.xlsx jan.xlsx --store data/transactions.csv

# Start over — backs up the current store first, never deletes outright
python3 scripts/reset_store.py

# Encrypt before committing to git / decrypt back to a working copy
python3 scripts/encrypt_store.py
python3 scripts/decrypt_store.py

# Run the dashboard
python3 -m http.server 8792
# -> http://localhost:8792/dashboard/index.html
```

A few things worth knowing before you dig into the rest of this document:

- **Duplicates are caught automatically**, across re-uploads, across multiple files, and against
  whatever's already in the store — no manual bookkeeping needed. See "Avoiding duplicates" below
  for the one edge case it can't catch.
- **`data/transactions.csv` is gitignored on purpose** — it holds real financial data. Only
  `data/transactions.csv.enc` (produced by `encrypt_store.py`) is meant to be committed.
  `data/category_overrides.json` has no personal data in it (just merchant keywords) and is safe
  to commit as-is.
- **The dashboard isn't just a viewer** — besides charts, it can ingest new files, add a single
  transaction by hand (cash, gifts, anything with no bank export), fix miscategorized transactions
  in the "Needs Review" panel, and load/save everything encrypted, all client-side.
- **`FINANCE_PASSPHRASE`** as an environment variable skips the interactive passphrase prompt for
  `encrypt_store.py` / `decrypt_store.py` — handy for scripting, but don't commit it anywhere.

## Project layout

```
finance_tracker/            Core library
  schema.py                   Unified column layout + category taxonomy
  categorize.py               Keyword rules -> (Category, Sub-category, Method)
  loader.py                   Read a raw monthly bank export (xlsx/csv), normalize columns
  pipeline.py                 Categorize raw rows, hash-based dedup, merge into the store
  overview.py                 Monthly_Overview-style aggregates + category breakdowns
  crypto.py                   AES-256-GCM encryption for the store (see Privacy below)
  overrides.py                User-taught merchant rules (see Reviewing uncertain categorizations)

scripts/
  seed_from_template.py       One-time import from an existing Excel tracker -> data/transactions.csv
  ingest_monthly.py           CLI: ingest one or more monthly files into data/transactions.csv
  reset_store.py              Back up (never delete) and empty the store, to rebuild from scratch
  encrypt_store.py            Encrypt data/transactions.csv -> data/transactions.csv.enc
  decrypt_store.py            Decrypt data/transactions.csv.enc -> data/transactions.csv

dashboard/
  index.html                   Self-contained dashboard (charts + upload-and-merge + encrypt/decrypt)
  vendor/                       Vendored Chart.js / PapaParse / SheetJS (no CDN calls, works offline)

notebook/
  pipeline_walkthrough.ipynb   Runs the same pipeline step by step, with explanations and charts

data/                          Local data (gitignored except the encrypted store — see Privacy)
  category_overrides.json      User-taught merchant rules from the dashboard's "Needs Review" panel
```

## The data model

Every transaction — income or expense — lives in one table with these columns:

`transaction_id, Date, Type, Category, Sub-category, Method, Amount (€), Notes, Month, Year, Source File`

- **Type** is `Income` or `Expense`.
- **Method** is the payment method for expenses (Cartão, MBWay, Dinheiro, Débito Direto, …) or the source for income (Transferência, MBWay, …).
- **transaction_id** is a SHA-1 hash of `date | description | amount`, computed identically in
  Python (`finance_tracker/pipeline.py`) and in the dashboard's JavaScript — so re-ingesting the
  same monthly file (via the CLI or the browser) is always a no-op, whichever tool you used first.

### Category taxonomy

| Category | Typical sub-categories | Matches on (examples) |
|---|---|---|
| **Necessário** | Combustível, Telecomunicações, Habitação, Seguros | Galp, Repsol, Vodafone, MEO, renda, condomínio, seguradoras |
| **Refeição** | Supermercado, Padaria, Restaurante | Continente, Pingo Doce, Lidl, restaurantes, cafés |
| **Lazer** | Compras Online, Subscrição, Desporto e Diversão, Viagem, Roupa | Amazon, Netflix/Spotify, bowling/cinema, voos/hotéis, Zara/Decathlon |
| **Saúde** | Farmácia, Consulta, Ginásio | farmácias, clínicas/hospitais, ginásios |
| **Geral** | Levantamento | levantamentos ATM |
| **Poupança/Investimento** | Ações/ETF, PPR/Fundo de Pensões, Criptomoeda | Degiro, XTB, eToro, Trading212 · SGF / "Gestora de Fundo" / fundos de pensões / PPR · Binance/Coinbase |
| **Comissões conta** | Comissão Bancária | comissões, manutenção de conta, imposto de selo |
| **Transferências Pessoais** | the counterparty's name, extracted from the description | any MBWay transfer, or a plain named bank transfer, with no merchant/purpose signal |
| **Outros** | — | anything unmatched (nothing is dropped) |

Income categories: `Salário, Salário_alim, Transferências Pessoais, Dinheiro, Outro` (with a
`Reembolso` sub-category for refunds).

**MBWay is a payment rail, not a category.** A raw bank line for one is just
`Trf. MB WAY para <name>` — there's no way to know *why* the money moved, unlike a card
purchase at a named merchant. So MBWay transfers (and plain named bank transfers) go under
**Transferências Pessoais** rather than a guessed spending category (previously these were all
dumped into "Lazer", which was wrong more often than not). The two directions are treated
differently, deliberately:
- **Expenses** get the counterparty's name as the sub-category (`Method` records the rail —
  `MBWay` or `Transferência` — separately) — genuinely useful for spending analysis, since it
  shows how much flowed *to* a specific person over time.
- **Income** just gets a fixed `Recebido` sub-category, not the sender's name. Unlike spending,
  who money vaguely arrived from isn't a useful "where did my money go" signal, so there's no
  value in the extra richness there.

This intentionally does **not** apply to the historical seed data: there, the user had manually
looked up each MBWay payment's real purpose (a coffee, a physio session, a phone top-up), and
that manual work is preserved as-is rather than overwritten by a guess.

Anything that doesn't match a keyword rule falls into `Outros`/`Outro` rather than being dropped.
Extend the rule lists in `finance_tracker/categorize.py` — and mirror the change in
`dashboard/index.html`, which keeps its own copy for fully offline use — as you spot new merchants
or entities. Matching is whole-word (a word-boundary regex), so short keywords like `ppr` won't
false-positive inside unrelated words. Or teach it interactively — see below.

## Reviewing uncertain categorizations

The dashboard has a **"Needs Review"** panel listing every expense that didn't get a confident,
specific category — i.e. anything still sitting in `Outros` (no keyword matched at all) or
`Transferências Pessoais` (a peer-to-peer transfer, purpose unknown from the description alone).
Clicking "Review" on a row opens a side panel to set the real Category / Sub-category / Method by
hand; saving edits that transaction in place, and "Download updated transactions.csv" persists it.

For `Outros` rows specifically, the panel also offers **"Remember for future transactions like
this"** with an editable match keyword (prefilled from the description). Checking it saves a rule
to `data/category_overrides.json` — checked before the built-in rules in `categorize.py`, both by
the dashboard and by `scripts/ingest_monthly.py` — so correcting an unrecognized merchant once
clears every other matching row immediately *and* auto-applies to that merchant in future monthly
files, without editing any code.

**This "remember" option deliberately never appears for `Transferências Pessoais` rows.** A
merchant's category is a stable fact (the bowling alley is always "Lazer"), but a peer-to-peer
transfer's purpose isn't — the same person might send you rent one month and a birthday gift the
next, so learning "this name → this category" would silently mis-categorize unrelated future
transactions from them. Those get fixed one at a time instead.

## Avoiding duplicates

Every transaction's `transaction_id` is a SHA-1 hash of `date | description | amount` — a
property of the transaction itself, not of which file it came from or when you uploaded it. That
means duplicates are caught in every situation that matters, with no extra step:

- **Re-uploading the exact same monthly file** — every row hashes the same way, so it adds zero
  new transactions the second time.
- **The same transaction appearing in two different files you upload together** — e.g. a general
  account export and a card-specific export that both happen to cover the same purchase. Both the
  dashboard and `scripts/ingest_monthly.py` process multiple files by merging each one into the
  same running store in turn, so the second file's copy is recognized as already-known the moment
  it's processed — not silently double-counted.
- **A file that overlaps with data you already have** — the same check runs against whatever is
  already in `data/transactions.csv` (or already loaded in the browser), regardless of when or how
  it got there.
- **A manual entry you accidentally add twice** — the "Add a transaction manually" form builds the
  same kind of hash, so clicking "Add" twice on identical values only ever produces one row.

What it *can't* catch: two genuinely different transactions that happen to share the same date,
description, and amount (rare, but possible — e.g. two identical €5 coffees on the same day would
hash identically and the second would be treated as a duplicate). If you need to start over
entirely and rebuild from a clean slate — e.g. after experimenting, or to double-check a batch of
files imports the way you expect — use `scripts/reset_store.py` (CLI) or "🗑 Clear all data"
(dashboard), then re-add your files; the same hash-based check applies throughout the rebuild.

## Usage

**Setup:**
```bash
pip install -r requirements.txt
```

**One-time seed** from an existing Excel tracker (Expenses/Income sheets):
```bash
python3 scripts/seed_from_template.py path/to/your_tracker.xlsx
```

**Each new month**, ingest the raw bank export — you can pass several files at once (see
"Avoiding duplicates" below for what happens if two of them overlap):
```bash
python3 scripts/ingest_monthly.py path/to/new_export.xlsx
python3 scripts/ingest_monthly.py nov.xlsx dec.xlsx jan.xlsx --store data/transactions.csv
```
This prints how many transactions were added vs. already present, and updates `data/transactions.csv` in place.

**Starting over** — back up and empty the store, then rebuild it:
```bash
python3 scripts/reset_store.py
# then re-run seed_from_template.py / ingest_monthly.py as above
```
This never deletes your data outright — it renames the current `transactions.csv` to a
timestamped `transactions.backup-<timestamp>.csv` first, so resetting is always reversible.

**Dashboard** — serve the repo over a local HTTP server (plain `file://` blocks the dashboard's
auto-load of `data/transactions.csv` due to browser security restrictions) and open it:
```bash
python3 -m http.server 8792
```
then visit `http://localhost:8792/dashboard/index.html`. From there you can also pick "Add monthly
file(s) (xlsx/csv)" — selecting multiple files at once is fine — to categorize and merge new
months directly in the browser, then "Download updated transactions.csv" to save the result back
over `data/transactions.csv`. "🗑 Clear all data" resets the in-browser working copy to empty (it
only touches what's loaded in the tab — nothing on disk changes unless you download afterward),
so you can rebuild from scratch the same way. The "Needs Review" panel (see below) lets you fix
anything the keyword rules couldn't confidently categorize; "Download updated
category_overrides.json" saves any merchant rules you taught it that way, so
they're picked up by future CLI ingestion too — unlike `transactions.csv`, this file has no
personal financial data in it (just merchant keywords), so it's fine to commit as-is.

**Adding a transaction manually** — for anything with no bank export at all (cash you received or
spent, a gift, etc.), use the "Add a transaction manually" form: pick Income or Expense, fill in
the date, amount, category, and any notes, and it's added straight into the store — same charts,
same table, same "Download updated transactions.csv" afterward. It goes through the same
duplicate check as an upload, so double-clicking "Add" by accident on identical values won't
create two rows (see "Avoiding duplicates" below).

**Notebook** — `notebook/pipeline_walkthrough.ipynb` runs the same load → categorize → merge →
aggregate steps with explanations, useful as a reference or for ad-hoc analysis beyond what the
dashboard charts.

## Privacy: encrypting the store

`data/transactions.csv` holds real transaction data, so this repo's `.gitignore` excludes it —
only the **encrypted** file is meant to be committed:

```bash
# before committing: encrypt the plaintext CSV
python3 scripts/encrypt_store.py
# -> writes data/transactions.csv.enc (AES-256-GCM, passphrase-derived key via PBKDF2-SHA256)

# after cloning, or any time you need the plaintext back locally
python3 scripts/decrypt_store.py
```

Both scripts read the passphrase from the `FINANCE_PASSPHRASE` environment variable if set,
otherwise prompt for it interactively (hidden input — never logged, echoed, or written to disk).
**There is no recovery mechanism if you lose the passphrase** — that's inherent to this being a
real encryption scheme rather than obfuscation.

The dashboard can also load and save the encrypted file directly, decrypting entirely client-side
via the browser's native Web Crypto API — nothing is sent over the network and the passphrase
never leaves your browser tab:
- **Load encrypted (.enc)** — decrypts and loads `transactions.csv.enc` in place of the plaintext CSV
- **Download encrypted (.enc)** — encrypts the current in-memory store and downloads it

Both sides (Python and JavaScript) use the exact same format — `salt(16 bytes) || nonce(12 bytes)
|| AES-256-GCM ciphertext`, same PBKDF2 iteration count — so a file encrypted by one decrypts
cleanly on the other.

This protects the file *at rest* (on disk, in git history, in backups). It does not protect data
while a script or the dashboard has it open and decrypted in memory — that's a different threat
model (full-disk encryption / OS-level access control) that this project doesn't attempt to solve.
