"""
Deputados estaduais de São Paulo (Alesp), fora do SAPL.

Fontes lidas aqui (abertas, sem login nem captcha):
  - dados abertos (XML em https://www.al.sp.gov.br/repositorioDados/, catálogo em https://www.al.sp.gov.br/dados-abertos/):
    deputados/deputados.xml (94 em exercício), deputados/despesas_gabinetes_<ano>.xml (verba de gabinete com CNPJ),
    processo_legislativo/proposituras.zip + documento_autor.zip (autoria; só PL, PLC, PR, PDL, PEC e P. Const.)
  - API do portal https://legis-api-portal-prd.al.sp.gov.br: /parlamentar-portal (foto) e /lista-presenca-parlamentar/<matrícula>/<mês>/<ano>
  - subsídio mensal por nome civil: https://www.al.sp.gov.br/repositorio/folha-de-pagamento/folha-deputados-<ano>-<mês>.html

  - normas com autoria: /processo?transformadoNorma=true (PL, PLC, PR, PDL, PEC) e /processo/detalhes/todos/<sigla>/<ano>/<número> (urlNorma, autores com matrícula)
  - pautas e atas: /sessoes-plenarias/consulta, /sessoes-plenarias/<id>/{pauta,ordem-do-dia,integra} e /colegiado/reunioes (documentosReuniao)
  - contratos e atas de registro de preço do órgão: HTML https://www.al.sp.gov.br/alesp/contratos/ e detalhe (CNPJ, valor, vigência)
  - regras da verba: links dos textos legais citados em https://www.al.sp.gov.br/deputado/contas/

Não coletado: gabinete (funcionarios_lotacoes.xml parado em 05/2023, sem lotação atual); voto nominal de plenário e diárias (não publicados);
convênios e aditamentos da página de contratos; XML legislacao_normas.zip (sem autoria); requerimentos, indicações e moções (79 mil documentos desde 2023, só volume); votações nominais do plenário
(só PDF por sessão em /sessao-plenaria/?tab=votacoes); votos em comissões (comissoes_permanentes_votacoes.xml: voto em parecer,
fora do contrato); diárias e emendas (sem fonte localizada).
"""

import html as html_lib
import io
import re
import time
from defusedxml import ElementTree as ET
import zipfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import zlib
from datetime import date, timedelta
from functools import partial
from urllib.parse import quote

import estaduais_comum as comum
import identidades

UF = "SP"
SITE = "https://www.al.sp.gov.br"
REPOSITORIO = f"{SITE}/repositorioDados"
API = "https://legis-api-portal-prd.al.sp.gov.br"
DADOS_ABERTOS = f"{SITE}/dados-abertos/"
DEPUTADOS_XML = f"{REPOSITORIO}/deputados/deputados.xml"
DEPUTADOS_PAGINA = f"{SITE}/deputado/lista/"
PARLAMENTARES_API = f"{API}/parlamentar-portal"
DESPESAS_PAGINA = f"{SITE}/deputado/contas/"
FOLHA_INDICE = f"{SITE}/alesp/folha-de-pagamento-deputados/"
FOLHA = f"{SITE}/repositorio/folha-de-pagamento/folha-deputados-{{ano}}-{{mes:02d}}.html"
PRESENCA_PAGINA = f"{SITE}/deputado/presenca-plenario"
PROPOSITURAS_ZIP = f"{REPOSITORIO}/processo_legislativo/proposituras.zip"
AUTORES_ZIP = f"{REPOSITORIO}/processo_legislativo/documento_autor.zip"
PROPOSITURA_PAGINA = f"{SITE}/propositura/?id={{id}}"
LEGISLATURA = 20
PRIMEIRO_ANO = 2023
LIMITE_EMENTA = 400
PAUSA = 0.1
PASTA = comum.DADOS / UF
TAMANHO_PAGINA = 300
TIPOS_NORMA = (1, 2, 3, 4, 5)   # PL, PLC, PR, PDL, PEC: listaIdTipoProcesso da API do portal
DOCUMENTOS_COMISSAO = {"Pauta de colegiado": "ordem-do-dia", "Ata de Reunião de Comissão": "atas"}
CONTRATOS_PAGINA = f"{SITE}/alesp/contratos/"
DETALHE_CONTRATO = f"{SITE}/alesp/contratos/detalhe/?detContrato={{hash}}"
FONTE_ID = "alesp_contratos"
RELER_SESSOES_DIAS = 30   # pauta e ata de sessão mais nova que isso (ou futura) é lida de novo: a Mesa publica a íntegra depois
RELER_FALHA_DIAS = 7      # sessão cuja leitura deu erro só é tentada de novo depois disso
RELER_CONTRATO_DIAS = 14  # contrato do ano corrente e do anterior é relido a cada 14 a 27 dias (escalonado), para pegar vigência e valor novos
NATUREZAS = {"1": ("PL", "Projeto de lei"), "2": ("PLC", "Projeto de lei complementar"), "3": ("PR", "Projeto de resolução"),
             "4": ("PDL", "Projeto de decreto legislativo"), "5": ("PEC", "Proposta de emenda à Constituição"),
             "10": ("PCONST", "Projeto de Constituição")}
SITUACAO_PRESENCA = {"presente": 0, "nao justificada": 2, "ausencia em sessao extraordinaria": 2}


baixar = partial(comum.baixar, timeout=300)


# ---------------------------------------------------------------- deputados

def parse_deputados(xml: bytes) -> list[dict]:
    achados = []
    for d in ET.fromstring(xml).iter("Deputado"):
        if d.findtext("Situacao") != "EXE" or not d.findtext("Matricula"):
            continue
        matricula = d.findtext("Matricula").strip()
        achados.append({"id": matricula, "nome": " ".join((d.findtext("NomeParlamentar") or "").split()), "nomeCivil": None, "foto": None,
                        "email": comum.email(d.findtext("Email")), "titular": True, "partido": comum.sigla_partido(d.findtext("Partido")),
                        "fonte": f"{SITE}/deputado/?matricula={matricula}", "idAutor": (d.findtext("IdSPL") or "").strip() or None})
    return achados


def fotos(parlamentares: list[dict]) -> dict:
    """{matrícula: URL da foto}; o portal monta a URL com o caminho que a API devolve."""
    return {str(p["nuMatricula"]): "https://www3.al.sp.gov.br/legis/" + p["txFoto"].lstrip("/") for p in parlamentares if p.get("txFoto")}


ligar_civis = partial(identidades.ligar_civis, uf=UF)
ligar_civis_pelo_tse = partial(identidades.ligar_civis_pelo_tse, uf=UF)


# ---------------------------------------------------------------- proposituras

def ler_proposituras(zip_bytes: bytes, primeiro_ano: int) -> dict:
    achadas = {}
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z, z.open(z.namelist()[0]) as f:
        for _, el in ET.iterparse(f):
            if el.tag == "propositura":
                natureza = (el.findtext("IdNatureza") or "").strip()
                ano = int(el.findtext("AnoLegislativo") or 0)
                if natureza in NATUREZAS and ano >= primeiro_ano:
                    achadas[(el.findtext("IdDocumento") or "").strip()] = {
                        "natureza": natureza, "ano": ano, "numero": (el.findtext("NroLegislativo") or "").strip(),
                        "ementa": " ".join((el.findtext("Ementa") or "").split()), "data": comum.data_iso(el.findtext("DtPublicacao"))}
                el.clear()
    return achadas


def ler_autores(zip_bytes: bytes, documentos) -> dict:
    autores = defaultdict(set)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z, z.open(z.namelist()[0]) as f:
        for _, el in ET.iterparse(f):
            if el.tag == "DocumentoAutor":
                doc = (el.findtext("IdDocumento") or "").strip()
                if doc in documentos:
                    autores[doc].add(((el.findtext("IdAutor") or "").strip(), " ".join((el.findtext("NomeAutor") or "").split())))
                el.clear()
    return autores


def materias_por_ano(proposituras: dict, autores: dict, deputados: list[dict]) -> dict:
    """{ano: {id: matéria}}, só com autores que são deputados em exercício (pelo IdAutor ou, sem ele, pelo nome)."""
    por_autor = {d["idAutor"]: d["id"] for d in deputados if d.get("idAutor")}
    nomes = {n for v in autores.values() for i, n in v if i not in por_autor}
    por_nome = identidades.ligar_nomes(nomes, deputados, UF)
    anos: dict = defaultdict(dict)
    for doc, p in proposituras.items():
        ids = sorted({por_autor.get(i) or por_nome.get(n) for i, n in autores.get(doc, ()) if por_autor.get(i) or por_nome.get(n)})
        if not ids:
            continue
        ementa = p["ementa"]
        if len(ementa) > LIMITE_EMENTA:
            ementa = ementa[:LIMITE_EMENTA].rsplit(" ", 1)[0] + "..."
        sigla, descricao = NATUREZAS[p["natureza"]]
        url = PROPOSITURA_PAGINA.format(id=doc)
        anos[p["ano"]][doc] = {"tipo": sigla, "tipoDescricao": descricao, "numero": int(p["numero"]) if p["numero"].isdigit() else None,
                               "ano": p["ano"], "dataApresentacao": p["data"], "ementa": ementa, "situacao": None, "emTramitacao": None,
                               "linkTexto": url, "idsAutores": ids, "idsDeputados": ids, "fonte": url}
    return anos


# ---------------------------------------------------------------- verba de gabinete

def itens_verba(xml: bytes, ids_por_matricula: dict) -> list[dict]:
    itens = []
    for d in ET.fromstring(xml).iter("despesa"):
        id_dep = ids_por_matricula.get((d.findtext("Matricula") or "").strip())
        if not id_dep:
            continue
        itens.append({"idDeputado": id_dep, "mes": int(d.findtext("Mes")), "categoria": (d.findtext("Tipo") or "").strip() or None,
                      **comum.fornecedor(d.findtext("Fornecedor"), d.findtext("CNPJ")),
                      "valor": comum.valor_br(d.findtext("Valor")), "fonte": DESPESAS_PAGINA})
    return sorted(itens, key=lambda i: (i["mes"], i["idDeputado"], i["categoria"] or "", i["fornecedor"] or "", i["valor"] or 0))


# ---------------------------------------------------------------- subsídio

def parse_folha(texto: str) -> list[dict]:
    achados = []
    for linha in re.findall(r"<tr>(.*?)</tr>", texto, re.S):
        celulas = [html_lib.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", linha, re.S)]
        if len(celulas) == 4 and celulas[0] and comum.valor_br(celulas[1]) is not None:
            achados.append({"nome": " ".join(celulas[0].split()), "bruto": comum.valor_br(celulas[1]), "tributos": comum.valor_br(celulas[2]),
                            "liquido": comum.valor_br(celulas[3])})
    return achados


def meses_da_folha(indice: str) -> list[tuple[int, int]]:
    return sorted({(int(a), int(m)) for a, m in re.findall(r"folha-deputados-(\d{4})-(\d{2})\.html", indice)})


def itens_folha(linhas: list[dict], ligados: dict, ano: int, mes: int) -> list[dict]:
    url = FOLHA.format(ano=ano, mes=mes)
    return [{"idDeputado": ligados[lin["nome"]], "mes": mes, "bruto": lin["bruto"], "liquido": lin["liquido"],
             "componentes": {"Tributos": lin["tributos"]}, "fonte": url} for lin in linhas if lin["nome"] in ligados]


# ---------------------------------------------------------------- presença

def contar_presenca(registros: list[dict]) -> list[int]:
    """[presente, licenca, ausente] de uma lista de /lista-presenca-parlamentar. Sessão sem deliberação não tem presença;
    "Justificada", licenças, afastamentos e serviço à Casa entram como licença."""
    conta = [0, 0, 0]
    for r in registros:
        situacao = comum.sem_acento(r.get("situacao"))
        if situacao.startswith("sessao nao deliberativa"):
            continue
        conta[SITUACAO_PRESENCA.get(situacao, 1)] += 1
    return conta


def itens_presenca(por_mes: dict) -> list[dict]:
    """`por_mes` {(id, "AAAA-MM"): [presente, licenca, ausente]} -> itens por mês e por ano."""
    somas: dict = defaultdict(lambda: [0, 0, 0])
    itens = []
    for (i, periodo), c in sorted(por_mes.items()):
        itens.append({"idDeputado": i, "periodo": periodo, "presente": c[0], "ausente": c[2], "licenca": c[1], "totalSessoes": sum(c),
                      "fonte": PRESENCA_PAGINA})
        for k in range(3):
            somas[(i, periodo[:4])][k] += c[k]
    for (i, ano), c in sorted(somas.items()):
        itens.append({"idDeputado": i, "periodo": ano, "presente": c[0], "ausente": c[2], "licenca": c[1], "totalSessoes": sum(c),
                      "fonte": PRESENCA_PAGINA})
    return itens


def presenca_do_mes(sessao, matricula: str, mes: int, ano: int) -> list[dict]:
    r = sessao.get(f"{API}/lista-presenca-parlamentar/{matricula}/{mes}/{ano}", timeout=60)
    r.raise_for_status()
    time.sleep(PAUSA)
    return r.json()


def presenca_do_ano(sessao, deputados: list[dict], ano: int, existentes: list[dict], hoje: date) -> list[dict]:
    ultimo = hoje.month if ano == hoje.year else 12
    guardados = {(i["idDeputado"], i["periodo"]): [i["presente"], i["licenca"], i["ausente"]] for i in existentes if len(i["periodo"]) == 7}
    refazer = {f"{ano}-{m:02d}" for m in range(max(1, ultimo - 1), ultimo + 1)}
    pendentes = [(d["id"], f"{ano}-{m:02d}") for d in deputados for m in range(1, ultimo + 1)
                 if (d["id"], f"{ano}-{m:02d}") not in guardados or f"{ano}-{m:02d}" in refazer]

    def um(par):
        id_dep, periodo = par
        return par, contar_presenca(presenca_do_mes(sessao, id_dep, int(periodo[5:]), ano))

    with ThreadPoolExecutor(max_workers=2) as pool:
        guardados.update(pool.map(um, pendentes))
    return itens_presenca({k: v for k, v in guardados.items() if k[1][:4] == str(ano) and sum(v)})


# ---------------------------------------------------------------- normas legais com autoria

def pegar_json(s, caminho: str, **params):
    """GET na API do portal; 404 e corpo vazio viram None."""
    r = s.get(f"{API}{caminho}", params=params or None, timeout=60)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    time.sleep(PAUSA)
    return r.json() if r.content.strip() else None


def paginas(s, caminho: str, **params):
    pagina = 0
    while True:
        d = pegar_json(s, caminho, page=pagina, size=TAMANHO_PAGINA, **params) or {}
        yield from d.get("content") or []
        pagina += 1
        if d.get("last", True) or pagina >= d.get("totalPages", 0):
            return


def curta(texto, limite: int = LIMITE_EMENTA) -> str | None:
    t = " ".join((texto or "").split())
    return (t if len(t) <= limite else t[:limite].rsplit(" ", 1)[0] + "...") or None


def precisa_do_detalhe(p: dict, matriculas: set) -> bool:
    """A listagem só traz o autor principal: projeto de vários autores ou de deputado em exercício tem os autores lidos no detalhe."""
    return p.get("tipoAutorPrincipal") == "varios" or str(p.get("numeroAutorPrincipal")) in matriculas


def norma_do_detalhe(d: dict, matriculas: set) -> tuple[str, dict] | None:
    """(id da norma no portal, norma) de um projeto que virou norma, com os deputados em exercício entre os autores (pela matrícula);
    None se não virou norma ou nenhum autor é deputado em exercício."""
    ids = sorted({str(a["matricula"]) for a in d.get("autores") or [] if str(a.get("matricula")) in matriculas})
    m = re.match(r"\s*(.+?)\s+n[ºo°]\s*([\d.]+),\s*de\s*(\d\d/\d\d/\d{4})", d.get("descricaoNorma") or "")
    achado = re.fullmatch(r"/norma/(\d+)", d.get("urlNorma") or "")
    if not (d.get("transformadoNorma") and ids and m and achado):
        return None
    data = comum.data_br_iso(m[3])
    return achado[1], {"tipo": m[1], "numero": int(m[2].replace(".", "")), "ano": int(data[:4]) if data else None, "data": data,
                       "ementa": curta(d.get("resumo")), "situacao": None, "idsDeputados": ids, "fonte": f"{SITE}{achado[0]}",
                       "projeto": d.get("descricao"), "linkProjeto": f"{SITE}/propositura/?id={d['idProcesso']}"}


def normas_candidatas(s, matriculas: set, anos) -> dict:
    """{idProcesso: item da listagem} dos projetos que viraram norma (PL, PLC, PR, PDL, PEC de cada ano) e interessam a algum deputado."""
    achadas = {}
    for ano in anos:
        for tipo in TIPOS_NORMA:
            for p in paginas(s, "/processo", listaIdTipoProcesso=tipo, transformadoNorma="true", ano=ano):
                if precisa_do_detalhe(p, matriculas):
                    achadas[p["idProcesso"]] = p
    return achadas


def coletar_normas(s, deputados: list[dict], hoje: date) -> None:
    matriculas = {d["id"] for d in deputados}
    agora = hoje.isoformat()
    arq = PASTA / "normas_vistas.json"
    vistos = comum.ler(arq, {}).get("processos") or {}
    anos = {a: comum.ler(PASTA / f"normas_{a}.json", {}).get("normas") or {} for a in range(PRIMEIRO_ANO, hoje.year + 1)}
    candidatas = normas_candidatas(s, matriculas, range(PRIMEIRO_ANO, hoje.year + 1))
    fila = [p for pid, p in sorted(candidatas.items(), reverse=True) if str(pid) not in vistos]
    novas = 0
    falhas = []

    def gravar():
        for ano, normas in anos.items():
            if normas or (PASTA / f"normas_{ano}.json").exists():
                comum.salvar(PASTA / f"normas_{ano}.json", {"coletadoEm": agora, "fonte": f"{SITE}/norma/pesquisa", "normas": normas})
        comum.salvar(arq, {"coletadoEm": agora, "processos": vistos})

    def um(p):
        try:
            return p, pegar_json(s, f"/processo/detalhes/todos/{p['tipoProcesso']}/{p['anoTipo']}/{p['numeroTipo']}")
        except comum.PrazoEsgotado:
            raise
        except Exception:
            return p, False

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            for n, (p, d) in enumerate(pool.map(um, fila), 1):
                if d is False:
                    falhas.append(p["idProcesso"])
                    continue
                achada = norma_do_detalhe(d, matriculas) if d else None
                vistos[str(p["idProcesso"])] = agora
                if achada:
                    nid, norma = achada
                    for lote in anos.values():
                        lote.pop(nid, None)
                    anos.setdefault(norma["ano"] or hoje.year, {})[nid] = norma
                    novas += 1
                if n % 100 == 0:
                    gravar()
                    print(f"SP: normas {n}/{len(fila)} projetos lidos", flush=True)
    finally:
        gravar()
    print(f"SP: {sum(len(n) for n in anos.values())} normas de autoria de deputado ({novas} novas; {len(fila)} projetos lidos de {len(candidatas)} candidatos)")
    if falhas:
        comum.avisar(f"SP: a API respondeu erro no detalhe de {len(falhas)} projetos (tentados de novo na próxima coleta)")


# ---------------------------------------------------------------- pautas e atas (plenário e comissões)

def como_lista(x) -> list:
    return x if isinstance(x, list) else [x] if x else []


def item_pauta(sessao: dict, pautas: list[dict], ordens: list[dict]) -> dict | None:
    arquivos = [{"nome": comum.compactar(p.get("titulo")) or "Pauta da sessão", "url": p["urlDocumento"]} for p in pautas if p.get("urlDocumento")]
    arquivos += [{"nome": comum.compactar(o.get("txTitulo")) or "Ordem do dia", "url": o["urlDocumento"]} for o in ordens if o.get("urlDocumento")]
    if not arquivos:
        return None
    return {"id": str(sessao["id"]), "reuniao": f"s{sessao['id']}", "origem": "plenario", "tipo": "ordem-do-dia", "titulo": sessao["titulo"],
            "data": comum.data_iso(sessao["dtInicio"]), "arquivos": arquivos, "fonte": arquivos[0]["url"]}


def item_ata(sessao: dict, integra: dict | None) -> dict | None:
    if not integra or not integra.get("urlIntegra"):
        return None
    arquivos = [{"nome": comum.compactar(integra.get("tituloIntegra")) or "Íntegra da sessão", "url": integra["urlIntegra"]}]
    if integra.get("urlIntegraDO"):
        arquivos.append({"nome": "Íntegra no Diário Oficial", "url": integra["urlIntegraDO"]})
    return {"id": str(sessao["id"]), "reuniao": f"s{sessao['id']}", "origem": "plenario", "tipo": "atas", "titulo": sessao["titulo"],
            "data": comum.data_iso(sessao["dtInicio"]), "arquivos": arquivos, "fonte": integra["urlIntegra"]}


def ler_sessao(s, sessao: dict) -> list[dict]:
    """Pauta, ordem do dia e íntegra (ata) de uma sessão plenária; só pede o que os indicadores da consulta dizem que existe."""
    base = f"/sessoes-plenarias/{sessao['id']}"
    pautas = como_lista(pegar_json(s, f"{base}/pauta")) if sessao.get("temPauta") else []
    ordens = como_lista(pegar_json(s, f"{base}/ordem-do-dia")) if sessao.get("temOrdemDoDia") else []
    integra = pegar_json(s, f"{base}/integra") if sessao.get("temIntegra") else None
    return [i for i in (item_pauta(sessao, pautas, ordens), item_ata(sessao, integra)) if i]


def itens_comissoes(reunioes: list[dict]) -> list[dict]:
    """Pauta e ata de reuniões de comissão: um item por documento que tem arquivo publicado."""
    achados = []
    for r in reunioes:
        colegiados = ", ".join(c.get("sigla") or c.get("nome") or "" for c in r.get("colegiadosRelacionados") or []).strip(", ")
        for d in r.get("documentosReuniao") or []:
            tipo = DOCUMENTOS_COMISSAO.get(d.get("tipo"))
            url = d.get("linkArquivo") or d.get("linkArquivoPDF")
            if not (tipo and url and r.get("dtReuniao")):
                continue
            nome = comum.compactar(d.get("descricao")) or d["tipo"]
            achados.append({"id": str(d["idDocumento"]), "reuniao": f"c{r['idReuniao']}", "origem": "comissao", "tipo": tipo,
                            "titulo": comum.compactar(f"{colegiados} - {r.get('tituloReuniao') or 'Reunião'} nº {r.get('nuReuniao') or ''}"),
                            "data": comum.data_iso(r["dtReuniao"]), "arquivos": [{"nome": nome, "url": url}], "fonte": url,
                            "situacao": (r.get("status") or {}).get("txNome")})
    return achados


def coletar_pautas_atas(s, hoje: date) -> None:
    agora = hoje.isoformat()
    estado = {}
    for ano in range(PRIMEIRO_ANO, hoje.year + 1):
        arq = PASTA / f"pautas_{ano}.json"
        e = comum.ler(arq, {})
        e.setdefault("itens", {})
        e.setdefault("lidas", {})
        e.setdefault("falhas", {})
        e["_novo"] = not comum.ano_encerrado(ano, hoje, arq)
        estado[ano] = e
    recentes = (hoje - timedelta(days=RELER_SESSOES_DIAS)).isoformat()
    recentes_falha = (hoje - timedelta(days=RELER_FALHA_DIAS)).isoformat()
    pendentes = []
    for ano, e in estado.items():
        if not e["_novo"]:
            continue
        try:
            sessoes = list(paginas(s, "/sessoes-plenarias/consulta", ano=ano))
        except comum.PrazoEsgotado:
            raise
        except Exception as ex:
            comum.avisar(f"SP: lista de sessões plenárias {ano}: {ex}")
            continue
        pendentes += [(ano, x) for x in sessoes if x.get("dtInicio") and (str(x["id"]) not in e["lidas"] or (comum.data_iso(x["dtInicio"]) or "") >= recentes)
                      and e["falhas"].get(str(x["id"]), "") <= recentes_falha]
    lidas = 0

    def uma(par):
        ano, x = par
        try:
            return ano, x, ler_sessao(s, x)
        except comum.PrazoEsgotado:
            raise
        except Exception:
            return ano, x, None

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            for ano, x, itens in pool.map(uma, sorted(pendentes, key=lambda p: p[1]["dtInicio"], reverse=True)):
                e, rid = estado[ano], str(x["id"])
                if itens is None:
                    e["falhas"][rid] = agora
                    continue
                e["itens"] = {k: v for k, v in e["itens"].items() if v.get("reuniao") != f"s{x['id']}"}
                e["itens"].update({f"{i['tipo']}|{i['id']}": i for i in itens})
                e["lidas"][rid] = agora
                e["falhas"].pop(rid, None)
                lidas += 1
        for ano, e in estado.items():
            if not e["_novo"]:
                continue
            reunioes = list(paginas(s, "/colegiado/reunioes", ano=ano))
            e["itens"] = {k: v for k, v in e["itens"].items() if v.get("origem") != "comissao"}
            e["itens"].update({f"{i['tipo']}|{i['id']}": i for i in itens_comissoes(reunioes)})
    finally:
        for ano, e in estado.items():
            if e["_novo"] or e["itens"]:
                comum.salvar(PASTA / f"pautas_{ano}.json", {"coletadoEm": agora, "fonte": f"{SITE}/sessao-plenaria/", "itens": e["itens"],
                                                           "lidas": e["lidas"], "falhas": e["falhas"]})
    contagem = {}
    for e in estado.values():
        for i in e["itens"].values():
            contagem[(i["origem"], i["tipo"])] = contagem.get((i["origem"], i["tipo"]), 0) + 1
    print(f"SP: pautas e atas {sum(contagem.values())} ({', '.join(f'{o} {t} {n}' for (o, t), n in sorted(contagem.items()))}); {lidas} sessões lidas agora")
    falhas = sum(len(e["falhas"]) for e in estado.values())
    if falhas:
        comum.avisar(f"SP: pauta ou ata de {falhas} sessões plenárias respondeu erro; tentadas de novo em {RELER_FALHA_DIAS} dias")


# ---------------------------------------------------------------- contratos e atas de registro de preço do órgão

def texto_html(fragmento: str) -> str:
    return " ".join(html_lib.unescape(re.sub(r"<[^>]+>", " ", fragmento)).split())


def url_arquivo(url: str) -> str:
    return quote(html_lib.unescape(url).strip(), safe=":/%?=&")


def parse_listagem(pagina: str) -> list[dict]:
    """Contratos, atas de registro de preço e dispensas da página /alesp/contratos/ (convênios e outros ficam de fora: sem CNPJ nem valor).
    Cada item: hash do detalhe, processo (número e ano), modalidade, objeto, PDF, encerrado e aditamentos."""
    marcas = [(m.start(), m.group(1), bool(m.group(2))) for m in re.finditer(r'<div class="modulo_(contratos|atas|dispensas)(_encerrado)?"', pagina)]
    fins = [m.start() for m in re.finditer(r'<div id="(?:bloco(?:Autorizacoes|Convenio|ContratoEncerrado)|mapa)"', pagina)]
    achados = []
    for k, (ini, modulo, encerrado) in enumerate(marcas):
        limites = fins + [m[0] for m in marcas[k + 1:k + 2]]
        fim = min([f for f in limites if f > ini] or [len(pagina)])
        for cartao in pagina[ini:fim].split('<li class="card"')[1:]:
            hashes = re.findall(r"detContrato=([0-9a-f]{32})", cartao)
            m = re.search(r"<strong>\s*Processo Digital\s+(\d+)\s*/\s*(\d{4})\s*</strong>", cartao)
            if not (hashes and m):
                continue
            badge = re.search(r'<b class="badge[^"]*">(.*?)</b>', cartao, re.S)
            objeto = re.search(r'<i style="color: #666">(.*?)</i>', cartao, re.S)
            pdfs = re.findall(r'href="([^"]+\.pdf)"', cartao, re.I)
            achados.append({"hash": hashes[0], "numero": int(m[1]), "ano": int(m[2]), "modulo": modulo, "encerrado": encerrado,
                            "modalidade": texto_html(badge[1]) if badge else None, "objeto": texto_html(objeto[1]) if objeto else None,
                            "pdf": url_arquivo(pdfs[0]) if pdfs else None, "aditamentos": len(set(hashes[1:]))})
    return achados


def parse_detalhe(pagina: str) -> dict:
    """Campos da tabela "Contrato" do detalhe (rótulo sem acento -> texto) e links dos documentos; a tabela "Informações Financeiras" não é lida."""
    tabela = pagina.split("Informa&ccedil;&otilde;es Financeiras")[0].split("Informações Financeiras")[0]
    campos, docs = {}, []
    for linha in re.findall(r"<tr>(.*?)</tr>", tabela, re.S | re.I):
        celulas = re.findall(r"<td[^>]*>(.*?)</td>", linha, re.S | re.I)
        if len(celulas) == 2:
            rotulo = comum.sem_acento(texto_html(celulas[0])).upper()
            campos[rotulo] = texto_html(celulas[1])
            if rotulo == "DOCUMENTOS":
                docs = [url_arquivo(u) for u in re.findall(r'href="([^"]+)"', celulas[1])]
    return {"campos": campos, "documentos": docs}


def separar_contratada(texto: str | None) -> tuple[str | None, str | None]:
    """"MADARP NEGÓCIOS E SOLUÇÕES LTDA. - 54.456.948/0001-85" -> (nome, documento)."""
    m = re.fullmatch(r"(.*?)\s+-\s+([\d./-]{11,18})", texto or "")
    return (m[1], m[2]) if m else (texto or None, None)


def item_contrato(lista: dict, detalhe: dict) -> tuple[str, dict]:
    """(id, item) no formato de `comum.item_orgao`. Id de (fonte, tipo, hash do detalhe, que a Alesp publica na própria URL)."""
    c = detalhe["campos"]
    nome, doc = separar_contratada(c.get("CONTRATADA"))
    vigencia = re.search(r"de\s+(\d\d/\d\d/\d{4})\s+a\s+(\d\d/\d\d/\d{4})", c.get("VIGENCIA") or "")
    tipo = "ata_registro" if lista["modulo"] == "atas" else "contrato"
    pdfs = detalhe["documentos"] or ([lista["pdf"]] if lista["pdf"] else [])
    rotulo = "Ata de registro de preços (PDF)" if tipo == "ata_registro" else "Contrato (PDF)"
    return comum.item_orgao(
        FONTE_ID, tipo, lista["hash"], fornecedor_nome=nome, documento=doc, valor=c.get("VALOR TOTAL"),
        inicio=comum.data_br_iso(vigencia[1]) if vigencia else None, fim=comum.data_br_iso(vigencia[2]) if vigencia else None,
        objeto=c.get("OBJETO") or lista["objeto"], numero=f"{lista['numero']}/{lista['ano']}",
        arquivos=[{"url": u, "nome": rotulo, "data": None} for u in pdfs], fonte=DETALHE_CONTRATO.format(hash=lista["hash"]),
        processo=f"{lista['numero']}/{lista['ano']}", modalidade=c.get("MODALIDADE") or lista["modalidade"],
        assinatura=comum.data_br_iso(c.get("ASSINATURA")), empenho=c.get("NO. DO EMPENHO") or None,
        encerrado=lista["encerrado"], aditamentos=lista["aditamentos"])


def devido_contrato(lido: str, chave: str, hoje: date) -> bool:
    return (hoje - date.fromisoformat(lido)).days >= RELER_CONTRATO_DIAS + zlib.crc32(chave.encode()) % RELER_CONTRATO_DIAS


def coletar_contratos(s, hoje: date) -> None:
    agora = hoje.isoformat()
    lista = [x for x in parse_listagem(baixar(s, CONTRATOS_PAGINA).decode("latin-1")) if x["ano"] >= PRIMEIRO_ANO]
    if not lista:
        raise RuntimeError("página de contratos sem nenhum item; mantém os arquivos anteriores")
    estado = {}
    for ano in range(PRIMEIRO_ANO, hoje.year + 1):
        e = comum.ler(PASTA / f"orgao_{ano}.json", {})
        e.setdefault("itens", {})
        e.setdefault("lidos", {})
        estado[ano] = e
    guardados = {i["idFonte"]: i for e in estado.values() for i in e["itens"].values()}

    def pendente(x):
        antigo = guardados.get(x["hash"])
        if antigo is None:
            return True
        lido = estado[x["ano"]]["lidos"].get(x["hash"], "2000-01-01")
        if x["ano"] >= hoje.year - 1 and devido_contrato(lido, x["hash"], hoje):
            return True
        return antigo.get("encerrado") != x["encerrado"] or antigo.get("aditamentos") != x["aditamentos"]

    fila = sorted((x for x in lista if x["ano"] in estado and pendente(x)), key=lambda x: (x["ano"], x["numero"]), reverse=True)
    falhas = []

    def um(x):
        try:
            r = s.get(DETALHE_CONTRATO.format(hash=x["hash"]), timeout=60)
            r.raise_for_status()
            time.sleep(PAUSA)
            return x, parse_detalhe(r.content.decode("latin-1"))
        except comum.PrazoEsgotado:
            raise
        except Exception:
            return x, None

    lidos = vazios = 0
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            for x, detalhe in pool.map(um, fila):
                if detalhe is None:
                    falhas.append(x["hash"])
                    continue
                if not detalhe["campos"]:
                    vazios += 1
                iid, item = item_contrato(x, detalhe)
                e = estado[x["ano"]]
                e["itens"] = {k: v for k, v in e["itens"].items() if v["idFonte"] != x["hash"]}
                e["itens"][iid] = item
                e["lidos"][x["hash"]] = agora
                lidos += 1
    finally:
        for ano, e in estado.items():
            if e["itens"] or (PASTA / f"orgao_{ano}.json").exists():
                comum.salvar(PASTA / f"orgao_{ano}.json", {"coletadoEm": agora, "fonte": CONTRATOS_PAGINA, "itens": e["itens"], "lidos": e["lidos"]})
    todos = [i for e in estado.values() for i in e["itens"].values()]
    print(f"SP: {sum(i['tipo'] == 'contrato' for i in todos)} contratos e {sum(i['tipo'] == 'ata_registro' for i in todos)} atas de registro do órgão "
          f"({lidos} detalhes lidos de {len(lista)} na página)")
    if falhas:
        comum.avisar(f"SP: {len(falhas)} detalhes de contrato sem resposta (tentados de novo na próxima coleta)")
    if vazios:
        comum.avisar(f"SP: {vazios} contratos da página sem tabela no detalhe (ficam só com objeto, modalidade e PDF da listagem, sem fornecedor)")


# ---------------------------------------------------------------- regras da verba (links dos textos legais)

def regras_da_verba(pagina: str) -> dict | None:
    """Atos e resoluções que a página de prestação de contas cita como regra da verba, como links para o texto da norma."""
    documentos = []
    for href, texto in re.findall(r'<a[^>]+href="(/norma\?id=\d+)"[^>]*>(.*?)</a>', pagina, re.S):
        titulo = texto_html(texto)
        ano = re.search(r"/(\d{4})\b", titulo)
        documentos.append({"ano": int(ano[1]) if ano else None, "titulo": titulo, "url": SITE + href.replace("/norma?id=", "/norma/?id=")})
    if not documentos:
        return None
    return {"ano": max(d["ano"] or 0 for d in documentos) or None, "fonte": DESPESAS_PAGINA, "documentos": documentos}


def coletar_regras(s) -> None:
    regra = regras_da_verba(baixar(s, DESPESAS_PAGINA).decode("latin-1"))
    if not regra:
        raise RuntimeError("nenhum ato ou resolução citado na página de prestação de contas; mantém o arquivo anterior")
    comum.salvar(PASTA / "regras_ressarcimento.json", regra)
    print(f"SP: regras da verba {len(regra['documentos'])} textos legais")


# ---------------------------------------------------------------- coleta

def coletar() -> None:
    pasta = comum.DADOS / UF
    hoje = date.today()
    agora = hoje.isoformat()
    s = comum.sessao()
    deputados = parse_deputados(baixar(s, DEPUTADOS_XML))
    if not deputados:
        comum.avisar("SP: lista de deputados vazia")
        return
    try:
        r = s.get(PARLAMENTARES_API, params={"filtroLegislatura": LEGISLATURA, "filtroEmExercicioPesquisa": "S"}, timeout=60)
        r.raise_for_status()
        fotos_por_matricula = fotos(r.json().get("content") or [])
    except Exception as e:
        comum.avisar(f"SP: sem fotos ({e})")
        fotos_por_matricula = {}
    for d in deputados:
        d["foto"] = fotos_por_matricula.get(d["id"])

    indice = s.get(FOLHA_INDICE, timeout=60).content.decode("latin-1")
    meses = [m for m in meses_da_folha(indice) if m[0] >= PRIMEIRO_ANO]
    folhas = {}
    for ano, mes in meses:
        arq_existente = comum.ler(pasta / f"remuneracao_{ano}.json", {"itens": []})["itens"]
        if any(i["mes"] == mes for i in arq_existente) and (ano, mes) != meses[-1]:
            continue
        r = s.get(FOLHA.format(ano=ano, mes=mes), timeout=60)
        r.raise_for_status()
        folhas[(ano, mes)] = parse_folha(r.content.decode("latin-1"))
    nomes_civis = {lin["nome"] for linhas in folhas.values() for lin in linhas}
    ligados = ligar_civis(nomes_civis, deputados)
    arq_tse = comum.RAIZ / "dados" / "tse" / "2022" / f"{UF}.json"
    if arq_tse.exists() and len(ligados) < len(deputados):
        restantes = [d for d in deputados if d["id"] not in set(ligados.values())]
        extras = ligar_civis_pelo_tse([n for n in nomes_civis if n not in ligados], restantes, comum.ler(arq_tse, []))
        ligados.update(extras)
    por_id = {i: c for c, i in ligados.items()}
    for d in deputados:
        d["nomeCivil"] = por_id.get(d["id"])
    sem_civil = [d["nome"] for d in deputados if not d["nomeCivil"]]
    if sem_civil:
        comum.avisar(f"SP: {len(sem_civil)} deputados sem nome civil ligado (sem subsídio): {', '.join(sem_civil[:12])}...")
    saida = [{k: v for k, v in d.items() if k != "idAutor"} for d in deputados]
    comum.salvar(pasta / "deputados.json", {"fonte": DEPUTADOS_PAGINA, "host": None, "legislatura": "2023-2027", "deputados": saida})
    print(f"SP: {len(deputados)} deputados, {len(ligados)} com nome civil")

    for (ano, mes), linhas in sorted(folhas.items()):
        arq = pasta / f"remuneracao_{ano}.json"
        itens = [i for i in comum.ler(arq, {"itens": []})["itens"] if i["mes"] != mes] + itens_folha(linhas, ligados, ano, mes)
        comum.salvar(arq, {"coletadoEm": agora, "fonte": FOLHA_INDICE, "itens": sorted(itens, key=lambda i: (i["mes"], i["idDeputado"]))})
    print(f"SP: subsídio de {len(folhas)} meses")

    ids_por_matricula = {d["id"]: d["id"] for d in deputados}
    for ano in range(PRIMEIRO_ANO, hoje.year + 1):
        arq = pasta / f"verbas_{ano}.json"
        if arq.exists() and ano < hoje.year:
            continue
        try:
            itens = itens_verba(baixar(s, f"{REPOSITORIO}/deputados/despesas_gabinetes_{ano}.xml"), ids_por_matricula)
        except Exception as e:
            comum.avisar(f"SP: verba {ano}: {e}")
            continue
        comum.salvar(arq, {"coletadoEm": agora, "fonte": DESPESAS_PAGINA, "itens": itens})
        print(f"SP: {ano} verba {len(itens)} lançamentos")

    try:
        proposituras = ler_proposituras(baixar(s, PROPOSITURAS_ZIP), PRIMEIRO_ANO)
        anos = materias_por_ano(proposituras, ler_autores(baixar(s, AUTORES_ZIP), proposituras), deputados)
        for ano in range(PRIMEIRO_ANO, hoje.year + 1):
            comum.salvar(pasta / f"materias_{ano}.json", {"coletadoEm": agora, "fonte": DADOS_ABERTOS, "materias": anos.get(ano, {})})
            print(f"SP: {ano} proposições {len(anos.get(ano, {}))}")
    except Exception as e:
        comum.avisar(f"SP: proposições: {e}")

    comum.rodar_etapas(UF, [
        ("normas com autoria", partial(coletar_normas, s, deputados, hoje)),
        ("pautas e atas", partial(coletar_pautas_atas, s, hoje)),
        ("contratos e atas de registro de preço", partial(coletar_contratos, s, hoje)),
        ("regras da verba", partial(coletar_regras, s)),
    ])

    try:
        arq = pasta / "presenca.json"
        itens = presenca_do_ano(s, deputados, hoje.year, comum.ler(arq, {"itens": []})["itens"], hoje)
        outros_anos = [i for i in comum.ler(arq, {"itens": []})["itens"] if not i["periodo"].startswith(str(hoje.year))]
        comum.salvar(arq, {"coletadoEm": agora, "fonte": PRESENCA_PAGINA, "itens": outros_anos + itens})
        print(f"SP: presença {len(itens)} linhas")
    except Exception as e:
        comum.avisar(f"SP: presença: {e}")


# ---------------------------------------------------------------- contratos

def _contrato_deputados(ctx):
    s = comum.sessao()
    xml = baixar(s, DEPUTADOS_XML).decode("utf-8")
    achados = re.findall(r"<Deputado>.*?</Deputado>", xml, re.S)[:2]
    achados = [re.sub(r"<(Biografia|txAreaAtuacao|txBaseEleitoral)>.*?</\1>", "", a, flags=re.S) for a in achados]
    r = s.get(PARLAMENTARES_API, params={"filtroLegislatura": LEGISLATURA, "filtroEmExercicioPesquisa": "S"}, timeout=60)
    r.raise_for_status()
    parlamentares = [{k: p.get(k) for k in ("nuMatricula", "txNomeParlamentar", "txFoto", "txEmail", "txPartido")} for p in r.json()["content"][:2]]
    return {"xml": "<Deputados>" + "".join(achados) + "</Deputados>", "parlamentares": parlamentares}


def _conferir_deputados(registro):
    achados = parse_deputados(registro["xml"].encode("utf-8"))
    falhas = [] if achados else ["nenhum deputado em exercício"]
    for d in achados:
        falhas += comum.campos_vazios(d, ("id", "nome", "partido", "idAutor"), "deputado")
    if not fotos(registro["parlamentares"]):
        falhas.append("parlamentar-portal sem txFoto")
    return falhas, []


def _contrato_verba(ctx):
    texto = baixar(comum.sessao(), f"{REPOSITORIO}/deputados/despesas_gabinetes_{date.today().year - 1}.xml").decode("utf-8")
    return {"xml": "<despesas>" + "".join(re.findall(r"<despesa>.*?</despesa>", texto, re.S)[:3]) + "</despesas>"}


def _conferir_verba(registro):
    raiz = ET.fromstring(registro["xml"])
    falhas = [] if len(raiz) else ["nenhuma despesa"]
    for d in raiz:
        falhas += [f"despesa sem {campo}" for campo in ("Ano", "Matricula", "Mes", "Valor", "CNPJ", "Tipo", "Fornecedor") if not (d.findtext(campo) or "").strip()]
    itens = itens_verba(registro["xml"].encode("utf-8"), {(d.findtext("Matricula") or "").strip(): "x" for d in raiz})
    if len(itens) != len(raiz):
        falhas.append("despesa não virou item")
    return falhas, []


def _contrato_folha(ctx):
    s = comum.sessao()
    indice = s.get(FOLHA_INDICE, timeout=60).content.decode("latin-1")
    ano, mes = meses_da_folha(indice)[-1]
    r = s.get(FOLHA.format(ano=ano, mes=mes), timeout=60)
    r.raise_for_status()
    texto = r.content.decode("latin-1")
    linhas = re.findall(r"<tr>.*?</tr>", texto, re.S)
    return {"indice": [f"folha-deputados-{ano}-{mes:02d}.html"], "linhas": "<table>" + "".join(linhas[:3]) + "</table>", "ano": ano, "mes": mes}


def _conferir_folha(registro):
    linhas = parse_folha(registro["linhas"])
    falhas = [] if linhas else ["nenhuma linha de subsídio"]
    falhas += ["subsídio sem valor" for lin in linhas if None in (lin["bruto"], lin["tributos"], lin["liquido"])]
    if not meses_da_folha(" ".join(registro["indice"])):
        falhas.append("índice sem mês")
    return falhas, []


def _contrato_presenca(ctx):
    s = comum.sessao()
    hoje = date.today()
    mes, ano = (hoje.month - 1, hoje.year) if hoje.month > 1 else (12, hoje.year - 1)
    return {"registros": presenca_do_mes(s, "300607", mes, ano)[:6]}


def _conferir_presenca(registro):
    falhas = [] if registro["registros"] else ["nenhuma sessão"]
    for r in registro["registros"]:
        falhas += comum.campos_vazios(r, ("idSessaoPlenaria", "data", "situacao"), "presença")
    return falhas, []


def _contrato_proposituras(ctx):
    s = comum.sessao()
    proposituras = ler_proposituras(baixar(s, PROPOSITURAS_ZIP), date.today().year - 1)
    pequenas = dict(list(proposituras.items())[:3])
    autores = ler_autores(baixar(s, AUTORES_ZIP), pequenas)
    return {"proposituras": pequenas, "autores": {k: sorted(v) for k, v in autores.items()}}


def _conferir_proposituras(registro):
    falhas = [] if registro["proposituras"] else ["nenhuma propositura"]
    for doc, p in registro["proposituras"].items():
        falhas += comum.campos_vazios(p, ("natureza", "ano", "numero", "ementa", "data"), "propositura")
        if not registro["autores"].get(doc):
            falhas.append("propositura sem autor")
    return falhas, []


def _contrato_normas(ctx):
    s = comum.sessao()
    lista = pegar_json(s, "/processo", listaIdTipoProcesso=1, transformadoNorma="true", ano=date.today().year - 1, page=0, size=60)["content"]
    p = next(x for x in lista if x["tipoAutorPrincipal"] == "Parlamentar")
    d = pegar_json(s, f"/processo/detalhes/todos/{p['tipoProcesso']}/{p['anoTipo']}/{p['numeroTipo']}")
    chaves = ("idProcesso", "descricao", "resumo", "transformadoNorma", "urlNorma", "descricaoNorma")
    autores = [{k: a.get(k) for k in ("matricula", "nome")} for a in d["autores"]]
    return {"lista": [p, next(x for x in lista if x["tipoAutorPrincipal"] == "Pessoa")], "detalhe": {**{k: d[k] for k in chaves}, "autores": autores}}


def _conferir_normas(registro):
    falhas = []
    d = registro["detalhe"]
    matriculas = {str(a["matricula"]) for a in d["autores"] if a["matricula"]}
    achada = norma_do_detalhe(d, matriculas)
    if not achada:
        return ["detalhe do projeto sem urlNorma, descricaoNorma ou autor com matrícula"], []
    falhas += comum.campos_vazios(achada[1], ("tipo", "numero", "ano", "data", "ementa", "fonte", "idsDeputados"), "norma")
    if not any(precisa_do_detalhe(p, matriculas) for p in registro["lista"]):
        falhas.append("listagem de /processo sem autor principal (tipoAutorPrincipal, numeroAutorPrincipal)")
    for p in registro["lista"]:
        falhas += comum.campos_vazios(p, ("idProcesso", "tipoProcesso", "anoTipo", "numeroTipo"), "projeto da listagem")
    return falhas, []


def _contrato_sessoes(ctx):
    s = comum.sessao()
    sessoes = pegar_json(s, "/sessoes-plenarias/consulta", ano=date.today().year, page=0, size=TAMANHO_PAGINA)["content"]
    x = next(x for x in sessoes if x["temPauta"] and x["temOrdemDoDia"] and x["temIntegra"])
    base = f"/sessoes-plenarias/{x['id']}"

    def recorte(d, chaves):
        return {k: d.get(k) for k in chaves}

    return {"sessao": recorte(x, ("id", "titulo", "dtInicio", "temPauta", "temOrdemDoDia", "temIntegra")),
            "pauta": recorte(pegar_json(s, f"{base}/pauta"), ("titulo", "urlDocumento")),
            "ordemDoDia": recorte(pegar_json(s, f"{base}/ordem-do-dia"), ("txTitulo", "urlDocumento")),
            "integra": pegar_json(s, f"{base}/integra")}


def _conferir_sessoes(registro):
    x = registro["sessao"]
    pauta = item_pauta(x, [registro["pauta"]], [registro["ordemDoDia"]])
    ata = item_ata(x, registro["integra"])
    if not (pauta and ata):
        return ["sessão sem pauta, ordem do dia ou íntegra (urlDocumento, urlIntegra)"], []
    return comum.campos_vazios(pauta, ("titulo", "data", "fonte"), "pauta") + comum.campos_vazios(ata, ("titulo", "data", "fonte"), "ata"), []


def _contrato_reunioes(ctx):
    reunioes = pegar_json(comum.sessao(), "/colegiado/reunioes", ano=date.today().year - 1, page=0, size=TAMANHO_PAGINA)["content"]
    com_arquivo = [r for r in reunioes if {i["tipo"] for i in itens_comissoes([r])} >= {"ordem-do-dia"}][:2]
    chaves = ("idReuniao", "nuReuniao", "tituloReuniao", "dtReuniao", "status", "colegiadosRelacionados")
    docs = ("idDocumento", "tipo", "descricao", "linkArquivo", "linkArquivoPDF")
    return {"reunioes": [{**{k: r[k] for k in chaves}, "documentosReuniao": [{k: d.get(k) for k in docs} for d in r["documentosReuniao"]]} for r in com_arquivo]}


def _conferir_reunioes(registro):
    itens = itens_comissoes(registro["reunioes"])
    if not itens:
        return ["nenhuma reunião de comissão com pauta ou ata em arquivo (documentosReuniao.linkArquivo)"], []
    falhas = []
    for i in itens:
        falhas += comum.campos_vazios(i, ("titulo", "data", "fonte"), "documento de reunião")
    return falhas, []


def _contrato_contratos(ctx):
    s = comum.sessao()
    pagina = baixar(s, CONTRATOS_PAGINA).decode("latin-1")
    recorte, detalhes = [], {}
    for modulo in ("contratos", "atas", "dispensas"):
        ini = pagina.index(f'<div class="modulo_{modulo}"')
        cartoes = pagina[ini:].split('<li class="card"')
        recorte.append(f'<div class="modulo_{modulo}" style="display: none">' + '<li class="card"'.join(cartoes[:3]))
        h = re.search(r"detContrato=([0-9a-f]{32})", cartoes[1])[1]
        detalhe = s.get(DETALHE_CONTRATO.format(hash=h), timeout=60).content.decode("latin-1")
        detalhes[h] = re.search(r'<table width="100%" class="tabela">.*?</table>', detalhe, re.S)[0]
    return {"listagem": "".join(recorte), "detalhes": detalhes}


def _conferir_contratos(registro):
    lista = parse_listagem(registro["listagem"])
    falhas = [] if lista else ["listagem sem contrato (div modulo_*, li card, Processo Digital)"]
    por_hash = {x["hash"]: x for x in lista}
    if {x["modulo"] for x in lista} != {"contratos", "atas", "dispensas"}:
        falhas.append("listagem sem contratos, atas e dispensas")
    for x in lista:
        falhas += comum.campos_vazios(x, ("hash", "numero", "ano", "modalidade", "objeto"), "contrato da listagem")
    for h, pagina in registro["detalhes"].items():
        iid, item = item_contrato(por_hash[h], parse_detalhe(pagina))
        falhas += comum.campos_vazios(item, ("fornecedor", "cnpj", "objeto", "inicio", "fim", "assinatura", "fonte"), "contrato do detalhe")
    return falhas, []


def _contrato_regras(ctx):
    pagina = baixar(comum.sessao(), DESPESAS_PAGINA).decode("latin-1")
    i = pagina.index("Sugerimos a leitura")
    return {"trecho": pagina[i:pagina.index("</p>", i) + 4]}


def _conferir_regras(registro):
    regra = regras_da_verba(registro["trecho"])
    if not regra:
        return ["página de prestação de contas sem link /norma?id= para os textos legais"], []
    return [f"texto legal sem título ou ano: {d}" for d in regra["documentos"] if not d["titulo"] or not d["ano"]], []


CONTRATOS = [
    {"nome": "estadual_sp_deputados", "fonte": DEPUTADOS_XML, "buscar": _contrato_deputados, "html": _conferir_deputados},
    {"nome": "estadual_sp_verba", "fonte": f"{REPOSITORIO}/deputados/despesas_gabinetes_<ano>.xml", "buscar": _contrato_verba, "html": _conferir_verba},
    {"nome": "estadual_sp_folha", "fonte": FOLHA_INDICE, "buscar": _contrato_folha, "html": _conferir_folha},
    {"nome": "estadual_sp_presenca", "fonte": f"{API}/lista-presenca-parlamentar/<matrícula>/<mês>/<ano>", "buscar": _contrato_presenca, "html": _conferir_presenca},
    {"nome": "estadual_sp_proposituras", "fonte": PROPOSITURAS_ZIP, "buscar": _contrato_proposituras, "html": _conferir_proposituras},
    {"nome": "estadual_sp_normas", "fonte": f"{API}/processo/detalhes/todos/<sigla>/<ano>/<número>", "buscar": _contrato_normas, "html": _conferir_normas},
    {"nome": "estadual_sp_sessoes", "fonte": f"{API}/sessoes-plenarias/<id>/pauta", "buscar": _contrato_sessoes, "html": _conferir_sessoes},
    {"nome": "estadual_sp_reunioes", "fonte": f"{API}/colegiado/reunioes", "buscar": _contrato_reunioes, "html": _conferir_reunioes},
    {"nome": "estadual_sp_contratos", "fonte": CONTRATOS_PAGINA, "buscar": _contrato_contratos, "html": _conferir_contratos},
    {"nome": "estadual_sp_regras", "fonte": DESPESAS_PAGINA, "buscar": _contrato_regras, "html": _conferir_regras},
]


if __name__ == "__main__":
    comum.principal(coletar)
