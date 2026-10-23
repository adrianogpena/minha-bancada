"""
Deputados estaduais da Bahia (ALBA), fora do SAPL. Grava em dados/estaduais/BA/ (contrato em estaduais_comum.py).

Fontes lidas aqui:
  - deputados (HTML estático): https://www.al.ba.gov.br/deputados/deputados-estaduais e a ficha de cada um (nome completo, e-mail);
  - verba indenizatória: planilha anual do portal de transparência,
    https://www.al.ba.gov.br/transparencia/verbas-idenizatorias-excel?ano=2026 (processo, NF, mês, deputado, categoria, valor);
  - proposições (autoria, data, ementa, situação): lista por tipo em /atividade-legislativa-nova/proposicoes e a página de cada uma;
  - emendas parlamentares estaduais: ZIP do CKAN https://dados.ba.gov.br/dataset/emendas-parlamentares (VW_PAINEL_EMENDAS_PARLAMENTARES_DESPESAS.csv).

Não coletado: votações e presença (só no NoPaper, atrás de Cloudflare: 403 até no Firefox; não contornado), remuneração dos
deputados (só PDF), diárias (o portal de RH só lista servidores), fornecedor e CNPJ da verba (só na página de cada lançamento).
"""

import csv
import io
import json
import re
import zipfile
import zlib
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from functools import partial

import requests
import urllib3

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
LEGISLATURA = "20ª (2023-2027)"
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


def baixar_ckan(s, url: str, timeout: int = TIMEOUT) -> bytes:
    """dados.ba.gov.br não envia o certificado intermediário (o Python recusa, o navegador aceita): sem verificar, só para dados abertos."""
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    comum.checar_prazo()
    r = requests.get(url, timeout=timeout, verify=False, headers={"User-Agent": comum.USER_AGENT})
    r.raise_for_status()
    return r.content


def iso_data(texto: str) -> str | None:
    try:
        return datetime.strptime((texto or "").strip()[:10], "%d/%m/%Y").date().isoformat()
    except ValueError:
        return None


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
                      "partido": comum.limpar(partido.group(1)) if partido else None})
    return lista


def ficha(html: str) -> dict:
    nome = re.search(r"<strong>Nome:\s*</strong>\s*<span>(.*?)</span>", html, re.S)
    email = re.search(r'<a href="\.email"><span>([^<@\s]+@[^<\s]+)</span>', html)
    return {"nomeCivil": comum.limpar(nome.group(1)) if nome else None, "email": email.group(1) if email else None}


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


def coletar_emendas(s, deputados: list[dict]) -> None:
    pacote = json.loads(baixar_ckan(s, EMENDAS_API))
    zip_bytes = baixar_ckan(s, url_zip_emendas(pacote), TIMEOUT_ARQUIVO)
    z = zipfile.ZipFile(io.BytesIO(zip_bytes))
    por_ano, sem_par = itens_emendas(decodificar(z.read(EMENDAS_CSV)), deputados)
    for ano, itens in sorted(por_ano.items()):
        comum.salvar(PASTA / f"emendas_{ano}.json", {"coletadoEm": date.today().isoformat(), "fonte": EMENDAS_PAGINA, "itens": itens})
    print(f"BA: emendas: {sum(len(v) for v in por_ano.values())} itens em {len(por_ano)} anos")
    if sem_par:
        comum.avisar(f"BA: emendas sem deputado atual ({len(sem_par)}): {sorted(sem_par)[:10]}")


# ---------------------------------------------------------------- execução

def coletar() -> None:
    s = comum.sessao()
    deputados = coletar_deputados(s)
    comum.rodar_etapas(UF, [("verba", lambda: coletar_verba(s, deputados)), ("proposições", lambda: coletar_proposicoes(s, deputados)),
                            ("emendas", lambda: coletar_emendas(s, deputados))])


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
    return {"csv": "\n".join(linhas[:4]), "arquivos": sorted(z.namelist())}


def _conferir_emendas(registro):
    falhas = []
    if EMENDAS_CSV not in registro["arquivos"]:
        falhas.append(f"ZIP sem {EMENDAS_CSV}")
    primeiro = registro["csv"].splitlines()[1].split(";")
    por_ano, _ = itens_emendas(registro["csv"], [{"id": "x", "nome": primeiro[8].strip('" '), "nomeCivil": None}])
    itens = [i for v in por_ano.values() for i in v]
    if not itens or any(i["empenhado"] is None or not i["objeto"] for i in itens):
        falhas.append("emendas sem ação ou valor empenhado")
    return falhas, []


CONTRATOS = [
    {"nome": "estadual_ba_deputados", "fonte": LISTA_URL, "buscar": _contrato_deputados, "html": _conferir_deputados},
    {"nome": "estadual_ba_verba", "fonte": VERBA_PAGINA, "buscar": _contrato_verba, "html": _conferir_verba},
    {"nome": "estadual_ba_proposicoes", "fonte": PROPOSICOES, "buscar": _contrato_proposicoes, "html": _conferir_proposicoes},
    {"nome": "estadual_ba_emendas", "fonte": EMENDAS_PAGINA, "buscar": _contrato_emendas, "html": _conferir_emendas},
]


if __name__ == "__main__":
    comum.principal(coletar)
