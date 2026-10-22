"""
Deputados estaduais de Roraima (ALE-RR), fora do SAPL.

Fontes abertas e lidas aqui:
  - deputados (nome parlamentar, nome civil, partido, foto, e-mail, ficha): https://al.rr.leg.br/deputados-estaduais-2023/ e a ficha de cada um;
  - verba indenizatória (ressarcimento de despesas parlamentares): um ODT por deputado e mês no portal da transparência, a partir de
    setembro de 2025 (resolução 036/2021), lido como tabela: uma linha por item de despesa com valor;
  - diárias: planilha mensal (XLSX/ODS) a partir de outubro de 2025; só as linhas de cargo "DEPUTADO(A)".
  Os dois últimos ficam em listas de arquivos do plugin WP Display Files (admin-ajax `wpdf_load_folder_data`).

Bloqueado: `https://sapl.al.rr.leg.br` (projetos, votações, presença) responde 403 Forbidden.
Só PDF (não coletado): verbas até agosto/2025, diárias até setembro/2025 (página própria), resumos da folha.
Sem dado por deputado: gestão de pessoal (planilha de servidores sem remuneração). Emendas parlamentares: link vazio no portal.
"""

import re
import sys
import zipfile
from datetime import date
from html import unescape
from io import BytesIO
from xml.etree import ElementTree

import estaduais_comum as comum

UF = "RR"
SITE = "https://al.rr.leg.br"
LISTA_DEPUTADOS = f"{SITE}/deputados-estaduais-2023/"
TRANSP = "https://transparencia.al.rr.leg.br"
VERBAS_PAGINA = f"{TRANSP}/execucao-orcamentaria-e-financeira/verbas-indenizatorias-a-partir-de-set25/"
DIARIAS_PAGINA = f"{TRANSP}/execucao-orcamentaria-e-financeira/diarias-e-passagens-a-partir-de-out25/"
AJAX = f"{TRANSP}/wp-admin/admin-ajax.php"
MESES_REVISTOS = 2
NS_ODF = {"t": "urn:oasis:names:tc:opendocument:xmlns:table:1.0"}
NS_XLSX = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
TITULOS = {"dr", "dra", "prof", "profa", "coronel", "dep", "de", "da", "do", "dos", "das"}

GRUPOS = {"1": "Apoio à atividade parlamentar", "2": "Manutenção de escritório", "3": "Serviços postais", "4": "Apoio técnico",
          "5": "Assinatura de publicações", "6": "Divulgação de atividades parlamentares", "7": "Serviços de segurança",
          "8": "Pesquisas sócio-econômicas", "9": "Especialização de servidores de gabinete"}
CATEGORIAS = {
    "1.1": "Serviços gráficos", "1.2": "Locação ou aquisição de licença de software", "1.3": "Acesso à internet",
    "1.4": "Material de consumo e expediente", "1.5": "Suprimento de informática", "1.6": "Locação ou aquisição de equipamentos",
    "2.1": "Aluguel de imóveis", "2.2": "Taxas de condomínio", "2.3": "IPTU, taxa de coleta de lixo e seguro contra incêndio",
    "2.4": "Água, esgoto e demais taxas de serviços relacionados", "2.5": "Energia elétrica e demais taxas de serviços relacionados",
    "2.6": "Telefone fixo e/ou celular e taxa de instalação ou similares",
    "2.7": "Aquisição e instalação de equipamentos de segurança eletrônica", "2.8": "Serviços de manutenção preventiva e corretiva predial",
    "3.1": "Correspondências em geral", "3.2": "Sedex, carta registrada e similar",
    "4.1": "Consultoria e assessoria de imprensa", "4.2": "Serviços de contabilidade", "4.3": "Consultoria e assessoria jurídica",
    "4.4": "Consultoria técnica em outras áreas de conhecimento", "5.1": "Revistas, jornais e periódicos", "5.2": "Informativos técnicos e jurídicos",
    "6.1": "Divulgação de atividades parlamentares (meios de comunicação, blog, influenciadores digitais e similares)",
    "7.1": "Serviços de empresa especializada em segurança pessoal", "8.1": "Pesquisas sócio-econômicas",
    "9.1": "Inscrição em cursos, palestras, seminários, simpósios, congressos ou eventos",
}


def limpar(html: str) -> str:
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", html)).split())


def _tokens(nome: str) -> set:
    return {t for t in re.sub(r"[^a-z ]", " ", comum.sem_acento(nome)).split() if t not in TITULOS}


def _extremos(nome: str) -> tuple:
    palavras = [t for t in re.sub(r"[^a-z ]", " ", comum.sem_acento(nome)).split() if t not in TITULOS]
    return (palavras[0], palavras[-1]) if len(palavras) >= 2 else ()


def ligar(nomes, deputados: list[dict]) -> dict:
    """Como `ligar_nomes`; o nome que não casa inteiro casa quando todas as suas palavras estão em um só nome (urna ou civil)."""
    ligados = comum.ligar_nomes(nomes, deputados)
    for n in nomes:
        if n in ligados or not _tokens(n):
            continue
        ids = {d["id"] for d in deputados if any(d.get(c) and _tokens(n) <= _tokens(d[c]) for c in ("nome", "nomeCivil"))}
        if len(ids) != 1:
            ids = {d["id"] for d in deputados if _extremos(n) and any(d.get(c) and _extremos(n) == _extremos(d[c]) for c in ("nome", "nomeCivil"))}
        if len(ids) == 1:
            ligados[n] = next(iter(ids))
    return ligados


# ---------------------------------------------------------------- deputados

def cartoes(html: str) -> list[dict]:
    """[{slug, url, foto}] dos cartões da lista de deputados (um por deputado)."""
    achados = {}
    for url, slug, foto in re.findall(r'<a href="(https://al\.rr\.leg\.br/deputados/([\w-]+)/)"[^>]*><img[^>]*?\bsrc="([^"]+)"', html):
        achados.setdefault(slug, {"slug": slug, "url": url, "foto": unescape(foto)})
    return list(achados.values())


def parse_ficha(html: str) -> dict:
    """{nome, nomeCivil, partido, email} da página de um deputado (título, <h1> e meta og:description)."""
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    titulo = re.search(r"<title>(.*?)</title>", html, re.S)
    nome = limpar(h1.group(1)) if h1 else (limpar(titulo.group(1)).split("|")[0].strip() if titulo else None)
    og = re.search(r'<meta property="og:description" content="([^"]*)"', html)
    desc = limpar(og.group(1)) if og else ""
    civil = re.search(r"Nome:\s*(.+?)\s+Data\b", desc)
    partido = re.search(r"Partido:\s*(.+?)\s+Gabinete", desc)
    email = re.search(r"mailto:([^\"'\s>]+)", html) or re.search(r"e-mail:\s*(\S+@\S+)", desc)
    return {"nome": nome or None, "nomeCivil": civil.group(1).strip() if civil else None,
            "partido": partido.group(1).strip() if partido else None, "email": unescape(email.group(1)).strip() if email else None}


def coletar_deputados(s) -> list[dict]:
    r = s.get(LISTA_DEPUTADOS, timeout=20)
    r.raise_for_status()
    lista = []
    for c in cartoes(r.text):
        resp = s.get(c["url"], timeout=20)
        resp.raise_for_status()
        f = parse_ficha(resp.text)
        if not f["nome"]:
            continue
        lista.append({"id": c["slug"], "nome": f["nome"], "nomeCivil": f["nomeCivil"] or f["nome"], "foto": c["foto"], "email": f["email"],
                      "titular": True, "partido": f["partido"], "fonte": c["url"]})
    return lista


# ---------------------------------------------------------------- listas de arquivos (WP Display Files)

def credenciais(html: str) -> tuple[str, str]:
    nonce = re.search(r'"wpdf_nonce":"(\w+)"', html)
    sid = re.search(r'data-sid="(\d+)"', html)
    if not nonce or not sid:
        raise RuntimeError("página sem lista de arquivos (wpdf_nonce/data-sid)")
    return nonce.group(1), sid.group(1)


def entradas(html: str) -> tuple[list[tuple[str, str]], list[dict]]:
    """([(nome, caminho)] das pastas, [{nome, tipo, url}] dos arquivos) de um trecho de lista."""
    pastas = [(unescape(n), unescape(c)) for n, c in re.findall(r'<li data-type="folder" data-name="([^"]+)" data-path="([^"]+)"', html)]
    arquivos = []
    for nome, tipo, corpo in re.findall(r'<li class="file_record" data-name="([^"]+)" data-file-type="(\w+)">(.*?)</li>', html, re.S):
        href = re.search(r'href="([^"]*wpdf_download[^"]*)"', corpo)
        if href:
            arquivos.append({"nome": unescape(nome), "tipo": tipo.lower(), "url": unescape(href.group(1))})
    return pastas, arquivos


class Lista:
    def __init__(self, s, pagina: str):
        self.s, self.pagina = s, pagina
        r = s.get(pagina, timeout=20)
        r.raise_for_status()
        self.nonce, self.sid = credenciais(r.text)
        self.raiz = entradas(r.text)

    def pasta(self, caminho: str) -> tuple[list, list]:
        r = self.s.post(AJAX, data={"action": "wpdf_load_folder_data", "folder_name": caminho.rstrip("/").split("/")[-1], "folder_path": caminho,
                                    "sid": self.sid, "wpdf_nonce": self.nonce}, timeout=20)
        r.raise_for_status()
        return entradas(r.json().get("inner_content", ""))


def numero_do_mes(nome_pasta: str) -> int | None:
    m = re.match(r"\s*(\d{1,2})\s*-", nome_pasta)
    if m:
        return int(m.group(1)) if 1 <= int(m.group(1)) <= 12 else None
    palavras = re.findall(r"[^\W\d_]+", nome_pasta)
    return comum.mes_numero(palavras[0]) if palavras else None


def ano_da_pasta(nome_pasta: str) -> int | None:
    m = re.search(r"(20\d\d)", nome_pasta)
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------- leitura de ODT/ODS/XLSX

def _texto_celula(c) -> str:
    return "".join(c.itertext()).strip()


def linhas_odf(conteudo: bytes) -> list[list[str]]:
    """Linhas de todas as tabelas de um ODT/ODS (células em ordem; colunas repetidas contam uma vez)."""
    raiz = ElementTree.fromstring(zipfile.ZipFile(BytesIO(conteudo)).read("content.xml"))
    linhas = []
    for linha in raiz.iter("{%s}table-row" % NS_ODF["t"]):
        celulas = []
        for c in linha.findall("t:table-cell", NS_ODF):
            repete = int(c.get("{%s}number-columns-repeated" % NS_ODF["t"], 1))
            celulas += [_texto_celula(c)] * (repete if _texto_celula(c) and repete < 50 else 1)
        if any(celulas):
            linhas.append(celulas)
    return linhas


def linhas_xlsx(conteudo: bytes) -> list[list[str]]:
    """Linhas da primeira aba de um XLSX, com as colunas A, B, C... preenchidas em ordem (vazia = "")."""
    z = zipfile.ZipFile(BytesIO(conteudo))
    strings = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ElementTree.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS_XLSX):
            strings.append("".join(t.text or "" for t in si.iter("{%s}t" % NS_XLSX["m"])))
    linhas = []
    for row in ElementTree.fromstring(z.read("xl/worksheets/sheet1.xml")).iter("{%s}row" % NS_XLSX["m"]):
        celulas = {}
        for c in row.findall("m:c", NS_XLSX):
            v = c.find("m:v", NS_XLSX)
            if v is None or v.text is None:
                continue
            col = re.match(r"[A-Z]+", c.get("r")).group(0)
            idx = 0
            for ch in col:
                idx = idx * 26 + ord(ch) - 64
            celulas[idx - 1] = strings[int(v.text)] if c.get("t") == "s" else v.text
        if celulas:
            linhas.append([celulas.get(i, "") for i in range(max(celulas) + 1)])
    return linhas


def linhas_planilha(conteudo: bytes, tipo: str) -> list[list[str]]:
    return linhas_xlsx(conteudo) if tipo == "xlsx" else linhas_odf(conteudo)


# ---------------------------------------------------------------- verba indenizatória

def parse_verba(linhas: list[list[str]]) -> list[dict]:
    """[{item, categoria, grupo, valor}] das linhas de despesa com valor de um demonstrativo mensal."""
    itens = []
    for l in linhas:
        if len(l) >= 3 and re.fullmatch(r"\d\.\d+", l[0].strip()):
            valor = comum.valor_br(l[2])
            if valor:
                cod = l[0].strip()
                itens.append({"item": cod, "categoria": CATEGORIAS.get(cod, l[1].strip()), "grupo": GRUPOS.get(cod.split(".")[0]), "valor": valor})
    return itens


def nome_do_arquivo(nome: str) -> str | None:
    """"Dep. Fulano de Tal - Janeiro 2026.odt" -> "Fulano de Tal"."""
    base = re.sub(r"\.\w+$", "", nome)
    m = re.match(r"\s*Dep\.?\s*(.*?)\s*-\s*[^\W\d_]+\s*\d{4}\s*$", base)
    return m.group(1).strip() if m else None


def itens_verba(arquivos: list[dict], baixar, deputados: list[dict], ano: int, mes: int) -> list[dict]:
    """Verbas de um mês: `baixar(url)` devolve os bytes do ODT; a fonte de cada item é o PDF do mesmo deputado e mês (ou o próprio ODT)."""
    por_nome: dict[str, dict] = {}
    for a in arquivos:
        nome = nome_do_arquivo(a["nome"])
        if nome and a["tipo"] in ("odt", "pdf"):
            por_nome.setdefault(nome, {})[a["tipo"]] = a["url"]
    ligados = ligar(list(por_nome), deputados)
    itens = []
    for nome, urls in por_nome.items():
        if nome not in ligados:
            comum.avisar(f"RR: verba de {nome!r} não casou com nenhum deputado")
            continue
        if "odt" not in urls:
            continue
        for i in parse_verba(linhas_odf(baixar(urls["odt"]))):
            itens.append({"idDeputado": ligados[nome], "mes": mes, "categoria": i["categoria"], "fornecedor": None, "cnpj": None, "valor": i["valor"],
                          "item": i["item"], "grupo": i["grupo"], "fonte": urls.get("pdf") or urls["odt"]})
    return itens


# ---------------------------------------------------------------- diárias

def _ano(a: str) -> int:
    return int(a) + (2000 if len(a) == 2 else 0)


def periodo_para_datas(periodo: str) -> tuple[str | None, str | None]:
    """Período do demonstrativo -> (início, fim) em AAAA-MM-DD. Aceita "25/02 A 01/03/2026", "17 A 20/07/26", "15 E 16/6/2026",
    "05/02/2026" e o número de série do Excel ("46197")."""
    texto = (periodo or "").strip()
    if re.fullmatch(r"\d{5}(\.\d+)?", texto):
        dia = date.fromordinal(date(1899, 12, 30).toordinal() + int(float(texto))).isoformat()
        return dia, dia
    partes = re.findall(r"\d{1,2}(?:/\d{1,2}(?:/\d{2,4})?)?", texto)
    if not partes:
        return None, None
    fim_p = partes[-1].split("/")
    if len(fim_p) != 3:
        return None, None
    try:
        fim = date(_ano(fim_p[2]), int(fim_p[1]), int(fim_p[0]))
    except ValueError:
        return None, None
    ini_p = partes[0].split("/")
    try:
        mes_ini = int(ini_p[1]) if len(ini_p) > 1 else (fim.month if int(ini_p[0]) <= fim.day else fim.month - 1 or 12)
        ano_ini = _ano(ini_p[2]) if len(ini_p) > 2 else (fim.year if mes_ini <= fim.month else fim.year - 1)
        return date(ano_ini, mes_ini, int(ini_p[0])).isoformat(), fim.isoformat()
    except ValueError:
        return None, fim.isoformat()


def registros_diarias(linhas: list[list[str]]) -> list[dict]:
    """Linhas de deputados (cargo "DEPUTADO(A)") do demonstrativo; as colunas vêm do cabeçalho (NOME, CARGO, DESTINO, FINALIDADE, PERÍODO, VALOR)."""
    cab = next((i for i, l in enumerate(linhas) if {"nome", "cargo", "destino"} <= {comum.sem_acento(c) for c in l}), None)
    if cab is None:
        return []
    col = {comum.sem_acento(c): i for i, c in enumerate(linhas[cab]) if c}
    registros = []
    for l in linhas[cab + 1:]:
        def campo(nome):
            i = col.get(nome)
            return l[i].strip() if i is not None and i < len(l) else ""
        if comum.sem_acento(campo("cargo")).startswith("deputad") and campo("nome"):
            registros.append({"nome": campo("nome"), "destino": campo("destino"), "motivo": campo("finalidade"), "periodo": campo("periodo"),
                              "valor": comum.valor_br(campo("valor"))})
    return registros


def itens_diarias(registros: list[dict], deputados: list[dict], fonte: str) -> list[dict]:
    ligados = ligar({r["nome"] for r in registros}, deputados)
    itens = []
    for r in registros:
        if r["nome"] not in ligados:
            comum.avisar(f"RR: diária de {r['nome']!r} não casou com nenhum deputado")
            continue
        ini, fim = periodo_para_datas(r["periodo"])
        itens.append({"idDeputado": ligados[r["nome"]], "data": ini or fim, "dataFim": fim, "destino": r["destino"] or None, "motivo": r["motivo"] or None,
                      "valor": r["valor"], "fonte": fonte})
    return itens


# ---------------------------------------------------------------- coleta

def _baixar(s):
    def baixar(url):
        r = s.get(url, timeout=60)
        r.raise_for_status()
        return r.content
    return baixar


def _meses(lista: Lista):
    """(ano, mês, caminho da pasta) de cada pasta mensal da lista, do mais antigo ao mais novo."""
    achados = []
    for nome_ano, caminho_ano in lista.raiz[0]:
        ano = ano_da_pasta(nome_ano)
        for nome_mes, caminho_mes in lista.pasta(caminho_ano)[0]:
            mes = numero_do_mes(nome_mes)
            if ano and mes:
                achados.append((ano, mes, caminho_mes))
    return sorted(achados)


def coletar_verbas(s, deputados: list[dict], pasta, hoje: date) -> None:
    lista = Lista(s, VERBAS_PAGINA)
    baixar = _baixar(s)
    atual = hoje.year * 12 + hoje.month
    por_ano: dict[int, dict] = {}
    for ano, mes, caminho in _meses(lista):
        envelope = por_ano.setdefault(ano, comum.ler(pasta / f"verbas_{ano}.json", {"itens": [], "mesesColetados": []}))
        if mes in envelope.get("mesesColetados", []) and atual - (ano * 12 + mes) > MESES_REVISTOS:
            continue
        arquivos = lista.pasta(caminho)[1]
        novos = itens_verba(arquivos, baixar, deputados, ano, mes)
        if not novos and not arquivos:
            continue
        envelope["itens"] = [i for i in envelope["itens"] if i["mes"] != mes] + novos
        envelope["mesesColetados"] = sorted(set(envelope.get("mesesColetados", [])) | {mes})
    for ano, envelope in por_ano.items():
        comum.salvar(pasta / f"verbas_{ano}.json", {"coletadoEm": hoje.isoformat(), "fonte": VERBAS_PAGINA, "mesesColetados": envelope["mesesColetados"],
                                                    "itens": sorted(envelope["itens"], key=lambda i: (i["mes"], str(i["idDeputado"]), i["item"]))})
        print(f"RR: verbas {ano} {len(envelope['itens'])} lançamentos em {len(envelope['mesesColetados'])} meses")


def coletar_diarias(s, deputados: list[dict], pasta, hoje: date) -> None:
    lista = Lista(s, DIARIAS_PAGINA)
    baixar = _baixar(s)
    por_ano: dict[int, list] = {}
    for ano, mes, caminho in _meses(lista):
        arquivos = lista.pasta(caminho)[1]
        pdfs = [a for a in arquivos if a["tipo"] == "pdf" and not re.search(r"sem efeito", a["nome"], re.I)]
        planilhas = [a for a in arquivos if a["tipo"] in ("xlsx", "ods") and not re.search(r"sem efeito", a["nome"], re.I)]
        for p in planilhas:
            registros = registros_diarias(linhas_planilha(baixar(p["url"]), p["tipo"]))
            for i in itens_diarias(registros, deputados, (pdfs[0] if pdfs else p)["url"]):
                por_ano.setdefault(int((i["data"] or f"{ano}")[:4]), []).append(i)
    for ano, itens in sorted(por_ano.items()):
        itens.sort(key=lambda i: (i["data"] or "", str(i["idDeputado"])))
        comum.salvar(pasta / f"diarias_{ano}.json", {"coletadoEm": hoje.isoformat(), "fonte": DIARIAS_PAGINA, "itens": itens})
        print(f"RR: diárias {ano} {len(itens)} registros")


def coletar() -> None:
    pasta = comum.DADOS / UF
    hoje = date.today()
    s = comum.sessao()
    deputados = coletar_deputados(s)
    if not deputados:
        comum.avisar("RR: lista de deputados vazia")
        return
    comum.salvar(pasta / "deputados.json", {"fonte": LISTA_DEPUTADOS, "host": None, "legislatura": "2023-2027", "deputados": deputados})
    print(f"RR: {len(deputados)} deputados")
    coletar_verbas(s, deputados, pasta, hoje)
    coletar_diarias(s, deputados, pasta, hoje)


# ---------------------------------------------------------------- contratos

def _get(url: str):
    r = comum.sessao().get(url, timeout=30)
    r.raise_for_status()
    return r


def _contrato_deputados(ctx):
    html = _get(LISTA_DEPUTADOS).text
    ancoras = re.findall(r'<a href="https://al\.rr\.leg\.br/deputados/[\w-]+/"[^>]*><img[^>]*?\bsrc="[^"]+"', html)[:3]
    primeiro = cartoes(html)[0]
    ficha = _get(primeiro["url"]).text
    titulo = re.search(r"<title>.*?</title>", ficha, re.S).group(0)
    h1 = re.search(r"<h1[^>]*>.*?</h1>", ficha, re.S).group(0)
    og = re.search(r'<meta property="og:description" content="[^"]*"', ficha).group(0)
    mail = re.search(r'<a href="mailto:[^"]+"', ficha)
    return {"lista": "\n".join(ancoras), "ficha": "\n".join([titulo, h1, og, mail.group(0) if mail else ""])}


def _conferir_deputados(registro):
    falhas = []
    if not cartoes(registro["lista"]):
        falhas.append("lista de deputados sem cartões (link da ficha + foto)")
    f = parse_ficha(registro["ficha"])
    for campo in ("nome", "nomeCivil", "partido"):
        if not f[campo]:
            falhas.append(f"ficha de deputado sem {campo}")
    return falhas, [] if f["email"] else ["ficha sem e-mail"]


def _contrato_listagem(ctx):
    lista = Lista(comum.sessao(), VERBAS_PAGINA)
    ano = lista.raiz[0][-1][1]
    mes = lista.pasta(ano)[0][-1][1]
    r = comum.sessao().post(AJAX, data={"action": "wpdf_load_folder_data", "folder_name": mes.rstrip("/").split("/")[-1], "folder_path": mes,
                                        "sid": lista.sid, "wpdf_nonce": lista.nonce}, timeout=20)
    r.raise_for_status()
    interno = r.json()["inner_content"]
    trechos = re.findall(r'<li class="file_record".*?</li>', interno, re.S)[:4]
    return {"raiz": "".join(f'<li data-type="folder" data-name="{n}" data-path="{c}"></li>' for n, c in lista.raiz[0]), "pasta": "".join(trechos)}


def _conferir_listagem(registro):
    falhas = []
    if not entradas(registro["raiz"])[0]:
        falhas.append("lista de arquivos sem pastas por ano")
    arquivos = entradas(registro["pasta"])[1]
    if not arquivos:
        falhas.append("pasta mensal sem arquivos com link de download")
    for a in arquivos:
        if nome_do_arquivo(a["nome"]) is None:
            falhas.append(f"nome de arquivo fora do padrão 'Dep. Nome - Mês Ano': {a['nome']}")
    return falhas, []


def _contrato_verba(ctx):
    lista = Lista(comum.sessao(), VERBAS_PAGINA)
    mes = lista.pasta(lista.raiz[0][-1][1])[0][-1][1]
    odt = next(a for a in lista.pasta(mes)[1] if a["tipo"] == "odt")
    linhas = linhas_odf(_get(odt["url"]).content)
    return {"arquivo": odt["nome"], "linhas": linhas}


def _conferir_verba(registro):
    falhas = []
    if nome_do_arquivo(registro["arquivo"]) is None:
        falhas.append("nome do ODT fora do padrão")
    itens = parse_verba(registro["linhas"])
    if not itens:
        falhas.append("demonstrativo sem item de despesa com valor")
    todos = [l for l in registro["linhas"] if len(l) >= 2 and re.fullmatch(r"\d\.\d+", l[0].strip())]
    desconhecidos = [l[0] for l in todos if l[0].strip() not in CATEGORIAS]
    return falhas, [f"item de despesa novo: {', '.join(desconhecidos)}"] if desconhecidos else []


def _indice_cabecalho(linhas):
    return next((i for i, l in enumerate(linhas) if {"nome", "cargo", "destino"} <= {comum.sem_acento(c) for c in l}), None)


def _contrato_diarias(ctx):
    lista = Lista(comum.sessao(), DIARIAS_PAGINA)
    for _, _, caminho in reversed(_meses(lista)):
        for a in lista.pasta(caminho)[1]:
            if a["tipo"] in ("xlsx", "ods") and not re.search(r"sem efeito", a["nome"], re.I):
                linhas = linhas_planilha(_get(a["url"]).content, a["tipo"])
                cab = _indice_cabecalho(linhas)
                if cab is None:
                    continue
                deputados = [l for l in linhas[cab + 1:] if any(re.match(r"(?i)deputad", c) for c in l)][:3]
                if deputados:
                    return {"arquivo": a["nome"], "linhas": [*linhas[: cab + 1], *deputados]}
    raise RuntimeError("nenhuma planilha de diárias com linha de deputado")


def _conferir_diarias(registro):
    falhas = []
    registros = registros_diarias(registro["linhas"])
    if not registros:
        falhas.append("planilha de diárias sem linha de deputado (cabeçalho NOME/CARGO/DESTINO mudou?)")
    for r in registros:
        ini, fim = periodo_para_datas(r["periodo"])
        if not fim:
            falhas.append(f"período ilegível: {r['periodo']!r}")
        if r["valor"] is None:
            falhas.append("diária sem valor")
    return falhas, []


CONTRATOS = [
    dict(nome="estadual_rr_deputados", fonte=LISTA_DEPUTADOS, buscar=_contrato_deputados, html=_conferir_deputados),
    dict(nome="estadual_rr_listagem", fonte=VERBAS_PAGINA, buscar=_contrato_listagem, html=_conferir_listagem),
    dict(nome="estadual_rr_verba", fonte=VERBAS_PAGINA, buscar=_contrato_verba, html=_conferir_verba),
    dict(nome="estadual_rr_diarias", fonte=DIARIAS_PAGINA, buscar=_contrato_diarias, html=_conferir_diarias),
]


if __name__ == "__main__":
    coletar()
    sys.exit(0)
