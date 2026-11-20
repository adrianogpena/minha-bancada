"""Relatório de candidatos ao glossário (site/assets/js/glossario.js). Offline; só lê, não altera nada.

Lê os textos que o site mostra (site/dados/ e site/*.html) e lista siglas em caixa alta e palavras
suspeitas de jargão que ainda não estão cobertas pelas variantes do glossário, com ocorrências e um exemplo.
Uso: python scripts/glossario_candidatos.py [--saida arquivo]
"""
import argparse
import html
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

SUSPEITOS = ["prejudicad", "ressalvad", "terminativ", "apensad", "desarquivad", "sobrestad", "suplente", "licença",
             "CEAP", "empenho", "liquidação", "restos a pagar", "quórum", "obstrução", "art. 17", "conclusiv",
             "promulga", "veto", "tramitação em conjunto", "regime de urgência", "requerimento", "indicação",
             "PRONTPAUT", "AGDESP"]
UFS = {"AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
       "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"}
CHAVES_ROTULO = {"cargo", "cargoTse", "categoria", "tipo", "rotulo", "situacao", "descricao", "funcao"}
SIGLA = re.compile(r"(?<![\wÀ-ÿ])[A-ZÀ-Ý]{2,6}(?![\wÀ-ÿ])")


def simples(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c)).lower()


def carregar(caminho):
    try:
        return json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def textos_json(obj, so_chaves=None, chave=None):
    """Todas as strings de um JSON (ou só as de certas chaves)."""
    if isinstance(obj, str):
        if so_chaves is None or chave in so_chaves:
            yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from textos_json(v, so_chaves, k)
    elif isinstance(obj, list):
        for v in obj:
            yield from textos_json(v, so_chaves, chave)


def texto_html(conteudo):
    conteudo = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", conteudo)
    return html.unescape(re.sub(r"<[^>]+>", " ", conteudo))


def coletar(site):
    """Devolve [(origem, texto)] com o que o site mostra."""
    dados = site / "dados"
    saida = []

    def juntar(origem, textos):
        saida.extend((origem, " ".join(t.split())) for t in textos if t and t.strip())

    props = carregar(dados / "proposicoes.json")
    if isinstance(props, list):
        juntar("proposicoes.json (situação)", (p.get("s") for p in props if isinstance(p, dict)))
    for nome in ("votacoes.json", "votacoes_senado.json"):
        lista = carregar(dados / nome)
        if isinstance(lista, list):
            juntar(f"{nome} (descrição)", (v.get("descricao") for v in lista if isinstance(v, dict)))
    for arq in sorted((dados / "tramitacao_senado").glob("*.json")):
        d = carregar(arq)
        if not isinstance(d, dict):
            continue
        juntar("tramitacao_senado (informe)", (i[2] for i in d.get("informes", []) if isinstance(i, list) and len(i) > 2))
        juntar("tramitacao_senado (situação)", (s[3] for s in d.get("situacoes", []) if isinstance(s, list) and len(s) > 3))
    for arq in sorted((dados / "tramitacao").glob("*.json")):
        d = carregar(arq)
        if isinstance(d, dict):
            juntar("tramitacao (evento)", textos_json(d.get("eventos", [])))
    for sub in ("nucleo", "deputado"):
        for arq in sorted((dados / sub).glob("*.json")):
            d = carregar(arq)
            if d is not None:
                juntar(f"{sub} (rótulo)", textos_json(d, CHAVES_ROTULO))
    for arq in sorted(site.glob("*.html")):
        juntar(f"{arq.name} (página)", texto_html(arq.read_text(encoding="utf-8")).splitlines())
    return saida


def variantes_cobertas(site):
    js = site / "assets/js/glossario.js"
    if not js.exists():
        return set()
    achadas = set()
    for bloco in re.findall(r"variantes:\s*\[(.*?)\]", js.read_text(encoding="utf-8"), re.S):
        achadas.update(re.findall(r'"([^"]+)"', bloco))
    return achadas


def siglas_excluidas(site):
    excluidas = set(UFS)
    partidos = carregar(site / "dados/nucleo/partidos.json")
    for t in textos_json(partidos if partidos is not None else []):
        if SIGLA.fullmatch(t):
            excluidas.add(t)
    if isinstance(partidos, dict):
        excluidas.update(k for k in partidos if SIGLA.fullmatch(k))
    return excluidas


def exemplo(texto, ini, fim):
    a = max(0, ini - 50)
    trecho = texto[a:a + 120]
    return ("…" if a else "") + trecho


def candidatos(site):
    textos = coletar(site)
    cobertas = variantes_cobertas(site)
    cobertas_simples = {simples(v) for v in cobertas}
    excluidas = siglas_excluidas(site)
    contagem = defaultdict(lambda: [0, "", ""])

    def registrar(chave, origem, texto, ini, fim):
        c = contagem[chave]
        c[0] += 1
        if not c[1]:
            c[1], c[2] = origem, exemplo(texto, ini, fim)

    for origem, texto in textos:
        for m in SIGLA.finditer(texto):
            s = m.group()
            if s in excluidas or s in cobertas or s in SUSPEITOS or texto.isupper():
                continue
            registrar(s, origem, texto, m.start(), m.end())
        norm = simples(texto)
        for sus in SUSPEITOS:
            chave = simples(sus)
            if any(chave in c for c in cobertas_simples):
                continue
            for m in re.finditer(r"(?<![a-z0-9])" + re.escape(chave), norm):
                registrar(sus, origem, texto, m.start(), m.end())
    return sorted(((n, t, o, e) for t, (n, o, e) in contagem.items()), key=lambda x: (-x[0], x[1]))


def relatorio(site):
    linhas = ["ocorrências\ttermo\torigem\texemplo"]
    linhas += [f"{n}\t{t}\t{o}\t{e}" for n, t, o, e in candidatos(site)]
    return "\n".join(linhas) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--saida", help="grava o relatório neste arquivo em vez de imprimir")
    ap.add_argument("--site", default=str(RAIZ / "site"), help="pasta do site (padrão: site/)")
    args = ap.parse_args()
    texto = relatorio(Path(args.site))
    if args.saida:
        Path(args.saida).write_text(texto, encoding="utf-8")
    else:
        print(texto, end="")


if __name__ == "__main__":
    main()
