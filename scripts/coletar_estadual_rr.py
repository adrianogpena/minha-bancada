"""
Deputados estaduais de Roraima (ALE-RR), fora do SAPL.

Fontes abertas e lidas aqui:
  - deputados (nome parlamentar, nome civil, partido, foto, e-mail, ficha): https://al.rr.leg.br/deputados-estaduais-2023/ e a ficha de cada um;
  - verba indenizatória (ressarcimento de despesas parlamentares): um ODT por deputado e mês no portal da transparência, a partir de
    setembro de 2025 (resolução 036/2021), lido como tabela: uma linha por item de despesa com valor;
  - diárias: planilha mensal (XLSX/ODS) a partir de outubro de 2025; só as linhas de cargo "DEPUTADO(A)".
  Os dois últimos ficam em listas de arquivos do plugin WP Display Files (admin-ajax `wpdf_load_folder_data`), como as três seguintes;
  - gabinete: "CONSULTA SERVIDORES.xlsx" mensal (gestão de pessoal), só o setor "GAB. DEP. <nome>"; sem remuneração;
  - contratos do órgão: pastas por processo com os PDFs do contrato (só os links; fornecedor e valor estão só no PDF);
  - licitações e contratações diretas (dispensa, inexigibilidade): XLSX mensal, acumulado no ano.

Bloqueado: `https://sapl.al.rr.leg.br` (projetos, votações, presença) responde 403 Forbidden.
Só PDF (não coletado): verbas até agosto/2025, diárias até setembro/2025 (página própria), resumos da folha.
Sem dado: remuneração (a planilha de pessoal não traz valores). Emendas parlamentares: link vazio no portal.
"""

import re
import zipfile
from datetime import date
from html import unescape
from io import BytesIO
from functools import partial
from defusedxml import ElementTree

import estaduais_comum as comum
import identidades
import ids

UF = "RR"
SITE = "https://al.rr.leg.br"
LISTA_DEPUTADOS = f"{SITE}/deputados-estaduais-2023/"
TRANSP = "https://transparencia.al.rr.leg.br"
VERBAS_PAGINA = f"{TRANSP}/execucao-orcamentaria-e-financeira/verbas-indenizatorias-a-partir-de-set25/"
DIARIAS_PAGINA = f"{TRANSP}/execucao-orcamentaria-e-financeira/diarias-e-passagens-a-partir-de-out25/"
GESTAO_PAGINA = f"{TRANSP}/execucao-orcamentaria-e-financeira/gestao-de-pessoal-a-partir-de-set25/"
CONTRATOS_PAGINA = f"{TRANSP}/execucao-orcamentaria-e-financeira/contratos-a-partir-de-out25/"
LICITACOES_PAGINA = f"{TRANSP}/execucao-orcamentaria-e-financeira/licitacoes-a-partir-de-out25/"
AJAX = f"{TRANSP}/wp-admin/admin-ajax.php"
FONTE_ID = "alerr_rr"
PEQUENAS = {"de", "da", "do", "das", "dos", "e"}
MESES_REVISTOS = 2
NS_ODF = {"t": "urn:oasis:names:tc:opendocument:xmlns:table:1.0"}

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


ligar = partial(identidades.ligar_nomes, uf=UF)


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
    nome = comum.limpar(h1.group(1)) if h1 else (comum.limpar(titulo.group(1)).split("|")[0].strip() if titulo else None)
    og = re.search(r'<meta property="og:description" content="([^"]*)"', html)
    desc = comum.limpar(og.group(1)) if og else ""
    civil = re.search(r"Nome:\s*(.+?)\s+Data\b", desc)
    partido = re.search(r"Partido:\s*(.+?)\s+Gabinete", desc)
    email = re.search(r"mailto:([^\"'\s>]+)", html) or re.search(r"e-mail:\s*(\S+@\S+)", desc)
    return {"nome": nome or None, "nomeCivil": civil.group(1).strip() if civil else None,
            "partido": comum.sigla_partido(partido.group(1)) if partido else None, "email": comum.email(email.group(1)) if email else None}


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
    for linha in raiz.iter("{{{}}}table-row".format(NS_ODF["t"])):
        celulas = []
        for c in linha.findall("t:table-cell", NS_ODF):
            repete = int(c.get("{{{}}}number-columns-repeated".format(NS_ODF["t"]), 1))
            celulas += [_texto_celula(c)] * (repete if _texto_celula(c) and repete < 50 else 1)
        if any(celulas):
            linhas.append(celulas)
    return linhas


def linhas_xlsx(conteudo: bytes) -> list[list[str]]:
    """Linhas da primeira aba de um XLSX, com as colunas A, B, C... preenchidas em ordem (vazia = "")."""
    linhas = []
    for linha in comum.xlsx_linhas(conteudo, aparar=False):
        celulas = {}
        for col, valor in linha.items():
            idx = 0
            for ch in col:
                idx = idx * 26 + ord(ch) - 64
            celulas[idx - 1] = valor
        linhas.append([celulas.get(i, "") for i in range(max(celulas) + 1)])
    return linhas


def linhas_planilha(conteudo: bytes, tipo: str) -> list[list[str]]:
    return linhas_xlsx(conteudo) if tipo == "xlsx" else linhas_odf(conteudo)


# ---------------------------------------------------------------- verba indenizatória

def parse_verba(linhas: list[list[str]]) -> list[dict]:
    """[{item, categoria, grupo, valor}] das linhas de despesa com valor de um demonstrativo mensal."""
    itens = []
    for lin in linhas:
        if len(lin) >= 3 and re.fullmatch(r"\d\.\d+", lin[0].strip()):
            valor = comum.valor_br(lin[2])
            if valor:
                cod = lin[0].strip()
                itens.append({"item": cod, "categoria": CATEGORIAS.get(cod, lin[1].strip()), "grupo": GRUPOS.get(cod.split(".")[0]), "valor": valor})
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
        itens.extend({"idDeputado": ligados[nome], "mes": mes, "categoria": i["categoria"], "fornecedor": None, "cnpj": None, "valor": i["valor"],
                      "item": i["item"], "grupo": i["grupo"], "fonte": urls.get("pdf") or urls["odt"]}
                     for i in parse_verba(linhas_odf(baixar(urls["odt"]))))
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
    cab = next((i for i, lin in enumerate(linhas) if {"nome", "cargo", "destino"} <= {comum.sem_acento(c) for c in lin}), None)
    if cab is None:
        return []
    col = {comum.sem_acento(c): i for i, c in enumerate(linhas[cab]) if c}
    registros = []
    for lin in linhas[cab + 1:]:
        def campo(nome, lin=lin):
            i = col.get(nome)
            return lin[i].strip() if i is not None and i < len(lin) else ""
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


# ---------------------------------------------------------------- gabinete

def titulo(nome: str) -> str:
    palavras = (nome or "").lower().split()
    return " ".join(p if (i and p in PEQUENAS) else p.capitalize() for i, p in enumerate(palavras))


def simbolo_do_cargo(cargo: str | None) -> tuple[str | None, str | None]:
    """"FS-11 Secretario Parlamentar " -> ("FS-11", "Secretario Parlamentar"); cargo sem símbolo ("MOTORISTA") -> (None, cargo)."""
    c = comum.compactar(cargo)
    m = re.match(r"([A-Z]{1,4}-[A-Z0-9]+)\s+(.*)$", c or "")
    return (m.group(1), m.group(2)) if m else (None, c)


def servidores_do_gabinete(linhas: list[list[str]], deputados: list[dict]) -> list[dict]:
    """Servidores lotados em "GAB. DEP. <nome>" da planilha de pessoal (colunas pelo cabeçalho). O gabinete só vale se o nome liga a um
    único deputado (`ligar`); presidência, lideranças e unidades ficam de fora. A planilha só lista quem está na folha do mês, sem
    remuneração. O id sai da matrícula que a fonte publica."""
    cab = next((i for i, lin in enumerate(linhas) if {"matricula", "nome", "setor"} <= {comum.sem_acento(c) for c in lin}), None)
    if cab is None:
        return []
    col = {comum.sem_acento(c): i for i, c in enumerate(linhas[cab])}

    def campo(lin, nome):
        i = next((i for c, i in col.items() if c.startswith(nome)), None)
        return lin[i].strip() if i is not None and i < len(lin) else ""

    registros = [lin for lin in linhas[cab + 1:] if re.match(r"GAB\. DEP\. \S", campo(lin, "setor"))]
    nomes = {campo(lin, "setor"): campo(lin, "setor")[len("GAB. DEP. "):].strip() for lin in registros}
    ligados = ligar(set(nomes.values()), deputados)
    itens = {}
    for lin in registros:
        id_dep, matricula, nome = ligados.get(nomes[campo(lin, "setor")]), campo(lin, "matricula"), campo(lin, "nome")
        if not id_dep or not matricula or not nome:
            continue
        simbolo, cargo = simbolo_do_cargo(campo(lin, "cargo"))
        iid = ids.gerar_id("srv", FONTE_ID, matricula)
        itens[iid] = {"id": iid, "idDeputado": id_dep, "matricula": matricula, "nome": titulo(nome), "cargo": cargo, "simbolo": simbolo,
                      "vinculo": comum.compactar(campo(lin, "desc")), "admissao": comum.data_br_iso(campo(lin, "dt"))}
    return sorted(itens.values(), key=lambda i: (i["idDeputado"], i["simbolo"] or "", i["nome"], i["matricula"]))


def coletar_gabinete(s, deputados: list[dict], pasta, hoje: date) -> None:
    lista = Lista(s, GESTAO_PAGINA)
    for ano, mes, caminho in reversed(_meses(lista)):
        planilha = next((a for a in lista.pasta(caminho)[1] if a["tipo"] == "xlsx" and "servidores" in comum.sem_acento(a["nome"])), None)
        if planilha:
            break
    else:
        raise RuntimeError("gestão de pessoal sem planilha CONSULTA SERVIDORES")
    itens = servidores_do_gabinete(linhas_xlsx(_baixar(s)(planilha["url"])), deputados)
    if not itens:
        raise RuntimeError("nenhum servidor ligado a gabinete de deputado; mantém o arquivo anterior")
    comum.salvar(pasta / "gabinete.json", {"coletadoEm": hoje.isoformat(), "referencia": f"{ano}-{mes:02d}", "fonte": GESTAO_PAGINA, "itens": itens})
    print(f"RR: gabinetes {len(itens)} servidores de {len({i['idDeputado'] for i in itens})} deputados ({mes:02d}/{ano})")


# ---------------------------------------------------------------- contratos do órgão (pastas por processo, só links)

NUMERO_CONTRATO = re.compile(r"CONTRATO[\s\-]+0*(\d+)-(\d{4})", re.I)


def rotulo_do_arquivo(nome: str) -> str:
    base = "Documento"
    for padrao, rotulo in ((r"ADITIVO", "Termo aditivo"), (r"APOSTIL", "Termo de apostilamento"), (r"RERRATIFIC", "Termo de rerratificação"),
                           (r"CONTRATO", "Contrato")):
        if re.search(padrao, nome, re.I):
            base = rotulo
            break
    return f"Publicação: {base.lower()}" if re.search(r"PUBLIC", nome, re.I) else base


def contratos_da_pasta(nome_pasta: str, arquivos: list[dict], fonte: str) -> dict:
    """{id: item} dos contratos de uma pasta de processo, no formato de `comum.item_orgao`. Um contrato por número "NN-AAAA" dos
    arquivos que começam com CONTRATO (sem publicação); os demais PDFs vão para o contrato do mesmo número ou, sendo um só na pasta,
    para ele. Pasta sem contrato (só empenho) não gera item. Fornecedor, valor e vigência ficam só no PDF: não são lidos."""
    pdfs = [a for a in arquivos if a["tipo"] == "pdf"]
    contratos = {}
    for a in pdfs:
        m = NUMERO_CONTRATO.match(a["nome"])
        if m and not re.search(r"PUBLIC", a["nome"], re.I):
            contratos.setdefault((int(m.group(2)), int(m.group(1))), [])
    if not contratos:
        return {}
    for a in sorted(pdfs, key=lambda a: (bool(re.search(r"PUBLIC", a["nome"], re.I)), a["nome"])):
        m = NUMERO_CONTRATO.search(a["nome"])
        chave = (int(m.group(2)), int(m.group(1))) if m else None
        if chave not in contratos:
            if len(contratos) != 1:
                continue
            chave = next(iter(contratos))
        contratos[chave].append({"url": a["url"], "nome": rotulo_do_arquivo(a["nome"]), "data": None})
    processo = re.search(r"(\d+)-(\d{4})\s*$", nome_pasta.strip())
    itens = {}
    for (ano, n), arquivos_c in sorted(contratos.items()):
        numero = f"{n:02d}/{ano}"
        iid, item = comum.item_orgao(FONTE_ID, "contrato", numero, fornecedor_nome=None, numero=numero, arquivos=arquivos_c, fonte=fonte,
                                     processo=f"{int(processo.group(1))}/{processo.group(2)}" if processo else None)
        itens[iid] = item
    return itens


def coletar_contratos(s, pasta, hoje: date) -> None:
    lista = Lista(s, CONTRATOS_PAGINA)
    for nome_ano, caminho_ano in lista.raiz[0]:
        ano = ano_da_pasta(nome_ano)
        if not ano or comum.ano_encerrado(ano, hoje, pasta / f"orgao_{ano}.json"):
            continue
        comum.tentar(UF, f"contratos {ano}", partial(contratos_do_ano, lista, caminho_ano, ano, pasta / f"orgao_{ano}.json", hoje))


def contratos_do_ano(lista: Lista, caminho_ano: str, ano: int, arq, hoje: date) -> None:
    itens = {}
    for nome, caminho in lista.pasta(caminho_ano)[0]:
        itens |= contratos_da_pasta(nome, lista.pasta(caminho)[1], CONTRATOS_PAGINA)
    if not itens and comum.ler(arq, {}).get("itens"):
        raise RuntimeError(f"{ano} sem contrato na lista; mantém o arquivo anterior")
    comum.salvar(arq, {"coletadoEm": hoje.isoformat(), "fonte": CONTRATOS_PAGINA, "itens": itens})
    print(f"RR: {ano} contratos {len(itens)} do órgão (só links dos PDFs)")


# ---------------------------------------------------------------- licitações e contratações diretas (XLSX mensal acumulado no ano)

CNPJ_NO_TEXTO = re.compile(r"\d{2}\.?\d{3}\.?\d{3}/\d{4}-?\d{2}")
TIPOS_LICITACAO = ("licitacao", "contratacao_direta")


def tipo_da_planilha(nome: str) -> str | None:
    n = nome.upper()
    if not n.endswith(".XLSX"):
        return None
    return "contratacao_direta" if "DIRETAS" in n else "licitacao" if "LICITA" in n else None


def cnpj_do_texto(texto: str | None) -> str | None:
    """CNPJ válido quando o texto do vencedor traz exatamente um ("LOTE ÚNICO: GRZ LTDA CNPJ: 07.872.397/0001-50")."""
    import fornecedores
    achados = {re.sub(r"\D", "", c) for c in CNPJ_NO_TEXTO.findall(texto or "")}
    doc = fornecedores.documento(next(iter(achados))) if len(achados) == 1 else None
    return doc[1] if doc and doc[0] == "cnpj" else None


def itens_licitacoes(linhas: list[list[str]], tipo: str, fonte: str, mes: int) -> dict:
    """{id: item} de uma planilha de licitações ou de contratações diretas (dispensa e inexigibilidade). As colunas vêm do cabeçalho
    (mudam de ordem entre meses); a planilha de cada mês traz o ano inteiro, então a mais nova vale. Id do processo (e do número do
    procedimento nas diretas, em que um processo tem várias dispensas); se ainda repetir, acrescenta o edital."""
    cab = next((i for i, lin in enumerate(linhas) if any(comum.sem_acento(c) == "objeto" for c in lin)), None)
    if cab is None:
        return {}
    col = [comum.sem_acento(c) for c in linhas[cab]]

    def achar(teste):
        return next((i for i, c in enumerate(col) if teste(c)), None)

    pos = {"procedimento": achar(lambda c: c.startswith("procedimento")), "processo": achar(lambda c: "processo" in c),
           "edital": achar(lambda c: "edital" in c), "modalidade": achar(lambda c: c.startswith("modalidade")),
           "objeto": achar(lambda c: c == "objeto"), "estimado": achar(lambda c: c.startswith("despesa")),
           "vencedor": achar(lambda c: c.startswith("vencedor")), "data": achar(lambda c: c == "data"),
           "valor": achar(lambda c: c.startswith("valor homologado")), "situacao": achar(lambda c: c.startswith("situa"))}
    itens, vistos = {}, set()
    for lin in linhas[cab + 1:]:
        def campo(nome, lin=lin):
            i = pos.get(nome)
            return lin[i].strip() if i is not None and i < len(lin) else ""

        def valor(nome):
            return comum.valor_br(campo(nome)) if campo(nome) not in ("", "-") else None
        if not campo("objeto") or not campo("processo"):
            continue
        base = f"{campo('procedimento')}|{campo('processo')}" if tipo == "contratacao_direta" else campo("processo")
        idf = base if base not in vistos else f"{base}|{campo('edital')}"
        vistos.add(base)
        vencedor = comum.compactar(campo("vencedor"))
        diario = bool(vencedor and re.match(r"DOALE", vencedor, re.I))
        iid = ids.gerar_id("lic", f"{FONTE_ID}_{tipo}", idf)
        itens[iid] = {"tipo": tipo, "idFonte": idf, "processo": campo("processo"), "procedimento": campo("procedimento") or None,
                      "edital": campo("edital") or None, "modalidade": comum.compactar(campo("modalidade")), "objeto": comum.compactar(campo("objeto")),
                      "valorEstimado": valor("estimado"), "vencedor": None if diario or vencedor in (None, "-") else vencedor,
                      "cnpj": cnpj_do_texto(vencedor), "referenciaDiario": vencedor if diario else None,
                      "data": periodo_para_datas(campo("data"))[1], "valorHomologado": valor("valor"),
                      "situacao": comum.compactar(campo("situacao")), "mes": mes, "fonte": fonte}
    return itens


def coletar_licitacoes(s, pasta, hoje: date) -> None:
    lista = Lista(s, LICITACOES_PAGINA)
    baixar = _baixar(s)
    meses_por_ano: dict[int, list] = {}
    for ano, mes, caminho in _meses(lista):
        meses_por_ano.setdefault(ano, []).append((mes, caminho))
    for ano, meses in sorted(meses_por_ano.items()):
        arq = pasta / f"licitacoes_{ano}.json"
        if comum.ano_encerrado(ano, hoje, arq):
            continue
        comum.tentar(UF, f"licitações {ano}", partial(licitacoes_do_ano, lista, baixar, ano, sorted(meses, reverse=True), arq, hoje))


def licitacoes_do_ano(lista: Lista, baixar, ano: int, meses: list, arq, hoje: date) -> None:
    """Lê o mês mais novo que tem planilha de cada tipo: a planilha traz o ano acumulado. A fonte de cada item é o PDF do mesmo mês."""
    itens, referencia = {}, {}
    for mes, caminho in meses:
        arquivos = lista.pasta(caminho)[1]
        for a in arquivos:
            tipo = tipo_da_planilha(a["nome"])
            if not tipo or tipo in referencia:
                continue
            pdf = next((p for p in arquivos if p["tipo"] == "pdf" and tipo_da_planilha(re.sub(r"\.pdf$", ".xlsx", p["nome"], flags=re.I)) == tipo), None)
            itens |= itens_licitacoes(linhas_xlsx(baixar(a["url"])), tipo, (pdf or a)["url"], mes)
            referencia[tipo] = f"{ano}-{mes:02d}"
        if len(referencia) == len(TIPOS_LICITACAO):
            break
    if not itens:
        if comum.ler(arq, {}).get("itens"):
            raise RuntimeError(f"{ano} sem planilha de licitações na lista; mantém o arquivo anterior")
        return
    comum.salvar(arq, {"coletadoEm": hoje.isoformat(), "referencia": referencia, "fonte": LICITACOES_PAGINA, "itens": itens})
    print(f"RR: {ano} licitações {sum(i['tipo'] == 'licitacao' for i in itens.values())} e contratações diretas "
          f"{sum(i['tipo'] == 'contratacao_direta' for i in itens.values())} do órgão")


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

    def encerrado(ano):  # o arquivo gravado fica como está
        return comum.ano_encerrado(ano, hoje, pasta / f"diarias_{ano}.json")

    for ano, _mes, caminho in _meses(lista):
        if encerrado(ano):
            continue
        arquivos = lista.pasta(caminho)[1]
        pdfs = [a for a in arquivos if a["tipo"] == "pdf" and not re.search(r"sem efeito", a["nome"], re.I)]
        planilhas = [a for a in arquivos if a["tipo"] in ("xlsx", "ods") and not re.search(r"sem efeito", a["nome"], re.I)]
        for p in planilhas:
            registros = registros_diarias(linhas_planilha(baixar(p["url"]), p["tipo"]))
            for i in itens_diarias(registros, deputados, (pdfs[0] if pdfs else p)["url"]):
                por_ano.setdefault(int((i["data"] or f"{ano}")[:4]), []).append(i)
    for ano, itens in sorted(por_ano.items()):
        if encerrado(ano):
            continue
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
    comum.rodar_etapas(UF, [("gabinete", lambda: coletar_gabinete(s, deputados, pasta, hoje)),
                            ("contratos do órgão", lambda: coletar_contratos(s, pasta, hoje)),
                            ("licitações e contratações diretas", lambda: coletar_licitacoes(s, pasta, hoje))])


# ---------------------------------------------------------------- contratos (amostras reais das fontes)

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
    falhas += comum.campos_vazios(f, ("nome", "nomeCivil", "partido"), "ficha de deputado")
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
    falhas += [f"nome de arquivo fora do padrão 'Dep. Nome - Mês Ano': {a['nome']}" for a in arquivos if nome_do_arquivo(a["nome"]) is None]
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
    todos = [lin for lin in registro["linhas"] if len(lin) >= 2 and re.fullmatch(r"\d\.\d+", lin[0].strip())]
    desconhecidos = [lin[0] for lin in todos if lin[0].strip() not in CATEGORIAS]
    return falhas, [f"item de despesa novo: {', '.join(desconhecidos)}"] if desconhecidos else []


def _indice_cabecalho(linhas):
    return next((i for i, lin in enumerate(linhas) if {"nome", "cargo", "destino"} <= {comum.sem_acento(c) for c in lin}), None)


def _contrato_diarias(ctx):
    lista = Lista(comum.sessao(), DIARIAS_PAGINA)
    for _, _, caminho in reversed(_meses(lista)):
        for a in lista.pasta(caminho)[1]:
            if a["tipo"] in ("xlsx", "ods") and not re.search(r"sem efeito", a["nome"], re.I):
                linhas = linhas_planilha(_get(a["url"]).content, a["tipo"])
                cab = _indice_cabecalho(linhas)
                if cab is None:
                    continue
                deputados = [lin for lin in linhas[cab + 1:] if any(re.match(r"(?i)deputad", c) for c in lin)][:3]
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


def _contrato_gabinete(ctx):
    lista = Lista(comum.sessao(), GESTAO_PAGINA)
    for _, _, caminho in reversed(_meses(lista)):
        planilha = next((a for a in lista.pasta(caminho)[1] if a["tipo"] == "xlsx" and "servidores" in comum.sem_acento(a["nome"])), None)
        if planilha:
            linhas = linhas_xlsx(_get(planilha["url"]).content)
            cab = next(i for i, lin in enumerate(linhas) if "Nome" in lin)
            gabinetes = {}
            for lin in linhas[cab + 1:]:
                if len(lin) > 6 and lin[6].startswith("GAB. DEP.") and lin[6] not in gabinetes and "-" in lin[5][:6]:
                    gabinetes[lin[6]] = lin
            outro = next(lin for lin in linhas[cab + 1:] if len(lin) > 6 and not lin[6].startswith("GAB."))
            return {"arquivo": planilha["nome"], "linhas": [*linhas[: cab + 1], *list(gabinetes.values())[:3], outro]}
    raise RuntimeError("gestão de pessoal sem planilha CONSULTA SERVIDORES")


def _conferir_gabinete(registro):
    falhas = []
    cab = registro["linhas"][0] if registro["linhas"] and "Setor" in registro["linhas"][0] else next((lin for lin in registro["linhas"] if "Setor" in lin), None)
    if cab is None:
        return ["planilha de pessoal sem o cabeçalho (Matrícula, Nome, Setor...)"], []
    deputados = [{"id": "x", "nome": lin[6][len("GAB. DEP. "):], "nomeCivil": lin[6][len("GAB. DEP. "):]} for lin in registro["linhas"] if len(lin) > 6 and lin[6].startswith("GAB. DEP.")]
    itens = servidores_do_gabinete(registro["linhas"], deputados)
    if not itens:
        falhas.append("planilha de pessoal sem servidor em setor 'GAB. DEP. <nome>'")
    for i in itens:
        falhas += comum.campos_vazios(i, ("matricula", "nome", "cargo", "admissao"), "servidor de gabinete")
    return falhas, [] if any(i["simbolo"] for i in itens) else ["cargo de gabinete sem símbolo (FS-11...)"]


def _contrato_contratos(ctx):
    lista = Lista(comum.sessao(), CONTRATOS_PAGINA)
    for nome_ano, caminho_ano in reversed(lista.raiz[0]):
        for nome, caminho in reversed(lista.pasta(caminho_ano)[0]):
            arquivos = lista.pasta(caminho)[1]
            if contratos_da_pasta(nome, arquivos, CONTRATOS_PAGINA) and len(arquivos) > 2:
                return {"pasta": nome, "arquivos": arquivos}
    raise RuntimeError("nenhuma pasta de processo com contrato")


def _conferir_contratos(registro):
    itens = contratos_da_pasta(registro["pasta"], registro["arquivos"], CONTRATOS_PAGINA)
    if not itens:
        return ["pasta de processo sem arquivo 'CONTRATO NN-AAAA'"], []
    falhas = []
    for i in itens.values():
        falhas += comum.campos_vazios(i, ("numero", "processo", "arquivos"), "contrato")
        if not any(a["nome"] == "Contrato" for a in i["arquivos"]):
            falhas.append("contrato sem o PDF do contrato")
    return falhas, [] if any(a["nome"].startswith("Publicação") for i in itens.values() for a in i["arquivos"]) else ["pasta sem PDF de publicação"]


def _contrato_licitacoes(ctx):
    lista = Lista(comum.sessao(), LICITACOES_PAGINA)
    saida = {}
    for _, _, caminho in reversed(_meses(lista)):
        for a in lista.pasta(caminho)[1]:
            tipo = tipo_da_planilha(a["nome"])
            if tipo and tipo not in saida:
                linhas = linhas_xlsx(_get(a["url"]).content)
                cab = next(i for i, lin in enumerate(linhas) if any(comum.sem_acento(c) == "objeto" for c in lin))
                comcnpj = [lin for lin in linhas[cab + 1:] if CNPJ_NO_TEXTO.search(" ".join(lin))]
                resto = [lin for lin in linhas[cab + 1:] if lin not in comcnpj and len(lin) > 4 and lin[0].strip()]
                saida[tipo] = {"arquivo": a["nome"], "linhas": [*linhas[: cab + 1], *comcnpj[:1], *resto[:2]]}
        if len(saida) == len(TIPOS_LICITACAO):
            return saida
    raise RuntimeError("licitações sem planilha de licitação e de contratação direta")


def _conferir_licitacoes(registro):
    falhas = []
    for tipo in TIPOS_LICITACAO:
        itens = itens_licitacoes(registro[tipo]["linhas"], tipo, LICITACOES_PAGINA, 1)
        if not itens:
            falhas.append(f"planilha de {tipo} sem linha com objeto e processo (cabeçalho mudou?)")
        for i in itens.values():
            falhas += comum.campos_vazios(i, ("processo", "modalidade", "objeto", "situacao"), tipo)
            if tipo == "contratacao_direta" and not i["procedimento"]:
                falhas.append("contratação direta sem número do procedimento")
        if itens and not any(i["data"] for i in itens.values()):
            falhas.append(f"{tipo}: nenhuma data legível")
    return falhas, []


CONTRATOS = [
    {"nome": "estadual_rr_deputados", "fonte": LISTA_DEPUTADOS, "buscar": _contrato_deputados, "html": _conferir_deputados},
    {"nome": "estadual_rr_listagem", "fonte": VERBAS_PAGINA, "buscar": _contrato_listagem, "html": _conferir_listagem},
    {"nome": "estadual_rr_verba", "fonte": VERBAS_PAGINA, "buscar": _contrato_verba, "html": _conferir_verba},
    {"nome": "estadual_rr_diarias", "fonte": DIARIAS_PAGINA, "buscar": _contrato_diarias, "html": _conferir_diarias},
    {"nome": "estadual_rr_gabinete", "fonte": GESTAO_PAGINA, "buscar": _contrato_gabinete, "html": _conferir_gabinete},
    {"nome": "estadual_rr_contratos", "fonte": CONTRATOS_PAGINA, "buscar": _contrato_contratos, "html": _conferir_contratos},
    {"nome": "estadual_rr_licitacoes", "fonte": LICITACOES_PAGINA, "buscar": _contrato_licitacoes, "html": _conferir_licitacoes},
]


if __name__ == "__main__":
    comum.principal(coletar)
