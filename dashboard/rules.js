// AUTO-GENERATED — DO NOT EDIT BY HAND.
//
// Written by scripts/generate_dashboard_rules.py from finance_tracker/taxonomy.py
// and finance_tracker/categorize.py, which are the single source of truth for
// the taxonomy and the rule tables. Editing this file directly means the
// dashboard and the CLI categorize the same bank export differently — which is
// exactly what happened when these tables were maintained by hand.
//
// To change a rule: edit categorize.py (or taxonomy.py), then re-run
//   python3 scripts/generate_dashboard_rules.py


// ---- Taxonomy (finance_tracker/taxonomy.py) ----
// The complete list of Category -> Sub-category pairs that may exist.
// The review panel builds its pickers from this and refuses anything
// outside it, exactly like taxonomy.validate() does in Python.
const TAXONOMY = {
  "Expense": {
    "Saúde": [
      "Lentes",
      "Fisioterapia",
      "Farmácia",
      "Consultas/Exames",
      "Outros"
    ],
    "Investimentos": [
      "ETFs/DEGIRO",
      "PPR",
      "Outros"
    ],
    "Alimentação": [
      "Compras",
      "Restaurantes",
      "Café/Padaria",
      "Take-away/Delivery",
      "Outros"
    ],
    "Lazer": [
      "Escape Room",
      "Saídas Noite/Bares",
      "Férias",
      "Cinema/Espetáculos",
      "LEGO/Pop-Culture/Memorabilia",
      "Roupa",
      "Subscrições",
      "Compras Online",
      "Gaming",
      "Outros"
    ],
    "Educação": [
      "Cursos/Formação",
      "Livros/Material",
      "Outros"
    ],
    "Geral": [
      "Gasóleo",
      "Carro",
      "Telemóvel",
      "Transportes",
      "Casa",
      "Seguros",
      "Comissões e Impostos",
      "Revolut",
      "TradeRepublic",
      "Outros"
    ],
    "Desporto": [
      "Futebol",
      "Corrida",
      "Ginásio",
      "Equipamento",
      "Outros"
    ],
    "Prendas": [
      "Aniversário",
      "Natal",
      "Outros"
    ],
    "Cabelo": [
      "Cabeleireiro/Barbeiro",
      "Produtos",
      "Outros"
    ],
    "Outros": [
      "Por Classificar",
      "Outros",
      "Levantamento",
      "Transferências Pessoais"
    ]
  },
  "Income": {
    "Salário": [
      "Salário",
      "Outros"
    ],
    "Salário Alimentação": [
      "Salário Alimentação"
    ],
    "Transferências Pessoais": [
      "MBWay",
      "Transferência"
    ],
    "Subsídios": [
      "Desemprego",
      "Outros"
    ],
    "Reembolsos": [
      "IRS",
      "Seguros",
      "Estornos"
    ],
    "Outros": [
      "Por Classificar",
      "Outros"
    ]
  }
};

// ---- Legacy pairs (finance_tracker/taxonomy.py LEGACY_ALIASES) ----
// Keyed "Type|Category|sub-category" with the sub-category lowercased;
// a "*" sub-category matches any. resolvePair() below mirrors
// taxonomy.resolve().
const LEGACY_ALIASES = {
  "Expense|Refeição|supermercado": [
    "Alimentação",
    "Compras"
  ],
  "Expense|Refeição|continente": [
    "Alimentação",
    "Compras"
  ],
  "Expense|Refeição|pingo doce": [
    "Alimentação",
    "Compras"
  ],
  "Expense|Refeição|restaurante": [
    "Alimentação",
    "Restaurantes"
  ],
  "Expense|Refeição|jantar": [
    "Alimentação",
    "Restaurantes"
  ],
  "Expense|Refeição|almoço": [
    "Alimentação",
    "Restaurantes"
  ],
  "Expense|Refeição|padaria": [
    "Alimentação",
    "Café/Padaria"
  ],
  "Expense|Refeição|*": [
    "Alimentação",
    "Outros"
  ],
  "Expense|Necessário|combustível": [
    "Geral",
    "Gasóleo"
  ],
  "Expense|Necessário|gasoleo": [
    "Geral",
    "Gasóleo"
  ],
  "Expense|Necessário|telecomunicações": [
    "Geral",
    "Telemóvel"
  ],
  "Expense|Necessário|telemovel": [
    "Geral",
    "Telemóvel"
  ],
  "Expense|Necessário|seguros": [
    "Geral",
    "Seguros"
  ],
  "Expense|Necessário|habitação": [
    "Geral",
    "Casa"
  ],
  "Expense|Necessário|*": [
    "Geral",
    "Outros"
  ],
  "Expense|Comissões conta|*": [
    "Geral",
    "Comissões e Impostos"
  ],
  "Expense|Geral|levantamento": [
    "Outros",
    "Levantamento"
  ],
  "Expense|Geral|gasoleo": [
    "Geral",
    "Gasóleo"
  ],
  "Expense|Geral|prenda": [
    "Prendas",
    "Outros"
  ],
  "Expense|Geral|random": [
    "Outros",
    "Por Classificar"
  ],
  "Expense|Saúde|ginásio": [
    "Desporto",
    "Ginásio"
  ],
  "Expense|Saúde|consulta": [
    "Saúde",
    "Consultas/Exames"
  ],
  "Expense|Saúde|laboratório": [
    "Saúde",
    "Consultas/Exames"
  ],
  "Expense|Saúde|hospital luz": [
    "Saúde",
    "Consultas/Exames"
  ],
  "Expense|Saúde|wells": [
    "Saúde",
    "Farmácia"
  ],
  "Expense|Poupança/Investimento|ações/etf": [
    "Investimentos",
    "ETFs/DEGIRO"
  ],
  "Expense|Poupança/Investimento|ppr/fundo de pensões": [
    "Investimentos",
    "PPR"
  ],
  "Expense|Poupança/Investimento|ppr": [
    "Investimentos",
    "PPR"
  ],
  "Expense|Investimento|ppr": [
    "Investimentos",
    "PPR"
  ],
  "Expense|Investimento|*": [
    "Investimentos",
    "Outros"
  ],
  "Expense|Poupança/Investimento|*": [
    "Investimentos",
    "Outros"
  ],
  "Expense|Lazer|comida": [
    "Alimentação",
    "Restaurantes"
  ],
  "Expense|Lazer|supermercado": [
    "Alimentação",
    "Compras"
  ],
  "Expense|Lazer|saídas noite": [
    "Lazer",
    "Saídas Noite/Bares"
  ],
  "Expense|Lazer|cinema": [
    "Lazer",
    "Cinema/Espetáculos"
  ],
  "Expense|Lazer|viagem": [
    "Lazer",
    "Férias"
  ],
  "Expense|Lazer|subscrição": [
    "Lazer",
    "Subscrições"
  ],
  "Expense|Lazer|disney plus": [
    "Lazer",
    "Subscrições"
  ],
  "Expense|Lazer|twicth": [
    "Lazer",
    "Subscrições"
  ],
  "Expense|Lazer|eneba": [
    "Lazer",
    "Compras Online"
  ],
  "Expense|Lazer|encomendas - roupa": [
    "Lazer",
    "Roupa"
  ],
  "Expense|Lazer|prenda": [
    "Prendas",
    "Outros"
  ],
  "Expense|Lazer|bowling": [
    "Lazer",
    "Outros"
  ],
  "Expense|Lazer|museu": [
    "Lazer",
    "Cinema/Espetáculos"
  ],
  "Expense|Lazer|desporto": [
    "Desporto",
    "Outros"
  ],
  "Expense|Lazer|futebol": [
    "Desporto",
    "Futebol"
  ],
  "Expense|Lazer|desporto e diversão": [
    "Lazer",
    "Outros"
  ],
  "Income|Salário_alim|*": [
    "Salário Alimentação",
    "Salário Alimentação"
  ],
  "Income|Salário|transferência": [
    "Salário",
    "Salário"
  ],
  "Income|Dinheiro|mbway": [
    "Transferências Pessoais",
    "MBWay"
  ],
  "Income|Dinheiro|dinheiro": [
    "Transferências Pessoais",
    "MBWay"
  ],
  "Income|Dinheiro/MBWay|*": [
    "Transferências Pessoais",
    "MBWay"
  ],
  "Income|Outro|reembolso": [
    "Reembolsos",
    "Estornos"
  ],
  "Income|Outro|reembolsos irs": [
    "Reembolsos",
    "IRS"
  ]
};

const COLUMNS = ["transaction_id", "Date", "Type", "Category", "Sub-category", "Method", "Amount (€)", "Notes", "Review Note", "Reviewed At", "Month", "Year", "Source File"];
const TYPE_INCOME = "Income";
const TYPE_EXPENSE = "Expense";
const EXPENSE_CATEGORIES = ["Saúde", "Investimentos", "Alimentação", "Lazer", "Educação", "Geral", "Desporto", "Prendas", "Cabelo", "Outros"];
const INCOME_CATEGORIES = ["Salário", "Salário Alimentação", "Transferências Pessoais", "Subsídios", "Reembolsos", "Outros"];
const METHODS = ["Cartão", "MBWay", "Transferência", "Débito Direto", "Cartão Alimentação", "Dinheiro", "Levantamento", "Não especificado"];
const UNSPECIFIED_METHOD = "Não especificado";
const MEAL_CARD_METHOD = "Cartão Alimentação";
const SAVINGS_CATEGORY = "Investimentos";
const UNCLASSIFIED_CATEGORY = "Outros";
const UNCLASSIFIED_SUB = "Por Classificar";
const REVIEW_NOTE = "Review Note";
const REVIEWED_AT = "Reviewed At";

// ---- Rule tables (finance_tracker/categorize.py) ----
// Each rule: [patterns, category, sub_category, suggestedMethod].
// `patterns` are regex fragments matched against the NORMALIZED
// description (lowercased, accents stripped) with word boundaries
// added by compileRule(). The suggested method is a default only —
// the rail is detected separately by overlayMethod() and wins
// whenever the description names one.
const GATEWAY_PATTERNS = ["nuvei", "easypay", "eupago", "safecharge", "payshop", "stripe", "adyen", "worldpay", "redunicre"];

const PURPOSE_INCOME_RULES = [
  [["subsidio de alimentacao", "cartao alimentacao", "cheque refeicao", "ticket refeicao", "coverflex", "edenred"], "Salário Alimentação", "Salário Alimentação", "Cartão Alimentação"],
  [["ordenado", "salario", "vencimento", "remuneracao", "retroativo", "retroativos"], "Salário", "Salário", "Transferência"],
  [["irs", "reembolso irs", "reembolsos irs", "autoridade tributaria", "financas"], "Reembolsos", "IRS", "Transferência"],
  [["seguro", "seguros", "fidelidade", "tranquilidade", "ageas", "zurich", "generali"], "Reembolsos", "Seguros", "Transferência"],
  [["reembolso", "reembolsos", "estorno", "devolucao", "credito a favor"], "Reembolsos", "Estornos", "Transferência"],
  [["desemprego", "subsidio de desemprego", "seguranca social"], "Subsídios", "Desemprego", "Transferência"],
  [["subsidio", "subsidios", "abono"], "Subsídios", "Outros", "Transferência"],
];

const PURPOSE_EXPENSE_RULES = [
  [["manutencao de conta", "comiss(?:ao|oes)", "imposto do selo", "imposto de selo", "despesas bancarias", "anuidade", "juros", "disponibilizacao de cartao", "taxa", "taxas", "alfandeg[a-z]*"], "Geral", "Comissões e Impostos", "Débito Direto"],
  [["levantamento", "levantamentos", "atm", "multibanco levantamento"], "Outros", "Levantamento", "Levantamento"],
  [["degiro", "trading ?212", "xtb", "etoro", "interactive brokers", "etf", "etfs", "xetra", "corretora"], "Investimentos", "ETFs/DEGIRO", "Transferência"],
  [["ppr", "sgf", "fundo de pens(?:ao|oes)", "fundos de pens(?:ao|oes)", "poupanca reforma", "gestora de fundo", "gestora fundo"], "Investimentos", "PPR", "Transferência"],
  [["continente", "pingo doce", "lidl", "aldi", "mercadona", "minipreco", "auchan", "intermarche", "jumbo", "recheio", "supermercado", "supermercato", "mercearia", "talho", "frutaria", "el corte ingles"], "Alimentação", "Compras", "Cartão"],
  [["uber eats", "glovo", "bolt food", "mc ?donald[a-z]*", "burger king", "kfc", "telepizza", "pizza hut", "dominos", "champions burger", "mr dog[a-z]*", "smashville", "republica cachorros"], "Alimentação", "Take-away/Delivery", "Cartão"],
  [["padaria", "pastelaria", "confeitaria", "cafe", "caffe", "brunch", "gelataria", "queijaria", "chocolate", "doces", "uaucacau", "pequeno almoco", "pe almoco", "pequenos almocos"], "Alimentação", "Café/Padaria", "Cartão"],
  [["discoteca", "boite", "nightclub", "pub", "bar", "bares", "cocktail", "cocktails", "beer", "cerveja", "cervejas", "jazz", "taberna", "tasquinha", "adega"], "Lazer", "Saídas Noite/Bares", "Cartão"],
  [["restaurante", "restaurantes", "rest", "tasca", "churrasqueira", "churrasco", "marisqueira", "cervejaria", "pizzaria", "trattoria", "petisco", "petiscos", "bifanas", "brasao", "brasa", "grill", "sushi", "snack", "esplanada", "almoco", "almocos", "jantar", "jantares", "comida", "lanche", "refeicao", "pizz[a-z]*", "gaucho", "cantina", "montaditos", "areas portugal", "churrascaria", "marisco", "mariscos"], "Alimentação", "Restaurantes", "Cartão"],
  [["netflix", "spotify", "disney", "hbo", "max", "twitch", "youtube premium", "amazon prime", "crunchyroll", "playstation plus", "xbox game pass", "subscricao"], "Lazer", "Subscrições", "Cartão"],
  [["amazon", "ebay", "aliexpress", "shein", "temu", "asos", "zalando"], "Lazer", "Compras Online", "Cartão"],
  [["lego", "funko", "warhammer", "bandai", "fnac", "gamestop", "colecionaveis"], "Lazer", "LEGO/Pop-Culture/Memorabilia", "Cartão"],
  [["steam games", "steampowered", "playstation", "psn", "nintendo", "xbox", "epic games", "riot games", "blizzard", "ubisoft", "ea games", "fifa[a-z0-9]*", "eneba"], "Lazer", "Gaming", "Cartão"],
  [["escape room", "escape rooms"], "Lazer", "Escape Room", "Cartão"],
  [["cinema", "cinemas", "uci", "teatro", "museu", "museus", "concerto", "concertos", "espetaculo", "espetaculos", "coliseu", "altice arena", "world of wine", "story centre", "comedia", "casino"], "Lazer", "Cinema/Espetáculos", "Cartão"],
  [["booking", "airbnb", "ryanair", "easyjet[a-z0-9]*", "tap", "latam", "vueling", "hotel", "hostel", "civitatis", "aeroporto", "aerop", "turismo", "viagem", "viagens", "ferias"], "Lazer", "Férias", "Cartão"],
  [["zara", "h&m", "primark", "bershka", "stradivarius", "pull & bear", "tiger", "pandora", "hawkers", "tedi", "sapataria", "boutique", "roupa", "roupas", "camisola", "carhart[a-z]*"], "Lazer", "Roupa", "Cartão"],
  [["bowling", "minigolfe", "mini golfe", "karting", "kart", "paintball", "trampolins", "arcade"], "Lazer", "Outros", "Cartão"],
  [["ginasio", "fitness", "holmes place", "solinca", "bhout", "gym", "smart club", "crossfit"], "Desporto", "Ginásio", "Cartão"],
  [["futebol", "balizas", "balizaslandia", "sport lisboa", "fc porto", "sporting", "benfica", "estadio", "stadium", "arena", "bilhete jogo"], "Desporto", "Futebol", "Cartão"],
  [["corrida", "corridas", "running", "maratona", "triatlo", "trail", "sao silvestre"], "Desporto", "Corrida", "Cartão"],
  [["decathlon", "sport zone", "sportino", "sokito", "nike", "adidas", "jd sports"], "Desporto", "Equipamento", "Cartão"],
  [["lentes", "optica", "opticas", "oculos", "multiopticas", "opticalia", "alain afflelou", "oftalmolog[a-z]*"], "Saúde", "Lentes", "Cartão"],
  [["fisioterapia", "fisiatria", "osteopatia"], "Saúde", "Fisioterapia", "Cartão"],
  [["farmacia", "farmacias", "parafarmacia", "wells", "well s"], "Saúde", "Farmácia", "Cartão"],
  [["hospital", "clinica", "clin", "cuf", "lusiadas", "unilabs", "laboratorio", "analises", "dentista", "medicina dentaria", "consulta", "consultas", "medico", "medica"], "Saúde", "Consultas/Exames", "Cartão"],
  [["livraria", "wook", "bertrand", "papelaria", "papel"], "Educação", "Livros/Material", "Cartão"],
  [["curso", "cursos", "formacao", "universidade", "propina", "propinas", "explicacoes", "academia"], "Educação", "Cursos/Formação", "Cartão"],
  [["prenda", "prendas", "presente", "presentes", "florista", "flores", "aniversario"], "Prendas", "Outros", "Cartão"],
  [["gasoleo", "gasolina", "combustivel", "combustiveis", "galp", "repsol", "cepsa", "prio", "bp"], "Geral", "Gasóleo", "Cartão"],
  [["uber(?! eats)", "bolt(?! food)", "taxi", "comboios", "cp comboios", "metro do porto", "stcp", "via verde", "portagem", "portagens", "brisa", "ascendi", "parquimetro", "empark", "estacionamento"], "Geral", "Transportes", "Cartão"],
  [["oficina", "pneus", "pneu", "inspecao", "revisao", "iuc", "stand auto", "auto reparacao", "bateria auto"], "Geral", "Carro", "Cartão"],
  [["vodaf[a-z]*", "vdaf[a-z]*", "meo", "nowo", "nos", "telemovel", "telecomunicacoes", "carregamento telemovel"], "Geral", "Telemóvel", "Cartão"],
  [["seguro", "seguros", "allianz seguros", "fidelidade", "tranquilidade", "ageas", "zurich", "generali", "una seguros"], "Geral", "Seguros", "Débito Direto"],
  [["renda", "condominio", "prestacao casa", "credito habitacao", "edp", "endesa", "iberdrola", "aguas de", "epal", "ikea", "leroy merlin", "energia", "energy", "gas natural", "galp energia"], "Geral", "Casa", "Débito Direto"],
  [["revolut"], "Geral", "Revolut", "Transferência"],
  [["trade ?republic"], "Geral", "TradeRepublic", "Transferência"],
];
