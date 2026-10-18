"""
Monta, a partir de dados/estaduais/<UF>/ (coletar_estaduais.py), os arquivos
que o site lê para deputados estaduais:

  site/dados/estadual/<UF>/<id>.json     votos e projetos de um deputado
  site/dados/votacoes_estadual_<UF>.json lista das votações nominais da Assembleia

Devolve o mapa nome -> (UF, id), que o gerar_politicos usa para ligar a ficha
do TSE à página com votos e projetos. Não acessa a internet.
"""

import json
import re
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BRUTO = RAIZ / "dados" / "estaduais"
SAIDA = RAIZ / "site" / "dados"

VOTOS = {"sim": "sim", "não": "nao", "nao": "nao", "abstenção": "abstencao", "abstencao": "abstencao",
         "obstrução": "obstrucao", "obstrucao": "obstrucao", "não votou": "ausente", "nao votou": "ausente"}


def ler(caminho: Path, padrao=None):
    if caminho.exists():
        return json.loads(caminho.read_text(encoding="utf-8"))
    return padrao


def salvar(caminho: Path, obj) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def tipo_voto(v: str) -> str:
    return VOTOS.get((v or "").strip().lower(), "outro")


def gerar_governo(uf: str, pasta: Path, host: str) -> None:
    """site/dados/governo/<UF>.json: o que o governador enviou à Assembleia, do mais novo ao mais antigo."""
    itens = []
    for arq in sorted(pasta.glob("governo_[0-9]*.json")):
        for mid, m in ler(arq, {}).get("materias", {}).items():
            itens.append({"id": mid, "tipo": m["t"], "td": m["td"], "numero": m["n"], "ano": m["a"], "ap": m.get("ap"),
                          "ementa": re.sub(r"\s+", " ", m["e"]).strip(), "sit": m["sit"], "pdf": m.get("pdf")})
    if not itens:
        return
    itens.sort(key=lambda x: (x["ap"] or "", x["id"]), reverse=True)
    salvar(SAIDA / "governo" / f"{uf}.json", {"host": host, "materias": itens})


def gerar_assembleia(uf: str, pasta: Path) -> list[dict]:
    info = ler(pasta / "deputados.json")
    if not info:
        return []
    host = info["host"]
    deputados = {d["id"]: d for d in info["deputados"]}
    votacoes = ler(pasta / "votacoes.json", {"votacoes": {}})["votacoes"]
    materias_votadas = ler(pasta / "materias_votadas.json", {})

    lista = []
    for vid, v in votacoes.items():
        mat = materias_votadas.get(str(v["m"])) or {}
        votos = [(p, tipo_voto(t)) for p, t in v["v"]]
        placar = {"sim": v["sim"] or 0, "nao": v["nao"] or 0, "abstencao": v["abs"] or 0}
        lista.append({
            "id": vid, "data": v["d"], "descricao": mat.get("td") or "Votação",
            "proposicao": f"{mat['t']} {mat['n']}/{mat['a']}" if mat else None,
            "ementa": mat.get("e") or None, "aprovada": v["ok"], "resultadoTexto": v.get("res"),
            "placar": placar, "_votos": votos,
        })
    lista.sort(key=lambda v: (v["data"], v["id"]), reverse=True)

    votos_dep, primeira = defaultdict(dict), {}
    for v in lista:
        for pid, t in v["_votos"]:
            votos_dep[pid][v["id"]] = t
            if pid not in primeira or v["data"] < primeira[pid]:
                primeira[pid] = v["data"]
    resumo = [{k: x for k, x in v.items() if k != "_votos"} for v in lista]
    salvar(SAIDA / f"votacoes_estadual_{uf}.json", resumo)

    projetos = defaultdict(list)
    for arq in sorted(pasta.glob("materias_[0-9]*.json")):
        for mid, m in ler(arq, {}).get("materias", {}).items():
            for pid in m["dep"]:
                coautores = [deputados[o]["nome"] for o in m["dep"] if o != pid and o in deputados and deputados[o].get("nome")]
                projetos[pid].append({"id": mid, "tipo": m["t"], "td": m.get("td"), "numero": m["n"], "ano": m["a"],
                                      "ap": m.get("ap"), "ementa": m["e"], "sit": m["sit"], "tr": m.get("tr"),
                                      "pdf": m.get("pdf"), **({"co": coautores} if coautores else {})})

    for pid in deputados:
        desde = primeira.get(pid)  # antes do primeiro voto o deputado pode nem estar em exercício
        meus = sorted(projetos.get(pid, []), key=lambda p: (p["ap"] or "", p["id"]), reverse=True)
        salvar(SAIDA / "estadual" / uf / f"{pid}.json", {
            "id": pid, "host": host, "foto": deputados[pid].get("foto"), "email": deputados[pid].get("email"),
            "titular": deputados[pid].get("titular"),
            "votos": [{"id": v["id"], "voto": votos_dep[pid].get(v["id"], "ausente")}
                      for v in resumo if desde and v["data"] >= desde],
            "proposicoes": meus,
        })
    gerar_governo(uf, pasta, host)
    print(f"Gerado: {uf}, {len(deputados)} deputados, {len(resumo)} votações nominais, "
          f"{sum(len(v) for v in projetos.values())} autorias de projetos")
    return list(deputados.values())


def gerar() -> dict:
    """Devolve {(nome sem acento, UF): (UF, id)} para ligar com a ficha do TSE."""
    from gerar_politicos import chave_nome
    ligacao = {}
    if not BRUTO.exists():
        return ligacao
    for pasta in sorted(p for p in BRUTO.iterdir() if p.is_dir()):
        for d in gerar_assembleia(pasta.name, pasta):
            civil = re.sub(r"\s*\(.*?\)", "", d.get("nomeCivil") or "")  # "Fulano da Silva (Fulaninho)" -> nome sem apelido
            for nome in (d.get("nome"), d.get("nomeCivil"), civil):
                if nome:
                    ligacao[chave_nome(nome, pasta.name)] = (pasta.name, d["id"])
    return ligacao
