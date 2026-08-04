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
