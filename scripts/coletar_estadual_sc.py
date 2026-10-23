"""
Deputados estaduais de Santa Catarina (ALESC), fora do SAPL.

Fontes lidas aqui (abertas, sem login):
  - deputados em exercício e remuneração mensal: https://transparencia.alesc.sc.gov.br/deputados?ano=&mes=
    (tabela com o nome civil; o contracheque de cada um vem de /deputados/contracheque/<id>?ano=&mes=, resposta HTMX);
    partido e nome de urna vêm dos eleitos de 2022 do TSE (dados/tse/2022/SC.json) quando o nome civil casa;
  - gabinetes parlamentares (cota de exercício parlamentar), CSV por ano: /gabinetes-parlamentares/csv/<ano>
  - diárias e passagens, CSV por ano (só linhas com vínculo "Deputado"): /diarias/csv/<ano>
  - presença em sessões plenárias, uma página por sessão: https://portalelegis.alesc.sc.gov.br/sessoes-plenarias/<codigo>/presenca

Não coletado: proposições e votações (e-Legis, um documento por proposição, sem exportação), presença em comissões.
"""

import csv
import io
import re
from datetime import date
from html import unescape
from functools import partial

import estaduais_comum as comum

UF = "SC"
TRANSPARENCIA = "https://transparencia.alesc.sc.gov.br"
ELEGIS = "https://portalelegis.alesc.sc.gov.br"
TSE_ARQUIVO = comum.arquivo_tse(UF)
DEPUTADOS_URL = f"{TRANSPARENCIA}/deputados"
GABINETES_PAGINA = f"{TRANSPARENCIA}/gabinetes-parlamentares"
DIARIAS_PAGINA = f"{TRANSPARENCIA}/diarias"
SESSOES_URL = f"{ELEGIS}/sessoes-plenarias"
CABECALHO_AJAX = {"X-Requested-With": "XMLHttpRequest"}
PRIMEIRO_ANO = 2023
ANOS_REMUNERACAO = 2
MESES_RECENTES = 2
TITULOS = {"dr", "dra", "prof", "profa", "delegado", "delegada", "dep", "deputado", "deputada", "da", "de", "do", "dos", "das", "e"}
tokens = partial(comum.palavras, ignorar=TITULOS)
CAMPOS_NOME = ("nome", "nomeCivil", "nomeFonte")


def _cabe(a: list, b: list) -> bool:
    """Toda palavra de `a` está em `b`, igual ou como começo de palavra de 4 letras ou mais ("alex" em "alexander")."""
    return bool(a) and all(any(x == y or (len(x) >= 4 and y.startswith(x)) for y in b) for x in a)


def _unico(alvo: list, candidatos: list[tuple]):
    """Chave do único candidato que casa com `alvo` (um contém o outro); None se houver zero ou mais de um."""
    achados = {k for k, toks in candidatos if _cabe(alvo, toks) or (len(toks) >= 2 and _cabe(toks, alvo))}
    if len(achados) > 1:
        achados = {k for k, toks in candidatos if sorted(toks) == sorted(alvo)} or achados
    return next(iter(achados)) if len(achados) == 1 else None


def ligar(nomes, deputados: list[dict]) -> dict:
    """Como `ligar_nomes`; o nome que não casa inteiro casa pelas palavras (sem "da", "de"...) com um só nome de deputado.
    "Ana Paula da Silva (Paulinha)" também tenta só o apelido entre parênteses."""
    ligados = comum.ligar_nomes(nomes, deputados)
    candidatos = [(d["id"], t) for d in deputados for c in CAMPOS_NOME if d.get(c) and (t := tokens(d[c]))]
    for n in nomes:
        if n in ligados:
            continue
        for v in [re.sub(r"\([^)]*\)", " ", n)] + re.findall(r"\(([^)]*)\)", n):
            achado = _unico(tokens(v), candidatos)
            if achado is not None:
                ligados[n] = achado
                break
    return ligados


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
    candidatos = [(e["sequencial"], t) for e in eleitos for campo in ("nome", "urna") if e.get(campo) and (t := tokens(e[campo]))]
    por_id = {e["sequencial"]: e for e in eleitos}
    saida = []
    for d in lista:
        e = por_id.get(_unico(tokens(d["nomeCivil"]), candidatos))
        saida.append({"id": d["idContracheque"], "nome": e["urna"] if e and e.get("urna") else d["nomeCivil"].title(),
                      "nomeCivil": e["nome"] if e else d["nomeCivil"].title(), "nomeFonte": d["nomeCivil"].title(), "foto": None,
                      "email": e.get("email") if e else None, "titular": True, "partido": e.get("partido") if e else None, "fonte": DEPUTADOS_URL})
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
        itens.append({"idDeputado": did, "mes": int(data[5:7]), "categoria": categoria, "fornecedor": linha.get("Favorecido") or None, "cnpj": None,
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
    print(f"SC: {len(deputados)} deputados")


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
