"""Keyword-based categorization of raw bank transaction descriptions.

Rules are checked in order, first match wins. Matching is whole-word (via a
word-boundary regex) so short keywords like "ppr" or "etf" don't false-positive
on unrelated words that merely contain those letters (e.g. "Petfiestas").

Extend EXPENSE_RULES / INCOME_RULES to teach the categorizer new merchants or
entities — no other code needs to change. Mirror any change in
dashboard/index.html's copy of these tables (used for offline, client-side
categorization).

MBWay (and a plain bank "Transferência") is a payment *rail*, not a spending
category — a raw bank description for one of these is just "Trf. MB WAY para
<name>", with no merchant or purpose signal at all, unlike a card purchase. So
expenses over these rails route to "Transferências Pessoais" with the
counterparty's name as the sub-category (via _mbway_counterparty /
_transfer_counterparty below) — useful for spending analysis, since it shows
who money went to. Income over the same rails uses a fixed "Recebido"
sub-category instead: unlike spending, knowing the *sender's* name isn't
particularly useful for "where did my money go" analysis, so there's no need
for the same richness there. Either way, Method still records which rail it
went over (MBWay / Transferência), independent of Category. This is
deliberately different from Personal_Finance_Tracker_With_Formulas.xlsx's
historical data, where the user manually looked up what each MBWay payment was
for (e.g. "Cerveja", "Fisioterapia") — that manual categorization is preserved
as-is by scripts/seed_from_template.py and is more accurate than anything this
module could infer from the bank description alone.

`overrides` (see overrides.py) let a user teach new merchant/entity rules
through the dashboard's "Needs Review" panel without editing this file —
checked before the built-in rules below. They only apply to commercial/
merchant fallbacks ("Outros"/"Outro") that were never derived from a
Transferências Pessoais match, precisely because a peer-to-peer transfer's
purpose can vary month to month — see overrides.py for the full rationale.
"""

import re

_MBWAY_NAME_RE = re.compile(r"mb\s*way\s+(?:para|de)\s+(.+)$", re.IGNORECASE)
_TRANSFER_NAME_RE = re.compile(r"transfer[êe]ncia\s+(?:para|de)\s+(.+)$", re.IGNORECASE)


def _clean_name(raw: str) -> str:
    name = raw.strip(" .")
    return name if name else "Diversos"


def _mbway_counterparty(description: str) -> str:
    m = _MBWAY_NAME_RE.search(description)
    return _clean_name(m.group(1)) if m else "Diversos"


def _transfer_counterparty(description: str) -> str:
    m = _TRANSFER_NAME_RE.search(description)
    return _clean_name(m.group(1)) if m else "Diversos"


# Each rule: (keywords, category, sub_category, method)
# sub_category may be a fixed string, or a callable(description) -> str for
# rules whose sub-category depends on the specific transaction (e.g. the
# transfer counterparty's name).
INCOME_RULES = [
    (["mbway", "mb way"], "Transferências Pessoais", "Recebido", "MBWay"),
    (["ordenado", "salário", "salario", "vencimento"], "Salário", "Salário", "Transferência"),
    (["subsídio de alimentação", "subsidio de alimentacao", "cartão alimentação", "cartao alimentacao"],
     "Salário_alim", "Salário_alim", "Cartão Alimentação"),
    (["reembolso", "estorno", "devolução", "devolucao"], "Transferências Pessoais", "Reembolso", "Transferência"),
    (["transferência", "transferencia"], "Transferências Pessoais", "Recebido", "Transferência"),
]

# Each rule: (keywords, category, sub_category, method)
EXPENSE_RULES = [
    (["levantamento", "atm"], "Geral", "Levantamento", "Levantamento"),

    # Savings & investments — brokerage / ETFs / stocks
    (["degiro", "trading212", "trading 212", "xtb", "etoro", "revolut trading", "interactive brokers"],
     "Poupança/Investimento", "Ações/ETF", "Transferência"),
    # Savings & investments — pension funds / PPR (e.g. "Golden Sgf Soc Gestora Fundo Pensoes Sa")
    (["sgf", "gestora de fundo", "gestora fundo", "fundo de pensões", "fundo de pensoes",
      "fundo pensões", "fundo pensoes", "ppr", "poupança reforma", "poupanca reforma"],
     "Poupança/Investimento", "PPR/Fundo de Pensões", "Transferência"),
    # Savings & investments — crypto
    (["binance", "coinbase", "kraken", "criptomoeda", "cripto", "crypto"],
     "Poupança/Investimento", "Criptomoeda", "Transferência"),

    (["mbway", "mb way"], "Transferências Pessoais", _mbway_counterparty, "MBWay"),

    (["supermercado", "continente", "pingo doce", "lidl", "aldi", "mercadona", "minipreço", "minipreco", "auchan"],
     "Refeição", "Supermercado", "Cartão"),
    (["padaria", "pastelaria"], "Refeição", "Padaria", "Cartão"),
    (["restaurante", "café", "cafe", "pizzaria", "pizz", "churrasco", "gaucho", "marisqueira", "cervejaria"],
     "Refeição", "Restaurante", "Cartão"),

    (["combustível", "combustivel", "gasolina", "gasóleo", "gasoleo", "galp", "repsol", "cepsa", "prio", "bp"],
     "Necessário", "Combustível", "Cartão"),
    (["vodafone", "meo", "nowo", "nos", "telemóvel", "telemovel", "internet"],
     "Necessário", "Telecomunicações", "Débito Direto"),
    (["renda", "prestação casa", "prestacao casa", "crédito habitação", "credito habitacao", "condomínio", "condominio"],
     "Necessário", "Habitação", "Débito Direto"),
    (["seguros", "seguro", "fidelidade", "allianz", "tranquilidade", "ageas"],
     "Necessário", "Seguros", "Débito Direto"),

    (["farmácia", "farmacia", "wells"], "Saúde", "Farmácia", "Cartão"),
    (["fisioterapia", "hospital", "clinica", "clínica", "dentista", "médico", "medico"],
     "Saúde", "Consulta", "Cartão"),
    (["ginásio", "ginasio", "fitness", "holmes place", "solinca"], "Saúde", "Ginásio", "Débito Direto"),

    (["amazon", "ebay", "aliexpress", "eneba", "shein", "wook"], "Lazer", "Compras Online", "Cartão"),
    (["netflix", "spotify", "disney", "hbo", "twitch", "youtube premium", "amazon prime"],
     "Lazer", "Subscrição", "Cartão"),
    (["bowling", "escape room", "cinema", "museu"], "Lazer", "Desporto e Diversão", "Cartão"),
    (["flights", "booking", "ryanair", "tap", "easyjet", "hotel", "airbnb", "viagem"],
     "Lazer", "Viagem", "Cartão"),
    (["zara", "h&m", "primark", "decathlon", "sport zone"], "Lazer", "Roupa", "Cartão"),

    (["comissão", "comissao", "manutenção de conta", "manutencao de conta", "imposto de selo", "imposto selo"],
     "Comissões conta", "Comissão Bancária", "Débito Direto"),

    # Generic named bank transfer with no merchant/purpose signal (checked
    # last, so any more specific rule above still wins).
    (["transferência", "transferencia"], "Transferências Pessoais", _transfer_counterparty, "Transferência"),
]


def _matches(desc_lower: str, keyword: str) -> bool:
    return re.search(rf"\b{re.escape(keyword.strip())}\b", desc_lower) is not None


def _match(desc_lower: str, description: str, rules):
    for keywords, category, sub_category, method in rules:
        if any(_matches(desc_lower, kw) for kw in keywords):
            sub = sub_category(description) if callable(sub_category) else sub_category
            return category, sub, method
    return None


def _overrides_to_rules(overrides, txn_type: str):
    return [
        (o["keywords"], o["category"], o["sub_category"], o.get("method", ""))
        for o in (overrides or [])
        if o.get("type") in (txn_type, "both")
    ]


def categorize_transaction(description: str, amount: float, overrides=None) -> tuple:
    """Return (category, sub_category, method) for a raw transaction.

    amount > 0 => income rules; amount < 0 => expense rules. `overrides` (see
    overrides.py), if given, are checked before the built-in rules, so a
    user-taught merchant rule always wins.

    Falls back to a generic bucket ("Outro"/"Outros") when nothing matches,
    so every transaction is still captured for manual re-categorization later.
    """
    description = str(description)
    desc_lower = description.lower()

    if amount > 0:
        rules = _overrides_to_rules(overrides, "income") + INCOME_RULES
        hit = _match(desc_lower, description, rules)
        return hit if hit else ("Outro", "Outro", "Transferência")

    rules = _overrides_to_rules(overrides, "expense") + EXPENSE_RULES
    hit = _match(desc_lower, description, rules)
    return hit if hit else ("Outros", "Outros", "Cartão")
