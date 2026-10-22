"""
Monta, a partir de dados/estaduais/<UF>/ (coletar_estaduais.py), os arquivos
que o site lê para deputados estaduais:

  site/dados/estadual/<UF>/<id>.json     votos e projetos de um deputado, mais (quando a coleta tem os
                                         arquivos) resumos de verba, remuneração, presença, diárias e emendas
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


INICIO_LEGISLATURA = 2023
TOP_FORNECEDORES = 10


def numero(x) -> float:
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) else 0.0


def itens_por_deputado(pasta: Path, padrao: str) -> tuple:
    """{idDeputado: [(ano do arquivo, item)]} dos arquivos <padrao>[_<ano>].json; None no ano do arquivo sem ano."""
    saida, fonte = defaultdict(list), None
    for arq in sorted(pasta.glob(padrao)):
        m = re.search(r"_(\d{4})\.json$", arq.name)
        ano = int(m.group(1)) if m else None
        if ano is not None and ano < INICIO_LEGISLATURA:
            continue
        env = ler(arq, {})
        fonte = env.get("fonte") or fonte
        for it in env.get("itens", []):
            saida[str(it.get("idDeputado"))].append((ano, it))
    return saida, fonte


def resumo_verba(itens: list, fonte) -> dict:
    anos = {}
    for ano, it in itens:
        a = anos.setdefault(ano, {"total": 0.0, "meses": defaultdict(float), "categorias": defaultdict(float), "fornecedores": defaultdict(float)})
        v = numero(it.get("valor"))
        a["total"] += v
        a["meses"][it.get("mes")] += v
        a["categorias"][it.get("categoria") or "Sem categoria"] += v
        if it.get("fornecedor"):
            a["fornecedores"][(it["fornecedor"], it.get("cnpj"))] += v
    out = []
    for ano in sorted(anos, key=lambda x: x or 0):
        a = anos[ano]
        forn = sorted(a["fornecedores"].items(), key=lambda kv: -kv[1])[:TOP_FORNECEDORES]
        out.append({"ano": ano, "total": round(a["total"], 2),
                    "meses": [{"mes": m, "total": round(t, 2)} for m, t in sorted(a["meses"].items(), key=lambda kv: str(kv[0]))],
                    "categorias": [{"categoria": c, "total": round(t, 2)} for c, t in sorted(a["categorias"].items(), key=lambda kv: -kv[1])],
                    "fornecedores": [{"fornecedor": f, "cnpj": c, "total": round(t, 2)} for (f, c), t in forn]})
    return {"fonte": fonte, "anos": out}


def resumo_remuneracao(itens: list, fonte) -> dict:
    ano, it = max(itens, key=lambda x: (x[0] or 0, numero_mes(x[1].get("mes"))))
    return {"fonte": it.get("fonte") or fonte, "ano": ano, "mes": it.get("mes"), "bruto": it.get("bruto"),
            "liquido": it.get("liquido"), "componentes": it.get("componentes")}


def numero_mes(m) -> int:
    try:
        return int(str(m).split("-")[-1])
    except ValueError:
        return 0


def resumo_diarias(itens: list, fonte) -> dict:
    anos = defaultdict(lambda: [0.0, 0])
    for ano, it in itens:
        a = anos[ano or int(str(it.get("data") or 0)[:4] or 0)]
        a[0] += numero(it.get("valor"))
        a[1] += 1
    return {"fonte": fonte, "anos": [{"ano": a, "total": round(t, 2), "quantidade": q} for a, (t, q) in sorted(anos.items())]}


def resumo_emendas(itens: list, fonte) -> dict:
    anos = defaultdict(lambda: [0.0, 0.0, 0])
    for ano, it in itens:
        a = anos[it.get("ano") or ano]
        a[0] += numero(it.get("empenhado"))
        a[1] += numero(it.get("pago"))
        a[2] += 1
    return {"fonte": fonte, "anos": [{"ano": a, "empenhado": round(e, 2), "pago": round(p, 2), "quantidade": q} for a, (e, p, q) in sorted(anos.items())]}


def resumo_presenca(itens: list, fonte) -> dict:
    campos = ("periodo", "presente", "ausente", "licenca", "totalSessoes")
    return {"fonte": fonte, "periodos": sorted(({k: it.get(k) for k in campos} for _, it in itens), key=lambda x: str(x["periodo"]))}


def resumos_novos(pasta: Path) -> dict:
    """{idDeputado: {bloco: resumo}} só com os arquivos que a coleta da UF tem."""
    blocos = (("verba", "verbas_*.json", resumo_verba), ("remuneracao", "remuneracao_*.json", resumo_remuneracao),
              ("presenca", "presenca.json", resumo_presenca), ("diarias", "diarias_*.json", resumo_diarias),
              ("emendas", "emendas_*.json", resumo_emendas))
    saida = defaultdict(dict)
    for nome, padrao, f in blocos:
        por_dep, fonte = itens_por_deputado(pasta, padrao)
        for pid, itens in por_dep.items():
            if itens:
                saida[pid][nome] = f(itens, fonte)
    return saida


def tipo_voto(v: str) -> str:
    return VOTOS.get((v or "").strip().lower(), "outro")


def gerar_governo(uf: str, pasta: Path, host: str) -> None:
    """site/dados/governo/<UF>.json: o que o governador enviou à Assembleia, do mais novo ao mais antigo."""
    itens = []
    for arq in sorted(pasta.glob("governo_[0-9]*.json")):
        for mid, m in ler(arq, {}).get("materias", {}).items():
            itens.append({"id": mid, "tipo": "VET" if re.search(r"veto", m["tipoDescricao"], re.I) else m["tipo"],
                          "tipoDescricao": m["tipoDescricao"], "numero": m["numero"], "ano": m["ano"], "dataApresentacao": m.get("dataApresentacao"),
                          "ementa": re.sub(r"\s+", " ", m["ementa"]).strip(), "situacao": m["situacao"], "linkTexto": m.get("linkTexto")})
    if not itens:
        return
    itens.sort(key=lambda x: (x["dataApresentacao"] or "", x["id"]), reverse=True)
    salvar(SAIDA / "governo" / f"{uf}.json", {"host": host, "materias": itens})


def gerar_assembleia(uf: str, pasta: Path) -> list[dict]:
    info = ler(pasta / "deputados.json")
    if not info:
        return []
    host = info.get("host")
    novos = resumos_novos(pasta)
    deputados = {d["id"]: d for d in info["deputados"]}
    votacoes = ler(pasta / "votacoes.json", {"votacoes": {}})["votacoes"]
    materias_votadas = ler(pasta / "materias_votadas.json", {})

    lista = []
    for vid, v in votacoes.items():
        mat = materias_votadas.get(str(v["idMateria"])) or {}
        votos = [(p, tipo_voto(t)) for p, t in v["votos"]]
        placar = {"sim": v["sim"] or 0, "nao": v["nao"] or 0, "abstencao": v["abstencoes"] or 0}
        lista.append({
            "id": vid, "data": v["data"], "descricao": mat.get("tipoDescricao") or "Votação",
            "proposicao": f"{mat['tipo']} {mat['numero']}/{mat['ano']}" if mat else None,
            "ementa": mat.get("ementa") or None, "aprovada": v["aprovada"], "resultadoTexto": v.get("resultado"),
            "placar": placar, "_votos": votos,
            **({"fonte": v["fonte"]} if v.get("fonte") else {}),
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
            for pid in m["idsDeputados"]:
                coautores = [deputados[o]["nome"] for o in m["idsDeputados"] if o != pid and o in deputados and deputados[o].get("nome")]
                projetos[pid].append({"id": mid, "tipo": m["tipo"], "tipoDescricao": m.get("tipoDescricao"), "numero": m["numero"], "ano": m["ano"],
                                      "dataApresentacao": m.get("dataApresentacao"), "ementa": m["ementa"], "situacao": m["situacao"],
                                      "emTramitacao": m.get("emTramitacao"), "linkTexto": m.get("linkTexto"),
                                      **({"coautores": coautores} if coautores else {}),
                                      **({"fonte": m["fonte"]} if m.get("fonte") else {})})

    for pid in deputados:
        desde = primeira.get(pid)  # antes do primeiro voto o deputado pode nem estar em exercício
        meus = sorted(projetos.get(pid, []), key=lambda p: (p["dataApresentacao"] or "", p["id"]), reverse=True)
        salvar(SAIDA / "estadual" / uf / f"{pid}.json", {
            "id": pid, "host": host, "foto": deputados[pid].get("foto"), "email": deputados[pid].get("email"),
            "titular": deputados[pid].get("titular"),
            "votos": [{"id": v["id"], "voto": votos_dep[pid].get(v["id"], "ausente")}
                      for v in resumo if desde and v["data"] >= desde],
            "proposicoes": meus,
            **({"fonte": deputados[pid]["fonte"]} if deputados[pid].get("fonte") else {}),
            **novos.get(str(pid), {}),
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
