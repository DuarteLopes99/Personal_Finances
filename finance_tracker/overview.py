"""Compute a Monthly_Overview-style aggregate table from the centralized
transactions store, mirroring the SUMIFS logic of the original Excel template.
"""

import pandas as pd

from . import schema


def compute_monthly_overview(df: pd.DataFrame) -> pd.DataFrame:
    """Group transactions by Year/Month and compute Income, Expenses (excluding
    savings/investment transfers), Net, Savings/Investments, and Total Balance.
    """
    if df.empty:
        return pd.DataFrame(columns=[
            "Year", "Month", "Income (€)", "Expenses (€)", "Net (€)",
            "Savings/Investments (€)", "Total Balance (€)",
        ])

    df = df.copy()
    is_income = df[schema.TYPE] == schema.TYPE_INCOME
    is_savings = df[schema.CATEGORY] == schema.SAVINGS_CATEGORY
    is_expense = (df[schema.TYPE] == schema.TYPE_EXPENSE) & ~is_savings

    groups = df.groupby([schema.YEAR, schema.MONTH])

    income = df[is_income].groupby([schema.YEAR, schema.MONTH])[schema.AMOUNT].sum()
    expenses = df[is_expense].groupby([schema.YEAR, schema.MONTH])[schema.AMOUNT].sum()
    savings = df[is_savings].groupby([schema.YEAR, schema.MONTH])[schema.AMOUNT].sum()

    overview = pd.DataFrame(index=groups.size().index)
    overview["Income (€)"] = income
    overview["Expenses (€)"] = expenses
    overview["Savings/Investments (€)"] = savings
    overview = overview.fillna(0.0)

    overview["Net (€)"] = overview["Income (€)"] - overview["Expenses (€)"]
    overview["Total Balance (€)"] = overview["Net (€)"] - overview["Savings/Investments (€)"]

    overview = overview.reset_index().rename(columns={schema.YEAR: "Year", schema.MONTH: "Month"})
    overview = overview.sort_values(["Year", "Month"]).reset_index(drop=True)

    cols = ["Year", "Month", "Income (€)", "Expenses (€)", "Net (€)",
            "Savings/Investments (€)", "Total Balance (€)"]
    return overview[cols].round(2)


def compute_category_breakdown(df: pd.DataFrame, type_filter: str = schema.TYPE_EXPENSE) -> pd.DataFrame:
    """Total amount per Category for a given Type, sorted descending."""
    if df.empty:
        return pd.DataFrame(columns=["Category", "Amount (€)"])
    subset = df[df[schema.TYPE] == type_filter]
    out = (
        subset.groupby(schema.CATEGORY)[schema.AMOUNT]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
        .rename(columns={schema.CATEGORY: "Category", schema.AMOUNT: "Amount (€)"})
    )
    return out.round(2)


def compute_method_breakdown(df: pd.DataFrame, type_filter: str = schema.TYPE_EXPENSE) -> pd.DataFrame:
    """Total amount per Method (payment rail) for a given Type, sorted descending.

    Complements compute_category_breakdown: Category answers "what was it
    for", Method answers "how did the money move" — e.g. how much flowed
    through MBWay vs. card vs. the meal-allowance card.
    """
    if df.empty:
        return pd.DataFrame(columns=["Method", "Amount (€)"])
    subset = df[df[schema.TYPE] == type_filter]
    out = (
        subset.groupby(schema.METHOD)[schema.AMOUNT]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
        .rename(columns={schema.METHOD: "Method", schema.AMOUNT: "Amount (€)"})
    )
    return out.round(2)


def exclude_method(df: pd.DataFrame, method: str = schema.MEAL_CARD_METHOD) -> pd.DataFrame:
    """Drop every transaction (income or expense) paid/received via `method` —
    e.g. exclude Cartão Alimentação to see the picture without meal-allowance
    money, the same toggle the dashboard offers.
    """
    return df[df[schema.METHOD] != method]


# ---------------------------------------------------------------------------
# Monthly spending analytics
#
# The aggregates above answer "what did this month total?". These answer the
# questions you actually ask a finance dashboard: is this month unusual, what
# drove it, what am I paying every month without thinking about it, and — if
# the month is still running — where will it land. Each has a mirror in
# dashboard/index.html's "Monthly analysis" card.
# ---------------------------------------------------------------------------

def _spendable(df: pd.DataFrame) -> pd.DataFrame:
    """Expenses that count as spending: money out, excluding transfers into
    savings/investments (that money is still yours — it moved, it wasn't spent).
    """
    return df[(df[schema.TYPE] == schema.TYPE_EXPENSE)
              & (df[schema.CATEGORY] != schema.SAVINGS_CATEGORY)]


def compute_subcategory_breakdown(df: pd.DataFrame, type_filter: str = schema.TYPE_EXPENSE,
                                  top_n: int = None) -> pd.DataFrame:
    """Total per Category / Sub-category, sorted descending.

    A level finer than compute_category_breakdown: "Alimentação" being your
    biggest category is not actionable, "Alimentação / Restaurantes at €310
    while Compras is €180" is.
    """
    if df.empty:
        return pd.DataFrame(columns=["Category", "Sub-category", "Amount (€)", "Count"])
    subset = df[df[schema.TYPE] == type_filter]
    out = (
        subset.groupby([schema.CATEGORY, schema.SUBCATEGORY])[schema.AMOUNT]
        .agg(["sum", "size"])
        .reset_index()
        .rename(columns={schema.CATEGORY: "Category", schema.SUBCATEGORY: "Sub-category",
                         "sum": "Amount (€)", "size": "Count"})
        .sort_values("Amount (€)", ascending=False)
        .reset_index(drop=True)
    )
    out["Amount (€)"] = out["Amount (€)"].round(2)
    return out.head(top_n) if top_n else out


def compute_category_by_month(df: pd.DataFrame) -> pd.DataFrame:
    """Spending per category per month — one row per month, one column per
    category. The shape a stacked bar chart wants, and the quickest way to see
    which category is trending up rather than which was biggest once.
    """
    spendable = _spendable(df)
    if spendable.empty:
        return pd.DataFrame()
    pivot = spendable.pivot_table(
        index=[schema.YEAR, schema.MONTH], columns=schema.CATEGORY,
        values=schema.AMOUNT, aggfunc="sum", fill_value=0.0,
    )
    return pivot.sort_index().round(2)


def compute_savings_rate(df: pd.DataFrame) -> pd.DataFrame:
    """Per month: income, spending, what went to savings, and the share of
    income that wasn't spent. The single number that says whether a month went
    well independently of how big that month's income happened to be.
    """
    if df.empty:
        return pd.DataFrame(columns=["Year", "Month", "Income (€)", "Spending (€)",
                                     "Savings (€)", "Savings rate (%)"])
    keys = [schema.YEAR, schema.MONTH]
    income = df[df[schema.TYPE] == schema.TYPE_INCOME].groupby(keys)[schema.AMOUNT].sum()
    spending = _spendable(df).groupby(keys)[schema.AMOUNT].sum()
    savings = df[df[schema.CATEGORY] == schema.SAVINGS_CATEGORY].groupby(keys)[schema.AMOUNT].sum()

    out = pd.DataFrame(index=df.groupby(keys).size().index)
    out["Income (€)"] = income
    out["Spending (€)"] = spending
    out["Savings (€)"] = savings
    out = out.fillna(0.0)
    # Guard the zero-income month (a gap in the data, or a month you were
    # between jobs): a rate is meaningless there, not 0% and not -inf.
    out["Savings rate (%)"] = (
        (out["Income (€)"] - out["Spending (€)"]) / out["Income (€)"] * 100
    ).where(out["Income (€)"] > 0)
    return out.reset_index().rename(
        columns={schema.YEAR: "Year", schema.MONTH: "Month"}).round(2)


def compute_month_over_month(df: pd.DataFrame, lookback: int = 3) -> pd.DataFrame:
    """Each month's spending next to the previous month and to a trailing
    average, as absolute and percentage deltas.

    The trailing average deliberately excludes the month being judged — a
    month compared against an average it is itself part of always looks
    closer to normal than it really is.
    """
    monthly = _spendable(df).groupby([schema.YEAR, schema.MONTH])[schema.AMOUNT].sum()
    if monthly.empty:
        return pd.DataFrame(columns=["Year", "Month", "Spending (€)", "Prev month (€)",
                                     f"Trailing {lookback}m avg (€)", "vs prev (%)", "vs avg (%)"])
    monthly = monthly.sort_index()
    out = monthly.reset_index().rename(
        columns={schema.YEAR: "Year", schema.MONTH: "Month", schema.AMOUNT: "Spending (€)"})
    out["Prev month (€)"] = out["Spending (€)"].shift(1)
    trailing = out["Spending (€)"].shift(1).rolling(lookback, min_periods=1).mean()
    out[f"Trailing {lookback}m avg (€)"] = trailing
    out["vs prev (%)"] = (out["Spending (€)"] / out["Prev month (€)"] - 1) * 100
    out["vs avg (%)"] = (out["Spending (€)"] / trailing - 1) * 100
    return out.round(2)


def detect_recurring(df: pd.DataFrame, min_months: int = 3, tolerance: float = 0.15) -> pd.DataFrame:
    """Find charges that look like subscriptions or standing commitments.

    A charge qualifies when the same sub-category shows up in at least
    `min_months` distinct months with an amount that stays within `tolerance`
    of its own median — that combination is what separates Netflix at €8.99
    every month from a restaurant that also happens to be monthly but never
    for the same amount twice.

    Returns one row per recurring charge with its typical amount and the
    annualized cost, which is usually the number that changes behaviour.
    """
    spendable = _spendable(df)
    if spendable.empty:
        return pd.DataFrame(columns=["Category", "Sub-category", "Typical (€)", "Months",
                                     "Last seen", "Annualized (€)"])

    spendable = spendable.copy()
    spendable["_month_key"] = (spendable[schema.YEAR].astype(str) + "-"
                               + spendable[schema.MONTH].astype(int).astype(str).str.zfill(2))

    rows = []
    for (category, sub_category), group in spendable.groupby([schema.CATEGORY, schema.SUBCATEGORY]):
        months = group["_month_key"].nunique()
        if months < min_months:
            continue
        typical = group[schema.AMOUNT].median()
        if typical <= 0:
            continue
        within = (group[schema.AMOUNT] - typical).abs() <= typical * tolerance
        if within.mean() < 0.6:
            continue
        rows.append({
            "Category": category,
            "Sub-category": sub_category,
            "Typical (€)": round(typical, 2),
            "Months": months,
            "Last seen": group[schema.DATE].max(),
            "Annualized (€)": round(typical * 12, 2),
        })
    out = pd.DataFrame(rows, columns=["Category", "Sub-category", "Typical (€)", "Months",
                                      "Last seen", "Annualized (€)"])
    return out.sort_values("Annualized (€)", ascending=False).reset_index(drop=True)


def project_month_end(df: pd.DataFrame, year: int, month: int, as_of_day: int = None,
                      days_in_month: int = 30) -> dict:
    """Where a still-running month lands if the rest of it looks like the part
    already spent. Returns spent-so-far, daily rate, and the projection.

    Only meaningful for the current month — for a finished one, `spent` is
    already the answer and the projection equals it.
    """
    period = df[(df[schema.YEAR] == year) & (df[schema.MONTH] == month)]
    spent = float(_spendable(period)[schema.AMOUNT].sum())
    if as_of_day is None:
        as_of_day = days_in_month
    as_of_day = max(1, min(as_of_day, days_in_month))
    per_day = spent / as_of_day
    return {
        "spent": round(spent, 2),
        "per_day": round(per_day, 2),
        "projected": round(per_day * days_in_month, 2),
        "as_of_day": as_of_day,
        "days_in_month": days_in_month,
    }
