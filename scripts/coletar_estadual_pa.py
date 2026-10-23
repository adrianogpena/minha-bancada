"""
Deputados estaduais do Pará (ALEPA), fora do SAPL.

Fontes lidas aqui (todas abertas, sem login):
  - deputados em exercício, partido, foto, ficha, presença: https://alepa.pa.gov.br/Transparencia/FrequenciaSessoes
    (cartões HTML por deputado; o filtro Ano/Mês é um callback DevExpress que o `requests` reproduz com
    __DXCallbackName=cbpFrequencia, __DXCallbackArgument=c0:, ano, mes, tipoSessao); ficha em /Institucional/Deputado/<id>
  - verba indenizatória (liquidações) e diárias dos parlamentares: dashboards DevExpress em alepa.quartertec.com.br
    (dashboard57 e dashboard58), lidos pela API GET /api/dashboard/data
  - verba de gabinete (total mensal por gabinete): https://sigep.alepa.pa.gov.br/transp/frame_verbagabinete.php

Só PDF ou fora do alcance (não coletado): estrutura remuneratória dos deputados (PDF), remuneração de pessoal (só servidores,
busca por nome), emendas estaduais (portal do Estado em www.sistemas.pa.gov.br), projetos e votações (sem fonte de transparência).
"""

import json
import re
from datetime import date
from html import unescape
from functools import partial

import estaduais_comum as comum

UF = "PA"
ALEPA = "https://alepa.pa.gov.br"
FREQUENCIA_URL = f"{ALEPA}/Transparencia/FrequenciaSessoes"
FICHA_URL = f"{ALEPA}/Institucional/Deputado/{{}}"
VERBA_PAGINA = f"{ALEPA}/Transparencia/Page/VerbaIndenizatoria"
DIARIAS_PAGINA = f"{ALEPA}/Transparencia/Page/DiariasdosParlamentares"
GABINETE_PAGINA = f"{ALEPA}/Transparencia/Page/VerbadeGabinete"
GABINETE_URL = "https://sigep.alepa.pa.gov.br/transp/frame_verbagabinete.php"
DASHBOARD_URL = "https://alepa.quartertec.com.br/api/dashboard/data"
DASHBOARD_VERBA, DASHBOARD_DIARIAS = "dashboard57", "dashboard58"
PARAMETROS = [{"name": "CPF_Deputados", "value": "7BD68C11-DC21-4571-8EF6-AAB6E15355EF", "type": "System.String", "allowMultiselect": True, "selectAll": True}]
PRIMEIRO_ANO = 2023
PRIMEIRO_MES = (2023, 2)
MESES_RECENTES = 2


TITULOS = {"dr", "dra", "prof", "profa", "deleg", "delegado", "delegada", "dep", "deputado", "deputada"}
ligar = partial(comum.ligar_por_palavras, ignorar=TITULOS)


def mes_anterior(ano: int, mes: int) -> tuple[int, int]:
    return (ano - 1, 12) if mes == 1 else (ano, mes - 1)


# ---------------------------------------------------------------- deputados e presença

def parse_cartoes(html: str) -> dict:
    """{totalSessoes, deputados:[{id, nome, partido, foto, ficha, presente, licenciado, ausente}]} da página de frequência."""
    total = re.search(r"Total de sess.es:\s*(\d+)", html)
    deputados = []
    for bloco in html.split("card-frequencia-deputados")[1:]:
        h3 = re.search(r"<h3><b>(.*?)</b></h3>", bloco, re.S)
        if not h3:
            continue
        nome_partido = comum.limpar(h3.group(1))
        m = re.match(r"(.*?)\s*\(([^()]*)\)$", nome_partido)
        nome, partido = (m.group(1), m.group(2)) if m else (nome_partido, None)
        link = re.search(r"href='/Institucional/Deputado/(\d+)'", bloco)
        foto = re.search(r'<img src="([^"]+)"', bloco)
        contagens = {k: int(v) for k, v in re.findall(r"<p><b>(Presente|Licenciado|Ausente):\s*</b>(\d+)</p>", bloco)}
        deputados.append({"id": link.group(1) if link else None, "nome": nome, "partido": partido,
                          "foto": foto.group(1).replace("\\", "/").split("?")[0].replace(" ", "%20") if foto else None,
                          "ficha": FICHA_URL.format(link.group(1)) if link else None,
                          "presente": contagens.get("Presente"), "licenciado": contagens.get("Licenciado"), "ausente": contagens.get("Ausente")})
    return {"totalSessoes": int(total.group(1)) if total else None, "deputados": deputados}


def parse_ficha(html: str) -> dict:
    civil = re.search(r"Nome completo:\s*(?:<[^>]+>\s*)*([^<]+)", html)
    email = re.search(r"mailto:([^\"'>\s]+)", html)
    return {"nomeCivil": " ".join(unescape(civil.group(1)).split()) if civil else None, "email": email.group(1) if email else None}


def id_deputado(d: dict) -> str:
    return d["id"] or "sem-" + re.sub(r"\W+", "-", comum.sem_acento(d["nome"]))


def itens_presenca(pagina: dict, ano: int, mes: int) -> list[dict]:
    total = pagina["totalSessoes"]
    itens = []
    for d in pagina["deputados"]:
        if d["presente"] is None:
            continue
        itens.append({"idDeputado": id_deputado(d), "periodo": f"{ano}-{mes:02d}", "presente": d["presente"], "ausente": d["ausente"], "licenca": d["licenciado"],
                      "totalSessoes": total, "fonte": FREQUENCIA_URL})
    return itens


# ---------------------------------------------------------------- dashboards DevExpress (verba indenizatória e diárias)

def consulta_dashboard(sessao, dashboard: str, ano: int) -> dict:
    filtro = {"Filter": [{"dimensions": [{"@ItemType": "Dimension", "@DataMember": "Ano", "@DefaultId": "DataItem0",
                                          "NumericFormat": {"@FormatType": "General"}, "@SortOrder": "Descending"}], "values": [[ano]]}]}
    r = sessao.get(DASHBOARD_URL, params={"dashboardId": dashboard, "parameters": json.dumps(PARAMETROS, separators=(",", ":")),
                                          "itemId": "gridDashboardItem2", "query": json.dumps(filtro, separators=(",", ":"))}, timeout=60)
    r.raise_for_status()
    return r.json()["ItemData"]["DataStorageDTO"]


def linhas_dashboard(dto: dict) -> list[dict]:
    """Decodifica a grade (Data NL, Deputado, Classificação, Descrição, Valor)."""
    mapas = dto["EncodeMaps"]
    linhas = []
    for fatia in dto["Slices"]:
        chaves = fatia["KeyIds"]
        for chave, valores in fatia["Data"].items():
            indices = json.loads(chave)
            r = {c: mapas[c][i] for c, i in zip(chaves, indices, strict=False)}
            valor = valores.get("0")
            linhas.append({"data": (r.get("DataItem1") or "")[:10], "deputado": r.get("DataItem0"), "conta": r.get("DataItem5"),
                           "descricao": r.get("DataItem2"), "valor": valor})
    return sorted(linhas, key=lambda lin: (lin["data"], lin["deputado"] or "", lin["descricao"] or ""))


def recortar_dto(dto: dict, n: int = 2) -> dict:
    """Guarda só n células da grade, com os mapas de código reduzidos ao que elas usam."""
    fatia = dto["Slices"][0]
    chaves = list(fatia["Data"])[:n]
    novos = {c: [] for c in fatia["KeyIds"]}
    dados = {}
    for chave in chaves:
        indices = []
        for c, i in zip(fatia["KeyIds"], json.loads(chave), strict=False):
            valor = dto["EncodeMaps"][c][i]
            if valor not in novos[c]:
                novos[c].append(valor)
            indices.append(novos[c].index(valor))
        dados[json.dumps(indices, separators=(",", ":"))] = fatia["Data"][chave]
    return {"EncodeMaps": novos, "Slices": [{"KeyIds": fatia["KeyIds"], "ValueIds": fatia["ValueIds"], "Data": dados}]}


def itens_verba(linhas: list[dict], ids: dict, ano: int) -> list[dict]:
    itens = []
    for lin in linhas:
        if lin["deputado"] not in ids or not lin["data"]:
            continue
        itens.append({"idDeputado": ids[lin["deputado"]], "mes": int(lin["data"][5:7]), "categoria": lin["conta"], "fornecedor": None, "cnpj": None,
                      "valor": lin["valor"], "data": lin["data"], "descricao": lin["descricao"], "fonte": VERBA_PAGINA})
    return [i for i in itens if i["data"].startswith(str(ano))]


def itens_diarias(linhas: list[dict], ids: dict, ano: int) -> list[dict]:
    itens = []
    for lin in linhas:
        if lin["deputado"] not in ids or not lin["data"] or not lin["data"].startswith(str(ano)):
            continue
        itens.append({"idDeputado": ids[lin["deputado"]], "data": lin["data"], "destino": None, "motivo": lin["descricao"], "valor": lin["valor"],
                      "categoria": lin["conta"], "fonte": DIARIAS_PAGINA})
    return itens


# ---------------------------------------------------------------- verba de gabinete (SIGEP)

def parse_gabinetes(html: str) -> list[dict]:
    """[{gabinete, referencia, assessores, total}] da tabela mensal; gabinete sem o prefixo "GAB. DEP."."""
    itens = []
    for linha in re.findall(r"<tr>\s*<td>\s*GAB\..*?</tr>", html, re.S):
        celulas = [comum.limpar(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", linha, re.S)]
        if len(celulas) < 4:
            continue
        nome = re.sub(r"^GAB\.\s*(DEP\.?)?\s*", "", celulas[0])
        itens.append({"gabinete": nome, "referencia": celulas[1], "assessores": int(celulas[2]) if celulas[2].isdigit() else None,
                      "total": comum.valor_br(celulas[3])})
    return itens


def itens_gabinete(gabinetes: list[dict], ids: dict, ano: int, mes: int) -> list[dict]:
    itens = []
    for g in gabinetes:
        if g["gabinete"] not in ids or g["total"] is None:
            continue
        itens.append({"idDeputado": ids[g["gabinete"]], "mes": mes, "categoria": "Verba de gabinete (pessoal)", "fornecedor": None, "cnpj": None,
                      "valor": g["total"], "assessores": g["assessores"], "fonte": GABINETE_PAGINA})
    return itens


def consulta_gabinete(sessao, ano: int, mes: int) -> str:
    r = sessao.post(GABINETE_URL, data={"anoref": f"{ano % 100:02d}", "mes": f"{mes:02d}"}, timeout=60)
    r.raise_for_status()
    return r.text


# ---------------------------------------------------------------- coleta

def consulta_frequencia(sessao, ano: int, mes: int) -> str:
    r = sessao.post(FREQUENCIA_URL, data={"__DXCallbackName": "cbpFrequencia", "__DXCallbackArgument": "c0:", "ano": str(ano), "mes": str(mes),
                                           "tipoSessao": "0"}, timeout=60)
    r.raise_for_status()
    return r.text


def meses_ate(hoje: date):
    ano, mes = PRIMEIRO_MES
    while (ano, mes) <= (hoje.year, hoje.month):
        yield ano, mes
        ano, mes = (ano + 1, 1) if mes == 12 else (ano, mes + 1)


def coletar() -> None:
    pasta = comum.DADOS / UF
    hoje = date.today()
    agora = hoje.isoformat()
    s = comum.sessao()
    r = s.get(FREQUENCIA_URL, timeout=30)
    r.raise_for_status()
    atual = parse_cartoes(r.text)
    if not atual["deputados"]:
        comum.avisar("PA: nenhum deputado na página de frequência")
        return
    antigos = {d["id"]: d for d in (comum.ler(pasta / "deputados.json", {}).get("deputados", []))}
    deputados = []
    for d in atual["deputados"]:
        ficha = {}
        if d["id"]:
            if d["id"] in antigos and antigos[d["id"]].get("nomeCivil"):
                ficha = {"nomeCivil": antigos[d["id"]]["nomeCivil"], "email": antigos[d["id"]].get("email")}
            else:
                rf = s.get(d["ficha"], timeout=30)
                ficha = parse_ficha(rf.text) if rf.ok else {}
        deputados.append({"id": id_deputado(d), "nome": comum.nome_limpo(d["nome"]), "nomeCivil": ficha.get("nomeCivil"), "foto": d["foto"], "email": ficha.get("email"),
                          "titular": True, "partido": d["partido"], "fonte": d["ficha"] or FREQUENCIA_URL})
    comum.salvar(pasta / "deputados.json", {"fonte": FREQUENCIA_URL, "host": None, "legislatura": "2023-2027", "deputados": deputados})

    existente = comum.ler(pasta / "presenca.json", {"itens": []})["itens"]
    guardados = {i["periodo"] for i in existente}
    itens = [i for i in existente if i["periodo"] not in {f"{a}-{m:02d}" for a, m in comum.meses_recentes(hoje, MESES_RECENTES)}]
    for ano, mes in meses_ate(hoje):
        periodo = f"{ano}-{mes:02d}"
        if periodo in guardados and (ano, mes) not in comum.meses_recentes(hoje, MESES_RECENTES):
            continue
        pagina = parse_cartoes(consulta_frequencia(s, ano, mes))
        if pagina["totalSessoes"]:
            itens += itens_presenca(pagina, ano, mes)
    itens.sort(key=lambda i: (i["periodo"], str(i["idDeputado"])))
    comum.salvar(pasta / "presenca.json", {"coletadoEm": agora, "fonte": FREQUENCIA_URL, "itens": itens})
    print(f"PA: presença {len(itens)} registros")

    for ano in range(PRIMEIRO_ANO, hoje.year + 1):
        if all(comum.ano_encerrado(ano, hoje, pasta / f"{nome}_{ano}.json") for nome in ("verbas", "diarias")):
            continue
        linhas = linhas_dashboard(consulta_dashboard(s, DASHBOARD_VERBA, ano))
        verba = itens_verba(linhas, ligar({lin["deputado"] for lin in linhas}, deputados), ano)
        gabinete = []
        for mes in range(1, 13 if ano < hoje.year else hoje.month + 1):
            gabs = parse_gabinetes(consulta_gabinete(s, ano, mes))
            gabinete += itens_gabinete(gabs, ligar({g["gabinete"] for g in gabs}, deputados), ano, mes)
        comum.salvar(pasta / f"verbas_{ano}.json", {"coletadoEm": agora, "fonte": VERBA_PAGINA, "itens": verba + gabinete})
        linhas = linhas_dashboard(consulta_dashboard(s, DASHBOARD_DIARIAS, ano))
        diarias = itens_diarias(linhas, ligar({lin["deputado"] for lin in linhas}, deputados), ano)
        comum.salvar(pasta / f"diarias_{ano}.json", {"coletadoEm": agora, "fonte": DIARIAS_PAGINA, "itens": diarias})
        print(f"PA: {ano} verbas {len(verba)} + gabinete {len(gabinete)}, diárias {len(diarias)}")
    print(f"PA: {len(deputados)} deputados")


# ---------------------------------------------------------------- contratos

def _recortar_cartoes(html: str, n: int = 2) -> str:
    inicio = html.index("<h3 class='sub-title'>")
    blocos = [m.start() for m in re.finditer(r'<div id="cardView_DXDataCard\d+"', html)]
    fim = html.index("</table>", blocos[n - 1]) if len(blocos) >= n else len(html)
    fim = blocos[n] if len(blocos) > n else fim
    return html[inicio:fim]


def _contrato_frequencia(ctx):
    s = comum.sessao()
    r = s.get(FREQUENCIA_URL, timeout=30)
    r.raise_for_status()
    return {"trecho": _recortar_cartoes(r.text)}


def _conferir_frequencia(registro):
    pagina = parse_cartoes(registro["trecho"])
    falhas = []
    if not pagina["totalSessoes"] and pagina["totalSessoes"] != 0:
        falhas.append("sem 'Total de sessões'")
    if not pagina["deputados"]:
        falhas.append("nenhum cartão de deputado")
    for d in pagina["deputados"]:
        falhas += comum.campos_vazios(d, ("id", "nome", "partido", "foto", "presente", "ausente"), "deputado", vazios=(None,))
    return falhas, []


def _contrato_ficha(ctx):
    s = comum.sessao()
    r = s.get(FICHA_URL.format(1024), timeout=30)
    r.raise_for_status()
    i = r.text.index("Nome completo")
    return {"trecho": r.text[max(i - 400, 0): i + 600], "email": re.search(r"mailto:[^\"']+", r.text).group(0)}


def _conferir_ficha(registro):
    ficha = parse_ficha(registro["trecho"] + registro["email"])
    return [f"ficha sem {k}" for k, v in ficha.items() if not v], []


def _contrato_dashboard(dashboard):
    def buscar(ctx):
        s = comum.sessao()
        return {"DataStorageDTO": recortar_dto(consulta_dashboard(s, dashboard, date.today().year))}
    return buscar


def _conferir_dashboard(registro):
    linhas = linhas_dashboard(registro["DataStorageDTO"])
    falhas = [] if linhas else ["grade do dashboard sem linhas"]
    for lin in linhas:
        falhas += comum.campos_vazios(lin, ("data", "deputado", "descricao", "valor"), "linha", vazios=(None, ""))
    return falhas, []


def _contrato_gabinete(ctx):
    s = comum.sessao()
    hoje = date.today()
    ano, mes = mes_anterior(hoje.year, hoje.month)
    html = consulta_gabinete(s, ano, mes)
    linhas = re.findall(r"<tr>\s*<td>\s*GAB\..*?</tr>", html, re.S)
    inicio = html.index("<thead>")
    fim = html.index("</tbody>")
    corpo = "".join(linhas[:2])
    return {"html": html[inicio:html.index("<tbody>") + 7] + corpo + html[fim:fim + 8]}


def _conferir_gabinete(registro):
    itens = parse_gabinetes(registro["html"])
    falhas = [] if itens else ["tabela de verba de gabinete sem linhas"]
    for i in itens:
        falhas += comum.campos_vazios(i, ("gabinete", "referencia", "assessores", "total"), "gabinete", vazios=(None,))
    return falhas, []


CONTRATOS = [
    {"nome": "estadual_pa_frequencia", "fonte": FREQUENCIA_URL, "buscar": _contrato_frequencia, "html": _conferir_frequencia},
    {"nome": "estadual_pa_ficha", "fonte": FICHA_URL.format(1024), "buscar": _contrato_ficha, "html": _conferir_ficha},
    {"nome": "estadual_pa_verba_indenizatoria", "fonte": VERBA_PAGINA, "buscar": _contrato_dashboard(DASHBOARD_VERBA), "html": _conferir_dashboard},
    {"nome": "estadual_pa_diarias", "fonte": DIARIAS_PAGINA, "buscar": _contrato_dashboard(DASHBOARD_DIARIAS), "html": _conferir_dashboard},
    {"nome": "estadual_pa_verba_gabinete", "fonte": GABINETE_PAGINA, "buscar": _contrato_gabinete, "html": _conferir_gabinete},
]


if __name__ == "__main__":
    comum.principal(coletar)
