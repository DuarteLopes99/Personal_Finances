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
