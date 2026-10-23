"""
Índice de proposições (projetos, PECs…) para a página proposicoes.html, e a ficha de cada uma com os políticos ligados a ela:
autores (deputados e senadores com ficha no site) e as votações do Plenário em que foi votada.

  site/dados/proposicoes.json            lista enxuta, uma linha por proposição (a busca roda no navegador)
  site/dados/proposicao/<casa>-<id>.json ficha: autores e votações (casa: "c" Câmara, "s" Senado)

Os votos de cada político ficam em site/dados/votacao[_senado]/<id>.json; a ficha só liga para eles.
Não acessa a internet.
"""

from collections import defaultdict

from gerar_politicos import salvar

TAMANHO_EMENTA = 180
MAX_VOTACOES = 30


def _item(casa: str, p: dict, destino) -> dict:
    """Linha do índice: chave, tipo, número, ano, ementa curta, situação e destino (aprovada, rejeitada, tramitando, sem)."""
    return {"k": f"{casa}-{p['id']}", "c": casa, "t": p["tipo"], "n": p["numero"], "a": p["ano"],
            "e": (p.get("ementa") or "").strip()[:TAMANHO_EMENTA], "s": p.get("situacao"), "d": destino(p.get("situacao"))}


def _votacoes(lista: list | None, nominais: dict) -> list:
    saida = []
    for v in sorted(lista or [], key=lambda x: x.get("data") or "", reverse=True)[:MAX_VOTACOES]:
        n = nominais.get(str(v["id"]))
        saida.append({"id": str(v["id"]), "data": v.get("data"), "descricao": v.get("descricao") or (n or {}).get("descricao"),
                      **({"nominal": True, "placar": n["placar"], "aprovada": n.get("aprovada")} if n else {})})
    return saida


def gerar(saida, deputados: dict, detalhes: dict, autorias: dict, votacoes_projeto: dict, nominais: dict,
          senadores: list, autorias_senado: dict, votacoes_senado: list, tipos: set, destino) -> int:
    """Grava o índice e as fichas; devolve quantas proposições entraram. `nominais`: votações nominais da Câmara por id."""
    indice, fichas = [], {}
    deputados = {str(k): v for k, v in deputados.items()}   # chaves int no gerar.py, str nos arquivos de autoria

    # --- Câmara: autores = quem assinou (proposicoes_autores.json) + quem a tem na própria lista (cobre autoria ainda não coletada)
    por_id, donos = {}, defaultdict(list)
    for did, d in deputados.items():
        for p in d["proposicoes"]:
            if p.get("tipo") in tipos:
                por_id.setdefault(p["id"], {**p, **{c: v for c, v in (detalhes.get(str(p["id"])) or {}).items() if c in ("situacao", "orgao", "dataApresentacao")}})
                donos[p["id"]].append(str(did))
    for pid, p in por_id.items():
        aut = autorias.get(str(pid)) or {}
        autores, vistos = [], set()
        for i, nome, *_ in aut.get("autores", []):
            dep = deputados.get(str(i)) if i is not None else None
            autores.append({"nome": dep["nome"] if dep else nome, "casa": "c",
                            **({"id": str(i), "partido": dep["partido"], "uf": dep["uf"]} if dep else {}),
                            **({"principal": True} if i is not None and i == aut.get("idPrincipal") else {})})
            vistos.add(str(i))
        for did in donos[pid]:
            if did not in vistos:
                autores.append({"nome": deputados[did]["nome"], "casa": "c", "id": did, "partido": deputados[did]["partido"], "uf": deputados[did]["uf"]})
        item = _item("c", p, destino)
        indice.append(item)
        fichas[item["k"]] = {**item, "orgao": p.get("orgao"), "apresentacao": p.get("dataApresentacao"), "autores": autores,
                             "votacoes": _votacoes(votacoes_projeto.get(str(pid)), nominais)}

    # --- Senado: a matéria aparece nas autorias de cada senador; o Plenário é ligado pelo código da matéria (propId)
    sen = {str(s["id"]): s for s in senadores}
    nominais_sen = defaultdict(list)
    for v in votacoes_senado:
        if v.get("propId"):
            nominais_sen[str(v["propId"])].append(v)
    materias = {}
    for sid, itens in autorias_senado.items():
        if sid not in sen:
            continue
        for a in itens:
            if a.get("tipo") not in tipos:
                continue
            m = materias.setdefault(a["id"], {"p": a, "autores": []})
            m["autores"].append({"nome": sen[sid]["nome"], "casa": "s", "id": sid, "partido": sen[sid].get("partido"), "uf": sen[sid].get("uf"),
                                 **({"principal": True} if a.get("principal") else {})})
    for mid, m in materias.items():
        a = m["p"]
        item = _item("s", {"id": mid, "tipo": a["tipo"], "numero": a["numero"], "ano": a["ano"], "ementa": a.get("ementa"), "situacao": a.get("situacao")}, destino)
        indice.append(item)
        votacoes = [{"id": str(v["id"]), "data": v["data"], "descricao": v["descricao"], "nominal": True, "placar": v["placar"], "aprovada": v.get("aprovada"),
                     **({"secreta": True} if v.get("secreta") else {})}
                    for v in sorted(nominais_sen.get(mid, []), key=lambda x: x["data"], reverse=True)[:MAX_VOTACOES]]
        fichas[item["k"]] = {**item, "apresentacao": a.get("dataApresentacao"), "autores": sorted(m["autores"], key=lambda x: not x.get("principal")),
                             "votacoes": votacoes}

    indice.sort(key=lambda i: (i["a"], i["n"]), reverse=True)
    salvar(saida / "proposicoes.json", indice)
    for k, ficha in fichas.items():
        salvar(saida / "proposicao" / f"{k}.json", ficha)
    return len(indice)
