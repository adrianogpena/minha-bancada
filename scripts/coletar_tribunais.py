"""
Coleta dos ministros dos tribunais superiores (STF, STJ, TST, TSE, STM e TCU), primeira etapa: quem compõe cada Corte hoje.
Os sites oficiais bloqueiam coleta automática (403 / "Request Rejected"), então a lista vem da tabela "Composição atual" da
Wikipédia em português (API do MediaWiki, HTML renderizado); a página oficial de cada tribunal vai como fonte para conferência.
Grava dados/tribunais/tribunais.json (vai para o git; `vistoDesde`/`vistoAte` são os dias da coleta em que o ministro
apareceu e sumiu da tabela):

  {coletadoEm, tribunais: {sigla: {nome, fonte, wikipedia, atualizadoEm,
      atuais: [{nome, wiki, categoria, posse, nomeadoPor, vaga, estado, nascimento, limite, observacao, vistoDesde}],
      anteriores: [{... , vistoAte}]}}}

`posse` em ISO quando a tabela traz a data completa; `nomeadoPor` é o presidente que nomeou (STF, STJ, TST, TCU, STM).

Uso:
    python scripts/coletar_tribunais.py
"""

import datetime as dt
import html as htmllib
import re
from pathlib import Path
from urllib.parse import unquote

import estaduais_comum as comum

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO = RAIZ / "dados" / "tribunais" / "tribunais.json"
WIKI = "https://pt.wikipedia.org/w/api.php?action=parse&prop=text&format=json&formatversion=2&redirects=1&page="
WIKI_PAGINA = "https://pt.wikipedia.org/wiki/"
MESES = {m: i for i, m in enumerate("janeiro fevereiro marco abril maio junho julho agosto setembro outubro novembro dezembro".split(), 1)}

# sigla: (nome, página da Wikipédia, página oficial da composição, mínimo de ministros esperado)
TRIBUNAIS = {
    "STF": ("Supremo Tribunal Federal", "Supremo_Tribunal_Federal", "https://portal.stf.jus.br/ostf/ministros/", 9),
    "STJ": ("Superior Tribunal de Justiça", "Superior_Tribunal_de_Justiça", "https://www.stj.jus.br/sites/portalp/Institucional/Ministros", 25),
    "TST": ("Tribunal Superior do Trabalho", "Tribunal_Superior_do_Trabalho", "https://www.tst.jus.br/ministros", 20),
    "TSE": ("Tribunal Superior Eleitoral", "Tribunal_Superior_Eleitoral", "https://www.tse.jus.br/institucional/composicao-do-tse", 5),
    "STM": ("Superior Tribunal Militar", "Superior_Tribunal_Militar", "https://www.stm.jus.br/o-stm-stm/composicao-da-corte", 12),
    "TCU": ("Tribunal de Contas da União", "Tribunal_de_Contas_da_União", "https://portal.tcu.gov.br/ministros-e-ministros-substitutos", 7),
}

# o que cada coluna da tabela da Wikipédia vira; o primeiro cabeçalho que casar vale
COLUNAS = [
    ("nome", r"^(nome|ministro)"),
    ("posse", r"posse|inicio"),
    ("nomeadoPor", r"nomeacao|indicacao"),
    ("vaga", r"^vaga|origem da vaga|^origem$"),
    ("estado", r"estado|origem$"),
    ("nascimento", r"nascimento"),
    ("limite", r"limite|aposent"),
    ("observacao", r"observ|funcoes|^cargo"),
]
LINKS_OFICIAIS = {"nomeadoPor"}


def texto(celula: str) -> str:
    """Texto visível da célula: sem chave de ordenação oculta, notas de rodapé nem espaços especiais."""
    c = re.sub(r'<span[^>]*display:\s*none[^>]*>.*?</span>', "", celula, flags=re.S)
    c = re.sub(r"<sup[^>]*>.*?</sup>|<style.*?</style>", "", c, flags=re.S)
    c = re.sub(r"<br\s*/?>", " ", c)
    c = re.sub(r"<[^>]+>", "", c)
    return re.sub(r"\s+", " ", htmllib.unescape(c).replace("\xa0", " ")).strip()


def data_extenso(t: str | None) -> str | None:
    """'3 de agosto de 2023' ou '22/12/2014' em ISO; ausente ou incompleta (só o ano) vale None."""
    if not t:
        return None
    if m := re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", t):
        return comum.data_br_iso(m.group(0))
    if m := re.search(r"(\d{1,2})\s*[ºo°]?\s+de\s+([a-zç]+)\s+(?:de\s+)?(\d{4})", comum.sem_acento(t).lower()):
        mes = MESES.get(m.group(2))
        if mes:
            return f"{m.group(3)}-{mes:02d}-{int(m.group(1)):02d}"
    return None


def colunas(cabecalho: list[str]) -> dict[str, int]:
    """{campo: índice} pelos cabeçalhos; coluna sem cabeçalho reconhecido fica de fora."""
    saida: dict[str, int] = {}
    usados: set[int] = set()
    for campo, padrao in COLUNAS:
        for i, h in enumerate(cabecalho):
            if i not in usados and re.search(padrao, comum.sem_acento(h).lower()):
                saida[campo] = i
                usados.add(i)
                break
    return saida


def celulas(linha: str) -> list[tuple[str, str]]:
    """[(tag, html)] das células da linha, com colspan/rowspan ignorados (a tabela é lida por posição)."""
    return [(m.group(1), m.group(2)) for m in re.finditer(r"<(t[hd])\b[^>]*>(.*?)</t[hd]>", linha, re.S)]


def ler_tabelas(pagina: str) -> list[dict]:
    """Ministros da primeira tabela da página com colunas de nome e de posse.

    Linha de uma célula só (`colspan`) é título de grupo (ex.: "Ministros substitutos") e vira `categoria` das seguintes.
    Cabeçalho é a primeira linha só de <th>; linhas que começam com <th> de número (antiguidade) deslocam o nome uma coluna,
    por isso o índice se mede pelo cabeçalho de cada linha: a linha de dados tem o mesmo número de células que o cabeçalho."""
    for tabela in re.findall(r"<table\b[^>]*wikitable.*?</table>", pagina, re.S):
        linhas = re.findall(r"<tr\b.*?</tr>", tabela, re.S)
        cab = next((c for c in map(celulas, linhas) if len(c) > 2 and all(t == "th" for t, _ in c)), None)
        if not cab:
            continue
        cabecalho = [texto(h) for _, h in cab]
        col = colunas(cabecalho)
        if "nome" not in col or "posse" not in col:
            continue
        saida, categoria = [], None
        for linha in linhas:
            cel = celulas(linha)
            if len(cel) == 1:
                categoria = texto(cel[0][1]) or categoria
                continue
            if len(cel) != len(cabecalho) or all(t == "th" for t, _ in cel) and cel[0][1] == cab[0][1]:
                continue
            ministro = linha_ministro(cel, col, categoria)
            if ministro:
                saida.append(ministro)
        if saida:
            return saida
    return []


def linha_ministro(cel: list[tuple[str, str]], col: dict[str, int], categoria: str | None) -> dict | None:
    bruto = {campo: cel[i][1] for campo, i in col.items()}
    nome = texto(bruto["nome"])
    nome = re.sub(r"\s*\((presidente|vice-presidente|corregedor[^)]*|[^)]*)\)\s*$", "", nome, flags=re.I) if nome.endswith(")") else nome
    nome = re.sub(r"\s*\(\d{4}\s*[–-]\s*\)\s*$", "", nome).strip()   # "(1972–)" da lista do STF
    if not nome or len(nome) < 5:
        return None
    link = re.search(r'<a\b[^>]*href="/wiki/([^"#?]+)"', bruto["nome"])
    posse = texto(bruto["posse"])
    saida = {"nome": nome, "wiki": unquote(htmllib.unescape(link.group(1))) if link else None, "posse": data_extenso(posse), "posseTexto": posse}
    if categoria:
        saida["categoria"] = categoria
    for campo in ("nomeadoPor", "vaga", "estado", "nascimento", "limite", "observacao"):
        if campo in bruto and (v := texto(bruto[campo])):
            saida[campo] = v
    if "nascimento" in saida:
        saida["nascimento"] = data_extenso(saida["nascimento"]) or saida["nascimento"]
    return saida


def atualizar(anterior: dict | None, lidos: list[dict], hoje: str) -> dict:
    """Mantém `vistoDesde` de quem continua, abre quem entrou e fecha (`vistoAte`) quem saiu."""
    antes = {comum.sem_acento(x["nome"]): x for x in (anterior or {}).get("atuais", [])}
    atuais = [{**x, "vistoDesde": antes.get(comum.sem_acento(x["nome"]), {}).get("vistoDesde") or hoje} for x in lidos]
    agora = {comum.sem_acento(x["nome"]) for x in lidos}
    saidas = [{**x, "vistoAte": hoje} for k, x in antes.items() if k not in agora]
    return {"atuais": atuais, "anteriores": (anterior or {}).get("anteriores", []) + saidas}


def coletar_tribunal(sigla: str, anterior: dict | None, hoje: str) -> dict:
    nome, pagina, oficial, minimo = TRIBUNAIS[sigla]
    r = comum.get(comum.sessao(), WIKI + pagina, timeout=60).json()
    lidos = ler_tabelas(r["parse"]["text"])
    if len(lidos) < minimo:
        raise RuntimeError(f"{sigla}: só {len(lidos)} ministros reconhecidos na tabela; mantendo a lista anterior")
    novo = atualizar(anterior, lidos, hoje)
    print(f"{sigla}: {len(novo['atuais'])} ministros")
    return {"nome": nome, "fonte": oficial, "wikipedia": WIKI_PAGINA + pagina, **novo}


def main() -> None:
    hoje = dt.date.today().isoformat()
    antigo = comum.ler(ARQUIVO) or {}
    tribunais = dict(antigo.get("tribunais", {}))

    def etapa(sigla):
        def f():
            tribunais[sigla] = coletar_tribunal(sigla, tribunais.get(sigla), hoje)
        return f

    comum.rodar_etapas("tribunais", [(s, etapa(s)) for s in TRIBUNAIS])
    comum.salvar(ARQUIVO, {"coletadoEm": hoje, "tribunais": tribunais})


if __name__ == "__main__":
    main()
