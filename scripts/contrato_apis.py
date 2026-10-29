"""
Contrato das APIs externas: grava respostas reais (pequenas) como fixtures e, toda semana, confere se as APIs
ainda devolvem os campos de que os coletores dependem.

  - `--gravar` consulta cada API, guarda uma amostra reduzida e a "forma" da resposta (caminhos e tipos dos
    campos) em tests/fixtures/contratos/<nome>.json. Os testes usam essas amostras no lugar de respostas inventadas.
  - `--verificar` consulta de novo e compara com a forma gravada. Falha (código 1) se sumir ou mudar de tipo um
    campo que o código usa (listado em `usados`); o resto vira aviso. Fonte fora do ar é aviso, não falha.
    O resumo vai para o log e para $GITHUB_STEP_SUMMARY.

Uso:
    python scripts/contrato_apis.py --listar
    python scripts/contrato_apis.py --gravar [nome ...]
    python scripts/contrato_apis.py --verificar [nome ...]

Caminhos: "a.b" é o campo b dentro de a; "a[]" são os itens de uma lista; "**chave" é a chave em qualquer nível
(sem diferenciar maiúsculas, como o coletor do Senado lê). Arquivos do TSE são conferidos pelas colunas do CSV.
"""

import argparse
import datetime as dt
import io
import json
import os
import sys
import importlib
import tempfile
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parent.parent
FIXTURES = RAIZ / "tests" / "fixtures" / "contratos"
UA = "minha-bancada (projeto de transparencia; verificacao semanal de contrato)"
AMOSTRA = 2          # itens guardados por lista
TEXTO_MAX = 300      # caracteres guardados por texto

CAMARA = "https://dadosabertos.camara.leg.br/api/v2"
SENADO = "https://legis.senado.leg.br/dadosabertos"
SENADO_ADM = "https://adm.senado.gov.br/adm-dadosabertos/api/v1"
TSE = "https://cdn.tse.jus.br/estatistica/sead/odsele"
SAPL = "sapl.al.pb.leg.br"
SPLEGIS = "https://splegisws.saopaulo.sp.leg.br/ws/ws2.asmx"
HOJE = dt.date.today()
ANO = HOJE.year if HOJE.month > 2 else HOJE.year - 1   # logo no início do ano ainda há pouco o que listar


# ---------------------------------------------------------------- forma da resposta

def tipo_de(v) -> str:
    return ("null" if v is None else "bool" if isinstance(v, bool) else "int" if isinstance(v, int)
            else "float" if isinstance(v, float) else "str" if isinstance(v, str) else "list" if isinstance(v, list) else "dict")


def forma(obj) -> dict[str, dict]:
    """caminho -> {"tipos": [...], "opcional": True se faltou em algum objeto da amostra}."""
    tipos: dict[str, set] = defaultdict(set)
    pai: dict[str, str] = {}
    presentes, ocorrencias = Counter(), Counter()

    def visita(v, caminho):
        tipos[caminho].add(tipo_de(v))
        if isinstance(v, dict):
            ocorrencias[caminho] += 1
            for k, x in v.items():
                c = f"{caminho}.{k}" if caminho else k
                pai[c] = caminho
                presentes[c] += 1
                visita(x, c)
        elif isinstance(v, list):
            for x in v:
                visita(x, caminho + "[]")

    visita(obj, "")
    saida = {}
    for c, t in sorted(tipos.items()):
        if not c:
            continue
        info = {"tipos": sorted(t)}
        if c in pai and presentes[c] < ocorrencias[pai[c]]:
            info["opcional"] = True
        saida[c] = info
    return saida


def reduzir(obj, n: int = AMOSTRA):
    """Mantém só os n primeiros itens de cada lista e corta textos longos."""
    if isinstance(obj, list):
        return [reduzir(x, n) for x in obj[:n]]
    if isinstance(obj, dict):
        return {k: reduzir(v, n) for k, v in obj.items()}
    if isinstance(obj, str) and len(obj) > TEXTO_MAX:
        return obj[:TEXTO_MAX]
    return obj


def casa(caminho: str, f: dict) -> list[str]:
    """Caminhos de `f` que correspondem a `caminho` (exato, ou **chave em qualquer nível)."""
    if caminho.startswith("**"):
        chave = caminho[2:].lower()
        return [c for c in f if c.replace("[]", ".").rstrip(".").rsplit(".", 1)[-1].lower() == chave]
    return [caminho] if caminho in f else []


def sem_amostra(caminho: str, f: dict) -> bool:
    """True se algum ancestral do caminho é uma lista vazia na resposta (não há o que conferir)."""
    partes = caminho.split("[]")
    acumulado = ""
    for p in partes[:-1]:
        acumulado += p
        if acumulado in f and "list" in f[acumulado]["tipos"] and acumulado + "[]" not in f:
            return True
        acumulado += "[]"
    return False


def comparar(gravada: dict, viva: dict, usados: list[str]) -> tuple[list[str], list[str]]:
    """(falhas, avisos): falha só para campo usado que sumiu ou mudou de tipo."""
    falhas, avisos = [], []
    for u in usados:
        achados_g, achados_v = casa(u, gravada), casa(u, viva)
        if not achados_g:
            avisos.append(f"{u}: campo usado não aparecia na amostra gravada")
        if not achados_v:
            if sem_amostra(u, viva):
                avisos.append(f"{u}: resposta atual sem itens para conferir")
            elif not achados_g:
                continue   # já avisado acima: nunca apareceu, então não dá para dizer que sumiu
            elif all(gravada[c].get("opcional") for c in achados_g):
                avisos.append(f"{u}: campo opcional ausente na amostra atual")
            else:
                falhas.append(f"{u}: campo sumiu da resposta")
            continue
        for c in achados_v:
            if c in gravada:
                antes, agora = set(gravada[c]["tipos"]), set(viva[c]["tipos"])
                if antes != {"null"} and not agora <= antes | {"null"}:
                    falhas.append(f"{c}: tipo mudou de {sorted(antes)} para {sorted(agora)}")
    for c in sorted(set(gravada) - set(viva)):
        if not gravada[c].get("opcional") and not sem_amostra(c, viva) and not any(c == u or u.startswith("**") for u in usados):
            avisos.append(f"{c}: campo da amostra gravada não veio agora")
    novos = sorted(set(viva) - set(gravada))
    if novos:
        avisos.append(f"campos novos: {', '.join(novos[:8])}{' …' if len(novos) > 8 else ''}")
    return falhas, avisos


def descontinuacao(resp) -> list[str]:
    """Avisos de endpoints que a própria API marca como descontinuados (Metadados.Descontinuacao do Senado)."""
    saida = []

    def achado(o, k):
        return next(iter(iterar(o, k)), None)

    if achado(resp, "DataDesativacaoCompleta"):
        saida.append(f"endpoint descontinuado: desativação completa em {achado(resp, 'DataDesativacaoCompleta')}"
                     f"{', substituto: ' + achado(resp, 'UrlServicoSubstituto') if achado(resp, 'UrlServicoSubstituto') else ''}")
    return saida


def comparar_colunas(gravadas: list[str], vivas: list[str], criticas: list[str], esperadas: list[str]) -> tuple[list[str], list[str]]:
    falhas = [f"coluna {c} sumiu do CSV" for c in criticas if c not in vivas]
    avisos = [f"coluna {c} não veio (o coletor tolera)" for c in esperadas if c not in vivas and c not in criticas]
    novas = sorted(set(vivas) - set(gravadas))
    if novas:
        avisos.append(f"colunas novas: {', '.join(novas[:8])}{' …' if len(novas) > 8 else ''}")
    return falhas, avisos


# ---------------------------------------------------------------- busca

def http_json(url: str, **params):
    r = requests.get(url, params=params or None, headers={"Accept": "application/json", "User-Agent": UA}, timeout=120)
    r.raise_for_status()
    return r.json()


def cabecalho_csv(url: str) -> list[str]:
    """Baixa o ZIP do TSE e devolve só as colunas do CSV (nacional, se houver)."""
    with tempfile.NamedTemporaryFile(suffix=".zip") as tmp:
        with requests.get(url, stream=True, timeout=300, headers={"User-Agent": UA}) as r:
            r.raise_for_status()
            for bloco in r.iter_content(1 << 20):
                tmp.write(bloco)
        tmp.flush()
        with zipfile.ZipFile(tmp.name) as z:
            nomes = [n for n in z.namelist() if n.lower().endswith(".csv")]
            nome = next((n for n in nomes if n.upper().endswith("_BRASIL.CSV")), nomes[0])
            with z.open(nome) as f:
                linha = io.TextIOWrapper(f, encoding="latin-1").readline()
    return [c.strip('"') for c in linha.strip().split(";")]


class Endpoint:
    def __init__(self, nome, fonte, buscar, usados=(), colunas_criticas=(), colunas_esperadas=(), html=None, independente=False):
        self.independente = independente
        self.nome, self.fonte, self.buscar, self.usados = nome, fonte, buscar, list(usados)
        self.colunas_criticas, self.colunas_esperadas, self.html = list(colunas_criticas), list(colunas_esperadas), html


ENDPOINTS: list[Endpoint] = []


def ep(nome, fonte, usados=(), **kw):
    def deco(f):
        ENDPOINTS.append(Endpoint(nome, fonte, f, usados, **kw))
        return f
    return deco


def campos(base: str, *nomes: str) -> list[str]:
    return [f"{base}.{n}" if base else n for n in nomes]


# ---------------------------------------------------------------- Câmara

@ep("camara_deputados", f"{CAMARA}/deputados", campos("dados[]", "id", "nome", "siglaPartido", "siglaUf", "urlFoto", "email") + ["links[].rel", "links[].href"])
def _(ctx):
    r = http_json(f"{CAMARA}/deputados", itens=15, ordem="ASC", ordenarPor="nome")
    ctx["deps"] = [d["id"] for d in r["dados"]]
    ctx["dep"] = ctx["deps"][0]
    return r


@ep("camara_deputado", f"{CAMARA}/deputados/{{id}}",
    campos("dados", "nomeCivil", "dataNascimento", "municipioNascimento", "ufNascimento", "escolaridade", "redeSocial", "ultimoStatus")
    + campos("dados.ultimoStatus", "nomeEleitoral", "siglaPartido", "siglaUf", "urlFoto", "email", "situacao", "condicaoEleitoral", "gabinete"))
def _(ctx):
    return http_json(f"{CAMARA}/deputados/{ctx['dep']}")


def _primeiro_com_dados(ctx, caminho, **params):
    """Primeira resposta não vazia entre os deputados da lista (profissão e mandato externo faltam em muitos)."""
    r = None
    for did in ctx["deps"]:
        r = http_json(f"{CAMARA}/deputados/{did}/{caminho}", **params)
        if r["dados"] and any(v for v in r["dados"][0].values()):
            return r
    return r


@ep("camara_profissoes", f"{CAMARA}/deputados/{{id}}/profissoes", campos("dados[]", "titulo", "dataHora"))
def _(ctx):
    return _primeiro_com_dados(ctx, "profissoes")


@ep("camara_ocupacoes", f"{CAMARA}/deputados/{{id}}/ocupacoes",
    campos("dados[]", "titulo", "entidade", "entidadeUF", "anoInicio", "anoFim"))
def _(ctx):
    return _primeiro_com_dados(ctx, "ocupacoes")


@ep("camara_mandatos_externos", f"{CAMARA}/deputados/{{id}}/mandatosExternos",
    campos("dados[]", "cargo", "siglaUf", "municipio", "anoInicio", "anoFim", "siglaPartidoEleicao"))
def _(ctx):
    return _primeiro_com_dados(ctx, "mandatosExternos")


@ep("camara_historico", f"{CAMARA}/deputados/{{id}}/historico",
    campos("dados[]", "idLegislatura", "dataHora", "siglaPartido", "situacao", "condicaoEleitoral", "descricaoStatus"))
def _(ctx):
    return http_json(f"{CAMARA}/deputados/{ctx['dep']}/historico")


@ep("camara_discursos", f"{CAMARA}/deputados/{{id}}/discursos",
    campos("dados[]", "dataHoraInicio", "tipoDiscurso", "sumario", "urlTexto", "urlVideo", "urlAudio") + ["dados[].faseEvento.titulo"])
def _(ctx):
    return _primeiro_com_dados(ctx, "discursos", itens=2, ordem="DESC", ordenarPor="dataHoraInicio", dataInicio="2023-02-01")


@ep("camara_despesas", f"{CAMARA}/deputados/{{id}}/despesas", campos("dados[]", "mes", "tipoDespesa", "valorLiquido", "nomeFornecedor", "dataDocumento", "urlDocumento"))
def _(ctx):
    # um deputado com despesas no ano: procura nos primeiros da lista
    for ano in (ANO, ANO - 1):
        for did in ctx["deps"]:
            r = http_json(f"{CAMARA}/deputados/{did}/despesas", ano=ano, itens=3)
            if r["dados"]:
                return r
    return r


@ep("camara_proposicoes", f"{CAMARA}/proposicoes", campos("dados[]", "id", "siglaTipo", "numero", "ano", "ementa"))
def _(ctx):
    r = http_json(f"{CAMARA}/proposicoes", siglaTipo="PL", ano=ANO, itens=3, ordem="DESC", ordenarPor="id")
    ctx["prop"] = r["dados"][0]["id"]
    return r


@ep("camara_proposicao", f"{CAMARA}/proposicoes/{{id}}",
    campos("dados", "dataApresentacao", "siglaTipo", "numero", "ano", "ementa", "urlInteiroTeor", "statusProposicao")
    + campos("dados.statusProposicao", "descricaoSituacao", "descricaoTramitacao", "despacho", "siglaOrgao", "dataHora", "regime"))
def _(ctx):
    return http_json(f"{CAMARA}/proposicoes/{ctx['prop']}")


@ep("camara_executivo", f"{CAMARA}/proposicoes?autor=Poder Executivo", campos("dados[]", "id") + ["links[].rel", "links[].href"])
def _(ctx):
    r = http_json(f"{CAMARA}/proposicoes", autor="Poder Executivo", siglaTipo="PL", ano=ANO, itens=3)
    if r["dados"]:
        ctx["exec"] = r["dados"][0]["id"]
    return r


@ep("camara_tramitacoes", f"{CAMARA}/proposicoes/{{id}}/tramitacoes", campos("dados[]", "despacho", "descricaoSituacao", "dataHora"))
def _(ctx):
    return http_json(f"{CAMARA}/proposicoes/{ctx.get('exec') or ctx['prop']}/tramitacoes")


@ep("camara_relacionadas", f"{CAMARA}/proposicoes/{{id}}/relacionadas", campos("dados[]", "id", "uri", "siglaTipo", "numero", "ano"))
def _(ctx):
    return http_json(f"{CAMARA}/proposicoes/{ctx['prop']}/relacionadas")


@ep("camara_votacoes", f"{CAMARA}/votacoes", campos("dados[]", "id", "data", "dataHoraRegistro", "siglaOrgao", "descricao", "aprovacao"))
def _(ctx):
    ini = (HOJE - dt.timedelta(days=29)).isoformat()
    r = http_json(f"{CAMARA}/votacoes", dataInicio=ini, dataFim=HOJE.isoformat(), ordem="DESC", ordenarPor="dataHoraRegistro", itens=60)
    for v in r["dados"]:
        if v.get("siglaOrgao") == "PLEN" and http_json(f"{CAMARA}/votacoes/{v['id']}/votos")["dados"]:
            ctx["votacao"] = v["id"]
            break
    r["dados"] = r["dados"][:AMOSTRA + 1]
    return r


@ep("camara_votos", f"{CAMARA}/votacoes/{{id}}/votos", ["dados[].deputado_.id", "dados[].tipoVoto"])
def _(ctx):
    return http_json(f"{CAMARA}/votacoes/{ctx['votacao']}/votos")


@ep("camara_votacao", f"{CAMARA}/votacoes/{{id}}", campos("dados", "proposicoesAfetadas"))
def _(ctx):
    return http_json(f"{CAMARA}/votacoes/{ctx['votacao']}")


# ---------------------------------------------------------------- Senado

@ep("senado_lista", f"{SENADO}/senador/lista/atual.json",
    campos("ListaParlamentarEmExercicio.Parlamentares.Parlamentar[]", "IdentificacaoParlamentar", "Mandato")
    + campos("ListaParlamentarEmExercicio.Parlamentares.Parlamentar[].Mandato", "DescricaoParticipacao", "UfParlamentar", "Titular.NomeParlamentar",
             "PrimeiraLegislaturaDoMandato.DataFim", "SegundaLegislaturaDoMandato.DataFim", "Exercicios.Exercicio[].DataInicio", "Exercicios.Exercicio[].DataFim")
    + campos("ListaParlamentarEmExercicio.Parlamentares.Parlamentar[].IdentificacaoParlamentar", "CodigoParlamentar", "NomeParlamentar", "NomeCompletoParlamentar",
             "SiglaPartidoParlamentar", "UfParlamentar", "UrlFotoParlamentar", "UrlPaginaParlamentar", "EmailParlamentar", "SexoParlamentar"))
def _(ctx):
    r = http_json(f"{SENADO}/senador/lista/atual.json")
    ctx["senador"] = r["ListaParlamentarEmExercicio"]["Parlamentares"]["Parlamentar"][0]["IdentificacaoParlamentar"]["CodigoParlamentar"]
    return r


@ep("senado_comissoes", f"{SENADO}/senador/{{id}}/comissoes",
    campos("MembroComissaoParlamentar.Parlamentar.MembroComissoes.Comissao[]", "DescricaoParticipacao", "DataInicio")
    + campos("MembroComissaoParlamentar.Parlamentar.MembroComissoes.Comissao[].IdentificacaoComissao", "CodigoComissao", "SiglaComissao", "NomeComissao", "SiglaCasaComissao"))
def _(ctx):
    return http_json(f"{SENADO}/senador/{ctx['senador']}/comissoes.json")


@ep("senado_mandatos", f"{SENADO}/senador/{{id}}/mandatos",
    campos("MandatoParlamentar.Parlamentar.Mandatos.Mandato[]", "CodigoMandato", "UfParlamentar", "DescricaoParticipacao",
           "PrimeiraLegislaturaDoMandato.DataInicio", "SegundaLegislaturaDoMandato.DataFim", "Partidos.Partido[].Sigla", "Partidos.Partido[].DataFiliacao"))
def _(ctx):
    return http_json(f"{SENADO}/senador/{ctx['senador']}/mandatos.json")


@ep("senado_votacoes", f"{SENADO}/votacao",
    campos("[]", "codigoSessaoVotacao", "dataSessao", "descricaoVotacao", "identificacao", "codigoMateria", "ementa", "resultadoVotacao", "votacaoSecreta")
    + campos("[].votos[]", "codigoParlamentar", "siglaVotoParlamentar", "descricaoVotoParlamentar"))
def _(ctx):
    ini = (HOJE - dt.timedelta(days=90)).isoformat()
    return http_json(f"{SENADO}/votacao", dataInicio=ini, dataFim=HOJE.isoformat())


@ep("senado_processos", f"{SENADO}/processo?codigoParlamentarAutor={{id}}",
    campos("[]", "id", "identificacao", "codigoMateria", "ementa", "autoria", "dataApresentacao", "situacaoAtual", "dataSituacaoAtual"))
def _(ctx):
    return http_json(f"{SENADO}/processo", codigoParlamentarAutor=ctx["senador"])


@ep("senado_ceaps", f"{SENADO_ADM}/senadores/despesas_ceaps/{{ano}}",
    campos("[]", "codSenador", "mes", "tipoDespesa", "valorReembolsado", "fornecedor", "cpfCnpj", "data"))
def _(ctx):
    return http_json(f"{SENADO_ADM}/senadores/despesas_ceaps/{HOJE.year}")


@ep("senado_recursos", f"{SENADO_ADM}/senadores/{{id}}/recursos-utilizados?ano={{ano}}",
    campos("", "statusCode", "data[].gastosNaoInclusos.totalValor", "data[].gastosNaoInclusos.despesas[].recurso", "data[].gastosNaoInclusos.despesas[].valor", "data[].beneficios[].beneficio", "data[].beneficios[].utilizacao", "data[].pessoal[].local", "data[].pessoal[].quantidade"))
def _(ctx):
    return http_json(f"{SENADO_ADM}/senadores/{ctx['senador']}/recursos-utilizados", ano=HOJE.year)


@ep("senado_escritorios", f"{SENADO_ADM}/senadores/escritorios-apoio",
    campos("", "data[].parlamentar.nome", "data[].parlamentar.estado", "data[].setor.endereco", "data[].setor.telefone"))
def _(ctx):
    return http_json(f"{SENADO_ADM}/senadores/escritorios-apoio")


# ---------------------------------------------------------------- ministros (scripts/coletar_ministros.py)

@ep("camara_arquivo_proposicoes", "https://dadosabertos.camara.leg.br/arquivos/proposicoes/json/proposicoes-{ano}.json",
    campos("dados[]", "id", "siglaTipo", "numero", "ano", "ementa", "dataApresentacao", "urlInteiroTeor")
    + campos("dados[].ultimoStatus", "data", "descricaoSituacao", "descricaoTramitacao", "siglaOrgao"))
def _(ctx):
    import coletar_ministros as m
    dados = http_json(f"{m.ARQUIVOS}/proposicoes/json/proposicoes-{ANO}.json")["dados"]
    ric = next(p for p in dados if p["siglaTipo"] == "RIC" and "resposta" in m.comum.sem_acento((p.get("ultimoStatus") or {}).get("descricaoTramitacao")))
    req = next(p for p in dados if p["siglaTipo"] == "REQ" and m.convocacao(p.get("ementa")))
    ctx["ric"] = ric["id"]
    return {"dados": [ric, req]}


@ep("camara_tramitacoes_ric", f"{CAMARA}/proposicoes/{{id}}/tramitacoes", campos("dados[]", "descricaoTramitacao", "despacho", "dataHora"))
def _(ctx):
    import coletar_ministros as m
    r = http_json(f"{CAMARA}/proposicoes/{ctx['ric']}/tramitacoes")
    # a amostra guarda só 2 itens: os que o coletor lê com texto que muda de forma (prazo no despacho e a resposta)
    r["dados"] = [t for t in r["dados"] if m.comum.sem_acento(t.get("descricaoTramitacao")).startswith(("abertura de prazo", "recebimento de resposta"))]
    return r


@ep("camara_arquivo_autores", "https://dadosabertos.camara.leg.br/arquivos/proposicoesAutores/json/proposicoesAutores-{ano}.json",
    campos("dados[]", "idProposicao", "idDeputadoAutor", "nomeAutor", "ordemAssinatura"), independente=True)
def _(ctx):
    return {"dados": http_json(f"https://dadosabertos.camara.leg.br/arquivos/proposicoesAutores/json/proposicoesAutores-{ANO}.json")["dados"][:AMOSTRA]}


@ep("senado_afastados", f"{SENADO}/senador/lista/afastados.json",
    campos("AfastamentoAtual.Parlamentares.Parlamentar[].IdentificacaoParlamentar", "CodigoParlamentar", "NomeParlamentar")
    + ["**DescricaoCausaAfastamento", "**DescricaoCargoAssumido", "**DataInicio", "**DataFim"], independente=True)
def _(ctx):
    r = http_json(f"{SENADO}/senador/lista/afastados.json")
    lista = r["AfastamentoAtual"]["Parlamentares"]["Parlamentar"]
    r["AfastamentoAtual"]["Parlamentares"]["Parlamentar"] = sorted(lista, key=lambda p: "DescricaoCargoAssumido" not in json.dumps(p))
    return r


@ep("senado_requerimentos", f"{SENADO}/processo?sigla=RQS&ano={{ano}}",
    campos("[]", "id", "identificacao", "tipoConteudo", "ementa", "autoria", "dataApresentacao", "tramitando", "urlDocumento"), independente=True)
def _(ctx):
    import coletar_ministros as m
    r = http_json(f"{SENADO}/processo", sigla="RQS", ano=ANO)
    return [p for p in r if (p.get("tipoConteudo") or "").strip() in m.TIPOS_SENADO and m.ministro(p.get("ementa"))]


def _planalto_pagina(ctx):
    import coletar_ministros as m
    html = requests.get(m.PLANALTO, headers={"User-Agent": UA, "Accept": "text/html"}, timeout=60).text
    ini, fim = html.find('<div class="documentByLine"'), html.find("</div>", html.find('id="parent-fieldname-text"'))
    return {"html": html[ini:fim + 6]}


def _planalto_conferir(registro):
    import coletar_ministros as m
    lista, atualizado = m.ler_planalto(registro["html"])
    falhas = [f"só {len(lista)} ministros reconhecidos na página"] if len(lista) < m.MINIMO_PLANALTO else []
    return falhas, [] if atualizado else ["página sem 'Atualizado em'"]


ENDPOINTS.append(Endpoint("planalto_ministros", "https://www.gov.br/planalto/pt-br/conheca-a-presidencia/ministros-e-ministras", _planalto_pagina,
                          html=_planalto_conferir))


def iterar(obj, chave):
    """Todos os valores da chave em qualquer nível."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == chave:
                yield v
            yield from iterar(v, chave)
    elif isinstance(obj, list):
        for v in obj:
            yield from iterar(v, chave)


# ---------------------------------------------------------------- SAPL (Assembleias e Câmaras)

def sapl(caminho, **params):
    return http_json(f"https://{SAPL}/api/{caminho.strip('/')}/", page_size=3, **params)


@ep("sapl_legislatura", f"https://{SAPL}/api/parlamentares/legislatura/", campos("results[]", "id", "numero", "data_inicio", "data_fim") + ["pagination.next_page"])
def _(ctx):
    r = sapl("parlamentares/legislatura")
    ctx["leg"] = r["results"][0]["id"]
    return r


@ep("sapl_mandato", f"https://{SAPL}/api/parlamentares/mandato/", campos("results[]", "parlamentar", "data_inicio_mandato", "data_fim_mandato", "titular"))
def _(ctx):
    r = sapl("parlamentares/mandato", legislatura=ctx["leg"])
    ctx["parl"] = r["results"][0]["parlamentar"]
    return r


@ep("sapl_parlamentar", f"https://{SAPL}/api/parlamentares/parlamentar/{{id}}/", ["nome_parlamentar", "nome_completo", "fotografia", "email"])
def _(ctx):
    return http_json(f"https://{SAPL}/api/parlamentares/parlamentar/{ctx['parl']}/")


@ep("sapl_tipoautor", f"https://{SAPL}/api/base/tipoautor/", campos("results[]", "id", "descricao"))
def _(ctx):
    return sapl("base/tipoautor")


@ep("sapl_autor", f"https://{SAPL}/api/base/autor/", campos("results[]", "id", "tipo", "object_id", "nome"))
def _(ctx):
    return sapl("base/autor")


@ep("sapl_tipomateria", f"https://{SAPL}/api/materia/tipomaterialegislativa/", campos("results[]", "id", "sigla", "descricao"))
def _(ctx):
    return sapl("materia/tipomaterialegislativa")


@ep("sapl_materia", f"https://{SAPL}/api/materia/materialegislativa/",
    campos("results[]", "id", "tipo", "numero", "ano", "data_apresentacao", "ementa", "em_tramitacao", "resultado", "texto_original", "autores"))
def _(ctx):
    return sapl("materia/materialegislativa", ano=ANO)


@ep("sapl_tiporesultado", f"https://{SAPL}/api/sessao/tiporesultadovotacao/", campos("results[]", "id", "nome", "natureza"))
def _(ctx):
    return sapl("sessao/tiporesultadovotacao")


@ep("sapl_votoparlamentar", f"https://{SAPL}/api/sessao/votoparlamentar/", campos("results[]", "votacao", "parlamentar", "voto"))
def _(ctx):
    r = sapl("sessao/votoparlamentar", data_hora__gte=f"{ANO}-01-01")
    if r["results"]:
        ctx["registro"] = r["results"][0]["votacao"]
    return r


@ep("sapl_registrovotacao", f"https://{SAPL}/api/sessao/registrovotacao/{{id}}/",
    ["data_hora", "materia", "tipo_resultado_votacao", "numero_votos_sim", "numero_votos_nao", "numero_abstencoes"])
def _(ctx):
    return http_json(f"https://{SAPL}/api/sessao/registrovotacao/{ctx['registro']}/")


# ---------------------------------------------------------------- SPLegis (São Paulo)

@ep("splegis_promoventes", f"{SPLEGIS}/PromoventesCMSPJSON", ["[].chave", "[].nome", "[].tipo.nome"])
def _(ctx):
    r = http_json(f"{SPLEGIS}/PromoventesCMSPJSON")
    import coletar_prefeitura_sp as sp
    prefeito = [p for p in r if (p.get("tipo") or {}).get("nome") == "EXECUTIVO" and p["nome"].lower() == sp.PREFEITO]
    ctx["promovente"] = prefeito[0]["chave"] if prefeito else None
    return prefeito + r[:1]


@ep("splegis_projetos", f"{SPLEGIS}/ProjetosPorAnoJSON", ["[].tipo", "[].numero", "[].ano", "[].data", "[].ementa"])
def _(ctx):
    r = http_json(f"{SPLEGIS}/ProjetosPorAnoJSON", Ano=ANO)
    ctx["projeto"] = next((p for p in r if p["tipo"] == "PL"), r[0])
    return r[:AMOSTRA + 1]


@ep("splegis_resumo", f"{SPLEGIS}/ProjetoResumoJSON", ["Autores[].Chave"])
def _(ctx):
    p = ctx["projeto"]
    return http_json(f"{SPLEGIS}/ProjetoResumoJSON", Tipo=p["tipo"], Numero=p["numero"], Ano=p["ano"])


@ep("splegis_tramitacao", f"{SPLEGIS}/ProjetosEmTramitacaoPorPromoventeJSON", ["[].tipo", "[].numero", "[].ano"])
def _(ctx):
    return http_json(f"{SPLEGIS}/ProjetosEmTramitacaoPorPromoventeJSON", Codigo=ctx["promovente"])[:AMOSTRA + 1]


@ep("splegis_vetos", f"{SPLEGIS}/ProjetosVetadosPorPromoventeJSON", ["[].tipo", "[].numero", "[].ano", "[].veto.nome"])
def _(ctx):
    return http_json(f"{SPLEGIS}/ProjetosVetadosPorPromoventeJSON", Codigo=ctx["promovente"])[:AMOSTRA + 1]


@ep("splegis_leis", f"{SPLEGIS}/LeisAprovadasPorPromoventeJSON", ["[].projeto.tipo", "[].projeto.numero", "[].projeto.ano", "[].numero", "[].publicacao"])
def _(ctx):
    return http_json(f"{SPLEGIS}/LeisAprovadasPorPromoventeJSON", Codigo=ctx["promovente"])[:AMOSTRA + 1]


# ---------------------------------------------------------------- TSE (colunas dos CSV)

def _colunas_cand():
    import coletar_tse
    return coletar_tse.COLUNAS


@ep("tse_consulta_cand", f"{TSE}/consulta_cand/consulta_cand_2024.zip", colunas_criticas=["SQ_CANDIDATO", "DS_CARGO", "DS_SIT_TOT_TURNO", "SG_UF", "SG_UE", "NM_UE", "NR_CANDIDATO"],
    colunas_esperadas=_colunas_cand())
def _(ctx):
    return {"colunas": cabecalho_csv(f"{TSE}/consulta_cand/consulta_cand_2024.zip")}


@ep("tse_bem_candidato", f"{TSE}/bem_candidato/bem_candidato_2024.zip",
    colunas_criticas=["SQ_CANDIDATO", "DS_TIPO_BEM_CANDIDATO", "DS_BEM_CANDIDATO", "VR_BEM_CANDIDATO"])
def _(ctx):
    return {"colunas": cabecalho_csv(f"{TSE}/bem_candidato/bem_candidato_2024.zip")}


@ep("tse_votacao_munzona", f"{TSE}/votacao_candidato_munzona/votacao_candidato_munzona_2024.zip",
    colunas_criticas=["DS_CARGO", "NR_TURNO", "SG_UE", "SQ_CANDIDATO", "QT_VOTOS_NOMINAIS", "DT_ELEICAO"])
def _(ctx):
    return {"colunas": cabecalho_csv(f"{TSE}/votacao_candidato_munzona/votacao_candidato_munzona_2024.zip")}


@ep("tse_redes_sociais", f"{TSE}/consulta_cand/rede_social_candidato_2024.zip", colunas_criticas=["SQ_CANDIDATO", "DS_URL"])
def _(ctx):
    return {"colunas": cabecalho_csv(f"{TSE}/consulta_cand/rede_social_candidato_2024.zip")}


# ---------------------------------------------------------------- Câmara de Goiânia (HTML)

def _go_pagina(ctx):
    import coletar_prefeitura_go as go
    go.confiar()
    total, itens = go.pagina(ANO, 1)
    return {"total": total, "itens": itens[:AMOSTRA]}


def _go_conferir(registro):
    falhas, avisos = [], []
    if not registro["total"]:
        falhas.append("página do SUAP sem 'Total de N itens'")
    if not registro["itens"]:
        falhas.append("nenhum processo reconhecido na página do SUAP")
    for i in registro["itens"]:
        avisos.extend(f"processo sem {c}" for c in ("uuid", "assunto", "interessados", "criado", "situacao") if not i.get(c))
    return falhas, avisos


ENDPOINTS.append(Endpoint("go_suap", "https://suap.camaragyn.go.gov.br/camara/consulta_publica/", _go_pagina, html=_go_conferir))


# ---------------------------------------------------------------- Assembleias fora do SAPL (um módulo por UF)

def registrar_estaduais(pasta: Path = Path(__file__).resolve().parent) -> None:
    """Acrescenta os CONTRATOS de cada scripts/coletar_estadual_<uf>.py; módulo que não importa é ignorado com aviso."""
    for arq in sorted(pasta.glob("coletar_estadual_*.py")):
        try:
            modulo = importlib.import_module(arq.stem)
            novos = [Endpoint(**{**d, "independente": True}) for d in getattr(modulo, "CONTRATOS", [])]
        except Exception as e:
            print(f"aviso: {arq.stem}: contratos não carregados ({e})", file=sys.stderr)
            continue
        ENDPOINTS.extend(novos)


registrar_estaduais()


# ---------------------------------------------------------------- gravar e verificar

def caminho(nome: str) -> Path:
    return FIXTURES / f"{nome}.json"


def executar(selecionados: list[str], acao):
    ctx: dict = {}
    nomes = set(selecionados)
    saida = {}
    for e in ENDPOINTS:
        independente = bool(e.independente or e.colunas_criticas or e.colunas_esperadas or e.html)   # não usam o que os anteriores devolveram
        if nomes and e.nome not in nomes and independente:
            continue
        try:
            resp = e.buscar(ctx)
        except Exception as ex:
            if not nomes or e.nome in nomes:   # falha de quem só serve de ponte para o contexto não conta
                saida[e.nome] = (e, None, f"{type(ex).__name__}: {str(ex)[:160]}")
            continue
        if not nomes or e.nome in nomes:
            saida[e.nome] = (e, resp, None)
    return saida


def montar_registro(e: Endpoint, resp) -> dict:
    base = {"fonte": e.fonte, "capturadoEm": HOJE.isoformat()}
    if e.colunas_criticas or e.colunas_esperadas:
        return {**base, "colunas": resp["colunas"]}
    if e.html:
        return {**base, "amostra": resp}
    amostra = reduzir(resp)
    return {**base, "amostra": amostra, "forma": forma(amostra)}


def gravar(selecionados: list[str]) -> int:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    problemas = 0
    for nome, (e, resp, erro) in executar(selecionados, "gravar").items():
        if erro:
            print(f"✗ {nome}: não gravado ({erro})")
            problemas += 1
            continue
        reg = montar_registro(e, resp)
        if "forma" in reg:
            for u in e.usados:
                if not casa(u, reg["forma"]) and not sem_amostra(u, reg["forma"]) and not u.startswith("**"):
                    print(f"  ! {nome}: campo usado {u} não aparece na amostra")
        caminho(nome).write_text(json.dumps(reg, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"✓ {nome}")
    return 1 if problemas else 0


def verificar(selecionados: list[str]) -> int:
    linhas, falhou = [], False
    for nome, (e, resp, erro) in executar(selecionados, "verificar").items():
        arq = caminho(nome)
        if erro and e.html:
            linhas.append((nome, "aviso", [f"fonte indisponível: {erro}"]))
            continue
        if erro:
            linhas.append((nome, "aviso", [f"fonte indisponível ou resposta inesperada: {erro}"]))
            continue
        if e.html:
            falhas, avisos = e.html(resp)
            if falhas:
                falhou = True
            linhas.append((nome, "falha" if falhas else "ok" if not avisos else "aviso", falhas + avisos))
            continue
        if not arq.exists():
            linhas.append((nome, "aviso", ["sem fixture gravada (rode --gravar)"]))
            continue
        gravado = json.loads(arq.read_text(encoding="utf-8"))
        if "colunas" in gravado:
            falhas, avisos = comparar_colunas(gravado["colunas"], resp["colunas"], e.colunas_criticas, e.colunas_esperadas)
        else:
            falhas, avisos = comparar(gravado["forma"], forma(reduzir(resp)), e.usados)
            avisos = descontinuacao(resp) + avisos
        if falhas:
            falhou = True
            linhas.append((nome, "falha", falhas + avisos))
        else:
            linhas.append((nome, "ok" if not avisos else "aviso", avisos))
    resumo = ["## Contrato das APIs externas", ""]
    for nome, estado, itens in linhas:
        icone = {"ok": "✅", "aviso": "⚠️", "falha": "❌"}[estado]
        resumo.append(f"- {icone} **{nome}**" + ("" if not itens else ":"))
        resumo += [f"  - {i}" for i in itens]
    texto = "\n".join(resumo)
    print(texto)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(texto + "\n")
    if os.environ.get("RESUMO_ARQUIVO"):
        Path(os.environ["RESUMO_ARQUIVO"]).write_text(texto + "\n", encoding="utf-8")
    return 1 if falhou else 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--gravar", action="store_true")
    g.add_argument("--verificar", action="store_true")
    g.add_argument("--listar", action="store_true")
    p.add_argument("nomes", nargs="*")
    a = p.parse_args()
    desconhecidos = set(a.nomes) - {e.nome for e in ENDPOINTS}
    if desconhecidos:
        sys.exit(f"Desconhecidos: {sorted(desconhecidos)}")
    if a.listar:
        for e in ENDPOINTS:
            print(f"{e.nome:24} {e.fonte}")
        return 0
    return gravar(a.nomes) if a.gravar else verificar(a.nomes)


if __name__ == "__main__":
    sys.exit(main())
