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
    "Comissões conta", "Outros",
]

INCOME_CATEGORIES = [
    "Salário", "Salário_alim", "Dinheiro", "Outro",
]

# Method used when a historical row simply never had one recorded (e.g. a
# blank "Payment Method" cell in the source Excel tracker) — never blank/None
# in the store itself, so charts always get a real, labeled bucket.
UNSPECIFIED_METHOD = "Não especificado"

# Payment methods (the rail money moved over) — deliberately separate from
# Category. MBWay and Transferência are never a Category (see categorize.py's
# module docstring); they only ever appear here, in Method.
METHODS = [
    "Cartão", "MBWay", "Transferência", "Débito Direto",
    "Cartão Alimentação", "Dinheiro", "Levantamento", UNSPECIFIED_METHOD,
]

# Category treated as savings/investment for Monthly_Overview purposes,
# excluded from the "Net" expense total the same way the template excludes
# "Cartão Alimentação" from certain sums.
SAVINGS_CATEGORY = "Poupança/Investimento"

# Method used for the meal-allowance card — excludable from analysis via the
# dashboard's "Exclude Cartão Alimentação" toggle / overview.exclude_method().
MEAL_CARD_METHOD = "Cartão Alimentação"
