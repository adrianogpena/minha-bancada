"""
Lista fixa de categorias de despesa: a mesma para Câmara, Senado e Assembleias, para comparar gasto entre casas.

`categoria_id(rotulo)` devolve o id da lista para o rótulo que a fonte usa ("A - COMBUSTÍVEIS E LUBRIFICANTES",
"Locomoção, hospedagem"...). O rótulo da fonte não se perde: os coletores gravam o original (`categoria` das verbas, `tipo` das
despesas) e o `gerar*` junta por id, guardando os rótulos originais ao lado. Rótulo que nenhuma regra reconhece vira `outros` e
entra em `DESCONHECIDAS` (o `gerar.py` avisa no fim); para cobri-lo, acrescente uma palavra a `REGRAS` e um caso em
tests/test_categorias.py. Não acessa a internet.

`REGRAS` é uma lista ordenada de (id, palavras): vale a primeira cujas palavras (sem acento, minúsculas) aparecem no rótulo. A ordem
resolve rótulos que misturam assuntos: "software" vem antes de "segurança" e de "internet" (o item do Senado que fala de material,
software e despesas postais é material), "locomoção" vem antes de "combustíveis" (idem, "Locomoção, hospedagem, alimentação,
combustíveis e lubrificantes"), "imóvel/aluguel" vem antes de "telefone" ("Imóvel de apoio (aluguel, condomínio, telefone...)").
"""

import re
import unicodedata

DESCONHECIDAS: set = set()   # rótulos que nenhuma regra reconheceu neste processo

CATEGORIAS = {
    "imovel": "Imóvel e escritório de apoio",
    "locomocao": "Passagens, locomoção, hospedagem e alimentação",
    "veiculos": "Veículos (locação, fretamento e manutenção)",
    "combustivel": "Combustíveis e lubrificantes",
    "comunicacao": "Divulgação da atividade parlamentar",
    "consultoria": "Consultorias, assessorias, pesquisas e trabalhos técnicos",
    "telecom": "Telefonia e internet",
    "material": "Material de expediente, informática, software e equipamentos",
    "publicacoes": "Assinaturas, publicações e serviços postais",
    "graficos": "Serviços gráficos e reprografia",
    "seguranca": "Segurança",
    "eventos": "Cursos, eventos e inscrições",
    "diarias": "Diárias",
    "pessoal": "Pessoal de gabinete",
    "sem_detalhe": "Reembolso ou verba sem detalhamento da fonte",
    "outros": "Outros",
}

REGRAS = [
    ("sem_detalhe", ("sem detalhamento", "reembolso de despesas indenizatorias", "cota parlamentar (reembolso)", "verba indenizatoria",
                     "indenizacoes")),
    ("pessoal", ("verba de gabinete", "pessoal de gabinete")),
    ("diarias", ("diaria",)),
    ("material", ("software", "licenca de uso")),
    ("locomocao", ("locomocao",)),
    ("imovel", ("imovel", "imoveis", "aluguel", "condominio", "iptu", "util.publica", "moradia", "coworking", "espaco compartilhado",
                "manutencao de bens")),
    ("comunicacao", ("divulgacao", "comunicacao", "imprensa", "publicidade")),
    ("graficos", ("grafic", "copias", "reprografia", "impressos")),
    ("telecom", ("telefon", "celular", "internet", "telecom", "pacote de dados")),
    ("publicacoes", ("assinatura", "periodico", "jornais", "revistas", "publicacoes", "clipping", "postais", "correspondencia", "telegrama")),
    ("seguranca", ("seguranca", "vigilancia")),
    ("eventos", ("curso", "palestra", "seminario", "congresso", "evento", "inscric", "participacao")),
    ("consultoria", ("consultoria", "assessoria", "pesquisa", "trabalhos tecnicos", "servicos tecnicos", "contabilidade", "juridic")),
    ("combustivel", ("combustiv", "lubrificante", "abastecimento")),
    ("veiculos", ("veiculo", "fretamento", "aeronave", "embarcac")),
    ("locomocao", ("passage", "hospedagem", "alimentacao", "refeicao", "taxi", "pedagio", "estacionamento", "transporte", "viagem",
                   "aereo", "bilhete")),
    ("material", ("material", "expediente", "suprimento", "informatica", "equipamento", "moveis", "almoxarifado", "consumo")),
    ("imovel", ("energia", "agua e esgoto", "agua,", "residuos", "coleta de lixo", "escritorio de apoio", "predial")),
    ("outros", ("outros", "anulacao de empenho", "rubrica")),
]


def _sem_acento(texto: str) -> str:
    t = unicodedata.normalize("NFD", texto or "")
    return " ".join("".join(c for c in t if unicodedata.category(c) != "Mn").lower().split())


def categoria_id(rotulo: str | None) -> str:
    """Id de `CATEGORIAS` para o rótulo da fonte. Vazio -> `sem_detalhe`; sem regra -> `outros` (e entra em `DESCONHECIDAS`)."""
    texto = _sem_acento(rotulo)
    if not texto:
        return "sem_detalhe"
    for cid, palavras in REGRAS:
        if any(p in texto for p in palavras):
            return cid
    DESCONHECIDAS.add(re.sub(r"\s+", " ", rotulo.strip()))
    return "outros"


def agrupar(valores) -> list[dict]:
    """[{id, categoria, total, originais: [[rótulo da fonte, total]]}] de {rótulo da fonte: total}, do maior para o menor."""
    por_id: dict = {}
    for rotulo, total in valores.items():
        grupo = por_id.setdefault(categoria_id(rotulo), {"total": 0.0, "originais": {}})
        grupo["total"] += total
        chave = (rotulo or "").strip() or "Sem categoria"
        grupo["originais"][chave] = grupo["originais"].get(chave, 0.0) + total
    return [{"id": cid, "categoria": CATEGORIAS[cid], "total": round(g["total"], 2),
             "originais": [[r, round(t, 2)] for r, t in sorted(g["originais"].items(), key=lambda kv: -kv[1])]}
            for cid, g in sorted(por_id.items(), key=lambda kv: -kv[1]["total"])]
