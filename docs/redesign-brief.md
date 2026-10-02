# Brief: Personal Finance Dashboard redesign

This is a working brief for Claude Code. Read it fully before changing anything, then work
phase by phase. Each phase ends with a verification step and its own commit.

The goal is to move `dashboard/index.html` from one long scrolling page to a tabbed app shell,
add a small set of planning and self-review features, and **lose nothing that works today**.
It stays a localhost dashboard served by `scripts/serve_dashboard.py`.

---

## 0. Ground rules (non-negotiable)

1. **No feature is removed.** Every control, panel, chart, table, keyboard behaviour and save
   path that exists today must exist afterwards, in a new place if needed. Section 2 is the
   inventory; extend it with anything you find that it misses.
2. **Move DOM, don't rewrite it.** Existing sections are wrapped into views and moved, keeping
   every element `id`, so the existing JavaScript keeps working. Only rewrite a handler when the
   new design requires it, and say why in the commit message.
3. **Stays local and offline.** Served from `127.0.0.1` only, `Cache-Control: no-store`, no CDN
   calls. New third-party files go in `dashboard/vendor/`. No build step, no framework, no npm
   dependency at runtime. Plain HTML, CSS and JS.
4. **Python and JS stay in agreement.** Anything computed in both places (taxonomy, rules,
   analytics, the new budget and projection logic) must give identical results. `dashboard/rules.js`
   is generated, never hand-edited: run `python3 scripts/generate_dashboard_rules.py` after
   touching `taxonomy.py`, `categorize.py` or `schema.py`.
5. **Privacy invariants hold.** No plaintext financial data in git. Every new data file that holds
   personal amounts or notes is gitignored, added to the pre-commit block list in
   `scripts/install_git_hooks.py`, and, if the dashboard writes it, added to `SAVEABLE` in
   `serve_dashboard.py`. Run `python3 scripts/strip_notebook_outputs.py` before committing.
6. **Accessibility is not regressed.** Keep: the skip link, landmarks, the visible focus ring,
   the modal review panel (focus in, focus trapped, focus returned, Escape closes), the `aria-live`
   status line, "View as table" on every chart, direction stated in words and not by colour alone,
   `prefers-reduced-motion`, `prefers-contrast`, light and dark themes.
7. **Never touch real data** in `data/` while developing. Use the synthetic data the notebook
   builds, or a fixture under `tests/fixtures/`.

---

## 1. Context

The repo is a personal finance pipeline: `finance_tracker/` (Python library), `scripts/` (CLI,
encryption, local server, git hooks, desktop shortcut), `dashboard/index.html` (the UI),
`notebook/` (walkthrough on synthetic data), `docs/` (design docs). Read `README.md`,
`docs/categorization.md` and `docs/knowledge-placement.md` before starting: they explain why the
review ladder, overrides and peer rules work the way they do, and the new features must fit that
ladder, not bypass it.

The ladder, top wins: **your review** > merchant override > built-in rule > peer rule > honest
fallback (`Outros / Por Classificar`, or `Transferências Pessoais`). A row with `Reviewed At` is
settled and nothing may overwrite it.

---

## 2. Feature inventory: preservation checklist

Before Phase 1, grep `dashboard/index.html`, `serve_dashboard.py` and `README.md` and turn this
list into `docs/feature-inventory.md`, adding anything missing. After each phase, walk the whole
list in the browser and tick it.

**Data and persistence**
- Auto-load `../data/transactions.csv` on start, with the status message on failure.
- Load `transactions.csv` from file (`#file-store`).
- Load and decrypt `.enc` client-side with a passphrase (`#file-store-enc`), Web Crypto,
  same format as `finance_tracker/crypto.py`.
- Add monthly file(s), xlsx/xls/csv, multiple at once (`#file-monthly`, `#btn-monthly`), with
  hash dedup within and across files and against the store.
- Clear all data (`#btn-clear`) with its confirm text; review decisions kept and re-applied.
- Downloads: `#btn-download` (CSV), `#btn-download-enc`, `#btn-download-overrides`,
  `#btn-download-reviews`, with their enable/disable logic.
- Save to `data/` through the server's PUT (`saveToDataFolder`), localStorage fallback,
  merge of file and localStorage by `reviewed_at`, the `__deleted` marker for undo.
- Overrides: load from file plus localStorage layering (`tryAutoLoadOverrides`), unsaved-rules
  warning.
- Server: single instance per repo (identity endpoint), port walk-up, PUT allowlist, atomic
  writes, merge-not-replace for the JSON files.

**Filters**
- Year filter (`#year-filter`) on charts and tables.
- Exclude meal card (`#exclude-meal-card`) on every chart, tile and the analysis card.
- The analysis card's own month selector ignores the year filter, so the baseline can reach
  across the year boundary. Keep that behaviour.

**Manual entry**
- "Add a transaction manually" form (`#mf-*`), taxonomy pickers, duplicate-safe.

**Totals**
- Stat tiles (`#tiles`).

**Review**
- Needs Review queue (`#review-card`, `#review-count`, `#review-empty`, `#review-body`).
- "Show auto-classified, unchecked rows" (`#btn-audit-auto`).
- Batch select and "Review N selected together" (`#review-select-all`,
  `#btn-review-selected`), which remembers no rule.
- Review panel (`#review-panel`, `#review-panel-backdrop`, all `#rp-*`): three states
  (complete / correct / edit), type banner, taxonomy pickers, "What was it?" note,
  apply-to-siblings with per-row ticks, select all/none and tally, merchant "Remember for future
  transactions like this" with editable keyword, opt-in peer rule (off by default, never sets
  Method), refusal of `Por Classificar` on save, Undo for bulk changes.

**Analysis**
- Monthly analysis: month and baseline selectors, health meters, stats with deltas in words,
  pacing chart, category-by-month chart, top sub-categories, recurring commitments, biggest
  expenses, outliers (median-based, €25 floor), analysis note.
- Data health panel: off-taxonomy pairs, future-dated rows, share still unclassified, reviewed
  count.
- Charts: income vs expenses by month, net by month, expense and income categories, expense and
  income methods, each with "View as table".

**Transactions**
- Table with search (notes, review notes, category), type, category, sub-category and review-state
  filters, caption with the filtered total, "Review" on any row, `reviewed` / `auto` badges.

**Launch**
- Desktop shortcut (symlink), no-store headers, `--no-browser`.

---

## 3. Phase 0: fix known bugs first (one commit each)

Verify each before fixing; these came from a code review of excerpts, not a full run.

1. **Two `median` functions in `index.html`.** One guards the empty array and one doesn't; the
   later declaration wins. Keep one, with the guard, returning `0` (or `null` where callers
   expect "no data") for an empty array. Check every caller.
2. **Recurring detection groups by sub-category.** Two subscriptions in one sub-category
   (€8.99 and €6.99) are reported as one ~€8 charge, halving the annual cost. Group by a
   normalized merchant key (normalized `Notes`, or the counterparty for transfers) within each
   sub-category. Also estimate cadence: monthly, or yearly when a charge repeats about every
   12 months, and annualize accordingly. Mirror in `overview.detect_recurring`.
3. **Refunds.** If `Type` is derived from the sign of the amount, a store refund becomes Income
   and inflates both income and spending. Confirm against a real export shape (synthetic copy).
   If confirmed, add a `Reembolso` handling: a positive amount whose description matches a
   refund pattern, or that a user marks as a refund in the review panel, is netted against the
   category of the purchase instead of counted as income. Add it to the taxonomy properly and
   regenerate `rules.js`. If not confirmed, document why in `docs/categorization.md`.

---

## 4. Phase 1: visual redesign and tab navigation

### 4.1 Design tokens

Replace the current palette and type with these. Keep everything as CSS custom properties on
`:root`, with a dark set under `@media (prefers-color-scheme: dark)`.

| Token | Light | Use |
|---|---|---|
| `--ground` | `#EEF1EF` | Page background |
| `--rail` | `#F7F9F8` | Sidebar background |
| `--surface` | `#FFFFFF` | Cards |
| `--ink` | `#16211D` | Primary text |
| `--muted` | `#52605A` | Secondary text (meets 4.5:1 on surface) |
| `--line` | `#D5DCD8` | Card borders, inputs |
| `--hairline` | `#E3E8E5` | Gridlines, row dividers |
| `--accent` | `#2A5A9C` | Primary actions, "spent" series, links |
| `--accent-soft` | `#DCE6F2` | Active nav item |
| `--over` | `#B4530A` | Over budget, review count badge, warnings |
| `--done` | `#5E7D6E` | Paid fixed costs |
| `--ai` | `#7A4FA0` | AI suggestion tag only |
| `--baseline` | `#9AA6A0` | Baseline/average series |

Derive the dark set yourself (same hues, adjusted lightness), and check contrast. Map the
existing `--series-*`, `--status-*`, `--good`, `--warn`, `--focus` tokens onto these rather than
deleting them, so nothing that references them breaks.

**Type:** Public Sans (400, 500, 600, 700), **self-hosted** as woff2 in
`dashboard/vendor/fonts/` with its OFL licence file, `font-display: swap`, falling back to
`system-ui, -apple-system, "Segoe UI", sans-serif`. If you can't download the font files, use the
system stack and say so. All numbers use `font-variant-numeric: tabular-nums`. Sentence case
everywhere; remove the uppercase labels on `.stat .label`.

Shape: cards 14px radius, 1px `--line` border, no shadows. Buttons and nav items at least 44px
tall. No emoji in the UI: replace the emoji on buttons with small inline stroke SVG icons or plain
text.

### 4.2 The app shell

```
┌──────────────┬────────────────────────────────────────────────────────────┐
│ Finanças     │  ‹  September 2026  ›   Day 21 of 30     [Year ▾] [□ Meal card] │
│              │  status line (aria-live)                                    │
│ This month   ├────────────────────────────────────────────────────────────┤
│ Review   (26)│                                                            │
│ Trends       │                 active view                                │
│ Transactions │                                                            │
│ Data         │                                                            │
│ (Goals)      │                                                            │
│              │                                                            │
│ ┌──────────┐ │                                                            │
│ │Store: enc│ │                                                            │
│ │Last impt │ │                                                            │
│ │[Import]  │ │                                                            │
│ └──────────┘ │                                                            │
└──────────────┴────────────────────────────────────────────────────────────┘
```

- **Sidebar** (`<nav aria-label="Main">`, 232px): wordmark, nav links with `aria-current="page"`
  on the active one, a red-orange count badge on Review (same number as `#review-count`), and a
  bottom box with store status (encrypted or plaintext, last modified, row count) and an
  "Import statement" button that triggers `#file-monthly`.
- **Top bar** (global, every view): month switcher with previous/next buttons (labelled for
  screen readers), "Day X of N" for the running month, the year filter and the meal-card toggle,
  and the status line. The status line moves here so it's visible from every tab.
- **Month switcher** drives `#analysis-month` (keep the select, synced both ways, visually hidden
  or placed inside the This month view). The year filter keeps its current scope.
- **Below 820px**: the sidebar becomes a horizontal, scrollable tab bar under the top bar; all
  grids become one column.

### 4.3 Tabs: hash router

Implement views as `<section class="view" id="view-month" hidden>` etc., switched by a tiny router.
The URL hash keeps the tab on reload and makes the browser back button work.

```js
// Minimal, no framework. Views are existing DOM moved into wrappers.
const VIEWS = ["month", "review", "trends", "transactions", "data"];  // + "goals" in Phase 4

function showView(name) {
  if (!VIEWS.includes(name)) name = "month";
  for (const v of VIEWS) {
    const el = document.getElementById(`view-${v}`);
    el.hidden = v !== name;
  }
  document.querySelectorAll("nav[aria-label=Main] a[data-view]").forEach(a => {
    if (a.dataset.view === name) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  // Charts created inside a hidden container have zero size. Resize the visible ones.
  Object.values(charts).forEach(c => { if (c && c.canvas.offsetParent !== null) c.resize(); });
  // Move focus to the view heading so screen-reader and keyboard users land in the new view.
  document.querySelector(`#view-${name} h1, #view-${name} h2`)?.focus({ preventScroll: true });
}
window.addEventListener("hashchange", () => showView(location.hash.replace("#/", "")));
showView(location.hash.replace("#/", ""));
```

Nav links are real links: `<a href="#/review" data-view="review">`. Give each view heading
`tabindex="-1"`. Keep the skip link pointing at the active view's heading. Check that rendering
functions still work when their view is hidden, and that `renderAll()` doesn't depend on
layout measurements of hidden elements.

### 4.4 Where every existing section goes

| Existing section | New home |
|---|---|
| Data source toolbar (8 buttons) | **Data** view, grouped: "Load" (CSV, .enc), "Add" (monthly files), "Save and export" (4 downloads), "Danger zone" (clear). The sidebar's Import button also triggers monthly upload. |
| Year filter, meal-card toggle | Top bar (global) |
| Status line | Top bar (global) |
| Add a transaction manually | **Transactions** view, collapsed `<details>` above the table, labelled "Add a transaction by hand" |
| Totals tiles | **Trends** view, top |
| Needs Review queue + batch toolbar | **Review** view |
| Monthly analysis card | Split: hero, meters, stats, pacing chart, biggest expenses and outliers in **This month**; category-by-month and top sub-categories in **Trends** |
| Recurring commitments | **Trends** (and feeds the projection, Phase 2) |
| Data health | Full panel in **Data** view; a one-line alert card on **This month** when there are issues |
| Income vs expenses, net, category and method charts | **Trends** |
| Transactions table | **Transactions** |
| Review panel (modal) | Unchanged, global, outside the views |

### 4.5 This month view

```
┌───────────────────────────────────────────────┬────────────────────────┐
│ €1,184 spent by day 21. At this pace          │ Savings rate so far    │
│ September lands near €1,546, which is €146    │ 31%                    │
│ over plan.                                    ├────────────────────────┤
│                                               │ Against 3-month avg    │
│  [pacing chart: spent (solid fill), projection│ +6%                    │
│   (dashed), plan (thin solid), 3-month avg    ├────────────────────────┤
│   (dotted), "today" marker]                   │ Fixed costs still due  │
│                                               │ €24                    │
│  legend in words                              ├────────────────────────┤
│                                               │ A simple daily pace    │
│                                               │ would say €1,691       │
└───────────────────────────────────────────────┴────────────────────────┘
┌ Budgets ─────────────────────────────── €1,122 of €1,300 · Edit budgets ┐
│ Supermercado    ████████░░░░   €214 of €260     €46 left                │
│ Restaurantes    ████████████   €186 of €150     €36 over   (orange)     │
│ ...                                                                     │
└─────────────────────────────────────────────────────────────────────────┘
┌ 26 to review ──────┐ ┌ 2 unusual amounts ─┐ ┌ 1 data health issue ┐
│ ... Open review    │ │ ... See both       │ │ ... Fix dates       │
└────────────────────┘ └────────────────────┘ └─────────────────────┘
  Health meters and the stats grid sit below, then biggest expenses.
```

- **Hero sentence** is generated: spent so far, projected landing, and the difference against the
  plan in euros and in words ("over plan" / "under plan"). For a finished month: "September
  closed at €X, €Y under plan." With no budgets set, compare with the baseline instead.
- **Pacing chart** extends the existing `renderPacingChart`: add a cumulative plan line (Phase 2)
  and a dashed projection segment from today to month end. Draw the "today" marker with a small
  inline Chart.js plugin, not a new vendored plugin. Keep `describeChart` and "View as table".
- **Right column**: four figures. The fourth explains the projection method only when it differs
  noticeably from a simple daily pace (more than 5%).
- **Budget rows**: name and category, a bar where the track is the budget, amount "€X of €Y",
  and a status in words ("€46 left", "€36 over", "Paid", "€24 still due"). Over-budget uses
  `--over` and the word "over", never colour alone.
- **Alert cards** link to the right tab (`#/review`, `#/transactions` with the outlier filter,
  `#/data`). Hide a card when its count is zero.

### 4.6 Review view

```
Review the September import
144 came in. 118 were filed by your rules and saved reviews. These need a decision.

┌──────────────────────────────────────────────┐ ┌ How the rules are doing ┐
│ 18 filed by your rules this import            │ │ Filed automatically 82% │
│ [Show them]  [Spot-check 5]                   │ │ Corrections to rules  6 │
├──────────────────────────────────────────────┤ │ Suggestions accepted    │
│ Suggestions to check (only when available)    │ │ Rules unused 6 months 4 │
│  card per row: description, date, amount,     │ │ Auto-filed, unchecked14 │
│  "Suggested: Cat / Sub" + source tag, "Why"   │ └─────────────────────────┘
│  evidence lines, [Change category] [Accept],  │
│  optional "remember" checkbox, off by default │
├──────────────────────────────────────────────┤
│ Needs review (existing queue table + batch)   │
└──────────────────────────────────────────────┘
```

- **Deviation from the mockup, on purpose:** the mock had "Accept all 18" for rule-filed rows.
  Don't build that. Mass-stamping `Reviewed At` would make "reviewed" mean "clicked a button" and
  would lock those rows against future rule fixes. Instead: "Show them" opens Transactions
  filtered to this import + "Auto-classified, unchecked", and "Spot-check 5" (Phase 2).
- **Suggestion cards** appear only when suggestions exist (Phase 2 / Phase 3). Accept opens no
  panel: it saves a review with the suggested pair. "Change category" opens the existing review
  panel pre-filled. Undo is available inline after accepting.
- The existing queue table, batch selection and the review panel stay exactly as they are,
  restyled.

### 4.7 Trends, Transactions, Data views

Restyle only. Trends: tiles, then a two-column chart grid (category-by-month full width), then
recurring commitments. Transactions: the manual-entry `<details>`, filters in one row, the table.
Data: the grouped file actions, encryption, data health panel, and a short "Where your data lives"
note (paths of the files in `data/`, what is encrypted, what is gitignored).

**Phase 1 done when:** every item in `docs/feature-inventory.md` is ticked, the router works with
back/forward and reload, all charts render at the right size after switching tabs, keyboard-only
use works across all views, and light/dark both pass contrast.

---

## 5. Phase 2: planning and self-review features

### 5.1 Budgets

- New file `data/budgets.json` (gitignored, blocked by the hook, added to `SAVEABLE`):

```json
{
  "version": 1,
  "monthly": [
    { "category": "Casa", "sub": "Renda", "amount": 350, "fixed": true },
    { "category": "Alimentação", "sub": "Supermercado", "amount": 260 },
    { "category": "Alimentação", "sub": null, "amount": 400 }
  ],
  "months": { "2026-12": [ { "category": "Lazer", "sub": null, "amount": 300 } ] }
}
```

  `sub: null` budgets a whole category. A month entry overrides the default for that line in that
  month only. `fixed: true` marks costs expected once early in the month (used by the plan line and
  the projection). Pairs must exist in the taxonomy; reject anything else on save.
- `finance_tracker/budgets.py` with `load_budgets`, `budget_for_month`, `budget_vs_actual(df, year,
  month)`. JS mirror in the dashboard. Same results, tested (5.6).
- "Edit budgets" opens a modal (same accessibility pattern as the review panel) with taxonomy
  pickers. Offer "Suggest from history": pre-fill each line with its 3-month median, the user edits
  and saves. Nothing is saved without a click.
- Health meter thresholds (70/90 and 10/30) become configurable in the same file under
  `"meters"`, defaulting to today's values.

### 5.2 Month-end projection

Replace `perDay × totalDays` in both `computeMonthlyAnalysis` and `overview.project_month_end`:

```
fixed_paid      = this month's spending on budget lines marked fixed + recurring charges already seen
fixed_remaining = recurring charges not yet seen this month whose typical day is after today
variable_spent  = spent - fixed_paid
variable_pace   = variable_spent / elapsed_days
projected       = spent + fixed_remaining + variable_pace × remaining_days
```

Return both the new projection and the simple one so the UI can explain the difference. A
finished month's projection is just its total.

### 5.3 Self-review: "How the rules are doing"

This is the core of the project's direction: the dashboard should tell its owner what to fix
next. All metrics are computed from data the store already has; **no schema change to
`transactions.csv`**.

First, add an explain mode to categorization that returns which rule produced the answer, without
changing any output: `categorize.explain(description, type, overrides) -> (category, sub, method,
source)` where `source` is `override:<keyword>`, `peer:<name>`, `rule:<pattern id>` or `fallback`.
Generate pattern ids into `rules.js`. Parity-test it (5.6).

Metrics, per import (`Source File`) and per month, last 3 imports shown:

| Metric | Definition |
|---|---|
| Filed automatically | Share of rows where `explain` returns anything other than `fallback`. Show the trend against earlier imports. |
| Corrections to rules | Reviewed rows where `explain` today gives a non-fallback pair that differs from the reviewed pair. Group by `source` and list the worst offender with an "Edit that rule" link (opens the override, or names the `categorize.py` pattern). |
| Suggestions accepted | From Phase 3's provenance: accepted unchanged / total accepted or changed, last 30 days. Hidden until there are suggestions. |
| Rules unused | Rules and overrides with zero matches in the last 6 months of the store. Link to a list. |
| Auto-filed, unchecked | Rows filed by a rule with no `Reviewed At`. |

**Spot-check:** "Spot-check 5" picks 5 random auto-filed, unchecked rows from the selected month
(seeded by month so the same 5 come up until checked) and steps through them in the review panel
with two quick actions: "Looks right" and "Fix it". "Looks right" saves a review with the current
pair and `source: "spot-check"`. Show the running estimate: "Of 25 spot-checked rows, 24 were
right."

Store the provenance by adding optional fields to review decisions in `review_decisions.json`
(`source`: `manual` | `batch` | `sibling` | `spot-check` | `suggestion`; `suggested`: the pair that
was proposed, if any). Older decisions without the fields stay valid. Mirror in
`finance_tracker/reviews.py`.

Write `docs/self-review.md` describing each metric, what it means, and what to do when it moves.

### 5.4 Suggestions from your own history (no AI, always on)

For rows in the queue, find similar **reviewed** rows locally: same counterparty for transfers,
otherwise token overlap on the normalized description (character n-gram TF-IDF is fine, implemented
in JS, a few hundred rows). If the top matches agree on one pair, show a suggestion card with the
source tag "Similar past reviews" and "Why" lines naming the matches (date, amount, pair). This
reuses knowledge already in the ladder and costs nothing. Accepting saves a review with
`source: "suggestion"` and `suggested` set. It never creates a rule; the existing "remember"
checkboxes stay available and off by default.

### 5.5 Small additions

- **Unusual amounts card** on This month, built from the existing outlier logic.
- **Data health alert** on This month when any check fails.
- **Review badge** in the sidebar, always in sync with `#review-count`.

### 5.6 Tests and parity

There is no test suite today. Add:

- `tests/` with pytest for `overview.py` (month-over-month, savings rate, recurring after the
  Phase 0 fix, projection), `budgets.py`, `reviews.py` provenance round-trip, and
  `categorize.explain`.
- `tests/fixtures/` with a synthetic store and budgets (reuse the notebook's generator).
- **Parity:** move the dashboard's pure analytics functions into `dashboard/analytics.js` (a
  classic script that attaches to `window.Analytics` and also does
  `if (typeof module !== "undefined") module.exports = Analytics;`). Load it with a `<script>` tag
  before the main script. `tests/parity/run_js.js` (Node, no dependencies) runs the fixture through
  it and prints JSON; `tests/test_parity.py` compares that JSON with the Python results and fails
  on any difference beyond rounding. Skip the parity test with a clear message when Node isn't
  installed.
- Add `pytest` to a `requirements-dev.txt`.

**Phase 2 done when:** budgets save and reload through the server and survive a restart; the plan
line and new projection render; all self-review metrics show on synthetic data; spot-check works
end to end; tests pass; inventory still fully ticked.

---

## 6. Phase 3: optional AI suggestions (off by default)

Only for rows the rules and history couldn't answer. Inspired by how Contas imports statements:
suggest, show evidence, the user validates, nothing is applied silently.

- **Off unless configured.** The server reads `FINANCE_LLM_PROVIDER` (`openai` or `anthropic`),
  the matching API key from the environment (`OPENAI_API_KEY` / `ANTHROPIC_API_KEY`) and
  `FINANCE_LLM_MODEL`. The identity endpoint reports `"suggestions": true|false`; the UI shows
  nothing AI-related when false. The key never reaches the browser.
- **Endpoint:** `POST /__suggest__` in `serve_dashboard.py`, standard library only (`urllib`).
  Reject requests whose `Origin`/`Host` isn't this server's own `127.0.0.1:<port>`, so another web
  page can't trigger paid calls. Check that the existing PUT handler does the same; if not, add it.
- **Triggered by a click**, never on load: "Suggest categories for 8 rows" with a line saying
  exactly what is sent.
- **What is sent:** for each row, the normalized description, amount, date and type; plus up to 5
  similar reviewed examples (description and chosen pair) from 5.4. No notes, no account numbers,
  no other rows.
- **Constrained output:** structured output with a JSON schema whose `category`/`sub` field is an
  enum of valid taxonomy pairs for that row's type, plus `confidence` (`high`/`low`) and
  `evidence_ids` (which examples it relied on). Validate server-side again; drop anything outside
  the taxonomy.
- **UI:** suggestion cards as in 4.6 with the source tag "AI suggestion" (or "AI suggestion, low
  confidence" in `--over`), "Why" lines built from the evidence rows. Accepting saves a review with
  `source: "suggestion"`, `suggested` set, `suggested_by: "ai"`. Never a rule.
- **Cache** results by `transaction_id` in `data/suggestions_cache.json` (gitignored, hook-blocked),
  so the same row is never paid for twice.
- **Cap** per request (for example 25 rows) and show the count before sending.

**Phase 3 done when:** with no env vars nothing changes; with a key, suggestions appear only after
the click, invalid pairs are impossible, acceptance feeds the self-review metric.

---

## 7. Phase 4: goals (optional, ask before starting)

Temporary savings goals with a target and a deadline, like Contas' sinking funds: `data/goals.json`
(gitignored), a Goals tab with progress, amount still needed per month, and an optional "Goal"
picker in the review panel when the category is the savings category. Don't build this unless
the user confirms; list it in `docs/backlog.md` otherwise.

---

## 8. Out of scope (note in `docs/backlog.md`, don't build)

- Cloud sync, accounts, Firestore. The project stays local.
- Binding the server to the LAN. For phone access later, document Tailscale to reach
  `127.0.0.1` safely instead.
- A phone quick-add PWA (possible later as a capture-only app that exports an encrypted file the
  dashboard merges via the existing dedup).
- Account balances / net worth with a "sync to reality" anchor.

---

## 9. Working method

- One commit per numbered item in Phase 0, then per sub-section in Phases 1–3. Clear messages.
- Before each commit: `python3 scripts/generate_dashboard_rules.py --check`, `pytest`,
  `python3 scripts/strip_notebook_outputs.py --check`, and a manual pass through the inventory for
  anything the change touched.
- Update `README.md` (new tabs, budgets, self-review, suggestions, new data files and env vars) and
  the relevant `docs/` pages in the same commit as the feature.
- When a design detail here conflicts with something in the code you didn't expect, keep the
  existing behaviour, note the conflict in the commit message, and carry on.
- At the end, report: what was done, what deviated from this brief and why, and the inventory with
  every item ticked.
