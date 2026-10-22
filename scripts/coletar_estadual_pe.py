"""
Deputados estaduais de Pernambuco (ALEPE), fora do SAPL.

Fontes lidas aqui (abertas, sem login):
  - lista da legislatura (id, nome, partido, e-mail, foto): https://www.alepe.pe.gov.br/servicos/transparencia/dep/deputados.php?leg=-16
    (163 registros, inclui quem já saiu); os em exercício vêm de https://dadosabertos.alepe.pe.gov.br/api/v1/parlamentares/
  - verba indenizatória (mesmo JSON da tela https://transparencia.alepe.pe.gov.br/financas/verbas-indenizatorias):
    adm/verbaindenizatoria-dep-meses.php, adm/verbaindenizatoria.php (lançamento: tipo P = pedido, C = complemento)
    e adm/verbaindenizatorianotas.php (rubrica, data, CNPJ, empresa, valor); rubricas em adm/verbaindenizatoria-rubricas.php
  - projetos, indicações e requerimentos (XML) em https://dadosabertos.alepe.pe.gov.br/api/v1/proposicoes/<tipo>/?ano=

Não coletado: remuneração (a API só dá a tabela por cargo, não por pessoa); presença e votações (não existem nas fontes abertas;
o sistema legislativo https://legis.alepe.pe.gov.br pede login).
"""

import html as html_lib
import json
import re
import sys
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import requests

import estaduais_comum as comum

UF = "PE"
PORTAL = "https://www.alepe.pe.gov.br/servicos/transparencia"
API = "https://dadosabertos.alepe.pe.gov.br/api/v1"
SITE = "https://www.alepe.pe.gov.br"
DEPUTADOS_URL = f"{PORTAL}/dep/deputados.php?leg=-16"
PARLAMENTARES_URL = f"{API}/parlamentares/?formato=json"
RUBRICAS_URL = f"{PORTAL}/adm/verbaindenizatoria-rubricas.php"
MESES_URL = f"{PORTAL}/adm/verbaindenizatoria-dep-meses.php"
LANCAMENTOS_URL = f"{PORTAL}/adm/verbaindenizatoria.php"
NOTAS_URL = f"{PORTAL}/adm/verbaindenizatorianotas.php"
VERBA_PAGINA = "https://transparencia.alepe.pe.gov.br/financas/verbas-indenizatorias"
PROPOSICOES_PAGINA = "https://transparencia.alepe.pe.gov.br/proposicoes"
TIPOS_PROPOSICAO = ("projetos", "indicacoes", "requerimentos")
PRIMEIRO_ANO = 2023
MESES_RECENTES = 2
LIMITE_EMENTA = 400
TIPOS_LANCAMENTO = {"P": "Pedido", "C": "Complemento"}
SIGLA_TIPO = {"projetos": "PROJ", "indicacoes": "IND", "requerimentos": "REQ"}
NOME_TIPO = {"indicacoes": "Indicação", "requerimentos": "Requerimento"}
TAG_PROPOSICAO = {"projetos": "projeto", "indicacoes": "indicacao", "requerimentos": "requerimento"}


def get_json_utf8(sessao, url: str, **params):
    r = sessao.get(url, params=params, timeout=60)
    r.raise_for_status()
    return json.loads(r.content.decode("utf-8"))


# ---------------------------------------------------------------- deputados

def ligar(nomes, deputados: list[dict]) -> dict:
    """Como `ligar_nomes`; "João Paulo do PT" também tenta "João Paulo" quando "PT" é o partido de um deputado."""
    ligados = comum.ligar_nomes(nomes, deputados)
    partidos = {comum.sem_acento(d["partido"]) for d in deputados if d.get("partido")}
    for n in nomes:
        if n in ligados:
            continue
        m = re.match(r"^(.*\S)\s+d[oa]\s+(\S+)\s*$", n, re.I)
        if m and comum.sem_acento(m.group(2)) in partidos:
            achado = comum.ligar_nomes([m.group(1)], [d for d in deputados if comum.sem_acento(d.get("partido")) == comum.sem_acento(m.group(2))])
            if m.group(1) in achado:
                ligados[n] = achado[m.group(1)]
    return ligados


def montar_deputados(lista: list[dict], parlamentares: list[dict]) -> list[dict]:
    """Em exercício = os `parlamentares` da API; o id e os dados vêm da lista da legislatura quando o nome casa."""
    base = [{"id": d["id"], "nome": comum.nome_limpo(d["nome"]), "nomeCivil": None, "partido": d.get("partido")} for d in lista]
    ligados = ligar([p["nomeParlamentar"] for p in parlamentares], base)
    por_id = {d["id"]: d for d in lista}
    deputados = []
    for p in parlamentares:
        nome = comum.nome_limpo(p["nomeParlamentar"])
        achado = por_id.get(ligados.get(p["nomeParlamentar"]))
        if achado:
            foto = achado.get("foto")
            deputados.append({"id": achado["id"], "nome": nome, "nomeCivil": None, "foto": SITE + foto if foto else None,
                              "email": achado.get("email") or None, "titular": True, "partido": p.get("partido") or achado.get("partido"),
                              "fonte": DEPUTADOS_URL})
        else:
            deputados.append({"id": "sem-" + re.sub(r"\W+", "-", comum.sem_acento(nome)), "nome": nome, "nomeCivil": None, "foto": None,
                              "email": None, "titular": True, "partido": p.get("partido"), "fonte": PARLAMENTARES_URL})
    return deputados


# ---------------------------------------------------------------- verba indenizatória

def limpar_texto(texto: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", html_lib.unescape(html_lib.unescape(texto or ""))).split())


def itens_verba(lancamento: dict, notas: list[dict], id_deputado: str, ano: int, mes: int, rubricas: dict) -> list[dict]:
    tipo = TIPOS_LANCAMENTO.get(lancamento.get("tipo"), lancamento.get("tipo"))
    itens = []
    for n in notas:
        data = n.get("data") or ""
        m = re.match(r"(\d{2})/(\d{2})/(\d{4})$", data)
        itens.append({"idDeputado": id_deputado, "mes": mes, "categoria": rubricas.get(n.get("rubrica")) or f"Rubrica {n.get('rubrica')}",
                      "fornecedor": n.get("empresa") or None, "cnpj": n.get("cnpj") or None, "valor": comum.valor_br(n.get("valor")),
                      "data": f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None, "tipo": tipo, "numero": lancamento.get("numero"),
                      "docid": lancamento.get("docid"), "fonte": VERBA_PAGINA})
    if not notas and lancamento.get("total") is not None:
        itens.append({"idDeputado": id_deputado, "mes": mes, "categoria": "Sem detalhamento", "fornecedor": None, "cnpj": None,
                      "valor": comum.valor_br(lancamento.get("total")), "data": None, "tipo": tipo, "numero": lancamento.get("numero"),
                      "docid": lancamento.get("docid"), "fonte": VERBA_PAGINA})
    return itens


def rubricas_do_ano(sessao, ano: int) -> dict:
    return {r["numero_categoria"]: r["nome_categoria"] for r in get_json_utf8(sessao, RUBRICAS_URL, ano=ano)}


def verba_do_mes(sessao, id_deputado: str, ano: int, mes: int, rubricas: dict) -> list[dict]:
    itens = []
    for l in get_json_utf8(sessao, LANCAMENTOS_URL, dep=id_deputado, ano=ano, mes=mes):
        notas = get_json_utf8(sessao, NOTAS_URL, docid=l["docid"])
        itens += itens_verba(l, notas, id_deputado, ano, mes, rubricas)
    return itens


def verba_do_ano(sessao, deputados: list[dict], ano: int, existentes: list[dict], hoje: date) -> list[dict]:
    rubricas = rubricas_do_ano(sessao, ano)
    novos = comum.meses_recentes(hoje, MESES_RECENTES)
    itens = [i for i in existentes if (ano, i["mes"]) not in novos]
    guardados = {(i["idDeputado"], i["mes"]) for i in itens}

    def um(d):
        achados = []
        for m in get_json_utf8(sessao, MESES_URL, dep=d["id"], ano=ano):
            mes = int(m["mes"])
            if (d["id"], mes) in guardados:
                continue
            achados += verba_do_mes(sessao, d["id"], ano, mes, rubricas)
        return achados

    com_id = [d for d in deputados if not d["id"].startswith("sem-")]
    with ThreadPoolExecutor(max_workers=2) as pool:
        for achados in pool.map(um, com_id):
            itens += achados
    return sorted(itens, key=lambda i: (i["mes"], str(i["idDeputado"]), str(i["docid"]), i["data"] or ""))


# ---------------------------------------------------------------- proposições

def parse_proposicoes(conteudo: bytes, tipo: str) -> list[dict]:
    raiz = ET.fromstring(conteudo)
    itens = []
    for p in raiz.iter(TAG_PROPOSICAO[tipo]):
        data = p.get("dataPublicacao") or ""
        m = re.match(r"(\d{2})/(\d{2})/(\d{4})$", data)
        itens.append({"docid": p.get("docid"), "numero": p.get("numero"), "ano": p.get("ano"), "tipo": p.get("tipo"), "subtipo": p.get("subtipo"),
                      "ementa": limpar_texto(p.get("ementa")), "data": f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None,
                      "autores": [a.get("nome") for a in p.iter("autor") if a.get("tipo") == "DEPUTADO" and a.get("nome")]})
    return itens


def materias(proposicoes: list[dict], ids: dict, categoria: str) -> dict:
    achadas = {}
    for p in proposicoes:
        autores = sorted({ids[a] for a in p["autores"] if a in ids})
        if not autores:
            continue
        ementa = p["ementa"]
        if len(ementa) > LIMITE_EMENTA:
            ementa = ementa[:LIMITE_EMENTA].rsplit(" ", 1)[0] + "..."
        if categoria == "projetos":
            descricao = p["tipo"] or "Projeto"
        else:
            descricao = NOME_TIPO[categoria] + (f" ({p['subtipo']})" if p["subtipo"] else "")
        achadas[f"{categoria}-{p['docid']}"] = {
            "tipo": SIGLA_TIPO[categoria], "tipoDescricao": descricao,
            "numero": int(p["numero"]) if (p["numero"] or "").isdigit() else None, "ano": int(p["ano"]) if (p["ano"] or "").isdigit() else None,
            "dataApresentacao": p["data"], "ementa": ementa, "situacao": None, "emTramitacao": None, "linkTexto": None,
            "idsAutores": autores, "idsDeputados": autores, "fonte": PROPOSICOES_PAGINA}
    return achadas


def proposicoes_do_ano(sessao, ano: int, tipo: str) -> list[dict]:
    r = sessao.get(f"{API}/proposicoes/{tipo}/", params={"formato": "json", "ano": ano}, timeout=120)
    r.raise_for_status()
    return parse_proposicoes(r.content, tipo)


# ---------------------------------------------------------------- coleta

def coletar_proposicoes(s, deputados: list[dict], ano: int, pasta, agora: str) -> None:
    achadas = {}
    for tipo in TIPOS_PROPOSICAO:
        props = proposicoes_do_ano(s, ano, tipo)
        achadas.update(materias(props, ligar({a for p in props for a in p["autores"]}, deputados), tipo))
    comum.salvar(pasta / f"materias_{ano}.json", {"coletadoEm": agora, "fonte": PROPOSICOES_PAGINA, "materias": achadas})
    print(f"PE: {ano} proposições {len(achadas)}")


def coletar() -> None:
    pasta = comum.DADOS / UF
    hoje = date.today()
    agora = hoje.isoformat()
    s = comum.sessao()
    portal_no_ar = True
    try:
        deputados = montar_deputados(get_json_utf8(s, DEPUTADOS_URL), get_json_utf8(s, PARLAMENTARES_URL))
    except Exception as e:
        # o portal da ALEPE às vezes não aceita conexão (visto no GitHub Actions); a verba vem dele, as proposições não
        comum.avisar(f"PE: lista de deputados: {type(e).__name__}: {str(e)[:120]}")
        portal_no_ar = not isinstance(e, requests.ConnectionError)
        deputados = []
    if deputados:
        comum.salvar(pasta / "deputados.json", {"fonte": PARLAMENTARES_URL, "host": None, "legislatura": "2023-2027", "deputados": deputados})
        sem_id = [d["nome"] for d in deputados if d["id"].startswith("sem-")]
        if sem_id:
            comum.avisar(f"PE: sem id na lista da legislatura (sem verba): {', '.join(sem_id)}")
    else:
        deputados = (comum.ler(pasta / "deputados.json") or {}).get("deputados") or []
        if not deputados:
            comum.avisar("PE: lista de deputados vazia")
            return
        comum.avisar("PE: usando a lista de deputados da coleta anterior")
    print(f"PE: {len(deputados)} deputados")

    for ano in range(PRIMEIRO_ANO, hoje.year + 1):
        arq = pasta / f"verbas_{ano}.json"
        if portal_no_ar and not comum.ano_encerrado(ano, hoje, arq):
            try:
                itens = verba_do_ano(s, deputados, ano, comum.ler(arq, {"itens": []})["itens"], hoje)
                comum.salvar(arq, {"coletadoEm": agora, "fonte": VERBA_PAGINA, "itens": itens})
                print(f"PE: {ano} verba {len(itens)} notas")
            except Exception as e:
                comum.avisar(f"PE: verba {ano}: {type(e).__name__}: {str(e)[:120]}")
        if not comum.ano_encerrado(ano, hoje, pasta / f"materias_{ano}.json"):
            try:
                coletar_proposicoes(s, deputados, ano, pasta, agora)
            except Exception as e:
                comum.avisar(f"PE: proposições {ano}: {type(e).__name__}: {str(e)[:120]}")


# ---------------------------------------------------------------- contratos

def _contrato_deputados(ctx):
    s = comum.sessao()
    return {"lista": get_json_utf8(s, DEPUTADOS_URL)[:2], "parlamentares": get_json_utf8(s, PARLAMENTARES_URL)[:2]}


def _conferir_deputados(registro):
    falhas = []
    for d in registro["lista"]:
        for campo in ("id", "nome", "partido", "email", "foto"):
            if campo not in d:
                falhas.append(f"deputados.php sem {campo}")
    for p in registro["parlamentares"]:
        for campo in ("nomeParlamentar", "partido"):
            if not p.get(campo):
                falhas.append(f"parlamentares sem {campo}")
    return falhas or ([] if registro["lista"] and registro["parlamentares"] else ["lista vazia"]), []


def _contrato_verba(ctx):
    s = comum.sessao()
    ano = date.today().year - 1
    meses = get_json_utf8(s, MESES_URL, dep="4508", ano=ano)
    mes = meses[0]["mes"]
    lancamentos = get_json_utf8(s, LANCAMENTOS_URL, dep="4508", ano=ano, mes=mes)[:2]
    return {"ano": ano, "meses": meses[:2], "lancamentos": lancamentos, "notas": get_json_utf8(s, NOTAS_URL, docid=lancamentos[0]["docid"])[:2],
            "rubricas": get_json_utf8(s, RUBRICAS_URL, ano=ano)[:3]}


def _conferir_verba(registro):
    falhas = []
    if not registro["meses"] or "mes" not in registro["meses"][0]:
        falhas.append("dep-meses sem mes")
    for l in registro["lancamentos"]:
        for campo in ("docid", "numero", "tipo", "total"):
            if l.get(campo) in (None, ""):
                falhas.append(f"lançamento sem {campo}")
        if l.get("tipo") not in TIPOS_LANCAMENTO:
            falhas.append(f"tipo de lançamento novo: {l.get('tipo')}")
    if not registro["lancamentos"]:
        falhas.append("nenhum lançamento")
    for n in registro["notas"]:
        for campo in ("rubrica", "data", "cnpj", "empresa", "valor"):
            if n.get(campo) in (None, ""):
                falhas.append(f"nota sem {campo}")
    for r in registro["rubricas"]:
        for campo in ("numero_categoria", "nome_categoria"):
            if r.get(campo) in (None, ""):
                falhas.append(f"rubrica sem {campo}")
    return falhas, []


def _contrato_proposicoes(tipo):
    def buscar(ctx):
        s = comum.sessao()
        r = s.get(f"{API}/proposicoes/{tipo}/", params={"formato": "json", "ano": date.today().year}, timeout=120)
        r.raise_for_status()
        texto = r.content.decode("utf-8")
        tag = TAG_PROPOSICAO[tipo]
        achados = re.findall(rf"<{tag} .*?</{tag}>", texto, re.S)
        com_deputado = [a for a in achados if 'tipo="DEPUTADO"' in a]
        return {"xml": "<?xml version='1.0' encoding='utf-8'?>\n<%ss>%s</%ss>" % (tag, "".join(com_deputado[:2]), tag)}
    return buscar


def _conferir_proposicoes(tipo):
    def conferir(registro):
        itens = parse_proposicoes(registro["xml"].encode("utf-8"), tipo)
        falhas = [] if itens else ["nenhuma proposição"]
        for i in itens:
            for campo in ("docid", "numero", "ano", "ementa", "data"):
                if not i[campo]:
                    falhas.append(f"proposição sem {campo}")
            if not i["autores"]:
                falhas.append("proposição sem autor deputado")
        return falhas, []
    return conferir


CONTRATOS = [
    dict(nome="estadual_pe_deputados", fonte=DEPUTADOS_URL, buscar=_contrato_deputados, html=_conferir_deputados),
    dict(nome="estadual_pe_verba", fonte=VERBA_PAGINA, buscar=_contrato_verba, html=_conferir_verba),
    dict(nome="estadual_pe_projetos", fonte=f"{API}/proposicoes/projetos/", buscar=_contrato_proposicoes("projetos"), html=_conferir_proposicoes("projetos")),
    dict(nome="estadual_pe_indicacoes", fonte=f"{API}/proposicoes/indicacoes/", buscar=_contrato_proposicoes("indicacoes"), html=_conferir_proposicoes("indicacoes")),
    dict(nome="estadual_pe_requerimentos", fonte=f"{API}/proposicoes/requerimentos/", buscar=_contrato_proposicoes("requerimentos"), html=_conferir_proposicoes("requerimentos")),
]


if __name__ == "__main__":
    coletar()
    sys.exit(0)
