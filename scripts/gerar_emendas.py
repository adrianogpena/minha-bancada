"""
Emendas parlamentares de cada deputado e senador: site/dados/emendas/<pessoa>.json, a partir de `nucleo["emendas"]`
(identidades.ligar_emendas, que lê dados/emendas/<ano>.json do coletar_emendas.py). Sem internet.

Arquivo da pessoa: {anos:[{ano, n, empenhado, liquidado, pago}] (mais recente primeiro),
municipios:[{nome, uf, ibge, empenhado, pago, n, pixEmpenhado, pixPago, pixN}] (todos os destinos, do maior valor empenhado ao menor; `ibge` só
quando o nome casa com o município, e é o que o mapa do site usa; os campos pix* só nas emendas Pix), itens:[{codigo, ano, tipo, numero, local,
funcao, subfuncao, empenhado, liquidado, pago}]}. Valores em reais; o link da fonte de cada ano é montado no site.

Emenda Pix é a emenda individual de "Transferências Especiais" (a verba vai direto ao caixa do município, sem convênio).
O código IBGE vem de dados/municipios_nomes.json (gerar_municipios_ibge.py --nomes).
"""

from collections import defaultdict
from pathlib import Path

import estaduais_comum as comum
import gerar_municipios_ibge as ibge_nomes

NOMES = comum.RAIZ / "dados" / "municipios_nomes.json"
CAMPOS_ITEM = ("codigo", "ano", "tipo", "numero", "local", "funcao", "subfuncao", "empenhado", "liquidado", "pago")


def indice_municipios(nomes: dict) -> dict:
    """{(UF, nome sem acento): código IBGE}, com as grafias do TSE e as do IBGE (ibge_nomes.AJUSTES)."""
    indice = {(uf, ibge_nomes.chave(nome)): cod for cod, (uf, nome) in nomes.items()}
    for (uf, tse), ibge in ibge_nomes.AJUSTES.items():
        if (uf, tse) in indice:
            indice.setdefault((uf, ibge), indice[(uf, tse)])
    return indice


def eh_pix(tipo: str) -> bool:
    return "transferencias especiais" in ibge_nomes.chave(tipo or "")


def soma(itens: list[dict], campo: str) -> float:
    return round(sum(i.get(campo) or 0 for i in itens), 2)


def construir(emendas: list[dict], nomes: dict | None = None) -> dict[str, dict]:
    """{pessoa: arquivo}. `emendas`: itens ligados, cada um com `pessoa`; `nomes`: {código IBGE: [UF, nome]}."""
    indice = indice_municipios(nomes or {})
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
        municipios = sorted((municipio(m, uf, x, indice) for (m, uf), x in por_local.items()), key=lambda m: (-m["empenhado"], m["nome"], m["uf"]))
        saida[pid] = {
            "anos": [{"ano": a, "n": len(x), "empenhado": soma(x, "empenhado"), "liquidado": soma(x, "liquidado"), "pago": soma(x, "pago")}
                     for a, x in sorted(por_ano.items(), reverse=True)],
            "municipios": municipios,
            "itens": [{k: i[k] for k in CAMPOS_ITEM if k in i}
                      for i in sorted(itens, key=lambda i: (-i["ano"], -(i.get("empenhado") or 0), i["codigo"]))],
        }
    return saida


def municipio(nome: str, uf: str, itens: list[dict], indice: dict) -> dict:
    m = {"nome": nome, "uf": uf, "empenhado": soma(itens, "empenhado"), "pago": soma(itens, "pago"), "n": len(itens)}
    if (uf, ibge_nomes.chave(nome)) in indice:
        m["ibge"] = indice[(uf, ibge_nomes.chave(nome))]
    pix = [i for i in itens if eh_pix(i.get("tipo"))]
    if pix:
        m.update(pixEmpenhado=soma(pix, "empenhado"), pixPago=soma(pix, "pago"), pixN=len(pix))
    return m


def salvar(emendas: list[dict], saida: Path, nomes: dict | None = None) -> int:
    nomes = comum.ler(NOMES, {}) if nomes is None else nomes
    arquivos = construir(emendas, nomes)
    for pid, arq in arquivos.items():
        comum.salvar(saida / "emendas" / f"{pid}.json", arq)
    return len(arquivos)
