"""
Resumo oficial das leis citadas nas proposições: a ementa de cada lei, lida no LexML (https://www.lexml.gov.br/urn/urn:lex:br:federal:...),
que também aponta o texto no Planalto, no Senado e na Câmara.

Quais leis: as citadas (com data completa) na ementa e na ementa detalhada das proposições da Câmara e nas matérias do Senado
(leis.py extrai a citação e monta a URN). Grava dados/leis.json: {id da lei: {rotulo, urn, ementa, planalto, consultadoEm}}.
O id vem de leis.py (`ids.gerar_id("lei", "lexml", urn)`).

Lei já com ementa não é consultada de novo (a ementa de uma lei não muda). Lei sem ementa na resposta é tentada outra vez depois de
RENOVAR_VAZIAS_DIAS. Cada execução consulta no máximo ORCAMENTO_LEIS, com pausa entre consultas.

Uso:
    python scripts/coletar_leis.py
"""

import datetime as dt
import html
import re
import time
from pathlib import Path

import estaduais_comum as comum
import leis

DADOS = Path(__file__).resolve().parent.parent / "dados"
ORCAMENTO_LEIS = 400
RENOVAR_VAZIAS_DIAS = 14
PAUSA = 0.5


def textos_citantes(dados: Path = DADOS) -> list[str]:
    """Ementas e ementas detalhadas onde uma lei pode estar citada."""
    saida = []
    for arq in sorted((dados / "proposicoes_cadastro").glob("*.json")):
        saida += [l[2] for l in (comum.ler(arq, {}) or {}).values() if len(l) > 2 and l[2]]
    for det in (comum.ler(dados / "proposicoes_detalhe.json", {}) or {}).values():
        saida += [det.get(c) for c in ("ementa", "ementaDetalhada") if det.get(c)]
    for itens in (comum.ler(dados / "senado_autorias.json", {}) or {}).values():
        saida += [i.get("ementa") for i in itens if i.get("ementa")]
    return saida


def citadas(textos) -> dict[str, dict]:
    achadas = {}
    for t in textos:
        for lei in leis.citacoes(t):
            achadas.setdefault(lei["id"], lei)
    return achadas


def ler_pagina(pagina: str) -> dict:
    """Ementa e link do Planalto da página de uma norma no LexML (a ementa fica na linha 'Ementa' da tabela de metadados)."""
    m = re.search(r"<strong>Ementa</strong></div>\s*<div[^>]*>(.*?)</div>", pagina, re.S)
    ementa = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", m.group(1))).split()) if m else None
    p = re.search(r'href="(https?://(?:www\.|legislacao\.)?planalto\.gov\.br[^"]*)"', pagina)
    return {"ementa": ementa or None, "planalto": html.unescape(p.group(1)) if p else None}


def coletar(dados: Path = DADOS, sessao=None, hoje: dt.date | None = None) -> dict:
    hoje = hoje or dt.date.today()
    arquivo = dados / "leis.json"
    cache = comum.ler(arquivo, {}) or {}
    achadas = citadas(textos_citantes(dados))
    limite = (hoje - dt.timedelta(days=RENOVAR_VAZIAS_DIAS)).isoformat()
    fila = [i for i in achadas if i not in cache
            or (not cache[i].get("ementa") and cache[i].get("consultadoEm", "") < limite)][:ORCAMENTO_LEIS]
    print(f"Leis citadas: {len(achadas)}, no cache: {len(achadas.keys() & cache.keys())}; consultando {len(fila)}")
    s = sessao or comum.sessao(1)
    feitas = 0
    for i in fila:
        lei = achadas[i]
        try:
            pagina = comum.get(s, leis.url_lexml(lei["urn"]), timeout=40).text
            cache[i] = {"rotulo": lei["rotulo"], "urn": lei["urn"], **{k: v for k, v in ler_pagina(pagina).items() if v},
                        "consultadoEm": hoje.isoformat()}
            feitas += 1
        except Exception as e:
            comum.avisar(f"lei {lei['rotulo']}: {e}")
        if feitas % 50 == 0:
            comum.salvar(arquivo, cache)
        time.sleep(PAUSA)
    comum.salvar(arquivo, cache)
    print(f"Leis salvas: {feitas} novas, {len(cache)} no cache")
    return cache


if __name__ == "__main__":
    coletar()
