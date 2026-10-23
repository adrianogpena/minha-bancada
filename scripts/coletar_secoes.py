"""
Resume onde cada eleito foi votado, a partir dos ZIPs de votação por seção do TSE e da lista de
locais de votação (com latitude e longitude), baixados por scripts/baixar_tse.py. Guarda
dados/tse/secoes/<ano>/<UF>.json (vai para o git), com, por eleito (id da prestação, como em
coletar_contas.py; vice usa a chapa do titular):

    totalVotos  votos totais (no último turno disputado) e turno  número desse turno
    locaisDeVotacao  principais locais de votação: [nome, latitude, longitude, votos]
    municipios  principais municípios (só cargos estaduais e federais): [nome, votos]
    votosPorMunicipio  votos em todos os municípios (cargos estaduais e federais, menos presidente), para o mapa:
       [[código TSE do município, votos], ...]

Não guarda o endereço das escolas; o site mostra o local no mapa e a fonte.

Uso:
    python scripts/baixar_tse.py votacao_secao eleitorado_locais_votacao
    python scripts/coletar_secoes.py              # 2022 e 2024 (leva alguns minutos)
    python scripts/coletar_secoes.py --anos 2024

Fonte: https://dadosabertos.tse.jus.br (Votação por seção eleitoral; Eleitorado por local de votação)
"""

import argparse
import csv
import datetime as dt
import io
import json
import zipfile
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TSE = RAIZ / "dados" / "tse"
BRUTO = RAIZ / "dados" / "tse_bruto"
ANOS = [2022, 2024]
MUNICIPAIS = {"PREFEITO", "VICE-PREFEITO", "VEREADOR"}
TOP_LOCAIS = {"VEREADOR": 5, "PREFEITO": 10, "VICE-PREFEITO": 10}   # demais cargos: 10
TOP_MUNICIPIOS = 10
VERSAO = 2

csv.field_size_limit(1 << 24)


def ler_csv(zip_path: Path, filtro=None):
    """Devolve (colunas, linhas) de cada CSV do ZIP, sem montar dicionários (são dezenas de milhões de linhas)."""
    with zipfile.ZipFile(zip_path) as z:
        for nome in z.namelist():
            if nome.lower().endswith(".csv"):
                with z.open(nome) as f:
                    r = csv.reader(io.TextIOWrapper(f, encoding="latin-1", newline=""), delimiter=";")
                    cab = next(r)
                    yield {c: i for i, c in enumerate(cab)}, r


def coordenada(v: str) -> float | None:
    try:
        x = float(v)
    except ValueError:
        return None
    return round(x, 4) if x and abs(x) > 0.01 and x != -1 else None


def carregar_locais(ano: int) -> dict:
    """(UF, município, zona, local) -> (latitude, longitude)."""
    locais = {}
    for col, linhas in ler_csv(BRUTO / "eleitorado_locais_votacao" / f"eleitorado_local_votacao_{ano}.zip"):
        i = {k: col[k] for k in ("SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_LOCAL_VOTACAO", "NR_LATITUDE", "NR_LONGITUDE")}
        for l in linhas:
            k = (l[i["SG_UF"]], int(l[i["CD_MUNICIPIO"]]), int(l[i["NR_ZONA"]]), int(l[i["NR_LOCAL_VOTACAO"]]))
            if k not in locais:
                locais[k] = (coordenada(l[i["NR_LATITUDE"]]), coordenada(l[i["NR_LONGITUDE"]]))
    return locais


def eleitos_do_ano(ano: int) -> dict:
    """sq da prestação (titular, no caso de vice) -> (UF do arquivo, cargo do titular)."""
    alvo = {}
    for arq in sorted((TSE / str(ano)).glob("[A-Z][A-Z].json")):
        for e in json.loads(arq.read_text(encoding="utf-8")):
            alvo[e.get("sequencialChapa") or e["sequencial"]] = (e["uf"], e["cargo"].replace("VICE-", ""))
    return alvo


def coletar_ano(ano: int) -> None:
    alvo = eleitos_do_ano(ano)
    print(f"TSE seções {ano}: {len(alvo)} eleitos; carregando locais de votação")
    coords = carregar_locais(ano)
    total = defaultdict(int)       # (sq, turno) -> votos
    por_local = defaultdict(int)   # (sq, turno, uf, município, zona, local) -> votos
    nome_local = {}
    por_mun = defaultdict(int)     # (sq, turno, nome do município) -> votos
    por_cod = defaultdict(int)     # (sq, turno, código TSE do município) -> votos

    pasta_zips = BRUTO / "votacao_secao"
    for zip_path in sorted(pasta_zips.glob(f"votacao_secao_{ano}_*.zip")):
        print(f"  {zip_path.name}")
        for col, linhas in ler_csv(zip_path):
            sq_i, t_i, v_i = col["SQ_CANDIDATO"], col["NR_TURNO"], col["QT_VOTOS"]
            uf_i, mun_i, nm_i, z_i, loc_i, nl_i = (col["SG_UF"], col["CD_MUNICIPIO"], col["NM_MUNICIPIO"],
                                                   col["NR_ZONA"], col["NR_LOCAL_VOTACAO"], col["NM_LOCAL_VOTACAO"])
            for l in linhas:
                sq = l[sq_i]
                if sq not in alvo:
                    continue
                turno, votos = int(l[t_i]), int(l[v_i])
                total[(sq, turno)] += votos
                chave = (sq, turno, l[uf_i], int(l[mun_i]), int(l[z_i]), int(l[loc_i]))
                por_local[chave] += votos
                if chave not in nome_local:
                    nome_local[chave] = l[nl_i].strip()
                por_mun[(sq, turno, l[nm_i].strip())] += votos
                por_cod[(sq, turno, int(l[mun_i]))] += votos

    ultimo = {}
    for (sq, turno) in total:
        ultimo[sq] = max(ultimo.get(sq, 0), turno)
    locais_de = defaultdict(list)
    for chave, v in por_local.items():
        if ultimo.get(chave[0]) == chave[1] and v > 0:
            locais_de[chave[0]].append((v, chave))
    mun_de = defaultdict(list)
    for (sq, turno, nome), v in por_mun.items():
        if ultimo.get(sq) == turno and v > 0:
            mun_de[sq].append([nome, v])

    cod_de = defaultdict(list)
    for (sq, turno, cod), v in por_cod.items():
        if ultimo.get(sq) == turno and v > 0:
            cod_de[sq].append([cod, v])

    por_uf = defaultdict(dict)
    for sq, turno in ultimo.items():
        uf, cargo = alvo[sq]
        item = {"turno": turno, "totalVotos": total[(sq, turno)]}
        if cargo != "PRESIDENTE":
            top = sorted(locais_de[sq], key=lambda x: -x[0])[:TOP_LOCAIS.get(cargo, 10)]
            item["locaisDeVotacao"] = [[nome_local[c], *coords.get((c[2], c[3], c[4], c[5]), (None, None)), v] for v, c in top]
        if cargo not in MUNICIPAIS:
            item["municipios"] = sorted(mun_de[sq], key=lambda x: -x[1])[:TOP_MUNICIPIOS]
            if cargo != "PRESIDENTE":
                item["votosPorMunicipio"] = sorted(cod_de[sq], key=lambda x: -x[1])
        por_uf[uf][sq] = item

    pasta = TSE / "secoes" / str(ano)
    pasta.mkdir(parents=True, exist_ok=True)
    for antigo in pasta.glob("*.json"):
        antigo.unlink()
    for uf, mapa in por_uf.items():
        (pasta / f"{uf}.json").write_text(json.dumps(mapa, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (pasta / "_coleta.json").write_text(json.dumps({
        "coletadoEm": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "eleitos": sum(len(m) for m in por_uf.values()), "versao": VERSAO}), encoding="utf-8")
    print(f"  salvo em {pasta} ({sum(len(m) for m in por_uf.values())} eleitos)")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--anos", type=int, nargs="+", default=ANOS)
    for ano in p.parse_args().anos:
        coletar_ano(ano)


if __name__ == "__main__":
    main()
