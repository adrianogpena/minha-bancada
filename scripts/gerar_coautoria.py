"""Rede de coautoria da Câmara: com quem cada deputado mais assina projetos e o quanto os partidos assinam juntos.

Usa só dados já coletados: a autoria de cada proposição (dados/proposicoes_autores.json) e a lista de proposições de cada
deputado (tipo e data de apresentação). Conta projetos (TIPOS_PROJETO) assinados por mais de um deputado em exercício;
autores que não são deputados (Executivo, Senado, comissão) e projetos com mais de MAX_AUTORES deputados (assinatura em
massa, que ligaria todos a todos) ficam de fora. O partido de cada autor é o da data de apresentação, como em
`gerar.juntar_autoria`. Não acessa a internet.

Saída:
  por deputado  {projetos, parceiros: [[idDeputado, n], ...], outroPartido}   (guardado no arquivo do deputado)
  geral         {partidos: [{sigla, projetos, comOutros}], pares: {"A|B": n}, ...}   (site/dados/coautoria.json)
"""
from collections import Counter, defaultdict
from itertools import combinations

MAX_AUTORES = 30
MAX_PARCEIROS = 10


def construir(deputados: dict, autorias: dict, tipos_projeto: set, sigla_em) -> tuple[dict, dict]:
    """`sigla_em(idDeputado, dia)` devolve o partido do deputado no dia (ou o atual). Devolve (por_deputado, geral)."""
    projetos = {}
    for d in deputados.values():
        for p in d["proposicoes"]:
            if p.get("tipo") in tipos_projeto:
                projetos[str(p["id"])] = p.get("dataApresentacao")

    parceiros = defaultdict(Counter)
    total = Counter()
    outro_partido = Counter()
    partido_projetos = Counter()
    partido_com_outros = Counter()
    pares = Counter()
    ignorados = 0
    lidos = 0

    for pid, dia in projetos.items():
        deps = sorted({str(a[0]) for a in (autorias.get(pid) or {}).get("autores", []) if str(a[0]) in deputados})
        if len(deps) < 2:
            continue
        if len(deps) > MAX_AUTORES:
            ignorados += 1
            continue
        lidos += 1
        sigla = {i: sigla_em(i, dia) for i in deps}
        siglas = set(filter(None, sigla.values()))
        for i in deps:
            total[i] += 1
            parceiros[i].update(j for j in deps if j != i)
            if any(sigla[j] and sigla[j] != sigla[i] for j in deps):
                outro_partido[i] += 1
        for s in siglas:
            partido_projetos[s] += 1
            if len(siglas) > 1:
                partido_com_outros[s] += 1
        for a, b in combinations(sorted(siglas), 2):
            pares[f"{a}|{b}"] += 1

    por_deputado = {
        i: {"projetos": total[i], "outroPartido": outro_partido[i],
            "parceiros": [[j, n] for j, n in sorted(parceiros[i].items(), key=lambda x: (-x[1], x[0]))[:MAX_PARCEIROS]]}
        for i in total
    }
    geral = {
        "projetos": lidos, "ignorados": ignorados, "maxAutores": MAX_AUTORES,
        "partidos": [{"sigla": s, "projetos": n, "comOutros": partido_com_outros[s]}
                     for s, n in sorted(partido_projetos.items())],
        "pares": dict(sorted(pares.items())),
    }
    return por_deputado, geral
