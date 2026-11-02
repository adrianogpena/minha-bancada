"""
Deputados estaduais de Mato Grosso do Sul (ALEMS). Grava em dados/estaduais/MS/ (contrato em estaduais_comum.py).

Fontes lidas aqui:
  - lista de deputados: eleitos de 2022 do TSE (dados/tse/2022/MS.json); al.ms.gov.br não publica a lista em formato aberto;
  - CEAP (cota do exercício da atividade parlamentar), CSV por ano, 2012 em diante (aqui desde 2023):
    https://transparencia2.al.ms.gov.br/ceap/notas/exportar-csv?ano=2026; o comprovante (PDF da nota) é a fonte de cada item;
  - diárias: https://transparencia2.al.ms.gov.br/consulta-diarias/exportar-csv?ano=2026 (2021 a 2026: "Não houve despesa", sem itens).

  - pautas (instantâneo do dia, o histórico é o que as coletas diárias guardam): https://al.ms.gov.br/Pauta (projetos com prazo de
    emendas) e https://al.ms.gov.br/Ordemdodia (sessão do dia), HTML sem captcha, com projeto, processo, autor e ementa
    (pautas_<ano>.json, tipo "pauta" e "ordem-do-dia"); o autor deputado liga por identidades.ligar_nomes;
  - atas das sessões, PDFs do portal antigo gerdocumento/2128 (ano > mês > PDF), só link (pautas_<ano>.json, tipo "atas");
  - remuneração: PDF mensal "Deputado Estadual" do portal antigo (https://www.transparencia.al.ms.gov.br/pages/index.php/gerdocumento/1201,
    ano > mês), lido com pypdf em modo layout; o deputado só é gravado se créditos, débitos e líquido do PDF fecharem (remuneracao_<ano>.json);
  - contratos do órgão (gerdocumento/52, pastas de inexigibilidade, dispensa, pregão, convite, tomada de preço e concorrência por ano e
    processo) e atas de adesão a registro de preços (gerdocumento/1887): só título e link do PDF, sem fornecedor nem valor
    (orgao_<ano>.json). Processo de licitação sem documento de contrato na pasta não é gravado;
  - regras da verba: página da CEAP e PDF do ato da Mesa Diretora (gerdocumento/5477) como link (regras_ressarcimento.json).

Não coletado: proposições e votações (sistema sgpl atrás de desafio proof-of-work, não contornado), gabinete (a lista de servidores não
traz lotação), presença, normas com autoria e emendas (não publicadas).
"""

import csv
import io
import re
import time
import zlib
from collections import defaultdict
from datetime import date
from functools import partial
from html import unescape
from io import BytesIO

import estaduais_comum as comum
import identidades

UF = "MS"
PASTA = comum.DADOS / UF
TRANSP = "https://transparencia2.al.ms.gov.br"
CEAP_PAGINA = f"{TRANSP}/ceap"
CEAP_CSV = f"{TRANSP}/ceap/notas/exportar-csv?ano={{ano}}"
DIARIAS_PAGINA = f"{TRANSP}/consulta-diarias"
DIARIAS_CSV = f"{TRANSP}/consulta-diarias/exportar-csv?ano={{ano}}"
TSE_ARQUIVO = comum.arquivo_tse(UF)
TSE_FICHA = comum.ficha_tse(UF)
ANO_INICIAL = 2023
TIMEOUT = 90
SITE = "https://al.ms.gov.br"
PAUTA_PAGINA = f"{SITE}/Pauta"
ORDEM_PAGINA = f"{SITE}/Ordemdodia"
PORTAL = "https://www.transparencia.al.ms.gov.br/pages/index.php/gerdocumento/{}"
FONTE_ID = "alems_ms"
REMUNERACAO = 1201
ATAS_SESSAO = 2128
ATAS_ADESAO = 1887
REGRAS_PASTA = 5477
MODALIDADES = {"Inexigibilidade": 1230, "Dispensa": 1231, "Pregão": 1232, "Convite": 1234, "Tomada de Preço": 1235, "Concorrência": 1236}
MESES_RECENTES = 2
RENOVAR_COMPLETA_DIAS = 14
RELER_PROCESSO_DIAS = 7
PAUSA = 0.7


def deputados_do_tse() -> list[dict]:
    return comum.deputados_do_tse(TSE_ARQUIVO, TSE_FICHA)


def linhas_csv(texto: str, cabecalho_em: str) -> list[dict]:
    """Linhas do CSV com ';' como dicts de cabeçalho sem acento; ignora o que vem antes da linha com `cabecalho_em`."""
    todas = list(csv.reader(io.StringIO(texto.lstrip("﻿")), delimiter=";"))
    inicio = next((i for i, linha in enumerate(todas) if cabecalho_em in [comum.sem_acento(c).upper() for c in linha]), None)
    if inicio is None:
        return []
    cab = [comum.sem_acento(c).upper() for c in todas[inicio]]
    return [dict(zip(cab, linha, strict=False)) for linha in todas[inicio + 1:] if any(c.strip() for c in linha)]


ligar = partial(identidades.ligar_nomes, uf=UF)


def itens_ceap(linhas: list[dict], ligacao: dict, fonte: str) -> tuple[list[dict], set]:
    itens, sem_par = [], set()
    for linha in linhas:
        nome = linha.get("DEPUTADO", "")
        pid = ligacao.get(nome)
        if not pid:
            sem_par.add(comum.nome_limpo(nome))
            continue
        itens.append({"idDeputado": pid, "mes": comum.mes_numero(linha.get("MES")), "categoria": " ".join((linha.get("CATEGORIA") or "").split()) or None,
                      **comum.fornecedor(linha.get("FORNECEDOR"), linha.get("CPF/CNPJ")),
                      "valor": comum.valor_br(linha.get("VALOR (R$)")), "documento": linha.get("DOCUMENTO") or None,
                      "emissao": emissao_iso(linha.get("EMISSAO")), "fonte": (linha.get("COMPROVANTE") or "").strip() or fonte})
    return itens, sem_par


def emissao_iso(texto) -> str | None:
    return comum.data_br_iso(texto, inteiro=True)


def baixar(s, url: str) -> str:
    return comum.baixar(s, url, timeout=TIMEOUT).decode("utf-8-sig", errors="replace")


def coletar_ceap(s, deputados: list[dict]) -> None:
    hoje = date.today()
    sem_par = set()
    for ano in range(ANO_INICIAL, hoje.year + 1):
        destino = PASTA / f"verbas_{ano}.json"
        if ano < hoje.year and destino.exists():
            continue
        url = CEAP_CSV.format(ano=ano)
        linhas = linhas_csv(baixar(s, url), "DEPUTADO")
        ligacao = ligar({linha["DEPUTADO"] for linha in linhas}, deputados)
        itens, sp = itens_ceap(linhas, ligacao, f"{CEAP_PAGINA}")
        sem_par |= sp
        if itens or ano == hoje.year:
            comum.salvar(destino, {"coletadoEm": hoje.isoformat(), "fonte": CEAP_PAGINA, "itens": itens})
            print(f"MS: CEAP {ano}: {len(itens)} itens de {len(linhas)} linhas")
    if sem_par:
        comum.avisar(f"MS: CEAP sem deputado eleito em 2022 ({len(sem_par)}): {sorted(sem_par)[:12]}")


def linhas_diarias(texto: str) -> list[dict]:
    """Linhas de diárias com dados; o portal devolve uma linha "Não houve despesa" por mês quando não há."""
    return [linha for linha in linhas_csv(texto, "MES") if "nao houve" not in comum.sem_acento(linha.get("INFORMACAO", ""))]


def coletar_diarias(s) -> None:
    hoje = date.today()
    for ano in range(max(ANO_INICIAL, hoje.year - 1), hoje.year + 1):  # só conta e avisa, nada é gravado: anos encerrados não precisam
        n = len(linhas_diarias(baixar(s, DIARIAS_CSV.format(ano=ano))))
        print(f"MS: diárias {ano}: {n} lançamentos" + (" (portal: sem despesa)" if not n else ""))
        if n:
            comum.avisar(f"MS: diárias {ano} têm {n} linhas, formato com dados ainda não tratado")


# ---------------------------------------------------------------- pautas (HTML do dia)

def decodificar(conteudo: bytes) -> str:
    try:
        return conteudo.decode("utf-8")
    except UnicodeDecodeError:
        return conteudo.decode("cp1252", errors="replace")


def baixar_html(s, url: str) -> str:
    return decodificar(comum.baixar(s, url, timeout=TIMEOUT))


def linhas_da_pagina(html: str) -> list[str]:
    """Linhas de texto do miolo da Pauta/Ordem do dia (depois do último <hr />); o link do projeto vai no fim como `[[url]]`."""
    miolo = html.rsplit("<hr />", 1)[-1].split("</section>")[0]
    miolo = re.sub(r'<a [^>]*href="([^"]*)"[^>]*>(.*?)</a>', r"\2 [[\1]]", miolo, flags=re.S)
    miolo = re.sub(r"<br\s*/?>|</p>|</div>|</li>", "\n", miolo)
    texto = unescape(re.sub(r"<[^>]+>", "", miolo)).replace("\xa0", " ")
    return [linha for linha in (comum.compactar(x) for x in texto.split("\n")) if linha]


ITEM = re.compile(r"^(\d+)\s*-\s*(.+?)\s+n[ºo°]\s*([\d.]+)/(\d{4})(?:\s*\[\[(.*?)\]\])?\s*$", re.I)
PROCESSO = re.compile(r"^Processo\s+n[ºo°]\s*([\d.]+/\d{4})\s*$", re.I)
SESSAO = re.compile(r"SESS[ÃA]O\s+(.+?)\s+DO DIA\s+(\d\d/\d\d/\d{4})", re.I)
PRAZO = re.compile(r"AT[ÉE]\s+(\d\d/\d\d/\d{4})\s*$", re.I)
CORTE_AUTOR = re.compile(r"\s[-–—](?:\s|$)")


def autor_e_ementa(linha: str) -> tuple[str, str | None]:
    partes = CORTE_AUTOR.split(linha, maxsplit=1)
    return comum.compactar(partes[0]) or "", comum.compactar(partes[1]) if len(partes) > 1 else None


def nomes_do_autor(autor: str) -> list[str]:
    """Nomes de deputado do campo de autoria ("Deputado X", "Deputadas A e B"); outro autor (Poder Executivo, comissão, Mesa) não tem nome."""
    m = re.match(r"^Deputad[oa]s?\s+(.+)$", autor, re.I)
    if not m:
        return []
    return [n for n in (comum.compactar(x) for x in re.split(r"\s*,\s*|\s+e\s+", m.group(1))) if n]


def ler_pagina(html: str) -> list[dict]:
    """Blocos da página: {titulo, sessao (data ISO, só na Ordem do dia), prazoEmendas (ISO, só na Pauta), processos: [..]}. Projeto sem
    "Processo nº" ou sem linha de autoria não entra: a leitura não adivinha."""
    blocos, bloco, fase, atual = [], None, None, None

    def novo(titulo, **extra):
        nonlocal bloco, atual
        bloco = {"titulo": titulo, "processos": [], **extra}
        blocos.append(bloco)
        atual = None

    for linha in linhas_da_pagina(html):
        m_sessao = SESSAO.search(linha)
        if m_sessao and not ITEM.match(linha):
            novo(f"Sessão {m_sessao.group(1).lower()}", sessao=comum.data_br_iso(m_sessao.group(2)))
            fase = None
            continue
        if linha.upper().startswith("PER") and "PAUTA" in linha.upper() and "[[" not in linha:
            novo(linha[:1].upper() + linha[1:].lower(), prazoEmendas=None)
            fase = None
            continue
        pauta_aberta = bloco is not None and "prazoEmendas" in bloco and bloco["prazoEmendas"] is None
        if pauta_aberta and "PRAZO" in linha.upper() and PRAZO.search(linha):
            bloco["prazoEmendas"] = comum.data_br_iso(PRAZO.search(linha).group(1))
            continue
        if pauta_aberta and linha.startswith("("):
            bloco["titulo"] = f"{bloco['titulo']} {linha}"
            continue
        if bloco is not None and bloco.get("sessao") and linha.upper() == linha and re.search(r"DISCUSS|VOTA", linha) and not ITEM.match(linha):
            if not linha.startswith("PARECER"):
                fase = comum.compactar(linha.title())
                atual = None
            continue
        m_item = ITEM.match(linha)
        if m_item and bloco is not None:
            atual = {"tipo": comum.compactar(m_item.group(2)), "numero": m_item.group(3), "ano": int(m_item.group(4)), "processo": None, "fase": fase,
                     "autor": None, "ementa": None, "fonte": m_item.group(5) or None}
            bloco["processos"].append(atual)
            continue
        if atual is None:
            continue
        m_proc = PROCESSO.match(linha)
        if m_proc and atual["processo"] is None:
            atual["processo"] = m_proc.group(1)
        elif atual["processo"] and atual["autor"] is None and not linha.upper().startswith("PARECER"):
            atual["autor"], atual["ementa"] = autor_e_ementa(linha)
    return [{**b, "processos": [p for p in b["processos"] if p["processo"] and p["autor"]]} for b in blocos
            if any(p["processo"] and p["autor"] for p in b["processos"])]


def itens_da_pagina(blocos: list[dict], pagina: str, deputados: list[dict]) -> dict:
    """{chave: item} de `pautas_<ano>.json`, tipo "ordem-do-dia" (um por sessão, id = a data) ou "pauta" (um por período de pauta, id = título
    e prazo das emendas). Deputado autor liga só por `ligar`; nome sem par fica só como texto."""
    nomes = {n for b in blocos for p in b["processos"] for n in nomes_do_autor(p["autor"])}
    ligacao = ligar(nomes, deputados) if nomes else {}
    itens = {}
    for b in blocos:
        sessao = b.get("sessao")
        data = sessao or b.get("prazoEmendas")
        if not data:
            continue
        processos = []
        for p in b["processos"]:
            processos.append({**p, "fonte": p["fonte"] or pagina, "idsDeputados": [ligacao[n] for n in nomes_do_autor(p["autor"]) if n in ligacao]})
        ids_dep = sorted({i for p in processos for i in p["idsDeputados"]})
        tipo = "ordem-do-dia" if sessao else "pauta"
        iid = sessao if sessao else f"{b['titulo']}|{data}"
        itens[f"{tipo}|{iid}"] = {"id": iid, "tipo": tipo, "titulo": b["titulo"], "data": sessao, "prazoEmendas": b.get("prazoEmendas"),
                                  "arquivos": [], "processos": processos, "idsDeputados": ids_dep, "fonte": pagina}
    return itens


def coletar_pautas(s, deputados: list[dict]) -> None:
    hoje = date.today()
    novos = {}
    for pagina in (PAUTA_PAGINA, ORDEM_PAGINA):
        itens = itens_da_pagina(ler_pagina(baixar_html(s, pagina)), pagina, deputados)
        if not itens:
            raise RuntimeError(f"{pagina} sem nenhum projeto lido; mantém os arquivos anteriores")
        novos |= itens
    por_ano = defaultdict(dict)
    for chave, i in novos.items():
        por_ano[int((i["data"] or i["prazoEmendas"])[:4])][chave] = i
    for ano, itens in por_ano.items():
        arq = PASTA / f"pautas_{ano}.json"
        anterior = comum.ler(arq, {})
        guardados = dict(anterior.get("itens") or {})
        guardados.update(itens)
        comum.salvar(arq, {**anterior, "coletadoEm": hoje.isoformat(), "fonte": ORDEM_PAGINA, "itens": guardados})
        print(f"MS: pautas {ano}: {len(itens)} lidas agora, {len(guardados)} no arquivo")


# ---------------------------------------------------------------- portal antigo (gerdocumento): pastas e PDFs

def ler_pasta(html: str) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """([(id da subpasta, título)], [(título, url do PDF)]) do HTML de uma pasta do portal antigo (texto em UTF-8; título com caractere
    inválido na própria fonte fica como veio)."""
    pastas, arquivos = [], []
    for linha in re.findall(r"<tr>(.*?)</tr>", html[html.find("<tbody>"):], re.S):
        sub = re.search(r'<a href="(\d+)"(?:[^>"]|"[^"]*")*>(.*?)</a>', linha, re.S)
        pdf = re.search(r'href="(https?://[^"]*/uploads/[^"]+)"', linha)
        celulas = re.findall(r"<td[^>]*>(.*?)</td>", linha, re.S)
        if sub:
            pastas.append((sub.group(1), comum.compactar(unescape(re.sub(r"<[^>]+>", " ", sub.group(2))).replace("\xa0", " ").replace("+", " ")) or ""))
        elif pdf and len(celulas) > 1:
            arquivos.append((comum.compactar(unescape(re.sub(r"<[^>]+>", "", celulas[1]))) or "", pdf.group(1)))
    return pastas, arquivos


def pasta_do_portal(s, pasta: int | str) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    time.sleep(PAUSA)
    return ler_pasta(baixar_html(s, PORTAL.format(pasta)))


def pasta_do_ano(s, raiz: int | str, ano: int) -> str | None:
    return next((pid for pid, titulo in pasta_do_portal(s, raiz)[0] if titulo.strip() == str(ano)), None)


def id_do_pdf(url: str) -> str:
    return url.rsplit("/", 1)[-1].rsplit(".", 1)[0]


def pdf_arquivo(titulo: str, url: str) -> dict:
    return {"nome": titulo, "url": url, "data": None}


# ---------------------------------------------------------------- atas das sessões

DATA_NO_TITULO = re.compile(r"(\d\d)-(\d\d)-(\d{4})")


def item_ata(titulo: str, url: str, ano_pasta: int) -> tuple[str, dict]:
    m = DATA_NO_TITULO.search(titulo)
    data = comum.data_br_iso(f"{m.group(1)}/{m.group(2)}/{m.group(3)}") if m else None
    if data and int(data[:4]) != ano_pasta:
        data = None
    iid = id_do_pdf(url)
    return f"atas|{iid}", {"id": iid, "tipo": "atas", "titulo": titulo, "data": data, "arquivos": [{"nome": titulo, "url": url}],
                           "fonte": PORTAL.format(ATAS_SESSAO)}


def coletar_atas(s, hoje: date) -> None:
    for ano in range(ANO_INICIAL, hoje.year + 1):
        arq = PASTA / f"pautas_{ano}.json"
        if comum.ano_encerrado(ano, hoje, arq) and comum.ler(arq, {}).get("atasEm"):
            continue
        pasta = pasta_do_ano(s, ATAS_SESSAO, ano)
        if not pasta:
            comum.avisar(f"MS: pasta de atas {ano} não achada em gerdocumento/{ATAS_SESSAO}")
            continue
        anterior = comum.ler(arq, {})
        meses = dict(anterior.get("atasMeses") or {})
        itens = dict(anterior.get("itens") or {})
        recentes = {f"{a}-{m:02d}" for a, m in comum.meses_recentes(hoje, MESES_RECENTES)}
        lidas = 0
        try:
            for pid, titulo in pasta_do_portal(s, pasta)[0]:
                mes = comum.mes_numero(titulo)
                if not mes:
                    continue
                chave = f"{ano}-{mes:02d}"
                if chave in meses and chave not in recentes:
                    continue
                for t, url in pasta_do_portal(s, pid)[1]:
                    k, item = item_ata(t, url, ano)
                    itens[k] = item
                meses[chave] = hoje.isoformat()
                lidas += 1
        finally:
            comum.salvar(arq, {**anterior, "coletadoEm": hoje.isoformat(), "fonte": anterior.get("fonte") or ORDEM_PAGINA, "atasEm": hoje.isoformat(),
                               "atasMeses": meses, "itens": itens})
        print(f"MS: atas {ano}: {lidas} pastas de mês lidas, {sum(i['tipo'] == 'atas' for i in itens.values())} atas no arquivo")


# ---------------------------------------------------------------- remuneração (PDF mensal)

NUM = r"\d{1,3}(?:\.\d{3})*,\d\d"
CABECALHO_NOME = re.compile(r"^(\S.*?\S)\s{2,}(\d\d-\d{6})\s*$")
REFERENCIA = re.compile(r"Refer\S*ncia\s*:\s*([^\W\d_]+)/(\d{4})\s+Folha\s*:\s*(.+?)\s*$")
SUBTOTAL = re.compile(r"Sub Total\s*>>>\s+(" + NUM + r")\s+(" + NUM + r")\s+(" + NUM + r")\s*$")


def texto_do_pdf(conteudo: bytes) -> list[str]:
    from pypdf import PdfReader
    linhas = []
    for pagina in PdfReader(BytesIO(conteudo)).pages:
        linhas += (pagina.extract_text(extraction_mode="layout") or "").split("\n")
    return linhas


SUBTOTAL_PARTIDO = re.compile(r"^(?P<resto>.*?)\s*Sub Total\s*>>>\s+(?P<liq>" + NUM + r")\s*$")
DOIS_VALORES = re.compile(r"^\s*(" + NUM + r")\s+(" + NUM + r")\s*$")


def juntar_subtotal(linhas: list[str]) -> list[str]:
    """Quando o rótulo do último evento quebra ("FAP/UNALE - 35ª CHAMADA DO" + "FAP"), o PDF põe o líquido na linha do "Sub Total >>>" e
    crédito e débito na linha seguinte; junta tudo numa linha só, com a sobra do rótulo antes dela."""
    saida, i = [], 0
    while i < len(linhas):
        m = SUBTOTAL_PARTIDO.match(linhas[i])
        dois = DOIS_VALORES.match(linhas[i + 1]) if m and i + 1 < len(linhas) else None
        if m and dois:
            if m.group("resto").strip():
                saida.append("    " + m.group("resto").strip())
            saida.append(f"Sub Total >>>  {dois.group(1)}  {dois.group(2)}  {m.group('liq')}")
            i += 2
        else:
            saida.append(linhas[i])
            i += 1
    return saida


def folha_do_pdf(linhas: list[str]) -> tuple[tuple[int, int] | None, str | None, list[dict]]:
    """((ano, mês) e folha do cabeçalho, [{nome, matricula, creditos: {evento: valor}, debitos: {evento: valor}, totalCredito, totalDebito,
    liquido, ok}]). O evento vai para crédito ou débito pela coluna do número (comparada à do cabeçalho "Evento Crédito Débito"). `ok`
    só quando créditos, débitos e líquido fecham com o subtotal do PDF; sem isso o deputado não vira dado."""
    referencia = folha = None
    deputados, atual, corte, ultimo = [], None, None, None
    for linha in juntar_subtotal(linhas):
        m = REFERENCIA.search(linha)
        if m and referencia is None:
            mes = comum.mes_numero(m.group(1))
            referencia, folha = ((int(m.group(2)), mes) if mes else None), m.group(3)
            continue
        cab = CABECALHO_NOME.match(linha)
        if cab and "Evento" not in linha:
            atual = {"nome": comum.compactar(cab.group(1)), "matricula": cab.group(2), "creditos": {}, "debitos": {}, "ok": False}
            deputados.append(atual)
            corte = ultimo = None
            continue
        if atual is None:
            continue
        if re.search(r"Evento\s+Cr\S*dito\s+D\S*bito", linha):
            corte = (re.search(r"Cr\S*dito", linha).end() + re.search(r"D\S*bito", linha).end()) / 2
            ultimo = None
            continue
        st = SUBTOTAL.search(linha)
        if st:
            tc, td, liq = (comum.valor_br(g) for g in st.groups())
            atual.update(totalCredito=tc, totalDebito=td, liquido=liq)
            atual["ok"] = bool(atual["creditos"] and abs(round(sum(atual["creditos"].values()), 2) - tc) < 0.005
                               and abs(round(sum(atual["debitos"].values()), 2) - td) < 0.005 and abs(round(tc - td, 2) - liq) < 0.005)
            atual = None
            continue
        if corte is None:
            continue
        m_val = re.search(r"\s(" + NUM + r")\s*$", linha)
        rotulo = comum.compactar(linha[:m_val.start()] if m_val else linha)
        if not m_val:
            if rotulo and ultimo and not re.search(r"\d", rotulo):
                coluna, antigo = ultimo
                coluna[comum.compactar(f"{antigo} {rotulo}")] = coluna.pop(antigo)
                ultimo = (coluna, comum.compactar(f"{antigo} {rotulo}"))
            continue
        coluna = atual["creditos"] if m_val.end(1) <= corte else atual["debitos"]
        coluna[rotulo] = comum.valor_br(m_val.group(1))
        ultimo = (coluna, rotulo)
    return referencia, folha, deputados


def itens_remuneracao(deputados_pdf: list[dict], arquivo: dict, deputados: list[dict]) -> list[dict]:
    """Um item por deputado do PDF cuja conta fecha e cujo nome liga a um deputado (só por `ligar`)."""
    validos = [d for d in deputados_pdf if d["ok"]]
    ligados = ligar({d["nome"] for d in validos}, deputados)
    itens = []
    for d in validos:
        pid = ligados.get(d["nome"])
        if not pid:
            continue
        componentes = {**{rotulo.title(): v for rotulo, v in d["creditos"].items()}, "descontos": d["totalDebito"]}
        itens.append({"idDeputado": pid, "mes": arquivo["mes"], "bruto": d["totalCredito"], "liquido": d["liquido"], "componentes": componentes,
                      "matricula": d["matricula"], "pdf": arquivo["id"], "fonte": arquivo["url"]})
    return sorted(itens, key=lambda i: (i["idDeputado"], i["mes"]))


def arquivos_da_folha(s, ano: int) -> list[dict]:
    pasta = pasta_do_ano(s, REMUNERACAO, ano)
    if not pasta:
        return []
    achados = []
    for titulo, url in pasta_do_portal(s, pasta)[1]:
        mes = comum.mes_numero(titulo)
        if mes:
            achados.append({"ano": ano, "mes": mes, "id": id_do_pdf(url), "url": url})
    return sorted(achados, key=lambda a: (a["mes"], a["id"]))


def coletar_remuneracao(s, deputados: list[dict], hoje: date) -> None:
    for ano in range(ANO_INICIAL, hoje.year + 1):
        arq = PASTA / f"remuneracao_{ano}.json"
        if comum.ano_encerrado(ano, hoje, arq):
            continue
        arquivos = arquivos_da_folha(s, ano)
        if not arquivos:
            comum.avisar(f"MS: remuneração {ano}: nenhum PDF mensal na pasta; mantém o arquivo anterior")
            continue
        anterior = comum.ler(arq, {})
        completa_em = anterior.get("completaEm")
        completa_velha = not completa_em or (hoje - date.fromisoformat(completa_em)).days >= RENOVAR_COMPLETA_DIAS
        recentes = comum.meses_recentes(hoje, MESES_RECENTES)
        lidos, itens = dict(anterior.get("pdfs") or {}), list(anterior.get("itens") or [])
        novos = falhas = 0
        interrompido = None
        for a in arquivos:
            if a["id"] in lidos and not (completa_velha and (ano, a["mes"]) in recentes):
                continue
            try:
                time.sleep(PAUSA)
                referencia, folha, pdf = folha_do_pdf(texto_do_pdf(comum.baixar(s, a["url"], timeout=180)))
                if referencia != (a["ano"], a["mes"]) or "deputado" not in (folha or "").lower():
                    raise RuntimeError(f"PDF é da folha {folha!r} de {referencia}, a pasta diz {a['ano']}-{a['mes']:02d}")
                achados = itens_remuneracao(pdf, a, deputados)
                if len(achados) < len(pdf):
                    comum.avisar(f"MS: remuneração {ano}-{a['mes']:02d}: {len(pdf) - len(achados)} de {len(pdf)} deputados do PDF ficaram de fora "
                                 "(conta que não fecha ou nome sem par)")
                if not achados:
                    raise RuntimeError("nenhum deputado lido")
            except comum.PrazoEsgotado as e:
                interrompido = e
                break
            except Exception as e:  # noqa: BLE001
                falhas += 1
                comum.avisar(f"MS: remuneração {ano}-{a['mes']:02d} (PDF {a['id']}): {e}")
                continue
            itens = [i for i in itens if i.get("pdf") != a["id"]] + achados
            lidos[a["id"]] = a["mes"]
            novos += 1
        if novos or not arq.exists():
            completa = hoje.isoformat() if completa_velha and not falhas and not interrompido else completa_em
            comum.salvar(arq, {"coletadoEm": hoje.isoformat(), "completaEm": completa, "fonte": PORTAL.format(REMUNERACAO), "pdfs": lidos,
                               "itens": sorted(itens, key=lambda i: (i["mes"], i["idDeputado"]))})
        print(f"MS: remuneração {ano}: {novos} PDFs lidos, {len(lidos)} no arquivo ({falhas} falhas)")
        if interrompido:
            raise interrompido


# ---------------------------------------------------------------- contratos e atas de adesão do órgão (PDFs)

def tem_contrato(arquivos: list[tuple[str, str]]) -> bool:
    titulos = [comum.sem_acento(t).lower() for t, _ in arquivos]
    return any("contrato" in t and "minuta" not in t for t in titulos)


def item_contrato(modalidade: str, ano: int, processo: str, pasta: str, arquivos: list[tuple[str, str]]) -> tuple[str, dict] | None:
    """Processo de contratação (pasta `processo` do ano) com documento de contrato: título e links dos PDFs, sem fornecedor nem valor (o
    portal não os traz). Id `ctr_` da pasta do processo. Sem documento de contrato na pasta: None."""
    if not tem_contrato(arquivos):
        return None
    titulo = f"{modalidade} {processo}/{ano}"
    return comum.item_orgao(FONTE_ID, "contrato", pasta, fornecedor_nome=None, objeto=titulo, numero=f"{processo}/{ano}",
                            arquivos=[pdf_arquivo(t, u) for t, u in arquivos], fonte=PORTAL.format(pasta), modalidade=modalidade, titulo=titulo, ano=ano)


def item_ata_adesao(ano: int, titulo: str, url: str, pasta: str) -> tuple[str, dict]:
    return comum.item_orgao(FONTE_ID, "ata_adesao", id_do_pdf(url), fornecedor_nome=None, objeto=titulo, arquivos=[pdf_arquivo(titulo, url)],
                            fonte=PORTAL.format(pasta), titulo=titulo, ano=ano)


def pdfs_sob(s, pasta: str, profundidade: int = 1) -> list[tuple[str, str]]:
    pastas, arquivos = pasta_do_portal(s, pasta)
    if profundidade:
        for pid, _ in pastas:
            arquivos += pdfs_sob(s, pid, profundidade - 1)
    return arquivos


def coletar_orgao(s, hoje: date) -> None:
    for ano in range(ANO_INICIAL, hoje.year + 1):
        arq = PASTA / f"orgao_{ano}.json"
        if comum.ano_encerrado(ano, hoje, arq):
            continue
        anterior = comum.ler(arq, {})
        itens = dict(anterior.get("itens") or {})
        vistos = dict(anterior.get("vistos") or {})
        lidos = 0
        try:
            for modalidade, raiz in MODALIDADES.items():
                pasta_ano = pasta_do_ano(s, raiz, ano)
                if not pasta_ano:
                    continue
                for pid, nome in pasta_do_portal(s, pasta_ano)[0]:
                    ultima = vistos.get(pid)
                    if ultima and (hoje - date.fromisoformat(ultima)).days < RELER_PROCESSO_DIAS + zlib.crc32(pid.encode()) % RELER_PROCESSO_DIAS:
                        continue
                    achado = item_contrato(modalidade, ano, nome, pid, pdfs_sob(s, pid, 0))
                    if achado:
                        itens[achado[0]] = achado[1]
                    vistos[pid] = hoje.isoformat()
                    lidos += 1
            pasta_adesao = pasta_do_ano(s, ATAS_ADESAO, ano)
            if pasta_adesao:
                for titulo, url in pdfs_sob(s, pasta_adesao, 1):
                    k, item = item_ata_adesao(ano, titulo, url, pasta_adesao)
                    itens[k] = item
        finally:
            if itens or arq.exists():
                comum.salvar(arq, {"coletadoEm": hoje.isoformat(), "fonte": PORTAL.format(52), "vistos": vistos, "itens": itens})
        contratos = sum(i["tipo"] == "contrato" for i in itens.values())
        print(f"MS: órgão {ano}: {lidos} processos lidos agora; {contratos} contratos e {len(itens) - contratos} atas de adesão no arquivo (só título e link)")


# ---------------------------------------------------------------- regras da verba

def coletar_regras(s) -> None:
    documentos = [{"titulo": "Cota para o Exercício da Atividade Parlamentar (CEAP): explicação no Portal da Transparência", "url": CEAP_PAGINA,
                   "ano": None, "atualizadoEm": None}]
    documentos += [{"titulo": titulo, "url": url, "ano": None, "atualizadoEm": None} for titulo, url in pasta_do_portal(s, REGRAS_PASTA)[1]]
    if len(documentos) < 2:
        raise RuntimeError("nenhum ato da CEAP na pasta de regulamentação; mantém o arquivo anterior")
    comum.salvar(PASTA / "regras_ressarcimento.json", {"url": documentos[1]["url"], "ano": None, "titulo": documentos[1]["titulo"],
                                                       "fonte": PORTAL.format(REGRAS_PASTA), "documentos": documentos})
    print(f"MS: regras da verba: {len(documentos)} documentos")


def coletar() -> None:
    s = comum.sessao()
    deputados = deputados_do_tse()
    if not deputados:
        comum.avisar("MS: sem eleitos de 2022 em dados/tse/2022/MS.json")
        return
    comum.salvar(PASTA / "deputados.json", {"fonte": "https://divulgacandcontas.tse.jus.br/divulga/#/home", "host": None,
                                            "legislatura": "2023-2027", "deputados": deputados})
    print(f"MS: {len(deputados)} deputados")
    hoje = date.today()
    comum.rodar_etapas(UF, [("CEAP", lambda: coletar_ceap(s, deputados)), ("diárias", lambda: coletar_diarias(s)),
                            ("pautas", lambda: coletar_pautas(s, deputados)), ("atas", lambda: coletar_atas(s, hoje)),
                            ("remuneração", lambda: coletar_remuneracao(s, deputados, hoje)), ("órgão", lambda: coletar_orgao(s, hoje)),
                            ("regras da verba", lambda: coletar_regras(s))])


def _contrato_ceap(ctx):
    texto = baixar(comum.sessao(), CEAP_CSV.format(ano=date.today().year))
    return {"csv": "\n".join(texto.splitlines()[:12])}


def _conferir_ceap(registro):
    linhas = linhas_csv(registro["csv"], "DEPUTADO")
    if not linhas:
        return ["CSV da CEAP sem cabeçalho Deputado ou sem linhas"], []
    falhas = []
    falhas += comum.faltando(linhas[0], ("ANO", "MES", "CATEGORIA", "CPF/CNPJ", "FORNECEDOR", "DOCUMENTO", "EMISSAO", "VALOR (R$)", "COMPROVANTE"), "CSV da CEAP")
    if comum.valor_br(linhas[0].get("VALOR (R$)")) is None:
        falhas.append("valor da CEAP ilegível")
    if comum.mes_numero(linhas[0].get("MES")) is None:
        falhas.append("mês da CEAP não reconhecido")
    return falhas, []


def _contrato_diarias(ctx):
    texto = baixar(comum.sessao(), DIARIAS_CSV.format(ano=date.today().year))
    return {"csv": "\n".join(texto.splitlines()[:8])}


def _conferir_diarias(registro):
    linhas = linhas_csv(registro["csv"], "MES")
    if not linhas:
        return ["CSV de diárias sem cabeçalho Mês ou sem linhas"], []
    return [], []


def _recorte_pagina(html: str) -> str:
    return html.rsplit("<hr />", 1)[-1][:7000]


def _contrato_pauta(ctx):
    return {"html": _recorte_pagina(baixar_html(comum.sessao(), PAUTA_PAGINA))}


def _contrato_ordem(ctx):
    return {"html": _recorte_pagina(baixar_html(comum.sessao(), ORDEM_PAGINA))}


def _conferir_pagina(registro):
    blocos = ler_pagina(registro.get("html", ""))
    if not blocos:
        return ["nenhum projeto lido da página"], []
    falhas = []
    for p in blocos[0]["processos"]:
        falhas += comum.campos_vazios(p, ("tipo", "numero", "ano", "processo", "autor", "ementa"), p["tipo"], vazios=(None, ""))
    return falhas, []


def _contrato_portal(ctx):
    s = comum.sessao()
    anos = baixar_html(s, PORTAL.format(REMUNERACAO))
    pasta = pasta_do_ano(s, REMUNERACAO, date.today().year)
    meses = baixar_html(s, PORTAL.format(pasta)) if pasta else ""
    return {"anos": anos[anos.find("<tbody>"):][:4000], "meses": meses[meses.find("<tbody>"):][:4000]}


def _conferir_portal(registro):
    anos, meses = ler_pasta(registro.get("anos", "")), ler_pasta(registro.get("meses", ""))
    falhas = []
    if not any(t.strip().isdigit() for _, t in anos[0]):
        falhas.append("pasta da remuneração sem subpastas por ano")
    if not any(comum.mes_numero(t) for t, _ in meses[1]):
        falhas.append("pasta do ano sem PDF mensal")
    return falhas, []


def _contrato_folha(ctx):
    s = comum.sessao()
    arquivos = arquivos_da_folha(s, date.today().year) or arquivos_da_folha(s, date.today().year - 1)
    linhas = texto_do_pdf(comum.baixar(s, arquivos[-1]["url"], timeout=180))
    corte = [i for i, linha in enumerate(linhas) if SUBTOTAL.search(linha)][2] + 1
    return {"texto": "\n".join(linhas[:corte])}


def _conferir_folha(registro):
    referencia, folha, deputados = folha_do_pdf(registro.get("texto", "").split("\n"))
    falhas = []
    if not referencia or "deputado" not in (folha or "").lower():
        falhas.append("cabeçalho da folha sem referência ou sem a folha de deputado estadual")
    if not deputados or not all(d["ok"] for d in deputados):
        falhas.append("folha sem deputado ou com conta que não fecha")
    return falhas, []


CONTRATOS = [
    {"nome": "estadual_ms_ceap", "fonte": CEAP_PAGINA, "buscar": _contrato_ceap, "html": _conferir_ceap},
    {"nome": "estadual_ms_diarias", "fonte": DIARIAS_PAGINA, "buscar": _contrato_diarias, "html": _conferir_diarias},
    {"nome": "estadual_ms_pauta", "fonte": PAUTA_PAGINA, "buscar": _contrato_pauta, "html": _conferir_pagina},
    {"nome": "estadual_ms_ordem_do_dia", "fonte": ORDEM_PAGINA, "buscar": _contrato_ordem, "html": _conferir_pagina},
    {"nome": "estadual_ms_portal", "fonte": PORTAL.format(REMUNERACAO), "buscar": _contrato_portal, "html": _conferir_portal},
    {"nome": "estadual_ms_folha", "fonte": PORTAL.format(REMUNERACAO), "buscar": _contrato_folha, "html": _conferir_folha},
]


if __name__ == "__main__":
    comum.principal(coletar)
