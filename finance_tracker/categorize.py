"""Keyword-based categorization of raw bank transaction descriptions.

Categorization happens in two independent steps, deliberately kept separate:

1. **Category / Sub-category** comes only from purpose/merchant keywords
   (supermarket, restaurant, cinema, Vodafone, Degiro, ...) — see PURPOSE_RULES
   below. MBWay and "transferência" are NOT purpose signals and never appear
   in this table, because they say nothing about *why* money moved.
2. **Method** (the payment rail) is detected independently, from its own
   keywords, and can override whichever method a purpose rule suggested: a
   description containing "mbway" is always Method=MBWay, regardless of
   what it's for.

This matters because a rail keyword and a purpose keyword can both appear in
the same description — e.g. "Mbway - Cinemas" — and both must be honored:
Category=Lazer/Cinema (from the purpose keyword) *and* Method=MBWay (from the
rail keyword). Treating MBWay/"transferência" as a category (as an earlier
version of this module did) meant the rail always won and swallowed the
purpose signal, silently miscategorizing anything paid via MBWay that also
had a recognizable purpose.

When NO purpose keyword matches at all, the transaction falls back to
Category "Outros"/"Outro". If the independently-detected Method is MBWay or
Transferência (i.e. this looks like a peer-to-peer transfer with truly no
purpose signal — just "Trf. MB WAY para <name>"), the counterparty's name is
kept as the Sub-category instead of a flat "Diversos", since it's still
useful for spending analysis to see who money went to/from. Either way this
still lands in the dashboard's "Needs Review" queue.

Rules are checked in order, first match wins. Matching is whole-word (via a
word-boundary regex) so short keywords like "ppr" or "etf" don't false-positive
on unrelated words that merely contain those letters (e.g. "Petfiestas").

Extend PURPOSE_INCOME_RULES / PURPOSE_EXPENSE_RULES to teach the categorizer
new merchants or entities — no other code needs to change. Mirror any change
in dashboard/index.html's copy of these tables (used for offline, client-side
categorization).

`overrides` (see overrides.py) let a user teach new merchant/entity rules
through the dashboard's "Needs Review" panel without editing this file —
checked before the built-in purpose rules below, and skip the method-overlay
step entirely (a saved override is fully explicit: category, sub-category,
and method are all exactly what the user chose). They're only ever offered
for "Outros"/"Outro" rows whose Method is NOT MBWay/Transferência, precisely
because a peer-to-peer transfer's purpose can vary month to month — see
overrides.py for the full rationale.
"""

import re

_MBWAY_NAME_RE = re.compile(r"mb\s*way\s+(?:para|de)\s+(.+)$", re.IGNORECASE)
_TRANSFER_NAME_RE = re.compile(r"transfer[êe]ncia\s+(?:para|de)\s+(.+)$", re.IGNORECASE)


def _clean_name(raw: str) -> str:
    name = raw.strip(" .")
    return name if name else None


def _extract_counterparty(description: str):
    for pattern in (_MBWAY_NAME_RE, _TRANSFER_NAME_RE):
        m = pattern.search(description)
        if m:
            name = _clean_name(m.group(1))
            if name:
                return name
    return None


# Each rule: (keywords, category, sub_category, suggested_method). The
# suggested method is a default only — see _overlay_method — never a promise
# that the transaction actually went over that rail.
PURPOSE_INCOME_RULES = [
    (["ordenado", "salário", "salario", "vencimento"], "Salário", "Salário", "Transferência"),
    (["subsídio de alimentação", "subsidio de alimentacao", "cartão alimentação", "cartao alimentacao"],
     "Salário_alim", "Salário_alim", "Cartão Alimentação"),
    (["reembolso", "estorno", "devolução", "devolucao"], "Outro", "Reembolso", "Transferência"),
]

PURPOSE_EXPENSE_RULES = [
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

    (["supermercado", "continente", "pingo doce", "lidl", "aldi", "mercadona", "minipreço", "minipreco", "auchan"],
     "Refeição", "Supermercado", "Cartão"),
    (["padaria", "pastelaria"], "Refeição", "Padaria", "Cartão"),
    (["restaurante", "café", "cafe", "pizzaria", "pizz", "churrasco", "gaucho", "marisqueira", "cervejaria"],
     "Refeição", "Restaurante", "Cartão"),

    # Entertainment venues checked before the telecom block below: "NOS" is
    # both a telecom brand and (via "NOS Cinemas") a real cinema chain name,
    # so the more specific "cinema"/"bowling"/... match must win first.
    (["amazon", "ebay", "aliexpress", "eneba", "shein", "wook"], "Lazer", "Compras Online", "Cartão"),
    (["netflix", "spotify", "disney", "hbo", "twitch", "youtube premium", "amazon prime"],
     "Lazer", "Subscrição", "Cartão"),
    (["cinema", "cinemas"], "Lazer", "Cinema", "Cartão"),
    (["bowling"], "Lazer", "Bowling", "Cartão"),
    (["escape room"], "Lazer", "Escape Room", "Cartão"),
    (["museu", "museus"], "Lazer", "Museu", "Cartão"),
    (["flights", "booking", "ryanair", "tap", "easyjet", "hotel", "airbnb", "viagem"],
     "Lazer", "Viagem", "Cartão"),
    (["zara", "h&m", "primark", "decathlon", "sport zone"], "Lazer", "Roupa", "Cartão"),

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

    (["comissão", "comissao", "manutenção de conta", "manutencao de conta", "imposto de selo", "imposto selo"],
     "Comissões conta", "Comissão Bancária", "Débito Direto"),
]


def _matches(desc_lower: str, keyword: str) -> bool:
    return re.search(rf"\b{re.escape(keyword.strip())}\b", desc_lower) is not None


def _match_purpose(desc_lower: str, rules):
    for keywords, category, sub_category, suggested_method in rules:
        if any(_matches(desc_lower, kw) for kw in keywords):
            return category, sub_category, suggested_method
    return None


def _overlay_method(desc_lower: str, suggested_method: str) -> str:
    """The payment rail is detected independently of purpose, and a rail
    keyword always wins over whatever a purpose rule suggested."""
    if _matches(desc_lower, "mbway") or _matches(desc_lower, "mb way"):
        return "MBWay"
    if _matches(desc_lower, "transferência") or _matches(desc_lower, "transferencia"):
        return "Transferência"
    return suggested_method


def _match_override(desc_lower: str, overrides, txn_type: str):
    for o in (overrides or []):
        if o.get("type") not in (txn_type, "both"):
            continue
        if any(_matches(desc_lower, kw) for kw in o["keywords"]):
            return o["category"], o["sub_category"], o.get("method", "")
    return None


def categorize_transaction(description: str, amount: float, overrides=None) -> tuple:
    """Return (category, sub_category, method) for a raw transaction.

    amount > 0 => income rules; amount < 0 => expense rules. `overrides` (see
    overrides.py), if given, are checked before the built-in purpose rules,
    fully explicit and not subject to the method-overlay step — a saved
    override always wins outright.

    Falls back to a generic bucket ("Outro"/"Outros") when no purpose keyword
    matches, so every transaction is still captured for manual
    re-categorization later — nothing is silently dropped.
    """
    description = str(description)
    desc_lower = description.lower()
    is_income = amount > 0

    override_hit = _match_override(desc_lower, overrides, "income" if is_income else "expense")
    if override_hit:
        return override_hit

    purpose_rules = PURPOSE_INCOME_RULES if is_income else PURPOSE_EXPENSE_RULES
    hit = _match_purpose(desc_lower, purpose_rules)
    if hit:
        category, sub_category, suggested_method = hit
        return category, sub_category, _overlay_method(desc_lower, suggested_method)

    fallback_category = "Outro" if is_income else "Outros"
    method = _overlay_method(desc_lower, "Transferência" if is_income else "Cartão")
    sub_category = "Diversos"
    if method in ("MBWay", "Transferência"):
        name = _extract_counterparty(description)
        if name:
            sub_category = name
    return fallback_category, sub_category, method
