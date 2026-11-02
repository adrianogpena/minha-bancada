"""
Deputados estaduais da Bahia (ALBA), fora do SAPL. Grava em dados/estaduais/BA/ (contrato em estaduais_comum.py).

Fontes lidas aqui:
  - deputados (HTML estático): https://www.al.ba.gov.br/deputados/deputados-estaduais e a ficha de cada um (nome completo, e-mail);
  - verba indenizatória: planilha anual do portal de transparência,
    https://www.al.ba.gov.br/transparencia/verbas-idenizatorias-excel?ano=2026 (processo, NF, mês, deputado, categoria, valor);
  - proposições (autoria, data, ementa, situação): lista por tipo em /atividade-legislativa-nova/proposicoes e a página de cada uma;
  - emendas parlamentares estaduais: ZIP do CKAN https://dados.ba.gov.br/dataset/emendas-parlamentares (VW_PAINEL_EMENDAS_PARLAMENTARES_DESPESAS.csv).

  - presença em plenário: /atividade-legislativa/sessoes-plenarias (lista de sessões) e /atividade-legislativa/frequencia-sessao/<id>
    (deputado, Sim/Não), de 2021 até 18/06/2025; depois a ALBA migrou para o NoPaper (403), então não há presença mais nova;
  - contratos do órgão: /transparencia/contratos-convenios (HTML, sem CNPJ: fornecedor só pelo nome);
  - regras da verba: /transparencia/verbas-regula (PDFs das normas, só como link).

Não coletado: votações (só no NoPaper, atrás de Cloudflare: 403 até no Firefox; não contornado), remuneração dos
deputados (só PDF), diárias (o portal de RH só lista servidores), gabinete e normas com autoria (não publicados), fornecedor e CNPJ da
verba (só na página de cada lançamento) e atas de registro de preços (a licitação em licita.alba.ba.gov.br não traz ata).
"""

import csv
import io
import json
import re
import tempfile
import zipfile
import zlib
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from functools import partial
from pathlib import Path
from urllib.parse import quote

import certifi
import requests

import estaduais_comum as comum
import identidades

UF = "BA"
PASTA = comum.DADOS / UF
SITE = "https://www.al.ba.gov.br"
LISTA_URL = f"{SITE}/deputados/deputados-estaduais"
FICHA_URL = f"{SITE}/deputados/deputado-estadual"
VERBA_PAGINA = f"{SITE}/transparencia/verbas-idenizatorias"
VERBA_EXCEL = f"{SITE}/transparencia/verbas-idenizatorias-excel"
PROPOSICOES = f"{SITE}/atividade-legislativa-nova/proposicoes"
PROPOSICAO = f"{SITE}/atividade-legislativa-nova/proposicao"
CKAN = "https://dados.ba.gov.br"
EMENDAS_PAGINA = f"{CKAN}/dataset/emendas-parlamentares"
EMENDAS_API = f"{CKAN}/api/3/action/package_show?id=emendas-parlamentares"
EMENDAS_CSV = "VW_PAINEL_EMENDAS_PARLAMENTARES_DESPESAS.csv"
PAGAMENTOS_CSV = "VW_PAINEL_EMENDAS_PARLAMENTARES_PAGAMENTOS.csv"
ANO_PAGAMENTOS = 2026
SESSOES = f"{SITE}/atividade-legislativa/sessoes-plenarias"
FREQUENCIA = f"{SITE}/atividade-legislativa/frequencia-sessao"
CONTRATOS_PAGINA = f"{SITE}/transparencia/contratos-convenios"
REGRAS_PAGINA = f"{SITE}/transparencia/verbas-regula"
ANO_PRESENCA = 2021
ANO_CONTRATOS = 2023
LEGISLATURA ="20ª (2023-2027)"
ANO_VERBA = 2023
ANO_PROPOSICOES = 2023
TIMEOUT = 30
TIMEOUT_ARQUIVO = 120
EM_PARALELO = 2
RENOVAR_DETALHE_DIAS = 7   # o detalhe de proposição do ano corrente é relido a cada 7 a 20 dias (escalonado por proposição); anos encerrados só uma vez

TIPOS = {  # valor do filtro `tipo` -> (sigla, descrição)
    "PL.": ("PL", "Projeto de Lei"),
    "PLC": ("PLC", "Projeto de Lei Complementar"),
    "PEC": ("PEC", "Proposta de Emenda à Constituição"),
    "PDL": ("PDL", "Projeto de Decreto Legislativo"),
    "PRS": ("PRS", "Projeto de Resolução"),
}


def decodificar(conteudo: bytes) -> str:
    try:
        return conteudo.decode("utf-8-sig")
    except UnicodeDecodeError:
        return conteudo.decode("cp1252", errors="replace")


baixar = partial(comum.baixar, timeout=TIMEOUT)


INTERMEDIARIO_CKAN = Path(__file__).with_name("sectigo_ov_r36.pem")
_cadeia_ckan: list[str] = []


def cadeia_ckan() -> str:
    """Raízes do certifi + o intermediário que o servidor não envia (Sectigo OV R36, de http://crt.sectigo.com/SectigoPublicServerAuthenticationCAOVR36.crt)."""
    if not _cadeia_ckan or not Path(_cadeia_ckan[0]).exists():
        _cadeia_ckan[:] = [tempfile.mkstemp(suffix=".pem")[1]]
        Path(_cadeia_ckan[0]).write_text(Path(certifi.where()).read_text() + "\n" + INTERMEDIARIO_CKAN.read_text(), encoding="ascii")
    return _cadeia_ckan[0]


def baixar_ckan(s, url: str, timeout: int = TIMEOUT) -> bytes:
    """dados.ba.gov.br não envia o certificado intermediário (o Python recusa, o navegador aceita): verifica com ele versionado em scripts/."""
    comum.checar_prazo()
    r = requests.get(url, timeout=timeout, verify=cadeia_ckan(), headers={"User-Agent": comum.USER_AGENT})
    r.raise_for_status()
    return r.content


def iso_data(texto: str) -> str | None:
    return comum.data_br_iso(texto)


def data_serial(valor) -> date | None:
    try:
        return date(1899, 12, 30) + timedelta(days=int(float(valor)))
    except (TypeError, ValueError, OverflowError):
        return None


def sem_espacos(nome: str) -> str:
    return " ".join((nome or "").split())


# ---------------------------------------------------------------- deputados

def cartoes(html: str) -> list[dict]:
    """Cartões da página de deputados: id da ficha, nome parlamentar, partido e foto."""
    lista = []
    for m in re.finditer(r'<div class="col-md-3">(.*?<div class="partido-nome">.*?)</div>', html, re.S):
        bloco = m.group(1)
        link = re.search(r'<div class="deputado-nome">\s*<a href="/deputados/deputado-estadual/(\d+)">(.*?)</a>', bloco, re.S)
        if not link:
            continue
        foto = re.search(r'<img src="([^"]+)"', bloco)
        partido = re.search(r'<div class="partido-nome">(.*)', bloco, re.S)
        lista.append({"id": link.group(1), "nome": comum.limpar(link.group(2)),
                      "foto": f"{SITE}{foto.group(1)}" if foto and foto.group(1).startswith("/") else (foto.group(1) if foto else None),
                      "partido": comum.sigla_partido(comum.limpar(partido.group(1))) if partido else None})
    return lista


def ficha(html: str) -> dict:
    nome = re.search(r"<strong>Nome:\s*</strong>\s*<span>(.*?)</span>", html, re.S)
    email = re.search(r'<a href="\.email"><span>([^<@\s]+@[^<\s]+)</span>', html)
    return {"nomeCivil": comum.limpar(nome.group(1)) if nome else None, "email": comum.email(email.group(1)) if email else None}


def coletar_deputados(s) -> list[dict]:
    lista = cartoes(decodificar(baixar(s, LISTA_URL)))
    if not lista:
        raise RuntimeError("página de deputados sem cartões")

    def completar(d):
        url = f"{FICHA_URL}/{d['id']}"
        try:
            dados = ficha(decodificar(baixar(s, url)))
        except Exception as e:
            comum.avisar(f"BA: ficha de {d['id']}: {e}")
            dados = {"nomeCivil": None, "email": None}
        return {"id": d["id"], "nome": d["nome"], "nomeCivil": dados["nomeCivil"], "foto": d["foto"], "email": dados["email"],
                "titular": True, "partido": d["partido"], "fonte": url}

    with ThreadPoolExecutor(EM_PARALELO) as ex:
        deputados = list(ex.map(completar, lista))
    comum.salvar(PASTA / "deputados.json", {"fonte": LISTA_URL, "host": None, "legislatura": LEGISLATURA, "deputados": deputados})
    print(f"BA: {len(deputados)} deputados")
    return deputados


# ---------------------------------------------------------------- verba indenizatória (planilha anual)

def itens_verba(linhas: list[dict], deputados: list[dict], ano: int) -> tuple[list[dict], set]:
    """Linhas da planilha (cabeçalho "DEPUTADO (A)" em alguma coluna) viram itens do contrato; devolve também nomes sem par."""
    cab = next((linha for linha in linhas if "DEPUTADO (A)" in linha.values()), None)
    if not cab:
        return [], set()
    col = {v: k for k, v in cab.items()}
    dados = linhas[linhas.index(cab) + 1:]
    nomes = {sem_espacos(linha.get(col["DEPUTADO (A)"], "")) for linha in dados}
    ligacao = identidades.ligar_nomes(nomes, deputados, UF)
    itens, sem_par = [], set()
    for linha in dados:
        nome = sem_espacos(linha.get(col["DEPUTADO (A)"], ""))
        pid = ligacao.get(nome)
        if not pid:
            if nome:
                sem_par.add(nome)
            continue
        quando = data_serial(linha.get(col.get("DATA")))
        itens.append({"idDeputado": pid, "mes": quando.month if quando else None, "categoria": sem_espacos(linha.get(col["CATEGORIA"], "")) or None,
                      "fornecedor": None, "cnpj": None, "valor": comum.valor_br(linha.get(col["VALOR (R$)"])),
                      "processo": linha.get(col["N° PROCESSO"]) if "N° PROCESSO" in col else None,
                      "notaFiscal": linha.get(col["N° NF"]) if "N° NF" in col else None,
                      "fonte": f"{VERBA_PAGINA}?ano={ano}&deputado={pid}" + (f"&mes={quando.month}" if quando else "")})
    return itens, sem_par


def coletar_verba(s, deputados: list[dict]) -> None:
    hoje = date.today()
    for ano in range(ANO_VERBA, hoje.year + 1):
        destino = PASTA / f"verbas_{ano}.json"
        if ano < hoje.year and destino.exists():
            continue
        linhas = comum.xlsx_linhas(baixar(s, VERBA_EXCEL, {"ano": ano}, timeout=TIMEOUT_ARQUIVO))
        itens, sem_par = itens_verba(linhas, deputados, ano)
        if itens or ano == hoje.year:
            comum.salvar(destino, {"coletadoEm": hoje.isoformat(), "fonte": f"{VERBA_PAGINA}?ano={ano}", "itens": itens})
        print(f"BA: verbas {ano}: {len(itens)} lançamentos")
        if sem_par:
            comum.avisar(f"BA: verba {ano} sem deputado atual ({len(sem_par)}): {sorted(sem_par)[:10]}")


# ---------------------------------------------------------------- proposições

def ultima_pagina(html: str) -> int:
    m = re.search(r'page=(\d+)(?:&amp;|&)size=\d+"\s+title="Última Página"', html)
    return int(m.group(1)) + 1 if m else 1


def proposicoes_da_lista(html: str) -> list[dict]:
    """Linhas da tabela: slug da página, sigla, número, ano, ementa e o link do texto original."""
    lista = []
    for tr in re.findall(r'<tr class="table-itens">(.*?)</tr>', html, re.S):
        link = re.search(r'href="/atividade-legislativa-nova/proposicao/([A-Z.]+-(\d+)-(\d{4}))"', tr)
        if not link:
            continue
        ementa = re.search(r'<span class="fe-html-ativ">(.*?)</span>', tr, re.S)
        texto = re.search(r'href="(https?://[^"]+)"', tr)
        sigla = link.group(1).split("-")[0].rstrip(".")
        lista.append({"slug": link.group(1), "sigla": sigla, "numero": int(link.group(2)), "ano": int(link.group(3)),
                      "ementa": comum.limpar(ementa.group(1)) if ementa else None, "linkTexto": texto.group(1) if texto else None})
    return lista


def detalhe_proposicao(html: str) -> dict:
    autor = re.search(r"Autor:\s*<span>(.*?)</span>", html, re.S)
    entrada = re.search(r"<strong>Data de Entrada:</strong>\s*<span>(.*?)</span>", html, re.S)
    ementa = re.search(r"<strong>Ementa:</strong>\s*<span>(.*?)</span>", html, re.S)
    tramitacao = []
    bloco = re.search(r'<div class="inter-title">TRAMITAÇÃO</div>(.*?)</div>\s*</div>\s*</div>', html, re.S)
    if bloco:
        tramitacao = [comum.limpar(x) for x in re.findall(r"<span>(.*?)</span>", bloco.group(1), re.S)]
    uteis = [t for t in tramitacao if not re.search(r"- (Recebido|Encaminhado)", t)]
    return {"autor": comum.limpar(autor.group(1)) if autor else "", "dataApresentacao": iso_data(comum.limpar(entrada.group(1))) if entrada else None,
            "ementa": comum.limpar(ementa.group(1)) if ementa else None, "situacao": (uteis or tramitacao or [None])[-1]}


def autores(texto: str) -> list[str]:
    partes = re.split(r"\s*[,;/]\s*|\s+E\s+", texto or "")
    return [nome for p in partes if (nome := re.sub(r"(?i)^(DEPUTAD[OA]|DEP\.?)\s+", "", p.strip()).strip(" ."))]


def listar_proposicoes(s) -> dict:
    """{slug: item da lista} dos tipos de projeto desde ANO_PROPOSICOES."""
    achados = {}
    params = {"dataInicio": f"01/01/{ANO_PROPOSICOES}", "dataFim": date.today().strftime("%d/%m/%Y"), "size": 20}
    for tipo in TIPOS:
        try:
            primeira = decodificar(baixar(s, PROPOSICOES, {**params, "tipo": tipo, "page": 0}))
        except Exception as e:
            comum.avisar(f"BA: proposições {tipo}: {e}")
            continue
        paginas = [primeira]

        def pagina(n, tipo=tipo):
            try:
                return decodificar(baixar(s, PROPOSICOES, {**params, "tipo": tipo, "page": n}))
            except Exception as e:
                comum.avisar(f"BA: proposições {tipo} página {n}: {e}")
                return ""

        with ThreadPoolExecutor(EM_PARALELO) as ex:
            paginas += list(ex.map(pagina, range(1, ultima_pagina(primeira))))
        for h in paginas:
            for p in proposicoes_da_lista(h):
                achados[p["slug"]] = p
        print(f"BA: proposições {tipo}: {len(paginas)} páginas")
    return achados


def precisa_detalhe(chave: str, ano: int, vistas: dict, hoje: date) -> bool:
    """Detalhe nunca lido, ou do ano corrente e lido há tempo demais (prazo diferente por proposição, para não renovar tudo no mesmo dia)."""
    if chave not in vistas:
        return True
    prazo = RENOVAR_DETALHE_DIAS + zlib.crc32(chave.encode()) % 14
    return ano >= hoje.year and (hoje - date.fromisoformat(vistas[chave])).days >= prazo


def coletar_proposicoes(s, deputados: list[dict]) -> None:
    hoje = date.today()
    lista = listar_proposicoes(s)
    antigas: dict[str, dict] = {}   # matérias de deputados já guardadas, de todos os anos
    vistas: dict[str, str] = {}     # chave -> dia em que o detalhe foi lido (também das que não são de deputado)
    for ano in range(ANO_PROPOSICOES, hoje.year + 1):
        guardado = comum.ler(PASTA / f"materias_{ano}.json", {})
        antigas.update(guardado.get("materias", {}))
        vistas.update({c: guardado.get("coletadoEm") for c in guardado.get("materias", {})})   # arquivos antigos, sem `vistas`
        vistas.update(guardado.get("vistas", {}))
    chaves = {slug: f"{p['sigla']}-{p['numero']}-{p['ano']}" for slug, p in lista.items()}
    sem_cache = {slug: p for slug, p in lista.items() if precisa_detalhe(chaves[slug], p["ano"], vistas, hoje)}

    def detalhe(item):
        slug, p = item
        try:
            return slug, detalhe_proposicao(decodificar(baixar(s, f"{PROPOSICAO}/{slug}")))
        except Exception as e:
            comum.avisar(f"BA: proposição {slug}: {e}")
            return slug, None

    with ThreadPoolExecutor(EM_PARALELO) as ex:
        detalhes = dict(ex.map(detalhe, sem_cache.items()))
    ligacao = identidades.ligar_nomes({a for d in detalhes.values() if d for a in autores(d["autor"])}, deputados, UF)
    por_ano: dict[int, dict] = {}
    vistas_ano: dict[int, dict] = {}
    sem_par = set()
    for slug, p in lista.items():
        chave = chaves[slug]
        d = detalhes.get(slug)
        if slug not in sem_cache or not d:   # não precisava ler, ou a leitura falhou: fica o que já havia
            if chave in antigas:
                por_ano.setdefault(p["ano"], {})[chave] = antigas[chave]
            if chave in vistas:
                vistas_ano.setdefault(p["ano"], {})[chave] = vistas[chave]
            continue
        vistas_ano.setdefault(p["ano"], {})[chave] = hoje.isoformat()
        ids = sorted({ligacao[a] for a in autores(d["autor"]) if a in ligacao})
        if not ids:
            sem_par.add(d["autor"])
            continue
        por_ano.setdefault(p["ano"], {})[chave] = {
            "tipo": p["sigla"], "tipoDescricao": next(desc for sg, desc in TIPOS.values() if sg == p["sigla"]), "numero": p["numero"],
            "ano": p["ano"], "dataApresentacao": d["dataApresentacao"], "ementa": d["ementa"] or p["ementa"], "situacao": d["situacao"],
            "emTramitacao": None, "linkTexto": p["linkTexto"], "idsAutores": ids, "idsDeputados": ids, "fonte": f"{PROPOSICAO}/{slug}"}
    for ano in sorted(set(por_ano) | set(vistas_ano)):
        comum.salvar(PASTA / f"materias_{ano}.json", {"coletadoEm": hoje.isoformat(), "fonte": PROPOSICOES, "materias": por_ano.get(ano, {}),
                                                      "vistas": vistas_ano.get(ano, {})})
    print(f"BA: {sum(len(m) for m in por_ano.values())} projetos de deputados em {len(por_ano)} anos ({len(lista)} lidos, {len(detalhes)} detalhes)")
    if sem_par:
        comum.avisar(f"BA: autores sem deputado da lista ({len(sem_par)}): {sorted(sem_par)[:12]}")


# ---------------------------------------------------------------- emendas (CKAN)

def url_zip_emendas(pacote: dict) -> str:
    for r in pacote["result"]["resources"]:
        if (r.get("format") or "").upper() == "ZIP":
            return r["url"]
    raise RuntimeError("dataset de emendas sem recurso ZIP")


def itens_emendas(texto: str, deputados: list[dict]) -> tuple[dict, set]:
    """{ano: [itens]} a partir do CSV de despesas; só emendas de deputados da lista."""
    linhas = list(csv.DictReader(io.StringIO(texto), delimiter=";"))
    cab = {comum.sem_acento(k): k for k in (linhas[0] if linhas else {})}

    def campo(linha, nome):
        return linha.get(next((orig for sem, orig in cab.items() if sem.startswith(nome)), ""), "")

    ligacao = identidades.ligar_nomes({sem_espacos(campo(linha, "nome do deputado")) for linha in linhas}, deputados, UF)
    por_ano: dict[int, list] = {}
    sem_par = set()
    for linha in linhas:
        nome = sem_espacos(campo(linha, "nome do deputado"))
        pid = ligacao.get(nome)
        if not pid:
            if nome:
                sem_par.add(nome)
            continue
        ano = int(campo(linha, "ano exerc") or 0) or None
        if not ano:
            continue
        por_ano.setdefault(ano, []).append({
            "idDeputado": pid, "ano": ano, "objeto": sem_espacos(campo(linha, "acao do programa")) or None,
            "orgao": sem_espacos(campo(linha, "orgao")) or None, "unidade": sem_espacos(campo(linha, "unidade orcamentaria")) or None,
            "numero": campo(linha, "num_codigo") or None, "orcado": comum.valor_br(campo(linha, "valor orcado atual")),
            "empenhado": comum.valor_br(campo(linha, "valor empenhado")), "liquidado": comum.valor_br(campo(linha, "valor liquidado")),
            "pago": comum.valor_br(campo(linha, "valor pago")), "fonte": EMENDAS_PAGINA})
    return por_ano, sem_par


def itens_pagamentos(texto: str, emendas: set, ano_minimo: int = ANO_PAGAMENTOS) -> dict:
    """{ano do pagamento: [itens]} do CSV de pagamentos; só de emendas em `emendas` (num_codigo), pagos a partir de `ano_minimo`. Sem idDeputado: `numero` aponta a emenda."""
    linhas = list(csv.DictReader(io.StringIO(texto), delimiter=";"))
    cab = {comum.sem_acento(k): k for k in (linhas[0] if linhas else {})}

    def campo(linha, nome):
        return (linha.get(next((orig for sem, orig in cab.items() if sem.startswith(nome)), "")) or "").strip()

    efetivado = {"sim": True, "nao": False}
    por_ano: dict[int, list] = {}
    for linha in linhas:
        numero = campo(linha, "num_codigo_exec")
        data = iso_data(campo(linha, "data do pagamento"))
        if numero not in emendas or not data or int(data[:4]) < ano_minimo:
            continue
        por_ano.setdefault(int(data[:4]), []).append({
            "numero": numero, "data": data, "credor": sem_espacos(campo(linha, "razaosocialcredor")) or None,
            "valor": comum.valor_br(campo(linha, "val_pagto_nob")), "objeto": sem_espacos(campo(linha, "objeto")) or None,
            "empenho": campo(linha, "num_empenho") or None, "efetivado": efetivado.get(comum.sem_acento(campo(linha, "pagamento_efetivado")).lower())})
    for itens in por_ano.values():
        itens.sort(key=lambda i: (i["data"], i["numero"], i["empenho"] or ""))
    return por_ano


def coletar_emendas(s, deputados: list[dict]) -> None:
    pacote = json.loads(baixar_ckan(s, EMENDAS_API))
    zip_bytes = baixar_ckan(s, url_zip_emendas(pacote), TIMEOUT_ARQUIVO)
    z = zipfile.ZipFile(io.BytesIO(zip_bytes))
    por_ano, sem_par = itens_emendas(decodificar(z.read(EMENDAS_CSV)), deputados)
    for ano, itens in sorted(por_ano.items()):
        comum.salvar(PASTA / f"emendas_{ano}.json", {"coletadoEm": date.today().isoformat(), "fonte": EMENDAS_PAGINA, "itens": itens})
    print(f"BA: emendas: {sum(len(v) for v in por_ano.values())} itens em {len(por_ano)} anos")
    numeros = {i["numero"] for itens in por_ano.values() for i in itens if i["numero"]}
    pagamentos = itens_pagamentos(decodificar(z.read(PAGAMENTOS_CSV)), numeros)
    for ano, itens in sorted(pagamentos.items()):
        comum.salvar(PASTA / f"pagamentos_{ano}.json", {"coletadoEm": date.today().isoformat(), "fonte": EMENDAS_PAGINA, "itens": itens})
    print(f"BA: pagamentos de emendas: {sum(len(v) for v in pagamentos.values())} itens em {len(pagamentos)} anos")
    if sem_par:
        comum.avisar(f"BA: emendas sem deputado atual ({len(sem_par)}): {sorted(sem_par)[:10]}")


# ---------------------------------------------------------------- presença em plenário

def sessoes_da_lista(html: str) -> list[dict]:
    """Linhas da lista de sessões (número, tipo, data e o link da frequência, depois dos vídeos por orador): id, número, tipo e data ISO."""
    padrao = (r'<td width="100"><span>(.*?)</span></td>\s*<td><span>(.*?)</span></td>\s*<td><span>(\d{2}/\d{2}/\d{4})</span></td>'
              r'(?:(?!<td width="100"><span>).)*?/atividade-legislativa/frequencia-sessao/(\d+)')
    return [{"id": m.group(4), "numero": comum.limpar(m.group(1)), "tipo": comum.limpar(m.group(2)), "data": iso_data(m.group(3))}
            for m in re.finditer(padrao, html, re.S) if iso_data(m.group(3))]


def frequencia_da_sessao(html: str) -> dict | None:
    """{"data": ISO, "titulo": "52ª Sessão Ordinária", "presencas": {nome: True/False}} da página de frequência; None se o formato mudou."""
    cab = re.search(r'titulo-presidente">\s*(.*?)\s+-\s+(\d{2}/\d{2}/\d{4})', html, re.S)
    data = iso_data(cab.group(2)) if cab else None
    if not data:
        return None
    presencas = {}
    for nome, resposta in re.findall(r'<tr class="table-itens[^"]*">\s*<td><span>(.*?)</span></td>\s*<td><span>(.*?)</span></td>', html, re.S):
        nome, resposta = sem_espacos(comum.limpar(nome)), comum.sem_acento(comum.limpar(resposta)).lower()
        if nome and resposta in ("sim", "nao"):
            presencas[nome] = resposta == "sim"
    return {"data": data, "titulo": comum.limpar(cab.group(1)), "presencas": presencas}


def listar_sessoes(s, desde: int, hoje: date) -> dict:
    """{id: sessão} das sessões plenárias de `desde` até hoje; lê as páginas de cada ano até uma vir sem sessão nova."""
    achadas = {}
    for ano in range(desde, hoje.year + 1):
        params = {"dataInicio": f"{ano}-01-01", "dataFim": f"{ano}-12-31"}
        for pagina in range(0, 60):
            novas = [x for x in sessoes_da_lista(decodificar(baixar(s, SESSOES, {**params, "page": pagina}))) if x["id"] not in achadas]
            if not novas:
                break
            achadas.update({x["id"]: x for x in novas})
    return achadas


def somar_presenca(contagem: dict, frequencia: dict, ligacao: dict) -> None:
    """Soma uma sessão em `contagem` {(idDeputado, período): [presente, ausente]} para o ano e para o mês."""
    ano, mes = frequencia["data"][:4], frequencia["data"][:7]
    for nome, presente in frequencia["presencas"].items():
        pid = ligacao.get(nome)
        for periodo in ((pid, ano), (pid, mes)) if pid else ():
            contagem.setdefault(periodo, [0, 0])[0 if presente else 1] += 1


def itens_presenca(contagem: dict) -> list[dict]:
    return [{"idDeputado": pid, "periodo": periodo, "presente": p, "ausente": a, "licenca": 0, "totalSessoes": p + a, "fonte": SESSOES}
            for (pid, periodo), (p, a) in sorted(contagem.items())]


def coletar_presenca(s, deputados: list[dict]) -> None:
    """Cada sessão é lida uma vez: `lidas` guarda o que já entrou na contagem e a presença nova se soma ao que está no arquivo."""
    hoje = date.today()
    arq = PASTA / "presenca.json"
    antigo = comum.ler(arq, {})
    lidas = dict(antigo.get("lidas", {}))
    contagem = {(i["idDeputado"], i["periodo"]): [i["presente"], i["ausente"]] for i in antigo.get("itens", [])}
    ultimo = max(lidas.values(), default=None)
    desde = max(ANO_PRESENCA, int(ultimo[:4])) if ultimo else ANO_PRESENCA
    sessoes = listar_sessoes(s, desde, hoje)
    pendentes = [x for i, x in sorted(sessoes.items()) if i not in lidas]

    def ler_sessao(x):
        try:
            return x, frequencia_da_sessao(decodificar(baixar(s, f"{FREQUENCIA}/{x['id']}")))
        except comum.PrazoEsgotado:
            raise
        except Exception as e:
            comum.avisar(f"BA: frequência da sessão {x['id']}: {e}")
            return x, None

    def salvar():
        comum.salvar(arq, {"coletadoEm": hoje.isoformat(), "fonte": SESSOES, "lidas": dict(sorted(lidas.items())), "itens": itens_presenca(contagem)})

    novas = 0
    try:
        for inicio in range(0, len(pendentes), 40):
            with ThreadPoolExecutor(EM_PARALELO) as ex:
                lidos = list(ex.map(ler_sessao, pendentes[inicio: inicio + 40]))
            ligacao = identidades.ligar_nomes({n for _, f in lidos if f for n in f["presencas"]}, deputados, UF)
            for x, f in lidos:
                if not f or f["data"] != x["data"]:
                    continue
                if not f["presencas"]:   # solene ou especial, sem quadro de presença: depois de 60 dias não volta a ser lida
                    if (hoje - date.fromisoformat(f["data"])).days > 60:
                        lidas[x["id"]] = f["data"]
                    continue
                somar_presenca(contagem, f, ligacao)
                lidas[x["id"]] = f["data"]
                novas += 1
            salvar()
    except comum.PrazoEsgotado:
        salvar()
        comum.avisar("BA: prazo esgotado na presença; as sessões lidas ficaram guardadas")
    print(f"BA: presença: {novas} sessões novas de {len(pendentes)} pendentes ({len(lidas)} lidas), {len(contagem)} contagens")
    if not lidas:
        raise RuntimeError("nenhuma sessão lida")


# ---------------------------------------------------------------- contratos do órgão

def contratos_da_pagina(html: str) -> dict:
    """{id: item} dos contratos da tabela (`comum.item_orgao`); sem CNPJ, o fornecedor é só o nome."""
    itens = {}
    for tr in re.findall(r'<tr class="table-itens[^"]*">(.*?)</tr>', html, re.S):
        link = re.search(r'href="(/transparencia/contratos-convenios/detalhar/(\d+))"', tr)
        celulas = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if not link or len(celulas) < 8:
            continue
        numero = comum.limpar(celulas[0])
        inicio = iso_data(comum.limpar(celulas[1]))
        if not numero or not inicio:
            continue
        arquivos = [{"url": f"{SITE}{u}" if u.startswith("/") else u, "nome": nome, "data": None}
                    for nome, c in (("Aditivos", celulas[6]), ("Anexo", celulas[7])) for u in re.findall(r'href="([^"#][^"]*)"', c)]
        iid, item = comum.item_orgao("alba_ba", "contrato", link.group(2), fornecedor_nome=comum.limpar(celulas[2]), valor=comum.limpar(celulas[5]),
                                     inicio=inicio, numero=numero, arquivos=arquivos, fonte=f"{SITE}{link.group(1)}",
                                     modalidade=comum.limpar(celulas[3]) or None, situacao=comum.limpar(celulas[4]) or None)
        itens[iid] = item
    return itens


def coletar_contratos(s) -> None:
    hoje = date.today()
    itens = {}
    for pagina in range(0, 20):
        params = {"dataInicio": f"{ANO_CONTRATOS}-01-01", "dataFim": f"{hoje.year}-12-31", "page": pagina, "size": 200}
        novos = {k: v for k, v in contratos_da_pagina(decodificar(baixar(s, CONTRATOS_PAGINA, params))).items() if k not in itens}
        if not novos:
            break
        itens |= novos
    if not itens:
        raise RuntimeError("página de contratos sem linhas; mantém os arquivos anteriores")
    por_ano: dict[int, dict] = {}
    for iid, i in itens.items():
        por_ano.setdefault(int(i["inicio"][:4]), {})[iid] = i
    for ano, grupo in sorted(por_ano.items()):
        arq = PASTA / f"orgao_{ano}.json"
        if comum.ano_encerrado(ano, hoje, arq):
            continue
        comum.salvar(arq, {"coletadoEm": hoje.isoformat(), "fonte": CONTRATOS_PAGINA, "itens": grupo})
    print(f"BA: contratos do órgão: {len(itens)} em {len(por_ano)} anos")


# ---------------------------------------------------------------- regras da verba (PDFs como link)

def normas_da_verba(html: str) -> list[dict]:
    normas = []
    for tr in re.findall(r'<tr class="table-itens[^"]*">(.*?)</tr>', html, re.S):
        titulo = re.search(r"<strong>(.*?)</strong>", tr, re.S)
        pdf = re.search(r'href="(/fserver/[^"]+\.pdf)"', tr)
        ano = re.match(r"\s*(\d{4})\s*-", comum.limpar(titulo.group(1))) if titulo else None
        if titulo and pdf and ano:
            normas.append({"titulo": comum.limpar(titulo.group(1)), "url": SITE + quote(pdf.group(1), safe=":/%"), "ano": int(ano.group(1)),
                           "atualizadoEm": None})
    return normas


def coletar_regras(s) -> None:
    normas = normas_da_verba(decodificar(baixar(s, REGRAS_PAGINA)))
    if not normas:
        raise RuntimeError("nenhuma norma da verba na página; mantém o arquivo anterior")
    nova = max(normas, key=lambda n: n["ano"])
    comum.salvar(PASTA / "regras_ressarcimento.json", {"url": nova["url"], "ano": nova["ano"], "titulo": nova["titulo"], "fonte": REGRAS_PAGINA,
                                                       "documentos": normas})
    print(f"BA: regras da verba: {len(normas)} normas")


# ---------------------------------------------------------------- execução

def coletar() -> None:
    s = comum.sessao()
    deputados = coletar_deputados(s)
    comum.rodar_etapas(UF, [("verba", lambda: coletar_verba(s, deputados)), ("proposições", lambda: coletar_proposicoes(s, deputados)),
                            ("emendas", lambda: coletar_emendas(s, deputados)),
                            ("presença", lambda: coletar_presenca(s, deputados)), ("contratos do órgão", lambda: coletar_contratos(s)),
                            ("regras da verba", lambda: coletar_regras(s))])


# ---------------------------------------------------------------- contratos (amostras reduzidas das respostas reais)

def _contrato_deputados(ctx):
    s = comum.sessao()
    lista = decodificar(baixar(s, LISTA_URL))
    blocos = [m.start() for m in re.finditer(r'<div class="col-md-3">', lista)]
    primeiro = cartoes(lista)[0]["id"]
    pagina = decodificar(baixar(s, f"{FICHA_URL}/{primeiro}"))
    inicio = pagina.index("DADOS PESSOAIS")
    email = pagina.index('<a href=".email">')
    return {"lista": lista[blocos[0]: lista.index('<div style="border: 1px solid red;"></div>', blocos[1]) + 60],
            "ficha": pagina[inicio: inicio + 900] + "\n" + pagina[email - 40: email + 160]}


def _conferir_deputados(registro):
    falhas = []
    lista = cartoes(registro["lista"])
    if not lista or not all(d["id"] and d["nome"] and d["partido"] and d["foto"] for d in lista):
        falhas.append("cartões de deputados sem id, nome, partido ou foto")
    dados = ficha(registro["ficha"])
    if not dados["nomeCivil"]:
        falhas.append("ficha sem 'Nome:'")
    return falhas, [] if dados["email"] else ["ficha sem e-mail"]


def _contrato_verba(ctx):
    linhas = comum.xlsx_linhas(baixar(comum.sessao(), VERBA_EXCEL, {"ano": date.today().year}, timeout=TIMEOUT_ARQUIVO))
    return {"linhas": linhas[:7]}


def _conferir_verba(registro):
    itens, _ = itens_verba(registro["linhas"], [{"id": "x", "nome": n, "nomeCivil": None}
                                                 for n in {sem_espacos(linha.get("F", "")) for linha in registro["linhas"][3:]}], date.today().year)
    falhas = []
    if not itens:
        return ["planilha de verba sem lançamentos reconhecidos"], []
    falhas += ["lançamento sem valor, mês ou categoria" for i in itens if i["valor"] is None or not i["mes"] or not i["categoria"]]
    return falhas, []


def _contrato_proposicoes(ctx):
    s = comum.sessao()
    params = {"tipo": "PL.", "dataInicio": f"01/01/{ANO_PROPOSICOES}", "dataFim": date.today().strftime("%d/%m/%Y"), "size": 20, "page": 0}
    lista = decodificar(baixar(s, PROPOSICOES, params))
    primeiro = proposicoes_da_lista(lista)[0]["slug"]
    pagina = decodificar(baixar(s, f"{PROPOSICAO}/{primeiro}"))
    linhas = [m.start() for m in re.finditer(r'<tr class="table-itens">', lista)]
    pos = lista.index('title="Última Página"')
    inicio = pagina.index("Autor:")
    fim = pagina.index("TRAMITAÇÃO NAS COMISSÕES") if "TRAMITAÇÃO NAS COMISSÕES" in pagina else inicio + 900
    trami = pagina.index('<div class="inter-title">TRAMITAÇÃO</div>')
    return {"lista": lista[linhas[0]: lista.index("</tr>", linhas[1]) + 5] + "\n" + lista[pos - 120: pos + 40],
            "detalhe": pagina[inicio - 10: fim] + "\n" + pagina[trami: trami + 1200] + "</div></div></div>"}


def _conferir_proposicoes(registro):
    falhas = []
    if ultima_pagina(registro["lista"]) < 2:
        falhas.append("paginação (link 'Última Página') não reconhecida")
    itens = proposicoes_da_lista(registro["lista"])
    if not itens or not all(i["ementa"] and i["linkTexto"] for i in itens):
        falhas.append("lista de proposições sem ementa ou link do texto")
    d = detalhe_proposicao(registro["detalhe"])
    falhas += comum.campos_vazios(d, ("autor", "ementa", "dataApresentacao", "situacao"), "proposição")
    return falhas, []


def _contrato_emendas(ctx):
    s = comum.sessao()
    pacote = json.loads(baixar_ckan(s, EMENDAS_API))
    z = zipfile.ZipFile(io.BytesIO(baixar_ckan(s, url_zip_emendas(pacote), TIMEOUT_ARQUIVO)))
    texto = decodificar(z.read(EMENDAS_CSV))
    linhas = texto.splitlines()
    pagamentos = decodificar(z.read(PAGAMENTOS_CSV)).splitlines()
    return {"csv": "\n".join(linhas[:4]), "pagamentos": "\n".join(pagamentos[:4]), "arquivos": sorted(z.namelist())}


def _conferir_emendas(registro):
    falhas = []
    for arquivo in (EMENDAS_CSV, PAGAMENTOS_CSV):
        if arquivo not in registro["arquivos"]:
            falhas.append(f"ZIP sem {arquivo}")
    linha = registro["pagamentos"].splitlines()[1].split(";")
    pagos = itens_pagamentos(registro["pagamentos"], {linha[9].strip('" ')}, 0)
    if not pagos or any(not i["data"] or i["valor"] is None for v in pagos.values() for i in v):
        falhas.append("pagamentos de emendas sem data ou valor")
    primeiro = registro["csv"].splitlines()[1].split(";")
    por_ano, _ = itens_emendas(registro["csv"], [{"id": "x", "nome": primeiro[8].strip('" '), "nomeCivil": None}])
    itens = [i for v in por_ano.values() for i in v]
    if not itens or any(i["empenhado"] is None or not i["objeto"] for i in itens):
        falhas.append("emendas sem ação ou valor empenhado")
    return falhas, []


def _trecho_linhas(html, quantas):
    inicio = [m.start() for m in re.finditer(r'<tr class="table-itens', html)]
    return html[inicio[0]: html.index("</tr>", inicio[min(quantas, len(inicio)) - 1]) + 5]


def _contrato_presenca(ctx):
    s = comum.sessao()
    lista = decodificar(baixar(s, SESSOES, {"dataInicio": "2025-06-01", "dataFim": "2025-06-30", "page": 0}))
    freq = decodificar(baixar(s, f"{FREQUENCIA}/{sessoes_da_lista(lista)[0]['id']}"))
    cab = freq.index("titulo-presidente")
    linhas = [m.start() for m in re.finditer(r'<tr class="table-itens">\s*<td width="100">', lista)]
    return {"lista": lista[linhas[0]: linhas[1]], "frequencia": freq[cab - 40: cab + 160] + "\n" + _trecho_linhas(freq, 4)}


def _conferir_presenca(registro):
    falhas = []
    sessoes = sessoes_da_lista(registro["lista"])
    if not sessoes or not all(x["id"] and x["tipo"] and x["data"] for x in sessoes):
        falhas.append("lista de sessões sem id, tipo ou data")
    f = frequencia_da_sessao(registro["frequencia"])
    if not f or not f["presencas"]:
        falhas.append("frequência da sessão sem data ou sem deputados")
    return falhas, []


def _contrato_contratos(ctx):
    params = {"dataInicio": f"{ANO_CONTRATOS}-01-01", "dataFim": f"{date.today().year}-12-31", "page": 0, "size": 200}
    pagina = decodificar(baixar(comum.sessao(), CONTRATOS_PAGINA, params))
    cab = pagina.index("<thead")
    return {"html": pagina[cab: pagina.index("</tr>", cab) + 5] + "<tbody>" + _trecho_linhas(pagina, 2)}


def _conferir_contratos(registro):
    itens = contratos_da_pagina(registro["html"])
    if not itens:
        return ["tabela de contratos sem linhas reconhecidas"], []
    falhas = []
    for i in itens.values():
        falhas += comum.campos_vazios(i, ("numero", "fornecedor", "inicio", "valor", "fonte"), "contrato")
    return falhas, []


def _contrato_regras(ctx):
    return {"html": _trecho_linhas(decodificar(baixar(comum.sessao(), REGRAS_PAGINA)), 2)}


def _conferir_regras(registro):
    normas = normas_da_verba(registro["html"])
    if not normas or not all(n["url"].endswith(".pdf") for n in normas):
        return ["tabela de normas da verba sem PDF"], []
    return [], []


CONTRATOS = [
    {"nome": "estadual_ba_deputados", "fonte": LISTA_URL, "buscar": _contrato_deputados, "html": _conferir_deputados},
    {"nome": "estadual_ba_verba", "fonte": VERBA_PAGINA, "buscar": _contrato_verba, "html": _conferir_verba},
    {"nome": "estadual_ba_proposicoes", "fonte": PROPOSICOES, "buscar": _contrato_proposicoes, "html": _conferir_proposicoes},
    {"nome": "estadual_ba_emendas", "fonte": EMENDAS_PAGINA, "buscar": _contrato_emendas, "html": _conferir_emendas},
    {"nome": "estadual_ba_presenca", "fonte": SESSOES, "buscar": _contrato_presenca, "html": _conferir_presenca},
    {"nome": "estadual_ba_contratos", "fonte": CONTRATOS_PAGINA, "buscar": _contrato_contratos, "html": _conferir_contratos},
    {"nome": "estadual_ba_regras", "fonte": REGRAS_PAGINA, "buscar": _contrato_regras, "html": _conferir_regras},
]


if __name__ == "__main__":
    comum.principal(coletar)
