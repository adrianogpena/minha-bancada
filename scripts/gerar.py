"""
Transforma o cache bruto (dados/) nos arquivos JSON enxutos que o site lê
(site/dados/). Não acessa a internet.

Uso:
    python scripts/gerar.py
"""

import re
import shutil
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import categorias
import gerar_estaduais
import doadores
import empresas
import fornecedores as nucleo_fornecedores
import candidaturas
import identidades
import mandatos
import gerar_prefeituras
import gerar_politicos
import gerar_proposicoes
from gerar_politicos import ler, salvar

RAIZ = Path(__file__).resolve().parent.parent
BRUTO = RAIZ / "dados"
SAIDA = RAIZ / "site" / "dados"

VOTOS_NORMAIS = {"Sim": "sim", "Não": "nao", "Abstenção": "abstencao",
                 "Obstrução": "obstrucao", "Artigo 17": "art17"}


def tipo_voto(v: str | None) -> str:
    return VOTOS_NORMAIS.get(v or "", "outro")


def juntar_detalhe(p: dict, det: dict | None) -> dict:
    """Acrescenta à proposição a situação atual, quando já foi consultada.
    Mesmos nomes do dados/proposicoes_detalhe.json, exceto `inteiroTeor` (linkTexto no site)."""
    if not det:
        return p
    campos = ("dataApresentacao", "situacao", "despacho", "orgao", "dataSituacao", "ementaDetalhada", "palavrasChave",
              "tramitacao", "regime", "apensadoA", "anterior", "posterior")
    return {**p, **{c: det[c] for c in campos if det.get(c)}, **({"linkTexto": det["inteiroTeor"]} if det.get("inteiroTeor") else {})}


MAX_COAUTORES = 15


def partido_em(historico: list | None, dia: str | None) -> str | None:
    """Partido do deputado em `dia` (AAAA-MM-DD) pelo histórico da legislatura: o último registro até o dia.
    None quando não há histórico, o dia ou registro com partido até essa data (quem chama usa o partido atual)."""
    if not historico or not dia:
        return None
    ate = [h for h in historico if h.get("partido") and h.get("data") and h["data"] <= dia[:10]]
    return max(ate, key=lambda h: h["data"])["partido"] if ate else None


def juntar_autoria(p: dict, aut: dict | None, did: str, partidos: dict | None = None,
                   historicos: dict | None = None) -> dict:
    """Acrescenta, quando a autoria do projeto já foi coletada: `principal` (o deputado foi o primeiro
    a assinar), `coautores` (outros autores, com o partido entre parênteses quando é deputado em exercício;
    até MAX_COAUTORES), `totalAutores` (total de autores), `partidosDistintos` (partidos distintos entre os autores que são
    deputados em exercício, quando há mais de um) e `iniciativa` (tipo do autor principal, quando não é
    deputado: Poder Executivo, Senado, comissão...). O partido de cada autor é o da data de apresentação do projeto
    (`historicos`: id -> histórico da legislatura); sem histórico ou data, o atual (`partidos`)."""
    if not aut or not aut.get("autores"):
        return p
    partidos = partidos or {}
    historicos = historicos or {}

    def sigla_de(i) -> str | None:
        return partido_em(historicos.get(str(i)), p.get("dataApresentacao")) or partidos.get(str(i))

    outros = []
    for i, nome, *_ in aut["autores"]:
        if str(i) == did:
            continue
        sigla = sigla_de(i)
        outros.append(f"{nome} ({sigla})" if sigla else nome)
    if len(outros) > MAX_COAUTORES:
        outros = outros[:MAX_COAUTORES] + [f"e mais {len(outros) - MAX_COAUTORES}"]
    siglas = {s for i, *_ in aut["autores"] if (s := sigla_de(i))}
    primeiro = aut["autores"][0]
    extra = {"principal": str(aut.get("idPrincipal")) == did}
    if outros:
        extra["coautores"] = outros
        extra["totalAutores"] = len(aut["autores"])
    if len(siglas) > 1:
        extra["partidosDistintos"] = len(siglas)
    if aut.get("idPrincipal") is None and len(primeiro) > 2 and primeiro[2]:
        extra["iniciativa"] = primeiro[2]
    return {**p, **extra}


TIPOS_PROJETO = {"PL", "PLP", "PEC", "PDL", "PRC", "PLC", "PLS", "PRS", "PDS", "PLN", "PFC", "PLV", "MPV"}


def destino_projeto(situacao: str | None) -> str:
    """Mesma classificação de `desfecho` em site/assets/js/apis.js: aprovada, rejeitada, tramitando ou sem (sem desfecho conhecido)."""
    s = unicodedata.normalize("NFD", (situacao or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    if not situacao or "tramitacao encerrada" in s:
        return "sem"
    if re.match(r"(sancionad|promulgad|aprovad)", s):
        return "aprovada"
    if re.match(r"rejeitad", s):
        return "rejeitada"
    if re.search(r"transformad[ao] em (norma|lei)|sancionad", s):
        return "aprovada"
    if re.search(r"arquivad|retirad|vetad|prejudicad", s):
        return "rejeitada"
    if re.search(r"remetid[ao] a camara|aguardando sancao|remetid.*(sancao|senado)", s):
        return "aprovada"
    return "tramitando"


def resumir_autoria(proposicoes: list) -> dict:
    """Contagens de autoria dos projetos (não dos requerimentos e afins) do deputado, a partir das proposições já enriquecidas:
    `projetos`, `autoriaColetada` (projetos com a ordem de assinatura conhecida), `proprias` (autor principal),
    `aprovadasProprias` (autor principal e aprovado ou virou lei), `suprapartidarios` (assinados por deputados de mais de um partido)."""
    projetos = [p for p in proposicoes if p.get("tipo") in TIPOS_PROJETO]
    com_autoria = [p for p in projetos if p.get("principal") is not None]
    proprias = [p for p in com_autoria if p["principal"]]
    return {
        "projetos": len(projetos), "autoriaColetada": len(com_autoria), "proprias": len(proprias),
        "aprovadasProprias": sum(1 for p in proprias if destino_projeto(p.get("situacao")) == "aprovada"),
        "suprapartidarios": sum(1 for p in com_autoria if p.get("partidosDistintos", 0) > 1),
    }


ORIENTACOES = {"Sim": "sim", "Não": "nao", "Obstrução": "obstrucao"}
VOTOU = ("sim", "nao", "abstencao", "obstrucao")
DIVERGENCIAS = 10


def sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFD", texto).encode("ascii", "ignore").decode().lower()


def partidos_do_bloco(rotulo: str, blocos: list) -> set:
    """Partidos do bloco que a Câmara chama de "Bl UniPpPsd..." em votacoesOrientacoes: o nome vem truncado, com um pedaço
    do nome de cada partido colado ao seguinte. Cada pedaço é o começo da sigla (UNIÃO vira "Uni"); só serve o bloco cujas
    siglas, na ordem do nome, consomem o rótulo inteiro. Vazio quando nenhum bloco (ou mais de um) combina."""
    alvo = sem_acento(rotulo.removeprefix("Bl ").removesuffix("..."))
    achados = []
    for b in blocos:
        if b.get("federacao"):
            continue
        resto = alvo
        for sigla in (sem_acento(x) for x in b["nome"].split(", ")):
            k = next((k for k in range(len(sigla), 1, -1) if resto.startswith(sigla[:k])), 0)
            if not k:
                break
            resto = resto[k:]
        if not resto:
            achados.append(b)
    if len(achados) != 1:
        return set()
    return {x.upper() for x in achados[0]["partidos"] or achados[0]["nome"].split(", ")}  # blocos de um partido só vêm sem lista


def bancada_do_partido(partido: str, bancadas, blocos: dict | None = None) -> str | None:
    """Nome da bancada que orientou pelo partido numa votação: a sigla do partido, a federação ("Fdr PT-PCdoB-PV", às vezes
    truncada, como "Fdr PSDB-CIDADAN") ou o bloco ("Bl UniPpPsd...", ligado aos partidos por `blocos`: {rótulo: partidos})."""
    p = (partido or "").upper()
    for b in bancadas:
        if b.upper() == p:
            return b
    for b in bancadas:
        if b.startswith("Fdr ") and any(m == p or (len(m) >= 5 and p.startswith(m)) for m in b[4:].upper().split("-")):
            return b
    for b in bancadas:
        if p in (blocos or {}).get(b, ()):  # já em maiúsculas (partidos_do_bloco)
            return b
    return None


def resumir_comportamento(votos: list, orientacoes: dict, partido: str, blocos: dict | None = None) -> dict | None:
    """Quanto o deputado votou como o partido e como o Governo orientaram, só nas votações em que votou e a bancada deu
    orientação Sim, Não ou Obstrução (Liberado não conta). Usa o partido atual do deputado. None sem nenhuma orientação."""
    contas = {"partido": [0, 0], "governo": [0, 0]}
    divergencias = []
    for v in votos:
        o = orientacoes.get(v["id"])
        if not o or v["voto"] not in VOTOU:
            continue
        banc = bancada_do_partido(partido, [b for b in o if b != "Governo"], blocos)
        for chave, bancada in (("partido", banc), ("governo", "Governo" if "Governo" in o else None)):
            esperado = ORIENTACOES.get(o.get(bancada)) if bancada else None
            if not esperado:
                continue
            contas[chave][0] += 1
            if esperado == v["voto"]:
                contas[chave][1] += 1
            elif len(divergencias) < 3 * DIVERGENCIAS:
                divergencias.append({"id": v["id"], "data": v["data"], "proposicao": v.get("proposicao"), "descricao": v["descricao"],
                                     "contra": chave, "bancada": bancada, "orientacao": o[bancada], "voto": v["voto"]})
    if not any(c[0] for c in contas.values()):
        return None
    divergencias.sort(key=lambda x: x["data"], reverse=True)
    return {**{k: {"total": c[0], "seguiu": c[1]} for k, c in contas.items()}, "divergencias": divergencias[:DIVERGENCIAS]}


def medianas_sessoes(presenca: dict) -> dict:
    """Mediana de sessões deliberativas com presença, por ano, entre os deputados com alguma presença."""
    medianas = {}
    for ano, p in presenca.items():
        todos = sorted(d["sessoes"] for d in p["deputados"].values() if d["sessoes"])
        medianas[ano] = todos[len(todos) // 2] if todos else 0
    return medianas


def presenca_do_deputado(did: str, presenca: dict, medianas: dict) -> list:
    """Presença do deputado nos eventos da Câmara, um item por ano (do mais recente): sessões deliberativas do Plenário
    (presentes, total do ano e mediana dos deputados), reuniões de comissão e audiências, e outros eventos.
    Anos em que o deputado não aparece ficam de fora."""
    return [{"ano": int(ano), **presenca[ano]["deputados"][str(did)], "sessoesDeliberativas": presenca[ano]["sessoesDeliberativas"],
             "medianaSessoes": medianas[ano]}
            for ano in sorted(presenca, reverse=True) if str(did) in presenca[ano]["deputados"]]


def juntar_votacoes(p: dict, votacoes_projeto: list | None, nominais: dict, orientacoes: dict) -> dict:
    """Acrescenta ao projeto as votações dele (`votacoes`, as mais recentes primeiro, até MAX_VOTACOES_PROJETO). As nominais
    levam placar, resultado e as orientações das bancadas; as simbólicas e as de outros órgãos só data e descrição."""
    if not votacoes_projeto:
        return p
    saida = []
    for v in sorted(votacoes_projeto, key=lambda x: x["data"] or "", reverse=True)[:MAX_VOTACOES_PROJETO]:
        item = {"id": v["id"], "data": v["data"], "descricao": v["descricao"]}
        n = nominais.get(v["id"])
        if n:
            item.update(nominal=True, placar=n["placar"], aprovada=n["aprovada"])
            if n.get("orgao"):
                item["orgao"] = n["orgao"]
            if orientacoes.get(v["id"]):
                item["orientacoes"] = orientacoes[v["id"]]
        saida.append(item)
    return {**p, "votacoes": saida, "totalVotacoes": len(votacoes_projeto)}


MAX_VOTACOES_PROJETO = 8


def resumir_temas(proposicoes: list) -> list:
    """Temas oficiais dos projetos (já com `temas` e `principal` juntados): [[tema, projetos, aprovados, como autor principal]],
    do mais frequente para o menos. Projeto com vários temas conta em cada um."""
    por_tema: dict[str, list] = {}
    for p in proposicoes:
        for t in p.get("temas", []):
            c = por_tema.setdefault(t, [0, 0, 0])
            c[0] += 1
            c[1] += destino_projeto(p.get("situacao")) == "aprovada"
            c[2] += bool(p.get("principal"))
    return sorted(([t, *c] for t, c in por_tema.items()), key=lambda x: (-x[1], x[0]))


def ordenar_orgaos(orgaos: list) -> list:
    """Órgãos em que o deputado está agora primeiro (sem data de fim), depois os que deixou, do mais recente para o mais antigo."""
    recentes = sorted(orgaos, key=lambda o: o.get("inicio") or "", reverse=True)
    return sorted(recentes, key=lambda o: bool(o.get("fim")))


# cota parlamentar mensal (CEAP) de cada UF, em reais: tabela "valores atuais" do guia para jornalistas da Câmara (verificada em 2026-10-22, sem data de vigência na página)
LIMITE_COTA_UF = {
    "AC": 57359.87, "AL": 53164.36, "AM": 56151.46, "AP": 55929.26, "BA": 50965.29, "CE": 54879.34, "DF": 41612.55, "ES": 49160.15,
    "GO": 46979.73, "MA": 54537.99, "MG": 47645.91, "MS": 52707.93, "MT": 51439.83, "PA": 54624.17, "PB": 54402.48, "PE": 53997.81,
    "PI": 53195.84, "PR": 50807.19, "RJ": 47267.41, "RN": 55198.09, "RO": 56267.90, "RR": 58474.70, "RS": 53086.78, "SC": 51951.42,
    "SE": 52248.86, "SP": 48727.46, "TO": 51525.80,
}
MAIORES_NOTAS = 10


def maiores_notas(itens: list) -> list:
    """As maiores despesas do ano que têm o documento fiscal publicado, para o site listar com o link."""
    com_doc = [i for i in itens if i.get("documento") and i.get("valor")]
    return [{k: i.get(k) for k in ("data", "mes", "tipo", "fornecedor", "valor", "documento")}
            for i in sorted(com_doc, key=lambda i: -i["valor"])[:MAIORES_NOTAS]]


def limite_cota(uf: str, itens: list) -> dict | None:
    """Limite mensal da UF e quantos meses do ano já têm despesa lançada (a cota não usada acumula dentro do ano)."""
    mensal = LIMITE_COTA_UF.get(uf)
    meses = max((i["mes"] for i in itens if i.get("mes")), default=0)
    return {"mensal": mensal, "meses": meses} if mensal and meses else None


def resumir_despesas(ano: int, itens: list) -> dict:
    """Totais por tipo, mês e fornecedor, no formato que o site usa para deputados e senadores."""
    por_tipo, por_mes, fornecedores = Counter(), Counter(), Counter()
    for i in itens:
        por_tipo[i["tipo"]] += i["valor"]
        por_mes[i["mes"]] += i["valor"]
        fornecedores[i["fornecedor"] or "Não informado"] += i["valor"]
    return {
        "ano": ano, "total": round(sum(por_tipo.values()), 2),
        "porCategoria": categorias.agrupar(por_tipo),
        "porMes": sorted(([k, round(v, 2)] for k, v in por_mes.items())),
        "fornecedores": [[k, round(v, 2)] for k, v in fornecedores.most_common(10)],
        "recentes": itens[:30],
    }


def categoria_presenca(tipo: str, rotulo: str | None) -> str:
    """Classifica o registro de um senador numa votação nominal: compareceu (votou ou registrou presença sem voto),
    naoCompareceu, licenca, missao (missão oficial ou atividade parlamentar), ignorar (dispositivo não aplicável) ou outros."""
    if tipo != "ausente":
        return "compareceu"
    sigla, _, desc = (rotulo or "").partition("|")
    s, d = sigla.strip().lower(), desc.lower()
    if s == "p-nrv" or "presente" in d:
        return "compareceu"
    if s == "ncom" or "não compareceu" in d or "nao compareceu" in d:
        return "naoCompareceu"
    if s in ("ls", "lp", "lap") or "licen" in d:
        return "licenca"
    if s in ("mis", "ap") or any(k in d for k in ("missão", "missao", "atividade", "representa")):
        return "missao"
    if s == "na" or "não citado" in d or "nao citado" in d:
        return "ignorar"
    return "outros"


def resumir_presenca(c: Counter) -> dict:
    """Comparecimento do senador às votações nominais em que tem registro. Dispositivo não aplicável não entra na base."""
    base = sum(n for k, n in c.items() if k != "ignorar")
    return {"votacoes": base, **{k: c[k] for k in ("compareceu", "naoCompareceu", "licenca", "missao", "outros") if c[k]}}


def gerar_senadores() -> list:
    """Votos e projetos dos senadores em exercício -> site/dados/senador/<id>.json,
    site/dados/votacoes_senado.json (lista, sem o voto de cada um) e
    site/dados/votacao_senado/<id>.json (uma votação com o voto de cada senador)."""
    senadores = ler(BRUTO / "senado.json", []) or []
    if not senadores:
        return []
    votacoes = []
    for arq in sorted((BRUTO / "senado_votacoes").glob("[0-9]*.json")):
        votacoes += ler(arq, {}).values()
    votacoes.sort(key=lambda v: (v["data"], v.get("hora") or ""), reverse=True)
    autorias = ler(BRUTO / "senado_autorias.json", {}) or {}
    ceaps = ler(BRUTO / "senado_ceaps.json", {}) or {}
    recursos = ler(BRUTO / "senado_recursos.json", {}) or {}
    fichas = ler(BRUTO / "senado_ficha.json", {}) or {}

    por_id = {str(s["id"]): s for s in senadores}
    resumo, votos_por_sen, primeira = [], defaultdict(dict), {}
    presenca = defaultdict(Counter)
    for v in votacoes:
        contagem = Counter(x[1] for x in v["votos"])
        placar = {k: n for k, n in contagem.items() if k != "ausente"}
        # placar oficial da API quando ela informa; senão, o que se conta dos votos individuais
        totais = v.get("totais")
        if totais:
            placar.update(totais)
        # votação em que ninguém tem voto com direção só pode ser secreta, mesmo em dados salvos antes do campo existir
        secreta = bool(v.get("secreta")) or (contagem["secreto"] > 0 and not any(contagem[k] for k in ("sim", "nao", "abstencao", "obstrucao")))
        item = {
            "id": v["id"], "data": v["data"], "hora": v.get("hora"), "descricao": v["descricao"],
            "proposicao": v.get("proposicao"), "propId": v.get("propId"), "ementa": v.get("ementa"),
            "aprovada": v.get("aprovada"), "resultadoTexto": v.get("resultadoTexto"),
            "placar": placar, "placarOficial": bool(totais), "ausentes": contagem["ausente"],
            **({"secreta": True} if secreta else {}),
            **({"sessao": v["sessao"]} if v.get("sessao") else {}),
        }
        resumo.append(item)
        por_partido = defaultdict(Counter)
        detalhados = []
        for sid, t, *resto in v["votos"]:
            votos_por_sen[sid][v["id"]] = t
            sen = por_id.get(str(sid))
            partido = (sen or {}).get("partido") or "?"
            por_partido[partido][t] += 1
            # rótulo oficial ("AP|Atividade parlamentar"): a parte depois de "|" explica a ausência
            motivo = resto[0].partition("|")[2] if t == "ausente" and resto and resto[0] else ""
            detalhados.append({
                "id": str(sid), "nome": sen["nome"] if sen else f"Senador {sid}",
                "partido": partido, "uf": (sen or {}).get("uf") or "", "voto": t,
                **({"motivo": motivo} if motivo else {}),
                # fora do exercício hoje: sem ficha no site para ligar
                **({} if sen else {"anterior": True}),
            })
            presenca[sid][categoria_presenca(t, resto[0] if resto else "")] += 1
            if sid not in primeira or v["data"] < primeira[sid]:
                primeira[sid] = v["data"]
        salvar(SAIDA / "votacao_senado" / f"{v['id']}.json", {
            **item,
            "porPartido": {p: dict(c) for p, c in sorted(por_partido.items())},
            "votos": sorted(detalhados, key=lambda x: x["nome"]),
        })
    salvar(SAIDA / "votacoes_senado.json", resumo)

    for s in senadores:
        sid = str(s["id"])
        desde = primeira.get(sid)  # antes do primeiro voto o senador pode nem estar em exercício
        propostas = [{k: v for k, v in a.items() if v not in (None, "")} for a in autorias.get(sid, [])]
        salvar(SAIDA / "senador" / f"{sid}.json", {
            "id": sid,
            "votos": [{"id": v["id"], "voto": votos_por_sen[sid].get(v["id"], "ausente")}
                      for v in resumo if desde and v["data"] >= desde],
            "proposicoes": propostas,
            **({"presenca": resumir_presenca(presenca[sid])} if presenca.get(sid) else {}),
            # sem o arquivo (coleta falhou) o site mostra só o link para o Portal da Transparência
            **({"despesas": resumir_despesas(ceaps["ano"], ceaps["itens"].get(sid, []))} if ceaps else {}),
            **({k: fichas[sid][k] for k in ("comissoes", "mandatos") if k in fichas[sid]} if sid in fichas else {}),
            **({"recursos": {"ano": recursos["ano"], **recursos["recursos"][sid],
                             **({"escritorios": recursos["escritorios"][sid]} if sid in recursos.get("escritorios", {}) else {})}}
               if sid in recursos.get("recursos", {}) else {}),
        })
    print(f"Gerado: {len(senadores)} senadores, {len(resumo)} votações nominais do Senado")
    return resumo


def gerar_eleitorado() -> None:
    """Perfil do eleitorado por estado (dados/tse/eleitorado): o ano mais recente que o estado tem."""
    for arq in sorted((BRUTO / "tse" / "eleitorado" / "2022").glob("[A-Z][A-Z].json")):
        for ano in (2024, 2022):
            dados = ler(BRUTO / "tse" / "eleitorado" / str(ano) / arq.name)
            if dados:
                salvar(SAIDA / "eleitorado" / arq.name, {"ano": ano, "locais": dados})
                break


def main():
    ids = ler(BRUTO / "deputados.json", [])
    if not ids:
        raise SystemExit("Nada em dados/. Rode antes: python scripts/coletar.py")

    deputados = {}
    for did in ids:
        d = ler(BRUTO / "deputados" / f"{did}.json")
        if d:
            deputados[did] = d
    nucleo = identidades.construir(deputados, BRUTO)

    # todas as votações do histórico, só as nominais (com votos registrados)
    votacoes = []
    for arq in sorted((BRUTO / "votacoes").glob("*.json")):
        votacoes += [v for v in ler(arq, {}).values() if v.get("votos")]
    votacoes.sort(key=lambda v: (v["data"], v.get("hora") or ""), reverse=True)

    detalhes = ler(BRUTO / "proposicoes_detalhe.json", {}) or {}
    autorias = ler(BRUTO / "proposicoes_autores.json", {}) or {}
    temas = ler(BRUTO / "proposicoes_temas.json", {}) or {}
    orgaos = ler(BRUTO / "orgaos_deputados.json", {}) or {}
    orientacoes = ler(BRUTO / "orientacoes.json", {}) or {}
    votacoes_projetos = ler(BRUTO / "proposicoes_votacoes.json", {}) or {}
    presenca = ler(BRUTO / "presenca_eventos.json", {}) or {}
    medianas = medianas_sessoes(presenca)
    blocos_lista = ler(BRUTO / "blocos.json", []) or []
    blocos = {b: partidos_do_bloco(b, blocos_lista) for b in {b for o in orientacoes.values() for b in o if b.startswith("Bl ")}}
    partidos = {str(i): d["partido"] for i, d in deputados.items() if d.get("partido")}
    historicos = {str(i): d["historico"] for i, d in deputados.items() if d.get("historico")}

    if SAIDA.exists():
        shutil.rmtree(SAIDA)

    votos_por_dep = defaultdict(list)
    lista_votacoes = []
    for v in votacoes:
        placar = Counter(tipo_voto(t) for _, t in v["votos"])
        por_partido = defaultdict(Counter)
        detalhados = []
        for did, t in v["votos"]:
            dep = deputados.get(did)
            votos_por_dep[did].append({
                "id": v["id"], "data": v["data"], "descricao": v["descricao"],
                "proposicao": v.get("proposicao"), "aprovada": v.get("aprovada"),
                "voto": tipo_voto(t),
            })
            partido = dep["partido"] if dep else "?"
            por_partido[partido][tipo_voto(t)] += 1
            detalhados.append({
                "id": did, "nome": dep["nome"] if dep else f"Deputado {did}",
                "partido": partido, "uf": dep["uf"] if dep else "",
                "voto": tipo_voto(t),
            })
        resumo = {
            "id": v["id"], "data": v["data"], "hora": v.get("hora"),
            "descricao": v["descricao"], "proposicao": v.get("proposicao"),
            "propId": v.get("propId"), "ementa": v.get("ementa"),
            "aprovada": v.get("aprovada"), "placar": dict(placar),
            **({"orgao": v["orgao"]} if v.get("orgao") else {}),
        }
        lista_votacoes.append(resumo)
        salvar(SAIDA / "votacao" / f"{v['id']}.json", {
            **resumo,
            "porPartido": {p: dict(c) for p, c in sorted(por_partido.items())},
            "votos": sorted(detalhados, key=lambda x: x["nome"]),
        })
    salvar(SAIDA / "votacoes.json", lista_votacoes)
    nominais = {r["id"]: r for r in lista_votacoes}

    total_nominais = len(votacoes)
    resumo_deps = []
    eleicoes_deps = gerar_politicos.eleicao_deputados(deputados)
    totais_gasto = {did: round(sum(i["valor"] for i in d["despesas"]["itens"]), 2) for did, d in deputados.items()}
    gastos_por_uf = defaultdict(list)
    for did, d in deputados.items():
        gastos_por_uf[d["uf"]].append(totais_gasto[did])
    for did, d in deputados.items():
        itens = d["despesas"]["itens"]
        por_tipo = Counter()
        por_mes = Counter()
        fornecedores = Counter()
        for i in itens:
            por_tipo[i["tipo"]] += i["valor"]
            por_mes[i["mes"]] += i["valor"]
            fornecedores[i["fornecedor"] or "Não informado"] += i["valor"]
        total_gasto = totais_gasto[did]
        votos = votos_por_dep.get(did, [])
        votou = sum(1 for x in votos if x["voto"] in ("sim", "nao", "abstencao", "art17"))
        proposicoes = [juntar_autoria(juntar_detalhe(p, detalhes.get(str(p["id"]))), autorias.get(str(p["id"])), str(did), partidos, historicos)
                       for p in d["proposicoes"]]
        for p in proposicoes:
            if p.get("tipo") in TIPOS_PROJETO and temas.get(str(p["id"])):
                p["temas"] = temas[str(p["id"])]
        proposicoes = [juntar_votacoes(p, votacoes_projetos.get(str(p["id"])), nominais, orientacoes) if p.get("tipo") in TIPOS_PROJETO else p
                       for p in proposicoes]
        autoria = resumir_autoria(proposicoes)
        comportamento = resumir_comportamento(votos, orientacoes, d["partido"], blocos)
        da_uf = gastos_por_uf[d["uf"]]

        salvar(SAIDA / "deputado" / f"{did}.json", {
            "id": did, "pessoa": nucleo["chaves"].get(("camara", str(did))), "nome": d["nome"], "nomeCivil": d.get("nomeCivil"),
            "partido": d["partido"], "uf": d["uf"], "foto": d.get("foto"),
            "email": d.get("email"), "situacao": d.get("situacao"), "gabinete": d.get("gabinete") or None,
            "nascimento": d.get("nascimento"),
            "naturalidade": ", ".join(x for x in (d.get("municipioNascimento"), d.get("ufNascimento")) if x),
            "escolaridade": d.get("escolaridade"), "redesSociais": d.get("redesSociais", []),
            "proposicoes": proposicoes, "autoria": autoria,
            "temas": resumir_temas(proposicoes), "orgaos": ordenar_orgaos(orgaos.get(str(did), [])),
            "frentes": sorted(d["frentes"], key=lambda f: f["titulo"]) if d.get("frentes") is not None else None,
            **{k: d[k] for k in ("profissoes", "ocupacoes", "mandatosExternos", "historico", "discursos") if k in d},
            "votos": votos, "comportamento": comportamento, "presenca": presenca_do_deputado(did, presenca, medianas),
            "totalVotacoes": total_nominais, "eleicao": eleicoes_deps.get(did), "condicao": d.get("condicaoEleitoral"),
            "despesas": {
                "ano": d["despesas"]["ano"], "total": total_gasto,
                "porCategoria": categorias.agrupar(por_tipo),
                "porMes": sorted(([k, round(v, 2)] for k, v in por_mes.items())),
                "fornecedores": [[k, round(v, 2)] for k, v in fornecedores.most_common(10)],
                "recentes": itens[:30],
                "maiores": maiores_notas(itens),
                "mediaUF": {"uf": d["uf"], "media": round(sum(da_uf) / len(da_uf), 2), "deputados": len(da_uf)},
                "limite": limite_cota(d["uf"], itens),
            },
            "coletadoEm": d.get("coletadoEm"),
        })
        resumo_deps.append({
            "id": did, "nome": d["nome"], "partido": d["partido"], "uf": d["uf"],
            "foto": d.get("foto"), "proposicoes": len(d["proposicoes"]),
            "gasto": total_gasto, "votou": votou, "votacoes": total_nominais,
            "proprias": autoria["proprias"], "aprovadasProprias": autoria["aprovadasProprias"],
            "suprapartidarios": autoria["suprapartidarios"], "autoriaColetada": autoria["autoriaColetada"],
            "fidelidade": comportamento["partido"] if comportamento and comportamento["partido"]["total"] else None,
            "governismo": comportamento["governo"] if comportamento and comportamento["governo"]["total"] else None,
        })

    resumo_deps.sort(key=lambda x: x["nome"])
    salvar(SAIDA / "deputados.json", resumo_deps)
    votacoes_senado = gerar_senadores()
    total = gerar_proposicoes.gerar(SAIDA, deputados, detalhes, autorias, votacoes_projetos, nominais,
                                    ler(BRUTO / "senado.json", []) or [], ler(BRUTO / "senado_autorias.json", {}) or {},
                                    votacoes_senado, TIPOS_PROJETO, destino_projeto, nucleo["chaves"])
    print(f"Gerado: {total} proposições para a busca")
    forn = nucleo_fornecedores.construir(deputados, BRUTO, nucleo)
    cruzamento = doadores.construir(BRUTO, nucleo, forn)
    nucleo["ligacoes"]["doadores"] = cruzamento["ligacoes"]   # a tabela de ligações é uma só: o cruzamento entra antes de salvá-la
    identidades.salvar_nucleo(nucleo, SAIDA / "nucleo")
    candidaturas.salvar_candidaturas(candidaturas.construir(BRUTO, nucleo), SAIDA)
    mandatos.salvar_mandatos(mandatos.construir(deputados, BRUTO, nucleo), SAIDA)
    nucleo_fornecedores.salvar_fornecedores(forn, SAIDA)
    doadores.salvar_doadores(cruzamento, SAIDA)
    exibidos = {f["id"] for f in forn["ranking"]["fornecedores"]} | {c["fornecedor"] for c in cruzamento["cruzamentos"]}
    empresas.salvar_empresas(empresas.construir(BRUTO, exibidos, forn["datas"]), SAIDA)
    gerar_politicos.gerar(deputados, gerar_estaduais.gerar(), nucleo["chaves"])
    gerar_prefeituras.gerar()
    gerar_eleitorado()
    if (BRUTO / "executivo.json").exists():
        shutil.copy(BRUTO / "executivo.json", SAIDA / "executivo.json")
    shutil.copy(BRUTO / "municipios_ibge.json", SAIDA / "municipios_ibge.json")
    if (BRUTO / "historico").is_dir():   # histórico diário (scripts/historico.py): fica no git e a página historico.html lê daqui
        shutil.copytree(BRUTO / "historico", SAIDA / "historico")
    meta = ler(BRUTO / "meta.json", {}) or {}
    meta["ano"] = next(iter(deputados.values()))["despesas"]["ano"] if deputados else None
    meta["periodoVotacoes"] = [votacoes[-1]["data"], votacoes[0]["data"]] if votacoes else None
    salvar(SAIDA / "meta.json", meta)
    if categorias.DESCONHECIDAS:
        print(f"AVISO: {len(categorias.DESCONHECIDAS)} categorias de despesa sem regra em categorias.py (entraram em 'outros'): "
              + "; ".join(sorted(categorias.DESCONHECIDAS)[:20]))
    print(f"Gerado: {len(resumo_deps)} deputados, {len(lista_votacoes)} votações nominais -> {SAIDA}")


if __name__ == "__main__":
    main()
