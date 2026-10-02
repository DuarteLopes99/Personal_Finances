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

# Put a double-clickable launcher on the Desktop (macOS) — do this once
python3 scripts/install_desktop_shortcut.py

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

# Run the dashboard — double-click "Finance Dashboard" on the Desktop, or:
python3 scripts/serve_dashboard.py
```

A few things worth knowing before you dig into the rest of this document:

- **Duplicates are caught automatically**, across re-uploads, across multiple files, and against
  whatever's already in the store — no manual bookkeeping needed. See "Avoiding duplicates" below
  for the one edge case it can't catch.
- **The notebook uses synthetic data only, by design.** `pipeline_walkthrough.ipynb` builds its own
  12-row export and a 5-month store in memory; it never reads `data/transactions.csv` and never
  writes anything. Clear its outputs before committing (`python3 scripts/strip_notebook_outputs.py`)
  — the pre-commit hook enforces it, because a notebook stores its outputs inside itself and
  `.gitignore` cannot cover part of a file.
- **`data/transactions.csv` is gitignored on purpose** — it holds real financial data. Only
  `data/transactions.csv.enc` (produced by `encrypt_store.py`) is meant to be committed.
  `data/category_overrides.json` has no personal data in it (just keywords — though a peer rule
  will contain a counterparty's name, so check before committing one). `data/review_decisions.json`
  holds your own notes and the original bank descriptions, and is gitignored like the store.
- **The dashboard isn't just a viewer** — besides charts, it can ingest new files, add a single
  transaction by hand (cash, gifts, anything with no bank export), fix miscategorized transactions
  in the "Needs Review" panel, and load/save everything encrypted, all client-side.
- **Review decisions survive a rebuild.** What you worked out about a transaction — the category
  *and* the note explaining what it actually was — is stored outside the store, keyed by the
  transaction's hash, and re-applied automatically whenever that transaction reappears. Resetting
  and re-ingesting from scratch no longer throws that work away. See "Reviewing uncertain
  categorizations" below.
- **Double-click "Finance Dashboard" on the Desktop** to launch it (after running
  `scripts/install_desktop_shortcut.py` once). The shortcut is a symlink, and the server it starts
  sends no-cache headers, so you always get the current code and the current data — never a stale
  tab. See "The desktop shortcut" below.
- **`FINANCE_PASSPHRASE`** as an environment variable skips the interactive passphrase prompt for
  `encrypt_store.py` / `decrypt_store.py` — handy for scripting, but don't commit it anywhere.

## Documentation

Design documentation lives in [`docs/`](docs/):

| Document | Answers |
|---|---|
| [docs/pipeline-overview.md](docs/pipeline-overview.md) | What happens between a bank export and a chart, with flowcharts |
| [docs/categorization.md](docs/categorization.md) | How a category is decided — the ladder, its guarantees, its known hazards |
| [docs/knowledge-placement.md](docs/knowledge-placement.md) | Where to put something you know, and why knowledge is split across four places |

This README stays the practical guide — commands and day-to-day usage. Those documents cover why
the design is shaped the way it is, which is what matters when deciding where to add something.

## Project layout

```
finance_tracker/            Core library
  taxonomy.py                 THE strict Category/Sub-category vocabulary — the base of everything
  schema.py                   Unified column layout (re-exports the taxonomy)
  categorize.py               Regex rules -> (Category, Sub-category, Method)
  loader.py                   Read a raw monthly bank export (xlsx/csv), normalize columns
  pipeline.py                 Categorize raw rows, hash-based dedup, merge into the store
  overview.py                 Monthly aggregates, breakdowns, and the spending analytics
  crypto.py                   AES-256-GCM encryption for the store (see Privacy below)
  overrides.py                User-taught merchant + peer rules (see Reviewing uncertain categorizations)
  reviews.py                  Durable memory of manual review decisions, keyed by transaction hash

scripts/
  seed_from_template.py       One-time import from an existing Excel tracker -> data/transactions.csv
  ingest_monthly.py           CLI: ingest one or more monthly files into data/transactions.csv
  reset_store.py              Back up (never delete) and empty the store, to rebuild from scratch
  encrypt_store.py            Encrypt data/transactions.csv -> data/transactions.csv.enc
  decrypt_store.py            Decrypt data/transactions.csv.enc -> data/transactions.csv
  serve_dashboard.py          Local no-cache server + opens the dashboard (what the shortcut runs)
  generate_dashboard_rules.py Regenerate dashboard/rules.js from taxonomy.py + categorize.py
  recategorize.py             Re-run the taxonomy + rules over the store (dry run by default)
  strip_notebook_outputs.py   Clear notebook cell outputs — they contain real transaction data
  install_git_hooks.py        Pre-commit guard: blocks plaintext data, notebook outputs, stale rules
  Finance Dashboard.command   Double-clickable launcher (the Desktop shortcut points here)
  install_desktop_shortcut.py Put/remove that launcher on the Desktop

dashboard/
  index.html                   The dashboard (charts + upload-and-merge + review + encrypt/decrypt)
  rules.js                     GENERATED taxonomy + regex rules — never edit by hand
  vendor/                       Vendored Chart.js / PapaParse / SheetJS (no CDN calls, works offline)

notebook/
  pipeline_walkthrough.ipynb   The pipeline step by step on SYNTHETIC data — never reads your store

data/                          Local data (gitignored except the encrypted store — see Privacy)
  category_overrides.json      User-taught rules from the dashboard's "Needs Review" panel
  review_decisions.json        Manual review decisions + notes, keyed by transaction hash (gitignored)
```

## The data model

Every transaction — income or expense — lives in one table with these columns:

`transaction_id, Date, Type, Category, Sub-category, Method, Amount (€), Notes, Review Note,
Reviewed At, Month, Year, Source File`

- **Type** is `Income` or `Expense`. A **refund** ("Devolução", "Estorno", or anything you mark as
  one in the review panel) is an `Expense` with a **negative** amount, filed under what was bought,
  so it lowers that category's spending instead of counting as income. See
  [docs/categorization.md](docs/categorization.md#refunds-are-negative-spending-not-income).
- **Method** is the payment rail: `Cartão, MBWay, Transferência, Débito Direto, Cartão
  Alimentação, Dinheiro, Levantamento` (plus `Não especificado` for a handful of historical rows
  that never had one recorded). **MBWay and Transferência are only ever a Method, never a
  Category** — see below for why that distinction matters.
- **transaction_id** is a SHA-1 hash of `date | description | amount`, computed identically in
  Python (`finance_tracker/pipeline.py`) and in the dashboard's JavaScript — so re-ingesting the
  same monthly file (via the CLI or the browser) is always a no-op, whichever tool you used first.
  Because the hash depends only on the transaction itself, it is also stable across a full
  rebuild — which is what lets review decisions be re-attached to the right rows afterwards.
- **Review Note / Reviewed At** are filled in only by a manual review. `Review Note` is whatever
  you wrote down about what the transaction actually was; `Reviewed At` is a local-time timestamp
  and doubles as the "this row has a human answer" flag — keyword rules never overwrite a row
  that has one.

### Category taxonomy

`finance_tracker/taxonomy.py` declares **every Category / Sub-category pair that may exist** — 10
expense categories, 6 income categories, 63 valid pairs — and everything that writes a
classification is validated against it: the built-in rules at import time, user overrides before
they are saved, and the dashboard's review panel through a per-category picker rather than a text
box.

That inversion is the point. The taxonomy used to be a list of names that nothing enforced, so
every writer invented its own vocabulary and the store filled with `Gasoleo` next to `Combustível`,
`Telemovel` next to `Telecomunicações`, `SuperMercado` under `Lazer`, and 71 sub-categories that
were just people's names. Each splits one real spending line into two chart bars that never add up.

**Expenses**

| Category | Sub-categories |
|---|---|
| **Saúde** | Lentes · Fisioterapia · Farmácia · Consultas/Exames · Outros |
| **Investimentos** | ETFs/DEGIRO · PPR · Outros |
| **Alimentação** | Compras · Restaurantes · Café/Padaria · Take-away/Delivery · Outros |
| **Lazer** | Escape Room · Saídas Noite/Bares · Férias · Cinema/Espetáculos · LEGO/Pop-Culture/Memorabilia · Roupa · Subscrições · Compras Online · Gaming · Outros |
| **Educação** | Cursos/Formação · Livros/Material · Outros |
| **Geral** | Gasóleo · Carro · Telemóvel · Transportes · Casa · Seguros · Comissões e Impostos · Revolut · TradeRepublic · Outros |
| **Desporto** | Futebol · Corrida · Ginásio · Equipamento · Outros |
| **Prendas** | Aniversário · Natal · Outros |
| **Cabelo** | Cabeleireiro/Barbeiro · Produtos · Outros |
| **Outros** | Por Classificar · Outros · Levantamento · Transferências Pessoais |

**Income**

| Category | Sub-categories |
|---|---|
| **Salário** | Salário · Outros |
| **Salário Alimentação** | Salário Alimentação |
| **Transferências Pessoais** | MBWay · Transferência |
| **Subsídios** | Desemprego · Outros |
| **Reembolsos** | IRS · Seguros · Estornos |
| **Outros** | Por Classificar · Outros |

Three categories are shaped deliberately:

- **`Outros`** carries both kinds of "don't know". `Por Classificar` *is* the review queue and
  should trend to zero; `Outros`, `Levantamento` and `Transferências Pessoais` are settled facts
  that simply aren't spending categories — genuinely miscellaneous, cash withdrawn, money sent to a
  named person — and counting them as backlog would make the queue look permanently unfixable.
- **`Investimentos`** is money moving pocket-to-pocket, so it is excluded from every expense total.
- **`Reembolsos`** (income) is money back that is *not* a purchase undone: a tax refund, an
  insurance payout, a bare "reembolso". A shop refund is netted against the purchase instead.
- **`Cabelo`** is empty on purpose. It was added so the spend has somewhere to go the first time it
  happens, instead of landing in `Geral/Outros` and being invisible from then on. It deliberately
  has **no keyword rules**: a rule would retro-classify transactions already reviewed into other
  categories, silently rewriting answers that were given by hand. It fills up through the review
  panel and the manual-entry form, and a rule can be added once real descriptions exist.

#### One colour per category

Chart colours are keyed on the category **name**, from a fixed nine-hue palette plus a reserved
neutral for `Outros` — which is the residual bucket rather than an identity, so it wears ink rather
than a hue. Two consequences worth knowing:

- **No two categories share a colour.** Colours used to come from `palette[index % 8]`, and with
  more than eight expense categories that wrapped: `Outros` (index 8) came out the same blue as
  `Saúde` (index 0), in every chart showing both.
- **A colour follows its category, not its rank.** Filtering to a year with no `Educação` spend
  does not repaint everything below it, so the same category is the same colour in the doughnut,
  the stacked trend and the single-category line.

The palette is checked, not eyeballed: every adjacent pair clears a colour-blindness separation
floor (ΔE ≥ 8 in OKLab under simulated protanopia and deuteranopia) and a normal-vision floor
(ΔE ≥ 15), in both light and dark themes. Three light-theme hues sit under 3:1 contrast against the
page, which is why every chart also ships a "View as table" disclosure.

### How a description reaches a pair

Two independent steps, kept deliberately separate:

1. **Category / Sub-category** comes only from purpose signals (supermarket, restaurant, cinema,
   Vodafone, Degiro, ...). MBWay and "transferência" are never purpose signals — they say nothing
   about *why* money moved — so they never appear in this step.
2. **Method** (the rail) is detected independently and overrides whatever the category step
   suggested: a description containing "mbway" is always `Method=MBWay`, regardless of what it's for.

This matters because a rail keyword and a purpose keyword appear in the same description all the
time — `"Mbway - Cinemas"` — and both must be honored: **Lazer / Cinema-Espetáculos, via MBWay**.
An earlier version treated MBWay as its own category, so the rail always won and silently swallowed
the purpose signal.

Matching is by **regex over a normalized description** — lowercased, accents stripped, whitespace
collapsed — with whole-word boundaries applied automatically. So patterns are written unaccented
once instead of twice, `cerveja` doesn't match inside `cervejaria`, and `vodaf[a-z]*` reaches the
ten rows the bank truncated to `Carregamentos Vodafo`.

Order of authority, weakest to strongest: built-in rules → merchant overrides → your review. Ahead
of all of them sits one refusal: descriptions naming a **payment gateway** (Nuvei, Eupago, Stripe,
Easypay, Safecharge, Payshop) go straight to the review queue, because they name the processor and
never what was bought.

**When nothing matches**, the answer is an honest one rather than a guess: `Outros / Por
Classificar` for the review queue, or `Outros / Transferências Pessoais` when the rail is
MBWay/Transferência. The counterparty's name is **not** used as a sub-category — it stays in
`Notes`, where the queue still shows it.

Extend `PURPOSE_EXPENSE_RULES`/`PURPOSE_INCOME_RULES` in `finance_tracker/categorize.py` as you
spot new merchants, then regenerate the dashboard's copy:

```bash
python3 scripts/generate_dashboard_rules.py     # writes dashboard/rules.js
```

Patterns must use **ASCII-safe regex syntax only** — no `\b`, `\w` or `\p{...}` — since those are
exactly the constructs whose meaning differs between Python and the browser. See
[docs/categorization.md](docs/categorization.md).

**Write one rule per purpose, never one per payment rail.** The fourth element of a rule is only a
default for when the description names no rail at all — `_overlay_method()` detects the real rail
independently and overrides it, so a single `Ginásio` rule already handles both
`Ginasio Solinca` → `Saúde/Ginásio/Cartão` and `Mbway - Ginasio Solinca` →
`Saúde/Ginásio/MBWay`. A second copy of a rule differing only in that default is **unreachable**:
rules are first-match-wins, so the duplicate never executes.

Keywords are matched case-insensitively against the description, so a keyword written in capitals
still works — but they are lowercased in the tables by convention. Matching is whole-word (a word-boundary regex), so short
keywords like `ppr` won't false-positive inside unrelated words. Or teach it interactively — see
below.

### Analyzing by payment method

Category answers "what was it for"; Method answers "how did the money move". The dashboard has
**Expense methods** and **Income methods** charts alongside the category ones — same style,
same filters — so you can see at a glance how much flowed through MBWay vs. card vs. cash, etc.
`finance_tracker/overview.compute_method_breakdown()` is the Python-side equivalent (see the
notebook for an example).

### Excluding the meal-allowance card (Cartão Alimentação)

`Salário Alimentação` (income) and any expense paid with the `Cartão Alimentação` method are money
earmarked for food, not general disposable income — mirroring how the original Excel template
excluded it from its own Monthly_Overview sums. The dashboard's **"Exclude Cartão Alimentação
(meal card)"** checkbox (next to the year filter) lets you toggle between the full picture and
the picture *without* that money — applied consistently to the stat tiles, the "Income vs
Expenses by month" and "Net balance by month" charts, both category/method breakdowns, and the
transaction table, the same way the year filter already does. `finance_tracker/overview.
exclude_method()` is the Python-side equivalent.

## Reviewing and correcting categorizations

Two different jobs, with two different starting points, and the dashboard treats them as such.

**"Nothing matched this — what was it?"** is the **Needs Review** panel: every transaction, income
*and* expense, sitting on `Outros / Por Classificar`. Each row states its **Type** in a column of
its own, and the panel opens with an income/expense banner — the two draw from different category
lists and move every total on the page in opposite directions, so which one you're editing is never
left to be inferred from the amount.

**"The rules got this wrong"** is the **Transactions table**, where you already know the category
and simply disagree with it. Filter down to what you doubt, then hit *Review* on any row.

### Filtering to what you want to check

| Filter | Does |
|---|---|
| Type | Income / Expense — also narrows the two lists below to that type's categories |
| Category | Every category in the taxonomy, whether or not the store currently uses it |
| Sub-category | Re-stocked from whichever category is selected, so the pair can never contradict |
| Review state | *Awaiting an answer* · *Auto-classified, unchecked* · *Reviewed by hand* |
| Search | Notes, category, sub-category **and** review notes |

The category and sub-category lists come from `taxonomy.py`, not from the values the store happens
to contain. That's deliberate: being able to select an empty category is how you notice nothing was
ever filed under `Educação`, and a value that has drifted out of the taxonomy must not quietly
become a legitimate-looking filter option — the Data health panel is where those belong.

**Review state = "Auto-classified, unchecked"** is the one that's otherwise invisible: rows the
rules answered on their own that no human has ever looked at. An unchecked auto-classification and
a reviewed one look identical in the table, so filtering a category down to just the unchecked rows
is how you audit a rule you've written. The Needs Review card links straight to it.

The table caption reports the **total for the current filter**, not just a count — filtering to
Alimentação / Restaurantes and being told "54 transactions" answers half a question.

### The review panel

Clicking *Review* opens a side panel to set the Category / Sub-category / Method by hand. Saving
edits that transaction in place, stamps `Reviewed At`, and — when you launched through the desktop
shortcut or `scripts/serve_dashboard.py` — writes the store back to `data/transactions.csv` on its
own. "Download updated transactions.csv" is the fallback for a tab opened without the server.

It opens differently depending on what it's looking at, because the three states are genuinely
different questions:

| Row state | Panel says | Category picker |
|---|---|---|
| `Outros / Por Classificar` | *Complete this transaction* | Empty — an explicit choice is required |
| Auto-classified, unreviewed | *Correct this transaction* | Pre-selected to the current pair |
| Already reviewed | *Edit this review* | Pre-selected to the current pair |

Only a queued row starts blank, and only because leaving it untouched would save the row straight
back into the queue. Everything else opens on its current answer, so correcting one is a single
change rather than a re-entry of an answer that was already 90% right. `Por Classificar` is
offered but refused on save, for the same reason.

### Keeping the details, not just the answer

Working out what an unrecognized transaction was is the expensive part — checking a receipt,
remembering a date, matching an amount against a calendar entry. The category alone doesn't
record any of that, so the panel has a **"What was it?"** field, and everything you enter is kept
in three places at once:

- the store's own `Review Note` / `Reviewed At` columns, so it travels with `transactions.csv`
  (and is searchable from the Transactions table, alongside the description);
- **your browser's local storage**, written the instant you press Save — so closing the tab
  without downloading anything doesn't lose the decision;
- **`data/review_decisions.json`**, written straight to disk through the local server (the
  "Download review_decisions.json" button is the fallback when there isn't one), keyed by
  `transaction_id` — this is the copy the Python side reads.

Because the key is the transaction's own hash, a decision re-attaches itself to the right row
whenever that row reappears: re-ingesting a file, rebuilding the store from scratch, or restoring
a backup. `scripts/ingest_monthly.py` and `scripts/seed_from_template.py` re-apply saved decisions
automatically, and `scripts/reset_store.py` harvests them out of the store *before* wiping it. A
row carrying `Reviewed At` is also treated as settled — keyword rules and overrides never
overwrite a human answer.

Reviewing isn't one-shot either: every row in the Transactions table has an **Edit review**
button, so you can revisit a decision, read what you wrote last time, and change it.

### Applying one review to the identical items

Most of the queue is repeats: this store has 262 rows but only 160 distinct descriptions —
`Uber Rides` appears 10 times, `Carregamentos Vodafo` 10, `Balizaslandia Aveiro` 7. So when you
review one, the panel offers to apply the answer to the others with the **exact same
description**, showing the count, the total, and every date and amount before you commit. On this
store that turns 262 manual reviews into 160.

Three deliberate limits, each of which cost something to give up:

- **Exact match only.** Looser keys score better right up until you look at what they merge:
  grouping by the first two words clears 53% of this queue instead of 39%, but every peer transfer
  starts `Trf. MB WAY para`, so that key collapses all 32 distinct counterparties into one bucket
  and reviewing one person's transfer would re-file all 84 rows.
- **Pre-checked for merchants, unchecked for transfers.** For a merchant the name fixes the
  category regardless of amount — `Uber Rides` spans €4.94–€88.62 and is still Uber. For a peer
  transfer it doesn't: `Dr Duarte N Lopes` spans €13–€263 across 8 rows. Those are offered, with
  the amounts on screen, but you have to opt in each time.
- **Not offered at all when the description names nobody** — `Trf. MB WAY emitida` appears 9 times
  for €1.70 to €80.00 and identifies no counterparty, so identical text is not evidence of a shared
  purpose.

Each match has **its own checkbox**, so ten rows sharing a description don't have to share a fate:
tick the seven you're sure about and the other three stay in the queue for individual attention.
"Select all" / "Select none" are there for the common cases.

Auto-filled rows get the category and sub-category but **never your note** — that records what you
actually looked at. They carry a provenance marker instead, show as `auto` (dashed) rather than
`reviewed` in the Transactions table, and are counted separately in Data health. Because one click
can change ten rows, the status line offers an **Undo** that restores every one of them while
leaving the transaction you actually reviewed alone.

`scripts/ingest_monthly.py` does the merchant half of this automatically
(`reviews.apply_by_description`), so next month's `Uber Rides` inherits the answer you gave last
month's instead of landing back in the queue. It never auto-fills transfers: the dashboard can
offer those because a human is there to judge, and a batch import has nobody to ask. A derived row
is never itself used as a source, so one review can't chain across descriptions it never matched.

### Reviewing several unrelated transactions at once

Sometimes transactions belong together for a reason no description can express: four MBWay
transfers over three days that were one dinner split, a weekend of unrelated-looking payments for
the same trip. Tick any rows in the Needs Review table and press **"Review N selected together"**.

This is deliberately the *opposite* of the feature above. It categorizes exactly the rows you
picked and **remembers nothing about the grouping** — no override, no peer rule, no
description-keyed association. The reason those rows belonged together was one evening, not a
property of those counterparties, and learning it would mis-file every future transfer from the
same people. Your note *is* kept on each row, because unlike an auto-applied match you actually
looked at these.

The Method selector offers "Leave each transaction's own method", which is the default: a batch
usually spans several rails (a real one in this store mixes MBWay and Cartão), and the rail is an
observed fact per transaction. If you select both income and expense rows, the panel says so and
refuses to offer a category — there isn't one that could be right for both.

### Sub-categories are a picker, not a text box

Choosing a category re-stocks the sub-category dropdown with exactly that category's sub-categories
from `taxonomy.py`. An invalid pair cannot be expressed, so there is nothing to warn about.

This replaced a free-text box with a datalist of every sub-category the store had ever seen, plus a
soft "that pair looks wrong" warning — and a suggestion you can ignore is not a constraint. That
design is how the store acquired `Gasoleo`/`Gasóleo`, `Telemovel`/`Telecomunicações` and 71
sub-categories that were counterparty names.

`Por Classificar` is offered but refused on save: it *is* the queue, so saving it would put the row
straight back where it came from.

### Teaching it a rule

The panel also offers **"Remember for future transactions like this"** with an editable match
keyword (prefilled from the description). Checking it saves a rule to
`data/category_overrides.json` — checked before the built-in rules in `categorize.py`, both by the
dashboard and by `scripts/ingest_monthly.py` — so correcting an unrecognized merchant once clears
every other matching row immediately *and* auto-applies to that merchant in future monthly files,
without editing any code.

**For MBWay and bank transfers, a different, opt-in rule is offered instead.** A merchant's
category is a stable fact (the bowling alley is always "Lazer"), but a peer-to-peer transfer's
purpose usually isn't — the same person might send you rent one month and a birthday gift the
next. So that case gets its own separate, visually-flagged checkbox: **"Always file transfers
from/to this person under this sub-category"**, off by default, prefilled with the counterparty's
name rather than the whole description.

It's offered because the alternative — re-typing the same correction every month for a
counterparty who genuinely is always the same thing (the colleague you split lunch with, the
friend you pay for the weekly court booking) — is its own kind of data loss. It's deliberately
weaker than a merchant rule in three ways:

- it's saved with `"peer": true` and is only consulted in the **fallback** path, so a real purpose
  keyword always wins — `"Mbway - Cinemas"` stays Lazer/Cinema even if that counterparty has a
  peer rule;
- it sets Category and Sub-category but **never the Method** — the payment rail is something
  observed per transaction, not something to infer from a name;
- it matches against the extracted counterparty name, so it learns *"Ana Silva"* rather than the
  boilerplate around her, and it never applies to a card payment that happens to mention the same
  words.

Both kinds live in the same `category_overrides.json` and are told apart by the `peer` flag; a
file written before this existed still loads fine (no flag means a merchant rule).

## Monthly spending analytics

The charts answer "what did this month total?". The **Monthly analysis** card answers the
questions you actually open a finance dashboard to ask. Pick a month and a baseline window, and
it reports:

- **Spent**, with savings/investment transfers excluded — that money moved, it wasn't spent, and
  counting it makes every month you invested look like a blowout.
- **vs previous month** and **vs the trailing average**, in € and %. The trailing average
  deliberately excludes the month being judged: a month compared against an average it's part of
  always looks closer to normal than it really is.
- **Savings rate** — the share of income you didn't spend, which is the one number that says
  whether a month went well independently of how big that month's income happened to be.
- **Per day**, and for a month that's still running, where it lands at the current pace.
- **Spending pace through the month** — cumulative spend by day, against the average shape of the
  baseline months. Totals tell you a month was expensive after it's over; this tells you while you
  can still do something about it.
- **Category spend by month** (stacked) — which category is *trending*, as opposed to which was
  biggest once.
- **Top sub-categories this month** — "Alimentação is your biggest category" isn't actionable;
  "Restaurante €310 vs Supermercado €180" is.
- **Recurring commitments** — charges from the same merchant (or, for a transfer, the same
  counterparty) within a sub-category, for an amount within 15% of their own median, with the
  annualized cost. **Monthly** once they appear in 3+ distinct months (twelve charges a year);
  **yearly** when they repeat about every 12 months (one charge a year). The median check is what
  separates Netflix at €8.99 every month from a restaurant that's also monthly but never the same
  price twice; grouping by merchant is what keeps Netflix and Disney+ two charges rather than one
  averaged one.
- **Biggest expenses this month**, each as a share of the month.

The card honours the "Exclude Cartão Alimentação" toggle but deliberately ignores the year filter
— it has its own month selector, and comparing January against the previous three months has to be
able to reach back across the year boundary.

Every one of these has a Python equivalent in `finance_tracker/overview.py`
(`compute_month_over_month`, `compute_savings_rate`, `compute_subcategory_breakdown`,
`compute_category_by_month`, `detect_recurring`, `project_month_end`) — see the notebook.

### Tracking one category over time

Every card above answers a question about a *month*. **Track one category over time** answers the
other question — "how has this one thing been going?" — for a single Category or Sub-category
picked from a dropdown. The stacked *Category spend by month* chart technically contains that
answer, but reading one category out of nine stacked segments is guessing rather than reading.

Three views of the same selection:

| Mode | Answers |
|---|---|
| **Amount per month** | is this drifting up or down |
| **Share of that month's total** | is it growing *relative to* everything else, or did the whole month just get bigger |
| **Running total** | what has this cost me altogether so far |

Alongside the line it reports the total, the average per month, the highest month, the latest
month against the one before it, and how many of the months in range had any activity at all.

Two deliberate choices:

- **Months with no activity are drawn as zero, not skipped.** "We stopped spending on this in
  March" is the finding; joining February to June would draw a straight line through it.
- **The picker is built from the taxonomy, not from what the store contains**, so a category with
  nothing in it yet is still selectable and honestly shows a flat zero. That is how `Cabelo` looks
  today — an empty line is a real answer, and better than the category being invisible until its
  first haircut.

It follows the year filter and the meal-card toggle, so "All years" gives the full history.

### Data health

A short panel of non-destructive consistency checks, because these are the problems the charts
quietly average away rather than surface: **Category/Sub-category pairs outside the taxonomy**
(the whole pair, not just the category name — `Geral/Gasoleo` looks fine in a category chart while
splitting the sub-category chart in two), future-dated transactions, how much of your expense total
is still sitting in `Outros / Por Classificar`, and how many rows carry a manual review. Nothing is changed for you — it just tells you where the
numbers are softer than they look.

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
- **A manual entry you accidentally add twice** — the "Add a transaction by hand" form builds the
  same kind of hash, so clicking "Add" twice on identical values only ever produces one row.

What it *can't* catch: two genuinely different transactions that happen to share the same date,
description, and amount (rare, but possible — e.g. two identical €5 coffees on the same day would
hash identically and the second would be treated as a duplicate). If you need to start over
entirely and rebuild from a clean slate — e.g. after experimenting, or to double-check a batch of
files imports the way you expect — use `scripts/reset_store.py` (CLI) or "Clear all data"
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

**After changing a rule or the taxonomy**, bring the store in line with it. Dry run by default:
```bash
python3 scripts/recategorize.py            # what would change, and why
python3 scripts/recategorize.py --apply    # backs the store up first
```
It normalizes any pair that has fallen outside the taxonomy (via `LEGACY_ALIASES`, which is also
how a rename is carried out), converts unreviewed refunds still stored as income into negative
expenses, then re-runs today's rules over rows still awaiting an answer. It
never touches a row with `Reviewed At`, never demotes a real category into the review bucket, and
will refine a row sitting on a catch-all `Outros` sub-category if the rules can now name a specific
one **within the same category** — a regex may sharpen a human's answer, never overrule it.

**Starting over** — back up and empty the store, then rebuild it:
```bash
python3 scripts/reset_store.py
# then re-run seed_from_template.py / ingest_monthly.py as above
```
This never deletes your data outright — it renames the current `transactions.csv` to a
timestamped `transactions.backup-<timestamp>.csv` first, so resetting is always reversible.

**Adding a month never removes anything, and replacing needs your say-so.** "Add monthly file(s)"
(and the sidebar's "Import statement") only ever adds transactions it hasn't seen. Swapping the whole
history for a store file is in the Data tab's **Danger zone** as "Replace all history…": it tells you
how many transactions and which months will go, and only proceeds once you type `replace`. A bank
export picked there is added like a monthly file instead. The server backs on this: it refuses any
save that would remove a transaction already in `data/transactions.csv`, except that one confirmed
replace, and copies the old file to `data/transactions.backup-<timestamp>.csv` before writing it.

**Dashboard** — double-click **Finance Dashboard** on the Desktop (see below), or run:
```bash
python3 scripts/serve_dashboard.py          # --port 8792, --no-browser
```
A local HTTP server is required either way: under a plain `file://` origin the browser blocks the
dashboard's auto-load of `data/transactions.csv`, so it comes up empty. From there you can also pick "Add monthly
file(s) (xlsx/csv)" — selecting multiple files at once is fine — to categorize and merge new
months directly in the browser; the merged result is written back to `data/transactions.csv`
automatically, and "Download updated transactions.csv" remains as a manual export.
"Clear all data" resets the in-browser working copy to empty (it only touches what's loaded in
the tab — clearing also switches the automatic save off, so nothing on disk changes unless you
download afterward), so you can rebuild from scratch the same way — your saved review decisions
are kept and re-applied as the rows come back. The "Needs Review" panel lets you fix anything the rules
couldn't categorize, and the Transactions table's category / sub-category / review-state filters
let you audit and correct what they *did* categorize (see "Reviewing and correcting
categorizations"); rules you teach it and the review decisions and notes you record are both
saved into `data/` as you go, so future CLI ingestion picks them up without any button press (the
two Download buttons still work, and are the only route when there is no local server). Category and Method breakdowns sit side by side
for both Income and Expenses ("Analyzing by payment method" above), the "Monthly analysis" card
adds the month-by-month view ("Monthly spending analytics" below), and the "Exclude Cartão
Alimentação (meal card)" checkbox next to the year filter toggles the meal-allowance card in or
out of every chart and the stat tiles at once ("Excluding the meal-allowance card" above).

**Finding your way around the dashboard.** It is a set of tabs, kept in the address bar
(`#/month`, `#/review`, …) so a reload stays put and the browser's Back button works:

| Tab | What's there |
|---|---|
| **This month** | One sentence on where the month stands, the spending-pace chart with a projection to month end, the savings rate and comparison with your usual month, cards for anything waiting on you (reviews, unusual amounts, data health), the health meters and the month's biggest spends |
| **Review** | What the latest import left for you, and the Needs review queue |
| **Trends** | Totals, every chart over time, tracking one category, recurring commitments, month vs month and yearly totals |
| **Transactions** | The full table with its filters, and "Add a transaction by hand" |
| **Data** | Loading, adding, saving and clearing files, the Data health checks, and where each file lives |

The month switcher, the year filter, the meal-card toggle and the status line sit in the bar at the
top of every tab. The sidebar shows how many rows wait for review and what store is loaded, with an
"Import statement" button for the monthly export. On a phone the sidebar becomes a row of tabs.

**Adding a transaction manually** — for anything with no bank export at all (cash you received or
spent, a gift, etc.), use the "Add a transaction by hand" form at the top of the Transactions tab: pick Income or Expense, fill in
the date, amount, category, and any notes, and it's added straight into the store — same charts,
same table, and saved to `data/transactions.csv` the same way an upload is. It goes through the
same duplicate check as an upload, so double-clicking "Add" by accident on identical values won't
create two rows (see "Avoiding duplicates" below).

**Notebook** — `notebook/pipeline_walkthrough.ipynb` runs the same load → categorize → merge →
aggregate steps with explanations, useful as a reference or for ad-hoc analysis beyond what the
dashboard charts. Its last sections cover the opt-in peer rules, the spending analytics, and how a
review decision survives a full rebuild.

## The desktop shortcut

```bash
python3 scripts/install_desktop_shortcut.py            # install / repair
python3 scripts/install_desktop_shortcut.py --remove   # take it off the Desktop
```

This puts **Finance Dashboard.command** on your Desktop. Double-click it: a Terminal window opens
(that's the server — leave it open while you use the dashboard, close it or press Ctrl-C when
you're done), and the dashboard opens in your browser with today's data already loaded.

Two details make "always the most updated version" actually true, rather than merely likely:

- **The Desktop item is a symlink**, not a copy, pointing at `scripts/Finance Dashboard.command`.
  A copy would freeze today's launcher onto the Desktop and quietly keep running the old one after
  the project changes — exactly the staleness problem the shortcut exists to solve. (If you *move*
  the project folder, re-run the installer to repoint it.)
- **The server sends `Cache-Control: no-store`** on every response, so a browser that still has the
  dashboard open from last week can't serve you last week's HTML or last week's `transactions.csv`
  after you've ingested a new month.

It also binds to `127.0.0.1` only — the stock `python3 -m http.server` listens on every interface,
which puts your financial data on whatever network you're connected to — and walks up from port
8792 if that one is busy instead of failing.

On first launch macOS may ask whether you're sure you want to open it; choose Open. If you'd
rather not have a Terminal window, `python3 scripts/serve_dashboard.py --no-browser` works equally
well from a shell you already have open.

## Accessibility

The dashboard is fully keyboard-operable and readable with a screen reader:

- a skip link, real landmarks (`main`, `section` with labelled headings), and a visible focus ring
  on every interactive element;
- the file-picker buttons keep a focusable input (they were `display: none`, which silently made
  every "load a file" button unreachable by keyboard);
- the review panel is a real modal dialog — focus moves into it on open, is trapped inside it
  while it's open, returns to whatever opened it on close, and Escape closes it;
- the status line is an `aria-live` region, so loads, merges, saves and errors are announced;
- **every chart has a "View as table" disclosure with the same numbers**, and the canvas itself
  carries a one-line summary — a chart is invisible to a screen reader and to anyone who can't
  distinguish the series colours;
- direction is never carried by colour alone (each delta also says "more than"/"less than" in
  words);
- `prefers-reduced-motion` and `prefers-contrast` are both honoured, alongside the existing
  light/dark support.

## Keeping the plaintext store out of git

`.gitignore` is a convention, not a guarantee — `git add -f data/transactions.csv` bypasses it
silently, and this repo has a live remote. One forced add puts a year of real transaction data on
GitHub, in history, permanently; rewriting that out of a pushed repo is painful and never fully
reliable. So install the guard:

```bash
python3 scripts/install_git_hooks.py            # install
python3 scripts/install_git_hooks.py --remove
```

The pre-commit hook **refuses the commit** when any of these are staged:

- `data/*.csv`, `data/*.dec`, `data/review_decisions.json` — the plaintext store and your review
  notes;
- any `.xlsx` / `.xls` anywhere in the tree — raw bank exports;
- a `.ipynb` that still has cell outputs — see below;
- a stale `dashboard/rules.js`, since committing that ships a dashboard that categorizes
  differently from the CLI.

### The notebook is a hole `.gitignore` cannot cover

Every other rule above is about a file that should never be committed. The notebook is the
opposite: `notebook/pipeline_walkthrough.ipynb` **should** be tracked — the code and the
explanations are the point of it — but a notebook stores its outputs inside itself, so executing it
writes whatever it printed into a file that is already staged. No ignore rule can express "this
file, but only some of it".

This was a live leak, not a hypothetical: the committed notebook carried 17 lines of real
transaction descriptions before the guard existed.

Two things now close it, and both matter. The notebook **reads no real data at all** — it builds a
synthetic export and a synthetic store, so there is nothing personal for it to print. And the hook
still refuses any staged `.ipynb` carrying outputs, because "this notebook happens to be safe
today" is not a property you want a future edit to quietly revoke.

```bash
python3 scripts/strip_notebook_outputs.py            # clear them
python3 scripts/strip_notebook_outputs.py --check    # what the hook runs
```

Run the walkthrough locally as often as you like; clear it before committing.

**Those 17 lines are still in git history.** Removing them means rewriting history
(`git filter-repo` or similar) and force-pushing — worth doing if the remote is public, and worth
deciding deliberately rather than by default.

It also *warns* (without blocking) when `data/transactions.csv` is newer than
`data/transactions.csv.enc`, i.e. you have changes that exist nowhere in encrypted form. The hook
runs on plain `python3` with no third-party imports, so it works regardless of whether the venv is
active, and it distinguishes "the rules are stale" from "the checker couldn't run" rather than
blaming the former for the latter.

Current state of this repo: `data/transactions.csv` is correctly ignored and **has never been
committed** — no CSV appears anywhere in history. The notebook is clean as of now; its history is
not (see above).

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
- **Replace all history with an encrypted file (.enc)** — in the Data tab's Danger zone: decrypts
  `transactions.csv.enc` and, after you confirm, uses it in place of the current history
- **Download encrypted (.enc)** — encrypts the current in-memory store and downloads it

Both sides (Python and JavaScript) use the exact same format — `salt(16 bytes) || nonce(12 bytes)
|| AES-256-GCM ciphertext`, same PBKDF2 iteration count — so a file encrypted by one decrypts
cleanly on the other.

This protects the file *at rest* (on disk, in git history, in backups). It does not protect data
while a script or the dashboard has it open and decrypted in memory — that's a different threat
model (full-disk encryption / OS-level access control) that this project doesn't attempt to solve.
