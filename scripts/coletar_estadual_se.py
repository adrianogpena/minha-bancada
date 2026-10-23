"""
Deputados estaduais de Sergipe (Alese), fora do SAPL.

Fonte aberta e lida aqui:
  - deputados (nome, partido, foto, link da ficha no Alese Legis): carrossel da página inicial https://al.se.leg.br/ ;
    a Alese não publica nome civil nem e-mail nessa página: o nome civil vem dos eleitos de 2022 do TSE (dados/tse/2022/SE.json)
    quando um só nome casa.

Não coletado:
  - Alese Legis (https://aleselegis.al.se.leg.br: fichas, proposições, votações, presença) não respondeu (timeout) em duas tentativas;
  - ressarcimento dos deputados, diárias e subsídios/remuneração: um PDF por mês no portal da transparência (só PDF);
  - emendas parlamentares: página aponta para um painel Power BI do Executivo.
"""

import re
from html import unescape

import estaduais_comum as comum

UF = "SE"
HOME = "https://al.se.leg.br/"
FICHA = "https://aleselegis.al.se.leg.br/spl/parlamentar.aspx?id={}"
TSE_ARQUIVO = comum.arquivo_tse(UF)
TITULOS = {"dr", "dra", "prof", "profa", "dep"}
SINONIMOS = {"junior": "jr", "jr": "jr"}


def deputados_da_pagina(html: str) -> list[dict]:
    """Deputados do carrossel da página inicial (o carrossel repete cartões; vale um por id do Alese Legis)."""
    achados = {}
    for cartao in re.findall(r'<article class="qodef-portfolio-item.*?</article>', html, re.S):
        ident = re.search(r"parlamentar\.aspx\?id=(\d+)", cartao)
        titulo = re.search(r'<h4 class="qodef-item-title">(.*?)</h4>', cartao, re.S)
        if not ident or not titulo or not comum.limpar(titulo.group(1)):
            continue
        partido = re.search(r'qodef-ptf-category-holder"><span>(.*?)</span>', cartao, re.S)
        foto = re.search(r'<img[^>]*?\bsrc="([^"]+)"', cartao)
        nome = comum.limpar(titulo.group(1))
        achados.setdefault(ident.group(1), {"id": ident.group(1), "nome": nome, "nomeCivil": nome, "foto": unescape(foto.group(1)) if foto else None,
                                            "email": None, "titular": True, "partido": comum.limpar(partido.group(1)) if partido else None,
                                            "fonte": FICHA.format(ident.group(1))})
    return sorted(achados.values(), key=lambda d: comum.sem_acento(d["nome"]))


def _palavras(nome: str) -> list[str]:
    return [SINONIMOS.get(p, p) for p in re.sub(r"[^a-z ]", " ", comum.sem_acento(nome)).split() if p not in TITULOS]


def _casam(nome_alese: str, nome_tse: str) -> bool:
    a, b = _palavras(nome_alese), _palavras(nome_tse)
    if not a or not b:
        return False
    return "".join(a) == "".join(b) or set(b) <= set(a) or set(a) <= set(b)


def completar_com_tse(deputados: list[dict], eleitos: list[dict]) -> None:
    """Preenche `nomeCivil` com o nome do TSE quando um só eleito de 2022 casa com o nome da Alese (a Alese não publica o nome civil)."""
    for d in deputados:
        achados = [e for e in eleitos if _casam(d["nome"], e.get("urna") or "") or _casam(d["nome"], e["nome"])]
        if len(achados) == 1:
            d["nomeCivil"] = achados[0]["nome"]


def eleitos_do_tse() -> list[dict]:
    return comum.eleitos_tse(TSE_ARQUIVO)


def coletar() -> None:
    pasta = comum.DADOS / UF
    r = comum.sessao().get(HOME, timeout=30)
    r.raise_for_status()
    deputados = deputados_da_pagina(r.text)
    if not deputados:
        comum.avisar("SE: nenhum deputado na página inicial da Alese")
        return
    completar_com_tse(deputados, eleitos_do_tse())
    comum.salvar(pasta / "deputados.json", {"fonte": HOME, "host": None, "legislatura": "2023-2027", "deputados": deputados})
    print(f"SE: {len(deputados)} deputados")


def _contrato_deputados(ctx):
    r = comum.sessao().get(HOME, timeout=30)
    r.raise_for_status()
    return {"trecho": "\n".join(re.findall(r'<article class="qodef-portfolio-item.*?</article>', r.text, re.S)[:3])}


def _conferir_deputados(registro):
    falhas = []
    deputados = deputados_da_pagina(registro["trecho"])
    if not deputados:
        falhas.append("página inicial sem cartões de deputado (link do Alese Legis + nome)")
    for d in deputados:
        if not d["partido"]:
            falhas.append(f"cartão sem partido: {d['nome']}")
        if not d["foto"]:
            falhas.append(f"cartão sem foto: {d['nome']}")
    return falhas, []


CONTRATOS = [{"nome": "estadual_se_deputados", "fonte": HOME, "buscar": _contrato_deputados, "html": _conferir_deputados}]


if __name__ == "__main__":
    comum.principal(coletar)
