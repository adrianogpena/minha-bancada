"""
Deputados estaduais do Rio Grande do Norte (ALRN). Grava em dados/estaduais/RN/ (contrato em estaduais_comum.py).

Fonte: API aberta, sem login, do portal Transparência Legislativa (a mesma que o site usa; o CPF que ela devolve não é gravado):
  https://api-transparencialegislativa.al.rn.leg.br/elegis-api-transp-legislativa/
  - parlamentar: deputados com nome civil e filiação;
  - processo?iniciativa=<id>: proposições de cada deputado (aqui só projetos e propostas, desde 2023);
  - reuniao e reuniao/presenca/<id>: presença nas sessões plenárias ordinárias e extraordinárias, desde 2023;
  - processo/ultimas-votacoes e processo/<id>/detalhamento-votacao/<reunião>: votos nominais nas sessões plenárias, desde 2023.

Não coletado: cotas parlamentares (https://transparencia.al.rn.leg.br/verbas; a API em api-transparencia.al.rn.leg.br só responde com um
token embutido no código do site, que não foi usado), votações de comissão (o contrato não tem campo de comissão e quem não é
membro apareceria como ausente), remuneração dos deputados, diárias e emendas (não encontradas).
"""

import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import estaduais_comum as comum

UF = "RN"
PASTA = comum.DADOS / UF
API = "https://api-transparencialegislativa.al.rn.leg.br/elegis-api-transp-legislativa"
SITE = "https://transparencialegislativa.al.rn.leg.br"
ANO_INICIAL = 2023
DESDE = f"{ANO_INICIAL}-01-01"
TIMEOUT = 60
TAMANHO = 200
EM_PARALELO = 2
RENOVAR_COMPLETA_DIAS = 14   # a leitura incremental só vê projetos novos: arquivamentos de projetos antigos entram na releitura completa
RENOVAR_FALHA_DIAS = 7   # sessão cuja presença deu erro só é consultada de novo depois disso
MINUSCULAS = {"de", "da", "do", "dos", "das", "e"}
VOTOS = {1: "Sim", 0: "Não", 2: "Abstenção"}
TIPO_PLENARIO = {1, 2, 12}


def sessao() -> requests.Session:
    """Como comum.sessao, mas sem repetir erro 500: a API devolve 500 sempre para as reuniões e votações antigas."""
    s = comum.sessao()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=(429, 502, 503, 504), allowed_methods=("GET",))
    adaptador = HTTPAdapter(max_retries=retry, pool_connections=comum.CONEXOES_POR_HOST, pool_maxsize=comum.CONEXOES_POR_HOST, pool_block=True)
    s.mount("https://", adaptador)
    return s


def titulo(nome: str) -> str:
    palavras = []
    for p in (nome or "").split():
        b = p.lower()
        palavras.append(b if b in MINUSCULAS else p.upper() if b == "pt" else b.capitalize())
    return " ".join(palavras)


def pegar(s, caminho: str, **params):
    r = s.get(f"{API}/{caminho}", params=params or None, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def paginas(s, caminho: str, **params):
    """Itens de `dados` de todas as páginas (pagina começa em 0), na ordem da API."""
    pagina = 0
    while True:
        d = pegar(s, caminho, pagina=pagina, tamanhoPagina=TAMANHO, **params)
        yield from d.get("dados", [])
        if len(d.get("dados", [])) < TAMANHO:
            return
        pagina += 1


def partido_atual(p: dict) -> str | None:
    atuais = [f for f in p.get("filiacoes") or [] if not (f.get("vigencia") or {}).get("fim")]
    atuais.sort(key=lambda f: (f.get("vigencia") or {}).get("inicio") or "")
    return (atuais[-1]["partido"].get("nome") or atuais[-1]["partido"].get("sigla")) if atuais else None


def deputado(p: dict) -> dict:
    pid = p["id"]
    return {"id": str(pid), "nome": titulo(comum.nome_limpo(p["nomeParlamentar"])), "nomeCivil": titulo((p.get("pessoa") or {}).get("nome")),
            "foto": f"{API}/parlamentar/fotografia/{pid}", "email": None, "titular": True, "partido": partido_atual(p),
            "iniciativas": [i["id"] for i in p.get("iniciativas") or [] if i.get("tipo") == "PARLAMENTAR"],
            "fonte": f"{SITE}/parlamentar/{pid}"}


def coletar_deputados(s) -> list[dict]:
    brutos = pegar(s, "parlamentar")["dados"]
    deputados = [deputado(p) for p in brutos]
    publicos = [{k: v for k, v in d.items() if k != "iniciativas"} for d in deputados]
    comum.salvar(PASTA / "deputados.json", {"fonte": f"{SITE}/parlamentares", "host": None, "legislatura": "63ª (2023-2027)", "deputados": publicos})
    print(f"RN: {len(deputados)} deputados")
    return deputados


# ---------------------------------------------------------------- projetos

def eh_projeto(p: dict) -> bool:
    d = comum.sem_acento(((p.get("propositura") or {}).get("tipo") or {}).get("descricao") or "")
    return d.startswith(("projeto", "proposta"))


def materia(p: dict, ids: list[str]) -> tuple[str, dict]:
    prop = p["propositura"]
    tipo = prop["tipo"]
    return f"{tipo['sigla']}-{prop['numero']}-{prop['ano']}", {
        "tipo": tipo["sigla"], "tipoDescricao": titulo(tipo["descricao"]), "numero": prop["numero"], "ano": prop["ano"],
        "dataApresentacao": (p.get("dataEntrada") or "")[:10] or None, "ementa": " ".join((p.get("ementa") or "").split()),
        "situacao": "Arquivado" if p.get("dataArquivamento") else None, "emTramitacao": not p.get("dataArquivamento"), "linkTexto": None,
        "idsAutores": ids, "idsDeputados": ids, "fonte": f"{SITE}/projeto/{p['id']}"}


def projetos_do_deputado(s, d: dict, desde: str = DESDE) -> list[dict]:
    achados = []
    for ini in d["iniciativas"]:
        for p in paginas(s, "processo", iniciativa=ini):
            if (p.get("dataEntrada") or "") < desde:
                break
            if eh_projeto(p):
                achados.append(p)
    return achados


def montar_materias(por_deputado: dict[str, list[dict]]) -> dict[int, dict]:
    ids_por_chave: dict[str, set] = {}
    brutos: dict[str, dict] = {}
    for pid, lista in por_deputado.items():
        for p in lista:
            chave, _ = materia(p, [])
            ids_por_chave.setdefault(chave, set()).add(pid)
            brutos[chave] = p
    por_ano: dict[int, dict] = {}
    for chave, p in sorted(brutos.items()):
        _, m = materia(p, sorted(ids_por_chave[chave]))
        por_ano.setdefault(m["ano"], {})[chave] = m
    return por_ano


def desde_incremental(hoje: date) -> tuple[str, dict[int, dict]] | None:
    """(data a partir da qual ler, arquivos atuais) se a última coleta completa é recente e há arquivo de todos os anos; senão None."""
    atuais = {ano: comum.ler(PASTA / f"materias_{ano}.json") for ano in range(ANO_INICIAL, hoje.year + 1)}
    ultimo = atuais[hoje.year] or {}
    if all(atuais.values()) and ultimo.get("completaEm") and ultimo.get("coletadoEm") \
            and (hoje - date.fromisoformat(ultimo["completaEm"])).days < RENOVAR_COMPLETA_DIAS:
        return (date.fromisoformat(ultimo["coletadoEm"]) - timedelta(days=1)).isoformat(), atuais
    return None


def juntar_novos(atuais: dict[int, dict], novos: dict[int, dict]) -> dict[int, dict]:
    """Matérias de cada ano: as já guardadas mais as lidas agora (autores somados, versão nova no resto)."""
    por_ano = {ano: dict(a["materias"]) for ano, a in atuais.items()}
    for ano, materias in novos.items():
        for chave, m in materias.items():
            antiga = por_ano.get(ano, {}).get(chave)
            if antiga:
                ids = sorted(set(antiga["idsDeputados"]) | set(m["idsDeputados"]))
                m = {**m, "idsAutores": ids, "idsDeputados": ids}
            por_ano.setdefault(ano, {})[chave] = m
    return por_ano


def coletar_projetos(s, deputados: list[dict]) -> None:
    hoje = date.today()
    incremental = desde_incremental(hoje)
    desde = incremental[0] if incremental else DESDE

    def um(d):
        try:
            return d["id"], projetos_do_deputado(s, d, desde)
        except Exception as e:
            comum.avisar(f"RN: projetos de {d['nome']}: {e}")
            return d["id"], []

    with ThreadPoolExecutor(EM_PARALELO) as ex:
        por_deputado = dict(ex.map(um, deputados))
    por_ano = montar_materias(por_deputado)
    completa_em = hoje.isoformat()
    if incremental:
        por_ano = juntar_novos(incremental[1], por_ano)
        completa_em = incremental[1][hoje.year]["completaEm"]
    for ano, materias in por_ano.items():
        comum.salvar(PASTA / f"materias_{ano}.json", {"coletadoEm": hoje.isoformat(), "completaEm": completa_em, "fonte": f"{SITE}/projetos", "materias": materias})
    print(f"RN: {sum(len(m) for m in por_ano.values())} projetos em {len(por_ano)} anos" + (f" (lidos desde {desde})" if incremental else ""))


# ---------------------------------------------------------------- reuniões, presença e votações

def sessoes_plenarias(s) -> list[dict]:
    """Reuniões realizadas de tipo plenário desde ANO_INICIAL (a API devolve da mais nova para a mais antiga)."""
    achadas = []
    for r in paginas(s, "reuniao", situacao="R", tipoOrdenacao="DESC"):
        if (r.get("dataInicio") or "") < DESDE:
            break
        if (r.get("tipoReuniao") or {}).get("id") in TIPO_PLENARIO:
            achadas.append(r)
    return achadas


def situacao_presenca(evento) -> str:
    chave = (evento or {}).get("chave")
    if chave == "presenca":
        return "presente"
    if chave and chave.startswith("ausencia-justificada"):
        return "licenca"
    return "ausente"


def somar_presenca(sessoes: list[tuple[str, list[dict]]]) -> dict:
    """{(idDeputado, ano): {presente, ausente, licenca, totalSessoes}} a partir de [(data, registros de reuniao/presenca)]."""
    soma: dict[tuple, dict] = {}
    for data, registros in sessoes:
        ano = data[:4]
        for r in registros:
            c = soma.setdefault((str(r["id"]), ano), {"presente": 0, "ausente": 0, "licenca": 0, "totalSessoes": 0})
            c[situacao_presenca(r.get("evento"))] += 1
            c["totalSessoes"] += 1
    return soma


def coletar_presenca(s, deputados: list[dict], sessoes: list[dict]) -> None:
    ids = {d["id"] for d in deputados}
    arq = PASTA / "presenca_sessoes.json"
    cache = comum.ler(arq, {"sessoes": {}, "falhas": {}})
    guardadas, falhas_antigas = cache["sessoes"], cache["falhas"]
    hoje = date.today()
    recentes = (hoje - timedelta(days=RENOVAR_FALHA_DIAS)).isoformat()
    # sessão antiga já lida não muda (as dos últimos dias são lidas de novo); com erro, só é tentada de novo depois de RENOVAR_FALHA_DIAS
    pendentes = [r for r in sessoes if (str(r["id"]) not in guardadas or (r["dataInicio"] or "") >= recentes)
                 and (hoje - date.fromisoformat(falhas_antigas.get(str(r["id"]), "2000-01-01"))).days >= RENOVAR_FALHA_DIAS]
    falhas: list[int] = []

    def uma(r):
        try:
            registros = pegar(s, f"reuniao/presenca/{r['id']}")["dados"]
        except comum.PrazoEsgotado:
            raise
        except Exception:
            falhas.append(r["id"])
            return None
        return str(r["id"]), {"data": r["dataInicio"], "registros": [{"id": x["id"], "evento": {"chave": (x.get("evento") or {}).get("chave")}} for x in registros]}

    try:
        with ThreadPoolExecutor(EM_PARALELO) as ex:
            for x in ex.map(uma, pendentes):
                if x:
                    guardadas[x[0]] = x[1]
    finally:  # prazo esgotado no meio: o que já foi lido fica guardado para a próxima
        falhas_atuais = {i: d for i, d in falhas_antigas.items() if i not in guardadas}
        falhas_atuais.update({str(i): hoje.isoformat() for i in falhas})
        comum.salvar(arq, {"sessoes": guardadas, "falhas": falhas_atuais})
    lidas = [(guardadas[str(r["id"])]["data"], guardadas[str(r["id"])]["registros"]) for r in sessoes if str(r["id"]) in guardadas]
    soma = somar_presenca(lidas)
    itens = [{"idDeputado": pid, "periodo": ano, **c, "fonte": f"{SITE}/parlamentar/{pid}"} for (pid, ano), c in sorted(soma.items()) if pid in ids]
    comum.salvar(PASTA / "presenca.json", {"coletadoEm": date.today().isoformat(), "fonte": f"{SITE}/eventos-legislativos", "itens": itens})
    print(f"RN: presença {len(itens)} registros em {len(lidas)} de {len(sessoes)} sessões plenárias ({len(pendentes)} lidas agora)")
    sem_presenca = [int(i) for i in falhas_atuais if int(i) in {r["id"] for r in sessoes}]
    if sem_presenca:
        comum.avisar(f"RN: a API respondeu erro em {len(sem_presenca)} sessões plenárias (ids {min(sem_presenca)} a {max(sem_presenca)}), fora da presença")


def votacao(processo: dict, detalhe: dict, ids: set) -> tuple[dict, dict] | None:
    """(votação, matéria votada) de um processo, ou None se não houver votos nominais."""
    votos = []
    for v in (detalhe.get("votacao") or {}).get("dados") or []:
        rotulo = VOTOS.get(v.get("voto"))
        pid = str((v.get("parlamentar") or {}).get("id"))
        if rotulo and pid in ids:
            votos.append([pid, rotulo])
    if not votos:
        return None
    res = detalhe["votacao"].get("resumo") or {}
    abertura = processo["resultadoVotacao"]["dataSituacaoAbertura"]
    resultado = processo["resultadoVotacao"].get("resultadoVotacao")
    prop = processo["propositura"]
    return ({"data": abertura[:10], "idMateria": f"{prop['tipo']['sigla']}-{prop['numero']}-{prop['ano']}", "aprovada": resultado == "A",
             "resultado": {"A": "Aprovado", "R": "Rejeitado"}.get(resultado), "sim": res.get("sim"), "nao": res.get("nao"),
             "abstencoes": res.get("abstencao"), "votos": votos,
             "fonte": f"{SITE}/evento-legislativo/{processo['resultadoVotacao']['reuniao']['id']}"},
            {"tipo": prop["tipo"]["sigla"], "tipoDescricao": titulo(prop["tipo"]["descricao"]), "numero": prop["numero"], "ano": prop["ano"],
             "ementa": " ".join((processo.get("ementa") or "").split())})


def coletar_votacoes(s, deputados: list[dict], sessoes: list[dict]) -> None:
    ids = {d["id"] for d in deputados}
    plenarias = {r["id"] for r in sessoes}
    candidatas = []
    for p in paginas(s, "processo/ultimas-votacoes"):
        rv = p.get("resultadoVotacao") or {}
        if p.get("tipoVotacao") == "A" and (rv.get("dataSituacaoAbertura") or "") >= DESDE and (rv.get("reuniao") or {}).get("id") in plenarias:
            candidatas.append(p)
    existente = comum.ler(PASTA / "votacoes.json", {"votacoes": {}})["votacoes"]
    materias = comum.ler(PASTA / "materias_votadas.json", {})
    sem_detalhe: list[str] = []

    def uma(p):
        vid = f"{p['id']}-{p['resultadoVotacao']['reuniao']['id']}"
        if vid in existente:
            return vid, None
        try:
            return vid, votacao(p, pegar(s, f"processo/{p['id']}/detalhamento-votacao/{p['resultadoVotacao']['reuniao']['id']}"), ids)
        except Exception:
            sem_detalhe.append(vid)
            return vid, None

    with ThreadPoolExecutor(EM_PARALELO) as ex:
        resultados = list(ex.map(uma, candidatas))
    for vid, r in resultados:
        if r:
            existente[vid], materias[r[0]["idMateria"]] = r[0], r[1]
    comum.salvar(PASTA / "votacoes.json", {"fonte": f"{SITE}/ultimas-votacoes", "votacoes": existente})
    comum.salvar(PASTA / "materias_votadas.json", materias)
    print(f"RN: {len(existente)} votações nominais de plenário ({len(candidatas)} votações abertas em sessões plenárias)")
    if sem_detalhe:
        comum.avisar(f"RN: a API respondeu erro no detalhe de {len(sem_detalhe)} votações de plenário")


def coletar() -> None:
    s = sessao()
    deputados = coletar_deputados(s)
    sessoes = []
    try:
        sessoes = sessoes_plenarias(s)
    except Exception as e:
        comum.avisar(f"RN: lista de reuniões: {e}")
    etapas = [("projetos", lambda: coletar_projetos(s, deputados)), ("presença", lambda: coletar_presenca(s, deputados, sessoes)),
              ("votações", lambda: coletar_votacoes(s, deputados, sessoes))]
    for nome, etapa in etapas:
        try:
            etapa()
        except Exception as e:
            comum.avisar(f"RN: {nome}: {e}")


# ---------------------------------------------------------------- contratos

def _sem_cpf(o):
    if isinstance(o, dict):
        return {k: _sem_cpf(v) for k, v in o.items() if k != "cpf"}
    if isinstance(o, list):
        return [_sem_cpf(i) for i in o]
    return o


def _contrato_deputados(ctx):
    return {"parlamentar": _sem_cpf(pegar(sessao(), "parlamentar")["dados"][:3])}


def _conferir_deputados(registro):
    falhas = []
    if not registro["parlamentar"]:
        return ["parlamentar sem deputados"], []
    for p in registro["parlamentar"]:
        d = deputado(p)
        for campo in ("id", "nome", "nomeCivil", "partido"):
            if not d[campo]:
                falhas.append(f"deputado sem {campo}")
        if not d["iniciativas"]:
            falhas.append("deputado sem iniciativa PARLAMENTAR")
    return falhas, []


def _contrato_projetos(ctx):
    s = sessao()
    ini = deputado(pegar(s, "parlamentar")["dados"][0])["iniciativas"][0]
    return {"processos": pegar(s, "processo", pagina=0, tamanhoPagina=40, iniciativa=ini)["dados"][:40]}


def _conferir_projetos(registro):
    projetos = [p for p in registro["processos"] if eh_projeto(p)]
    if not projetos:
        return ["processo sem nenhum projeto na amostra"], []
    falhas = []
    for p in projetos:
        _, m = materia(p, ["1"])
        for campo in ("tipo", "numero", "ano", "ementa", "dataApresentacao"):
            if not m[campo]:
                falhas.append(f"projeto sem {campo}")
    return falhas, []


def _contrato_presenca(ctx):
    s = sessao()
    d = pegar(s, "reuniao", pagina=0, tamanhoPagina=30, situacao="R", tipoOrdenacao="DESC")["dados"]
    plenaria = next(r for r in d if (r.get("tipoReuniao") or {}).get("id") in TIPO_PLENARIO)
    return {"reunioes": d[:30], "presenca": pegar(s, f"reuniao/presenca/{plenaria['id']}")["dados"], "reuniao": plenaria["id"]}


def _conferir_presenca(registro):
    falhas = []
    if not any((r.get("tipoReuniao") or {}).get("id") in TIPO_PLENARIO for r in registro["reunioes"]):
        falhas.append("lista de reuniões sem sessão plenária")
    soma = somar_presenca([("2026-01-01", registro["presenca"])])
    if not soma:
        falhas.append("presença sem deputados")
    if not any(c["presente"] for c in soma.values()):
        falhas.append("nenhum presente na sessão de amostra")
    return falhas, []


def _contrato_votacao(ctx):
    s = sessao()
    lista = pegar(s, "processo/ultimas-votacoes", pagina=0, tamanhoPagina=40)["dados"]
    for p in lista:
        rv = p.get("resultadoVotacao")
        if p.get("tipoVotacao") != "A" or not rv:
            continue
        d = pegar(s, f"processo/{p['id']}/detalhamento-votacao/{rv['reuniao']['id']}")
        if (d.get("votacao") or {}).get("dados"):
            d["presenca"] = {"dados": [], "total": 0}
            d["reuniao"] = {"id": d["reuniao"]["id"], "dataInicio": d["reuniao"]["dataInicio"], "tipoReuniao": d["reuniao"]["tipoReuniao"]}
            return {"processo": p, "detalhe": _sem_cpf(d)}
    raise RuntimeError("nenhuma votação nominal entre as últimas 40")


def _conferir_votacao(registro):
    ids = {str(v["parlamentar"]["id"]) for v in registro["detalhe"]["votacao"]["dados"]}
    r = votacao(registro["processo"], registro["detalhe"], ids)
    if not r:
        return ["votação de amostra sem votos reconhecidos"], []
    falhas = []
    v, m = r
    for campo in ("data", "idMateria", "resultado", "sim"):
        if v[campo] is None:
            falhas.append(f"votação sem {campo}")
    if not m["ementa"]:
        falhas.append("matéria votada sem ementa")
    return falhas, []


CONTRATOS = [
    dict(nome="estadual_rn_deputados", fonte=f"{API}/parlamentar", buscar=_contrato_deputados, html=_conferir_deputados),
    dict(nome="estadual_rn_projetos", fonte=f"{API}/processo", buscar=_contrato_projetos, html=_conferir_projetos),
    dict(nome="estadual_rn_presenca", fonte=f"{API}/reuniao", buscar=_contrato_presenca, html=_conferir_presenca),
    dict(nome="estadual_rn_votacao", fonte=f"{API}/processo/ultimas-votacoes", buscar=_contrato_votacao, html=_conferir_votacao),
]


if __name__ == "__main__":
    coletar()
    sys.exit(0)
