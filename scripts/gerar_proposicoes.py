"""
Índice de proposições (projetos, PECs…) para a página proposicoes.html, e os políticos ligados a cada uma:
autores (deputados e senadores com ficha no site) e as votações do Plenário em que foi votada.

  site/dados/proposicoes.json        índice, uma linha por proposição (a busca roda no navegador; também dá o cabeçalho da ficha)
  site/dados/proposicao/<casa>-<ano>.json   {id: {o: órgão, ap: apresentação, au: autores, v: votações, em: ementa completa (só se o índice a cortou),
                                     ed: ementa detalhada, pc: palavras-chave, rg: regime, tr: última tramitação, ds: data dela, tx: link do inteiro teor,
                                     pr: id do projeto principal (se apensada), rl: id do deputado relator (nome e partido vêm de deputados.json), tm: temas, ls: ids das leis citadas}} das proposições do ano
                                     (casa: "c" Câmara, "s" Senado)
  site/dados/leis.json               {id da lei: {r: rótulo, u: link do LexML, e: ementa oficial, p: link do Planalto}} só das leis citadas (leis.py,
                                     coletar_leis.py); o texto da ementa citante fica no índice e na ficha, a lei aqui, uma vez só
  site/dados/senadores.json          id, nome, partido e UF dos senadores (os deputados já estão em deputados.json)
  site/dados/nucleo/autorias.json    a relação proposição -> pessoa: {porPessoa: {id da pessoa: [[chave da proposição, 1 se principal], ...]},
                                     semPessoa, proposicoes}; a chave é a mesma do índice ("c-<id>", "s-<id>"), o id da pessoa é o do núcleo
                                     de identidades. Autor sem ficha no site (ex-deputado, ministro, comissão) conta em `semPessoa`

Nada se repete: ementa e situação ficam só no índice; nome, partido e UF dos autores, só nas listas de deputados e senadores;
placar e resultado das votações, só em votacoes[_senado].json; o voto de cada político, só em votacao[_senado]/<id>.json.
Os autores são {id[, p: 1 se principal]} ou, sem ficha no site, {nome}. Não acessa a internet.
"""

from collections import defaultdict

import leis as modulo_leis
from gerar_politicos import salvar

TAMANHO_EMENTA = 180
MAX_VOTACOES = 30


def _item(casa: str, p: dict, destino) -> dict:
    """Linha do índice: chave, tipo, número, ano, ementa curta, situação e destino (aprovada, rejeitada, tramitando, sem)."""
    return {"k": f"{casa}-{p['id']}", "c": casa, "t": p["tipo"], "n": p["numero"], "a": p["ano"],
            "e": (p.get("ementa") or "").strip()[:TAMANHO_EMENTA], "s": p.get("situacao"), "d": destino(p.get("situacao"), bool(p.get("tramitacao") or p.get("dataSituacao")))}


def _sem_vazios(d: dict) -> dict:
    return {k: v for k, v in d.items() if v not in (None, "", [])}


def _votacoes(lista: list | None, nominais: dict) -> list:
    """Id e data; a descrição só das que não são nominais (das nominais ela está em votacoes.json)."""
    saida = []
    for v in sorted(lista or [], key=lambda x: x.get("data") or "", reverse=True)[:MAX_VOTACOES]:
        saida.append({"id": str(v["id"]), "data": v.get("data"), **({} if str(v["id"]) in nominais else {"descricao": v.get("descricao")})})
    return saida


def _complemento(p: dict, det: dict, temas: list | None, citadas: dict) -> dict:
    """Campos da ficha que vêm do detalhe da proposição: ementa inteira (o índice corta), ementa detalhada, palavras-chave, regime,
    última tramitação, link do texto, projeto principal, temas e as leis citadas (que entram em `citadas`: id -> lei)."""
    ementa = (p.get("ementa") or "").strip()
    detalhada = (det.get("ementaDetalhada") or "").strip()
    regime = (det.get("regime") or "").strip()
    achadas = modulo_leis.de_textos(ementa, detalhada)
    citadas.update({l["id"]: l for l in achadas})
    return {"em": ementa if len(ementa) > TAMANHO_EMENTA else None, "ed": detalhada if detalhada != ementa else None,
            "pc": det.get("palavrasChave"), "rg": regime if regime not in ("", ".") else None, "tr": det.get("tramitacao"),
            "ds": det.get("dataSituacao"), "tx": det.get("inteiroTeor"), "pr": det.get("apensadoA"), "rl": det.get("relator"), "tm": temas,
            "ls": [l["id"] for l in achadas]}


def _salvar_leis(saida, citadas: dict, leis_coletadas: dict) -> None:
    """leis.json: só as leis citadas; o resumo é a ementa oficial, quando já foi coletada."""
    salvar(saida / "leis.json", {i: _sem_vazios({"r": l["rotulo"], "u": modulo_leis.url_lexml(l["urn"]),
                                                  "e": (leis_coletadas.get(i) or {}).get("ementa"), "p": (leis_coletadas.get(i) or {}).get("planalto")})
                                 for i, l in sorted(citadas.items())})


def gerar(saida, deputados: dict, detalhes: dict, autorias: dict, votacoes_projeto: dict, nominais: dict,
          senadores: list, autorias_senado: dict, votacoes_senado: list, tipos: set, destino, pessoas: dict | None = None,
          temas: dict | None = None, leis_coletadas: dict | None = None) -> int:
    """Grava o índice e as fichas; devolve quantas proposições entraram. `nominais`: votações nominais da Câmara por id.
    `pessoas`: identidades.construir()["chaves"], para a relação proposição -> pessoa. `temas`: proposicoes_temas.json;
    `leis_coletadas`: dados/leis.json (ementa oficial das leis citadas)."""
    indice, fichas = [], defaultdict(dict)
    citadas, temas = {}, temas or {}
    pessoas = pessoas or {}
    por_pessoa, sem_pessoa = defaultdict(list), 0
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
        for au in autores:
            quem = pessoas.get(("camara", au["id"])) if "id" in au else None
            if quem:
                por_pessoa[quem].append([item["k"], au.get("p", 0)])
            else:
                sem_pessoa += 1
        fichas[f"c-{p['ano']}"][str(pid)] = _sem_vazios({"o": p.get("orgao"), "ap": p.get("dataApresentacao"), "au": autores,
                                                         "v": _votacoes(votacoes_projeto.get(str(pid)), nominais),
                                                         **_complemento(p, detalhes.get(str(pid)) or {}, temas.get(str(pid)), citadas)})

    # --- principais dos apensados, de autor fora da legislatura: o detalhe guarda tipo, número e ementa (sem autores na ficha)
    conhecidas = {str(i) for i in por_id}
    for pid, det in detalhes.items():
        if det.get("tipo") in tipos and pid not in conhecidas:
            p = {"id": pid, **{c: det.get(c) for c in ("tipo", "numero", "ano", "ementa", "situacao", "tramitacao", "dataSituacao")}}
            indice.append(_item("c", p, destino))
            fichas[f"c-{p['ano']}"][pid] = _sem_vazios({"o": det.get("orgao"), "ap": det.get("dataApresentacao"), "au": [],
                                                        **_complemento(p, det, temas.get(pid), citadas)})

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
        for au in m["autores"]:
            quem = pessoas.get(("senado", au["id"]))
            if quem:
                por_pessoa[quem].append([item["k"], au.get("p", 0)])
            else:
                sem_pessoa += 1
        votacoes = [{"id": str(v["id"]), "data": v["data"]}
                    for v in sorted(nominais_sen.get(mid, []), key=lambda x: x["data"], reverse=True)[:MAX_VOTACOES]]
        fichas[f"s-{a['ano']}"][mid] = _sem_vazios({"ap": a.get("dataApresentacao"), "au": sorted(m["autores"], key=lambda x: not x.get("p")), "v": votacoes,
                                                    **_complemento(a, {}, None, citadas)})

    indice.sort(key=lambda i: (int(i["a"] or 0), int(i["n"] or 0)), reverse=True)
    salvar(saida / "proposicoes.json", indice)
    salvar(saida / "nucleo" / "autorias.json", {"proposicoes": len(indice), "semPessoa": sem_pessoa,
                                                 "porPessoa": {k: sorted(v, key=lambda x: x[0]) for k, v in sorted(por_pessoa.items())}})
    for k, ficha in fichas.items():
        salvar(saida / "proposicao" / f"{k}.json", ficha)
    _salvar_leis(saida, citadas, leis_coletadas or {})
    salvar(saida / "senadores.json", [{"id": str(x["id"]), "nome": x["nome"], "partido": x.get("partido"), "uf": x.get("uf")} for x in senadores])
    return len(indice)
