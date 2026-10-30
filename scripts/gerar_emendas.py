"""
Emendas parlamentares de cada deputado e senador: site/dados/emendas/<pessoa>.json, a partir de `nucleo["emendas"]`
(identidades.ligar_emendas, que lê dados/emendas/<ano>.json do coletar_emendas.py). Sem internet.

Arquivo da pessoa: {anos:[{ano, n, empenhado, liquidado, pago}] (mais recente primeiro),
municipios:[{nome, uf, empenhado, pago, n}] (os 15 de maior valor empenhado), itens:[{codigo, ano, tipo, numero, local, funcao, subfuncao,
empenhado, liquidado, pago}]}. Valores em reais; o link da fonte de cada ano é montado no site.
"""

from collections import defaultdict
from pathlib import Path

import estaduais_comum as comum

MUNICIPIOS_EXIBIDOS = 15
CAMPOS_ITEM = ("codigo", "ano", "tipo", "numero", "local", "funcao", "subfuncao", "empenhado", "liquidado", "pago")


def soma(itens: list[dict], campo: str) -> float:
    return round(sum(i.get(campo) or 0 for i in itens), 2)


def construir(emendas: list[dict]) -> dict[str, dict]:
    """{pessoa: arquivo}. `emendas`: itens ligados, cada um com `pessoa`."""
    por_pessoa = defaultdict(list)
    for e in emendas:
        por_pessoa[e["pessoa"]].append(e)
    saida = {}
    for pid, itens in por_pessoa.items():
        por_ano, por_local = defaultdict(list), defaultdict(list)
        for i in itens:
            por_ano[i["ano"]].append(i)
            if i.get("municipio"):
                por_local[(i["municipio"], i["uf"])].append(i)
        municipios = sorted(
            ({"nome": m, "uf": uf, "empenhado": soma(x, "empenhado"), "pago": soma(x, "pago"), "n": len(x)} for (m, uf), x in por_local.items()),
            key=lambda m: (-m["empenhado"], m["nome"]))[:MUNICIPIOS_EXIBIDOS]
        saida[pid] = {
            "anos": [{"ano": a, "n": len(x), "empenhado": soma(x, "empenhado"), "liquidado": soma(x, "liquidado"), "pago": soma(x, "pago")}
                     for a, x in sorted(por_ano.items(), reverse=True)],
            "municipios": municipios,
            "itens": [{k: i[k] for k in CAMPOS_ITEM if k in i}
                      for i in sorted(itens, key=lambda i: (-i["ano"], -(i.get("empenhado") or 0), i["codigo"]))],
        }
    return saida


def salvar(emendas: list[dict], saida: Path) -> int:
    arquivos = construir(emendas)
    for pid, arq in arquivos.items():
        comum.salvar(saida / "emendas" / f"{pid}.json", arq)
    return len(arquivos)
