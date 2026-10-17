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
FIM_MANDATO = {2022: "2026-12-31", 2024: "2028-12-31", 2026: None}


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
            "h": f"deputado.html?id={d['id']}",
        })

    # --- senadores em exercício (Senado)
    for s in ler(BRUTO / "senado.json", []) or []:
        cargo, ordem = rotulo("SENADOR", s.get("genero"))
        sid = str(s["id"])
        fichas["senado"][sid] = {**s, "cargo": cargo, "fonte": "senado", "estado": "atual"}
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
                    "estado": estado, "fimMandato": FIM_MANDATO.get(ano), "paginaAtual": atual_href,
                    **({"estadual": estadual} if estadual else {}),
                }
                indice[uf].append({
                    "i": e["sq"], "f": arquivo, "n": e["urna"], "c": cargo, "k": ordem,
                    "p": e.get("partido"), "m": e.get("municipio"),
                    "g": e["ue"] if cargo_tse in MUNICIPAIS else None,
                    "e": estado, "b": e.get("totalBens") or None,
                })

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
    total = sum(len(v) for v in indice.values())
    print(f"Políticos no índice: {total} em {len(indice)} UFs; {len(fichas)} arquivos de fichas")
    return resumo
