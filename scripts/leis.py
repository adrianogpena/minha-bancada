"""
Leis citadas no texto de uma proposição ("Altera a Lei nº 9.250, de 26 de dezembro de 1995, ..."): extrai a citação, monta o
identificador oficial (URN LEX, padrão do LexML) e o id estável da lei. Não acessa a internet; o resumo da lei (a ementa oficial)
vem de coletar_leis.py, que grava dados/leis.json, e o link vai para o resolvedor do LexML, que leva ao texto no Planalto, no Senado
e na Câmara.

Só vale citação com data completa ("de 26 de dezembro de 1995"): sem a data não há URN, e adivinhar levaria à lei errada.

    citacoes(texto)        -> [{"id", "rotulo", "urn", "tipo", "numero", "data"}] na ordem do texto, sem repetir
    url_lexml(urn)         -> https://www.lexml.gov.br/urn/<urn>

O id é `ids.gerar_id("lei", "lexml", urn)`: sai só do tipo, da data e do número, então não muda ao reprocessar.
"""

import re

import ids

LEXML = "https://www.lexml.gov.br/urn"

# rótulo no texto (em minúsculas, sem acento) -> (tipo na URN, como aparece no rótulo)
TIPOS = {
    "lei complementar": ("lei.complementar", "Lei Complementar"),
    "lei delegada": ("lei.delegada", "Lei Delegada"),
    "decreto-lei": ("decreto.lei", "Decreto-Lei"),
    "decreto legislativo": ("decreto.legislativo", "Decreto Legislativo"),
    "decreto": ("decreto", "Decreto"),
    "medida provisoria": ("medida.provisoria", "Medida Provisória"),
    "emenda constitucional": ("emenda.constitucional", "Emenda Constitucional"),
    "lei": ("lei", "Lei"),
}
MESES = {m: i for i, m in enumerate(
    "janeiro fevereiro março abril maio junho julho agosto setembro outubro novembro dezembro".split(), 1)}
CONSTITUICAO = {"id_original": "br:federal:constituicao:1988-10-05;1988", "rotulo": "Constituição Federal de 1988",
                "tipo": "constituicao", "numero": "1988", "data": "1988-10-05"}

_TIPO = "|".join(sorted((t.replace(" ", r"\s+") for t in ("Lei Complementar", "Lei Delegada", "Decreto-Lei", "Decreto Legislativo",
                                                          "Decreto", "Medida Provisória", "Emenda Constitucional", "Lei")), key=len, reverse=True))
CITACAO = re.compile(
    rf"\b({_TIPO})\s+(?:federal\s+)?n[ºo°.]*\s*([\d.]+(?:-[A-Za-z0-9]{{1,2}})?)(?:\s*/\s*\d{{2,4}})?\s*,?\s+de\s+(\d{{1,2}})[ºo°]?\s+de\s+([A-Za-zçÇ]+)\s+de\s+(\d{{4}})",
    re.IGNORECASE)
CONSTITUICAO_NO_TEXTO = re.compile(r"\bConstitui[çc][ãa]o\s+(?:Federal|da\s+Rep[úu]blica)\b", re.IGNORECASE)


def _chave_tipo(texto: str) -> str:
    return " ".join(texto.lower().replace("ó", "o").split())


def url_lexml(urn: str) -> str:
    return f"{LEXML}/urn:lex:{urn}"


def _lei(tipo: str, numero: str, ano: int, mes: int, dia: int) -> dict:
    urn_tipo, rotulo_tipo = TIPOS[tipo]
    num = numero.replace(".", "").upper().lstrip("0") or "0"
    data = f"{ano:04d}-{mes:02d}-{dia:02d}"
    n_rotulo = f"{int(num):,}".replace(",", ".") if num.isdigit() else num
    if num.isdigit() is False and "-" in num:       # 2.200-2: milhar só na parte antes do hífen
        base, _, sufixo = num.partition("-")
        n_rotulo = (f"{int(base):,}".replace(",", ".") if base.isdigit() else base) + "-" + sufixo
    return {"urn": f"br:federal:{urn_tipo}:{data};{num.lower()}", "rotulo": f"{rotulo_tipo} nº {n_rotulo}/{ano}",
            "tipo": urn_tipo, "numero": num, "data": data}


def citacoes(texto: str | None) -> list[dict]:
    """Leis citadas no texto, na ordem em que aparecem e sem repetir. Cada uma: id, rótulo ("Lei nº 9.250/1995"), urn, tipo, número e data."""
    achados = []
    for m in CITACAO.finditer(texto or ""):
        mes = MESES.get(m.group(4).lower())
        dia, ano = int(m.group(3)), int(m.group(5))
        if not mes or not 1 <= dia <= 31 or not 1800 <= ano <= 2100:
            continue
        achados.append((m.start(), _lei(_chave_tipo(m.group(1)), m.group(2), ano, mes, dia)))
    for m in CONSTITUICAO_NO_TEXTO.finditer(texto or ""):
        achados.append((m.start(), {"urn": CONSTITUICAO["id_original"], "rotulo": CONSTITUICAO["rotulo"], "tipo": CONSTITUICAO["tipo"],
                                    "numero": CONSTITUICAO["numero"], "data": CONSTITUICAO["data"]}))
    saida, vistas = [], set()
    for _, lei in sorted(achados, key=lambda x: x[0]):
        if lei["urn"] in vistas:
            continue
        vistas.add(lei["urn"])
        saida.append({"id": ids.gerar_id("lei", "lexml", lei["urn"]), **lei})
    return saida


def de_textos(*textos: str | None) -> list[dict]:
    """Leis citadas em vários textos (ementa, ementa detalhada), sem repetir."""
    vistas, saida = set(), []
    for t in textos:
        for lei in citacoes(t):
            if lei["id"] not in vistas:
                vistas.add(lei["id"])
                saida.append(lei)
    return saida
