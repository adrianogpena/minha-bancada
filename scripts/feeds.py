"""
Feeds RSS do "Fique informado": um arquivo por local (Brasil, estado, capital) e por político acompanhável,
em site/feeds/<código>.xml. Cada dia com novidade no escopo vira um item. Não guarda nenhum dado de leitor:
quem assina é o leitor de RSS dele, que busca o arquivo estático.

Os códigos são os mesmos do campo "a" de site/dados/indice/<UF>.json (ver gerar_politicos.py):
    BR  UF:<sigla>  MUN:<sigla> (capital)  pres  dep:<id da Câmara>  gov:<UF>  est:<UF>:<id no SAPL>  pref:<UF>
O nome do arquivo troca ":" por "-" (UF:AC -> UF-AC.xml).

O histórico vem do git: um commit "Dados atualizados em AAAA-MM-DD" por dia, dos últimos DIAS dias.
Chamado depois de scripts/gerar.py (usa site/dados/); precisa de histórico git (git fetch --shallow-since).

Uso:
    python scripts/feeds.py [--dias 14]
"""

import argparse
import html
import json
from collections import defaultdict
from datetime import datetime, UTC
from email.utils import format_datetime

import resumo_email as r

SITE_DADOS = r.RAIZ / "site" / "dados"
SAIDA = r.RAIZ / "site" / "feeds"
INDICE = SITE_DADOS / "indice"
UFS = {"AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas", "BA": "Bahia", "CE": "Ceará", "DF": "Distrito Federal",
       "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão", "MT": "Mato Grosso", "MS": "Mato Grosso do Sul", "MG": "Minas Gerais",
       "PA": "Pará", "PB": "Paraíba", "PR": "Paraná", "PE": "Pernambuco", "PI": "Piauí", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
       "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima", "SC": "Santa Catarina", "SP": "São Paulo", "SE": "Sergipe", "TO": "Tocantins"}


def deputados_por_uf() -> dict[str, set[int]]:
    """UF -> ids (da Câmara) dos deputados federais, a partir do índice que gerar.py acabou de montar."""
    mapa = {}
    for arq in INDICE.glob("[A-Z][A-Z].json"):
        if arq.stem == "BR":
            continue
        itens = json.loads(arq.read_text(encoding="utf-8"))
        mapa[arq.stem] = {int(x["id"]) for x in itens if str(x.get("pagina", "")).startswith("deputado.html")}
    return mapa


def selecionar(d: dict, regras: set[str], deps_uf: dict[str, set[int]]) -> dict:
    """Parte de coletar() que cabe nas regras de um assinante, no mesmo formato."""
    br = "BR" in regras
    ufs = {x[3:] for x in regras if x.startswith("UF:")}
    deps = {int(x[4:]) for x in regras if x.startswith("dep:")}
    for uf in ufs:
        deps |= deps_uf.get(uf, set())

    def por_uf(chave: str, tudo, itens=lambda uf, m: False):
        """tudo(uf) diz se o estado inteiro entra; senão, entra o que `itens` aprovar."""
        novas, mudou = d[chave]
        n, m = defaultdict(list), defaultdict(list)
        for uf in set(novas) | set(mudou):
            if tudo(uf):
                n[uf], m[uf] = novas.get(uf, []), mudou.get(uf, [])
            else:
                n[uf] = [x for x in novas.get(uf, []) if itens(uf, x)]
                m[uf] = [x for x in mudou.get(uf, []) if itens(uf, x[0])]
        return (defaultdict(list, {k: v for k, v in n.items() if v or m[k]}),
                defaultdict(list, {k: v for k, v in m.items() if v or n.get(k)}))

    pres = br or "pres" in regras
    return {
        **d,
        "camara": [i for i in d["camara"] if br or deps & set(i["idsDeputados"])],
        "senado": d["senado"] if br else (0, 0),
        "detalhe": (0, 0),
        "executivo": d["executivo"] if pres else [],
        "executivo_situacao": d["executivo_situacao"] if pres else [],
        "estaduais": por_uf("estaduais", lambda uf: uf in ufs,
                            lambda uf, m: any(f"est:{uf}:{p}" in regras for p in m.get("idsDeputados", []))),
        "governo": por_uf("governo", lambda uf: uf in ufs or f"gov:{uf}" in regras),
        "municipais": por_uf("municipais", lambda uf: uf in ufs or f"MUN:{uf}" in regras or f"pref:{uf}" in regras),
        "votacoes": [uf for uf in d["votacoes"] if uf in ufs],
        "tse": [],
    }


def vazio(d: dict) -> bool:
    return not r.linhas(d)


def arquivo(codigo: str) -> str:
    return codigo.replace(":", "-") + ".xml"


def rotulos() -> dict[str, str]:
    """código -> nome do feed, a partir do que o site já gerou (cobertura.json e índice dos políticos)."""
    cob = json.loads((SITE_DADOS / "cobertura.json").read_text(encoding="utf-8"))
    mapa = {"BR": "Brasil: Câmara, Senado e Presidência"}
    mapa |= {f"UF:{u}": f"Estado: {UFS.get(u, u)}" for u in cob["estados"]}
    mapa |= {f"MUN:{u}": f"Capital: {m} ({u})" for u, m in cob["capitais"].items()}
    for arq in sorted(INDICE.glob("[A-Z][A-Z].json")):
        for x in json.loads(arq.read_text(encoding="utf-8")):
            if x.get("codigoFeed"):
                mapa.setdefault(x["codigoFeed"], f"{x['cargo']}: {x['nome']}")
    return mapa


def dias(n: int) -> list[tuple[str, str, str]]:
    """[(antes, depois, data)] dos últimos n dias com commit diário, do mais novo ao mais antigo. Vários commits no mesmo dia
    (execução manual além da agendada) viram um intervalo só, do pai do primeiro ao último, para o dia não repetir item."""
    por_dia = {}
    for linha in r.git("log", "--grep=^Dados atualizados em", "--format=%H %cs", "-n50").splitlines():
        commit, data = linha.split()
        try:
            r.git("rev-parse", "--verify", "-q", f"{commit}~1")
        except Exception:
            continue   # histórico raso: sem o commit anterior não há o que comparar
        por_dia.setdefault(data, []).append(commit)
    return [(f"{cs[-1]}~1", cs[0], data) for data, cs in list(por_dia.items())[:n]]


def item(titulo: str, data: str, codigo: str, corpo: str) -> str:
    """Um dia do feed; o link leva à página do histórico daquele dia, já filtrada pelo local ou político do feed."""
    quando = datetime.fromisoformat(data).replace(hour=12, tzinfo=UTC)
    return (f"<item><title>{html.escape(titulo)}</title><link>{html.escape(r.link_historico(data, [codigo]))}</link>"
            f"<guid isPermaLink=\"false\">minha-bancada-{html.escape(codigo)}-{data}</guid>"
            f"<pubDate>{format_datetime(quando)}</pubDate><description>{html.escape(corpo)}</description></item>")


def feed(codigo: str, nome: str, itens: list[str]) -> str:
    return ("<?xml version=\"1.0\" encoding=\"UTF-8\"?><rss version=\"2.0\"><channel>"
            f"<title>Minha Bancada — {html.escape(nome)}</title><link>{r.SITE}informado.html</link>"
            f"<description>O que mudou, por dia, em: {html.escape(nome)}</description><language>pt-BR</language>"
            + "".join(itens) + "</channel></rss>")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dias", type=int, default=14)
    a = p.parse_args()
    nomes, deps_uf = rotulos(), deputados_por_uf()
    itens = defaultdict(list)
    lista = dias(a.dias)
    for antes, depois, data in lista:
        d = r.coletar(antes, depois)
        for codigo in nomes:
            parte = selecionar(d, {codigo}, deps_uf)
            if vazio(parte):
                continue
            h, _ = r.montar(parte, r.resumo_longo(parte), detalhes=r.link_historico(data, [codigo]), sumario=False)
            itens[codigo].append(item(f"{data[8:]}/{data[5:7]}: {r.resumo_curto(parte)}", data, codigo, h))
    SAIDA.mkdir(parents=True, exist_ok=True)
    for antigo in SAIDA.glob("*.xml"):
        antigo.unlink()
    for codigo, nome in nomes.items():
        (SAIDA / arquivo(codigo)).write_text(feed(codigo, nome, itens[codigo]), encoding="utf-8")
    print(f"Feeds: {len(nomes)} arquivos, {sum(1 for v in itens.values() if v)} com itens, {len(lista)} dias lidos")


if __name__ == "__main__":
    main()
