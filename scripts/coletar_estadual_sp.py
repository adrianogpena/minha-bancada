"""
Deputados estaduais de São Paulo (Alesp), fora do SAPL.

Fontes lidas aqui (abertas, sem login nem captcha):
  - dados abertos (XML em https://www.al.sp.gov.br/repositorioDados/, catálogo em https://www.al.sp.gov.br/dados-abertos/):
    deputados/deputados.xml (94 em exercício), deputados/despesas_gabinetes_<ano>.xml (verba de gabinete com CNPJ),
    processo_legislativo/proposituras.zip + documento_autor.zip (autoria; só PL, PLC, PR, PDL, PEC e P. Const.)
  - API do portal https://legis-api-portal-prd.al.sp.gov.br: /parlamentar-portal (foto) e /lista-presenca-parlamentar/<matrícula>/<mês>/<ano>
  - subsídio mensal por nome civil: https://www.al.sp.gov.br/repositorio/folha-de-pagamento/folha-deputados-<ano>-<mês>.html

Não coletado: requerimentos, indicações e moções (79 mil documentos desde 2023, só volume); votações nominais do plenário
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
from datetime import date
from functools import partial

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


CONTRATOS = [
    {"nome": "estadual_sp_deputados", "fonte": DEPUTADOS_XML, "buscar": _contrato_deputados, "html": _conferir_deputados},
    {"nome": "estadual_sp_verba", "fonte": f"{REPOSITORIO}/deputados/despesas_gabinetes_<ano>.xml", "buscar": _contrato_verba, "html": _conferir_verba},
    {"nome": "estadual_sp_folha", "fonte": FOLHA_INDICE, "buscar": _contrato_folha, "html": _conferir_folha},
    {"nome": "estadual_sp_presenca", "fonte": f"{API}/lista-presenca-parlamentar/<matrícula>/<mês>/<ano>", "buscar": _contrato_presenca, "html": _conferir_presenca},
    {"nome": "estadual_sp_proposituras", "fonte": PROPOSITURAS_ZIP, "buscar": _contrato_proposituras, "html": _conferir_proposituras},
]


if __name__ == "__main__":
    comum.principal(coletar)
