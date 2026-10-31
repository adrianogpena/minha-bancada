"""
Ministros dos tribunais superiores para o site, a partir de dados/tribunais/ (coletar_tribunais.py e coletar_relatorias.py). Sem internet;
chamado por gerar.py.

  site/dados/tribunais.json  [{sigla, nome, fonte, wikipedia, coletadoEm, relatorias?: {rotulo, url, anos: [ano]}, ministros: [{id, nome, wiki?, pessoa?,
                               posse?, posseTexto?, nomeadoPor?, vaga?, estado?, nascimento?, limite?, categoria?, observacao?, vistoDesde,
                               relatorias?: {ano: n}, confirmado?, recentes?: [{numero, ano, tipo, colegiado, data, url}]}],
                               outrosRelatores?: [{nome, relatorias: {ano: n}, ultimo, recentes?}], saidas: [{id, nome, vistoDesde, vistoAte}]}]

`id` = identidades.id_ministro_tribunal (ids.gerar_id("mtr", "wikipedia", página do ministro ou tribunal|nome)); `pessoa` vem da ligação por nome
civil feita em `identidades.ligar_tribunais` (`nucleo["tribunais"]`); `parlamentar` {casa, id} quando ela já foi deputada ou senadora. `relatorias` (TCU e STJ, fontes oficiais) conta acórdãos relatados por ano;
`confirmado` diz se o ministro relatou algo no ano corrente ou no anterior. O relator que não casa com nenhum ministro da lista
(ministro-substituto, convocado ou ex-ministro) vai para `outrosRelatores`.
"""

import re
from collections import defaultdict
from pathlib import Path

import identidades
from estaduais_comum import sem_acento
from gerar_politicos import ler, salvar

CAMPOS = ("wiki", "posse", "posseTexto", "nomeadoPor", "vaga", "estado", "nascimento", "limite", "categoria", "observacao", "vistoDesde")
PARTICULAS = {"de", "da", "do", "das", "dos", "e"}
ANOS_MOSTRADOS = 3


def palavras(nome: str) -> set[str]:
    return {p for p in re.split(r"[^a-z]+", sem_acento(nome).lower()) if p and p not in PARTICULAS}


def casar_relator(relator: str, ministros: list[dict]) -> dict | None:
    """Ministro cujas palavras do nome contêm todas as do relator ("HERMAN BENJAMIN"); mais de um ou nenhum não casa."""
    chave = palavras(relator)
    achados = [m for m in ministros if chave and chave <= palavras(m["nome"])]
    return achados[0] if len(achados) == 1 else None


def relatorias_tcu(bruto: Path) -> tuple[dict, dict, str | None]:
    """({relator: {ano: n}}, {relator: [recentes]}, dia da última sessão)."""
    arq = ler(bruto / "tribunais" / "relatorias_tcu.json", {}) or {}
    anos: dict = defaultdict(lambda: defaultdict(int))
    for dia, por_relator in arq.get("dias", {}).items():
        for relator, tipos in por_relator.items():
            anos[relator][dia[:4]] += sum(tipos.values())
    return anos, arq.get("recentes", {}), max(arq.get("dias", {}), default=None)


def relatorias_stj(bruto: Path) -> dict:
    arq = ler(bruto / "tribunais" / "relatorias_stj.json", {}) or {}
    anos: dict = defaultdict(lambda: defaultdict(int))
    for r in arq.get("recursos", {}).values():
        for relator, por_ano in r.get("contagem", {}).items():
            for ano, n in por_ano.items():
                anos[relator][ano] += n
    return anos


def id_ministro(sigla: str, m: dict) -> str:
    return identidades.id_ministro_tribunal(sigla, m)


def ministro(sigla: str, m: dict, pessoas: dict, fontes: dict) -> dict:
    mid = id_ministro(sigla, m)
    saida = {"id": mid, "nome": m["nome"], **{k: m[k] for k in CAMPOS if m.get(k)}}
    if mid in pessoas:
        saida["pessoa"] = pessoas[mid]
        for casa in ("camara", "senado"):
            if fontes.get(pessoas[mid], {}).get(casa):
                saida["parlamentar"] = {"casa": casa, "id": str(fontes[pessoas[mid]][casa])}
                break
    if saida.get("posse"):
        saida.pop("posseTexto", None)   # o texto só vale quando a tabela não traz a data completa
    return saida


def juntar_relatorias(sigla: str, ministros: list[dict], por_relator: dict, recentes: dict, hoje_ano: int) -> list[dict]:
    """Acrescenta `relatorias`, `confirmado` e `recentes` aos ministros e devolve os relatores que não casam com ninguém."""
    usados: set[str] = set()
    for relator, anos in por_relator.items():
        m = casar_relator(relator, ministros)
        if not m:
            continue
        usados.add(relator)
        total = defaultdict(int)
        for ano, n in anos.items():
            total[ano] += n
        m["relatorias"] = {a: n for a, n in sorted(total.items(), reverse=True)[:ANOS_MOSTRADOS]}
        if recentes.get(relator):
            m["recentes"] = recentes[relator]
    for m in ministros:
        recente = m.get("relatorias", {})
        m["confirmado"] = any(recente.get(str(a)) for a in (hoje_ano, hoje_ano - 1))
    fora = []
    for relator, anos in por_relator.items():
        if relator in usados or not any(anos.values()):
            continue
        item = {"nome": relator.title(), "relatorias": {a: n for a, n in sorted(anos.items(), reverse=True)[:ANOS_MOSTRADOS]}, "ultimo": max(anos)}
        if recentes.get(relator):
            item["recentes"] = recentes[relator]
        fora.append(item)
    return sorted(fora, key=lambda x: (x["ultimo"], sum(x["relatorias"].values())), reverse=True)


def construir(bruto: Path, pessoas: dict | None = None, fontes: dict | None = None) -> list[dict]:
    arq = ler(bruto / "tribunais" / "tribunais.json", {}) or {}
    coletado = arq.get("coletadoEm")
    hoje_ano = int(coletado[:4]) if coletado else 0
    tcu, tcu_recentes, ultima_sessao = relatorias_tcu(bruto)
    stj = relatorias_stj(bruto)
    saida = []
    for sigla, t in arq.get("tribunais", {}).items():
        lista = [ministro(sigla, m, pessoas or {}, fontes or {}) for m in t["atuais"]]
        tribunal = {"sigla": sigla, "nome": t["nome"], "fonte": t["fonte"], "wikipedia": t["wikipedia"], "coletadoEm": coletado,
                    "ministros": lista,
                    "saidas": [{"id": id_ministro(sigla, m), "nome": m["nome"], "vistoDesde": m.get("vistoDesde"), "vistoAte": m["vistoAte"]}
                               for m in t.get("anteriores", [])]}
        if sigla == "TCU" and tcu:
            tribunal["outrosRelatores"] = juntar_relatorias(sigla, lista, tcu, tcu_recentes, hoje_ano)
            tribunal["relatorias"] = {"rotulo": "Acórdãos do TCU (API de dados abertos)", "url": "https://dados-abertos.apps.tcu.gov.br/api/acordao/recupera-acordaos",
                                      "ate": ultima_sessao}
        elif sigla == "STJ" and stj:
            tribunal["outrosRelatores"] = juntar_relatorias(sigla, lista, stj, {}, hoje_ano)
            tribunal["relatorias"] = {"rotulo": "Espelhos de acórdãos do STJ (dados abertos)", "url": "https://dadosabertos.web.stj.jus.br/dataset?q=espelhos+de+acordaos"}
        saida.append(tribunal)
    return saida


def salvar_tribunais(lista: list[dict], saida: Path) -> None:
    salvar(saida / "tribunais.json", lista)
    print(f"Tribunais: {len(lista)} cortes, {sum(len(t['ministros']) for t in lista)} ministros, "
          f"{sum(1 for t in lista for m in t['ministros'] if m.get('pessoa'))} ligados a pessoas")
