"""Column layout for the centralized transactions store.

The *taxonomy* — which Category / Sub-category pairs may exist — lives in
taxonomy.py and is re-exported here so existing callers (`schema.EXPENSE_CATEGORIES`,
`schema.METHODS`, ...) keep working. This module owns the shape of the table;
taxonomy.py owns the vocabulary that goes in it.

The layout mirrors the Expenses / Income sheets of the original Excel tracker,
collapsed into a single table with a `Type` column so one CSV can serve both.
"""

from .taxonomy import (
    EXPENSE_CATEGORIES,
    INCOME_CATEGORIES,
    MEAL_CARD_METHOD,
    METHODS,
    SAVINGS_CATEGORY,
    TYPE_EXPENSE,
    TYPE_INCOME,
    UNCLASSIFIED_CATEGORY,
    UNCLASSIFIED_SUB,
    UNSPECIFIED_METHOD,
    is_refund_row,
    is_unclassified,
    is_valid,
    subcategories,
)

TRANSACTION_ID = "transaction_id"
DATE = "Date"
TYPE = "Type"
CATEGORY = "Category"
SUBCATEGORY = "Sub-category"
METHOD = "Method"          # Payment Method for expenses, Source for income
AMOUNT = "Amount (€)"
NOTES = "Notes"
REVIEW_NOTE = "Review Note"   # what the user found out this transaction actually was
REVIEWED_AT = "Reviewed At"   # ISO timestamp of the manual review, "" if never reviewed
MONTH = "Month"
YEAR = "Year"
SOURCE_FILE = "Source File"

COLUMNS = [
    TRANSACTION_ID, DATE, TYPE, CATEGORY, SUBCATEGORY, METHOD,
    AMOUNT, NOTES, REVIEW_NOTE, REVIEWED_AT, MONTH, YEAR, SOURCE_FILE,
]

# Columns that carry a manual review decision rather than raw bank data. They
# are what `reviews.py` persists outside the store so that rebuilding
# transactions.csv from raw exports doesn't throw away the research the user
# did to work out what an unrecognized transaction actually was.
REVIEW_COLUMNS = [CATEGORY, SUBCATEGORY, METHOD, REVIEW_NOTE, REVIEWED_AT]

# The taxonomy names above are re-exported deliberately, so that callers can
# keep saying `schema.METHODS` / `schema.TYPE_EXPENSE` without caring which
# module owns the vocabulary. Declaring them here is also what tells a linter
# the imports aren't dead.
__all__ = [
    # Re-exported from taxonomy.py
    "EXPENSE_CATEGORIES", "INCOME_CATEGORIES", "MEAL_CARD_METHOD", "METHODS",
    "SAVINGS_CATEGORY", "TYPE_EXPENSE", "TYPE_INCOME", "UNCLASSIFIED_CATEGORY",
    "UNCLASSIFIED_SUB", "UNSPECIFIED_METHOD", "is_refund_row", "is_unclassified", "is_valid",
    "subcategories",
    # Owned by this module
    "TRANSACTION_ID", "DATE", "TYPE", "CATEGORY", "SUBCATEGORY", "METHOD",
    "AMOUNT", "NOTES", "REVIEW_NOTE", "REVIEWED_AT", "MONTH", "YEAR",
    "SOURCE_FILE", "COLUMNS", "REVIEW_COLUMNS",
]
