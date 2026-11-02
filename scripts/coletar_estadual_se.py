"""
Deputados estaduais de Sergipe (Alese), fora do SAPL.

Fonte aberta e lida aqui:
  - deputados (nome, partido, foto, link da ficha no Alese Legis): carrossel da página inicial https://al.se.leg.br/ ;
    a Alese não publica nome civil nem e-mail nessa página: o nome civil vem dos eleitos de 2022 do TSE (dados/tse/2022/SE.json)
    quando um só nome casa;
  - portal da transparência (WordPress + Download Manager): `GET /wp-json/wp/v2/pages?slug=<slug>` devolve a página com as abas
    Ano > Mês e, em cada mês, `data-downloadurl=".../download/<slug>/?wpdmdl=<ID>"`, que entrega o PDF (texto, sem OCR) sem login nem
    captcha. O mês de cada PDF é o da aba e é conferido com o cabeçalho do PDF (diferente: o PDF é descartado com aviso). Leitura com `pypdf`:
      ressarcimento-dos-deputados  um PDF por mês: deputado, inciso do art. 4º (rótulo da fonte), valor, e o total do deputado, que tem
                                   de fechar com a soma dos itens (senão o bloco é descartado); sem fornecedor, CNPJ nem nota;
      subsidio-e-remuneracoes      folha completa do mês (só 2025 em diante: 2023 e 2024 têm outro layout de PDF): dos deputados (cargo "Deputado") ficam bruto, descontos e líquido; os valores
                                   por coluna (subsídio, verbas, auxílios) não são gravados porque a ordem das colunas no texto do PDF
                                   não é confiável; do último mês publicado sai o gabinete (lotação "GABINETE DO DEPUTADO <nome>", id
                                   `srv_` da matrícula, sem valores);
      contratos                    lista de PDFs por ano (830 itens): só título e link (fornecedor, valor e vigência estão dentro do PDF
                                   e o título é livre; não são lidos). Ata de registro de preços: título com "Registro de Preços".

Não coletado:
  - Alese Legis (https://aleselegis.al.se.leg.br: fichas, proposições, normas, votações, presença, pautas, atas) não respondeu em duas
    tentativas (conexão recusada/timeout) e não tem outro endereço; a página "Atas das sessões" do portal é um iframe do webmail;
  - diárias (slug `diarias`): o PDF quebra cada registro em várias linhas e colunas desalinhadas; sem leitura por coordenadas não há
    confiança suficiente (erro viraria dado errado sobre político), então ficam de fora;
  - emendas parlamentares: página aponta para um painel Power BI do Executivo.
"""

import re
import time
from datetime import date
from functools import partial
from html import unescape
from io import BytesIO

import estaduais_comum as comum
import identidades
import ids

UF = "SE"
HOME = "https://al.se.leg.br/"
FICHA = "https://aleselegis.al.se.leg.br/spl/parlamentar.aspx?id={}"
TSE_ARQUIVO = comum.arquivo_tse(UF)
API_PAGINAS = HOME + "wp-json/wp/v2/pages?slug={}"
PAGINA = HOME + "portal-da-transparencia/"
PAGINAS = {"ressarcimento": ("ressarcimento-dos-deputados", PAGINA + "despesas/ressarcimento-dos-deputados/"),
           "folha": ("subsidio-e-remuneracoes", PAGINA + "recursos-humanos/subsidio-e-remuneracoes/"),
           "contratos": ("contratos", PAGINA + "contratos/")}
PDF = HOME + "download/{}/?wpdmdl={}"
FONTE_ID = "alese_se"
PRIMEIRO_ANO = 2023
PRIMEIRO_ANO_FOLHA = 2025   # a folha de 2023 e 2024 usa outro layout de PDF (matrícula de 5 dígitos, sem lotação em uma linha)
MESES_RECENTES = 2
RENOVAR_COMPLETA_DIAS = 14
PAUSA = 1.0
ligar = partial(identidades.ligar_nomes, uf=UF)
NUM = r"\d{1,3}(?:\.\d{3})*,\d\d"


def deputados_da_pagina(html: str) -> list[dict]:
    """Deputados do carrossel da página inicial (o carrossel repete cartões; vale um por id do Alese Legis)."""
    achados = {}
    for cartao in re.findall(r'<article class="qodef-portfolio-item.*?</article>', html, re.S):
        ident = re.search(r"parlamentar\.aspx\?id=(\d+)", cartao)
        titulo = re.search(r'<h4 class="qodef-item-title">(.*?)</h4>', cartao, re.S)
        if not ident or not titulo or not comum.limpar(titulo.group(1)):
            continue
        partido = re.search(r'qodef-ptf-category-holder"><span>(.*?)</span>', cartao, re.S)
        foto = re.search(r'<img[^>]*?\bsrc="([^"]+)"', cartao)
        nome = comum.limpar(titulo.group(1))
        achados.setdefault(ident.group(1), {"id": ident.group(1), "nome": nome, "nomeCivil": nome, "foto": unescape(foto.group(1)) if foto else None,
                                            "email": None, "titular": True, "partido": comum.sigla_partido(comum.limpar(partido.group(1))) if partido else None,
                                            "fonte": FICHA.format(ident.group(1))})
    return sorted(achados.values(), key=lambda d: comum.sem_acento(d["nome"]))


def completar_com_tse(deputados: list[dict], eleitos: list[dict]) -> None:
    """Preenche `nomeCivil` com o nome do TSE quando um só eleito de 2022 casa com o nome da Alese (a Alese não publica o nome civil)."""
    for d in deputados:
        achado = identidades.eleito_do_tse(UF, d["nome"], eleitos)
        if achado:
            d["nomeCivil"] = achado["nome"]


def eleitos_do_tse() -> list[dict]:
    return comum.eleitos_tse(TSE_ARQUIVO)


def titulo(nome: str) -> str:
    pequenas = {"de", "da", "do", "das", "dos", "e"}
    return " ".join(p if (i and p in pequenas) else p.capitalize() for i, p in enumerate((nome or "").lower().split()))


def chave_sem_espaco(nome: str) -> str:
    return comum.sem_acento(nome).replace(" ", "")


def reparar_nome(nome: str, deputados: list[dict]) -> str:
    """O PDF da folha parte palavras ("CA VALCANTE", "BA TALHA"): quando o nome sem espaços é igual ao de um só deputado (nome ou nome
    civil), vale o nome do deputado; senão o nome como veio."""
    alvo = chave_sem_espaco(nome)
    achados = {d["nome"] for d in deputados for c in ("nome", "nomeCivil") if d.get(c) and chave_sem_espaco(d[c]) == alvo}
    return achados.pop() if len(achados) == 1 else nome


# ---------------------------------------------------------------- páginas do portal e PDFs

def arquivos_da_pagina(html: str) -> list[dict]:
    """[{ano, mes, id, slug}] na ordem da página: o ano vem do título da seção e o mês do rótulo da aba, antes de cada link de download.
    A ordem dos links dentro do ano não vale (há meses fora de lugar): vale o rótulo da aba."""
    ano = mes = None
    achados = []
    padrao = (r'elementor-heading-title[^>]*>\s*(\d{4})\s*<|elementor-tab-mobile-title[^>]*>\s*([^\W\d_]+)'
              r'|data-downloadurl="[^"]*?/download/([^/"]+)/\?wpdmdl=(\d+)')
    for m in re.finditer(padrao, html):
        if m.group(1):
            ano, mes = int(m.group(1)), None
        elif m.group(2):
            mes = comum.mes_numero(m.group(2))
        elif ano and mes:
            achados.append({"ano": ano, "mes": mes, "id": m.group(4), "slug": m.group(3)})
    return achados


def buscar_pagina(s, slug: str) -> tuple[str, str | None]:
    """(HTML da página, data de modificação) de `wp-json/wp/v2/pages?slug=`."""
    r = comum.get(s, API_PAGINAS.format(slug), timeout=90)
    paginas = r.json()
    if not paginas:
        raise RuntimeError(f"página {slug} não existe mais no portal")
    return paginas[0]["content"]["rendered"], paginas[0].get("modified")


def texto_do_pdf(conteudo: bytes) -> list[str]:
    """Linhas de texto do PDF (todas as páginas), com `pypdf`."""
    from pypdf import PdfReader
    linhas = []
    for pagina in PdfReader(BytesIO(conteudo)).pages:
        linhas += (pagina.extract_text() or "").split("\n")
    return linhas


def baixar_pdf(s, arquivo: dict) -> list[str]:
    time.sleep(PAUSA)
    return texto_do_pdf(comum.baixar(s, url_pdf(arquivo), timeout=180))


def url_pdf(arquivo: dict) -> str:
    return PDF.format(arquivo["slug"], arquivo["id"])


# ---------------------------------------------------------------- ressarcimento (verba indenizatória)

def _ano_mes(texto: str) -> tuple[int, int] | None:
    m = re.search(r"(\d\d)/(\d{4})", texto)
    return (int(m.group(2)), int(m.group(1))) if m else None


def blocos_ressarcimento(linhas: list[str]) -> tuple[tuple[int, int] | None, list[dict]]:
    """((ano, mês) de pagamento do cabeçalho, [{deputado, competencia, itens: [(rótulo, valor)], total}]). O bloco do deputado fecha no
    "Total:"; bloco sem total ou com soma diferente do total é descartado (não vira dado)."""
    pagamento, blocos, atual = None, [], None
    for linha in (l.strip() for l in linhas):
        if linha.startswith("Mês/Ano de Pagamento"):
            pagamento = _ano_mes(linha)
        elif linha.startswith("Deputado:"):
            nome = comum.compactar(linha.split(":", 1)[1])
            if atual and atual["deputado"] == nome:
                continue
            atual = {"deputado": nome, "competencia": None, "itens": [], "total": None}
            blocos.append(atual)
        elif atual is not None and linha.startswith("Competência:"):
            atual["competencia"] = _ano_mes(linha)
        elif atual is not None and (m := re.match(r"^\d+\s+(Art\..*?)\s+(?:R\$\s*)?(" + NUM + r")$", linha)):
            atual["itens"].append((comum.compactar(m.group(1)), comum.valor_br(m.group(2))))
        elif atual is not None and (m := re.match(r"^Total:\s*(?:R\$\s*)?(" + NUM + r")$", linha)):
            atual["total"] = comum.valor_br(m.group(1))
            atual = None
    validos = []
    for b in blocos:
        if b["total"] is None or not b["itens"] or abs(sum(v for _, v in b["itens"]) - b["total"]) > 0.01:
            comum.avisar(f"SE: ressarcimento de {b['deputado']} descartado (itens não fecham com o total)")
        else:
            validos.append(b)
    return pagamento, validos


def itens_ressarcimento(linhas: list[str], arquivo: dict, deputados: list[dict]) -> list[dict]:
    pagamento, blocos = blocos_ressarcimento(linhas)
    if pagamento != (arquivo["ano"], arquivo["mes"]):
        raise RuntimeError(f"PDF {arquivo['id']} é do pagamento {pagamento}, a aba diz {arquivo['ano']}-{arquivo['mes']:02d}")
    ligados = ligar({b["deputado"] for b in blocos}, deputados)
    itens = []
    for b in blocos:
        if b["deputado"] not in ligados:
            continue
        competencia = f"{b['competencia'][0]}-{b['competencia'][1]:02d}" if b["competencia"] else None
        for rotulo, valor in b["itens"]:
            itens.append({"idDeputado": ligados[b["deputado"]], "mes": arquivo["mes"], "competencia": competencia, "categoria": rotulo,
                          "valor": valor, "fornecedor": None, "cnpj": None, "pdf": arquivo["id"], "fonte": url_pdf(arquivo)})
    return itens


# ---------------------------------------------------------------- folha de pagamento (remuneração e gabinete)

REGISTRO_FOLHA = re.compile(r"^(\d{6}) (.+?) (?:" + NUM + r"\s*)+?(\d\d/\d\d/\d{4}) (.*?) ((?:" + NUM + r" ?)+)(.*)$")
FIM_DE_PAGINA = ("Página", "DETALHAMENTO")


def registros_da_folha(linhas: list[str]) -> list[str]:
    """Um texto por servidor: a linha da matrícula (6 dígitos) e, quando a lotação quebrou em outras linhas, as seguintes até os valores."""
    registros = []
    for linha in linhas:
        if re.match(r"^\d{6} ", linha):
            registros.append(linha)
        elif registros and not linha.startswith(FIM_DE_PAGINA) and not REGISTRO_FOLHA.match(registros[-1]):
            registros[-1] = f"{registros[-1]} {linha.strip()}"
    return registros


def servidores_da_folha(linhas: list[str]) -> tuple[tuple[int, int] | None, list[dict]]:
    """((ano, mês) do cabeçalho, [servidor]). Do texto só entram o que é confiável: matrícula, nome, admissão, lotação, cargo e as três
    últimas colunas (rendimentos, descontos, líquido), conferidas por rendimentos - descontos = líquido."""
    texto = " ".join(linhas[:40])
    cab = re.search(r"([A-ZÇ]+)/(\d{4})", texto)
    mes = comum.mes_numero(cab.group(1)) if cab else None
    referencia = (int(cab.group(2)), mes) if cab and mes else None
    servidores = []
    for reg in registros_da_folha(linhas):
        m = REGISTRO_FOLHA.match(reg)
        if not m:
            continue
        valores = [comum.valor_br(v) for v in re.findall(NUM, m.group(5))]
        if len(valores) < 5 or abs(valores[-5] - valores[-2] - valores[-1]) > 0.02:
            continue
        servidores.append({"matricula": m.group(1), "nome": comum.compactar(m.group(2)), "admissao": comum.data_br_iso(m.group(3)),
                           "lotacao": comum.compactar(m.group(4)), "cargo": comum.compactar(m.group(6)), "bruto": valores[-5],
                           "descontos": valores[-2], "liquido": valores[-1]})
    return referencia, servidores


def nome_da_lotacao(lotacao: str | None) -> str | None:
    m = re.match(r"^GABINETE D[OA] DEPUTAD[OA]\s+(.+)$", lotacao or "")
    return comum.compactar(m.group(1)) if m else None


def eh_deputado(servidor: dict) -> bool:
    return (servidor["cargo"] or "").lower() in ("deputado", "deputada")


def itens_remuneracao(servidores: list[dict], arquivo: dict, deputados: list[dict]) -> list[dict]:
    """Folha dos deputados (cargo "Deputado"), ligados pelo nome civil; sem ligação pelo nome, tenta o nome da lotação do gabinete."""
    meus = [s for s in servidores if eh_deputado(s)]
    nomes = {s["matricula"]: reparar_nome(s["nome"], deputados) for s in meus}
    lotacoes = {s["matricula"]: reparar_nome(nome_da_lotacao(s["lotacao"]) or "", deputados) for s in meus}
    ligados = ligar(set(nomes.values()) | {n for n in lotacoes.values() if n}, deputados)
    itens = []
    for s in meus:
        id_dep = ligados.get(nomes[s["matricula"]]) or ligados.get(lotacoes[s["matricula"]])
        if id_dep:
            itens.append({"idDeputado": id_dep, "mes": arquivo["mes"], "bruto": s["bruto"], "liquido": s["liquido"],
                          "componentes": {"descontos": s["descontos"]}, "matricula": s["matricula"], "pdf": arquivo["id"],
                          "fonte": url_pdf(arquivo)})
    return sorted(itens, key=lambda i: (i["idDeputado"], i["mes"]))


def servidores_do_gabinete(servidores: list[dict], deputados: list[dict]) -> list[dict]:
    """Servidores (menos o próprio deputado) com lotação "GABINETE DO(A) DEPUTADO(A) <nome>" ligada a um só deputado. Id `srv_` da
    matrícula; sem valores."""
    nomes = {s["lotacao"]: reparar_nome(nome_da_lotacao(s["lotacao"]), deputados) for s in servidores if nome_da_lotacao(s["lotacao"])}
    ligados = ligar(set(nomes.values()), deputados)
    itens = {}
    for s in servidores:
        id_dep = ligados.get(nomes.get(s["lotacao"]))
        if not id_dep or eh_deputado(s):
            continue
        iid = ids.gerar_id("srv", FONTE_ID, s["matricula"])
        itens[iid] = {"id": iid, "idDeputado": id_dep, "matricula": s["matricula"], "nome": titulo(s["nome"]), "cargo": s["cargo"],
                      "simbolo": s["cargo"], "admissao": s["admissao"]}
    return sorted(itens.values(), key=lambda i: (i["idDeputado"], i["simbolo"] or "", i["nome"], i["matricula"]))


# ---------------------------------------------------------------- um arquivo por ano, só os PDFs novos

def pdfs_do_ano(s, pasta, prefixo: str, ano: int, arquivos: list[dict], hoje: date, fonte: str, ler_pdf, forcar=()) -> None:
    """Grava `<prefixo>_<ano>.json` com os itens de cada PDF do ano. Ano encerrado com arquivo não é baixado. PDF já lido (id guardado em
    `pdfs`) só volta a ser lido nos meses recentes e só quando a completa tem mais de RENOVAR_COMPLETA_DIAS; `forcar`: ids lidos sempre.
    `ler_pdf(arquivo, linhas)` devolve os itens. Prazo esgotado grava o que leu antes de parar."""
    arq = pasta / f"{prefixo}_{ano}.json"
    if comum.ano_encerrado(ano, hoje, arq):
        return
    anterior = comum.ler(arq, {})
    completa_em = anterior.get("completaEm")
    completa_velha = not completa_em or (hoje - date.fromisoformat(completa_em)).days >= RENOVAR_COMPLETA_DIAS
    recentes = comum.meses_recentes(hoje, MESES_RECENTES)
    lidos = dict(anterior.get("pdfs") or {})
    itens = list(anterior.get("itens") or [])
    novos = falhas = 0
    interrompido = None
    for a in sorted((x for x in arquivos if x["ano"] == ano), key=lambda x: (x["mes"], x["id"])):
        if a["id"] in lidos and a["id"] not in forcar and not (completa_velha and (ano, a["mes"]) in recentes):
            continue
        try:
            achados = ler_pdf(a, baixar_pdf(s, a))
        except comum.PrazoEsgotado as e:
            interrompido = e
            break
        except Exception as e:  # noqa: BLE001
            falhas += 1
            comum.avisar(f"SE: {prefixo} {ano}-{a['mes']:02d} (PDF {a['id']}): {e}")
            continue
        itens = [i for i in itens if i.get("pdf") != a["id"]] + achados
        lidos[a["id"]] = a["mes"]
        novos += 1
    if novos or not arq.exists():
        completa = hoje.isoformat() if completa_velha and not falhas and not interrompido else completa_em
        comum.salvar(arq, {"coletadoEm": hoje.isoformat(), "completaEm": completa, "fonte": fonte, "pdfs": lidos,
                           "itens": sorted(itens, key=lambda i: (i["mes"], i["idDeputado"], i.get("categoria") or "", i.get("matricula") or ""))})
    print(f"SE: {prefixo} {ano}: {novos} PDFs lidos, {len(lidos)} no arquivo ({falhas} falhas)")
    if interrompido:
        raise interrompido


def coletar_ressarcimento(s, pasta, deputados: list[dict], hoje: date) -> None:
    slug, fonte = PAGINAS["ressarcimento"]
    arquivos = arquivos_da_pagina(buscar_pagina(s, slug)[0])
    if not arquivos:
        raise RuntimeError("nenhum PDF de ressarcimento na página; mantém os arquivos anteriores")
    for ano in range(PRIMEIRO_ANO, hoje.year + 1):
        comum.tentar(UF, f"ressarcimento {ano}", partial(pdfs_do_ano, s, pasta, "verbas", ano, arquivos, hoje, fonte,
                                                         lambda a, linhas: itens_ressarcimento(linhas, a, deputados)))


def coletar_folha(s, pasta, deputados: list[dict], hoje: date) -> None:
    slug, fonte = PAGINAS["folha"]
    arquivos = [a for a in arquivos_da_pagina(buscar_pagina(s, slug)[0]) if a["ano"] >= PRIMEIRO_ANO_FOLHA]
    if not arquivos:
        raise RuntimeError("nenhum PDF da folha na página; mantém os arquivos anteriores")
    ultimo = max(arquivos, key=lambda a: (a["ano"], a["mes"], a["id"]))
    gabinete_arq = pasta / "gabinete.json"
    gabinete_lido = (comum.ler(gabinete_arq, {}) or {}).get("pdf") == ultimo["id"]
    gabinete = {}

    def ler_pdf(a, linhas):
        referencia, servidores = servidores_da_folha(linhas)
        if referencia != (a["ano"], a["mes"]):
            raise RuntimeError(f"PDF {a['id']} é da folha {referencia}, a aba diz {a['ano']}-{a['mes']:02d}")
        if not servidores:
            raise RuntimeError("nenhum servidor lido da folha")
        if a["id"] == ultimo["id"]:
            gabinete["itens"] = servidores_do_gabinete(servidores, deputados)
        return itens_remuneracao(servidores, a, deputados)

    for ano in range(PRIMEIRO_ANO_FOLHA, hoje.year + 1):
        comum.tentar(UF, f"remuneração {ano}", partial(pdfs_do_ano, s, pasta, "remuneracao", ano, arquivos, hoje, fonte, ler_pdf,
                                                       () if gabinete_lido or ano != ultimo["ano"] else (ultimo["id"],)))
    if gabinete.get("itens"):
        comum.salvar(gabinete_arq, {"coletadoEm": hoje.isoformat(), "pdf": ultimo["id"], "referencia": f"{ultimo['ano']}-{ultimo['mes']:02d}",
                                    "fonte": url_pdf(ultimo), "itens": gabinete["itens"]})
        print(f"SE: gabinetes {len(gabinete['itens'])} servidores de {len({i['idDeputado'] for i in gabinete['itens']})} deputados "
              f"({ultimo['ano']}-{ultimo['mes']:02d})")
    elif not gabinete_lido:
        raise RuntimeError("gabinete não lido do último PDF da folha; mantém o arquivo anterior")


# ---------------------------------------------------------------- contratos e atas de registro de preço do órgão

def itens_contratos(html: str, ano: int) -> dict:
    """{id: item} do ano da página de contratos: título e link do PDF (o título é livre; fornecedor e valor ficam dentro do PDF e não
    são lidos). Ata de registro de preços: título com "Registro de Preços"; o resto é contrato (inclui aditivos). Id `ctr_` do
    slug do download, que é o id na fonte."""
    itens = {}
    ano_aba = ultimo = None
    padrao = (r'elementor-heading-title[^>]*>\s*(\d{4})\s*<|package-title"><a href=\'[^\']*/download/([^/\']+)/\'>(.*?)</a>'
              r'|data-downloadurl="[^"]*?/download/([^/"]+)/\?wpdmdl=(\d+)')
    for m in re.finditer(padrao, html, re.S):
        if m.group(1):
            ano_aba = int(m.group(1))
        elif m.group(2):
            ultimo = None
            nome = comum.compactar(unescape(m.group(3)))
            if ano_aba != ano or not nome:
                continue
            ata = "registro de preco" in comum.sem_acento(nome)
            iid, item = comum.item_orgao(FONTE_ID, "ata_registro" if ata else "contrato", m.group(2), fornecedor_nome=None, objeto=nome,
                                         arquivos=[], fonte=PAGINAS["contratos"][1], titulo=nome)
            itens[iid] = item
            ultimo = (iid, m.group(2), nome)
        elif ultimo and ultimo[1] == m.group(4):
            itens[ultimo[0]]["arquivos"] = [{"url": PDF.format(m.group(4), m.group(5)), "nome": ultimo[2], "data": None}]
    return itens


def anos_da_pagina(html: str) -> list[int]:
    return sorted({int(a) for a in re.findall(r'elementor-heading-title[^>]*>\s*(\d{4})\s*<', html)})


def coletar_contratos(s, pasta, hoje: date) -> None:
    html, modificado = buscar_pagina(s, PAGINAS["contratos"][0])
    anos = [a for a in anos_da_pagina(html) if a >= PRIMEIRO_ANO]
    if not anos:
        raise RuntimeError("página de contratos sem anos; mantém os arquivos anteriores")
    for ano in anos:
        arq = pasta / f"orgao_{ano}.json"
        if comum.ano_encerrado(ano, hoje, arq) or (arq.exists() and comum.ler(arq, {}).get("modificadoEm") == modificado):
            continue
        itens = itens_contratos(html, ano)
        if not itens:
            comum.avisar(f"SE: contratos {ano}: nenhum item na página; mantém o arquivo anterior")
            continue
        comum.salvar(arq, {"coletadoEm": hoje.isoformat(), "modificadoEm": modificado, "fonte": PAGINAS["contratos"][1], "itens": itens})
        n_atas = sum(i["tipo"] == "ata_registro" for i in itens.values())
        print(f"SE: {ano} contratos {len(itens) - n_atas} e atas de registro {n_atas} do órgão (só título e link)")


def coletar() -> None:
    pasta = comum.DADOS / UF
    hoje = date.today()
    s = comum.sessao()
    r = s.get(HOME, timeout=30)
    r.raise_for_status()
    deputados = deputados_da_pagina(r.text)
    if not deputados:
        comum.avisar("SE: nenhum deputado na página inicial da Alese")
        return
    completar_com_tse(deputados, eleitos_do_tse())
    comum.salvar(pasta / "deputados.json", {"fonte": HOME, "host": None, "legislatura": "2023-2027", "deputados": deputados})
    print(f"SE: {len(deputados)} deputados")
    comum.rodar_etapas(UF, [("ressarcimento", lambda: coletar_ressarcimento(s, pasta, deputados, hoje)),
                            ("remuneração e gabinete", lambda: coletar_folha(s, pasta, deputados, hoje)),
                            ("contratos e atas de registro do órgão", lambda: coletar_contratos(s, pasta, hoje))])


def _contrato_deputados(ctx):
    r = comum.sessao().get(HOME, timeout=30)
    r.raise_for_status()
    return {"trecho": "\n".join(re.findall(r'<article class="qodef-portfolio-item.*?</article>', r.text, re.S)[:3])}


def _conferir_deputados(registro):
    falhas = []
    deputados = deputados_da_pagina(registro["trecho"])
    if not deputados:
        falhas.append("página inicial sem cartões de deputado (link do Alese Legis + nome)")
    for d in deputados:
        if not d["partido"]:
            falhas.append(f"cartão sem partido: {d['nome']}")
        if not d["foto"]:
            falhas.append(f"cartão sem foto: {d['nome']}")
    return falhas, []


def _trecho_pagina(html: str, n: int) -> str:
    """Da primeira seção de ano até o n-ésimo link de download (com as abas dos meses no meio)."""
    inicio = html.rfind("<", 0, html.find("elementor-heading-title"))
    fim = 0
    for _ in range(n):
        fim = html.find("</a>", html.find("data-downloadurl", fim)) + 4
    return html[inicio:fim]


def _contrato_ressarcimento(ctx):
    s = comum.sessao()
    html = buscar_pagina(s, PAGINAS["ressarcimento"][0])[0]
    trecho = _trecho_pagina(html, 2)
    return {"html": trecho, "linhas": baixar_pdf(s, arquivos_da_pagina(html)[0])[:40]}


def _conferir_ressarcimento(registro):
    falhas = []
    arquivos = arquivos_da_pagina(registro["html"])
    if not arquivos:
        falhas.append("página do ressarcimento sem ano, aba de mês e link wpdmdl")
    pagamento, blocos = blocos_ressarcimento(registro["linhas"])
    if not pagamento or not blocos:
        falhas.append("PDF do ressarcimento sem 'Mês/Ano de Pagamento' ou sem bloco de deputado que feche com o total")
    for b in blocos:
        falhas += comum.campos_vazios(b, ("deputado", "competencia", "total"), "bloco de ressarcimento")
    return falhas, []


def _contrato_folha(ctx):
    s = comum.sessao()
    html = buscar_pagina(s, PAGINAS["folha"][0])[0]
    linhas = baixar_pdf(s, arquivos_da_pagina(html)[0])
    registros = [l for l in linhas if re.match(r"^\d{6} ", l)]
    deputados = [l for l in registros if l.endswith("Deputado") or l.endswith("Deputada")][:2]
    gabinete = [l for l in registros if "GABINETE DO DEPUTADO" in l and not l.endswith(("Deputado", "Deputada"))][:2]
    return {"html": _trecho_pagina(html, 2), "linhas": linhas[:36] + deputados + gabinete}


def _conferir_folha(registro):
    falhas = []
    if not arquivos_da_pagina(registro["html"]):
        falhas.append("página da folha sem ano, aba de mês e link wpdmdl")
    referencia, servidores = servidores_da_folha(registro["linhas"])
    if not referencia:
        falhas.append("PDF da folha sem 'MÊS/ANO' no cabeçalho")
    if not any(eh_deputado(s) for s in servidores):
        falhas.append("PDF da folha sem servidor de cargo 'Deputado' legível")
    if not any(nome_da_lotacao(s["lotacao"]) and not eh_deputado(s) for s in servidores):
        falhas.append("PDF da folha sem servidor lotado em 'GABINETE DO DEPUTADO'")
    for s in servidores:
        falhas += comum.campos_vazios(s, ("matricula", "nome", "admissao", "lotacao", "cargo", "bruto", "liquido"), "servidor da folha")
    return falhas, []


def _contrato_contratos(ctx):
    html = buscar_pagina(comum.sessao(), PAGINAS["contratos"][0])[0]
    return {"html": _trecho_pagina(html, 3)}


def _conferir_contratos(registro):
    falhas = []
    anos = anos_da_pagina(registro["html"])
    itens = itens_contratos(registro["html"], anos[0]) if anos else {}
    if not itens:
        falhas.append("página de contratos sem item (título e link de download)")
    if not all(i["arquivos"] for i in itens.values()):
        falhas.append("item de contrato sem link wpdmdl")
    return falhas, []


CONTRATOS = [
    {"nome": "estadual_se_deputados", "fonte": HOME, "buscar": _contrato_deputados, "html": _conferir_deputados},
    {"nome": "estadual_se_ressarcimento", "fonte": PAGINAS["ressarcimento"][1], "buscar": _contrato_ressarcimento, "html": _conferir_ressarcimento},
    {"nome": "estadual_se_folha", "fonte": PAGINAS["folha"][1], "buscar": _contrato_folha, "html": _conferir_folha},
    {"nome": "estadual_se_contratos", "fonte": PAGINAS["contratos"][1], "buscar": _contrato_contratos, "html": _conferir_contratos},
]


if __name__ == "__main__":
    comum.principal(coletar)
