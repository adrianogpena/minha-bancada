"""
Relatorias dos tribunais superiores por fontes oficiais que respondem à coleta (o resto bloqueia; ver CHANGELOG.md). Servem para conferir
a lista de ministros da Wikipédia (coletar_tribunais.py), achar ministros-substitutos e ex-ministros e contar quanto cada um relata.
Grava em dados/tribunais/ (vai para o git):

  relatorias_tcu.json  {coletadoEm, fonte, dias: {AAAA-MM-DD: {relator: {tipo: n}}}, recentes: {relator: [{numero, ano, tipo, colegiado, data, url}]}}
      acórdãos do TCU (API de dados abertos, sem chave), por dia de sessão desde 2025; a coleta seguinte relê só os últimos dias.
  relatorias_stj.json  {coletadoEm, fonte, recursos: {id: {modificado, nome, orgao, contagem: {relator: {ano: n}}}}}
      espelhos de acórdãos do STJ (dados abertos, um JSON por mês e por órgão julgador) desde 2023; só relê recurso novo ou modificado.

Uso:
    python scripts/coletar_relatorias.py
"""

import datetime as dt
import os
import re
import time
from collections import defaultdict
from pathlib import Path

import estaduais_comum as comum
from estaduais_comum import avisar

RAIZ = Path(__file__).resolve().parent.parent
PASTA = RAIZ / "dados" / "tribunais"
TCU_API = "https://dados-abertos.apps.tcu.gov.br/api/acordao/recupera-acordaos"
STJ_CKAN = "https://dadosabertos.web.stj.jus.br/api/3/action/package_show?id="
STJ_ORGAOS = ["corte-especial", "primeira-secao", "segunda-secao", "terceira-secao", "primeira-turma", "segunda-turma", "terceira-turma",
              "quarta-turma", "quinta-turma", "sexta-turma"]
ANO_INICIAL = 2023          # governo atual começa em 1º de janeiro de 2023
ANO_INICIAL_TCU = 2025      # a API pagina por deslocamento e fica lenta nas páginas fundas (55 s em 40.000): só o ano anterior e o corrente
PAGINA_TCU = 1000
FOLGA_DIAS = 7              # a coleta seguinte relê os últimos dias, para pegar acórdão publicado com atraso
RECENTES_POR_RELATOR = 10
PRAZO_SEG = float(os.environ.get("TRIBUNAIS_PRAZO_MIN", "20")) * 60


def agregar_tcu(itens: list[dict]) -> tuple[dict, dict]:
    """({dia: {relator: {tipo: n}}}, {relator: [acórdãos mais novos]}) dos acórdãos como a API do TCU publicou."""
    dias: dict = {}
    recentes: dict = defaultdict(list)
    for a in itens:
        dia, relator = comum.data_br_iso(a.get("dataSessao")), (a.get("relator") or "").strip()
        if not dia or not relator:
            continue
        tipo = (a.get("tipo") or "").strip()
        por_tipo = dias.setdefault(dia, {}).setdefault(relator, {})
        por_tipo[tipo] = por_tipo.get(tipo, 0) + 1
        recentes[relator].append({"numero": a.get("numeroAcordao"), "ano": a.get("anoAcordao"), "tipo": tipo, "colegiado": a.get("colegiado"),
                                  "data": dia, "url": a.get("urlAcordao")})
    return dias, {r: ordenar(v) for r, v in recentes.items()}


def ordenar(lista: list[dict]) -> list[dict]:
    return sorted(lista, key=lambda x: (x["data"], str(x["numero"])), reverse=True)[:RECENTES_POR_RELATOR]


def coletar_tcu(hoje: str, fim: float) -> None:
    arq = PASTA / "relatorias_tcu.json"
    antigo = comum.ler(arq) or {}
    dias_antigos = antigo.get("dias", {})
    corte = f"{ANO_INICIAL_TCU}-01-01"
    if dias_antigos:
        corte = max(corte, (dt.date.fromisoformat(max(dias_antigos)) - dt.timedelta(days=FOLGA_DIAS)).isoformat())
    lidos, inicio, sessao = [], 0, comum.sessao()
    completo = False
    while time.monotonic() < fim:
        pagina = comum.get(sessao, TCU_API, params={"inicio": inicio, "quantidade": PAGINA_TCU}, timeout=120).json()
        lidos += pagina
        datas = [d for a in pagina if (d := comum.data_br_iso(a.get("dataSessao")))]
        if not pagina or (datas and max(datas) < corte):
            completo = True
            break
        inicio += PAGINA_TCU
    if not completo:   # a última página lida pode ter só parte do dia mais antigo: esse dia fica de fora e a próxima coleta o relê
        datas = [d for a in lidos if (d := comum.data_br_iso(a.get("dataSessao")))]
        if datas:
            parcial = min(datas)
            lidos = [a for a in lidos if (comum.data_br_iso(a.get("dataSessao")) or "") > parcial]
            corte = max(corte, parcial)
        avisar(f"relatorias: TCU: prazo esgotado em {inicio} acórdãos; só as sessões depois de {corte} foram gravadas")
    dias, recentes = agregar_tcu([a for a in lidos if (comum.data_br_iso(a.get("dataSessao")) or "") >= corte])
    juntos = {d: v for d, v in dias_antigos.items() if d < corte}
    juntos.update(dias)
    rec = dict(antigo.get("recentes", {}))
    for relator, lista in recentes.items():
        mescla = {(x["numero"], x["ano"], x["tipo"]): x for x in rec.get(relator, []) + lista}
        rec[relator] = ordenar(list(mescla.values()))
    comum.salvar(arq, {"coletadoEm": hoje, "fonte": TCU_API, "dias": dict(sorted(juntos.items())), "recentes": rec})
    print(f"TCU: {len(lidos)} acórdãos lidos, {len(juntos)} dias de sessão")


def contar_stj(itens: list[dict]) -> dict:
    """{relator: {ano: n}} dos espelhos de acórdão de um recurso do STJ (`dataDecisao` AAAAMMDD)."""
    saida: dict = {}
    for a in itens:
        relator, dia = (a.get("ministroRelator") or "").strip(), str(a.get("dataDecisao") or "")
        if relator and re.fullmatch(r"\d{8}", dia):
            por_ano = saida.setdefault(relator, {})
            por_ano[dia[:4]] = por_ano.get(dia[:4], 0) + 1
    return saida


def recursos_stj(pacote: dict) -> list[dict]:
    """Recursos JSON mensais (nome AAAAMMDD.json) do conjunto, a partir de ANO_INICIAL."""
    return [r for r in pacote["result"]["resources"]
            if (r.get("format") or "").upper() == "JSON" and re.fullmatch(r"\d{8}\.json", r.get("name") or "")
            and int(r["name"][:4]) >= ANO_INICIAL]


def coletar_stj(hoje: str, fim: float) -> None:
    arq = PASTA / "relatorias_stj.json"
    recursos = (comum.ler(arq) or {}).get("recursos", {})
    sessao, novos, pendentes = comum.sessao(), 0, 0
    for orgao in STJ_ORGAOS:
        try:
            lista = recursos_stj(comum.get(sessao, STJ_CKAN + f"espelhos-de-acordaos-{orgao}", timeout=60).json())
        except Exception as e:
            avisar(f"relatorias: STJ {orgao}: {e}")
            continue
        for r in lista:
            if recursos.get(r["id"], {}).get("modificado") == r.get("last_modified"):
                continue
            if time.monotonic() > fim:
                pendentes += 1
                continue
            try:
                itens = comum.get(sessao, r["url"], timeout=300).json()
            except Exception as e:
                avisar(f"relatorias: STJ {orgao} {r['name']}: {e}")
                continue
            recursos[r["id"]] = {"modificado": r.get("last_modified"), "nome": r["name"], "orgao": orgao, "contagem": contar_stj(itens)}
            novos += 1
    comum.salvar(arq, {"coletadoEm": hoje, "fonte": STJ_CKAN + "espelhos-de-acordaos-<órgão julgador>", "recursos": recursos})
    print(f"STJ: {novos} arquivos lidos, {len(recursos)} no total")
    if pendentes:
        avisar(f"relatorias: STJ: {pendentes} arquivos ficaram para a próxima coleta")


def main() -> None:
    hoje = dt.date.today().isoformat()
    fim = time.monotonic() + PRAZO_SEG
    comum.rodar_etapas("relatorias", [("TCU", lambda: coletar_tcu(hoje, fim)), ("STJ", lambda: coletar_stj(hoje, fim))])


if __name__ == "__main__":
    main()
