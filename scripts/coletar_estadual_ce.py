"""
Deputados estaduais do Ceará (Alece), fora do SAPL. Grava em dados/estaduais/CE/ (contrato em estaduais_comum.py).

Fontes lidas aqui:
  - deputados (HTML estático): https://www.al.ce.gov.br/deputados e a ficha de cada um (nome completo, e-mail);
  - verba de desempenho parlamentar (a cota), CSV por mês, 2021 em diante:
    https://transparencia.al.ce.gov.br/despesas/verba-desempenho-parlamentar/csv?mes=10&ano=2026
  - remuneração dos deputados (CSV mensal de todo o pessoal, só as linhas DEPUTADOS) e diárias (CSV anual);
  - votações nominais: a página /consultas-gerais/votacao-nominal traz todas as matérias com o link do XLSX de cada uma
    (o XLSX tem blocos SIM / NÃO / ABSTENÇÃO por deputado; quem não votou fica em branco);
  - proposições (autoria, ementa, situação): https://www2.al.ce.gov.br/legislativo/proposicoes/numero.php, só tipos de projeto.

Não coletado: emendas (a página só publica o quadro consolidado da LOA, sem arquivo aberto), presença (não existe).
"""

import csv
import io
import re
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from html import unescape
from defusedxml import ElementTree

import estaduais_comum as comum

UF = "CE"
PASTA = comum.DADOS / UF
SITE = "https://www.al.ce.gov.br"
TRANSP = "https://transparencia.al.ce.gov.br"
PROPOSICOES = "https://www2.al.ce.gov.br/legislativo/proposicoes/numero.php"
LISTA_URL = f"{SITE}/deputados"
VOTACOES_URL = f"{TRANSP}/consultas-gerais/votacao-nominal"
VDP_PAGINA = f"{TRANSP}/despesas/verba-desempenho-parlamentar"
PESSOAL_PAGINA = f"{TRANSP}/gestao-de-pessoas/pessoal"
DIARIAS_PAGINA = f"{TRANSP}/despesas/despesas-diarias"
LEGISLATURA = "31ª (2023-2027)"
ANO_VDP = 2021
ANO_REMUNERACAO = 2023
ANO_PROPOSICOES = 2023
TIMEOUT = 20
TIMEOUT_CSV = 90
EM_PARALELO = 2
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

TABELAS = {  # tabela em numero.php -> (sigla, descrição)
    "projeto_lei": ("PL", "Projeto de Lei"),
    "projeto_compl": ("PLC", "Projeto de Lei Complementar"),
    "projeto_emen": ("PEC", "Proposta de Emenda à Constituição"),
    "projeto_decre": ("PDL", "Projeto de Decreto Legislativo"),
    "projeto_reso": ("PR", "Projeto de Resolução"),
}
CATEGORIAS_VDP = [
    ("anulacao", "Anulação de empenho"), ("cartoes eletronicos", "Alimentação e refeição"), ("alimentacao", "Alimentação e refeição"),
    ("refeicao", "Alimentação e refeição"), ("reembolso", "Reembolso de despesas indenizatórias"),
    ("telecomunica", "Telefonia e dados"), ("telefonia", "Telefonia e dados"), ("pacote de dados", "Telefonia e dados"),
    ("juridic", "Consultoria jurídica"), ("comunicacao", "Assessoria de comunicação"),
    ("consultoria", "Consultoria e assessoria"), ("assessoria", "Consultoria e assessoria"),
    ("impress", "Impressos gráficos"), ("locacao", "Locação de veículos"), ("combustiv", "Combustível"),
]


def sem_ponto(nome: str) -> str:
    return " ".join((nome or "").replace(".", " ").split())


def ligar(nomes, deputados: list[dict]) -> dict:
    """Como comum.ligar_nomes, sem diferenciar pontos ("AP. LUIZ HENRIQUE" e "Ap Luiz Henrique")."""
    sem = [{**d, "nome": sem_ponto(d.get("nome")), "nomeCivil": sem_ponto(d.get("nomeCivil"))} for d in deputados]
    achados = comum.ligar_nomes({sem_ponto(n) for n in nomes}, sem)
    return {n: achados[sem_ponto(n)] for n in nomes if sem_ponto(n) in achados}


def decodificar(conteudo: bytes, codificacao: str | None = None) -> str:
    if codificacao:
        return conteudo.decode(codificacao, errors="replace")
    try:
        return conteudo.decode("utf-8-sig")
    except UnicodeDecodeError:
        return conteudo.decode("cp1252", errors="replace")


def baixar(s, url: str, timeout: int = TIMEOUT) -> bytes:
    r = s.get(url, timeout=timeout)
    r.raise_for_status()
    return r.content


def limpar(html: str) -> str:
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", html)).split())


def iso_data(texto: str) -> str | None:
    texto = (texto or "").strip()
    for formato in ("%d/%m/%Y", "%d.%m.%y", "%d.%m.%Y"):
        try:
            return datetime.strptime(texto, formato).date().isoformat()
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------- deputados

def cartoes(html: str) -> list[dict]:
    """Cartões da página de deputados; os do bloco "Suplentes em Exercício" saem com titular False."""
    corte = html.find("Suplentes em Exerc")
    lista = []
    for m in re.finditer(r'<div\s+class="deputado_card[^"]*"(.*?)</div>', html, re.S):
        bloco = m.group(1)
        link = re.search(r'<a href="https?://[^/"]+/deputados/([a-z0-9\-]+)"[^>]*>(.*?)</a>', bloco, re.S)
        if not link:
            continue
        foto = re.search(r'src="([^"]+)"', bloco)
        partido = re.search(r'deputado_card--partido[^>]*>(.*?)</p>', bloco, re.S)
        lista.append({"id": link.group(1), "nome": limpar(link.group(2)), "foto": foto.group(1) if foto else None,
                      "partido": limpar(partido.group(1)) if partido else None,
                      "titular": not (corte >= 0 and m.start() > corte)})
    return lista


def campo_ficha(html: str, rotulo: str) -> str | None:
    m = re.search(rf'<span class="font-weight-bold">\s*{rotulo}\s*</span>\s*<span[^>]*>(.*?)</span>', html, re.S)
    valor = limpar(m.group(1)) if m else ""
    return valor if valor and valor != "-" else None


def ficha(html: str) -> dict:
    email = campo_ficha(html, "E-mails")
    achado = re.search(r"[\w.+-]+@[\w.-]+\.\w+", email or "")
    return {"nomeCivil": campo_ficha(html, "Nome Completo"), "email": achado.group(0) if achado else None}


def coletar_deputados(s) -> list[dict]:
    lista = cartoes(decodificar(baixar(s, LISTA_URL), "utf-8"))
    if not lista:
        raise RuntimeError("página de deputados sem cartões")

    def completar(d):
        url = f"{SITE}/deputados/{d['id']}"
        try:
            dados = ficha(decodificar(baixar(s, url), "utf-8"))
        except Exception as e:
            comum.avisar(f"CE: ficha de {d['id']}: {e}")
            dados = {"nomeCivil": None, "email": None}
        return {"id": d["id"], "nome": d["nome"], "nomeCivil": dados["nomeCivil"], "foto": d["foto"], "email": dados["email"],
                "titular": d["titular"], "partido": d["partido"], "fonte": url}

    with ThreadPoolExecutor(EM_PARALELO) as ex:
        deputados = list(ex.map(completar, lista))
    comum.salvar(PASTA / "deputados.json", {"fonte": LISTA_URL, "host": None, "legislatura": LEGISLATURA, "deputados": deputados})
    print(f"CE: {len(deputados)} deputados ({sum(d['titular'] for d in deputados)} titulares)")
    return deputados


# ---------------------------------------------------------------- CSVs do portal (VDP, remuneração, diárias)

def linhas_csv(texto: str, cabecalho_em: str) -> list[dict]:
    """Linhas do CSV com ';' como dicts de cabeçalho sem acento; ignora o que vem antes da linha com `cabecalho_em`."""
    todas = list(csv.reader(io.StringIO(texto), delimiter=";"))
    inicio = next((i for i, l in enumerate(todas) if cabecalho_em in [comum.sem_acento(c).upper() for c in l]), None)
    if inicio is None:
        return []
    cab = [comum.sem_acento(c).upper() for c in todas[inicio]]
    return [dict(zip(cab, l)) for l in todas[inicio + 1:] if any(c.strip() for c in l)]


def categoria_vdp(descricao: str) -> str:
    d = comum.sem_acento(descricao)
    for chave, nome in CATEGORIAS_VDP:
        if chave in d:
            return nome
    return "Outros"


def itens_vdp(linhas: list[dict], ligacao: dict, fonte: str) -> tuple[list[dict], set]:
    itens, sem_par = [], set()
    for l in linhas:
        nome = l.get("DEPUTADO", "")
        pid = ligacao.get(nome)
        if not pid:
            sem_par.add(comum.nome_limpo(nome))
            continue
        periodo = (l.get("PERIODO") or "").split("/")
        itens.append({"idDeputado": pid, "mes": int(periodo[0]) if periodo[0].isdigit() else None,
                      "categoria": categoria_vdp(l.get("DESCRICAO", "")), "fornecedor": l.get("CREDOR") or None,
                      "cnpj": l.get("CNPJ") or None, "valor": comum.valor_br(l.get("VALOR")), "empenho": l.get("EMPENHO") or None,
                      "descricao": " ".join((l.get("DESCRICAO") or "").split()) or None, "fonte": fonte})
    return itens, sem_par


def meses_do_ano(ano: int) -> range:
    hoje = date.today()
    return range(1, (hoje.month if ano == hoje.year else 12) + 1)


def coletar_por_ano(s, nome_arquivo: str, fonte: str, ano_inicial: int, dia_por_mes: bool, baixar_periodo, montar) -> set:
    """Baixa cada mês (ou o ano) e grava <nome_arquivo>_<ano>.json; anos passados que já existem não são baixados de novo."""
    sem_par = set()
    for ano in range(ano_inicial, date.today().year + 1):
        destino = PASTA / f"{nome_arquivo}_{ano}.json"
        if ano < date.today().year and destino.exists():
            continue
        periodos = list(meses_do_ano(ano)) if dia_por_mes else [None]

        def um(mes):
            try:
                return montar(ano, mes, baixar_periodo(s, ano, mes))
            except Exception as e:
                comum.avisar(f"CE: {nome_arquivo} {ano}{'-%02d' % mes if mes else ''}: {e}")
                return [], set()

        with ThreadPoolExecutor(EM_PARALELO) as ex:
            resultados = list(ex.map(um, periodos))
        itens = [i for r, _ in resultados for i in r]
        for _, sp in resultados:
            sem_par |= sp
        if itens or ano == date.today().year:
            comum.salvar(destino, {"coletadoEm": date.today().isoformat(), "fonte": fonte, "itens": itens})
            print(f"CE: {nome_arquivo} {ano}: {len(itens)} itens")
    return sem_par


def coletar_vdp(s, deputados: list[dict]) -> None:
    def baixar_mes(s, ano, mes):
        return decodificar(baixar(s, f"{TRANSP}/despesas/verba-desempenho-parlamentar/csv?mes={mes}&ano={ano}", TIMEOUT_CSV))

    def montar(ano, mes, texto):
        linhas = linhas_csv(texto, "DEPUTADO")
        ligacao = ligar({l["DEPUTADO"] for l in linhas}, deputados)
        return itens_vdp(linhas, ligacao, f"{VDP_PAGINA}?mes={mes}&ano={ano}")

    sem_par = coletar_por_ano(s, "verbas", VDP_PAGINA, ANO_VDP, True, baixar_mes, montar)
    if sem_par:
        comum.avisar(f"CE: VDP sem deputado atual ({len(sem_par)}): {sorted(sem_par)[:12]}...")


def itens_remuneracao(linhas: list[dict], ligacao: dict, ano: int, mes: int) -> tuple[list[dict], set]:
    itens, sem_par = [], set()
    for l in linhas:
        if (l.get("CATEGORIA") or "").strip().upper() != "DEPUTADOS":
            continue
        pid = ligacao.get(l.get("NOME", ""))
        if not pid:
            sem_par.add(l.get("NOME", ""))
            continue
        componentes = {"descontosLegais": comum.valor_br(l.get("DESCONTOS LEGAIS")),
                       "abatimentoTeto": comum.valor_br(l.get('ABATIMENTO EM FUNCAO DO "TETO" CONSTITUCIONAL')),
                       "decimoTerceiro": comum.valor_br(l.get("13O SAL / ADTO 13O SAL")),
                       "descontosDecimoTerceiro": comum.valor_br(l.get("DESCONTOS ADTO 13O SAL"))}
        itens.append({"idDeputado": pid, "mes": mes, "bruto": comum.valor_br(l.get("REMUNERACAO BRUTA")),
                      "liquido": comum.valor_br(l.get("REMUNERACAO LIQUIDA")),
                      "componentes": {k: v for k, v in componentes.items() if v}, "fonte": f"{PESSOAL_PAGINA}?mes={mes:02d}&ano={ano}"})
    return itens, sem_par


def coletar_remuneracao(s, deputados: list[dict]) -> None:
    def baixar_mes(s, ano, mes):
        return decodificar(baixar(s, f"{PESSOAL_PAGINA}/csv?mes={mes:02d}&ano={ano}", TIMEOUT_CSV))

    def montar(ano, mes, texto):
        linhas = linhas_csv(texto, "NOME")
        ligacao = ligar({l.get("NOME", "") for l in linhas if (l.get("CATEGORIA") or "").upper() == "DEPUTADOS"}, deputados)
        return itens_remuneracao(linhas, ligacao, ano, mes)

    sem_par = coletar_por_ano(s, "remuneracao", PESSOAL_PAGINA, ANO_REMUNERACAO, True, baixar_mes, montar)
    if sem_par:
        comum.avisar(f"CE: remuneração sem deputado atual ({len(sem_par)}): {sorted(sem_par)[:12]}")


def itens_diarias(linhas: list[dict], ligacao: dict, ano: int) -> tuple[list[dict], set]:
    itens, sem_par = [], set()
    for l in linhas:
        nome = l.get("BENEFICIARIO", "")
        pid = ligacao.get(nome)
        if not pid:
            sem_par.add(nome)
            continue
        itens.append({"idDeputado": pid, "data": iso_data(l.get("DATA PAGAMENTO")), "destino": None,
                      "motivo": " ".join((l.get("DESCRICAO") or "").split()) or None, "valor": comum.valor_br(l.get("VALOR")),
                      "empenho": l.get("EMPENHO") or None, "fonte": f"{DIARIAS_PAGINA}?ano={ano}"})
    return itens, sem_par


def coletar_diarias(s, deputados: list[dict]) -> None:
    def baixar_ano(s, ano, mes):
        return decodificar(baixar(s, f"{DIARIAS_PAGINA}?ano={ano}&export=csv", TIMEOUT_CSV))

    def montar(ano, mes, texto):
        linhas = linhas_csv(texto, "BENEFICIARIO")
        ligacao = ligar({l.get("BENEFICIARIO", "") for l in linhas}, deputados)
        return itens_diarias(linhas, ligacao, ano)

    coletar_por_ano(s, "diarias", DIARIAS_PAGINA, ANO_REMUNERACAO, False, baixar_ano, montar)


# ---------------------------------------------------------------- votações nominais

def votacoes_da_pagina(html: str) -> list[dict]:
    """Linhas da tabela de votações: sessão, data, matéria e os links do PDF e do XLSX."""
    lista = []
    for tr in re.findall(r"<tr>(.*?)</tr>", html, re.S):
        xlsx = re.search(r'href="([^"]*votacao_nominal_materia_csv/([^"/]+)\.xlsx)"', tr)
        if not xlsx:
            continue
        pdf = re.search(r'href="([^"]*votacao_nominal_materia/[^"]+\.pdf)"', tr)
        celulas = [limpar(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        lista.append({"id": xlsx.group(2), "xlsx": xlsx.group(1), "pdf": pdf.group(1) if pdf else xlsx.group(1),
                      "sessao": celulas[2] if len(celulas) > 2 else None, "data": iso_data(celulas[3]) if len(celulas) > 3 else None,
                      "materia": celulas[4] if len(celulas) > 4 else None})
    return lista


def ler_xlsx(conteudo: bytes) -> list[dict]:
    """Primeira planilha como lista de linhas {coluna: texto}, só células preenchidas."""
    z = zipfile.ZipFile(io.BytesIO(conteudo))
    textos = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ElementTree.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
            textos.append("".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")))
    folha = ElementTree.fromstring(z.read("xl/worksheets/sheet1.xml"))
    linhas = []
    for row in folha.iter(f"{{{NS['m']}}}row"):
        celulas = {}
        for c in row.findall("m:c", NS):
            v = c.find("m:v", NS)
            if v is None or v.text is None:
                continue
            valor = textos[int(v.text)] if c.get("t") == "s" else v.text
            if valor.strip():
                celulas[re.match(r"[A-Z]+", c.get("r")).group(0)] = valor.strip()
        if celulas:
            linhas.append(celulas)
    return linhas


def tipo_da_materia(texto: str) -> tuple[str, str | None]:
    t = comum.sem_acento(texto)
    for chave, sigla, nome in [("proposta de emenda", "PEC", "Proposta de Emenda à Constituição"),
                               ("lei complementar", "PLC", "Projeto de Lei Complementar"), ("projeto de lei", "PL", "Projeto de Lei"),
                               ("decreto legislativo", "PDL", "Projeto de Decreto Legislativo"), ("resolucao", "PR", "Projeto de Resolução"),
                               ("veto", "VET", "Veto"), ("requerimento", "REQ", "Requerimento"), ("indicacao", "IND", "Indicação")]:
        if chave in t[:120]:
            return sigla, nome
    return "MAT", None


def voto_normalizado(texto: str) -> str | None:
    t = comum.sem_acento(re.sub(r"\(.*?\)", "", texto or ""))
    return {"sim": "sim", "nao": "não", "abstencao": "abstenção"}.get(t)


def votacao_do_xlsx(linhas: list[dict]) -> dict | None:
    """Cabeçalho (data, resultado, matéria) e votos [(nome, partido, voto)] de um "RELATÓRIO DE VOTAÇÃO"."""
    cabecalho = " ".join(l.get("A", "") for l in linhas[:8])
    data = re.search(r"Data:\s*(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{4})", cabecalho)
    resultado = re.search(r"Resultado:\s*([A-Za-zÀ-ú]+)", cabecalho)
    materia = next((l["A"] for l in linhas[:8] if l.get("A", "").upper().startswith(("MATERIA", "MATÉRIA"))), "")
    numero = re.search(r"(\d+)\s*/\s*(\d{4})\s*[-–—]\s*(.*)", materia, re.S)
    votos, apuracao = [], {}
    for l in linhas:
        if l.get("A", "").upper().startswith("APURA"):
            apuracao = {"sim": l.get("D"), "nao": l.get("E"), "abstencao": l.get("F")}
        if not l.get("B") or not l.get("A", "").isdigit():
            continue
        voto = next((voto_normalizado(l[c]) for c in "DEF" if l.get(c) and voto_normalizado(l[c])), None)
        if voto:
            votos.append((l["B"], l.get("C"), voto))
    if not votos:
        return None
    tipo, descricao = tipo_da_materia(numero.group(3) if numero else materia)
    return {"data": iso_data("/".join(data.groups())) if data else None, "aprovada": (resultado.group(1).lower().startswith("aprov") if resultado else None),
            "resultado": resultado.group(1).capitalize() if resultado else None, "votos": votos, "apuracao": apuracao,
            "numero": numero.group(1) if numero else None, "ano": int(numero.group(2)) if numero else None,
            "tipo": tipo, "tipoDescricao": descricao, "ementa": " ".join((numero.group(3) if numero else materia).split())}


def coletar_votacoes(s, deputados: list[dict]) -> None:
    lista = votacoes_da_pagina(decodificar(baixar(s, VOTACOES_URL), "utf-8"))
    if not lista:
        raise RuntimeError("página de votações nominais sem matérias")
    existente = comum.ler(PASTA / "votacoes.json", {"votacoes": {}})["votacoes"]
    materias = comum.ler(PASTA / "materias_votadas.json", {})
    novas = [v for v in lista if v["id"] not in existente]

    def uma(v):
        try:
            return v, votacao_do_xlsx(ler_xlsx(baixar(s, v["xlsx"])))
        except Exception as e:
            comum.avisar(f"CE: votação {v['id']}: {e}")
            return v, None

    with ThreadPoolExecutor(EM_PARALELO) as ex:
        resultados = list(ex.map(uma, novas))
    sem_par = set()
    for v, dados in resultados:
        if not dados:
            continue
        ligacao = ligar({n for n, _, _ in dados["votos"]}, deputados)
        sem_par |= {n for n, _, _ in dados["votos"] if n not in ligacao}
        votos = [[ligacao[n], voto] for n, _, voto in dados["votos"] if n in ligacao]
        contagem = {k: int(dados["apuracao"][k]) if str(dados["apuracao"].get(k) or "").isdigit() else sum(1 for _, _, x in dados["votos"] if x == nome)
                    for k, nome in (("sim", "sim"), ("nao", "não"), ("abstencao", "abstenção"))}
        existente[v["id"]] = {"data": dados["data"] or v["data"], "idMateria": v["id"], "aprovada": dados["aprovada"],
                              "resultado": dados["resultado"], "sim": contagem["sim"], "nao": contagem["nao"],
                              "abstencoes": contagem["abstencao"], "votos": votos, "fonte": v["pdf"]}
        materias[v["id"]] = {"tipo": dados["tipo"], "tipoDescricao": dados["tipoDescricao"], "numero": dados["numero"],
                             "ano": dados["ano"], "ementa": dados["ementa"]}
    comum.salvar(PASTA / "votacoes.json", {"fonte": VOTACOES_URL, "votacoes": existente})
    comum.salvar(PASTA / "materias_votadas.json", materias)
    print(f"CE: {len(existente)} votações nominais ({len(novas)} novas de {len(lista)} na página)")
    if sem_par:
        comum.avisar(f"CE: votos sem deputado da lista ({len(sem_par)}): {sorted(sem_par)}")


# ---------------------------------------------------------------- proposições

def ultima_pagina(html: str) -> int:
    m = re.search(r"absolutepage=(\d+)'>&Uacute;ltima", html)
    return int(m.group(1)) if m else 1


def campo_proposicao(bloco: str, rotulo: str) -> str:
    m = re.search(rf"<b>{re.escape(rotulo)}</b></font>(?:&nbsp;)?<br>\s*<font[^>]*>(.*?)</font>", bloco, re.S)
    return m.group(1) if m else ""


def proposicoes_da_pagina(html: str) -> list[dict]:
    itens = []
    for bloco in html.split("N&ordm; do Proj.:")[1:]:
        cel = re.search(r"</b></font><br>\s*<font[^>]*>(.*?)</font>", bloco, re.S)
        num = re.search(r"(\d+)\s*/\s*(\d{2,4})", limpar(cel.group(1))) if cel else None
        if not num:
            continue
        ano = int(num.group(2))
        ano += 2000 if ano < 100 else 0
        ementa_html = campo_proposicao(bloco, "Ementa:")
        link = re.search(r"href=['\"]([^'\"]+)['\"]", ementa_html)
        trecho = re.search(r"Localiza&ccedil;&atilde;o:</b></font>.*?<br>\s*<font[^>]*>(.*?)</font>", bloco, re.S)
        movimentos = [limpar(x) for x in re.split(r"<br\s*/?>", trecho.group(1))] if trecho else []
        lei = limpar(campo_proposicao(bloco, "Lei:"))
        obs = limpar(campo_proposicao(bloco, "OBS:"))
        situacao = f"Lei {lei}" if lei and lei != "-" else (movimentos[-1] if movimentos else (obs if obs and obs != "-" else None))
        itens.append({"numero": int(num.group(1)), "ano": ano, "autor": limpar(campo_proposicao(bloco, "Autor:")),
                      "dataApresentacao": iso_data(limpar(campo_proposicao(bloco, "Entrada:"))), "ementa": limpar(ementa_html),
                      "linkTexto": link.group(1) if link else None, "situacao": situacao})
    return itens


def autores(texto: str) -> list[str]:
    """Nomes do campo Autor ("A, COAUTORIA: B", "AUTORIA: DEPUTADO C.")."""
    nomes = []
    for a in re.split(r"\s*[,;/]\s*|\s+E\s+|(?i:\s*COAUTOR(?:IA|ES)\s*:?\s*|\s*AUTORIA\s*:\s*)", texto or ""):
        a = re.sub(r"(?i)^DEPUTAD[OA]\s+", "", a.strip()).strip(" .")
        if a:
            nomes.append(a)
    return nomes


def coletar_proposicoes(s, deputados: list[dict]) -> None:
    brutos = {}
    sem_par = set()
    for tabela, (sigla, descricao) in TABELAS.items():
        for opcao in ("T", "D"):
            base = f"{PROPOSICOES}?nome=31_legislatura&tabela={tabela}&opcao={opcao}"
            try:
                primeira = decodificar(baixar(s, base), "utf-8")
            except Exception as e:
                comum.avisar(f"CE: proposições {tabela}/{opcao}: {e}")
                continue
            paginas = {1: primeira}

            def pagina(n, base=base):
                try:
                    return n, decodificar(baixar(s, f"{base}&absolutepage={n}"), "utf-8")
                except Exception as e:
                    comum.avisar(f"CE: proposições {tabela}/{opcao} página {n}: {e}")
                    return n, ""

            with ThreadPoolExecutor(EM_PARALELO) as ex:
                for n, h in ex.map(pagina, range(2, ultima_pagina(primeira) + 1)):
                    paginas[n] = h
            for h in paginas.values():
                for p in proposicoes_da_pagina(h):
                    if p["ano"] >= ANO_PROPOSICOES:
                        brutos[(sigla, p["numero"], p["ano"])] = {**p, "tipo": sigla, "tipoDescricao": descricao, "emTramitacao": opcao == "T",
                                                                 "fonte": base}
            print(f"CE: proposições {tabela}/{opcao}: {len(paginas)} páginas")
    ligacao = ligar({a for p in brutos.values() for a in autores(p["autor"])}, deputados)
    por_ano: dict[int, dict] = {}
    for (sigla, numero, ano), p in sorted(brutos.items()):
        ids = sorted({ligacao[a] for a in autores(p["autor"]) if a in ligacao})
        if not ids:
            sem_par.add(p["autor"])
            continue
        por_ano.setdefault(ano, {})[f"{sigla}-{numero}-{ano}"] = {
            "tipo": sigla, "tipoDescricao": p["tipoDescricao"], "numero": numero, "ano": ano, "dataApresentacao": p["dataApresentacao"],
            "ementa": p["ementa"], "situacao": p["situacao"], "emTramitacao": p["emTramitacao"], "linkTexto": p["linkTexto"],
            "idsAutores": ids, "idsDeputados": ids, "fonte": p["fonte"]}
    for ano, materias in por_ano.items():
        comum.salvar(PASTA / f"materias_{ano}.json", {"coletadoEm": date.today().isoformat(), "fonte": PROPOSICOES, "materias": materias})
    print(f"CE: {sum(len(m) for m in por_ano.values())} projetos de deputados em {len(por_ano)} anos ({len(brutos)} lidos)")
    if sem_par:
        comum.avisar(f"CE: autores sem deputado da lista ({len(sem_par)}): {sorted(sem_par)[:15]}")


# ---------------------------------------------------------------- execução

def coletar() -> None:
    s = comum.sessao()
    deputados = coletar_deputados(s)
    for nome, etapa in [("verba", coletar_vdp), ("votações", coletar_votacoes), ("proposições", coletar_proposicoes),
                        ("remuneração", coletar_remuneracao), ("diárias", coletar_diarias)]:
        try:
            etapa(s, deputados)
        except Exception as e:
            comum.avisar(f"CE: {nome}: {e}")


# ---------------------------------------------------------------- contratos (amostras reduzidas das respostas reais)

def _recortar_lista(html: str) -> str:
    inicio = [m.start() for m in re.finditer(r'<div\s+class="deputado_card', html)]
    corte = html.find("Suplentes em Exerc")
    titulares = [i for i in inicio if corte < 0 or i < corte][:3]
    suplentes = [i for i in inicio if corte >= 0 and i > corte][:2]
    pedacos = [html[i: html.find("</div>", i) + 6] for i in titulares]
    if suplentes:
        pedacos.append(html[corte - 10: corte + 60])
        pedacos += [html[i: html.find("</div>", i) + 6] for i in suplentes]
    return "\n".join(pedacos)


def _contrato_deputados(ctx):
    s = comum.sessao()
    lista = decodificar(baixar(s, LISTA_URL), "utf-8")
    primeiro = cartoes(lista)[0]["id"]
    pagina = decodificar(baixar(s, f"{SITE}/deputados/{primeiro}"), "utf-8")
    inicio = pagina.index("Nome Completo")
    return {"lista": _recortar_lista(lista), "ficha": pagina[inicio - 200: inicio + 3600]}


def _conferir_deputados(registro):
    falhas = []
    lista = cartoes(registro["lista"])
    if not lista or not all(d["id"] and d["nome"] and d["partido"] and d["foto"] for d in lista):
        falhas.append("cartões de deputados sem slug, nome, partido ou foto")
    if not any(not d["titular"] for d in lista):
        falhas.append("bloco de suplentes não reconhecido")
    dados = ficha(registro["ficha"])
    if not dados["nomeCivil"]:
        falhas.append("ficha sem 'Nome Completo'")
    return falhas, [] if dados["email"] else ["ficha sem e-mail"]


def _contrato_vdp(ctx):
    texto = decodificar(baixar(comum.sessao(), f"{TRANSP}/despesas/verba-desempenho-parlamentar/csv?mes=10&ano=2026", TIMEOUT_CSV))
    return {"csv": "\n".join(texto.splitlines()[:6])}


def _conferir_vdp(registro):
    linhas = linhas_csv(registro["csv"], "DEPUTADO")
    falhas = []
    if not linhas:
        return ["CSV da VDP sem cabeçalho DEPUTADO ou sem linhas"], []
    for coluna in ("PERIODO", "EMPENHO", "DESCRICAO", "CNPJ", "CREDOR", "VALOR"):
        if coluna not in linhas[0]:
            falhas.append(f"CSV da VDP sem a coluna {coluna}")
    if comum.valor_br(linhas[0].get("VALOR")) is None:
        falhas.append("VALOR da VDP ilegível")
    return falhas, []


def _contrato_pessoal(ctx):
    texto = decodificar(baixar(comum.sessao(), f"{PESSOAL_PAGINA}/csv?mes=09&ano=2026", TIMEOUT_CSV))
    linhas = texto.splitlines()
    return {"csv": "\n".join(linhas[:1] + [l for l in linhas if ";DEPUTADOS;" in l][:2])}


def _conferir_pessoal(registro):
    linhas = linhas_csv(registro["csv"], "NOME")
    falhas = []
    if not linhas:
        return ["CSV de pessoal sem cabeçalho NOME ou sem linhas de deputados"], []
    for coluna in ("CATEGORIA", "REMUNERACAO BRUTA", "REMUNERACAO LIQUIDA"):
        if coluna not in linhas[0]:
            falhas.append(f"CSV de pessoal sem a coluna {coluna}")
    itens, _ = itens_remuneracao(linhas, {l["NOME"]: "x" for l in linhas}, 2026, 9)
    if not itens or itens[0]["bruto"] is None:
        falhas.append("remuneração bruta de deputado ilegível")
    return falhas, []


def _contrato_diarias(ctx):
    texto = decodificar(baixar(comum.sessao(), f"{DIARIAS_PAGINA}?ano=2026&export=csv", TIMEOUT_CSV))
    return {"csv": "\n".join(texto.splitlines()[:4])}


def _conferir_diarias(registro):
    linhas = linhas_csv(registro["csv"], "BENEFICIARIO")
    if not linhas:
        return ["CSV de diárias sem cabeçalho BENEFICIÁRIO ou sem linhas"], []
    falhas = [f"CSV de diárias sem a coluna {c}" for c in ("DESCRICAO", "DATA PAGAMENTO", "VALOR") if c not in linhas[0]]
    itens, _ = itens_diarias(linhas, {l["BENEFICIARIO"]: "x" for l in linhas}, 2026)
    if not itens or itens[0]["data"] is None or itens[0]["valor"] is None:
        falhas.append("data ou valor de diária ilegível")
    return falhas, []


def _contrato_votacoes_lista(ctx):
    html = decodificar(baixar(comum.sessao(), VOTACOES_URL), "utf-8")
    inicio = html.index("<table")
    linhas = [m.start() for m in re.finditer(r"<tr>", html[inicio:])]
    return {"html": html[inicio: inicio + linhas[3] + 2000 if len(linhas) > 3 else inicio + 4000]}


def _conferir_votacoes_lista(registro):
    lista = votacoes_da_pagina(registro["html"] + "</td></tr>")
    falhas = []
    if not lista:
        return ["tabela de votações nominais sem links de XLSX"], []
    for v in lista:
        if not (v["id"] and v["data"] and v["materia"] and v["pdf"]):
            falhas.append("linha de votação sem id, data, matéria ou PDF")
    return falhas, []


def _contrato_votacao_xlsx(ctx):
    s = comum.sessao()
    lista = votacoes_da_pagina(decodificar(baixar(s, VOTACOES_URL), "utf-8"))
    linhas = ler_xlsx(baixar(s, lista[0]["xlsx"]))
    return {"linhas": linhas[:14] + [l for l in linhas if l.get("A", "").upper().startswith("APURA")]}


def _conferir_votacao_xlsx(registro):
    dados = votacao_do_xlsx(registro["linhas"])
    if not dados:
        return ["XLSX de votação sem data ou sem votos"], []
    falhas = []
    if not dados["numero"] or not dados["ano"]:
        falhas.append("matéria sem número/ano")
    if dados["aprovada"] is None:
        falhas.append("resultado da votação não reconhecido")
    if not {"sim", "não"} & {v for _, _, v in dados["votos"]}:
        falhas.append("nenhum voto SIM ou NÃO")
    return falhas, []


def _contrato_proposicoes(ctx):
    html = decodificar(baixar(comum.sessao(), f"{PROPOSICOES}?nome=31_legislatura&tabela=projeto_lei&opcao=D", TIMEOUT), "utf-8")
    pos = html.index("&Uacute;ltima")
    blocos = [m.start() for m in re.finditer(r"N&ordm; do Proj\.:", html)]
    fim = blocos[2] if len(blocos) > 2 else len(html)
    return {"html": html[max(0, pos - 120): pos + 40] + "\n" + html[blocos[0] - 80: fim]}


def _conferir_proposicoes(registro):
    falhas = []
    if ultima_pagina(registro["html"]) < 2:
        falhas.append("paginação (link 'Última') não reconhecida")
    itens = proposicoes_da_pagina(registro["html"])
    if not itens:
        return falhas + ["nenhuma proposição reconhecida"], []
    for p in itens:
        for campo in ("autor", "ementa", "dataApresentacao"):
            if not p[campo]:
                falhas.append(f"proposição sem {campo}")
    return falhas, []


CONTRATOS = [
    dict(nome="estadual_ce_deputados", fonte=LISTA_URL, buscar=_contrato_deputados, html=_conferir_deputados),
    dict(nome="estadual_ce_vdp", fonte=VDP_PAGINA, buscar=_contrato_vdp, html=_conferir_vdp),
    dict(nome="estadual_ce_pessoal", fonte=PESSOAL_PAGINA, buscar=_contrato_pessoal, html=_conferir_pessoal),
    dict(nome="estadual_ce_diarias", fonte=DIARIAS_PAGINA, buscar=_contrato_diarias, html=_conferir_diarias),
    dict(nome="estadual_ce_votacoes_lista", fonte=VOTACOES_URL, buscar=_contrato_votacoes_lista, html=_conferir_votacoes_lista),
    dict(nome="estadual_ce_votacao_xlsx", fonte=VOTACOES_URL, buscar=_contrato_votacao_xlsx, html=_conferir_votacao_xlsx),
    dict(nome="estadual_ce_proposicoes", fonte=PROPOSICOES, buscar=_contrato_proposicoes, html=_conferir_proposicoes),
]


if __name__ == "__main__":
    coletar()
    sys.exit(0)
