"""
Deputados estaduais do Pará (ALEPA), fora do SAPL.

Fontes lidas aqui (todas abertas, sem login):
  - deputados em exercício, partido, foto, ficha, presença: https://alepa.pa.gov.br/Transparencia/FrequenciaSessoes
    (cartões HTML por deputado; o filtro Ano/Mês é um callback DevExpress que o `requests` reproduz com
    __DXCallbackName=cbpFrequencia, __DXCallbackArgument=c0:, ano, mes, tipoSessao); ficha em /Institucional/Deputado/<id>
  - verba indenizatória (liquidações) e diárias dos parlamentares: dashboards DevExpress em alepa.quartertec.com.br
    (dashboard57 e dashboard58), lidos pela API GET /api/dashboard/data
  - verba de gabinete (total mensal por gabinete): https://sigep.alepa.pa.gov.br/transp/frame_verbagabinete.php

Gabinete (servidores ativos lotados em "GAB. DEP. <nome>", sem valores): CSV do SIGEP,
https://sigep.alepa.pa.gov.br/transp/downloadcsvpessoal.php?nb=&cb=&lt=GAB.+DEP. (a tela frame_relacaopessoal.php corta em 100 linhas por
página; o CSV traz todos os gabinetes numa requisição). Remuneração mensal do deputado: frame_servidores.php (filtro por nome, ano e mês; a
lista traz um link com tokens por linha para detalhecc.php, usado como veio), só linhas de cargo DEPUTADO ESTADUAL, ligadas por nome.

Só PDF ou fora do alcance (não coletado): estrutura remuneratória dos deputados (PDF), remuneração dos demais servidores, emendas estaduais (portal do Estado em www.sistemas.pa.gov.br), projetos (a lista de proposições só devolve 10 por
chamada e o pager não se reproduz).

Voto nominal por deputado: https://alepa.pa.gov.br/Legislativo/VotacoesNominais. O filtro é um callback DevExpress
(POST /Legislativo/CallbackPanelVotacoesNominais, __DXCallbackName=cbpPautas, ano e mes; o mes é obrigatório e o cookie vem do GET da
página) com uma linha por proposição e turno; o detalhe (GET /Legislativo/DetalhesVotacaoNominal?IdProposicao=&IdVotacao=) lista nome e
partido por voto (SIM, NÃO, ABSTENÇÃO, NÃO VOTARAM), sem id de deputado: a ligação é por nome (`identidades.ligar_nomes`, UF PA).
Leitura incremental: mês encerrado vem do arquivo; só os MESES_RECENTES últimos e os meses que faltam são listados de novo, e só
votação ainda não lida baixa o detalhe.

Normas legais (catálogo, sem autoria nem data): https://bancodeleis.alepa.pa.gov.br/api/leis.php?ano=&tipo=&numero=&q= (no máximo 50 por
chamada, `numero` casa por trecho; resposta cheia é partida por dígitos). Pautas e atas (links): callbacks mensais
/Legislativo/CallbackPanelPautas e CallbackPanelAtas. Contratos (dashboard52) e licitações (dashboard59, filtradas por "registro de
preços" no objeto) do órgão: alepa.quartertec.com.br, sem CNPJ (o nome vem como está, sem ligação a fornecedor).
"""

import csv
import io
import json
import re
import time
from datetime import date
from html import unescape
from functools import partial

import estaduais_comum as comum
import identidades
import ids

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
PAUSA = 1.0
VOTACOES_PAGINA = f"{ALEPA}/Legislativo/VotacoesNominais"
VOTACOES_LISTA_URL = f"{ALEPA}/Legislativo/CallbackPanelVotacoesNominais"
VOTACAO_URL = f"{ALEPA}/Legislativo/DetalhesVotacaoNominal?IdProposicao={{}}&IdVotacao={{}}"
FONTE_ID = "alepa_pa"
SIGEP = "https://sigep.alepa.pa.gov.br/transp"
SERVIDORES_BASE = f"{SIGEP}/"
PESSOAL_PAGINA = f"{SIGEP}/frame_relacaopessoal.php"
GABINETE_CSV_URL = f"{SIGEP}/downloadcsvpessoal.php"
SERVIDORES_URL = SERVIDORES_PAGINA = f"{SIGEP}/frame_servidores.php"
LOTACAO_GABINETE = re.compile(r"^\s*\d*\s*-?\s*GAB\.?\s*DEP\.?\s+(.+)$", re.I)
PRIMEIRO_MES_REMUNERACAO = (2026, 1)
PAGINAS_BUSCA = 3
MAX_TERMOS = 4
TITULOS_BUSCA = {"dr", "dra", "deleg", "delegado", "delegada", "coronel", "prof", "profa", "dep", "deputado", "deputada", "filho", "junior", "neto"}
PRIMEIRO_ANO_LEGISLATIVO = 2025   # normas, pautas e atas: só do ano anterior ao atual em diante
NORMAS_API = "https://bancodeleis.alepa.pa.gov.br/api/leis.php"
NORMAS_PAGINA = f"{ALEPA}/Home/Page/BancodeLeis"
NORMAS_TIPOS = (1, 2, 3, 4, 10, 11, 12)
NORMAS_LIMITE = 50
NORMAS_RELER_DIAS = 7
NORMAS_PAUSA = 1.0
PAUTAS = {"ordem-do-dia": (f"{ALEPA}/Legislativo/Pautas", f"{ALEPA}/Legislativo/CallbackPanelPautas", "cbpPautas"),
          "atas": (f"{ALEPA}/Legislativo/Atas", f"{ALEPA}/Legislativo/CallbackPanelAtas", "cbpAtas")}
CONTRATOS_PAGINA = f"{ALEPA}/Transparencia/Page/Contratos"
LICITACOES_PAGINA = f"{ALEPA}/Transparencia/Page/Licitacoes"
DASHBOARD_CONTRATOS, DASHBOARD_LICITACOES = ("dashboard52", "gridDashboardItem1"), ("dashboard59", "gridDashboardItem2")
VOTOS_PA = {"SIM": "sim", "NAO": "não", "ABSTENCAO": "abstenção", "NAO VOTARAM": "não votou"}
SIGLAS = {"PROJETO DE LEI": "PL", "PROJETO DE LEI COMPLEMENTAR": "PLC", "PROJETO DE DECRETO LEGISLATIVO": "PDL", "PROJETO DE RESOLUCAO": "PRE",
          "PROPOSTA DE EMENDA A CONSTITUICAO": "PEC", "VETO": "VET"}


ligar = partial(identidades.ligar_nomes, uf=UF)


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
        deputados.append({"id": link.group(1) if link else None, "nome": nome, "partido": comum.sigla_partido(partido),
                          "foto": foto.group(1).replace("\\", "/").split("?")[0].replace(" ", "%20") if foto else None,
                          "ficha": FICHA_URL.format(link.group(1)) if link else None,
                          "presente": contagens.get("Presente"), "licenciado": contagens.get("Licenciado"), "ausente": contagens.get("Ausente")})
    return {"totalSessoes": int(total.group(1)) if total else None, "deputados": deputados}


def parse_ficha(html: str) -> dict:
    civil = re.search(r"Nome completo:\s*(?:<[^>]+>\s*)*([^<]+)", html)
    email = re.search(r"mailto:([^\"'>\s]+)", html)
    return {"nomeCivil": " ".join(unescape(civil.group(1)).split()) if civil else None, "email": comum.email(email.group(1)) if email else None}


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
            linhas.append({"data": comum.data_iso(r.get("DataItem1")) or "", "deputado": r.get("DataItem0"), "conta": r.get("DataItem5"),
                           "descricao": r.get("DataItem2"), "valor": comum.valor_br(valor)})
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


# ---------------------------------------------------------------- gabinete e remuneração (SIGEP)

def texto_resposta(r) -> str:
    """Corpo em UTF-8 (o SIGEP não informa o charset das páginas e o `requests` erra a detecção)."""
    return r.content.decode("utf-8-sig", errors="replace")


def pedir(sessao, metodo: str, url: str, **kw) -> str:
    time.sleep(PAUSA)
    r = getattr(sessao, metodo.lower())(url, timeout=60, **kw)
    r.raise_for_status()
    return texto_resposta(r)


def parse_pessoal_csv(texto: str) -> list[dict]:
    """[{matricula, nome, cargo, classificacao, lotacao, situacao}] do CSV `downloadcsvpessoal.php` (Matricula;Nome;Admissao;Exoneracao;
    Cargo/Funcao;Classificacao;Lotacao;Situacao). Datas de admissão e exoneração não são lidas."""
    linhas = csv.reader(io.StringIO(texto), delimiter=";")
    cabecalho = next(linhas, [])
    posicao = {comum.sem_acento(c).lower().strip(): i for i, c in enumerate(cabecalho)}
    faltam = [c for c in ("matricula", "nome", "cargo/funcao", "lotacao", "situacao") if c not in posicao]
    if faltam:
        raise RuntimeError(f"CSV de pessoal sem as colunas {', '.join(faltam)}")

    def campo(l, nome):
        i = posicao.get(nome)
        return comum.compactar(l[i]) if i is not None and i < len(l) else None

    return [{"matricula": campo(l, "matricula"), "nome": campo(l, "nome"), "cargo": campo(l, "cargo/funcao"), "classificacao": campo(l, "classificacao"),
             "lotacao": campo(l, "lotacao"), "situacao": campo(l, "situacao")} for l in linhas if l]


def simbolo_do_cargo(cargo: str | None) -> str | None:
    """"FUNCAO PUB. APOIO LEGISLATIVO FPAL-04" -> "FPAL-04"; sem símbolo no fim, o cargo inteiro."""
    m = re.search(r"([A-Z]+-[\d.]+)$", cargo or "")
    return m.group(1) if m else cargo


def servidores_do_gabinete(linhas: list[dict], deputados: list[dict]) -> list[dict]:
    """Servidores ativos lotados em "<código> - GAB. DEP. <nome>". O gabinete só vale se a lotação liga a um único deputado (`ligar`);
    gabinete de ex-deputado, liderança e diretoria ficam de fora. Sem valores nem datas: o id sai da matrícula que a fonte publica."""
    gabinete = {}
    for l in linhas:
        m = LOTACAO_GABINETE.match(l["lotacao"] or "")
        if m and m.group(1).strip():
            gabinete[l["lotacao"]] = m.group(1).strip()
    ligados = ligar(set(gabinete.values()), deputados)
    itens = {}
    for l in linhas:
        id_dep = ligados.get(gabinete.get(l["lotacao"]))
        if not id_dep or not l["matricula"] or not l["nome"] or (l["situacao"] or "").lower() != "ativo":
            continue
        iid = ids.gerar_id("srv", f"{FONTE_ID}_sigep", l["matricula"])
        itens[iid] = {"id": iid, "idDeputado": id_dep, "matricula": l["matricula"], "nome": l["nome"], "simbolo": simbolo_do_cargo(l["cargo"]) or l["classificacao"]}
    return sorted(itens.values(), key=lambda i: (i["idDeputado"], i["simbolo"] or "", i["nome"], i["matricula"]))


def coletar_gabinete(s, pasta, deputados: list[dict], agora: str) -> None:
    """Uma só requisição devolve todos os gabinetes (a tela HTML corta em 100 por página; o CSV vem inteiro)."""
    linhas = parse_pessoal_csv(pedir(s, "GET", GABINETE_CSV_URL, params={"nb": "", "cb": "", "lt": "GAB. DEP."}))
    itens = servidores_do_gabinete(linhas, deputados)
    if not itens:
        raise RuntimeError("nenhum servidor ligado a gabinete de deputado; mantém o arquivo anterior")
    comum.salvar(pasta / "gabinete.json", {"coletadoEm": agora, "fonte": PESSOAL_PAGINA, "itens": itens})
    print(f"PA: gabinetes {len(itens)} servidores de {len({i['idDeputado'] for i in itens})} deputados")


def ultimo_mes_publicado(html: str) -> tuple[int, int]:
    """(ano, mês) que a tela de servidores oferece primeiro: o mais recente com folha publicada."""
    ano = re.search(r'<select[^>]*name="anoref".*?<option value="(\d\d)"', html, re.S)
    mes = re.search(r'<select[^>]*name="mes".*?<option value="(\d\d)"', html, re.S)
    if not ano or not mes:
        raise RuntimeError("tela de servidores sem os filtros de ano e mês")
    return 2000 + int(ano.group(1)), int(mes.group(1))


def parse_servidores(html: str) -> tuple[list[dict], list[str]]:
    """([{matricula, nome, cargo, lotacao, detalhe}], links das outras páginas do resultado). Os links levam tokens da sessão: usar como vieram."""
    linhas = []
    padrao = r'<td>\s*(\d+)\s*</td>\s*<td>\s*<a href="(detalhecc\.php[^"]+)">(.*?)</a>\s*</td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>'
    for matricula, href, nome, cargo, lotacao in re.findall(padrao, html, re.S):
        linhas.append({"matricula": matricula, "nome": comum.limpar(nome), "cargo": comum.limpar(cargo), "lotacao": comum.limpar(lotacao), "detalhe": unescape(href)})
    paginas = [unescape(h) for h in re.findall(r"<a href='(/transp/frame_servidores\.php\?[^']*pg=\d+)'", html)]
    return linhas, list(dict.fromkeys(paginas))


def parse_detalhe(html: str) -> dict:
    """{ano, mes, valores:{rótulo sem acento em minúsculas: valor}} da folha de um servidor (CPF mascarado e demais dados pessoais não são lidos)."""
    periodo = re.search(r"Rendimentos,\s*([^/<\s]+)\s*/\s*(\d{4})", html)
    valores = {}
    for rotulo, valor in re.findall(r"<td[^>]*>([^<]*[A-Za-z][^<]*)</td>\s*<td[^>]*>&nbsp;</td>\s*<td[^>]*>\s*(R\$[^<]*)</td>", html):
        valores[comum.sem_acento(comum.limpar(rotulo)).lower()] = comum.valor_br(comum.limpar(valor))
    mes = comum.MESES.get(comum.sem_acento(periodo.group(1)).lower()) if periodo else None
    return {"ano": int(periodo.group(2)) if periodo else None, "mes": mes, "valores": valores}


def componentes_remuneracao(valores: dict) -> dict:
    rotulos = (("remuneracao", "Remuneração"), ("ferias", "Férias"), ("adiantamento de 13o", "Adiantamento de 13º"), ("pecunia", "Pecúnia"),
               ("descontos", "Descontos"), ("redutor cosntitucional", "Redutor Constitucional"), ("redutor constitucional", "Redutor Constitucional"))
    saida = {}
    for chave, rotulo in rotulos:
        if valores.get(chave):
            saida[rotulo] = valores[chave]
    return saida


def com_nome_civil_tse(deputados: list[dict]) -> list[dict]:
    """A folha traz o nome civil, que a ficha da Assembleia nem sempre dá certo ("Maria do Carmo Maria Martins"): o nome do TSE
    (eleito de 2022 que `identidades.eleito_do_tse` acha pelo nome de urna) vale primeiro."""
    eleitos = comum.eleitos_tse(comum.arquivo_tse(UF))
    saida = []
    for d in deputados:
        e = identidades.eleito_do_tse(UF, d["nome"], eleitos) if eleitos else None
        saida.append({**d, "nomeCivil": e["nome"]} if e else d)
    return saida


def termos_de_busca(d: dict) -> list[str]:
    """Textos para o filtro de nome (sem acento, o banco da fonte não casa acento): nome civil, nome parlamentar e, por fim, as palavras do nome."""
    inteiros = [comum.sem_acento(n).upper() for n in (d.get("nomeCivil"), d.get("nome")) if n]
    palavras = sorted({p for n in inteiros for p in n.split() if len(p) >= 4 and p.lower() not in TITULOS_BUSCA}, key=lambda p: (-len(p), p))
    return list(dict.fromkeys(inteiros + palavras))[:MAX_TERMOS]


def buscar_do_cargo(sessao, ano: int, mes: int, termo: str) -> list[dict]:
    """Linhas de cargo DEPUTADO ESTADUAL que o filtro de nome devolve (segue as páginas do resultado, no máximo PAGINAS_BUSCA)."""
    html = pedir(sessao, "POST", SERVIDORES_URL, data={"anoref": f"{ano % 100:02d}", "mes": f"{mes:02d}", "b_nome": termo})
    linhas, paginas = parse_servidores(html)
    for link in paginas[: PAGINAS_BUSCA - 1]:
        if any(l["cargo"] == "DEPUTADO ESTADUAL" for l in linhas):
            break
        linhas += parse_servidores(pedir(sessao, "GET", "https://sigep.alepa.pa.gov.br" + link))[0]
    return [l for l in linhas if l["cargo"] == "DEPUTADO ESTADUAL"]


def remuneracao_do_mes(sessao, ano: int, mes: int, deputados: list[dict], buscas: dict) -> list[dict]:
    """Folha do mês de cada deputado: acha a linha pelo nome (nome civil primeiro; o termo que deu certo fica em `buscas` para o mês
    seguinte), liga o nome ao deputado (`ligar`) e abre o detalhe pelo link da lista."""
    achadas: dict = {}
    ligados: dict = {}
    for d in deputados:
        if d["id"] in ligados.values():
            continue
        termos = termos_de_busca(d)
        if buscas.get(d["id"]) in termos:
            termos.remove(buscas[d["id"]])
            termos.insert(0, buscas[d["id"]])
        for termo in termos:
            achadas |= {l["matricula"]: l for l in buscar_do_cargo(sessao, ano, mes, termo)}
            ligados = ligar({l["nome"] for l in achadas.values()}, deputados)
            if d["id"] in ligados.values():
                buscas[d["id"]] = termo
                break
    por_nome = {l["nome"]: l for l in achadas.values()}
    ligacao = ligar(set(por_nome), deputados)
    itens, sem_linha = [], []
    for d in deputados:
        nome = next((n for n, id_dep in ligacao.items() if id_dep == d["id"]), None)
        if not nome:
            sem_linha.append(d["nome"])
            continue
        folha = parse_detalhe(pedir(sessao, "GET", SERVIDORES_BASE + por_nome[nome]["detalhe"]))
        v = folha["valores"]
        if (folha["ano"], folha["mes"]) != (ano, mes) or v.get("total bruto") is None:
            sem_linha.append(d["nome"])
            continue
        itens.append({"idDeputado": d["id"], "mes": mes, "bruto": v.get("total bruto"), "liquido": v.get("total liquido"),
                      "componentes": componentes_remuneracao(v), "fonte": SERVIDORES_PAGINA})
    if sem_linha and itens:
        comum.avisar(f"PA: remuneração {ano}-{mes:02d} sem linha de deputado para: {', '.join(sorted(sem_linha))}")
    return sorted(itens, key=lambda i: i["idDeputado"])


def coletar_remuneracao(s, pasta, deputados: list[dict], hoje: date, agora: str) -> None:
    """remuneracao_<ano>.json com a folha mensal de cada deputado. Mês já lido fora dos MESES_RECENTES (contados do último publicado) vem
    do arquivo; ano encerrado não é relido. Grava ao fim de cada mês, então o prazo da coleta só adia os meses seguintes."""
    deputados = com_nome_civil_tse(deputados)
    ultimo = ultimo_mes_publicado(pedir(s, "GET", SERVIDORES_URL))
    recentes = comum.meses_recentes(date(ultimo[0], ultimo[1], 1), MESES_RECENTES)
    anteriores = sorted(pasta.glob("remuneracao_[0-9]*.json"))
    buscas = dict(comum.ler(anteriores[-1], {}).get("buscas") or {}) if anteriores else {}
    for ano in range(PRIMEIRO_MES_REMUNERACAO[0], ultimo[0] + 1):
        arq = pasta / f"remuneracao_{ano}.json"
        if comum.ano_encerrado(ano, hoje, arq):
            continue
        anterior = comum.ler(arq, {})
        itens, lidos = list(anterior.get("itens") or []), dict(anterior.get("meses") or {})
        for mes in range(1, 13):
            periodo = f"{ano}-{mes:02d}"
            if (ano, mes) < PRIMEIRO_MES_REMUNERACAO or (ano, mes) > ultimo or (periodo in lidos and (ano, mes) not in recentes):
                continue
            novos = remuneracao_do_mes(s, ano, mes, deputados, buscas)
            if not novos:
                raise RuntimeError(f"folha de {periodo} sem nenhum deputado; mantém o arquivo anterior")
            itens = sorted([i for i in itens if i["mes"] != mes] + novos, key=lambda i: (i["mes"], i["idDeputado"]))
            lidos[periodo] = agora
            comum.salvar(arq, {"coletadoEm": agora, "fonte": SERVIDORES_PAGINA, "meses": lidos, "buscas": dict(sorted(buscas.items())), "itens": itens})
            print(f"PA: remuneração {periodo} {len(novos)} deputados")


# ---------------------------------------------------------------- voto nominal

def parse_lista_votacoes(html: str) -> list[dict]:
    """[{idProposicao, idVotacao, data, titulo}] do mês, sem repetir (cada cartão tem também os links de download)."""
    itens = {}
    padrao = r"<a class='pauta-item-title' href='/Legislativo/DetalhesVotacaoNominal\?IdProposicao=(\d+)&(?:amp;)?IdVotacao=(\d+)'>(.*?)</a>"
    for m in re.finditer(padrao, html, re.S):
        texto = comum.limpar(m.group(3))
        d = re.match(r"(\d{2}/\d{2}/\d{4})\s*-\s*(.*)", texto)
        itens[(m.group(1), m.group(2))] = {"idProposicao": m.group(1), "idVotacao": m.group(2),
                                           "data": comum.data_br_iso(d.group(1)) if d else None, "titulo": d.group(2) if d else texto}
    return list(itens.values())


def parse_votacao(html: str) -> dict:
    """{sessaoTipo, sessaoNumero, projeto, data, autor, turno, resultado, votos:{SIM:[[nome, partido]]...}, quantidades:{SIM:n...}}."""
    campos = {comum.sem_acento(comum.limpar(k)).lower(): comum.limpar(v) for k, v in re.findall(r"<td><strong>(.*?):</strong>(.*?)</td>", html, re.S)}
    votos, quantidades = {}, {}
    partes = re.split(r'<div class="section-title">(.*?)</div>', html)
    for rotulo, corpo in zip(partes[1::2], partes[2::2], strict=False):
        chave = comum.sem_acento(comum.limpar(rotulo)).upper()
        itens = [comum.limpar(x) for x in re.findall(r'<div class="voto-item">(.*?)</div>', corpo, re.S)]
        votos[chave] = [[itens[i], itens[i + 1] if i + 1 < len(itens) else None] for i in range(0, len(itens), 2)]
        q = re.search(r"Quantidade:\s*(\d+)", corpo)
        quantidades[chave] = int(q.group(1)) if q else None
    return {"sessaoTipo": campos.get("tipo"), "sessaoNumero": campos.get("numero"), "projeto": campos.get("projeto"),
            "data": comum.data_br_iso(campos.get("data")), "autor": campos.get("autor"),
            "turno": campos.get("turno"), "resultado": campos.get("resultado"), "votos": votos, "quantidades": quantidades}


def aprovada(resultado: str | None) -> bool | None:
    r = comum.sem_acento(resultado or "").upper()
    if r.startswith(("NAO APROV", "REJEIT", "REPROV", "PREJUDIC", "DERROT")):
        return False
    if r.startswith("APROV"):
        return True
    return None


def materia_votada(projeto: str | None, turno: str | None) -> dict:
    """{tipo, tipoDescricao, numero, ano, ementa} do texto "PROJETO DE LEI COMPLEMENTAR N º 10/2026" e do turno."""
    texto = " ".join((projeto or "").split())
    m = re.match(r"(.*?)\s+N\s*[º°o]?\s*(\d+)/(\d{4})$", texto)
    tipo = (m.group(1) if m else texto).strip()
    chave = comum.sem_acento(tipo).upper()
    sigla = SIGLAS.get(chave) or "".join(w[0] for w in chave.split() if len(w) > 2) or "VOT"
    return {"tipo": sigla, "tipoDescricao": tipo.capitalize() + (f" ({turno.lower()})" if turno else ""),
            "numero": int(m.group(2)) if m else None, "ano": int(m.group(3)) if m else None, "ementa": None}


def votacao_gravada(lido: dict, item: dict, ligacao: dict) -> tuple[str, dict, dict]:
    """(id, votação, matéria votada) de uma votação lida; o voto de nome sem deputado ligado não é gravado."""
    vid = ids.gerar_id("vot", FONTE_ID, f"{item['idProposicao']}|{item['idVotacao']}")
    votos = [[ligacao[n], VOTOS_PA[rotulo]] for rotulo, lista in lido["votos"].items() if rotulo in VOTOS_PA for n, _ in lista if n in ligacao]
    q = lido["quantidades"]
    contagem = {k: q.get(rotulo) if q.get(rotulo) is not None else len(lido["votos"].get(rotulo, []))
                for k, rotulo in (("sim", "SIM"), ("nao", "NAO"), ("abstencoes", "ABSTENCAO"))}
    votacao = {"data": lido["data"] or item["data"], "idMateria": vid, "aprovada": aprovada(lido["resultado"]), "resultado": lido["resultado"], **contagem,
               "votos": sorted(votos, key=lambda v: str(v[0])), "fonte": VOTACAO_URL.format(item["idProposicao"], item["idVotacao"]),
               "idProposicao": item["idProposicao"], "idVotacao": item["idVotacao"], "turno": lido["turno"], "autor": lido["autor"],
               "sessao": " ".join(x for x in (lido["sessaoTipo"], lido["sessaoNumero"]) if x) or None}
    return vid, votacao, materia_votada(lido["projeto"] or item["titulo"], lido["turno"])


def consulta_lista_votacoes(sessao, ano: int, mes: int) -> str:
    r = sessao.post(VOTACOES_LISTA_URL, data={"__DXCallbackName": "cbpPautas", "__DXCallbackArgument": "c0:", "ano": str(ano), "mes": str(mes)}, timeout=60)
    r.raise_for_status()
    return r.text


def consulta_votacao(sessao, item: dict) -> str:
    r = sessao.get(VOTACAO_URL.format(item["idProposicao"], item["idVotacao"]), timeout=60)
    r.raise_for_status()
    return r.text


def votacoes_dos_meses(sessao, deputados: list[dict], arquivo: dict, hoje: date, salvar_parcial=None) -> tuple[dict, dict, dict]:
    """(votações, matérias votadas, estado por mês) juntando o que o arquivo já tinha. Mês já lido fora dos MESES_RECENTES não é
    listado de novo; votação já lida (ou sem lista nominal) não baixa o detalhe. `salvar_parcial(votações, matérias, estado)` roda
    ao fim de cada mês."""
    votacoes, materias = dict(arquivo.get("votacoes") or {}), dict(arquivo.get("materias") or {})
    estado = dict(arquivo.get("meses") or {})
    recentes = comum.meses_recentes(hoje, MESES_RECENTES)
    sem_par: set = set()
    sessao.get(VOTACOES_PAGINA, timeout=30).raise_for_status()
    for ano, mes in meses_ate(hoje):
        periodo = f"{ano}-{mes:02d}"
        if periodo in estado and (ano, mes) not in recentes:
            continue
        lidas = set(estado.get(periodo, {}).get("lidas", []))
        novos = []
        for item in parse_lista_votacoes(consulta_lista_votacoes(sessao, ano, mes)):
            chave = f"{item['idProposicao']}|{item['idVotacao']}"
            if chave not in lidas:
                time.sleep(PAUSA)
                novos.append((chave, item, parse_votacao(consulta_votacao(sessao, item))))
        ligacao = ligar({n for _, _, lido in novos for lista in lido["votos"].values() for n, _ in lista}, deputados)
        for chave, item, lido in novos:
            lidas.add(chave)
            if not any(lido["votos"].get(r) for r in VOTOS_PA):
                continue
            sem_par |= {n for lista in lido["votos"].values() for n, _ in lista if n not in ligacao}
            vid, votacao, materia = votacao_gravada(lido, item, ligacao)
            votacoes[vid], materias[vid] = votacao, materia
        estado[periodo] = {"lidoEm": hoje.isoformat(), "lidas": sorted(lidas)}
        if salvar_parcial:
            salvar_parcial(votacoes, materias, estado)
    if sem_par:
        comum.avisar(f"PA: votos de nomes sem deputado ligado (não gravados): {', '.join(sorted(sem_par))}")
    return votacoes, materias, estado


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


def coletar_catalogos(s, pasta, hoje: date) -> None:
    """Normas legais, pautas e atas e contratos do órgão: não dependem da lista de deputados."""
    agora = hoje.isoformat()

    def pautas(ano):
        arq = pasta / f"pautas_{ano}.json"
        anterior = comum.ler(arq, {})
        itens, meses = pautas_do_ano(s, ano, hoje, anterior)
        comum.salvar(arq, {"coletadoEm": agora, "fonte": f"{ALEPA}/Legislativo/Pautas", "meses": meses, "itens": itens})
        print(f"PA: {ano} pautas e atas {len(itens)}")

    def normas_legais(ano):
        arq = pasta / f"leis_{ano}.json"
        anterior = comum.ler(arq, {})
        recente = anterior.get("coletadoEm") and (hoje - date.fromisoformat(anterior["coletadoEm"])).days < NORMAS_RELER_DIAS
        if anterior.get("normas") and (ano < hoje.year - 1 or recente):
            return
        achadas = normas_do_ano(s, ano)
        if not achadas and anterior.get("normas"):
            raise RuntimeError(f"banco de leis devolveu lista vazia para {ano}; mantém o arquivo anterior")
        comum.salvar(arq, {"coletadoEm": agora, "fonte": NORMAS_PAGINA, "normas": achadas})
        print(f"PA: {ano} normas {len(achadas)}")

    def orgao():
        itens = itens_contratos(celulas_grade(consulta_grade(s, DASHBOARD_CONTRATOS)))
        n_contratos = len(itens)
        itens |= itens_atas_registro(celulas_grade(consulta_grade(s, DASHBOARD_LICITACOES)))
        por_ano = orgao_por_ano(itens)
        if not por_ano and any(pasta.glob("orgao_[0-9]*.json")):
            raise RuntimeError("dashboards devolveram lista vazia; mantém os arquivos anteriores")
        for ano, lista in por_ano.items():
            comum.salvar(pasta / f"orgao_{ano}.json", {"coletadoEm": agora, "fonte": CONTRATOS_PAGINA, "itens": lista})
        print(f"PA: contratos {n_contratos} e atas de registro {len(itens) - n_contratos} do órgão em {len(por_ano)} anos")

    for ano in range(PRIMEIRO_ANO_LEGISLATIVO, hoje.year + 1):
        comum.tentar(UF, f"pautas e atas {ano}", partial(pautas, ano))
        comum.tentar(UF, f"normas {ano}", partial(normas_legais, ano))
    comum.tentar(UF, "contratos e atas de registro do órgão", orgao)


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
        coletar_catalogos(s, pasta, hoje)
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
    comum.tentar(UF, "gabinete", partial(coletar_gabinete, s, pasta, deputados, agora))
    comum.tentar(UF, "remuneração", partial(coletar_remuneracao, s, pasta, deputados, hoje, agora))

    def votacoes():
        arq = pasta / "votacoes.json"
        anterior = {**comum.ler(arq, {}), "materias": comum.ler(pasta / "materias_votadas.json", {})}

        def gravar(votos, materias, estado):
            comum.salvar(arq, {"coletadoEm": agora, "fonte": VOTACOES_PAGINA, "meses": estado, "votacoes": votos})
            comum.salvar(pasta / "materias_votadas.json", materias)

        votos, _, estado = votacoes_dos_meses(s, deputados, anterior, hoje, gravar)
        print(f"PA: votações {len(votos)} em {len(estado)} meses")

    comum.tentar(UF, "votações", votacoes)
    coletar_catalogos(s, pasta, hoje)


# ---------------------------------------------------------------- normas legais, pautas e atas, contratos do órgão

def consulta_grade(sessao, dashboard: tuple[str, str]) -> dict:
    """Grade inteira de um dashboard sem parâmetros nem filtro (contratos e licitações do órgão)."""
    r = sessao.get(DASHBOARD_URL, params={"dashboardId": dashboard[0], "parameters": "[]", "itemId": dashboard[1], "query": "{}"}, timeout=60)
    r.raise_for_status()
    return r.json()["ItemData"]["DataStorageDTO"]


def celulas_grade(dto: dict) -> list[dict]:
    """Uma linha por célula da fatia com mais dimensões: {DataItemN: valor} das dimensões e das medidas (pelo nome da medida)."""
    fatia = max(dto["Slices"], key=lambda f: len(f["KeyIds"]))
    mapas = dto["EncodeMaps"]
    linhas = []
    for chave, valores in fatia["Data"].items():
        linha = {c: mapas[c][i] for c, i in zip(fatia["KeyIds"], json.loads(chave), strict=False)}
        if isinstance(valores, dict):
            linha |= {medida: valores.get(str(pos)) for medida, pos in fatia["ValueIds"].items()}
        linhas.append(linha)
    return linhas


def modalidade_do_contrato(texto) -> tuple[str | None, str | None]:
    """"008/2026 Pregão" -> ("Pregão", "008/2026")."""
    m = re.match(r"\s*(\S+)\s+(.*\S)\s*$", str(texto or ""))
    return (m.group(2), m.group(1)) if m else (comum.compactar(texto), None)


def itens_contratos(linhas: list[dict]) -> dict:
    """{id: item} dos contratos (dashboard52); o id da fonte é o IdApFisContrato. Fiscal e gestor (servidores) ficam de fora; a grade
    não traz valor nem CNPJ."""
    itens = {}
    for lin in sorted(linhas, key=lambda x: str(x.get("DataItem5"))):
        idf = lin.get("DataItem5")
        inicio = comum.data_iso(lin.get("DataItem1"))
        if idf is None or not inicio or not comum.compactar(lin.get("DataItem4")):
            continue
        modalidade, numero_mod = modalidade_do_contrato(lin.get("DataItem3"))
        iid, item = comum.item_orgao(FONTE_ID, "contrato", idf, fornecedor_nome=lin["DataItem4"], inicio=inicio, objeto=lin.get("DataItem0"),
                                     numero=comum.compactar(lin.get("DataItem8")), fonte=CONTRATOS_PAGINA, modalidade=modalidade,
                                     numeroModalidade=numero_mod, situacao=comum.compactar(lin.get("DataItem2")), protocolo=None, diretoria=None)
        itens[iid] = item
    return itens


def itens_atas_registro(linhas: list[dict]) -> dict:
    """{id: item} das licitações do dashboard59 cujo objeto trata de registro de preços. Id da fonte: ano|modalidade|número. O valor é o
    estimado do certame; o vencedor vem só pelo nome."""
    itens, vistos = {}, set()
    for lin in sorted(linhas, key=lambda x: tuple(str(x.get(k)) for k in ("DataItem6", "DataItem0", "DataItem2", "DataItem1"))):
        objeto = comum.compactar(lin.get("DataItem1"))
        if not objeto or "REGISTRO DE PRECO" not in comum.sem_acento(objeto).upper() or not comum.compactar(lin.get("DataItem7")):
            continue
        edital = comum.data_iso(lin.get("DataItem9"))
        ano = str(lin.get("DataItem6") or "").strip()
        ano = ano if re.fullmatch(r"20\d\d", ano) else (edital or "")[:4]
        numero = comum.compactar(lin.get("DataItem2"))
        modalidade = comum.compactar(lin.get("DataItem0"))
        idf = f"{ano}|{modalidade}|{numero}"
        if not ano or not numero or not edital or idf in vistos:
            continue
        vistos.add(idf)
        valor = lin.get("DataItem11")
        iid, item = comum.item_orgao(FONTE_ID, "ata_registro", idf, fornecedor_nome=lin["DataItem7"], inicio=edital, objeto=objeto, numero=None,
                                     valor=valor if isinstance(valor, (int, float)) else None, fonte=LICITACOES_PAGINA, modalidade=modalidade,
                                     numeroModalidade=f"{numero}/{ano}", situacao=comum.compactar(lin.get("DataItem10")), protocolo=None, diretoria=None)
        itens[iid] = item
    return itens


def orgao_por_ano(itens: dict) -> dict[int, dict]:
    """{ano: {id: item}} pelo ano do início, de PRIMEIRO_ANO em diante."""
    anos = {}
    for iid, i in itens.items():
        ano = int(i["inicio"][:4])
        if ano >= PRIMEIRO_ANO:
            anos.setdefault(ano, {})[iid] = i
    return anos


def parse_norma(n: dict) -> dict | None:
    numero = comum.compactar(n.get("numero"))
    if n.get("id") is None or not numero:
        return None
    return {"tipo": comum.compactar(n.get("tipo")), "numero": numero, "ano": int(n["ano"]) if str(n.get("ano")).isdigit() else None,
            "ementa": comum.compactar(n.get("ementa")), "link": comum.compactar(n.get("link_pdf")), "fonte": NORMAS_PAGINA}


def consulta_normas(sessao, ano: int, tipo: int, numero: str = "") -> list[dict]:
    time.sleep(NORMAS_PAUSA)
    r = sessao.get(NORMAS_API, params={"ano": ano, "tipo": tipo, "numero": numero, "q": ""}, timeout=60)
    r.raise_for_status()
    j = r.json()
    if not j.get("status"):
        raise RuntimeError(f"leis.php ano={ano} tipo={tipo} numero={numero}: status falso")
    return j.get("resultados") or []


def normas_do_tipo(sessao, ano: int, tipo: int) -> dict:
    """{id: norma}. A API devolve no máximo NORMAS_LIMITE por chamada e `numero` casa por trecho: resposta cheia é refeita com mais um
    dígito (0-9) no fim do trecho, até vir menos que o limite; todo número é achado pelo trecho que o começa."""
    achadas, fila, vistos = {}, [""], set()
    while fila:
        trecho = fila.pop(0)
        if trecho in vistos:
            continue
        vistos.add(trecho)
        lista = consulta_normas(sessao, ano, tipo, trecho)
        for n in lista:
            if (norma := parse_norma(n)):
                achadas[str(n["id"])] = norma
        if len(lista) >= NORMAS_LIMITE:
            fila += [trecho + d for d in "0123456789"]
    return achadas


def normas_do_ano(sessao, ano: int) -> dict:
    achadas = {}
    for tipo in NORMAS_TIPOS:
        achadas |= normas_do_tipo(sessao, ano, tipo)
    return dict(sorted(achadas.items(), key=lambda kv: (kv[1]["tipo"] or "", int(kv[1]["numero"]) if kv[1]["numero"].isdigit() else 0, kv[0])))


def parse_pautas(tipo: str, html: str) -> list[dict]:
    """[{id, tipo, titulo, data, arquivos:[{nome, url}]}] de um mês. Pauta: link para a página da pauta; ata: PDF em downloads.alepa.pa.gov.br."""
    itens = {}
    for m in re.finditer(r"<a class='pauta-item-title'(?: target='_blank')? href='([^']+)'>(.*?)</a>", html, re.S):
        href, texto = unescape(m.group(1)), comum.limpar(m.group(2))
        idf = re.search(r"(?:Id=|/)(\d+)(?:\.\w+)?$", href)
        if not idf:
            continue
        d = re.match(r"(\d{2}/\d{2}/\d{4})\s*-\s*(.*)", texto)
        titulo = d.group(2) if d else texto
        itens[idf.group(1)] = {"id": idf.group(1), "tipo": tipo, "titulo": titulo, "data": comum.data_br_iso(d.group(1)) if d else None,
                               "arquivos": [{"nome": titulo, "url": href if href.startswith("http") else ALEPA + href}]}
    return list(itens.values())


def consulta_pautas(sessao, tipo: str, ano: int, mes: int) -> str:
    _, url, callback = PAUTAS[tipo]
    r = sessao.post(url, data={"__DXCallbackName": callback, "__DXCallbackArgument": "c0:", "ano": str(ano), "mes": str(mes)}, timeout=60)
    r.raise_for_status()
    return r.text


def pautas_do_ano(sessao, ano: int, hoje: date, anterior: dict) -> tuple[dict, dict]:
    """(itens {tipo|id: item}, meses {tipo|AAAA-MM: dia da leitura}). Mês já lido fora dos MESES_RECENTES vem do arquivo anterior."""
    itens, meses = dict(anterior.get("itens") or {}), dict(anterior.get("meses") or {})
    recentes = comum.meses_recentes(hoje, MESES_RECENTES)
    for tipo, (pagina, _, _) in PAUTAS.items():
        sessao.get(pagina, timeout=30).raise_for_status()
        for mes in range(1, 13 if ano < hoje.year else hoje.month + 1):
            periodo = f"{tipo}|{ano}-{mes:02d}"
            if periodo in meses and (ano, mes) not in recentes:
                continue
            time.sleep(PAUSA)
            for i in parse_pautas(tipo, consulta_pautas(sessao, tipo, ano, mes)):
                itens[f"{tipo}|{i['id']}"] = i
            meses[periodo] = hoje.isoformat()
    return dict(sorted(itens.items(), key=lambda kv: (kv[1]["data"] or "", kv[0]))), meses


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


def _contrato_pessoal_gabinete(ctx):
    s = comum.sessao()
    linhas = pedir(s, "GET", GABINETE_CSV_URL, params={"nb": "", "cb": "", "lt": "GAB. DEP. GUSTAVO SEFER"}).splitlines()
    inativo = next(l for l in linhas[1:] if l.endswith(";Inativo"))
    return {"csv": chr(10).join(linhas[:3] + [inativo])}


def _conferir_pessoal_gabinete(registro):
    linhas = parse_pessoal_csv(registro["csv"])
    falhas = [] if linhas else ["CSV de pessoal sem linhas"]
    for l in linhas:
        falhas += comum.campos_vazios(l, ("matricula", "nome", "lotacao", "situacao"), "servidor")
        if not LOTACAO_GABINETE.match(l["lotacao"] or ""):
            falhas.append("lotação fora do formato '<código> - GAB. DEP. <nome>'")
    if {l["situacao"] for l in linhas} - {"Ativo", "Inativo"}:
        falhas.append("situação nova no CSV de pessoal")
    return falhas, []


def _contrato_remuneracao(ctx):
    s = comum.sessao()
    pagina = pedir(s, "GET", SERVIDORES_URL)
    ano, mes = ultimo_mes_publicado(pagina)
    cabecalho = pagina[pagina.index('<select'): pagina.index("</select>", pagina.index('name="mes"')) + 9]
    html = pedir(s, "POST", SERVIDORES_URL, data={"anoref": f"{ano % 100:02d}", "mes": f"{mes:02d}", "b_nome": "GUSTAVO BEMERGUY SEFER"})
    linhas, _ = parse_servidores(html)
    lista = html[html.index("<table"): html.index("</table>") + 8]
    detalhe = pedir(s, "GET", SERVIDORES_BASE + next(l for l in linhas if l["cargo"] == "DEPUTADO ESTADUAL")["detalhe"])
    return {"filtros": cabecalho, "lista": lista, "detalhe": detalhe[detalhe.index("<table"): detalhe.index("</table>") + 8]}


def _conferir_remuneracao(registro):
    falhas = []
    try:
        ultimo_mes_publicado(registro["filtros"])
    except RuntimeError as e:
        falhas.append(str(e))
    linhas, _ = parse_servidores(registro["lista"])
    deputados = [l for l in linhas if l["cargo"] == "DEPUTADO ESTADUAL"]
    if not deputados:
        falhas.append("lista de servidores sem DEPUTADO ESTADUAL")
    for l in linhas:
        falhas += comum.campos_vazios(l, ("matricula", "nome", "cargo", "lotacao", "detalhe"), "servidor")
    folha = parse_detalhe(registro["detalhe"])
    falhas += [f"detalhe sem {c}" for c in ("ano", "mes") if not folha[c]]
    falhas += [f"detalhe sem o valor '{r}'" for r in ("remuneracao", "total bruto", "descontos", "total liquido") if folha["valores"].get(r) is None]
    return falhas, []


def _recortar_votacao(html: str, n: int = 2) -> str:
    inicio = html.index('<table class="table-header">')
    corpo = html[inicio:]

    def reduzir(m):
        itens = re.findall(r'<div class="voto-item">.*?</div>', m.group(2), re.S)[: n * 2]
        return m.group(1) + "".join(itens) + m.group(3)

    return re.sub(r'(<div class="votos-lista">)(.*?)(</div>\s*<p class="quantidade">)', reduzir, corpo, flags=re.S)


def _contrato_votacao(ctx):
    s = comum.sessao()
    s.get(VOTACOES_PAGINA, timeout=30).raise_for_status()
    hoje = date.today()
    ano, mes = hoje.year, hoje.month
    for _ in range(12):
        itens = parse_lista_votacoes(consulta_lista_votacoes(s, ano, mes))
        for item in itens:
            html = consulta_votacao(s, item)
            if any(parse_votacao(html)["votos"].get(r) for r in VOTOS_PA):
                return {"lista": f"<a class='pauta-item-title' href='/Legislativo/DetalhesVotacaoNominal?IdProposicao={item['idProposicao']}"
                                 f"&IdVotacao={item['idVotacao']}'>{item['data'][8:]}/{item['data'][5:7]}/{item['data'][:4]} - {item['titulo']}</a>",
                        "detalhe": _recortar_votacao(html)}
        ano, mes = mes_anterior(ano, mes)
    raise RuntimeError("nenhuma votação nominal nos últimos 12 meses")


def _conferir_votacao(registro):
    itens = parse_lista_votacoes(registro["lista"])
    falhas = [] if itens else ["lista de votações sem item"]
    for i in itens:
        falhas += comum.campos_vazios(i, ("idProposicao", "idVotacao", "data", "titulo"), "item")
    lido = parse_votacao(registro["detalhe"])
    falhas += comum.campos_vazios(lido, ("projeto", "data", "turno", "resultado", "sessaoTipo", "sessaoNumero"), "votação")
    novos = set(lido["votos"]) - set(VOTOS_PA)
    if novos:
        falhas.append(f"voto novo na votação: {', '.join(sorted(novos))}")
    if not any(lido["votos"].get(r) for r in VOTOS_PA):
        falhas.append("votação sem nomes")
    for lista in lido["votos"].values():
        for nome, partido in lista:
            falhas += [f"voto de {nome or '?'} sem {c}" for c, v in (("nome", nome), ("partido", partido)) if not v]
    return falhas, []


def recortar_grade(dto: dict, filtro, n: int = 2) -> dict:
    """Como `recortar_dto`, mas guarda as n primeiras células da grade cuja linha passa em `filtro`."""
    fatia = max(dto["Slices"], key=lambda f: len(f["KeyIds"]))
    novos = {c: [] for c in fatia["KeyIds"]}
    dados = {}
    for chave, valores in fatia["Data"].items():
        linha = {c: dto["EncodeMaps"][c][i] for c, i in zip(fatia["KeyIds"], json.loads(chave), strict=False)}
        if not filtro(linha) or len(dados) >= n:
            continue
        indices = []
        for c in fatia["KeyIds"]:
            if linha[c] not in novos[c]:
                novos[c].append(linha[c])
            indices.append(novos[c].index(linha[c]))
        dados[json.dumps(indices, separators=(",", ":"))] = valores
    return {"EncodeMaps": novos, "Slices": [{"KeyIds": fatia["KeyIds"], "ValueIds": fatia["ValueIds"], "Data": dados}]}


def _contrato_orgao(ctx):
    s = comum.sessao()
    contratos = recortar_grade(consulta_grade(s, DASHBOARD_CONTRATOS), lambda lin: True, 3)
    licitacoes = recortar_grade(consulta_grade(s, DASHBOARD_LICITACOES), lambda lin: "REGISTRO DE PRE" in comum.sem_acento(lin.get("DataItem1") or "").upper(), 2)
    return {"contratos": contratos, "licitacoes": licitacoes}


def _conferir_orgao(registro):
    falhas = []
    for chave, itens in (("contratos", itens_contratos(celulas_grade(registro["contratos"]))),
                         ("licitacoes", itens_atas_registro(celulas_grade(registro["licitacoes"])))):
        if not itens:
            falhas.append(f"{chave}: nenhum item lido")
        for i in itens.values():
            falhas += [f"{chave}: faltou {c}" for c in ("fornecedor", "inicio", "objeto", "situacao", "modalidade") if not i[c]]
    return falhas, []


def _contrato_normas(ctx):
    return {"resultados": consulta_normas(comum.sessao(), date.today().year, 4)[:3]}


def _conferir_normas(registro):
    falhas = [] if registro["resultados"] else ["nenhuma norma lida"]
    for n in registro["resultados"]:
        falhas += comum.campos_vazios(parse_norma(n) or {}, ("tipo", "numero", "ano", "ementa", "link"), "norma", vazios=(None, ""))
    return falhas, []


def _recorte_pautas(html: str, n: int = 2) -> str:
    return "".join(m.group(0) for _, m in zip(range(n), re.finditer(r"<a class='pauta-item-title'.*?</a>", html, re.S), strict=False))


def _contrato_pautas(ctx):
    s = comum.sessao()
    achados = {}
    for tipo, (pagina, _, _) in PAUTAS.items():
        s.get(pagina, timeout=30).raise_for_status()
        ano, mes = date.today().year, date.today().month
        for _ in range(12):
            html = consulta_pautas(s, tipo, ano, mes)
            if parse_pautas(tipo, html):
                achados[tipo] = _recorte_pautas(html)
                break
            ano, mes = mes_anterior(ano, mes)
    return achados


def _conferir_pautas(registro):
    falhas = []
    for tipo in PAUTAS:
        itens = parse_pautas(tipo, registro.get(tipo, ""))
        if not itens:
            falhas.append(f"{tipo}: nenhum item")
        for i in itens:
            falhas += comum.campos_vazios(i, ("id", "titulo", "data", "arquivos"), tipo, vazios=(None, ""))
            if not i["arquivos"][0]["url"].startswith("http"):
                falhas.append(f"{tipo}: link sem http")
    return falhas, []


CONTRATOS = [
    {"nome": "estadual_pa_frequencia", "fonte": FREQUENCIA_URL, "buscar": _contrato_frequencia, "html": _conferir_frequencia},
    {"nome": "estadual_pa_ficha", "fonte": FICHA_URL.format(1024), "buscar": _contrato_ficha, "html": _conferir_ficha},
    {"nome": "estadual_pa_verba_indenizatoria", "fonte": VERBA_PAGINA, "buscar": _contrato_dashboard(DASHBOARD_VERBA), "html": _conferir_dashboard},
    {"nome": "estadual_pa_diarias", "fonte": DIARIAS_PAGINA, "buscar": _contrato_dashboard(DASHBOARD_DIARIAS), "html": _conferir_dashboard},
    {"nome": "estadual_pa_verba_gabinete", "fonte": GABINETE_PAGINA, "buscar": _contrato_gabinete, "html": _conferir_gabinete},
    {"nome": "estadual_pa_pessoal_gabinete", "fonte": PESSOAL_PAGINA, "buscar": _contrato_pessoal_gabinete, "html": _conferir_pessoal_gabinete},
    {"nome": "estadual_pa_remuneracao", "fonte": SERVIDORES_PAGINA, "buscar": _contrato_remuneracao, "html": _conferir_remuneracao},
    {"nome": "estadual_pa_votacao_nominal", "fonte": VOTACOES_PAGINA, "buscar": _contrato_votacao, "html": _conferir_votacao},
    {"nome": "estadual_pa_normas", "fonte": NORMAS_API, "buscar": _contrato_normas, "html": _conferir_normas},
    {"nome": "estadual_pa_pautas_atas", "fonte": PAUTAS["ordem-do-dia"][0], "buscar": _contrato_pautas, "html": _conferir_pautas},
    {"nome": "estadual_pa_orgao", "fonte": CONTRATOS_PAGINA, "buscar": _contrato_orgao, "html": _conferir_orgao},
]


if __name__ == "__main__":
    comum.principal(coletar)
