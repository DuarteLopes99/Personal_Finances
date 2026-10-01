"""Regex classification of raw bank descriptions into the strict taxonomy.

Read `taxonomy.py` first — it declares every Category / Sub-category pair that
may exist. This module only decides *which* of those pairs a description gets;
it can never invent a new one. `_validate_rules()` at the bottom checks every
rule against the taxonomy at import time, so a typo in a category name is an
ImportError, not a new bar in a chart three months later.

Two questions, never mixed
--------------------------
1. **Category / Sub-category** comes only from purpose signals (supermarket,
   restaurant, cinema, Vodafone, Degiro...). MBWay and "transferência" are NOT
   purpose signals and never appear in the rule tables — they say nothing about
   *why* money moved.
2. **Method** (the payment rail) is detected independently by `_overlay_method`
   and always wins over whatever a rule suggested: a description containing
   "mbway" is Method=MBWay regardless of what it was for.

Both signals routinely appear in the same string — "Mbway - Cinemas" names a
rail *and* a purpose — and both must be honored: Lazer/Cinema-Espetáculos *and*
MBWay. The fourth element of each rule is only a default for when the
description names no rail at all. Never write one rule per payment method; the
second copy is unreachable (first match wins) and the overlay already covers it.

Normalization, and why patterns carry no accents
------------------------------------------------
Every description is passed through `normalize()` before matching: Unicode NFD,
combining marks dropped, lowercased, whitespace collapsed. So `Refeição` and
`Refeicao` are the same string by the time a pattern sees it, and every pattern
here is written unaccented. This removes a whole class of bug that used to need
two spellings of every keyword — and, more importantly, it lets both engines
agree: the browser's `\\b` is ASCII-only while Python's is Unicode-aware, so
`\\bcafé\\b` silently matched in the CLI and not in the dashboard.

For the same reason patterns may use **only ASCII-safe regex syntax**: no `\\b`,
no `\\w`, no `\\p{...}`. Word boundaries are applied for you by `_compile()` as
explicit `[a-z0-9_]` lookarounds, identical in both engines. Use `[a-z0-9]*` to
absorb the bank's truncation (`vodaf[a-z]*` reaches both "Vodafone" and the
truncated "Vodafo").

Precedence
----------
0. **Refunds** decide the *side*, not the answer: money in with a refund word
   ("Devolução", "Estorno") is a purchase being undone, so it goes down the
   expense side of everything below instead of the income side.
1. **Payment gateways** — Nuvei, Eupago, Stripe & co. resell other merchants,
   so the description names the processor and not what was bought. They are
   forced into the review queue rather than guessed at.
2. **Merchant overrides** — the user's own corrections (see overrides.py).
3. **These rule tables**, in order, first match wins.
4. **Peer overrides** — opt-in, fallback path only, so a real purpose signal
   always beats them.
5. **The unclassified bucket** — Outros / Por Classificar, plus the two honest
   non-purpose buckets (Levantamento, Transferências Pessoais).
"""

import re
import unicodedata

from . import taxonomy as tx

# Boundary applied around every pattern. ASCII-only on purpose: after
# normalize() strips diacritics the text is effectively ASCII, and an
# ASCII-only class is the one thing Python and JavaScript define identically.
_WORD = "a-z0-9_"

_COMBINING = re.compile("[\\u0300-\\u036f]")  # combining marks left by NFD
_WHITESPACE = re.compile(r"\s+")

METHODS = tx.METHODS


def normalize(description) -> str:
    """Lowercase, unaccented, whitespace-collapsed form used for all matching.

    Mirrored exactly in dashboard/index.html's `normalize()`. Any change here
    is a change to the classification of every future transaction, and must be
    made in both engines or they drift.
    """
    text = unicodedata.normalize("NFD", str(description))
    text = _COMBINING.sub("", text)
    return _WHITESPACE.sub(" ", text).strip().lower()


def _compile(patterns) -> "re.Pattern":
    body = "|".join(patterns)
    return re.compile(f"(?<![{_WORD}])(?:{body})(?![{_WORD}])")


# ---------------------------------------------------------------------------
# Payment gateways
# ---------------------------------------------------------------------------
# These companies process payments *for* other merchants: "Nuvei Limited" or
# "Pagamento Eupago Instituicao Pagamento Lda" tells you a payment happened and
# nothing whatsoever about what was bought. Guessing a category from them would
# be inventing data, so they short-circuit straight to the review queue.
#
# SumUp and IfThenPay are deliberately absent: their descriptions carry the
# real merchant after the prefix ("Sumup *lovecraft"), so an override on that
# merchant must be allowed to work.
GATEWAY_PATTERNS = [
    "nuvei", "easypay", "eupago", "safecharge", "payshop", "stripe",
    "adyen", "worldpay", "redunicre",
]
GATEWAY_RE = _compile(GATEWAY_PATTERNS)

# ---------------------------------------------------------------------------
# Refunds
# ---------------------------------------------------------------------------
# Money coming back with one of these words is a purchase being undone, not
# income (see REFUNDS in taxonomy.py). It is categorized through the EXPENSE
# path, so `Devolucao Zara Porto` reaches the `zara` rule and is filed under
# Lazer / Roupa, and the store keeps it as a negative expense. When the rest of
# the description names nothing the rules know, it lands in the review queue
# like any other unknown expense, and the human says what was bought.
REFUND_PATTERNS = ["devolucao", "devolucoes", "estorno", "estornos"]
REFUND_RE = _compile(REFUND_PATTERNS)


def is_refund(description, amount) -> bool:
    """Whether a raw bank row is a refund: money in, with a refund word.

    Mirrored by isRefund() in dashboard/index.html.
    """
    return amount > 0 and bool(REFUND_RE.search(normalize(description)))

# ---------------------------------------------------------------------------
# INCOME
# ---------------------------------------------------------------------------
PURPOSE_INCOME_RULES = [
    (["subsidio de alimentacao", "cartao alimentacao", "cheque refeicao",
      "ticket refeicao", "coverflex", "edenred"],
     "Salário Alimentação", "Salário Alimentação", "Cartão Alimentação"),

    (["ordenado", "salario", "vencimento", "remuneracao", "retroativo", "retroativos"],
     "Salário", "Salário", "Transferência"),

    # Refunds before subsidies: "Reembolsos Irs" contains both a refund word
    # and a tax word, and it is a repayment, not a benefit.
    (["irs", "reembolso irs", "reembolsos irs", "autoridade tributaria", "financas"],
     "Reembolsos", "IRS", "Transferência"),
    (["seguro", "seguros", "fidelidade", "tranquilidade", "ageas", "zurich", "generali"],
     "Reembolsos", "Seguros", "Transferência"),
    # `estorno` and `devolucao` used to be here too. They name a purchase being
    # undone, so they are refunds now (REFUND_PATTERNS below) and never reach
    # this table. A bare "reembolso" says nothing about a purchase and stays.
    (["reembolso", "reembolsos", "credito a favor"],
     "Reembolsos", "Estornos", "Transferência"),

    (["desemprego", "subsidio de desemprego", "seguranca social"],
     "Subsídios", "Desemprego", "Transferência"),
    (["subsidio", "subsidios", "abono"],
     "Subsídios", tx.CATCH_ALL_SUB, "Transferência"),
]

# ---------------------------------------------------------------------------
# EXPENSES
# ---------------------------------------------------------------------------
# Order is load-bearing in several places, each marked below. First match wins.
PURPOSE_EXPENSE_RULES = [
    # --- Bank costs -------------------------------------------------------
    # First, because "Comissão de disponibilização de cartão de débito" and
    # "Imposto do Selo sobre comissão" would otherwise be scanned against every
    # merchant pattern below for no reason.
    (["manutencao de conta", "comiss(?:ao|oes)", "imposto do selo", "imposto de selo",
      "despesas bancarias", "anuidade", "juros", "disponibilizacao de cartao",
      "taxa", "taxas", "alfandeg[a-z]*"],
     "Geral", "Comissões e Impostos", "Débito Direto"),

    (["levantamento", "levantamentos", "atm", "multibanco levantamento"],
     tx.UNCLASSIFIED_CATEGORY, "Levantamento", "Levantamento"),

    # --- Investments ------------------------------------------------------
    (["degiro", "trading ?212", "xtb", "etoro", "interactive brokers", "etf", "etfs",
      "xetra", "corretora"],
     "Investimentos", "ETFs/DEGIRO", "Transferência"),
    (["ppr", "sgf", "fundo de pens(?:ao|oes)", "fundos de pens(?:ao|oes)",
      "poupanca reforma", "gestora de fundo", "gestora fundo"],
     "Investimentos", "PPR", "Transferência"),

    # --- Food -------------------------------------------------------------
    (["continente", "pingo doce", "lidl", "aldi", "mercadona", "minipreco", "auchan",
      "intermarche", "jumbo", "recheio", "supermercado", "supermercato", "mercearia",
      "talho", "frutaria", "el corte ingles"],
     "Alimentação", "Compras", "Cartão"),
    # Delivery/fast-food before the café and restaurant blocks: "Uber Eats" must
    # not fall through to the `uber` transport rule, and "Pizza Hut" is not a
    # sit-down pizzaria.
    (["uber eats", "glovo", "bolt food", "mc ?donald[a-z]*", "burger king", "kfc",
      "telepizza", "pizza hut", "dominos", "champions burger", "mr dog[a-z]*",
      "smashville", "republica cachorros"],
     "Alimentação", "Take-away/Delivery", "Cartão"),
    (["padaria", "pastelaria", "confeitaria", "cafe", "caffe", "brunch", "gelataria",
      "queijaria", "chocolate", "doces", "uaucacau",
      "pequeno almoco", "pe almoco", "pequenos almocos"],
     "Alimentação", "Café/Padaria", "Cartão"),
    # Nightlife before restaurants: "Beer Kingdom" and "Bar da Pedra" are not
    # dinner. The reverse order was a known defect — every venue whose name
    # contained a food word was silently filed as a meal.
    # `cerveja` but not `cervejaria`: whole-word matching keeps them apart, and
    # in Portuguese a cervejaria is a restaurant while "cerveja" on its own is
    # a night out.
    (["discoteca", "boite", "nightclub", "pub", "bar", "bares", "cocktail", "cocktails",
      "beer", "cerveja", "cervejas", "jazz", "taberna", "tasquinha", "adega"],
     "Lazer", "Saídas Noite/Bares", "Cartão"),
    # The meal words at the end are the user's own shorthand from the Excel
    # seed ("Jantar c/ ...", "Almoço ...") rather than anything a bank writes.
    # They are still the most reliable purpose signal those rows have.
    (["restaurante", "restaurantes", "rest", "tasca", "churrasqueira", "churrasco",
      "marisqueira", "cervejaria", "pizzaria", "trattoria", "petisco", "petiscos",
      "bifanas", "brasao", "brasa", "grill", "sushi", "snack", "esplanada",
      "almoco", "almocos", "jantar", "jantares", "comida", "lanche", "refeicao",
      # `pizz[a-z]*` rather than `pizzaria`: the bank truncates, and one real
      # row reads "S Martino Douro Pizz".
      "pizz[a-z]*", "gaucho", "cantina", "montaditos", "areas portugal",
      "churrascaria", "marisco", "mariscos"],
     "Alimentação", "Restaurantes", "Cartão"),

    # --- Leisure ----------------------------------------------------------
    # Subscriptions before online shops: "Amazon Prime" is a subscription, and
    # a bare `amazon` rule above it would swallow it — that exact ordering bug
    # made Lazer/Subscrição unreachable for Prime.
    (["netflix", "spotify", "disney", "hbo", "max", "twitch", "youtube premium",
      "amazon prime", "crunchyroll", "playstation plus", "xbox game pass", "subscricao"],
     "Lazer", "Subscrições", "Cartão"),
    # `eneba` deliberately absent — it sells game keys, so it belongs to the
    # Gaming rule below. A keyword in two rules makes the later one unreachable.
    (["amazon", "ebay", "aliexpress", "shein", "temu", "asos", "zalando"],
     "Lazer", "Compras Online", "Cartão"),
    (["lego", "funko", "warhammer", "bandai", "fnac", "gamestop", "colecionaveis"],
     "Lazer", "LEGO/Pop-Culture/Memorabilia", "Cartão"),
    (["steam games", "steampowered", "playstation", "psn", "nintendo", "xbox",
      "epic games", "riot games", "blizzard", "ubisoft", "ea games", "fifa[a-z0-9]*",
      "eneba"],
     "Lazer", "Gaming", "Cartão"),
    (["escape room", "escape rooms"],
     "Lazer", "Escape Room", "Cartão"),
    # Before the telecom block: "NOS" is both a telecom brand and, via "NOS
    # Cinemas", a cinema chain — the specific match has to win.
    (["cinema", "cinemas", "uci", "teatro", "museu", "museus", "concerto", "concertos",
      "espetaculo", "espetaculos", "coliseu", "altice arena", "world of wine",
      "story centre", "comedia", "casino"],
     "Lazer", "Cinema/Espetáculos", "Cartão"),
    (["booking", "airbnb", "ryanair", "easyjet[a-z0-9]*", "tap", "latam", "vueling",
      "hotel", "hostel", "civitatis", "aeroporto", "aerop", "turismo", "viagem",
      "viagens", "ferias"],
     "Lazer", "Férias", "Cartão"),
    (["zara", "h&m", "primark", "bershka", "stradivarius", "pull & bear", "tiger",
      "pandora", "hawkers", "tedi", "sapataria", "boutique", "roupa", "roupas",
      "camisola", "carhart[a-z]*"],
     "Lazer", "Roupa", "Cartão"),
    # Activities with no sub-category of their own. They are unambiguously
    # leisure, and inventing "Bowling" / "Minigolfe" / "Karting" lines for a
    # handful of rows each is how a taxonomy stops being readable.
    (["bowling", "minigolfe", "mini golfe", "karting", "kart", "paintball",
      "trampolins", "arcade"],
     "Lazer", tx.CATCH_ALL_SUB, "Cartão"),

    # --- Sport ------------------------------------------------------------
    (["ginasio", "fitness", "holmes place", "solinca", "bhout", "gym", "smart club",
      "crossfit"],
     "Desporto", "Ginásio", "Cartão"),
    # `stadium`/`estadio` before the insurance rule below, because
    # "S700 - Allianz Stadium" is a football ground, not a policy.
    (["futebol", "balizas", "balizaslandia", "sport lisboa", "fc porto", "sporting",
      "benfica", "estadio", "stadium", "arena", "bilhete jogo"],
     "Desporto", "Futebol", "Cartão"),
    (["corrida", "corridas", "running", "maratona", "triatlo", "trail",
      "sao silvestre"],
     "Desporto", "Corrida", "Cartão"),
    (["decathlon", "sport zone", "sportino", "sokito", "nike", "adidas", "jd sports"],
     "Desporto", "Equipamento", "Cartão"),

    # --- Health -----------------------------------------------------------
    # Optics before pharmacy: "Well's Óptica" is glasses, not a chemist.
    (["lentes", "optica", "opticas", "oculos", "multiopticas", "opticalia",
      "alain afflelou", "oftalmolog[a-z]*"],
     "Saúde", "Lentes", "Cartão"),
    (["fisioterapia", "fisiatria", "osteopatia"],
     "Saúde", "Fisioterapia", "Cartão"),
    (["farmacia", "farmacias", "parafarmacia", "wells", "well s"],
     "Saúde", "Farmácia", "Cartão"),
    (["hospital", "clinica", "clin", "cuf", "lusiadas", "unilabs", "laboratorio",
      "analises", "dentista", "medicina dentaria", "consulta", "consultas",
      "medico", "medica"],
     "Saúde", "Consultas/Exames", "Cartão"),

    # --- Education --------------------------------------------------------
    (["livraria", "wook", "bertrand", "papelaria", "papel"],
     "Educação", "Livros/Material", "Cartão"),
    (["curso", "cursos", "formacao", "universidade", "propina", "propinas",
      "explicacoes", "academia"],
     "Educação", "Cursos/Formação", "Cartão"),

    # --- Gifts ------------------------------------------------------------
    (["prenda", "prendas", "presente", "presentes", "florista", "flores", "aniversario"],
     "Prendas", tx.CATCH_ALL_SUB, "Cartão"),

    # --- General / recurring ---------------------------------------------
    (["gasoleo", "gasolina", "combustivel", "combustiveis", "galp", "repsol", "cepsa",
      "prio", "bp"],
     "Geral", "Gasóleo", "Cartão"),
    # `uber(?! eats)` is belt-and-braces — the delivery rule above already
    # claims Uber Eats — but it keeps this rule correct if the order changes.
    (["uber(?! eats)", "bolt(?! food)", "taxi", "comboios", "cp comboios",
      "metro do porto", "stcp", "via verde", "portagem", "portagens", "brisa",
      "ascendi", "parquimetro", "empark", "estacionamento"],
     "Geral", "Transportes", "Cartão"),
    (["oficina", "pneus", "pneu", "inspecao", "revisao", "iuc", "stand auto",
      "auto reparacao", "bateria auto"],
     "Geral", "Carro", "Cartão"),
    # `vodaf[a-z]*` rather than `vodafone`: the bank truncates descriptions at
    # ~20 characters, so ten real rows say only "Carregamentos Vodafo" and a
    # whole-word `vodafone` can never reach them. `vdaf[a-z]*` catches the
    # user's own typo in the seeded rows.
    (["vodaf[a-z]*", "vdaf[a-z]*", "meo", "nowo", "nos", "telemovel",
      "telecomunicacoes", "carregamento telemovel"],
     "Geral", "Telemóvel", "Cartão"),
    # `allianz` alone is not enough — "Allianz Stadium" is a football ground,
    # and it was being filed as insurance.
    (["seguro", "seguros", "allianz seguros", "fidelidade", "tranquilidade", "ageas",
      "zurich", "generali", "una seguros"],
     "Geral", "Seguros", "Débito Direto"),
    (["renda", "condominio", "prestacao casa", "credito habitacao", "edp", "endesa",
      "iberdrola", "aguas de", "epal", "ikea", "leroy merlin", "energia", "energy",
      "gas natural", "galp energia"],
     "Geral", "Casa", "Débito Direto"),
    # The two platform sub-categories added to the taxonomy. Revolut is listed
    # here and NOT under Investimentos on purpose: a Revolut transfer is a
    # move to another account you hold, and what it is eventually spent on is
    # invisible from this side.
    (["revolut"], "Geral", "Revolut", "Transferência"),
    (["trade ?republic"], "Geral", "TradeRepublic", "Transferência"),
]

_COMPILED_INCOME = [(_compile(p), c, s, m) for p, c, s, m in PURPOSE_INCOME_RULES]
_COMPILED_EXPENSE = [(_compile(p), c, s, m) for p, c, s, m in PURPOSE_EXPENSE_RULES]

# ---------------------------------------------------------------------------
# Rails
# ---------------------------------------------------------------------------
_RAIL_MBWAY = _compile(["mbway", "mb way"])
_RAIL_TRANSFER = _compile(["transferencia", "transferencias", "trf", "trf imed"])
_RAIL_MEAL_CARD = _compile(["cartao alimentacao", "coverflex", "edenred"])

_MBWAY_NAME_RE = re.compile(r"mb\s*way\s+(?:para|de)\s+(.+)$", re.IGNORECASE)
_TRANSFER_NAME_RE = re.compile(r"transfer[êe]ncia\s+(?:para|de)\s+(.+)$", re.IGNORECASE)


def _clean_name(raw: str):
    name = raw.strip(" .")
    return name if name else None


def extract_counterparty(description: str):
    """The person on the other side of a transfer, or None.

    Kept even though the name is no longer used as a Sub-category (the store
    accumulated 71 of those, which is a phone book, not a taxonomy). It is what
    peer overrides are matched against, so a rule learns "Ana Silva" rather
    than the boilerplate around her.
    """
    for pattern in (_MBWAY_NAME_RE, _TRANSFER_NAME_RE):
        m = pattern.search(str(description))
        if m:
            name = _clean_name(m.group(1))
            if name:
                return name
    return None


def _overlay_method(normalized: str, suggested_method: str) -> str:
    """The rail is detected independently of purpose and always wins."""
    if _RAIL_MEAL_CARD.search(normalized):
        return "Cartão Alimentação"
    if _RAIL_MBWAY.search(normalized):
        return "MBWay"
    if _RAIL_TRANSFER.search(normalized):
        return "Transferência"
    return suggested_method


def _match_purpose(normalized: str, compiled_rules):
    for pattern, category, sub_category, suggested_method in compiled_rules:
        if pattern.search(normalized):
            return category, sub_category, suggested_method
    return None


def _match_override(normalized: str, overrides, txn_type: str, peer: bool = False):
    """First matching override of the requested kind, or None.

    Override keywords are user-typed plain text, not regex — they are escaped
    and normalized here so that a keyword saved as "Café Central" still matches
    a description the bank wrote as "CAFE CENTRAL".
    """
    for o in (overrides or []):
        if bool(o.get("peer")) is not peer:
            continue
        if o.get("type") not in (txn_type, "both"):
            continue
        keywords = [re.escape(normalize(k)) for k in o.get("keywords", []) if str(k).strip()]
        if keywords and _compile(keywords).search(normalized):
            return o["category"], o["sub_category"], o.get("method", "")
    return None


def categorize_transaction(description: str, amount: float, overrides=None) -> tuple:
    """Return (category, sub_category, method) for one raw transaction.

    amount > 0 uses the income rules, amount < 0 the expense rules — except a
    refund (is_refund), which is money in but answers "what was bought", so it
    goes through the expense rules and gets an expense pair. The result is
    always a pair that exists in taxonomy.py — when nothing matches, that pair
    is an honest "don't know" (Outros / Por Classificar) rather than a guess,
    and the dashboard's review queue is built from exactly those rows.
    """
    normalized = normalize(description)
    is_income = amount > 0 and not REFUND_RE.search(normalized)
    txn_type = tx.TYPE_INCOME if is_income else tx.TYPE_EXPENSE
    default_rail = "Transferência" if is_income else "Cartão"

    # 1. Gateways name the processor, never the merchant — refuse to guess.
    if GATEWAY_RE.search(normalized):
        category, sub_category = tx.unclassified(txn_type)
        return category, sub_category, _overlay_method(normalized, default_rail)

    # 2. The user's own corrections. They decide the purpose, never the rail:
    # the gym costs the same whether you tapped a card or sent MBWay, and the
    # description says which.
    override_hit = _match_override(normalized, overrides, "income" if is_income else "expense")
    if override_hit:
        category, sub_category, method = override_hit
        return category, sub_category, _overlay_method(normalized, method or default_rail)

    # 3. Built-in rules.
    hit = _match_purpose(normalized, _COMPILED_INCOME if is_income else _COMPILED_EXPENSE)
    if hit:
        category, sub_category, suggested_method = hit
        return category, sub_category, _overlay_method(normalized, suggested_method)

    # 4. Fallback. A transfer to or from a named person with no purpose signal
    # is a real, known fact — it just isn't a spending category, so it gets the
    # taxonomy's bucket for exactly that instead of the review queue. The
    # sender/recipient stays in Notes.
    method = _overlay_method(normalized, default_rail)
    if method in ("MBWay", "Transferência"):
        name = extract_counterparty(description)
        peer_hit = _match_override(normalize(name or description), overrides,
                                   "income" if is_income else "expense", peer=True)
        if peer_hit:
            peer_category, peer_sub, _ = peer_hit
            return peer_category, peer_sub, method
        peer_category, peer_sub = tx.LEGACY_PEER_CATEGORIES[txn_type]
        if is_income:
            peer_sub = "MBWay" if method == "MBWay" else "Transferência"
        return peer_category, peer_sub, method

    category, sub_category = tx.unclassified(txn_type)
    return category, sub_category, method


def _validate_rules() -> None:
    """Every rule must name a pair that exists in the taxonomy.

    Runs at import. The point of a strict taxonomy is that nothing can write
    outside it, and the rule tables are the largest writer — a category renamed
    in taxonomy.py but not here should stop the program, not quietly produce a
    category that no chart knows about.
    """
    for rules, txn_type in ((PURPOSE_INCOME_RULES, tx.TYPE_INCOME),
                            (PURPOSE_EXPENSE_RULES, tx.TYPE_EXPENSE)):
        for patterns, category, sub_category, method in rules:
            tx.validate(txn_type, category, sub_category,
                        where=f"categorize.py rule {patterns[0]!r}: ")
            if method not in METHODS:
                raise ValueError(
                    f"categorize.py rule {patterns[0]!r}: {method!r} is not a known "
                    f"Method. Valid: {', '.join(METHODS)}"
                )


_validate_rules()
