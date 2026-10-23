"""
Índice de proposições (projetos, PECs…) para a página proposicoes.html, e os políticos ligados a cada uma:
autores (deputados e senadores com ficha no site) e as votações do Plenário em que foi votada.

  site/dados/proposicoes.json        índice, uma linha por proposição (a busca roda no navegador; também dá o cabeçalho da ficha)
  site/dados/proposicao/<casa>-<ano>.json   {id: {o: órgão, ap: apresentação, au: autores, v: votações}} das proposições do ano
                                     (casa: "c" Câmara, "s" Senado)
  site/dados/senadores.json          id, nome, partido e UF dos senadores (os deputados já estão em deputados.json)

Nada se repete: ementa e situação ficam só no índice; nome, partido e UF dos autores, só nas listas de deputados e senadores;
placar e resultado das votações, só em votacoes[_senado].json; o voto de cada político, só em votacao[_senado]/<id>.json.
Os autores são {id[, p: 1 se principal]} ou, sem ficha no site, {nome}. Não acessa a internet.
"""

from collections import defaultdict

from gerar_politicos import salvar

TAMANHO_EMENTA = 180
MAX_VOTACOES = 30


def _item(casa: str, p: dict, destino) -> dict:
    """Linha do índice: chave, tipo, número, ano, ementa curta, situação e destino (aprovada, rejeitada, tramitando, sem)."""
    return {"k": f"{casa}-{p['id']}", "c": casa, "t": p["tipo"], "n": p["numero"], "a": p["ano"],
            "e": (p.get("ementa") or "").strip()[:TAMANHO_EMENTA], "s": p.get("situacao"), "d": destino(p.get("situacao"))}


def _sem_vazios(d: dict) -> dict:
    return {k: v for k, v in d.items() if v not in (None, "", [])}


def _votacoes(lista: list | None, nominais: dict) -> list:
    """Id e data; a descrição só das que não são nominais (das nominais ela está em votacoes.json)."""
    saida = []
    for v in sorted(lista or [], key=lambda x: x.get("data") or "", reverse=True)[:MAX_VOTACOES]:
        saida.append({"id": str(v["id"]), "data": v.get("data"), **({} if str(v["id"]) in nominais else {"descricao": v.get("descricao")})})
    return saida


def gerar(saida, deputados: dict, detalhes: dict, autorias: dict, votacoes_projeto: dict, nominais: dict,
          senadores: list, autorias_senado: dict, votacoes_senado: list, tipos: set, destino) -> int:
    """Grava o índice e as fichas; devolve quantas proposições entraram. `nominais`: votações nominais da Câmara por id."""
    indice, fichas = [], defaultdict(dict)
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
            autores.append({"id": str(i), **({"p": 1} if i == aut.get("idPrincipal") else {})} if dep else {"nome": nome})
            vistos.add(str(i))
        for did in donos[pid]:
            if did not in vistos:
                autores.append({"id": did})
        item = _item("c", p, destino)
        indice.append(item)
        fichas[f"c-{p['ano']}"][str(pid)] = _sem_vazios({"o": p.get("orgao"), "ap": p.get("dataApresentacao"), "au": autores,
                                                         "v": _votacoes(votacoes_projeto.get(str(pid)), nominais)})

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
            m["autores"].append({"id": sid, **({"p": 1} if a.get("principal") else {})})
    for mid, m in materias.items():
        a = m["p"]
        item = _item("s", {"id": mid, "tipo": a["tipo"], "numero": a["numero"], "ano": a["ano"], "ementa": a.get("ementa"), "situacao": a.get("situacao")}, destino)
        indice.append(item)
        votacoes = [{"id": str(v["id"]), "data": v["data"]}
                    for v in sorted(nominais_sen.get(mid, []), key=lambda x: x["data"], reverse=True)[:MAX_VOTACOES]]
        fichas[f"s-{a['ano']}"][mid] = _sem_vazios({"ap": a.get("dataApresentacao"), "au": sorted(m["autores"], key=lambda x: not x.get("p")), "v": votacoes})

    indice.sort(key=lambda i: (i["a"], i["n"]), reverse=True)
    salvar(saida / "proposicoes.json", indice)
    for k, ficha in fichas.items():
        salvar(saida / "proposicao" / f"{k}.json", ficha)
    salvar(saida / "senadores.json", [{"id": str(x["id"]), "nome": x["nome"], "partido": x.get("partido"), "uf": x.get("uf")} for x in senadores])
    return len(indice)
