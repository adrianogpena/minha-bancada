"""
Núcleo de candidaturas e disputas: o que o TSE publica em tabelas separadas, ligado por ids.

  site/dados/nucleo/candidaturas/<ano>.json   [{id, pessoa, cargo, uf, local, partido, numero, resultado, votos, ...}]
  site/dados/nucleo/disputas/<ano>.json   {id da disputa: {cargo, local, uf, vagas, turnos, partidos, coligacoes}}

Candidatura = um eleito numa eleição (o TSE aqui só traz eleitos e quem vai ao 2º turno), com `pessoa` (núcleo de
identidades), `partido` e `federacao` (ids do núcleo), votos, patrimônio e o resumo da campanha (receitas, despesas, de onde veio
o dinheiro e custo do voto). Vice não tem prestação de contas própria: `chapa` aponta para a candidatura do titular, que tem as contas.

Disputa = cargo + local de uma eleição. Junta o que estava em três arquivos por ano e UF (comparecimento e vagas; votos por partido;
coligações e federações), uma vez só, em vez de repetido na ficha de cada candidato. A disputa de uma candidatura tem o id
`id_disputa(ano, cargo, local)` (não vai no registro, para não repetir o que já se deduz). `coligacoes[].comEleitos` lista só
os partidos da coligação que elegeram alguém (o arquivo de origem guarda só esses); `composicao` traz todos, como o TSE escreve.

Ids: "can_<ano>_<sequencial do TSE>" e "dsp_<ano>_<cargo>_<local>" (cargo sem acento nem "VICE-": o vice disputa com o titular).
Campos omitidos quando se deduzem: `local` quando é a própria UF (cargos estaduais e federais), `situacao` quando é "eleito".
O detalhe das contas (doadores, gastos por categoria) e a votação por seção seguem nas fichas; aqui entra só o que liga e compara.
Não acessa a internet; chamado pelo scripts/gerar.py.
"""

import re
import unicodedata
from pathlib import Path

import identidades
from gerar_politicos import custo_do_voto, ler, salvar

ORIGENS = {   # origem da receita (TSE) -> chave curta
    "Recursos de pessoas físicas": "pessoasFisicas", "Recursos próprios": "proprios", "Recursos de outros candidatos": "outrosCandidatos",
    "Recursos de partido político": "partido", "Recursos de Financiamento Coletivo": "financiamentoColetivo",
    "Rendimentos de aplicações financeiras": "aplicacoes", "Recursos de origens não identificadas": "naoIdentificada",
    "Doações pela Internet": "internet",
}


def _slug(texto: str) -> str:
    t = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", t.lower()).strip("_")


def id_disputa(ano: int, cargo: str, local: str) -> str:
    return f"dsp_{ano}_{_slug(cargo.replace('VICE-', ''))}_{local}"


def _origem(rotulo: str) -> str:
    return ORIGENS.get(rotulo) or _slug(rotulo)


def _disputas(bruto: Path, ano: int, uf: str) -> dict:
    """{chave "CARGO|local": disputa} a partir de disputa, partidos e coligações de um ano e UF."""
    disputa, partidos, aliancas = (ler(bruto / "tse" / pasta / str(ano) / f"{uf}.json", {}) or {} for pasta in ("disputa", "partidos", "coligacoes"))
    saida = {}
    for chave in sorted(set(disputa) | set(partidos) | set(aliancas), key=lambda c: (c.startswith("VICE-"), c)):
        cargo, local = chave.split("|")
        if cargo.startswith("VICE-") and f"{cargo[5:]}|{local}" in saida:    # o vice disputa com o titular: vale a linha do titular
            continue
        cargo = cargo.replace("VICE-", "")
        chave = f"{cargo}|{local}"
        d = {"cargo": cargo, "local": local, "uf": uf}
        if chave in disputa:
            d["vagas"] = disputa[chave].get("vagas")
            d["turnos"] = disputa[chave].get("turnos")
        if chave in partidos:
            d["totalVotosPartidos"] = partidos[chave]["totalVotos"]
            d["partidos"] = {}
            for sigla, (legenda, nominais, federacao) in partidos[chave]["partidos"].items():
                par = identidades.partido_id(sigla)
                fed = identidades.federacao_de(federacao)
                d["partidos"][par or sigla] = [legenda, nominais, *([identidades.federacao_id(fed)] if fed else [])]
        if chave in aliancas:
            membros = {}
            for sigla, i in aliancas[chave]["coligacaoDoPartido"].items():
                membros.setdefault(i, []).append(identidades.partido_id(sigla) or sigla)
            d["coligacoes"] = [{"tipo": tipo, "nome": nome or None, "composicao": composicao, "situacao": situacao, "comEleitos": sorted(membros.get(i, []))}
                               for i, (tipo, nome, composicao, situacao) in enumerate(aliancas[chave]["coligacoes"])]
        saida[chave] = d
    return saida


def construir(bruto: Path, nucleo: dict) -> dict:
    """Devolve {candidaturas, disputas: {ano: {id: disputa}}, resumo}. `nucleo` é o resultado de identidades.construir()."""
    chaves = nucleo["chaves"]
    candidaturas, disputas = [], {}
    sem = {"semPessoa": 0, "semDisputa": 0, "semContas": 0}
    for pasta in sorted(p for p in (bruto / "tse").glob("*") if p.is_dir() and p.name.isdigit()):
        ano = int(pasta.name)
        for arq in sorted(pasta.glob("[A-Z][A-Z].json")):
            uf = arq.stem
            eleitos = ler(arq, [])
            locais = _disputas(bruto, ano, uf)
            contas = ler(bruto / "tse" / "contas" / str(ano) / f"{uf}.json", {}) or {}
            for chave, d in locais.items():
                disputas.setdefault(ano, {})[id_disputa(ano, d["cargo"], d["local"])] = d
            for e in eleitos:
                pessoa = chaves.get(("tse", ano, e["sequencial"]))
                if not pessoa:
                    sem["semPessoa"] += 1
                vice = e["cargo"].startswith("VICE-")
                chave = f"{e['cargo'].replace('VICE-', '')}|{e['unidadeEleitoral']}"
                c = contas.get(e.get("sequencialChapa") or e["sequencial"])
                votos = e.get("votos") or []
                par = identidades.partido_id(e.get("partido"))
                fed = identidades.federacao_de(e.get("federacao"))
                if not vice and not c and ano < 2026:
                    sem["semContas"] += 1
                if chave not in locais and ano < 2026:
                    sem["semDisputa"] += 1
                cand = {
                    "id": f"can_{ano}_{e['sequencial']}", "pessoa": pessoa, "cargo": e["cargo"], "uf": "BR" if e["uf"] in ("BR", "BRASIL") else e["uf"],
                    "local": e["unidadeEleitoral"] if e["unidadeEleitoral"] != e["uf"] else None, "partido": par, "federacao": identidades.federacao_id(fed) if fed else None,
                    "numero": e.get("numero"), "resultado": e.get("resultado"), "situacao": e.get("situacao") if e.get("situacao") != "eleito" else None,
                    "votos": sum(v.get("votos") or 0 for v in votos) or None, "percentual": votos[-1].get("percentual") if votos else None,
                    "bens": e.get("totalBens") or None,
                    "chapa": f"can_{ano}_{e['sequencialChapa']}" if vice and e.get("sequencialChapa") else None,
                }
                if c and not vice:
                    custo = custo_do_voto(e, c)
                    cand.update(receitas=c["receitas"], despesas=c.get("despesasPagas"),
                                origens={_origem(o): v for o, v in c["origensReceita"]} or None,
                                custoVoto=round(custo, 2) if custo is not None else None)
                candidaturas.append({k: v for k, v in cand.items() if v is not None})
    candidaturas.sort(key=lambda c: c["id"])
    return {"candidaturas": candidaturas, "disputas": disputas,
            "resumo": {"candidaturas": len(candidaturas), "disputas": sum(len(m) for m in disputas.values()), **sem,
                       "comContas": sum(1 for c in candidaturas if "receitas" in c)}}


def salvar_candidaturas(res: dict, saida: Path) -> None:
    por_ano = {}
    for c in res["candidaturas"]:
        por_ano.setdefault(c["id"].split("_")[1], []).append(c)
    for ano, lista in por_ano.items():
        salvar(saida / "nucleo" / "candidaturas" / f"{ano}.json", lista)
    for ano, mapa in res["disputas"].items():
        salvar(saida / "nucleo" / "disputas" / f"{ano}.json", mapa)
    r = res["resumo"]
    print(f"Candidaturas: {r['candidaturas']} ({r['comContas']} com contas); disputas: {r['disputas']}")
