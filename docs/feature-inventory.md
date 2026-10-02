# Feature inventory: preservation checklist

Everything the dashboard and its server do today, so a redesign can prove it lost nothing. Built
from section 2 of [redesign-brief.md](redesign-brief.md), then extended by reading
`dashboard/index.html`, `scripts/serve_dashboard.py` and `README.md` end to end. Items marked
*(added)* were missing from the brief's list.

How to use it: after each phase, walk the whole list in the browser on **synthetic data** (never
`data/`) and tick each item. An item that can't be ticked gets a note saying what is still wrong.
"Where" says which view holds the item once the tabbed shell exists.

Element ids are listed because the redesign moves DOM rather than rewriting it: if an id still
exists and its handler still fires, the feature survived.

---

## Data and persistence

- [ ] **Auto-load on start.** `tryAutoLoad()` fetches `../data/transactions.csv`; on failure the
  status line explains why (file:// origin, no server) and points at the Load button and the
  desktop shortcut.
- [ ] **Load order on start** *(added)*: review memory, then overrides, then the store, so saved
  decisions are re-applied on arrival rather than one render later.
- [ ] **Load transactions.csv from a file** (`#file-store`). Resets the session's added/duplicate
  counters and disables `#btn-download`.
- [ ] **Load and decrypt `.enc`** (`#file-store-enc`): passphrase prompt, Web Crypto
  AES-256-GCM + PBKDF2-SHA256 (200,000 iterations), `salt[16] || nonce[12] || ciphertext`, same
  format as `finance_tracker/crypto.py`. A wrong passphrase gives a status-line error, not a crash.
- [ ] **Add monthly file(s)** (`#file-monthly` inside the `#btn-monthly` label): xlsx, xls, csv,
  several at once, processed in order into the same store. Hash dedup within a file, across the
  files in one pick, and against the store. Status reports per file (`+added / dup`, or
  `FAILED — reason`), the session totals, and how many rows were restored from review memory.
  The input is cleared afterwards so the same file can be picked again.
- [ ] **`#btn-monthly` enabled state** *(added)*: starts with the `disabled` class and is enabled
  by a successful load, by Clear, and by a manual entry. (Pre-existing quirk: with no store on disk
  and no manual entry yet, the label is not clickable, though its input is still reachable by
  keyboard. Kept as is.)
- [ ] **Clear all data** (`#btn-clear`): confirm dialog naming the row count, promising nothing on
  disk changes, and saying saved review decisions are kept and re-applied. Clearing disarms the
  automatic store save and cancels a pending one.
- [ ] **Downloads**, each with its enable logic:
  - `#btn-download` (CSV, sorted by year, month, date): enabled after an upload, a manual entry or
    a review save; disabled by a fresh load and by Clear.
  - `#btn-download-enc`: passphrase + confirmation prompt, refuses on mismatch; enabled once a
    store is loaded, disabled by Clear.
  - `#btn-download-overrides`: enabled once a rule is taught or unsaved local rules are found.
  - `#btn-download-reviews`: enabled once any decision exists (loaded, harvested or new). Clears
    the "unsaved" flag.
- [ ] **Save to `data/` through the server** (`saveToDataFolder`, HTTP PUT): reviews, overrides
  and the store. Remembers when the server isn't there and stops trying.
- [ ] **Store save guards** *(added)*: armed only after a store has been loaded, never writes an
  empty store, debounced 400 ms so a batch is one write, disarmed by Clear.
- [ ] **localStorage fallback** for reviews and overrides, with a status-line warning when the
  browser refuses to store.
- [ ] **Merge of file and localStorage reviews** by `reviewed_at`, newest wins (`mergeDecisions`).
- [ ] **`__deleted` tombstones** so an undone review isn't resurrected by the server's merge;
  cleared after a successful save.
- [ ] **Harvest reviews already in the store's columns** into review memory *(added)*
  (`harvestReviewsFromStore`).
- [ ] **Re-apply saved decisions** after every load and ingest (`applyReviewsToStore`), mapping
  legacy pairs through `LEGACY_ALIASES` (`resolvePair`); an unplaceable decision keeps its note
  and timestamp but not its category, with a console warning.
- [ ] **Re-run the categorizer over queued rows on load** *(added)* (`applyOverridesToStore`), so
  a new override or rule reaches rows already loaded. Never touches a row with `Reviewed At` or a
  settled `Outros` row.
- [ ] **Overrides: file plus localStorage layering** (`tryAutoLoadOverrides`), local entries
  replacing file entries with the same identity, and the **unsaved-rules warning** naming how many
  exist only in this browser.
- [ ] **Leave-page warning** *(added)* (`beforeunload`): unsaved reviews, unsaved overrides, or a
  store that is still waiting on its debounce or has no server to save to.
- [ ] **Server: single instance per repo** (`/__finance_dashboard__` identity endpoint answering
  `app` and `root`); a second launch opens the running one and exits.
- [ ] **Server: port walk-up** from 8792, 20 attempts, only past ports held by something else.
- [ ] **Server: PUT allowlist** (`SAVEABLE`: the three data files), 32 MB cap, 400 on bad
  Content-Length, 403 on anything else.
- [ ] **Server: atomic writes** (temp file + `os.replace`).
- [ ] **Server: merge, not replace,** for the JSON files: reviews union by id with newer
  `reviewed_at` winning and `__deleted` applied after; overrides union by keywords + type + peer,
  incoming wins.
- [ ] **Server: localhost only** (`127.0.0.1`) and **quiet logging** *(added)*: only 4xx/5xx and
  saves are printed.
- [ ] **Server: store summary on launch** *(added)* (`describe_store`): row count and last
  modified, or a pointer to the `.enc` / to adding files.

## Filters

- [ ] **Year filter** (`#year-filter`): "All years" plus every year in the store; keeps the
  selection across re-renders. Applies to tiles, the four breakdown charts, both trend charts,
  Track one category, Month vs month, Yearly analysis and the Transactions table.
- [ ] **Exclude meal card** (`#exclude-meal-card`): drops `Cartão Alimentação` rows from every
  chart, tile, table and the analysis card.
- [ ] **Analysis card ignores the year filter** (`analysisRows`), so the baseline can reach across
  the year boundary.
- [ ] **Not filtered by year** *(added)*: the Needs Review queue and Data health always look at the
  whole store.

## Manual entry

- [ ] **"Add a transaction manually"** (`#mf-type`, `#mf-date`, `#mf-amount`, `#mf-category`,
  `#mf-subcategory`, `#mf-method`, `#mf-notes`, `#mf-add`). Date defaults to today in local time,
  method to Dinheiro.
- [ ] **Taxonomy pickers**: category list follows the type; sub-category list follows the
  category, so an off-taxonomy pair can't be expressed. `assertValidPair` as a last check.
- [ ] **Validation** *(added)*: a date is required, the amount must be above zero.
- [ ] **Duplicate-safe**: same hash as an upload; a second identical add is refused with a status
  message.
- [ ] **After adding** *(added)*: clears amount and notes, enables download, monthly upload and
  Clear, re-renders.

## Totals

- [ ] **Stat tiles** (`#tiles`): Income, Expenses (investments excluded), Net, Savings /
  Investments, with the year and meal-card filters applied.

## Review

- [ ] **Needs Review queue** (`#review-card`, `#review-count`, `#review-empty`, `#review-body`,
  `#review-table-wrap`, `#review-toolbar`): every unreviewed `Outros / Por Classificar` row,
  income and expense, newest first, with a Type column. Empty state explains why some `Outros`
  rows are not in it.
- [ ] **"Show auto-classified, unchecked rows"** (`#btn-audit-auto`): sets the review-state filter
  to "auto", clears the search and brings the Transactions table into view.
- [ ] **Batch select** (`#review-select-all`, per-row `.review-select`, `#btn-review-selected`,
  `#review-selected-count`, `#review-selection-hint`): indeterminate state, selection dropped for
  rows that leave the queue. "Review N selected together" saves categories and notes and **remembers
  no rule**.
- [ ] **Review panel** (`#review-panel`, `#review-panel-backdrop`, `#rp-*`) as a modal dialog:
  focus moves in, Tab is trapped, Escape and the backdrop close it, focus returns to the opener.
- [ ] **Three states**: Complete (queued, empty picker), Correct (auto-classified, pre-selected),
  Edit (reviewed, pre-selected, shows when).
- [ ] **Type banner** (`#rp-type-banner`, `#rp-type-badge`, `#rp-type-explainer`): income /
  expense / mixed, with the total.
- [ ] **Taxonomy pickers** (`#rp-category`, `#rp-subcategory`, `#rp-subcategory-hint`, `#rp-method`).
- [ ] **"What was it?" note** (`#rp-review-note`); a derived row opens with an empty box instead
  of its provenance marker *(added)*.
- [ ] **Apply to siblings** (`#rp-siblings-field`, `#rp-apply-siblings`, `#rp-siblings-label`,
  `#rp-siblings-hint`, `#rp-siblings-list`): exact normalized description, same type, still queued;
  pre-ticked for merchants, unticked for named transfers (caution rail), not offered for unnamed
  transfers (explained); per-row ticks; **select all / none and tally** (`#rp-siblings-all`,
  `#rp-siblings-none`, `#rp-siblings-tally`); the master box follows the rows. Siblings get the
  pair, a `↳ auto-applied` marker instead of the note, `derived_from`, and the method only if it
  matched the source row's original method.
- [ ] **Merchant "Remember for future transactions like this"** (`#rp-remember-field`,
  `#rp-remember`, `#rp-keyword`) with an editable, comma-separated keyword, prefilled from the
  description.
- [ ] **Opt-in peer rule** (`#rp-remember-peer-field`, `#rp-remember-peer`, `#rp-peer-keyword`,
  `#rp-peer-hint`): only for MBWay / Transferência rows, off by default, prefilled with the
  counterparty, saved with `peer: true` and **no Method**.
- [ ] **Override upsert** *(added)*: re-teaching the same keywords replaces the rule; after a rule
  is saved, matching queued rows are re-categorized and counted in the status line.
- [ ] **Refusal of `Por Classificar`** on save, and of a missing category.
- [ ] **Undo for bulk changes**: sibling apply and batch review both put an "Undo (N)" button on
  the status line that restores every touched field and forgets new decisions.
- [ ] **Batch panel specifics** *(added)* (`#rp-batch-field`, `#rp-batch-label`, `#rp-batch-list`):
  hides single-row fields and all "remember" offers, refuses a mixed income/expense selection,
  defaults Method to "Leave each transaction's own method".
- [ ] **Cancel** (`#rp-cancel`) and **Save** (`#rp-save`).
- [ ] **`reviewed` / `auto` badges** in the Transactions table, `auto` dashed.

## Analysis

- [ ] **Month selector** (`#analysis-month`): newest first; defaults to the newest month that is
  not in the future; keeps the selection across re-renders.
- [ ] **Baseline selector** (`#analysis-baseline`): 3, 6 or 12 previous months, excluding the
  month being judged.
- [ ] **Health meters** (`#analysis-meters`): Spent and Kept as a share of income, thresholds
  70 / 90 and 10 / 30, icon and word for each band, ticks on the track, `role="img"` label, a
  plain sentence when the month has no income.
- [ ] **Stats with deltas in words** (`#analysis-stats`): Spent, vs previous month, vs N-month
  average, Income, Savings rate, Per day (with the month-end projection while the month runs).
- [ ] **Analysis note** (`#analysis-note`): projection sentence for a running month, otherwise the
  savings-exclusion note or "not enough history".
- [ ] **Pacing chart** (`#chart-pacing`): cumulative spend by day, the month's line stopping at
  today, the baseline average dashed, plus its explanatory caption. *(Pre-existing gap: it has no
  "View as table".)*
- [ ] **Category spend by month** (`#chart-cat-trend`, `#cat-trend-table`), stacked.
- [ ] **Top sub-categories this month** (`#chart-top-sub`, `#top-sub-table`), single hue.
- [ ] **Track one category over time** *(added)* (`#focus-pick`, `#focus-mode`, `#focus-stats`,
  `#chart-focus`, `#focus-note`, `#focus-table`): picker built from the taxonomy, three modes
  (amount, share, running total), zero months drawn, follows the year and meal-card filters,
  re-renders only itself on change.
- [ ] **Major spends & outliers** (`#biggest-body`, `#biggest-note`, `#outlier-count`): top 12 of
  the selected month, outliers first; outlier = at least 2.5× its sub-category median over €25,
  needing 3+ sightings; "no baseline" otherwise; share of month.
- [ ] **Recurring commitments** (`#recurring-body`, `#recurring-note`): whole loaded history,
  3+ months within 15% of the median, typical, months, per year, last seen.
- [ ] **Month vs month** *(added)* (`#mom-body`, `#mom-note`): newest first, income, spending, net,
  kept, change in words; range and median in the note.
- [ ] **Yearly analysis** *(added)* (`#yearly-body`, `#yearly-note`): per year, with part-year
  years called out.
- [ ] **Data health** (`#health-list`): off-taxonomy pairs (top 6), future-dated rows, share still
  unclassified (warning from 15%), reviewed count split into direct and auto-applied plus decisions
  in memory and the unsaved hint, missing payment method *(added)*. Marker plus a screen-reader
  word for each check.
- [ ] **Charts**: Income vs Expenses by month (`#chart-trend`, `#trend-table`), Net by month
  (`#chart-net`, `#net-table`), Expense and Income categories (`#chart-expense-cat`,
  `#expense-cat-table`, `#chart-income-cat`, `#income-cat-table`), Expense and Income methods
  (`#chart-expense-method`, `#expense-method-table`, `#chart-income-method`,
  `#income-method-table`), each with "View as table".
- [ ] **One colour per category name** *(added)* (`colorFor`): fixed nine-hue order, `Outros` on
  the neutral, unknown categories on their own neutral; same colour in every chart.
- [ ] **Every canvas has a one-line `aria-label` summary** *(added)* (`describeChart`).

## Transactions

- [ ] **Table** (`#tx-body`), newest first, capped at 500 rows with a message saying so.
- [ ] **Search** (`#search-box`) over notes, category, sub-category and review notes.
- [ ] **Filters**: type (`#type-filter`, also narrows the category lists), category
  (`#cat-filter`, from the taxonomy), sub-category (`#subcat-filter`, re-stocked from the
  category), review state (`#review-filter`: awaiting an answer, auto-classified unchecked,
  reviewed by hand).
- [ ] **Clear filters** *(added)* (`#btn-clear-filters`).
- [ ] **Caption with the filtered total** (`#tx-count`).
- [ ] **"Review" / "Edit review" on any row**, with a screen-reader description of the row.
- [ ] **`reviewed` / `auto` badges** and the review note under the description.

## Accessibility and theming

- [ ] **Skip link** to the main content.
- [ ] **Landmarks**: `main`, labelled `section`s.
- [ ] **Visible focus ring** on every interactive element, including the file-picker labels
  (`:focus-within`).
- [ ] **File inputs stay focusable** (hidden, not `display: none`).
- [ ] **Modal review panel** behaviour (see Review).
- [ ] **`aria-live` status line** (`#status-line`), warning style, inline Undo button.
- [ ] **Direction in words**, not colour alone, on every delta.
- [ ] **`prefers-reduced-motion`**, **`prefers-contrast: more`**, **light and dark**, plus a
  `data-theme` attribute override *(added)*.

## Launch

- [ ] **Desktop shortcut** is a symlink to `scripts/Finance Dashboard.command`.
- [ ] **No-store headers** on every response.
- [ ] **`--no-browser`** and **`--port`** flags.
