"""Column layout and category taxonomy for the centralized transactions store.

This mirrors the Expenses / Income sheets of Personal_Finance_Tracker_With_Formulas.xlsx,
collapsed into a single table with a `Type` column so one CSV can serve both.
"""

TRANSACTION_ID = "transaction_id"
DATE = "Date"
TYPE = "Type"
CATEGORY = "Category"
SUBCATEGORY = "Sub-category"
METHOD = "Method"          # Payment Method for expenses, Source for income
AMOUNT = "Amount (€)"
NOTES = "Notes"
MONTH = "Month"
YEAR = "Year"
SOURCE_FILE = "Source File"

COLUMNS = [
    TRANSACTION_ID, DATE, TYPE, CATEGORY, SUBCATEGORY, METHOD,
    AMOUNT, NOTES, MONTH, YEAR, SOURCE_FILE,
]

TYPE_INCOME = "Income"
TYPE_EXPENSE = "Expense"

EXPENSE_CATEGORIES = [
    "Necessário", "Refeição", "Lazer", "Saúde", "Geral", "Poupança/Investimento",
    "Comissões conta", "Transferências Pessoais", "Outros",
]

# "Transferências Pessoais" covers MBWay and plain named bank transfers —
# a payment rail (recorded in Method), not a spending category, so it
# doesn't imply a purpose the way "Refeição" or "Lazer" do. See
# categorize.py's module docstring for why these can't be inferred further.
INCOME_CATEGORIES = [
    "Salário", "Salário_alim", "Transferências Pessoais", "Dinheiro", "Outro",
]

# Category treated as savings/investment for Monthly_Overview purposes,
# excluded from the "Net" expense total the same way the template excludes
# "Cartão Alimentação" from certain sums.
SAVINGS_CATEGORY = "Poupança/Investimento"
