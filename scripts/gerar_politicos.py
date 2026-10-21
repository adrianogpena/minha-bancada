"""
Monta o índice de todos os políticos (vereador a presidente) que o site usa:

  site/dados/indice/<UF>.json   lista leve, para busca e filtros (BR = Presidência)
  site/dados/p/<arquivo>.json   fichas completas, agrupadas por município ou estado

Fontes: dados/tse/ (eleitos 2022, 2024 e 2026), dados/senado.json e os
deputados federais em exercício já coletados da Câmara.
Chamado pelo scripts/gerar.py; não acessa a internet.
"""

import json
import unicodedata
from collections import defaultdict
from pathlib import Path

from coletar_prefeituras import TODAS as CAPITAIS_COM_DADOS

RAIZ = Path(__file__).resolve().parent.parent
BRUTO = RAIZ / "dados"
SAIDA = RAIZ / "site" / "dados"

# cargo do TSE -> (masculino, feminino, ordem de exibição)
CARGOS = {
    "PRESIDENTE": ("Presidente", "Presidenta", 1),
    "VICE-PRESIDENTE": ("Vice-presidente", "Vice-presidenta", 2),
    "SENADOR": ("Senador", "Senadora", 3),
    "DEPUTADO FEDERAL": ("Deputado federal", "Deputada federal", 4),
    "GOVERNADOR": ("Governador", "Governadora", 5),
    "VICE-GOVERNADOR": ("Vice-governador", "Vice-governadora", 6),
    "DEPUTADO ESTADUAL": ("Deputado estadual", "Deputada estadual", 7),
    "DEPUTADO DISTRITAL": ("Deputado distrital", "Deputada distrital", 7),
    "PREFEITO": ("Prefeito", "Prefeita", 8),
    "VICE-PREFEITO": ("Vice-prefeito", "Vice-prefeita", 9),
    "VEREADOR": ("Vereador", "Vereadora", 10),
}
# de qual eleição vem quem está no cargo hoje (deputados federais e
# senadores vêm das APIs da Câmara e do Senado, que já refletem substituições)
MANDATO_ATUAL = {
    2022: {"PRESIDENTE", "VICE-PRESIDENTE", "GOVERNADOR", "VICE-GOVERNADOR",
           "DEPUTADO ESTADUAL", "DEPUTADO DISTRITAL"},
    2024: {"PREFEITO", "VICE-PREFEITO", "VEREADOR"},
}
ELEICAO_NOVA = 2026
MUNICIPAIS = {"PREFEITO", "VICE-PREFEITO", "VEREADOR"}
# (início, fim) do mandato por eleição e cargo. Presidente e governadores tomam posse em 5 e 6 de
# janeiro desde a EC 111/2021 (a partir de 2027); o mandato acaba um dia antes da posse seguinte.
MANDATOS = {
    2018: {"SENADOR": ("2019-02-01", "2027-01-31")},
    2022: {"PRESIDENTE": ("2023-01-01", "2027-01-04"), "VICE-PRESIDENTE": ("2023-01-01", "2027-01-04"),
           "GOVERNADOR": ("2023-01-01", "2027-01-05"), "VICE-GOVERNADOR": ("2023-01-01", "2027-01-05"),
           "SENADOR": ("2023-02-01", "2031-01-31"),
           **{c: ("2023-02-01", "2027-01-31") for c in ("DEPUTADO FEDERAL", "DEPUTADO ESTADUAL", "DEPUTADO DISTRITAL")}},
    2024: {c: ("2025-01-01", "2028-12-31") for c in ("PREFEITO", "VICE-PREFEITO", "VEREADOR")},
    2026: {"PRESIDENTE": ("2027-01-05", "2031-01-04"), "VICE-PRESIDENTE": ("2027-01-05", "2031-01-04"),
           "GOVERNADOR": ("2027-01-06", "2031-01-05"), "VICE-GOVERNADOR": ("2027-01-06", "2031-01-05"),
           "SENADOR": ("2027-02-01", "2035-01-31"),
           **{c: ("2027-02-01", "2031-01-31") for c in ("DEPUTADO FEDERAL", "DEPUTADO ESTADUAL", "DEPUTADO DISTRITAL")}},
}


def periodo(ano: int, cargo_tse: str) -> tuple[str | None, str | None]:
    return MANDATOS.get(ano, {}).get(cargo_tse, (None, None))


CAMPOS_ELEICAO = ("ano", "sq", "eleicao", "ue", "uf", "cargoTse", "resultado", "votos", "titular")


_RESUMOS = {}


def resumo_tse(pasta: str, ano: int, uf: str) -> dict:
    chave = (pasta, ano, uf)
    if chave not in _RESUMOS:
        _RESUMOS[chave] = ler(BRUTO / "tse" / pasta / str(ano) / f"{uf}.json", {})
    return _RESUMOS[chave]


def contas_de(ano: int, e: dict):
    """Resumo da prestação de contas de campanha (dados/tse/contas/<ano>/<UF>.json), ou None."""
    return resumo_tse("contas", ano, e["uf"]).get(e.get("chapaSq") or e["sq"])


def secoes_de(ano: int, e: dict):
    """Onde o eleito foi votado (dados/tse/secoes/<ano>/<UF>.json), ou None."""
    return resumo_tse("secoes", ano, e["uf"]).get(e.get("chapaSq") or e["sq"])


def disputa_de(ano: int, e: dict):
    """Comparecimento e vagas do cargo e local da eleição (dados/tse/disputa/<ano>/<UF>.json), ou None."""
    return resumo_tse("disputa", ano, e["uf"]).get(f"{e['cargo'].replace('VICE-', '')}|{e['ue']}")


def partido_de(ano: int, e: dict):
    """Votos do partido (e da federação) no cargo e local da eleição (dados/tse/partidos/<ano>/<UF>.json), ou None.
    l = legenda, n = nominais, t = votos válidos dos partidos; f/fl/fn = federação e seus votos de legenda e nominais."""
    local = resumo_tse("partidos", ano, e["uf"]).get(f"{e['cargo']}|{e['ue']}")
    p = local and local["p"].get(e.get("partido"))
    if not p:
        return None
    r = {"l": p[0], "n": p[1], "t": local["t"]}
    if p[2]:
        membros = [v for v in local["p"].values() if v[2] == p[2]]
        r.update(f=p[2], fl=sum(v[0] for v in membros), fn=sum(v[1] for v in membros))
    return r


def alianca_de(ano: int, e: dict):
    """Tipo (C coligação, F federação, I isolado), nome, composição e situação da legenda do partido do eleito
    (dados/tse/coligacoes/<ano>/<UF>.json), ou None."""
    local = resumo_tse("coligacoes", ano, e["uf"]).get(f"{e['cargo']}|{e['ue']}")
    i = local and local["p"].get(e.get("partido"))
    return dict(zip("tncs", local["c"][i])) if i is not None else None


def eleitos_por_nome(cargo_tse: str) -> dict:
    """Eleitos de 2018 e 2022 a um cargo federal, por nome e UF, para ligar com a Câmara e o Senado."""
    achados = defaultdict(list)
    for ano in (2018, 2022):
        for arq in sorted((BRUTO / "tse" / str(ano)).glob("[A-Z][A-Z].json")):
            for e in ler(arq, []):
                if e["cargo"] != cargo_tse:
                    continue
                bloco = {**{k: e.get(k) for k in CAMPOS_ELEICAO if k != "ano"}, "ano": ano, "cargoTse": cargo_tse}
                bloco["inicioMandato"], bloco["fimMandato"] = periodo(ano, cargo_tse)
                bloco["contas"] = contas_de(ano, e)
                bloco["secoes"] = secoes_de(ano, e)
                bloco["disputa"] = disputa_de(ano, e)
                bloco["partidoVotos"] = partido_de(ano, e)
                bloco["alianca"] = alianca_de(ano, e)
                for n in (e.get("nome"), e.get("urna")):
                    achados[chave_nome(n, e["uf"])].append(bloco)
    return achados


def achar_eleicao(achados: dict, nomes: list, uf: str, fim: str | None = None):
    for n in nomes:
        for b in sorted(achados.get(chave_nome(n, uf), []), key=lambda b: -b["ano"]):
            if not fim or b["fimMandato"][:4] == fim[:4]:
                return b
    return None


def eleicao_deputados(deputados: dict) -> dict:
    """id do deputado federal -> como foi eleito em 2022 (None se for suplente que assumiu)."""
    achados = eleitos_por_nome("DEPUTADO FEDERAL")
    return {did: achar_eleicao(achados, [d.get("nomeCivil"), d.get("nome")], d["uf"]) for did, d in deputados.items()}


def ler(caminho: Path, padrao=None):
    if caminho.exists():
        return json.loads(caminho.read_text(encoding="utf-8"))
    return padrao


def salvar(caminho: Path, obj) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def chave_nome(nome: str | None, uf: str | None) -> str:
    n = unicodedata.normalize("NFD", (nome or "").lower())
    n = "".join(c for c in n if unicodedata.category(c) != "Mn")
    return f"{' '.join(n.split())}|{(uf or '').upper()}"


def rotulo(cargo: str, genero: str | None) -> tuple[str, int]:
    m, f, ordem = CARGOS.get(cargo, (cargo.title(), cargo.title(), 99))
    return (f if (genero or "").upper().startswith("F") else m), ordem


def gerar(deputados: dict, estaduais: dict | None = None) -> dict:
    estaduais = estaduais or {}
    indice = defaultdict(list)       # UF -> entradas
    fichas = defaultdict(dict)       # arquivo -> {id: ficha}

    # páginas atuais de deputados federais e senadores, para ligar com o TSE
    paginas_atuais = {}
    for d in deputados.values():
        href = f"deputado.html?id={d['id']}"
        paginas_atuais[chave_nome(d.get("nomeCivil"), d["uf"])] = href
        paginas_atuais[chave_nome(d.get("nome"), d["uf"])] = href

    # --- deputados federais em exercício (Câmara)
    for d in deputados.values():
        indice[d["uf"]].append({
            "i": d["id"], "n": d["nome"], "c": "Deputado federal", "k": 4,
            "p": d["partido"], "e": "atual", "fo": d.get("foto"),
            "h": f"deputado.html?id={d['id']}", "a": f"dep:{d['id']}",
        })

    # --- senadores em exercício (Senado)
    eleitos_senado = eleitos_por_nome("SENADOR")
    for s in ler(BRUTO / "senado.json", []) or []:
        cargo, ordem = rotulo("SENADOR", s.get("genero"))
        sid = str(s["id"])
        fichas["senado"][sid] = {**s, "cargo": cargo, "fonte": "senado", "estado": "atual",
                                 "eleicao": achar_eleicao(eleitos_senado, [s.get("titular")] if s.get("titular") else [s.get("nomeCivil"), s.get("nome")],
                                                          s["uf"], s.get("fimMandato"))}
        paginas_atuais[chave_nome(s.get("nomeCivil"), s["uf"])] = f"politico.html?f=senado&i={sid}"
        paginas_atuais[chave_nome(s.get("nome"), s["uf"])] = f"politico.html?f=senado&i={sid}"
        indice[s["uf"]].append({
            "i": sid, "f": "senado", "n": s["nome"], "c": cargo, "k": ordem,
            "p": s.get("partido"), "e": "atual", "fo": s.get("foto"),
        })

    # --- TSE: mandatos atuais e eleitos de 2026
    anos = sorted(int(p.name) for p in (BRUTO / "tse").glob("*") if p.is_dir() and p.name.isdigit())
    for ano in anos:
        for arq in sorted((BRUTO / "tse" / str(ano)).glob("[A-Z][A-Z].json")):
            for e in ler(arq, []):
                cargo_tse = e["cargo"]
                if ano == ELEICAO_NOVA:
                    estado = e["situacao"]                     # "eleito" ou "2turno"
                elif cargo_tse in MANDATO_ATUAL.get(ano, set()):
                    estado = "atual"
                else:
                    continue
                cargo, ordem = rotulo(cargo_tse, e.get("genero"))
                uf = "BR" if e["uf"] in ("BR", "BRASIL") else e["uf"]
                arquivo = f"t/{ano}/{e['ue']}" if cargo_tse in MUNICIPAIS else f"t/{ano}/{uf}"
                atual_href = None
                if estado != "atual":
                    atual_href = paginas_atuais.get(chave_nome(e.get("nome"), uf)) or \
                        paginas_atuais.get(chave_nome(e.get("urna"), uf))
                estadual = None
                if estado == "atual" and cargo_tse in ("DEPUTADO ESTADUAL", "DEPUTADO DISTRITAL"):
                    achado = estaduais.get(chave_nome(e.get("urna"), uf)) or estaduais.get(chave_nome(e.get("nome"), uf))
                    estadual = {"uf": achado[0], "id": achado[1]} if achado else None
                fichas[arquivo][e["sq"]] = {
                    **e, "cargo": cargo, "cargoTse": cargo_tse, "ano": ano, "fonte": "tse",
                    "estado": estado, "inicioMandato": periodo(ano, cargo_tse)[0], "fimMandato": periodo(ano, cargo_tse)[1],
                    "paginaAtual": atual_href,
                    "contas": contas_de(ano, e),
                    "secoes": secoes_de(ano, e),
                    "disputa": disputa_de(ano, e),
                    "partidoVotos": partido_de(ano, e),
                    "alianca": alianca_de(ano, e),
                    **({"estadual": estadual} if estadual else {}),
                }
                alvo = None   # código dos feeds da página Fique informado; só para quem tem dados acompanháveis (ver scripts/feeds.py)
                if estado == "atual":
                    if cargo_tse == "PRESIDENTE":
                        alvo = "pres"
                    elif cargo_tse == "GOVERNADOR":
                        alvo = f"gov:{uf}"
                    elif estadual:
                        alvo = f"est:{estadual['uf']}:{estadual['id']}"
                    elif cargo_tse == "PREFEITO" and CAPITAIS_COM_DADOS.get(uf, ("",))[0] == e["ue"]:
                        alvo = f"pref:{uf}"
                indice[uf].append({
                    "a": alvo, "i": e["sq"], "f": arquivo, "n": e["urna"], "c": cargo, "k": ordem,
                    "p": e.get("partido"), "m": e.get("municipio"),
                    "g": e["ue"] if cargo_tse in MUNICIPAIS else None,
                    "e": estado, "b": e.get("totalBens") or None,
                    "fo": e.get("foto"),
                })

    # cargos federais do Brasil todo, para a visão nacional da página inicial (u = estado)
    indice["BR"] += [{**x, "u": uf} for uf, lista in indice.items() if uf != "BR" for x in lista if x["k"] in (3, 4)]

    # --- grava
    for uf, lista in indice.items():
        lista.sort(key=lambda x: (x["k"], x.get("m") or "", x["n"] or ""))
        salvar(SAIDA / "indice" / f"{uf}.json", [{k: v for k, v in x.items() if v is not None} for x in lista])
    for arquivo, mapa in fichas.items():
        salvar(SAIDA / "p" / f"{arquivo}.json", mapa)

    resumo = {}
    for uf, lista in indice.items():
        cont = defaultdict(int)
        for x in lista:
            cont[x["e"]] += 1
        resumo[uf] = dict(cont)
    salvar(SAIDA / "indice" / "_resumo.json", resumo)
    # o que a página Fique informado oferece: estados com Assembleia coletada e capitais com a Câmara Municipal coletada
    capitais = {}
    for uf, lista in indice.items():
        for x in lista:
            if x.get("a") == f"pref:{uf}":
                capitais[uf] = x.get("m") or uf
    salvar(SAIDA / "cobertura.json", {
        "estados": sorted(p.parent.name for p in (BRUTO / "estaduais").glob("*/deputados.json")),
        "capitais": dict(sorted(capitais.items())),
    })
    total = sum(len(v) for v in indice.values())
    print(f"Políticos no índice: {total} em {len(indice)} UFs; {len(fichas)} arquivos de fichas")
    return resumo
