"""
Deputados estaduais do Rio de Janeiro (ALERJ), fora do SAPL.

Fontes abertas e lidas aqui:
  - lista de deputados: eleitos de 2022 do TSE (dados/tse/2022/RJ.json); a ALERJ não publica lista em formato aberto;
  - presença: Ordem do Dia (Lotus Notes), um documento por mês, faltas por deputado
    http://alerjln1.alerj.rj.gov.br/ordemdia.nsf/presint?OpenForm
  - emendas impositivas: planilha XLSX por ano, aba "Impositivas", no relatório
    https://transparencia.alerj.rj.gov.br/section/report/121

Só PDF (não coletado): diárias /119, viagens /66, benefícios /33, folha /73. Sem arquivo: subsídio /62.
"""

import re
import sys
import zipfile
from datetime import date
from html import unescape
from io import BytesIO
from urllib.parse import quote
from xml.etree import ElementTree

import estaduais_comum as comum

UF = "RJ"
TSE_ARQUIVO = comum.RAIZ / "dados" / "tse" / "2022" / "RJ.json"
TRANSPARENCIA = "https://transparencia.alerj.rj.gov.br"
EMENDAS_URL = f"{TRANSPARENCIA}/section/report/121"
PRESENCA_BASE = "http://alerjln1.alerj.rj.gov.br"
PRESENCA_URL = f"{PRESENCA_BASE}/ordemdia.nsf/presint?OpenForm"
TSE_FICHA = "https://divulgacandcontas.tse.jus.br/divulga/#/candidato/2022/2040602022/RJ/{}"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def texto(resposta) -> str:
    try:
        return resposta.content.decode("utf-8")
    except UnicodeDecodeError:
        return resposta.content.decode("cp1252", errors="replace")


def limpar(html: str) -> str:
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", html)).split())


# ---------------------------------------------------------------- deputados

def deputados_do_tse() -> list[dict]:
    eleitos = comum.ler(TSE_ARQUIVO, [])
    lista = []
    for e in eleitos:
        if e.get("cargo") != "DEPUTADO ESTADUAL" or e.get("situacao") != "eleito":
            continue
        lista.append({"id": e["sequencial"], "nome": e.get("urna") or e["nome"], "nomeCivil": e["nome"], "foto": None,
                      "email": e.get("email"), "titular": True, "partido": e.get("partido"), "fonte": TSE_FICHA.format(e["sequencial"])})
    return sorted(lista, key=lambda d: comum.sem_acento(d["nome"]))


TITULOS = {"dr", "dra", "prof", "profa", "delegado", "delegada", "dep"}


def _tokens(nome: str) -> set:
    return {t for t in re.sub(r"[^a-z ]", " ", comum.sem_acento(nome)).split() if t not in TITULOS}


def ligar(nomes, deputados: list[dict]) -> dict:
    """Como `ligar_nomes`; o nome que não casa inteiro casa quando todas as suas palavras estão em um só nome (urna ou civil)."""
    ligados = comum.ligar_nomes(nomes, deputados)
    for n in nomes:
        if n in ligados or not _tokens(n):
            continue
        ids = {d["id"] for d in deputados if any(d.get(c) and _tokens(n) <= _tokens(d[c]) for c in ("nome", "nomeCivil"))}
        if len(ids) == 1:
            ligados[n] = next(iter(ids))
    return ligados


# ---------------------------------------------------------------- presença (Ordem do Dia)

def links_presenca(html: str) -> list[dict]:
    """[{url, data}] de cada documento mensal; `data` é a de publicação (AAAA-MM-DD)."""
    achados = []
    for href, rotulo in re.findall(r'<a href="(/ordemdia\.nsf/[^"]+\?OpenDocument)"[^>]*>(.*?)</a>', html, re.S):
        m = re.search(r"(\d\d)/(\d\d)/(\d{4})", limpar(rotulo))
        if m:
            achados.append({"url": PRESENCA_BASE + unescape(href), "data": f"{m.group(3)}-{m.group(1)}-{m.group(2)}"})
    return achados


def periodo_do_mes(mes: int, publicado: str) -> str:
    ano, mes_pub = int(publicado[:4]), int(publicado[5:7])
    return f"{ano if mes <= mes_pub else ano - 1}-{mes:02d}"


def parse_presenca(html: str, publicado: str) -> dict:
    """{periodo, totalSessoes, faltas:{nome: faltas}} de um documento mensal."""
    cabecalho = limpar(html.split("<table", 1)[0])
    mes = re.search(r"de\s*:\s*([^\W\d_]+)", cabecalho)
    mes_n = comum.mes_numero(mes.group(1)) if mes else None
    total = re.search(r"TOTAL DE SESS.{1,3}ES DELIBERATIVAS\s*-\s*(\d+)", html)
    faltas = {}
    for linha in re.findall(r"<tr valign=\"top\">(.*?)</tr>", html, re.S):
        celulas = [limpar(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", linha, re.S)]
        for i in range(0, len(celulas) - 2, 3):
            nome, n_faltas = celulas[i], celulas[i + 1]
            if not nome or nome == "DEPUTADO":
                continue
            faltas[nome] = int(n_faltas) if n_faltas.isdigit() else 0
    return {"periodo": periodo_do_mes(mes_n, publicado) if mes_n else None, "totalSessoes": int(total.group(1)) if total else None, "faltas": faltas}


def itens_presenca(doc: dict, url: str, deputados: list[dict]) -> list[dict]:
    ligados = ligar(doc["faltas"], deputados)
    itens = []
    for nome, faltas in doc["faltas"].items():
        if nome not in ligados:
            continue
        total = doc["totalSessoes"]
        itens.append({"idDeputado": ligados[nome], "periodo": doc["periodo"], "presente": None if total is None else max(total - faltas, 0),
                      "ausente": faltas, "licenca": None, "totalSessoes": total, "fonte": url})
    return itens


# ---------------------------------------------------------------- emendas impositivas (XLSX)

def links_emendas(html: str) -> dict:
    """{ano: url do XLSX} da página do relatório /121."""
    achados = {}
    for ano, bloco in re.findall(r'id="collapse-(\d{4})"(.*?)(?=id="collapse-\d{4}"|$)', html, re.S):
        for href, rotulo in re.findall(r'<a[^>]*href="(/download-spic[^"]*)"[^>]*>(.*?)</a>', bloco, re.S):
            if limpar(rotulo).lower() == "excel":
                achados[int(ano)] = TRANSPARENCIA + unescape(href)
    return achados


def ler_xlsx(conteudo: bytes) -> dict:
    """{nome da aba: [{coluna: valor}]} só com biblioteca padrão."""
    z = zipfile.ZipFile(BytesIO(conteudo))
    strings = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ElementTree.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
            strings.append("".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")))
    rels = {r.get("Id"): r.get("Target") for r in ElementTree.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
    abas = {}
    for aba in ElementTree.fromstring(z.read("xl/workbook.xml")).find("m:sheets", NS):
        alvo = rels[aba.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")].lstrip("/")
        caminho = alvo if alvo.startswith("xl/") else f"xl/{alvo}"
        linhas = []
        for row in ElementTree.fromstring(z.read(caminho)).iter(f"{{{NS['m']}}}row"):
            celulas = {}
            for c in row.findall("m:c", NS):
                v = c.find("m:v", NS)
                if v is None or v.text is None:
                    continue
                col = re.match(r"[A-Z]+", c.get("r")).group(0)
                celulas[col] = strings[int(v.text)] if c.get("t") == "s" else v.text
            if celulas:
                linhas.append(celulas)
        abas[aba.get("name")] = linhas
    return abas


def emendas_da_aba(linhas: list[dict]) -> list[dict]:
    """Linhas da aba "Impositivas" viram dicts por nome de coluna (a linha de cabeçalho é a que tem "Autor")."""
    cab = next((l for l in linhas if "Autor" in l.values()), None)
    if not cab:
        return []
    nomes = {col: re.sub(r"[^a-z]", "", comum.sem_acento(v)) for col, v in cab.items()}
    registros = []
    for l in linhas[linhas.index(cab) + 1:]:
        r = {nomes[c]: v.strip() for c, v in l.items() if c in nomes}
        if r.get("autor") and r.get("emenda"):
            registros.append(r)
    return registros


def itens_emendas(registros: list[dict], deputados: list[dict], url: str, ano: int) -> list[dict]:
    ligados = ligar({r["autor"] for r in registros}, deputados)
    itens = []
    for r in registros:
        if r["autor"] not in ligados:
            continue
        itens.append({"idDeputado": ligados[r["autor"]], "ano": ano, "numero": r.get("emenda"), "objeto": r.get("objeto"), "orgao": r.get("orgao"),
                      "beneficiario": r.get("beneficiario"), "municipio": r.get("municipio"), "valor": comum.valor_br(r.get("valor")),
                      "empenhado": None, "pago": None, "fonte": url})
    return itens


# ---------------------------------------------------------------- coleta

def coletar() -> None:
    pasta = comum.DADOS / UF
    hoje = date.today().isoformat()
    s = comum.sessao()
    deputados = deputados_do_tse()
    if not deputados:
        comum.avisar("RJ: sem eleitos de 2022 em dados/tse/2022/RJ.json")
        return
    comum.salvar(pasta / "deputados.json", {"fonte": "https://divulgacandcontas.tse.jus.br/divulga/#/home", "host": None, "legislatura": "2023-2027",
                                            "deputados": deputados})

    itens = []
    r = s.get(PRESENCA_URL, timeout=20)
    r.raise_for_status()
    for doc in links_presenca(texto(r)):
        resp = s.get(doc["url"], timeout=20)
        resp.raise_for_status()
        itens += itens_presenca(parse_presenca(texto(resp), doc["data"]), doc["url"], deputados)
    comum.salvar(pasta / "presenca.json", {"coletadoEm": hoje, "fonte": PRESENCA_URL, "itens": itens})
    print(f"RJ: presença {len(itens)} registros")

    r = s.get(EMENDAS_URL, timeout=20)
    r.raise_for_status()
    for ano, url in links_emendas(texto(r)).items():
        resp = s.get(url, timeout=60)
        resp.raise_for_status()
        registros = emendas_da_aba(ler_xlsx(resp.content).get("Impositivas", []))
        itens = itens_emendas(registros, deputados, EMENDAS_URL, ano)
        comum.salvar(pasta / f"emendas_{ano}.json", {"coletadoEm": hoje, "fonte": EMENDAS_URL, "itens": itens})
        print(f"RJ: emendas {ano} {len(itens)} de {len(registros)}")
    print(f"RJ: {len(deputados)} deputados")


# ---------------------------------------------------------------- contratos

def _recortar(html: str, manter: int) -> str:
    """Tira as linhas de deputados além das `manter` primeiras (a linha de cabeçalho fica)."""
    linhas = re.findall(r'<tr valign="top">.*?</tr>', html, re.S)
    for linha in linhas[manter + 1:]:
        html = html.replace(linha, "")
    return html


def _contrato_presenca(ctx):
    s = comum.sessao()
    r = s.get(PRESENCA_URL, timeout=20)
    r.raise_for_status()
    doc = links_presenca(texto(r))[0]
    resp = s.get(doc["url"], timeout=20)
    resp.raise_for_status()
    return {"publicado": doc["data"], "html": _recortar(texto(resp), 2)}


def _conferir_presenca(registro):
    doc = parse_presenca(registro["html"], registro["publicado"])
    falhas = []
    if not doc["periodo"]:
        falhas.append("mês do documento de presença não reconhecido")
    if not doc["totalSessoes"]:
        falhas.append("sem 'TOTAL DE SESSÕES DELIBERATIVAS'")
    if not doc["faltas"]:
        falhas.append("nenhum deputado na tabela de presença")
    return falhas, []


def _contrato_emendas(ctx):
    s = comum.sessao()
    r = s.get(EMENDAS_URL, timeout=20)
    r.raise_for_status()
    links = links_emendas(texto(r))
    ano = max(links)
    resp = s.get(links[ano], timeout=60)
    resp.raise_for_status()
    linhas = ler_xlsx(resp.content).get("Impositivas", [])
    cab = next(i for i, l in enumerate(linhas) if "Autor" in l.values())
    html = texto(r)
    inicio = html.index('id="collapse-')
    return {"ano": ano, "linhas": linhas[: cab + 3], "pagina": html[inicio: html.index("Voltar", inicio)]}


def _conferir_emendas(registro):
    falhas = []
    if not links_emendas(registro["pagina"]):
        falhas.append("página do relatório /121 sem link de planilha por ano")
    regs = emendas_da_aba(registro["linhas"])
    if not regs:
        falhas.append("aba Impositivas sem emendas reconhecidas")
    for r in regs:
        for campo in ("autor", "valor", "objeto"):
            if not r.get(campo):
                falhas.append(f"emenda sem {campo}")
    return falhas, []


CONTRATOS = [
    dict(nome="estadual_rj_presenca", fonte=PRESENCA_URL, buscar=_contrato_presenca, html=_conferir_presenca),
    dict(nome="estadual_rj_emendas", fonte=EMENDAS_URL, buscar=_contrato_emendas, html=_conferir_emendas),
]


if __name__ == "__main__":
    coletar()
    sys.exit(0)
