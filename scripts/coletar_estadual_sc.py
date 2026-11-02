"""
Deputados estaduais de Santa Catarina (ALESC), fora do SAPL.

Fontes lidas aqui (abertas, sem login):
  - deputados em exercício e remuneração mensal: https://transparencia.alesc.sc.gov.br/deputados?ano=&mes=
    (tabela com o nome civil; o contracheque de cada um vem de /deputados/contracheque/<id>?ano=&mes=, resposta HTMX);
    partido e nome de urna vêm dos eleitos de 2022 do TSE (dados/tse/2022/SC.json) quando o nome civil casa;
  - gabinetes parlamentares (cota de exercício parlamentar), CSV por ano: /gabinetes-parlamentares/csv/<ano>
  - diárias e passagens, CSV por ano (só linhas com vínculo "Deputado"): /diarias/csv/<ano>
  - presença em sessões plenárias, uma página por sessão: https://portalelegis.alesc.sc.gov.br/sessoes-plenarias/<codigo>/presenca
  - proposições do processo legislativo (autoria por nome): https://portalelegis.alesc.sc.gov.br/proposicoes/processo-legislativo,
    10 por página; os filtros `inicio`/`fim` (data de abertura) dão a leitura incremental; de autoria do governador vão para
    governo_<ano>.json
  - gabinete (servidores por vínculo, sem valores): https://transparencia.alesc.sc.gov.br/servidores?setor_id=<id>, um setor
    "GAB DEP <nome>" por deputado
  - contratos e atas de registro de preço do órgão (cards HTML, 20 por página): https://transparencia.alesc.sc.gov.br/contratos?ano_vigencia=
  - regras da cota de gabinete: seção "Gabinetes Parlamentares" de https://leis.alesc.sc.gov.br/alesc/regulamentacao-interna

Não coletado: votações (as sessões amostradas só têm votação simbólica), presença em comissões, normas com autoria (a busca de
leis não exporta; a autoria vem da proposição).
"""

import csv
import io
import re
from datetime import date, timedelta
from html import unescape
from functools import partial

import estaduais_comum as comum
import identidades

UF = "SC"
TRANSPARENCIA = "https://transparencia.alesc.sc.gov.br"
ELEGIS = "https://portalelegis.alesc.sc.gov.br"
TSE_ARQUIVO = comum.arquivo_tse(UF)
DEPUTADOS_URL = f"{TRANSPARENCIA}/deputados"
GABINETES_PAGINA = f"{TRANSPARENCIA}/gabinetes-parlamentares"
DIARIAS_PAGINA = f"{TRANSPARENCIA}/diarias"
SESSOES_URL = f"{ELEGIS}/sessoes-plenarias"
CABECALHO_AJAX = {"X-Requested-With": "XMLHttpRequest"}
PROPOSICOES_URL = f"{ELEGIS}/proposicoes/processo-legislativo"
SERVIDORES_URL = f"{TRANSPARENCIA}/servidores"
CONTRATOS_URL = f"{TRANSPARENCIA}/contratos"
REGRAS_URL = "https://leis.alesc.sc.gov.br/alesc/regulamentacao-interna"
LEIS = "https://leis.alesc.sc.gov.br"
FONTE_ID = "alesc_sc"
SETOR_GABINETE = re.compile(r"^\s*GAB\.?\s*DEP\.?\s+(.+)$", re.I)
GABINETE_DIAS = 7   # ~130 páginas (um setor por deputado): relido uma vez por semana
RENOVAR_COMPLETA_DIAS = 14   # cada ano de proposições é relido inteiro nesta frequência (um ano por coleta), pela situação
FOLGA_DIAS = 1
PRIMEIRO_ANO = 2023
ANOS_REMUNERACAO = 2
MESES_RECENTES = 2
ligar = partial(identidades.ligar_nomes, uf=UF)


def mes_anterior(ano: int, mes: int) -> tuple[int, int]:
    return (ano - 1, 12) if mes == 1 else (ano, mes - 1)


# ---------------------------------------------------------------- deputados

def parse_deputados(html: str) -> list[dict]:
    """[{nomeCivil, idContracheque}] da tabela de subsídios."""
    achados = []
    for nome, ident in re.findall(r'<td class="fw-semibold">(.*?)</td>.*?/deputados/contracheque/(\d+)\?', html, re.S):
        achados.append({"nomeCivil": comum.limpar(nome), "idContracheque": ident})
    return achados


def deputados_com_tse(lista: list[dict]) -> list[dict]:
    """O nome civil da fonte casa com o do TSE por palavras; o casado leva nome de urna, nome do TSE e partido."""
    eleitos = comum.eleitos_tse(TSE_ARQUIVO)
    saida = []
    for d in lista:
        e = identidades.eleito_do_tse(UF, d["nomeCivil"], eleitos)
        saida.append({"id": d["idContracheque"], "nome": e["urna"] if e and e.get("urna") else d["nomeCivil"].title(),
                      "nomeCivil": e["nome"] if e else d["nomeCivil"].title(), "nomeFonte": d["nomeCivil"].title(), "foto": None,
                      "email": comum.email(e.get("email")) if e else None, "titular": True, "partido": comum.sigla_partido(e.get("partido")) if e else None, "fonte": DEPUTADOS_URL})
    return sorted(saida, key=lambda d: comum.sem_acento(d["nome"]))


# ---------------------------------------------------------------- remuneração (contracheque)

def parse_contracheque(html: str) -> dict:
    """{bruto, liquido, componentes:{nome: valor}}; descontos saem negativos."""
    componentes = {}
    for nome, valor in re.findall(r'<tr><td>([^<]+)</td><td class="text-end[^"]*">([^<]+)</td>', html):
        v = comum.valor_br(valor)
        if v is not None:
            componentes[unescape(nome).strip()] = v
    bruto = re.search(r"BRUTO</td>\s*<td[^>]*>\s*(R\$[^<]+)<", html)
    liquido = re.search(r"L.QUIDO</td>\s*<td[^>]*>\s*(R\$[^<]+)<", html)
    return {"bruto": comum.valor_br(bruto.group(1)) if bruto else None, "liquido": comum.valor_br(liquido.group(1)) if liquido else None,
            "componentes": componentes}


def itens_remuneracao(contracheques: dict, mes: int, ano: int) -> list[dict]:
    pagina = f"{DEPUTADOS_URL}?ano={ano}&mes={mes}"
    return [{"idDeputado": ident, "mes": mes, **c, "fonte": pagina} for ident, c in contracheques.items()]


# ---------------------------------------------------------------- CSV (gabinetes e diárias)

def ler_csv(texto: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(texto.lstrip("﻿")), delimiter=";"))


def itens_gabinetes(linhas: list[dict], deputados: list[dict]) -> list[dict]:
    ligados = ligar({linha["Conta"] for linha in linhas if linha.get("Conta")}, deputados)
    itens = []
    for linha in linhas:
        did, data = ligados.get(linha.get("Conta")), comum.data_br_iso(linha.get("Data de Referência"))
        if did is None or data is None:
            continue
        categoria = " / ".join(x for x in (linha.get("Verba"), linha.get("Descrição")) if x)
        itens.append({"idDeputado": did, "mes": int(data[5:7]), "categoria": categoria, "fornecedor": comum.compactar(linha.get("Favorecido")), "cnpj": None,
                      "valor": comum.valor_br(linha.get("Valor")), "data": data, "trecho": linha.get("Trecho") or None, "fonte": GABINETES_PAGINA})
    return itens


def itens_diarias(linhas: list[dict], deputados: list[dict]) -> list[dict]:
    so_deputados = [linha for linha in linhas if linha.get("Vínculo") == "Deputado"]
    ligados = ligar({linha["Nome"] for linha in so_deputados}, deputados)
    itens = []
    for linha in so_deputados:
        did, data = ligados.get(linha["Nome"]), comum.data_br_iso(linha.get("Data"))
        if did is None or data is None:
            continue
        itens.append({"idDeputado": did, "data": data, "destino": None, "motivo": None, "valor": comum.valor_br(linha.get("Valor")),
                      "quantidade": comum.valor_br(linha.get("Quantidade")), "fonte": linha.get("Relatório") or DIARIAS_PAGINA})
    return itens


# ---------------------------------------------------------------- presença em sessões (e-Legis)

def parse_sessoes(html: str) -> list[dict]:
    """[{codigo, titulo, data (AAAA-MM-DD), situacao}] de uma página da lista de sessões plenárias."""
    sessoes = []
    for bloco in html.split('<div class="card card-alesc mb-4">')[1:]:
        codigo = re.search(r"/sessoes-plenarias/(\w+)/presenca", bloco)
        titulo = re.search(r'<h4 class="mb-1">(.*?)</h4>', bloco, re.S)
        data = re.search(r"(\d\d/\d\d/\d{4})\s*·", bloco)
        situacao = re.search(r'</i>\s*([^<]+)</span>\s*</div>\s*</div>\s*</div>', bloco)
        if codigo and titulo and data:
            sessoes.append({"codigo": codigo.group(1), "titulo": comum.limpar(titulo.group(1)), "data": comum.data_br_iso(data.group(1)),
                            "situacao": comum.limpar(situacao.group(1)) if situacao else None})
    return sessoes


def total_paginas(html: str) -> int:
    paginas = [int(n) for n in re.findall(r"/sessoes-plenarias\?page=(\d+)", html)]
    return max(paginas) if paginas else 1


def parse_presenca(html: str) -> dict:
    """{nome: situação} da tabela de presença de uma sessão."""
    return {comum.limpar(n): comum.limpar(s) for n, s in re.findall(r"<tr>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*</tr>", html, re.S) if comum.limpar(n)}


def tipo_presenca(situacao: str) -> str:
    s = comum.sem_acento(situacao)
    if s.startswith("presente"):
        return "presente"
    if "justific" in s or "licen" in s:
        return "licenca"
    return "ausente"


def itens_presenca(sessoes: dict, deputados: list[dict]) -> list[dict]:
    """Soma por deputado e mês as sessões lidas: {codigo: {data, presencas:{nome: situação}}}."""
    sessoes = {c: s for c, s in sessoes.items() if s["presencas"]}
    nomes = {n for s in sessoes.values() for n in s["presencas"]}
    ligados = ligar(nomes, deputados)
    totais: dict = {}
    sessoes_mes: dict = {}
    for s in sessoes.values():
        periodo = s["data"][:7]
        sessoes_mes[periodo] = sessoes_mes.get(periodo, 0) + 1
        for nome, situacao in s["presencas"].items():
            if nome not in ligados:
                continue
            t = totais.setdefault((ligados[nome], periodo), {"presente": 0, "ausente": 0, "licenca": 0})
            t[tipo_presenca(situacao)] += 1
    return [{"idDeputado": did, "periodo": periodo, **t, "totalSessoes": sessoes_mes[periodo], "fonte": SESSOES_URL}
            for (did, periodo), t in sorted(totais.items(), key=lambda x: (x[0][1], str(x[0][0])))]


# ---------------------------------------------------------------- coleta

baixar = partial(comum.get, timeout=60)


def coletar_remuneracao(s, pasta, hoje: date, agora: str) -> None:
    for ano in range(hoje.year - ANOS_REMUNERACAO + 1, hoje.year + 1):
        arq = pasta / f"remuneracao_{ano}.json"
        itens = comum.ler(arq, {"itens": []})["itens"]
        feitos = {i["mes"] for i in itens}
        for mes in range(1, 13):
            if (ano, mes) > (hoje.year, hoje.month):
                break
            if mes in feitos and (ano, mes) not in comum.meses_recentes(hoje, MESES_RECENTES):
                continue
            itens = [i for i in itens if i["mes"] != mes]
            lista = parse_deputados(baixar(s, DEPUTADOS_URL, params={"ano": ano, "mes": mes}).text)
            contracheques = {}
            for d in lista:
                r = baixar(s, f"{DEPUTADOS_URL}/contracheque/{d['idContracheque']}", params={"ano": ano, "mes": mes}, headers=CABECALHO_AJAX)
                cc = parse_contracheque(r.text)
                if cc["bruto"] is not None:
                    contracheques[d["idContracheque"]] = cc
            itens += itens_remuneracao(contracheques, mes, ano)
        itens.sort(key=lambda i: (i["mes"], str(i["idDeputado"])))
        comum.salvar(arq, {"coletadoEm": agora, "fonte": DEPUTADOS_URL, "itens": itens})
        print(f"SC: remuneração {ano} {len(itens)} registros")


def coletar_presenca(s, pasta, deputados: list[dict], hoje: date, agora: str) -> None:
    arq = pasta / "presenca.json"
    guardado = comum.ler(arq, {})
    sessoes = guardado.get("sessoes", {})
    limite = f"{PRIMEIRO_ANO}-02-01"
    pagina, ultima, parar = 1, 1, False
    while pagina <= ultima and not parar:
        html = baixar(s, SESSOES_URL, params={"page": pagina}).text
        ultima = total_paginas(html)
        for sessao in parse_sessoes(html):
            if sessao["data"] < limite:
                parar = True
                continue
            if sessao["situacao"] != "Realizada" or sessao["codigo"] in sessoes:
                continue
            presencas = parse_presenca(baixar(s, f"{SESSOES_URL}/{sessao['codigo']}/presenca").text)
            sessoes[sessao["codigo"]] = {"data": sessao["data"], "titulo": sessao["titulo"], "presencas": presencas}
        pagina += 1
    comum.salvar(arq, {"coletadoEm": agora, "fonte": SESSOES_URL, "itens": itens_presenca(sessoes, deputados), "sessoes": sessoes})
    print(f"SC: presença {len(sessoes)} sessões")


def coletar() -> None:
    pasta = comum.DADOS / UF
    hoje = date.today()
    agora = hoje.isoformat()
    s = comum.sessao()
    lista = parse_deputados(baixar(s, DEPUTADOS_URL).text)
    if not lista:
        comum.avisar("SC: nenhum deputado na página de subsídios")
        return
    deputados = deputados_com_tse(lista)
    comum.salvar(pasta / "deputados.json", {"fonte": DEPUTADOS_URL, "host": None, "legislatura": "2023-2027", "deputados": deputados})

    for ano in range(PRIMEIRO_ANO, hoje.year + 1):
        if all(comum.ano_encerrado(ano, hoje, pasta / f"{nome}_{ano}.json") for nome in ("verbas", "diarias")):
            continue
        gab = itens_gabinetes(ler_csv(baixar(s, f"{GABINETES_PAGINA}/csv/{ano}").content.decode("utf-8-sig")), deputados)
        comum.salvar(pasta / f"verbas_{ano}.json", {"coletadoEm": agora, "fonte": GABINETES_PAGINA, "itens": gab})
        dia = itens_diarias(ler_csv(baixar(s, f"{DIARIAS_PAGINA}/csv/{ano}").content.decode("utf-8-sig")), deputados)
        comum.salvar(pasta / f"diarias_{ano}.json", {"coletadoEm": agora, "fonte": DIARIAS_PAGINA, "itens": dia})
        print(f"SC: {ano} gabinetes {len(gab)}, diárias {len(dia)}")
    coletar_presenca(s, pasta, deputados, hoje, agora)
    coletar_remuneracao(s, pasta, hoje, agora)
    comum.tentar(UF, "proposições", partial(coletar_proposicoes, s, pasta, deputados, hoje, agora))
    comum.tentar(UF, "gabinete", partial(coletar_gabinete, s, pasta, deputados, hoje, agora))
    comum.tentar(UF, "contratos do órgão", partial(coletar_orgao, s, pasta, hoje, agora))
    comum.tentar(UF, "regras da cota", partial(coletar_regras, s, pasta))
    print(f"SC: {len(deputados)} deputados")


# ---------------------------------------------------------------- proposições

def proposicoes_da_pagina(html: str) -> list[dict]:
    """Cards da lista: código (id da fonte, 5 caracteres), "PL./0667/2026", ementa, entrada, autores e situação."""
    itens = []
    for card in html.split('<div class="card card-alesc')[1:]:
        m = re.search(r'<a href="/proposicoes/(\w+)">\s*([A-Za-z]+)\.?/(\d+)/(\d{4})\s*</a>', card)
        if not m:
            continue
        ementa = re.search(r'<p class="mb-1 fst-italic"[^>]*>(.*?)</p>', card, re.S)
        campo = lambda rotulo: re.search(rf'fw-bold[^"]*">\s*{rotulo}\s*</div>\s*<div class="col-lg-10">(.*?)</div>', card, re.S)  # noqa: E731
        autoria, entrada, situacao = campo("Autoria"), campo("Entrada"), campo("Situa\\S+o atual")
        itens.append({"codigo": m.group(1), "tipo": m.group(2).upper(), "numero": int(m.group(3)), "ano": int(m.group(4)),
                      "ementa": comum.limpar(ementa.group(1)) if ementa else "", "dataApresentacao": comum.data_br_iso(comum.limpar(entrada.group(1))) if entrada else None,
                      "autores": [comum.limpar(a) for a in re.findall(r"<li>(.*?)</li>", autoria.group(1), re.S)] if autoria else [],
                      "situacao": comum.limpar(situacao.group(1)) if situacao else None})
    return itens


def total_proposicoes(html: str) -> int:
    m = re.search(r"Exibindo\s+[\d.]+\s*-\s*[\d.]+\s+de\s+([\d.]+)", html)
    return int(m.group(1).replace(".", "")) if m else 0


def ler_proposicoes(s, ano: int, inicio: str | None = None) -> list[dict]:
    """Proposições abertas no ano (ou só a partir de `inicio`), página a página. O parâmetro `ano` da página não filtra: o ano
    sai da janela de datas de abertura."""
    filtros = {"arquivados": 1, "inicio": inicio or f"{ano}-01-01", "fim": f"{ano}-12-31"}
    lidas, pagina = [], 1
    while True:
        html = baixar(s, PROPOSICOES_URL, params={**filtros, "page": pagina}).text
        achadas = proposicoes_da_pagina(html)
        lidas += achadas
        if not achadas or len(lidas) >= total_proposicoes(html):
            return lidas
        pagina += 1


def autor_deputado(nome: str) -> str | None:
    """"Deputado Jerry Comper" -> "Jerry Comper"; governador, comissões e Mesa -> None."""
    m = re.match(r"^\s*Deputad[oa]\s+(.+)$", nome or "", re.I)
    return m.group(1).strip() if m else None


def do_governador(p: dict) -> bool:
    return any(re.search(r"governador", a, re.I) for a in p["autores"])


def separar_proposicoes(lidas: list[dict], deputados: list[dict]) -> tuple[dict, dict]:
    """({chave: matéria de deputado}, {chave: matéria do governador}) no formato de materias_/governo_<ano>.json."""
    ligacao = ligar({n for p in lidas for a in p["autores"] if (n := autor_deputado(a))}, deputados)
    materias, governo = {}, {}
    for p in lidas:
        chave = f"{p['tipo']}-{p['numero']}-{p['ano']}"
        base = {"tipo": p["tipo"], "numero": p["numero"], "ano": p["ano"], "dataApresentacao": p["dataApresentacao"], "ementa": p["ementa"],
                "situacao": p["situacao"], "idFonte": p["codigo"], "linkTexto": f"{ELEGIS}/proposicoes/{p['codigo']}/documentos",
                "fonte": f"{ELEGIS}/proposicoes/{p['codigo']}"}
        ids = sorted({ligacao[n] for a in p["autores"] if (n := autor_deputado(a)) in ligacao})
        if ids:
            materias[chave] = {**base, "idsAutores": ids, "idsDeputados": ids}
        elif do_governador(p):
            governo[chave] = {**base, "tipoDescricao": p["tipo"]}
    return materias, governo


def coletar_proposicoes(s, pasta, deputados: list[dict], hoje: date, agora: str) -> None:
    """Ano sem arquivo: leitura inteira. Os demais: incremental pela data de abertura (desde a coleta anterior, com folga) e, um ano
    por coleta, releitura inteira quando a última passou de RENOVAR_COMPLETA_DIAS (a situação muda sem mudar a data de abertura)."""
    def idade(env):
        return (hoje - date.fromisoformat(env["completaEm"])).days if env.get("completaEm") else 10 ** 6

    anos = range(PRIMEIRO_ANO, hoje.year + 1)
    envs = {ano: comum.ler(pasta / f"materias_{ano}.json", {}) for ano in anos}
    vencidos = sorted((a for a in anos if envs[a] and idade(envs[a]) >= RENOVAR_COMPLETA_DIAS), key=lambda a: idade(envs[a]), reverse=True)
    completa_hoje = vencidos[:1]
    for ano in anos:
        env = envs[ano]
        completa = not env or ano in completa_hoje
        if not completa and comum.ano_encerrado(ano, hoje, pasta / f"materias_{ano}.json"):
            continue
        inicio = None if completa else (date.fromisoformat(env["coletadoEm"]) - timedelta(days=FOLGA_DIAS)).isoformat()
        materias, governo = separar_proposicoes(ler_proposicoes(s, ano, inicio), deputados)
        if completa and not materias and env.get("materias"):
            raise RuntimeError(f"proposições {ano}: lista vazia; mantém o arquivo anterior")
        if not completa:
            materias = {**env.get("materias", {}), **materias}
            governo = {**comum.ler(pasta / f"governo_{ano}.json", {}).get("materias", {}), **governo}
        comum.salvar(pasta / f"materias_{ano}.json", {"coletadoEm": agora, "completaEm": agora if completa else env.get("completaEm"),
                                                      "fonte": PROPOSICOES_URL, "materias": materias})
        comum.salvar(pasta / f"governo_{ano}.json", {"coletadoEm": agora, "fonte": PROPOSICOES_URL, "materias": governo})
        print(f"SC: {ano} proposições de deputados {len(materias)}, do governador {len(governo)}{' (completa)' if completa else ''}")


# ---------------------------------------------------------------- gabinete

def setores_de_gabinete(html: str) -> dict[str, str]:
    """{setor_id: nome do deputado} das opções "GAB DEP <nome>" do filtro de lotação."""
    return {i: m.group(1).strip() for i, rotulo in re.findall(r'<option value="(\d+)"[^>]*>\s*([^<]+)', html)
            if (m := SETOR_GABINETE.match(comum.limpar(rotulo)))}


def servidores_da_pagina(html: str) -> list[dict]:
    return [{"nome": comum.limpar(n), "vinculo": comum.limpar(v), "lotacao": comum.limpar(l), "matricula": i}
            for n, v, l, i in re.findall(r'<td class="fw-semibold">(.*?)</td>\s*<td>(.*?)</td>\s*<td class="small">(.*?)</td>.*?/servidores/contracheque/(\d+)', html, re.S)]


def coletar_gabinete(s, pasta, deputados: list[dict], hoje: date, agora: str) -> None:
    arq = pasta / "gabinete.json"
    anterior = comum.ler(arq, {})
    if anterior.get("coletadoEm") and (hoje - date.fromisoformat(anterior["coletadoEm"])).days < GABINETE_DIAS:
        return
    setores = setores_de_gabinete(baixar(s, SERVIDORES_URL).text)
    ligados = ligar(set(setores.values()), deputados)
    itens = []
    for setor, nome in sorted(setores.items()):
        id_dep = ligados.get(nome)
        if not id_dep:
            continue
        vistos, pagina = set(), 1
        while True:
            linhas = [l for l in servidores_da_pagina(baixar(s, SERVIDORES_URL, params={"setor_id": setor, "page": pagina}).text) if l["matricula"] not in vistos]
            if not linhas:
                break
            vistos |= {l["matricula"] for l in linhas}
            itens += [{"idDeputado": id_dep, "matricula": l["matricula"], "nome": l["nome"], "simbolo": l["vinculo"] or None}
                      for l in linhas if (l["vinculo"] or "").lower() != "deputado"]
            pagina += 1
    if not itens:
        raise RuntimeError("nenhum servidor ligado a gabinete de deputado; mantém o arquivo anterior")
    comum.salvar(arq, {"coletadoEm": agora, "fonte": SERVIDORES_URL, "itens": sorted(itens, key=lambda i: (i["idDeputado"], i["simbolo"] or "", i["nome"]))})
    print(f"SC: gabinetes {len(itens)} servidores de {len({i['idDeputado'] for i in itens})} deputados")


# ---------------------------------------------------------------- contratos e atas do órgão, regras da cota

def contratos_da_pagina(html: str) -> dict:
    itens = {}
    for card in html.split('<article class="card card-alesc')[1:]:
        m = re.search(r'href="/contratos/(\d+)"[^>]*>\s*N\S*\s*([^<]+)</a>', card)
        if not m:
            continue
        especie = re.search(r'text-uppercase small fw-semibold">([^<]*)', card)
        especie = comum.limpar(especie.group(1)) if especie else ""
        nome = re.search(r'<div class="fw-bold">(.*?)</div>\s*<div class="text-muted small">\s*(?:CNPJ|CPF)?:?\s*([^<]*)</div>', card, re.S)
        objeto = re.search(r'Objeto</span>\s*</div>\s*<p[^>]*>(.*?)</p>', card, re.S)
        valor = re.search(r'Valor Original</div>\s*<div[^>]*>(.*?)</div>', card, re.S)
        modalidade = re.search(r'Modalidade</div>\s*<div>(.*?)</div>', card, re.S)
        vigencia = re.search(r'Vig\S+ncia\s*</div>\s*<div>\s*(\d\d/\d\d/\d{4})\s*-\s*(\d\d/\d\d/\d{4})?', card)
        situacao = re.search(r'<span class="badge[^"]*">([^<]*)</span>', card)
        download = re.search(r'href="(/contratos/download/\d+)"', card)
        iid, item = comum.item_orgao(
            FONTE_ID, "ata_registro" if re.search(r"registro\s+de\s+pre", especie, re.I) else "contrato", m.group(1),
            fornecedor_nome=comum.limpar(nome.group(1)) if nome else None, documento=nome.group(2) if nome else None,
            valor=comum.valor_br(comum.limpar(valor.group(1))) if valor else None, objeto=comum.limpar(objeto.group(1)) if objeto else None,
            inicio=comum.data_br_iso(vigencia.group(1)) if vigencia else None, fim=comum.data_br_iso(vigencia.group(2)) if vigencia and vigencia.group(2) else None,
            numero=comum.limpar(m.group(2)), fonte=f"{CONTRATOS_URL}/{m.group(1)}", especie=especie or None,
            modalidade=(comum.limpar(modalidade.group(1)).strip("- ") or None) if modalidade else None,
            situacao=comum.limpar(situacao.group(1)) if situacao else None,
            arquivos=[{"nome": "Contrato (PDF)", "url": TRANSPARENCIA + download.group(1)}] if download else [])
        itens[iid] = item
    return itens


def coletar_orgao(s, pasta, hoje: date, agora: str) -> None:
    for ano in range(PRIMEIRO_ANO, hoje.year + 1):
        arq = pasta / f"orgao_{ano}.json"
        if comum.ano_encerrado(ano, hoje, arq):
            continue
        itens, pagina = {}, 1
        while True:
            novos = contratos_da_pagina(baixar(s, CONTRATOS_URL, params={"ano_vigencia": ano, "page": pagina}).text)
            if not novos or novos.keys() <= itens.keys():
                break
            itens |= novos
            pagina += 1
        if not itens and comum.ler(arq, {}).get("itens"):
            comum.avisar(f"SC: contratos {ano}: lista vazia; mantém o arquivo anterior")
            continue
        comum.salvar(arq, {"coletadoEm": agora, "fonte": f"{CONTRATOS_URL}?ano_vigencia={ano}", "itens": itens})
        print(f"SC: {ano} contratos e atas do órgão {len(itens)}")


def regras_da_cota(html: str) -> dict | None:
    """Atos da seção "Gabinetes Parlamentares"; url e ano = o mais novo que trata das cotas de custeio do gabinete."""
    partes = html.split('id="gabinetes-parlamentares"')
    if len(partes) < 2:
        return None
    secao = partes[1].split('class="card-title h5" id="')[0]
    docs = []
    for url, titulo, ementa in re.findall(r'<a href="(/ato-normativo/legislativo/\d+)">([^<]*)</a>.*?fst-italic mb-2">([^<]*)', secao, re.S):
        anos = re.findall(r"(?:19|20)\d\d", titulo)
        docs.append({"titulo": comum.limpar(titulo), "ementa": comum.compactar(ementa), "url": LEIS + url, "ano": int(anos[-1]) if anos else None})
    cotas = [d for d in docs if d["ano"] and re.search(r"\bcotas?\b", d["ementa"] or "", re.I)]
    if not cotas:
        return None
    atual = max(cotas, key=lambda d: d["ano"])
    return {"url": atual["url"], "ano": atual["ano"], "titulo": atual["titulo"], "fonte": f"{REGRAS_URL}#gabinetes-parlamentares", "documentos": docs}


def coletar_regras(s, pasta) -> None:
    regra = regras_da_cota(baixar(s, REGRAS_URL).text)
    if not regra:
        raise RuntimeError("seção de gabinetes parlamentares sem ato sobre as cotas; mantém o arquivo anterior")
    comum.salvar(pasta / "regras_ressarcimento.json", regra)


# ---------------------------------------------------------------- contratos

def _contrato_deputados(ctx):
    html = baixar(comum.sessao(), DEPUTADOS_URL).text
    i = html.index('<table class="table table-hover align-middle">')
    linhas = re.findall(r"<tr>\s*<td class=\"fw-semibold\">.*?</tr>", html[i:], re.S)
    return {"html": "<table>" + "".join(linhas[:2]) + "</table>"}


def _conferir_deputados(registro):
    lista = parse_deputados(registro["html"])
    falhas = [] if lista else ["tabela de deputados sem linhas"]
    return falhas + [f"deputado sem {k}" for d in lista for k, v in d.items() if not v], []


def _contrato_contracheque(ctx):
    s = comum.sessao()
    hoje = date.today()
    ano, mes = mes_anterior(hoje.year, hoje.month)
    lista = parse_deputados(baixar(s, DEPUTADOS_URL, params={"ano": ano, "mes": mes}).text)
    html = baixar(s, f"{DEPUTADOS_URL}/contracheque/{lista[0]['idContracheque']}", params={"ano": ano, "mes": mes}, headers=CABECALHO_AJAX).text
    i = html.index("<table")
    return {"html": html[i: html.index("</table>", i) + 8]}


def _conferir_contracheque(registro):
    cc = parse_contracheque(registro["html"])
    falhas = [f"contracheque sem {k}" for k in ("bruto", "liquido") if cc[k] is None]
    if not cc["componentes"]:
        falhas.append("contracheque sem componentes")
    return falhas, []


def _contrato_csv(caminho, vinculo=None):
    def buscar(ctx):
        texto = baixar(comum.sessao(), f"{TRANSPARENCIA}/{caminho}/csv/{date.today().year}").content.decode("utf-8-sig")
        linhas = texto.splitlines()
        if vinculo:
            return {"csv": "\n".join(linhas[:1] + [linha for linha in linhas[1:] if f";{vinculo};" in linha][:2])}
        return {"csv": "\n".join(linhas[:4])}
    return buscar


def _conferir_gabinetes(registro):
    linhas = ler_csv(registro["csv"])
    esperadas = {"Verba", "Descrição", "Conta", "Favorecido", "Trecho", "Data de Referência", "Valor"}
    falhas = [f"CSV sem a coluna {c}" for c in esperadas - set(linhas[0] if linhas else [])]
    return falhas + ([] if linhas else ["CSV de gabinetes sem linhas"]), []


def _conferir_diarias(registro):
    linhas = ler_csv(registro["csv"])
    esperadas = {"Nome", "Conta", "Vínculo", "Data", "Quantidade", "Valor", "Relatório"}
    falhas = [f"CSV sem a coluna {c}" for c in esperadas - set(linhas[0] if linhas else [])]
    return falhas + ([] if linhas else ["CSV de diárias sem linhas"]), []


def _contrato_sessoes(ctx):
    s = comum.sessao()
    html = baixar(s, SESSOES_URL).text
    sessoes = parse_sessoes(html)
    pagina = ""
    for sessao in (x for x in sessoes if x["situacao"] == "Realizada"):
        pagina = baixar(s, f"{SESSOES_URL}/{sessao['codigo']}/presenca").text
        if parse_presenca(pagina):
            break
    inicio = html.index('<div class="card card-alesc mb-4">')
    fim = html.index('<div class="card card-alesc mb-4">', html.index('<div class="card card-alesc mb-4">', inicio + 10) + 10)
    tabela = pagina[re.search(r"<table[^>]*>", pagina).start():]
    linhas = re.findall(r"<tr>\s*<td>.*?</tr>", tabela, re.S)
    return {"lista": html[inicio:fim], "total": total_paginas(html), "presenca": "<table>" + "".join(linhas[:3]) + "</table>"}


def _conferir_sessoes(registro):
    sessoes = parse_sessoes(registro["lista"])
    falhas = [] if sessoes else ["lista de sessões plenárias vazia"]
    falhas += ["sessão sem data ou situação" for x in sessoes if not x["data"] or not x["situacao"]]
    if not parse_presenca(registro["presenca"]):
        falhas.append("página de presença sem linhas")
    return falhas, []


CONTRATOS = [
    {"nome": "estadual_sc_deputados", "fonte": DEPUTADOS_URL, "buscar": _contrato_deputados, "html": _conferir_deputados},
    {"nome": "estadual_sc_contracheque", "fonte": DEPUTADOS_URL, "buscar": _contrato_contracheque, "html": _conferir_contracheque},
    {"nome": "estadual_sc_gabinetes", "fonte": f"{GABINETES_PAGINA}/dados-abertos", "buscar": _contrato_csv("gabinetes-parlamentares"), "html": _conferir_gabinetes},
    {"nome": "estadual_sc_diarias", "fonte": f"{DIARIAS_PAGINA}/dados-abertos", "buscar": _contrato_csv("diarias", "Deputado"), "html": _conferir_diarias},
    {"nome": "estadual_sc_sessoes", "fonte": SESSOES_URL, "buscar": _contrato_sessoes, "html": _conferir_sessoes},
]


if __name__ == "__main__":
    comum.principal(coletar)
