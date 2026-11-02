"""
Deputados estaduais do Rio Grande do Norte (ALRN). Grava em dados/estaduais/RN/ (contrato em estaduais_comum.py).

Fonte: API aberta, sem login, do portal Transparência Legislativa (a mesma que o site usa; o CPF que ela devolve não é gravado):
  https://api-transparencialegislativa.al.rn.leg.br/elegis-api-transp-legislativa/
  - parlamentar: deputados com nome civil e filiação;
  - processo?iniciativa=<id>: proposições de cada deputado (aqui só projetos e propostas, desde 2023);
  - reuniao e reuniao/presenca/<id>: presença nas sessões plenárias ordinárias e extraordinárias, desde 2023;
  - processo/ultimas-votacoes e processo/<id>/detalhamento-votacao/<reunião>: votos nominais nas sessões plenárias, desde 2023;
  - pautas: processo?reuniao=<id>&faseReuniao=1 (ordem do dia) e 2 (expediente) de cada sessão plenária, ligadas ao deputado pelo id de
    `iniciativa.parlamentar` (pautas_<ano>.json, tipo "ordem-do-dia");
  - atas: legis-videos/reuniao/<id> devolve o vídeo da sessão e, quando a Mesa publicou, o texto da ata (`ata`); o coletor guarda só o link
    https://api-legisvideos.al.rn.leg.br/video/ata/<hash> (a página da ata, 200 sem cabeçalho de tipo), em pautas_<ano>.json com tipo "atas".
    Cobertura parcial: em 188 vídeos recentes 101 tinham ata;
  - normas: processo?tipoPropositura=<1 PL, 2 PLC, 6 PDL, 8 resolução, 22 título honorífico> de iniciativa de deputado, confirmadas pela
    tramitação (processo/<id>/tramitacao com situação 27 Lei Sancionada, 26 Lei Promulgada, 127 Decreto Legislativo Promulgado ou 128
    Resolução promulgada); normas_<ano>.json. O número oficial da lei não vem no cadastro (`numeroExterno` não é o da lei): a norma leva o
    número do projeto de origem, a data da tramitação e o link do Diário Oficial (`linkDOE`) quando existe;
  - contratos e atas de registro de preços do órgão: PNCP (https://pncp.gov.br/api/consulta/v1, aberta), CNPJ da Assembleia 08.493.371/0001-64,
    janela máxima de 365 dias lida ano a ano (orgao_<ano>.json). A ata do PNCP não traz fornecedor nem valor.

Não coletado: cotas parlamentares (https://transparencia.al.rn.leg.br/verbas; a API em api-transparencia.al.rn.leg.br só responde com um
token embutido no código do site, que não foi usado; o mesmo vale para gabinete, remuneração e regras do ressarcimento), votações de comissão (o contrato não tem campo de comissão e quem não é
membro apareceria como ausente), remuneração dos deputados, diárias e emendas (não encontradas).
"""

import re
import time
import zlib
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from functools import partial
from zoneinfo import ZoneInfo

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
FUSO = ZoneInfo("America/Fortaleza")
PNCP = "https://pncp.gov.br/api/consulta/v1"
PNCP_SITE = "https://pncp.gov.br/app"
CNPJ_ORGAO = "08493371000164"
FONTE_ID = "alrn_pncp"
PNCP_TAMANHO = 500
PAUSA_PNCP = 2   # segundos entre requisições: o PNCP responde 429 depois de poucas seguidas
ESPERA_429 = 20
TENTATIVAS_PNCP = 4
ATAS_SITE = "https://api-legisvideos.al.rn.leg.br"
RELER_PAUTAS_DIAS = 7   # pauta e ata de sessão mais nova que isso é lida de novo todo dia (a Mesa publica depois)
TIPOS_NORMA = (1, 2, 6, 8, 22)
SITUACOES_NORMA = {27: "sancionado", 26: "promulgado", 127: "promulgado", 128: "promulgado"}
RELER_NORMA_DIAS = 7   # projeto de deputado ainda sem norma é relido a cada 7 a 13 dias (escalonado por id)
LIMITE_EMENTA = 300


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
    return comum.sigla_partido(atuais[-1]["partido"].get("nome") or atuais[-1]["partido"].get("sigla")) if atuais else None


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
        "dataApresentacao": comum.data_iso(p.get("dataEntrada")), "ementa": " ".join((p.get("ementa") or "").split()),
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
        for chave, nova in materias.items():
            antiga = por_ano.get(ano, {}).get(chave)
            juntada = nova
            if antiga:
                ids = sorted(set(antiga["idsDeputados"]) | set(nova["idsDeputados"]))
                juntada = {**nova, "idsAutores": ids, "idsDeputados": ids}
            por_ano.setdefault(ano, {})[chave] = juntada
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
    return ({"data": comum.data_iso(abertura), "idMateria": f"{prop['tipo']['sigla']}-{prop['numero']}-{prop['ano']}", "aprovada": resultado == "A",
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


# ---------------------------------------------------------------- contratos e atas de registro de preços do órgão (PNCP)

def sessao_pncp() -> requests.Session:
    """Sessão que não repete 429 por conta própria: `pncp_pagina` espera mais tempo entre as tentativas."""
    s = comum.sessao()
    retry = Retry(total=2, backoff_factor=1, status_forcelist=(502, 503, 504), allowed_methods=("GET",))
    s.mount("https://", HTTPAdapter(max_retries=retry, pool_connections=comum.CONEXOES_POR_HOST, pool_maxsize=comum.CONEXOES_POR_HOST, pool_block=True))
    return s


def pncp_pagina(s, recurso: str, **params) -> dict:
    """Uma página de /contratos ou /atas. 204 (sem registro na janela) vale como lista vazia; 429 espera e tenta de novo."""
    for tentativa in range(TENTATIVAS_PNCP):
        r = s.get(f"{PNCP}/{recurso}", params=params, timeout=TIMEOUT)
        if r.status_code == 204:
            return {"data": [], "totalPaginas": 0}
        if r.status_code == 429:
            time.sleep(ESPERA_429 * (tentativa + 1))
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"PNCP {recurso}: limite de requisições excedido (HTTP 429)")


def registros_pncp(s, recurso: str, ano: int) -> list[dict]:
    """Registros publicados no PNCP na janela do ano (máximo de 365 dias por consulta)."""
    filtro = {"cnpjOrgao": CNPJ_ORGAO} if recurso == "contratos" else {"cnpj": CNPJ_ORGAO}
    pagina, tudo = 1, []
    while True:
        d = pncp_pagina(s, recurso, dataInicial=f"{ano}0101", dataFinal=f"{ano}1231", pagina=pagina, tamanhoPagina=PNCP_TAMANHO, **filtro)
        tudo += d.get("data") or []
        if pagina >= (d.get("totalPaginas") or 0):
            return tudo
        pagina += 1
        time.sleep(PAUSA_PNCP)


def link_contrato(r: dict) -> str | None:
    """Página do contrato no PNCP, a partir do número de controle "<cnpj>-2-<sequencial>/<ano>"."""
    m = re.fullmatch(r"(\d{14})-\d-(\d+)/(\d{4})", r.get("numeroControlePNCP") or "")
    return f"{PNCP_SITE}/contratos/{m[1]}/{m[3]}/{int(m[2])}" if m else None


def link_ata(r: dict) -> str | None:
    """Página da ata no PNCP, a partir do número de controle "<cnpj>-1-<sequencial da compra>/<ano>-<sequencial da ata>"."""
    m = re.fullmatch(r"(\d{14})-\d-(\d+)/(\d{4})-(\d+)", r.get("numeroControlePNCPAta") or "")
    return f"{PNCP_SITE}/atas/{m[1]}/{m[3]}/{int(m[2])}/{int(m[4])}" if m else None


def itens_do_orgao(contratos: list[dict], atas: list[dict]) -> dict:
    """{id: item} no formato de `comum.item_orgao`. Id de (fonte, tipo, número de controle do PNCP). A ata do PNCP não traz fornecedor
    nem valor; o CPF de contratado pessoa física não é gravado (só o nome que o PNCP publica)."""
    itens = {}
    for r in sorted(contratos, key=lambda x: x.get("numeroControlePNCP") or ""):
        if not r.get("numeroControlePNCP"):
            continue
        link = link_contrato(r)
        numero = f"{r['numeroContratoEmpenho']}/{r['anoContrato']}" if r.get("numeroContratoEmpenho") and r.get("anoContrato") else None
        arquivos = [{"url": link, "nome": "Contrato no PNCP", "data": comum.data_iso(r.get("dataPublicacaoPncp"))}] if link else ()
        iid, item = comum.item_orgao(FONTE_ID, "contrato", r["numeroControlePNCP"], fornecedor_nome=r.get("nomeRazaoSocialFornecedor"),
                                     documento=r.get("niFornecedor"), valor=r.get("valorGlobal"), inicio=comum.data_iso(r.get("dataVigenciaInicio")),
                                     fim=comum.data_iso(r.get("dataVigenciaFim")), objeto=r.get("objetoContrato"), numero=numero, arquivos=arquivos,
                                     fonte=link or PNCP_SITE, tipoContrato=comum.compactar((r.get("tipoContrato") or {}).get("nome")),
                                     categoria=comum.compactar((r.get("categoriaProcesso") or {}).get("nome")), processo=comum.compactar(r.get("processo")),
                                     assinatura=comum.data_iso(r.get("dataAssinatura")))
        itens[iid] = item
    for r in sorted(atas, key=lambda x: x.get("numeroControlePNCPAta") or ""):
        if not r.get("numeroControlePNCPAta"):
            continue
        link = link_ata(r)
        arquivos = [{"url": link, "nome": "Ata de registro de preços no PNCP", "data": comum.data_iso(r.get("dataPublicacaoPncp"))}] if link else ()
        iid, item = comum.item_orgao(FONTE_ID, "ata_registro", r["numeroControlePNCPAta"], fornecedor_nome=None, valor=None,
                                     inicio=comum.data_iso(r.get("vigenciaInicio")), fim=comum.data_iso(r.get("vigenciaFim")), objeto=r.get("objetoContratacao"),
                                     numero=comum.compactar(r.get("numeroAtaRegistroPreco")), arquivos=arquivos, fonte=link or PNCP_SITE,
                                     situacao="Cancelada" if r.get("cancelado") else None, assinatura=comum.data_iso(r.get("dataAssinatura")))
        itens[iid] = item
    return itens


def orgao_do_ano(s, pasta, ano: int, hoje: date) -> None:
    arq = pasta / f"orgao_{ano}.json"
    if comum.ano_encerrado(ano, hoje, arq):
        return
    contratos = registros_pncp(s, "contratos", ano)
    time.sleep(PAUSA_PNCP)
    atas = registros_pncp(s, "atas", ano)
    itens = itens_do_orgao(contratos, atas)
    if not itens and comum.ler(arq, {}).get("itens"):
        raise RuntimeError(f"PNCP devolveu lista vazia para {ano}; mantém o arquivo anterior")
    comum.salvar(arq, {"coletadoEm": hoje.isoformat(), "fonte": f"{PNCP_SITE}/contratos", "itens": itens})
    n_atas = sum(i["tipo"] == "ata_registro" for i in itens.values())
    print(f"RN: {ano} contratos {len(itens) - n_atas} e atas de registro {n_atas} do órgão (PNCP)")


def coletar_orgao(s, pasta, hoje: date) -> None:
    for ano in range(ANO_INICIAL, hoje.year + 1):
        comum.tentar(UF, f"contratos e atas de registro {ano}", partial(orgao_do_ano, s, pasta, ano, hoje))
        time.sleep(PAUSA_PNCP)


# ---------------------------------------------------------------- pautas e atas das sessões plenárias

def dia_local(texto) -> str | None:
    """'2026-10-29T02:30:00.000Z' (UTC) -> '2026-10-28' no horário do Rio Grande do Norte."""
    if not texto:
        return None
    try:
        return datetime.fromisoformat(str(texto).replace("Z", "+00:00")).astimezone(FUSO).date().isoformat()
    except ValueError:
        return comum.data_iso(texto)


def curta(texto, limite: int = LIMITE_EMENTA) -> str:
    t = " ".join((texto or "").split())
    return t if len(t) <= limite else t[:limite].rsplit(" ", 1)[0] + "..."


def processos_da_pauta(por_fase: dict[int, list[dict]], ids: set) -> list[dict]:
    """Processos de uma sessão (fase 1 ordem do dia, 2 expediente), ligados ao deputado pelo id de `iniciativa.parlamentar`."""
    achados = []
    for fase, lista in sorted(por_fase.items()):
        for p in lista:
            prop = p.get("propositura") or {}
            pid = str(((p.get("iniciativa") or {}).get("parlamentar") or {}).get("id") or "")
            achados.append({"id": p["id"], "tipo": (prop.get("tipo") or {}).get("sigla"), "numero": prop.get("numero"), "ano": prop.get("ano"),
                            "fase": fase, "ementa": curta(p.get("ementa")), "idDeputado": pid if pid in ids else None})
    return achados


def item_pauta(r: dict, processos: list[dict]) -> dict | None:
    if not processos:
        return None
    tipo = (r.get("tipoReuniao") or {}).get("nome")
    titulo_sessao = comum.compactar(f"{tipo or 'Sessão'} {r.get('numero') or ''}")
    link = f"{SITE}/evento-legislativo/{r['id']}"
    return {"id": str(r["id"]), "reuniao": r["id"], "tipo": "ordem-do-dia", "titulo": titulo_sessao, "data": dia_local(r.get("dataInicio")),
            "arquivos": [{"nome": titulo_sessao, "url": link}], "processos": processos,
            "idsDeputados": sorted({p["idDeputado"] for p in processos if p["idDeputado"]}), "fonte": link}


def itens_ata(r: dict, videos: list[dict]) -> list[dict]:
    """Uma ata por vídeo da sessão que tem o texto da ata publicado (`ata`); só o link é guardado."""
    achados = []
    for v in videos:
        if v.get("ata") and v.get("hash"):
            nome = comum.compactar(v.get("titulo")) or "Ata da sessão"
            achados.append({"id": str(v["id"]), "reuniao": r["id"], "tipo": "atas", "titulo": nome, "data": dia_local(r.get("dataInicio")),
                            "arquivos": [{"nome": nome, "url": f"{ATAS_SITE}/video/ata/{v['hash']}"}], "fonte": f"{SITE}/evento-legislativo/{r['id']}"})
    return achados


def ler_reuniao(s, r: dict, ids: set) -> list[dict]:
    por_fase = {fase: pegar(s, "processo", reuniao=r["id"], faseReuniao=fase).get("dados") or [] for fase in (1, 2)}
    videos = pegar(s, f"legis-videos/reuniao/{r['id']}").get("dados") or []
    return [i for i in [item_pauta(r, processos_da_pauta(por_fase, ids)), *itens_ata(r, videos)] if i]


def coletar_pautas_atas(s, deputados: list[dict], sessoes: list[dict]) -> None:
    ids = {d["id"] for d in deputados}
    hoje = date.today()
    agora = hoje.isoformat()
    estado = {a: comum.ler(PASTA / f"pautas_{a}.json", {}) for a in range(ANO_INICIAL, hoje.year + 1)}
    for e in estado.values():
        e.setdefault("itens", {})
        e.setdefault("lidas", {})
        e.setdefault("falhas", {})
    recentes = (hoje - timedelta(days=RELER_PAUTAS_DIAS)).isoformat()
    recentes_falha = hoje - timedelta(days=RENOVAR_FALHA_DIAS)

    def ano_de(r):
        return int(r["dataInicio"][:4])

    pendentes = [r for r in sessoes if ano_de(r) in estado and (str(r["id"]) not in estado[ano_de(r)]["lidas"] or (r["dataInicio"] or "") >= recentes)
                 and date.fromisoformat(estado[ano_de(r)]["falhas"].get(str(r["id"]), "2000-01-01")) <= recentes_falha]

    def uma(r):
        try:
            return r, ler_reuniao(s, r, ids)
        except comum.PrazoEsgotado:
            raise
        except Exception:
            return r, None

    try:
        with ThreadPoolExecutor(EM_PARALELO) as ex:
            for r, itens in ex.map(uma, pendentes):
                e, rid = estado[ano_de(r)], str(r["id"])
                if itens is None:
                    e["falhas"][rid] = agora
                    continue
                e["itens"] = {k: v for k, v in e["itens"].items() if v.get("reuniao") != r["id"]}
                for i in itens:
                    e["itens"][f"{i['tipo']}|{i['id']}"] = i
                e["lidas"][rid] = agora
                e["falhas"].pop(rid, None)
    finally:
        for a, e in estado.items():
            comum.salvar(PASTA / f"pautas_{a}.json", {"coletadoEm": agora, "fonte": f"{SITE}/eventos-legislativos", "itens": e["itens"],
                                                      "lidas": e["lidas"], "falhas": e["falhas"]})
    todas = [i for e in estado.values() for i in e["itens"].values()]
    print(f"RN: pautas {sum(i['tipo'] == 'ordem-do-dia' for i in todas)} e atas {sum(i['tipo'] == 'atas' for i in todas)} em {len(sessoes)} sessões plenárias "
          f"({len(pendentes)} lidas agora)")
    falhas = sum(len(e["falhas"]) for e in estado.values())
    if falhas:
        comum.avisar(f"RN: pauta ou ata de {falhas} sessões plenárias respondeu erro; tentadas de novo em {RENOVAR_FALHA_DIAS} dias")


# ---------------------------------------------------------------- normas legais (projetos de deputado que viraram lei, decreto legislativo ou resolução)

def eh_de_deputado(p: dict, ids: set) -> bool:
    ini = p.get("iniciativa") or {}
    return ini.get("tipo") == "PARLAMENTAR" and str((ini.get("parlamentar") or {}).get("id")) in ids


def situacao_da_norma(tramitacao: list[dict]) -> dict | None:
    """Andamento que fez do projeto uma norma (27 Lei Sancionada, 26 Lei Promulgada, 127 Decreto Legislativo, 128 Resolução): o que tem
    link do Diário Oficial e, entre iguais, o mais antigo."""
    achadas = []
    for t in tramitacao:
        sit = t.get("situacaoProcesso") or {}
        if sit.get("id") in SITUACOES_NORMA:
            achadas.append({"id": sit["id"], "nome": sit.get("nome"), "data": dia_local((t.get("origem") or {}).get("data")), "linkDOE": t.get("linkDOE")})
    return min(achadas, key=lambda a: (not a["linkDOE"], a["data"] or "9999", a["id"])) if achadas else None


def norma(p: dict, sit: dict) -> tuple[str, dict]:
    """(chave do projeto de origem, norma). Número e ano são os do projeto: o cadastro não traz o número oficial da norma."""
    prop = p["propositura"]
    tipo = prop["tipo"]
    return f"{tipo['sigla']}-{prop['numero']}-{prop['ano']}", {
        "tipo": f"{titulo(tipo['descricao'])} {SITUACOES_NORMA[sit['id']]}", "numero": prop["numero"], "ano": prop["ano"], "data": sit["data"],
        "ementa": curta(p.get("ementa")), "situacao": sit["nome"], "idsDeputados": [str(p["iniciativa"]["parlamentar"]["id"])],
        "fonte": sit["linkDOE"] or f"{SITE}/projeto/{p['id']}", "idProcesso": p["id"]}


def candidatos_a_norma(s, ids: set, desde: str, ate: str) -> dict[int, dict]:
    achados = {}
    for tipo in TIPOS_NORMA:
        for p in paginas(s, "processo", tipoPropositura=tipo, dataInicio=desde, dataFinal=ate):
            if eh_de_deputado(p, ids):
                achados[p["id"]] = p
    return achados


def devido(visto: str, pid, hoje: date) -> bool:
    return (hoje - date.fromisoformat(visto)).days >= RELER_NORMA_DIAS + zlib.crc32(str(pid).encode()) % RELER_NORMA_DIAS


def coletar_normas(s, deputados: list[dict]) -> None:
    ids = {d["id"] for d in deputados}
    hoje = date.today()
    agora = hoje.isoformat()
    arq = PASTA / "normas_vistas.json"
    estado = comum.ler(arq, {})
    vistos = estado.get("processos") or {}
    completa = not estado.get("completaEm") or not estado.get("coletadoEm") or (hoje - date.fromisoformat(estado["completaEm"])).days >= RENOVAR_COMPLETA_DIAS
    desde = DESDE if completa else (date.fromisoformat(estado["coletadoEm"]) - timedelta(days=1)).isoformat()
    candidatas = candidatos_a_norma(s, ids, desde, f"{hoje.year}-12-31")
    fila = [pid for pid, p in candidatas.items() if str(pid) not in vistos
            or (p.get("dataArquivamento") and not vistos[str(pid)]["arquivado"] and not vistos[str(pid)].get("norma"))]
    pedidos = set(fila)
    fila += [int(pid) for pid, v in vistos.items() if int(pid) not in pedidos and not v["arquivado"] and not v.get("norma") and devido(v["visto"], pid, hoje)]
    anos = {a: comum.ler(PASTA / f"normas_{a}.json", {}) for a in range(ANO_INICIAL, hoje.year + 1)}
    achadas, falhas = 0, []

    def uma(pid):
        try:
            sit = situacao_da_norma(pegar(s, f"processo/{pid}/tramitacao"))
            if not sit:
                return pid, None
            return pid, norma(candidatas.get(pid) or pegar(s, f"processo/{pid}"), sit)
        except comum.PrazoEsgotado:
            raise
        except Exception:
            falhas.append(pid)
            return pid, None

    try:
        with ThreadPoolExecutor(EM_PARALELO) as ex:
            for pid, n in ex.map(uma, fila):
                if pid in falhas:
                    continue
                antigo = vistos.get(str(pid)) or {}
                arquivado = bool(candidatas[pid].get("dataArquivamento")) if pid in candidatas else antigo.get("arquivado", False)
                vistos[str(pid)] = {"visto": agora, "arquivado": arquivado, **({"norma": True} if n else {})}
                if n:
                    chave, item = n
                    ano = int(item["data"][:4]) if item["data"] else item["ano"]
                    anos.setdefault(ano, {}).setdefault("normas", {})[chave] = item
                    achadas += 1
    finally:
        for a, e in anos.items():
            if e.get("normas") is not None:
                comum.salvar(PASTA / f"normas_{a}.json", {"coletadoEm": agora, "fonte": f"{SITE}/projetos", "normas": e["normas"]})
        comum.salvar(arq, {"coletadoEm": agora, "completaEm": agora if completa else estado.get("completaEm"), "processos": vistos})
    total = sum(len(e.get("normas") or {}) for e in anos.values())
    print(f"RN: {total} normas de autoria de deputado ({achadas} novas; {len(fila)} projetos lidos de {len(vistos)} acompanhados)"
          + ("" if completa else f" (lista desde {desde})"))
    if falhas:
        comum.avisar(f"RN: a API respondeu erro na tramitação de {len(falhas)} projetos (tentados de novo na próxima coleta)")


def coletar() -> None:
    s = sessao()
    deputados = coletar_deputados(s)
    sessoes = []
    try:
        sessoes = sessoes_plenarias(s)
    except Exception as e:
        comum.avisar(f"RN: lista de reuniões: {e}")
    hoje = date.today()
    etapas = [("projetos", lambda: coletar_projetos(s, deputados)), ("presença", lambda: coletar_presenca(s, deputados, sessoes)),
              ("votações", lambda: coletar_votacoes(s, deputados, sessoes)),
              ("contratos e atas de registro do órgão", lambda: coletar_orgao(sessao_pncp(), PASTA, hoje)),
              ("pautas e atas", lambda: coletar_pautas_atas(s, deputados, sessoes)), ("normas", lambda: coletar_normas(s, deputados))]
    comum.rodar_etapas(UF, etapas)


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
        falhas += comum.campos_vazios(d, ("id", "nome", "nomeCivil", "partido"), "deputado")
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
        falhas += comum.campos_vazios(m, ("tipo", "numero", "ano", "ementa", "dataApresentacao"), "projeto")
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
    falhas += comum.campos_vazios(v, ("data", "idMateria", "resultado", "sim"), "votação", vazios=(None,))
    if not m["ementa"]:
        falhas.append("matéria votada sem ementa")
    return falhas, []


def _contrato_orgao(ctx):
    s = sessao_pncp()
    ano = date.today().year
    janela = dict(dataInicial=f"{ano}0101", dataFinal=f"{ano}1231", pagina=1, tamanhoPagina=50)
    contratos = pncp_pagina(s, "contratos", cnpjOrgao=CNPJ_ORGAO, **janela)["data"]
    time.sleep(PAUSA_PNCP)
    atas = pncp_pagina(s, "atas", cnpj=CNPJ_ORGAO, **janela)["data"]
    return {"contratos": [c for c in contratos if c.get("tipoPessoa") == "PJ"][:2], "atas": atas[:2]}


def _conferir_orgao(registro):
    falhas = []
    itens = itens_do_orgao(registro["contratos"], registro["atas"])
    if not any(i["tipo"] == "contrato" for i in itens.values()):
        falhas.append("PNCP /contratos sem contrato do órgão no ano")
    if not any(i["tipo"] == "ata_registro" for i in itens.values()):
        falhas.append("PNCP /atas sem ata de registro de preços do órgão no ano")
    for r in registro["contratos"]:
        falhas += comum.campos_vazios(r, ("numeroControlePNCP", "objetoContrato", "valorGlobal", "dataVigenciaInicio", "dataVigenciaFim",
                                          "niFornecedor", "nomeRazaoSocialFornecedor"), "contrato", vazios=(None, ""))
    for r in registro["atas"]:
        falhas += comum.campos_vazios(r, ("numeroControlePNCPAta", "numeroAtaRegistroPreco", "objetoContratacao", "vigenciaInicio", "vigenciaFim"), "ata", vazios=(None, ""))
    falhas += ["contrato ou ata sem link do PNCP" for i in itens.values() if not i["arquivos"]]
    return falhas, []


def _plenaria_com_pauta(s):
    for r in paginas(s, "reuniao", situacao="R", tipoOrdenacao="DESC"):
        if (r.get("tipoReuniao") or {}).get("id") in TIPO_PLENARIO:
            fases = {fase: pegar(s, "processo", reuniao=r["id"], faseReuniao=fase).get("dados") or [] for fase in (1, 2)}
            if any(fases.values()):
                return r, fases
    raise RuntimeError("nenhuma sessão plenária com pauta entre as reuniões realizadas")


def _contrato_pauta(ctx):
    s = sessao()
    r, fases = _plenaria_com_pauta(s)
    reduzida = {k: r[k] for k in ("id", "numero", "situacao", "dataInicio", "tipoReuniao")}
    return {"reuniao": reduzida, "fases": {str(f): [_sem_cpf(p) for p in lista[:2]] for f, lista in fases.items()}}


def _conferir_pauta(registro):
    falhas = []
    ids = {str(p["iniciativa"]["parlamentar"]["id"]) for lista in registro["fases"].values() for p in lista if (p.get("iniciativa") or {}).get("parlamentar")}
    processos = processos_da_pauta({int(f): lista for f, lista in registro["fases"].items()}, ids)
    item = item_pauta(registro["reuniao"], processos)
    if not item:
        return ["pauta da sessão sem processos"], []
    falhas += comum.campos_vazios(item, ("titulo", "data", "fonte"), "pauta")
    for p in processos:
        falhas += comum.campos_vazios(p, ("id", "tipo", "numero", "ano", "ementa"), "processo da pauta")
    if not any(p["idDeputado"] for p in processos):
        falhas.append("nenhum processo da pauta com iniciativa de deputado")
    return falhas, []


def _contrato_atas(ctx):
    s = sessao()
    for r in paginas(s, "reuniao", situacao="R", tipoOrdenacao="DESC"):
        if (r.get("tipoReuniao") or {}).get("id") not in TIPO_PLENARIO:
            continue
        videos = pegar(s, f"legis-videos/reuniao/{r['id']}").get("dados") or []
        com_ata = [v for v in videos if v.get("ata") and v.get("hash")]
        if com_ata:
            v = {k: com_ata[0][k] for k in ("id", "reuniao", "hash", "titulo", "dataVideo")}
            return {"reuniao": {k: r[k] for k in ("id", "numero", "dataInicio", "tipoReuniao")}, "videos": [{**v, "ata": "<p>texto da ata omitido da amostra</p>"}]}
    raise RuntimeError("nenhuma sessão plenária com ata publicada entre as reuniões realizadas")


def _conferir_atas(registro):
    itens = itens_ata(registro["reuniao"], registro["videos"])
    if not itens:
        return ["legis-videos sem ata (campos ata e hash)"], []
    return comum.campos_vazios(itens[0], ("titulo", "data", "fonte"), "ata"), []


PROCESSO_NORMA = 51724


def _contrato_normas(ctx):
    s = sessao()
    lista = pegar(s, "processo", pagina=0, tamanhoPagina=5, tipoPropositura=1)["dados"]
    p = pegar(s, f"processo/{PROCESSO_NORMA}")
    tram = pegar(s, f"processo/{PROCESSO_NORMA}/tramitacao")
    chaves = ("id", "ementa", "propositura", "iniciativa", "dataEntrada", "dataArquivamento")
    return {"lista": [{k: x[k] for k in chaves} for x in lista], "processo": {k: p[k] for k in chaves},
            "tramitacao": [t for t in tram if (t.get("situacaoProcesso") or {}).get("id") in SITUACOES_NORMA][:2] + tram[-1:]}


def _conferir_normas(registro):
    falhas = []
    sit = situacao_da_norma(registro["tramitacao"])
    if not sit:
        return ["tramitação sem situação de lei sancionada ou promulgada (ids 26, 27, 127, 128)"], []
    chave, n = norma(registro["processo"], sit)
    falhas += comum.campos_vazios(n, ("tipo", "numero", "ano", "data", "ementa", "situacao", "fonte"), "norma")
    if not registro["lista"] or not all((p.get("iniciativa") or {}).get("tipo") for p in registro["lista"]):
        falhas.append("lista de processos por tipo sem iniciativa")
    return falhas, []


CONTRATOS = [
    {"nome": "estadual_rn_deputados", "fonte": f"{API}/parlamentar", "buscar": _contrato_deputados, "html": _conferir_deputados},
    {"nome": "estadual_rn_projetos", "fonte": f"{API}/processo", "buscar": _contrato_projetos, "html": _conferir_projetos},
    {"nome": "estadual_rn_presenca", "fonte": f"{API}/reuniao", "buscar": _contrato_presenca, "html": _conferir_presenca},
    {"nome": "estadual_rn_votacao", "fonte": f"{API}/processo/ultimas-votacoes", "buscar": _contrato_votacao, "html": _conferir_votacao},
    {"nome": "estadual_rn_orgao", "fonte": f"{PNCP}/contratos", "buscar": _contrato_orgao, "html": _conferir_orgao},
    {"nome": "estadual_rn_pauta", "fonte": f"{API}/processo?reuniao=", "buscar": _contrato_pauta, "html": _conferir_pauta},
    {"nome": "estadual_rn_atas", "fonte": f"{API}/legis-videos/reuniao", "buscar": _contrato_atas, "html": _conferir_atas},
    {"nome": "estadual_rn_normas", "fonte": f"{API}/processo/{PROCESSO_NORMA}/tramitacao", "buscar": _contrato_normas, "html": _conferir_normas},
]


if __name__ == "__main__":
    comum.principal(coletar)
