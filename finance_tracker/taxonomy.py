"""THE taxonomy. Every Category / Sub-category pair the store is allowed to
contain is written here, and nothing else is legal anywhere in the system.

This file is deliberately data, not logic: no imports, no computation beyond
building a few lookup tables. `scripts/generate_dashboard_rules.py` loads it
straight from its path (bypassing the package `__init__`, which needs pandas),
so it must stay dependency-free.

Why "strict"
------------
Before this file existed the taxonomy was a list of category *names* in
schema.py that nothing enforced. Rules, user overrides and manual reviews could
each write any string they liked, and they did — the store ended up holding
`Gasoleo` next to `Combustível`, `Telemovel` next to `Telecomunicações`, `PPR`
next to `PPR/Fundo de Pensões`, `SuperMercado` filed under `Lazer`, and 71
sub-categories that were just people's names. Each of those splits a real
spending line into two chart bars that never add up.

So the direction of authority is inverted: the taxonomy is declared first, and
every producer of a classification is validated against it.

  - `categorize._validate_rules()` runs at import over PURPOSE_EXPENSE_RULES
    and PURPOSE_INCOME_RULES — a rule naming a pair that isn't here raises
    immediately, so a typo can never reach the store.
  - `overrides.add_override` refuses to save an off-taxonomy pair.
  - `scripts/recategorize.py` maps every legacy pair onto this one.

Rules for changing it
---------------------
Adding a sub-category is cheap: add it to the tuple and re-run
`scripts/generate_dashboard_rules.py`. Renaming or removing one is not — the
store already holds rows using the old name, so it needs an entry in
`LEGACY_ALIASES` below, which is what lets old data keep working.

Every category ends with a catch-all sub-category (`Outros`) on purpose: it
gives an honest home to "I know it was health, I don't know which kind" without
inventing a sub-category per transaction, and it keeps the review UI from
forcing a wrong specific answer.
"""

TYPE_INCOME = "Income"
TYPE_EXPENSE = "Expense"

# Two different admissions of ignorance, and collapsing them loses real
# information:
#
#   CATCH_ALL_SUB ("Outros")        — a settled answer. "I know the category,
#                                     the sub-category isn't worth its own line."
#                                     Saúde/Outros is finished work.
#   UNCLASSIFIED_SUB ("Por Classificar") — a TEMPORARY state. Nothing matched;
#                                     nobody has looked. This is what the Needs
#                                     Review queue and the Data health backlog
#                                     are built from, and it should trend to zero.
#
# `Outros` carries both: Outros/Por Classificar is the queue, Outros/Outros is
# the genuinely miscellaneous transaction that has a home nowhere else and needs
# no further thought.
CATCH_ALL_SUB = "Outros"
UNCLASSIFIED_CATEGORY = "Outros"
UNCLASSIFIED_SUB = "Por Classificar"

# ---------------------------------------------------------------------------
# EXPENSES
# ---------------------------------------------------------------------------
# Order matters: it is the display order in the dashboard's charts and tables,
# and the order of the category picker in the review panel.
EXPENSE_TAXONOMY = {
    "Saúde": (
        "Lentes",
        "Fisioterapia",
        "Farmácia",
        "Consultas/Exames",
        CATCH_ALL_SUB,
    ),
    # Not spending — money moving from one pocket to another. Excluded from
    # expense totals via SAVINGS_CATEGORY below, the same way the original
    # Excel tracker excluded it.
    "Investimentos": (
        "ETFs/DEGIRO",
        "PPR",
        CATCH_ALL_SUB,
    ),
    "Alimentação": (
        "Compras",
        "Restaurantes",
        "Café/Padaria",
        "Take-away/Delivery",
        CATCH_ALL_SUB,
    ),
    "Lazer": (
        "Escape Room",
        "Saídas Noite/Bares",
        "Férias",
        "Cinema/Espetáculos",
        "LEGO/Pop-Culture/Memorabilia",
        "Roupa",
        "Subscrições",
        "Compras Online",
        "Gaming",
        CATCH_ALL_SUB,
    ),
    "Educação": (
        "Cursos/Formação",
        "Livros/Material",
        CATCH_ALL_SUB,
    ),
    "Geral": (
        "Gasóleo",
        "Carro",
        "Telemóvel",
        "Transportes",
        "Casa",
        "Seguros",
        "Comissões e Impostos",
        "Revolut",
        "TradeRepublic",
        CATCH_ALL_SUB,
    ),
    "Desporto": (
        "Futebol",
        "Corrida",
        "Ginásio",
        "Equipamento",
        CATCH_ALL_SUB,
    ),
    "Prendas": (
        "Aniversário",
        "Natal",
        CATCH_ALL_SUB,
    ),
    # The honest-ignorance category, holding four distinct things:
    #   Por Classificar          — temporary: nothing matched, needs a human
    #   Outros                   — settled: genuinely miscellaneous, no better home
    #   Levantamento             — settled: cash out, purpose unknowable
    #   Transferências Pessoais  — settled: money to a named person, reason unknown
    # Only the first is backlog. The rest are answers.
    UNCLASSIFIED_CATEGORY: (
        UNCLASSIFIED_SUB,
        CATCH_ALL_SUB,
        "Levantamento",
        "Transferências Pessoais",
    ),
}

# ---------------------------------------------------------------------------
# INCOME
# ---------------------------------------------------------------------------
INCOME_TAXONOMY = {
    "Salário": (
        "Salário",
        CATCH_ALL_SUB,
    ),
    "Salário Alimentação": (
        "Salário Alimentação",
    ),
    # One category for money received from a person, split by rail rather than
    # by sender. Deliberately NOT one sub-category per name: the store already
    # accumulated 71 of those, which turned the income breakdown into a phone
    # book. The sender stays in Notes, where it belongs.
    "Transferências Pessoais": (
        "MBWay",
        "Transferência",
    ),
    "Subsídios": (
        "Desemprego",
        CATCH_ALL_SUB,
    ),
    # Money coming back, not money earned — worth its own line so it never
    # inflates apparent income. IRS lives here rather than under Subsídios
    # because a tax refund is a repayment, not a benefit.
    "Reembolsos": (
        "IRS",
        "Seguros",
        "Estornos",
    ),
    UNCLASSIFIED_CATEGORY: (
        UNCLASSIFIED_SUB,
        CATCH_ALL_SUB,
    ),
}

TAXONOMY = {
    TYPE_EXPENSE: EXPENSE_TAXONOMY,
    TYPE_INCOME: INCOME_TAXONOMY,
}

EXPENSE_CATEGORIES = list(EXPENSE_TAXONOMY)
INCOME_CATEGORIES = list(INCOME_TAXONOMY)

# Category excluded from the "Net" expense total in Monthly_Overview — money
# saved is not money spent.
SAVINGS_CATEGORY = "Investimentos"

# Payment rails. Not part of the Category taxonomy and never mixed into it:
# a rail is an observed property of how the money moved, while a category is a
# judgement about why. Conflating the two is what used to make every MBWay-paid
# cinema ticket disappear into a transfer bucket.
UNSPECIFIED_METHOD = "Não especificado"
MEAL_CARD_METHOD = "Cartão Alimentação"
METHODS = [
    "Cartão", "MBWay", "Transferência", "Débito Direto",
    MEAL_CARD_METHOD, "Dinheiro", "Levantamento", UNSPECIFIED_METHOD,
]

# ---------------------------------------------------------------------------
# Legacy names
# ---------------------------------------------------------------------------
# The store predates this file and holds pairs from the Excel-seeded taxonomy
# (Refeição / Necessário / Comissões conta / ...) plus a few one-off strings
# typed by hand. `scripts/recategorize.py` rewrites them using this map;
# it lives here, next to the taxonomy, so that the reason a name is gone is
# visible in the same file that removed it.
#
# Keys are (Type, old category, old sub-category) with the sub-category
# lowercased; "*" matches any sub-category in that category. Values are the
# new (category, sub-category).
LEGACY_ALIASES = {
    # --- Expenses: the Excel tracker's categories ---
    (TYPE_EXPENSE, "Refeição", "supermercado"): ("Alimentação", "Compras"),
    (TYPE_EXPENSE, "Refeição", "continente"): ("Alimentação", "Compras"),
    (TYPE_EXPENSE, "Refeição", "pingo doce"): ("Alimentação", "Compras"),
    (TYPE_EXPENSE, "Refeição", "restaurante"): ("Alimentação", "Restaurantes"),
    (TYPE_EXPENSE, "Refeição", "jantar"): ("Alimentação", "Restaurantes"),
    (TYPE_EXPENSE, "Refeição", "almoço"): ("Alimentação", "Restaurantes"),
    (TYPE_EXPENSE, "Refeição", "padaria"): ("Alimentação", "Café/Padaria"),
    (TYPE_EXPENSE, "Refeição", "*"): ("Alimentação", CATCH_ALL_SUB),

    (TYPE_EXPENSE, "Necessário", "combustível"): ("Geral", "Gasóleo"),
    (TYPE_EXPENSE, "Necessário", "gasoleo"): ("Geral", "Gasóleo"),
    (TYPE_EXPENSE, "Necessário", "telecomunicações"): ("Geral", "Telemóvel"),
    (TYPE_EXPENSE, "Necessário", "telemovel"): ("Geral", "Telemóvel"),
    (TYPE_EXPENSE, "Necessário", "seguros"): ("Geral", "Seguros"),
    (TYPE_EXPENSE, "Necessário", "habitação"): ("Geral", "Casa"),
    (TYPE_EXPENSE, "Necessário", "*"): ("Geral", CATCH_ALL_SUB),

    (TYPE_EXPENSE, "Comissões conta", "*"): ("Geral", "Comissões e Impostos"),

    (TYPE_EXPENSE, "Geral", "levantamento"): (UNCLASSIFIED_CATEGORY, "Levantamento"),
    (TYPE_EXPENSE, "Geral", "gasoleo"): ("Geral", "Gasóleo"),
    (TYPE_EXPENSE, "Geral", "prenda"): ("Prendas", CATCH_ALL_SUB),
    (TYPE_EXPENSE, "Geral", "random"): (UNCLASSIFIED_CATEGORY, UNCLASSIFIED_SUB),

    # Health: the gym was under Saúde, the taxonomy now files it under Desporto.
    (TYPE_EXPENSE, "Saúde", "ginásio"): ("Desporto", "Ginásio"),
    (TYPE_EXPENSE, "Saúde", "consulta"): ("Saúde", "Consultas/Exames"),
    (TYPE_EXPENSE, "Saúde", "laboratório"): ("Saúde", "Consultas/Exames"),
    (TYPE_EXPENSE, "Saúde", "hospital luz"): ("Saúde", "Consultas/Exames"),
    (TYPE_EXPENSE, "Saúde", "wells"): ("Saúde", "Farmácia"),

    (TYPE_EXPENSE, "Poupança/Investimento", "ações/etf"): ("Investimentos", "ETFs/DEGIRO"),
    (TYPE_EXPENSE, "Poupança/Investimento", "ppr/fundo de pensões"): ("Investimentos", "PPR"),
    (TYPE_EXPENSE, "Poupança/Investimento", "ppr"): ("Investimentos", "PPR"),
    (TYPE_EXPENSE, "Investimento", "ppr"): ("Investimentos", "PPR"),
    (TYPE_EXPENSE, "Investimento", "*"): ("Investimentos", CATCH_ALL_SUB),
    (TYPE_EXPENSE, "Poupança/Investimento", "*"): ("Investimentos", CATCH_ALL_SUB),

    # Lazer sub-categories that were free-text merchant names or misfilings.
    (TYPE_EXPENSE, "Lazer", "comida"): ("Alimentação", "Restaurantes"),
    (TYPE_EXPENSE, "Lazer", "supermercado"): ("Alimentação", "Compras"),
    (TYPE_EXPENSE, "Lazer", "saídas noite"): ("Lazer", "Saídas Noite/Bares"),
    (TYPE_EXPENSE, "Lazer", "cinema"): ("Lazer", "Cinema/Espetáculos"),
    (TYPE_EXPENSE, "Lazer", "viagem"): ("Lazer", "Férias"),
    (TYPE_EXPENSE, "Lazer", "subscrição"): ("Lazer", "Subscrições"),
    (TYPE_EXPENSE, "Lazer", "disney plus"): ("Lazer", "Subscrições"),
    (TYPE_EXPENSE, "Lazer", "twicth"): ("Lazer", "Subscrições"),
    (TYPE_EXPENSE, "Lazer", "eneba"): ("Lazer", "Compras Online"),
    (TYPE_EXPENSE, "Lazer", "encomendas - roupa"): ("Lazer", "Roupa"),
    (TYPE_EXPENSE, "Lazer", "prenda"): ("Prendas", CATCH_ALL_SUB),
    (TYPE_EXPENSE, "Lazer", "bowling"): ("Lazer", CATCH_ALL_SUB),
    (TYPE_EXPENSE, "Lazer", "museu"): ("Lazer", "Cinema/Espetáculos"),
    (TYPE_EXPENSE, "Lazer", "desporto"): ("Desporto", CATCH_ALL_SUB),
    (TYPE_EXPENSE, "Lazer", "futebol"): ("Desporto", "Futebol"),
    (TYPE_EXPENSE, "Lazer", "desporto e diversão"): ("Lazer", CATCH_ALL_SUB),

    # --- Income ---
    (TYPE_INCOME, "Salário_alim", "*"): ("Salário Alimentação", "Salário Alimentação"),
    (TYPE_INCOME, "Salário", "transferência"): ("Salário", "Salário"),
    (TYPE_INCOME, "Dinheiro", "mbway"): ("Transferências Pessoais", "MBWay"),
    (TYPE_INCOME, "Dinheiro", "dinheiro"): ("Transferências Pessoais", "MBWay"),
    (TYPE_INCOME, "Dinheiro/MBWay", "*"): ("Transferências Pessoais", "MBWay"),
    (TYPE_INCOME, "Outro", "reembolso"): ("Reembolsos", "Estornos"),
    (TYPE_INCOME, "Outro", "reembolsos irs"): ("Reembolsos", "IRS"),
}

# Where a transfer with a named counterparty lands. The name itself is never
# used as a sub-category — 71 of those accumulated before this file existed,
# which is a phone book rather than a taxonomy — so it stays in Notes and the
# row gets the type's generic personal-transfer bucket.
LEGACY_PEER_CATEGORIES = {
    TYPE_EXPENSE: (UNCLASSIFIED_CATEGORY, "Transferências Pessoais"),
    TYPE_INCOME: ("Transferências Pessoais", "Transferência"),
}


def categories(txn_type: str) -> list:
    """Ordered category names for "Income" or "Expense"."""
    return list(TAXONOMY[txn_type])


def subcategories(txn_type: str, category: str) -> list:
    """Ordered sub-category names for one category, or [] if unknown."""
    return list(TAXONOMY.get(txn_type, {}).get(category, ()))


def is_valid(txn_type: str, category: str, sub_category: str) -> bool:
    return sub_category in TAXONOMY.get(txn_type, {}).get(category, ())


def validate(txn_type: str, category: str, sub_category: str, where: str = "") -> None:
    """Raise ValueError unless the pair is in the taxonomy.

    Called at import time on the rule tables and on every user-taught override,
    so an off-taxonomy pair fails loudly at the point it is written instead of
    silently becoming a new bar in a chart three months later.
    """
    if txn_type not in TAXONOMY:
        raise ValueError(f"{where}unknown transaction type {txn_type!r}")
    if category not in TAXONOMY[txn_type]:
        raise ValueError(
            f"{where}{category!r} is not a {txn_type} category. "
            f"Valid: {', '.join(categories(txn_type))}"
        )
    if sub_category not in TAXONOMY[txn_type][category]:
        raise ValueError(
            f"{where}{sub_category!r} is not a sub-category of {category!r}. "
            f"Valid: {', '.join(subcategories(txn_type, category))}"
        )


def unclassified(txn_type: str) -> tuple:
    """The (category, sub-category) meaning "not classified yet"."""
    return UNCLASSIFIED_CATEGORY, UNCLASSIFIED_SUB


def is_unclassified(category, sub_category) -> bool:
    """Whether this pair means "nothing matched — still awaiting an answer".

    The **whole pair**, never the category alone. `Outros` also holds
    `Levantamento` and `Transferências Pessoais`, which are settled facts —
    cash withdrawn, money sent to a named person — rather than open questions.

    This exists because three separate places were each deciding it for
    themselves and one of them got it wrong: `reviews.apply_by_description`
    tested only the category, so a reviewed ATM withdrawal silently relabelled
    every other withdrawal sharing its description. `Transferências Pessoais`
    escaped the same fate only by accident, because that code path happens to
    skip transfer rails. One predicate, one place.
    """
    return (str(category), str(sub_category)) == (UNCLASSIFIED_CATEGORY, UNCLASSIFIED_SUB)


def resolve(txn_type: str, category, sub_category):
    """Best valid pair for a possibly-legacy one, or None if there isn't one.

    The shared front door for anything reading pairs written before this file
    existed — `scripts/recategorize.py` for the store, and
    `scripts/seed_from_template.py` for a fresh import from the Excel tracker.
    Both used to write whatever string the source contained, which is precisely
    how `Gasoleo`, `Telemovel` and 71 counterparty names got in.

    Returning None rather than a fallback is deliberate: the caller knows more
    than this function does about what to do next. The migration re-runs the
    regex rules; the seeder drops to the category's catch-all.
    """
    category = str(category or "").strip()
    sub_category = str(sub_category or "").strip()
    if is_valid(txn_type, category, sub_category):
        return category, sub_category

    key = sub_category.lower()
    for lookup in ((txn_type, category, key), (txn_type, category, "*")):
        aliased = LEGACY_ALIASES.get(lookup)
        if aliased and is_valid(txn_type, *aliased):
            return aliased
    return None
