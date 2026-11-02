"""
Deputados estaduais do Rio de Janeiro (ALERJ), fora do SAPL.

Fontes abertas e lidas aqui:
  - lista de deputados: eleitos de 2022 do TSE (dados/tse/2022/RJ.json); a ALERJ não publica lista em formato aberto;
  - presença: Ordem do Dia (Lotus Notes), um documento por mês, faltas por deputado
    http://alerjln1.alerj.rj.gov.br/ordemdia.nsf/presint?OpenForm
  - emendas impositivas: planilha XLSX por ano, aba "Impositivas", no relatório
    https://transparencia.alerj.rj.gov.br/section/report/121
  - normas com autoria (lei, lei complementar, decreto legislativo, resolução): bases Lotus Notes
    http://alerjln1.alerj.rj.gov.br/contlei.nsf (Lei, LeiComp, Decreto, Resolucao), pela busca de texto do Domino;
  - proposições (PEC, PLC, PL, PDL, PR e indicação legislativa): http://alerjln1.alerj.rj.gov.br/scpro2327.nsf, pela busca de texto
    por deputado na visão "Cadastro de Proposições" (uma linha por autor);
  - pautas das sessões plenárias (ordemdia.nsf) e atas das comissões permanentes e temporárias (compcom.nsf, comtemp.nsf): só links;
  - contratos (relatório anual em PDF) e atas de registro de preços: relatórios /118 e /51 da transparência, só links.

Particularidades do servidor (testadas em 2026-11-02): ele derruba a conexão dos parâmetros `Start`, `Count`, `ResortAscending`,
`CollapseView` e `RestrictToCategory` (a paginação das listas não funciona: só os 15 mais novos) e de requisições em sequência
rápida. Passam `?OpenForm`, `ExpandView` e, na visão (`/<base>.nsf/<id da visão>`), `?SearchView&Query=...&SearchMax=0&SearchOrder=4`,
que devolve até 1000 linhas (o servidor corta aí, por relevância, e não pela data). Por isso: a coleta espera `PAUSA` entre requisições,
repete depois de uma queda e divide a busca (por deputado) quando ela chega ao teto de 1000. Datas vêm como MM/DD/AAAA.
O texto vem ora em UTF-8, ora em cp1252, ora em UTF-8 codificado duas vezes (`decodificar` desfaz).

Só PDF (não coletado): diárias /119, viagens /66, benefícios /33, folha /73, contratos /118 e atas /51 (só o link). Sem arquivo: subsídio /62.
Fora (não publicado): voto nominal (a Ordem do Dia traz só a pauta), servidores por deputado (a folha diz só "DEPUTADO ESTADUAL"),
regras do ressarcimento.
"""

import re
import time
import unicodedata
from datetime import date
from html import unescape
from functools import partial
from urllib.parse import quote_plus

import requests

import estaduais_comum as comum
import identidades
import ids

UF = "RJ"
TSE_ARQUIVO = comum.arquivo_tse(UF)
TRANSPARENCIA = "https://transparencia.alerj.rj.gov.br"
EMENDAS_URL = f"{TRANSPARENCIA}/section/report/121"
PRESENCA_BASE = "http://alerjln1.alerj.rj.gov.br"
PRESENCA_URL = f"{PRESENCA_BASE}/ordemdia.nsf/presint?OpenForm"
TSE_FICHA = comum.ficha_tse(UF)
BASE = PRESENCA_BASE
ANO_INICIAL = 2023
PAUSA = 2.0   # segundos antes de cada requisição ao alerjln1: em sequência rápida ele derruba a conexão
ESPERA_QUEDA = 20   # segundos de espera (vezes a tentativa) depois de uma conexão derrubada
TENTATIVAS = 3
TIMEOUT = 60
LIMITE_BUSCA = 1000   # teto de linhas de uma busca de texto do Domino
RENOVAR_COMPLETA_DIAS = 7   # releitura completa das proposições, mesmo sem novidade no topo das listas
DATAS_POR_EXECUCAO = 150   # normas sem data lidas (um documento cada) por execução, das mais novas para as mais antigas
FONTE_ID = "alerj_rj"
CONTRATOS_URL = f"{TRANSPARENCIA}/section/report/118"
ATAS_REGISTRO_URL = f"{TRANSPARENCIA}/section/report/51"
INSTITUCIONAL = re.compile(r"^(comiss|mesa|poder|governador|tribunal|defensoria|ministerio|procurador|bancada|bloco|frente|executivo)")
TITULOS = identidades.TITULOS_UF[UF]

# tipo -> sigla, descrição, visão de busca, página da lista (só para a fonte) e disposição das colunas
NORMAS = {
    "lei": {"sigla": "LEI", "tipo": "Lei ordinária", "visao": "/contlei.nsf/c8aa0900025feef6032564ec0060dfff",
            "lista": "/contlei.nsf/LeiOrdInt?OpenForm", "colunas": "lei"},
    "lc": {"sigla": "LC", "tipo": "Lei complementar", "visao": "/contlei.nsf/a99e317a9cfec383032568620071f5d2",
           "lista": "/contlei.nsf/LeiCompInt?OpenForm", "colunas": "lei"},
    "dec": {"sigla": "DL", "tipo": "Decreto legislativo", "visao": "/contlei.nsf/1103082e25d77b2203256500004ddfd5",
            "lista": "/contlei.nsf/DecretoInt?OpenForm", "colunas": "autor"},
    "res": {"sigla": "RES", "tipo": "Resolução", "visao": "/contlei.nsf/803720d56d09c0e70325663200757b59",
            "lista": "/contlei.nsf/ResolucaoInt?OpenForm", "colunas": "autor"},
}
PROPOSICOES_VISAO = "/scpro2327.nsf/02ac6f279b568e24832566ec0018d839"
PROPOSICOES_LISTAS = ("LeiInt", "LeiCompInt", "EmendaInt", "DecretoInt", "ResolucaoInt", "IndLegInt")
TIPOS_PROPOSICAO = {"01": ("PEC", "Proposta de Emenda Constitucional"), "02": ("PLC", "Projeto de Lei Complementar"),
                    "03": ("PL", "Projeto de Lei"), "04": ("PDL", "Projeto de Decreto Legislativo"),
                    "05": ("PR", "Projeto de Resolução"), "06": ("INDLEG", "Indicação Legislativa")}
PAUTAS = {
    "ordem-do-dia": {"visao": "/ordemdia.nsf/c97e97dc1275d92503256bac007254ea", "lista": "/ordemdia.nsf/OrdemInt?OpenForm", "rotulo": "Pauta da sessão"},
    "ata-comissao": {"visao": "/compcom.nsf/e36c0566701326d503256810007413ca", "lista": "/compcom.nsf/AtasInt?OpenForm",
                     "rotulo": "Ata da comissão permanente"},
    "ata-comissao-temporaria": {"visao": "/comtemp.nsf/0d034cff75b288de03256bb1005be7f8", "lista": "/comtemp.nsf/AtasInt?OpenForm",
                                "rotulo": "Ata da comissão temporária"},
}


def deputados_do_tse() -> list[dict]:
    return comum.deputados_do_tse(TSE_ARQUIVO, TSE_FICHA)


def _byte(c: str) -> bytes:
    try:
        return c.encode("cp1252")
    except UnicodeEncodeError:
        if ord(c) < 256:
            return bytes([ord(c)])
        raise


def decodificar(conteudo: bytes) -> str:
    """UTF-8; se não for, cp1252; e UTF-8 codificado duas vezes ("NÂº", "ComissÃ£o") volta ao texto certo."""
    try:
        t = conteudo.decode("utf-8")
    except UnicodeDecodeError:
        return conteudo.decode("cp1252", errors="replace")
    if "Ã" not in t and "Â" not in t and "â€" not in t:
        return t
    try:
        return b"".join(_byte(c) for c in t).decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return t


def texto(resposta) -> str:
    return decodificar(resposta.content)


# ---------------------------------------------------------------- deputados

ligar = partial(identidades.ligar_nomes, uf=UF)


# ---------------------------------------------------------------- presença (Ordem do Dia)

def links_presenca(html: str) -> list[dict]:
    """[{url, data}] de cada documento mensal; `data` é a de publicação (AAAA-MM-DD)."""
    achados = []
    for href, rotulo in re.findall(r'<a href="(/ordemdia\.nsf/[^"]+\?OpenDocument)"[^>]*>(.*?)</a>', html, re.S):
        m = re.search(r"(\d\d)/(\d\d)/(\d{4})", comum.limpar(rotulo))
        if m:
            achados.append({"url": PRESENCA_BASE + unescape(href), "data": f"{m.group(3)}-{m.group(1)}-{m.group(2)}"})
    return achados


def periodo_do_mes(mes: int, publicado: str) -> str:
    ano, mes_pub = int(publicado[:4]), int(publicado[5:7])
    return f"{ano if mes <= mes_pub else ano - 1}-{mes:02d}"


def parse_presenca(html: str, publicado: str) -> dict:
    """{periodo, totalSessoes, faltas:{nome: faltas}} de um documento mensal."""
    cabecalho = comum.limpar(html.split("<table", 1)[0])
    mes = re.search(r"de\s*:\s*([^\W\d_]+)", cabecalho)
    mes_n = comum.mes_numero(mes.group(1)) if mes else None
    total = re.search(r"TOTAL DE SESS.{1,3}ES DELIBERATIVAS\s*-\s*(\d+)", html)
    faltas = {}
    for linha in re.findall(r"<tr valign=\"top\">(.*?)</tr>", html, re.S):
        celulas = [comum.limpar(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", linha, re.S)]
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
            if comum.limpar(rotulo).lower() == "excel":
                achados[int(ano)] = TRANSPARENCIA + unescape(href)
    return achados


def emendas_da_aba(linhas: list[dict]) -> list[dict]:
    """Linhas da aba "Impositivas" viram dicts por nome de coluna (a linha de cabeçalho é a que tem "Autor")."""
    cab = next((lin for lin in linhas if "Autor" in lin.values()), None)
    if not cab:
        return []
    nomes = {col: re.sub(r"[^a-z]", "", comum.sem_acento(v)) for col, v in cab.items()}
    registros = []
    for lin in linhas[linhas.index(cab) + 1:]:
        r = {nomes[c]: v.strip() for c, v in lin.items() if c in nomes}
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


# ---------------------------------------------------------------- Lotus Notes: requisição, linhas e busca

def pegar(s, url: str) -> str:
    """GET do alerjln1 com pausa antes e nova tentativa depois de conexão derrubada; devolve o texto da página."""
    ultimo = None
    for tentativa in range(1, TENTATIVAS + 1):
        time.sleep(PAUSA)
        try:
            r = s.get(url, timeout=TIMEOUT)
            r.raise_for_status()
            return texto(r)
        except requests.ConnectTimeout:
            raise
        except requests.ConnectionError as e:
            ultimo = e
            time.sleep(ESPERA_QUEDA * tentativa)
    raise ultimo


def _sem_acento_caixa(texto_busca: str) -> str:
    """Sem acento e com a caixa original (os operadores AND e OR da busca ficam em maiúsculas)."""
    return "".join(c for c in unicodedata.normalize("NFKD", texto_busca) if not unicodedata.combining(c))


def url_busca(visao: str, consulta: str) -> str:
    return f"{BASE}{visao}?SearchView&SearchMax=0&SearchOrder=4&Query={quote_plus(_sem_acento_caixa(consulta))}"


def consulta_nome(nome: str) -> str:
    """Frase para achar o deputado numa busca: o nome sem título, até duas palavras ("Dr. Pedro Ricardo" -> "Pedro Ricardo")."""
    palavras = comum.palavras(nome, TITULOS)[:2]
    return '"' + " ".join(palavras) + '"'


def data_us_iso(texto_data: str | None) -> str | None:
    """"10/14/2026" (mês/dia/ano, como o Domino mostra) -> "2026-10-14"."""
    m = re.match(r"\s*(\d\d)/(\d\d)/(\d{4})\b", texto_data or "")
    if not m:
        return None
    try:
        return date(int(m[3]), int(m[1]), int(m[2])).isoformat()
    except ValueError:
        return None


def hora_24(texto_hora: str | None) -> str | None:
    """"03:00:00 PM" -> "15:00"."""
    m = re.match(r"\s*(\d\d?):(\d\d)(?::\d\d)?\s*([AP]M)?", texto_hora or "", re.I)
    if not m:
        return None
    hora = int(m[1])
    if m[3]:
        hora = hora % 12 + (12 if m[3].upper() == "PM" else 0)
    return f"{hora:02d}:{m[2]}"


def linhas_html(html: str) -> list[str]:
    return re.findall(r'<tr valign="top">(.*?)</tr>', html, re.S)


def url_documento(href: str) -> str:
    caminho = unescape(href).split("&Highlight")[0]
    return caminho if caminho.startswith("http") else BASE + caminho


def unid_documento(url: str) -> str | None:
    m = re.search(r"/([0-9a-f]{32})\?OpenDocument", url or "")
    return m.group(1) if m else None


def celulas(linha: str) -> tuple[list[str], int | None, str | None]:
    """(textos das células, índice da célula do link do documento, URL do documento) de uma linha de lista ou de busca."""
    tds = re.findall(r"<td[^>]*>(.*?)</td>", linha, re.S)
    textos = [comum.limpar(td) for td in tds]
    for i, td in enumerate(tds):
        m = re.search(r'href="([^"]*\?OpenDocument[^"]*)"', td)
        if m:
            return textos, i, url_documento(m.group(1))
    return textos, None, None


def _coluna(textos: list[str], i: int, deslocamento: int) -> str:
    return textos[i + deslocamento] if i + deslocamento < len(textos) else ""


def separar_nomes(autoria: str) -> list[str]:
    return [n for n in dict.fromkeys(comum.compactar(x) for x in (autoria or "").split(",")) if n]


def nomes_de_deputados(nomes) -> list[str]:
    """Tira da lista o que é órgão (comissão, Mesa, Poder Executivo...): nada a ligar a deputado."""
    return [n for n in nomes if not INSTITUCIONAL.match(comum.sem_acento(n).lower())]


# ---------------------------------------------------------------- normas legais (contlei.nsf)

def parse_normas(html: str, chave: str) -> list[dict]:
    """Normas de uma lista ou busca: {numero, ano, situacao, ementa, autoria:[nomes], url}."""
    colunas = NORMAS[chave]["colunas"]
    normas = []
    for linha in linhas_html(html):
        c, i, url = celulas(linha)
        if i is None or not re.fullmatch(r"\d+", c[i]) or not re.fullmatch(r"\d{4}", _coluna(c, i, 1)):
            continue
        if colunas == "lei":
            situacao, ementa, autoria = _coluna(c, i, 3), _coluna(c, i, 4), _coluna(c, i, 5)
        else:
            situacao, autoria, ementa = "", _coluna(c, i, 2), _coluna(c, i, 3)
        normas.append({"numero": int(c[i]), "ano": int(c[i + 1]), "situacao": situacao or None, "ementa": comum.compactar(ementa),
                       "autoria": separar_nomes(autoria), "url": url})
    return normas


def data_da_norma(html: str) -> str | None:
    """"Data da Lei" ou "Data da promulgação" do documento da norma."""
    m = re.search(r"Data d[ae] (?:Lei|promulga\w+)\s*(\d\d/\d\d/\d{4})", comum.limpar(html))
    return data_us_iso(m.group(1)) if m else None


def id_norma(chave: str, numero: int, ano: int) -> str:
    return ids.gerar_id("nor", FONTE_ID, f"{NORMAS[chave]['sigla']}|{numero}|{ano}")


def normas_do_ano(s, chave: str, ano: int, deputados: list[dict]) -> list[dict]:
    """Normas do ano pela busca do ano na visão; no teto de 1000 linhas, de novo por deputado (`2026 AND "Nome"`)."""
    visao = NORMAS[chave]["visao"]
    linhas = parse_normas(pegar(s, url_busca(visao, str(ano))), chave)
    achadas = {n["numero"]: n for n in linhas if n["ano"] == ano}
    if len(linhas) >= LIMITE_BUSCA:
        for d in deputados:
            for n in parse_normas(pegar(s, url_busca(visao, f"{ano} AND {consulta_nome(d['nome'])}")), chave):
                if n["ano"] == ano:
                    achadas[n["numero"]] = n
    return sorted(achadas.values(), key=lambda n: n["numero"], reverse=True)


def coletar_normas(s, deputados: list[dict], pasta, hoje: date) -> None:
    """normas_<ano>.json de cada ano desde 2023 (ano encerrado não é lido de novo). A data só está no documento da norma: lida
    uma vez, das mais novas para as mais antigas, até `DATAS_POR_EXECUCAO` por execução."""
    datas_lidas = 0
    for ano in range(ANO_INICIAL, hoje.year + 1):
        arq = pasta / f"normas_{ano}.json"
        if comum.ano_encerrado(ano, hoje, arq):
            continue
        antes = (comum.ler(arq, {}) or {}).get("normas", {})
        novas = {}
        for chave in NORMAS:
            for n in normas_do_ano(s, chave, ano, deputados):
                nid = id_norma(chave, n["numero"], ano)
                novas[nid] = {"tipo": NORMAS[chave]["tipo"], "numero": n["numero"], "ano": ano, "data": (antes.get(nid) or {}).get("data"),
                              "ementa": n["ementa"], "situacao": n["situacao"], "autoria": n["autoria"], "fonte": n["url"]}
        ligados = ligar({a for n in novas.values() for a in nomes_de_deputados(n["autoria"])}, deputados)
        for n in novas.values():
            n["idsDeputados"] = list(dict.fromkeys(ligados[a] for a in n["autoria"] if a in ligados))
        todas = {**{nid: n for nid, n in antes.items() if nid not in novas}, **novas}
        falhas = 0
        try:
            for nid, n in sorted(todas.items(), key=lambda kv: (-kv[1]["numero"], kv[0])):
                if n.get("data") or datas_lidas >= DATAS_POR_EXECUCAO or falhas >= 3:
                    continue
                datas_lidas += 1
                try:
                    n["data"] = data_da_norma(pegar(s, n["fonte"]))
                    falhas = 0
                except comum.PrazoEsgotado:
                    raise
                except Exception as e:  # noqa: BLE001
                    falhas += 1
                    comum.avisar(f"RJ: data da norma {n['fonte']}: {e}")
        finally:
            comum.salvar(arq, {"coletadoEm": hoje.isoformat(), "fonte": BASE + NORMAS["lei"]["lista"], "normas": todas})
        print(f"RJ: normas {ano} {len(todas)} ({sum(1 for n in todas.values() if n['idsDeputados'])} com deputado ligado)")
    if datas_lidas >= DATAS_POR_EXECUCAO:
        print(f"RJ: {datas_lidas} datas de norma lidas; as que faltam ficam para a próxima execução")


# ---------------------------------------------------------------- proposições (scpro2327.nsf)

def limpar_ementa(ementa: str) -> str | None:
    return comum.compactar(re.sub(r"\s*=>.*$", "", ementa or ""))


def parse_proposicoes(html: str) -> list[dict]:
    """Linhas de uma lista ou busca de proposições: {cadastro, url, ementa, data, autor}. A busca traz uma linha por autor (ou por grupo de autores, separados por vírgula)."""
    linhas = []
    for linha in linhas_html(html):
        c, i, url = celulas(linha)
        if i is None or not re.fullmatch(r"\d{11}", c[i]):
            continue
        linhas.append({"cadastro": c[i], "url": url, "ementa": limpar_ementa(_coluna(c, i, 2)), "data": data_us_iso(_coluna(c, i, 3)),
                       "autor": comum.compactar(_coluna(c, i, 4))})
    return linhas


def juntar_proposicoes(registros: dict, linhas: list[dict]) -> None:
    """Acumula em `registros` {cadastro: {cadastro, url, ementa, data, autores}} as linhas de projetos (tipos 01 a 06)."""
    for l in linhas:
        if l["cadastro"][4:6] not in TIPOS_PROPOSICAO:
            continue
        r = registros.setdefault(l["cadastro"], {"cadastro": l["cadastro"], "url": l["url"], "ementa": l["ementa"], "data": l["data"], "autores": []})
        r["autores"] += [a for a in separar_nomes(l["autor"]) if a not in r["autores"]]


def item_proposicao(r: dict, ligados: dict) -> dict:
    sigla, descricao = TIPOS_PROPOSICAO[r["cadastro"][4:6]]
    return {"tipo": sigla, "tipoDescricao": descricao, "numero": int(r["cadastro"][6:]), "ano": int(r["cadastro"][:4]), "dataApresentacao": r["data"],
            "ementa": r["ementa"], "situacao": None, "emTramitacao": None, "linkTexto": r["url"], "idsAutores": r["autores"],
            "idsDeputados": list(dict.fromkeys(ligados[a] for a in r["autores"] if a in ligados)), "fonte": r["url"]}


def ler_proposicoes(pasta) -> dict:
    registros = {}
    for arq in sorted(pasta.glob("materias_[0-9]*.json")):
        for cad, m in (comum.ler(arq, {}) or {}).get("materias", {}).items():
            registros[cad] = {"cadastro": cad, "url": m["linkTexto"], "ementa": m["ementa"], "data": m["dataApresentacao"], "autores": m["idsAutores"]}
    return registros


def salvar_proposicoes(pasta, registros: dict, deputados: list[dict], hoje: date) -> None:
    ligados = ligar({a for r in registros.values() for a in nomes_de_deputados(r["autores"])}, deputados)
    por_ano = {}
    for cad, r in registros.items():
        por_ano.setdefault(cad[:4], {})[cad] = item_proposicao(r, ligados)
    for ano, materias in por_ano.items():
        comum.salvar(pasta / f"materias_{ano}.json", {"coletadoEm": hoje.isoformat(), "fonte": f"{BASE}/scpro2327.nsf/Internet/PropInt?OpenForm",
                                                      "materias": materias})


def topo_das_listas(s) -> set[str]:
    """Cadastros dos 15 mais novos de cada lista de projetos (a única parte que a paginação quebrada deixa ler)."""
    topo = set()
    for lista in PROPOSICOES_LISTAS:
        topo |= {l["cadastro"] for l in parse_proposicoes(pegar(s, f"{BASE}/scpro2327.nsf/Internet/{lista}?OpenForm"))}
    return topo


def coletar_proposicoes(s, deputados: list[dict], pasta, hoje: date) -> None:
    """Lê as proposições só quando o topo das listas traz cadastro novo ou a última leitura completa tem `RENOVAR_COMPLETA_DIAS`.
    A passada vai dos deputados lidos há mais tempo aos mais recentes e grava a cada 10 buscas (prazo)."""
    arq_estado = pasta / "proposicoes_estado.json"
    estado = comum.ler(arq_estado, {}) or {}
    registros = ler_proposicoes(pasta)
    topo = topo_das_listas(s)
    completa = estado.get("completaEm")
    velha = completa is None or (hoje - date.fromisoformat(completa)).days >= RENOVAR_COMPLETA_DIAS
    faltando = any(not (pasta / f"materias_{a}.json").exists() for a in range(ANO_INICIAL, hoje.year + 1))
    if not (topo - set(registros) - set(estado.get("topo", [])) or velha or faltando):
        print("RJ: proposições sem novidade")
        return
    lidos = dict(estado.get("deputados", {}))
    cheios = []
    try:
        for n, d in enumerate(sorted(deputados, key=lambda d: (lidos.get(d["id"], ""), d["id"])), 1):
            linhas = parse_proposicoes(pegar(s, url_busca(PROPOSICOES_VISAO, consulta_nome(d["nome"]))))
            if len(linhas) >= LIMITE_BUSCA:
                cheios.append(d["nome"])
            juntar_proposicoes(registros, linhas)
            lidos[d["id"]] = hoje.isoformat()
            if n % 10 == 0:
                salvar_proposicoes(pasta, registros, deputados, hoje)
                comum.salvar(arq_estado, {**estado, "deputados": lidos})
    finally:
        salvar_proposicoes(pasta, registros, deputados, hoje)
        comum.salvar(arq_estado, {**estado, "deputados": lidos})
    comum.salvar(arq_estado, {"completaEm": hoje.isoformat(), "topo": sorted(topo), "deputados": lidos})
    if cheios:
        comum.avisar(f"RJ: busca de proposições no teto de {LIMITE_BUSCA} linhas (pode faltar projeto antigo): {', '.join(cheios)}")
    print(f"RJ: proposições {len(registros)} (tipos 01 a 06) em {len(deputados)} buscas")


# ---------------------------------------------------------------- pautas e atas (links)

def parse_pautas(html: str, tipo: str) -> list[dict]:
    """Sessões ou reuniões de uma lista ou busca: {id, tipo, data, titulo, hora, comissao, arquivos, fonte}."""
    rotulo = PAUTAS[tipo]["rotulo"]
    itens = []
    for linha in linhas_html(html):
        c, i, url = celulas(linha)
        data = data_us_iso(c[i]) if i is not None else None
        if not data or not unid_documento(url):
            continue
        if tipo == "ordem-do-dia":
            hora = hora_24(_coluna(c, i, 1))
            titulo, comissao = " ".join(filter(None, [_coluna(c, i, 3), hora])), None
        else:
            hora = None
            titulo = _coluna(c, i, 1)
            comissao = comum.compactar(_coluna(c, i, 2)) if tipo == "ata-comissao" else None
        itens.append({"id": unid_documento(url), "tipo": tipo, "data": data, "titulo": comum.compactar(titulo), "hora": hora, "comissao": comissao,
                      "arquivos": [{"nome": rotulo, "url": url}], "fonte": url})
    return itens


def coletar_pautas(s, pasta, hoje: date) -> None:
    for ano in range(ANO_INICIAL, hoje.year + 1):
        arq = pasta / f"pautas_{ano}.json"
        if comum.ano_encerrado(ano, hoje, arq):
            continue
        itens = (comum.ler(arq, {}) or {}).get("itens", {})
        try:
            for tipo, cfg in PAUTAS.items():
                linhas = parse_pautas(pegar(s, url_busca(cfg["visao"], str(ano))), tipo)
                if len(linhas) >= LIMITE_BUSCA:
                    comum.avisar(f"RJ: busca de {tipo} em {ano} no teto de {LIMITE_BUSCA} linhas")
                for it in linhas:
                    if it["data"][:4] == str(ano):
                        itens[f"{tipo}|{it['id']}"] = it
        finally:
            comum.salvar(arq, {"coletadoEm": hoje.isoformat(), "fonte": BASE + PAUTAS["ordem-do-dia"]["lista"], "itens": itens})
        print(f"RJ: pautas e atas {ano} {len(itens)}")


# ---------------------------------------------------------------- contratos e atas de registro de preços (só links)

def links_relatorio(html: str) -> list[dict]:
    """[{ano, rotulo, url}] de um relatório da transparência: um bloco `collapse-<ano>` com linhas de rótulo e link de download."""
    achados = []
    for ano, bloco in re.findall(r'id="collapse-(\d{4})"(.*?)(?=id="collapse-\d{4}"|$)', html, re.S):
        for linha in bloco.split('class="row linha-mes"')[1:]:
            rotulo = re.search(r'mes-label">(.*?)</div>', linha, re.S)
            href = re.search(r'href="(/download-spic[^"]*)"', linha)
            if rotulo and href:
                achados.append({"ano": int(ano), "rotulo": comum.limpar(rotulo.group(1)), "url": TRANSPARENCIA + unescape(href.group(1))})
    return achados


def itens_orgao(contratos: list[dict], atas: list[dict]) -> dict:
    """{ano: {id: item}}: um contrato por relatório anual de contratos e uma ata de registro por ata, só com o link do PDF."""
    por_ano = {}
    for l in contratos:
        if comum.sem_acento(l["rotulo"]).lower() != "contratos":
            continue
        iid, item = comum.item_orgao(FONTE_ID, "contrato", f"relatorio-{l['ano']}", fornecedor_nome=None, objeto=f"Relatório de contratos de {l['ano']} (PDF)",
                                     arquivos=[{"url": l["url"], "nome": f"Contratos de {l['ano']} (PDF)", "data": None}], fonte=CONTRATOS_URL)
        por_ano.setdefault(l["ano"], {})[iid] = item
    for l in atas:
        m = re.match(r"Ata\s+(\d+/\d{4})\s*-\s*(.*)$", l["rotulo"], re.I)
        if not m:
            continue
        iid, item = comum.item_orgao(FONTE_ID, "ata_registro", m.group(1), fornecedor_nome=None, numero=m.group(1), objeto=m.group(2),
                                     arquivos=[{"url": l["url"], "nome": f"Ata {m.group(1)} (PDF)", "data": None}], fonte=ATAS_REGISTRO_URL)
        por_ano.setdefault(l["ano"], {})[iid] = item
    return por_ano


def coletar_orgao(s, pasta, hoje: date) -> None:
    contratos = links_relatorio(comum.get(s, CONTRATOS_URL, 30).text)
    atas = links_relatorio(comum.get(s, ATAS_REGISTRO_URL, 30).text)
    for ano, itens in itens_orgao(contratos, atas).items():
        antes = (comum.ler(pasta / f"orgao_{ano}.json", {}) or {}).get("itens", {})
        comum.salvar(pasta / f"orgao_{ano}.json", {"coletadoEm": hoje.isoformat(), "fonte": CONTRATOS_URL, "itens": {**antes, **itens}})
        print(f"RJ: órgão {ano} {len(itens)} (links de PDF)")


# ---------------------------------------------------------------- coleta

def coletar_presenca(s, deputados: list[dict], pasta, hoje: date) -> None:
    itens = []
    r = s.get(PRESENCA_URL, timeout=20)
    r.raise_for_status()
    for doc in links_presenca(texto(r)):
        resp = s.get(doc["url"], timeout=20)
        resp.raise_for_status()
        itens += itens_presenca(parse_presenca(texto(resp), doc["data"]), doc["url"], deputados)
    comum.salvar(pasta / "presenca.json", {"coletadoEm": hoje.isoformat(), "fonte": PRESENCA_URL, "itens": itens})
    print(f"RJ: presença {len(itens)} registros")


def coletar_emendas(s, deputados: list[dict], pasta, hoje: date) -> None:
    r = s.get(EMENDAS_URL, timeout=20)
    r.raise_for_status()
    for ano, url in links_emendas(texto(r)).items():
        if comum.ano_encerrado(ano, hoje, pasta / f"emendas_{ano}.json"):
            continue
        resp = s.get(url, timeout=60)
        resp.raise_for_status()
        registros = emendas_da_aba(comum.xlsx_abas(resp.content).get("Impositivas", []))
        itens = itens_emendas(registros, deputados, EMENDAS_URL, ano)
        comum.salvar(pasta / f"emendas_{ano}.json", {"coletadoEm": hoje.isoformat(), "fonte": EMENDAS_URL, "itens": itens})
        print(f"RJ: emendas {ano} {len(itens)} de {len(registros)}")


def coletar() -> None:
    pasta = comum.DADOS / UF
    hoje = date.today()
    s = comum.sessao()
    deputados = deputados_do_tse()
    if not deputados:
        comum.avisar("RJ: sem eleitos de 2022 em dados/tse/2022/RJ.json")
        return
    comum.salvar(pasta / "deputados.json", {"fonte": "https://divulgacandcontas.tse.jus.br/divulga/#/home", "host": None, "legislatura": "2023-2027",
                                            "deputados": deputados})
    comum.rodar_etapas(UF, [
        ("presença", lambda: coletar_presenca(s, deputados, pasta, hoje)),
        ("emendas", lambda: coletar_emendas(s, deputados, pasta, hoje)),
        ("normas", lambda: coletar_normas(s, deputados, pasta, hoje)),
        ("proposições", lambda: coletar_proposicoes(s, deputados, pasta, hoje)),
        ("pautas e atas", lambda: coletar_pautas(s, pasta, hoje)),
        ("contratos e atas de registro", lambda: coletar_orgao(s, pasta, hoje)),
    ])
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
    linhas = comum.xlsx_abas(resp.content).get("Impositivas", [])
    cab = next(i for i, lin in enumerate(linhas) if "Autor" in lin.values())
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
        falhas += comum.campos_vazios(r, ("autor", "valor", "objeto"), "emenda")
    return falhas, []


def _recortar_linhas(html: str, manter) -> str:
    """Tira de uma lista ou busca as linhas `<tr valign="top">` para as quais `manter(n, linha)` é falso."""
    partes, ultimo = [], 0
    for n, m in enumerate(re.finditer(r'<tr valign="top">.*?</tr>', html, re.S)):
        partes.append(html[ultimo:m.start()])
        ultimo = m.end()
        if manter(n, m.group(0)):
            partes.append(m.group(0))
    partes.append(html[ultimo:])
    return "".join(partes)


def _primeiras(html: str, quantas: int) -> str:
    return _recortar_linhas(html, lambda n, linha: n < quantas)


def _trecho_relatorio(html: str) -> str:
    inicio = html.index('id="collapse-')
    return html[inicio: html.index("Voltar", inicio)]


def _contrato_normas(ctx):
    s = comum.sessao()
    registro = {"lei": _primeiras(pegar(s, url_busca(NORMAS["lei"]["visao"], "2026")), 3),
                "lc": _primeiras(pegar(s, url_busca(NORMAS["lc"]["visao"], "2026")), 2),
                "dec": _primeiras(pegar(s, url_busca(NORMAS["dec"]["visao"], "2025")), 2),
                "res": _primeiras(pegar(s, url_busca(NORMAS["res"]["visao"], "2023")), 3)}
    registro["documento"] = pegar(s, parse_normas(registro["lei"], "lei")[0]["url"])[:3000]
    return registro


def _conferir_normas(registro):
    falhas = []
    for chave in NORMAS:
        normas = parse_normas(registro[chave], chave)
        if not normas:
            falhas.append(f"busca de {chave} sem normas reconhecidas")
        for n in normas:
            falhas += comum.campos_vazios(n, ("numero", "ano", "ementa", "url"), f"{chave} {n['numero']}")
    if not any(n["autoria"] for n in parse_normas(registro["lei"], "lei")):
        falhas.append("lei sem autoria")
    if not data_da_norma(registro["documento"]):
        falhas.append("documento da lei sem 'Data da Lei'")
    return falhas, []


def _contrato_proposicoes(ctx):
    s = comum.sessao()
    busca = pegar(s, url_busca(PROPOSICOES_VISAO, consulta_nome("Carlos Minc")))
    projetos = [i for i, l in enumerate(linhas_html(busca)) if l.count("scpro2327.nsf") and re.search(r">\d{4}0[1-6]\d{5}<", l)]
    escolhidas = set(projetos[:5])
    return {"busca": _recortar_linhas(busca, lambda n, linha: n in escolhidas),
            "lista": _primeiras(pegar(s, f"{BASE}/scpro2327.nsf/Internet/LeiInt?OpenForm"), 3)}


def _conferir_proposicoes(registro):
    falhas = []
    linhas = parse_proposicoes(registro["busca"])
    if not linhas:
        falhas.append("busca de proposições sem linhas reconhecidas")
    for l in linhas:
        falhas += comum.campos_vazios(l, ("ementa", "data", "autor", "url"), f"proposição {l['cadastro']}")
        if l["cadastro"][4:6] not in TIPOS_PROPOSICAO:
            falhas.append(f"proposição {l['cadastro']} de tipo fora dos conhecidos")
    if not parse_proposicoes(registro["lista"]):
        falhas.append("lista de projetos de lei sem cadastros")
    return falhas, []


def _contrato_pautas(ctx):
    s = comum.sessao()
    return {tipo: _primeiras(pegar(s, url_busca(cfg["visao"], "2026")), 3) for tipo, cfg in PAUTAS.items()}


def _conferir_pautas(registro):
    falhas = []
    for tipo in PAUTAS:
        itens = parse_pautas(registro[tipo], tipo)
        if not itens:
            falhas.append(f"busca de {tipo} sem itens reconhecidos")
        for i in itens:
            falhas += comum.campos_vazios(i, ("data", "titulo", "fonte"), f"{tipo} {i['id']}")
    return falhas, []


def _contrato_orgao(ctx):
    s = comum.sessao()
    return {"contratos": _trecho_relatorio(comum.get(s, CONTRATOS_URL, 30).text), "atas": _trecho_relatorio(comum.get(s, ATAS_REGISTRO_URL, 30).text)}


def _conferir_orgao(registro):
    falhas = []
    contratos, atas = links_relatorio(registro["contratos"]), links_relatorio(registro["atas"])
    if not any(comum.sem_acento(l["rotulo"]).lower() == "contratos" for l in contratos):
        falhas.append("relatório /118 sem linha CONTRATOS")
    if not itens_orgao(contratos, atas):
        falhas.append("nenhum contrato nem ata reconhecidos nos relatórios /118 e /51")
    if not any(re.match(r"Ata\s+\d+/\d{4}\s*-", l["rotulo"]) for l in atas):
        falhas.append("relatório /51 sem linha 'Ata NN/AAAA - objeto'")
    return falhas, []


CONTRATOS = [
    {"nome": "estadual_rj_presenca", "fonte": PRESENCA_URL, "buscar": _contrato_presenca, "html": _conferir_presenca},
    {"nome": "estadual_rj_emendas", "fonte": EMENDAS_URL, "buscar": _contrato_emendas, "html": _conferir_emendas},
    {"nome": "estadual_rj_normas", "fonte": BASE + NORMAS["lei"]["lista"], "buscar": _contrato_normas, "html": _conferir_normas},
    {"nome": "estadual_rj_proposicoes", "fonte": BASE + "/scpro2327.nsf/Internet/PropInt?OpenForm", "buscar": _contrato_proposicoes,
     "html": _conferir_proposicoes},
    {"nome": "estadual_rj_pautas", "fonte": BASE + PAUTAS["ordem-do-dia"]["lista"], "buscar": _contrato_pautas, "html": _conferir_pautas},
    {"nome": "estadual_rj_orgao", "fonte": CONTRATOS_URL, "buscar": _contrato_orgao, "html": _conferir_orgao},
]


if __name__ == "__main__":
    comum.principal(coletar)
