"""
Resume, para cada cargo e local da eleição, o comparecimento (aptos, compareceram, abstenções,
brancos, nulos, votos válidos) e as vagas em disputa, a partir dos ZIPs do TSE baixados por
scripts/baixar_tse.py. Guarda dados/tse/disputa/<ano>/<UF>.json (vai para o git), chaveado
por "CARGO|código do local" (município nos cargos municipais; UF ou BR nos demais).

Uso:
    python scripts/baixar_tse.py detalhe_votacao_munzona consulta_vagas
    python scripts/coletar_disputa.py              # 2022 e 2024
    python scripts/coletar_disputa.py --anos 2024

Fonte: https://dadosabertos.tse.jus.br (Detalhe da votação por município e zona; Vagas)
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
BRUTO = RAIZ / "dados" / "tse_bruto"
SAIDA = RAIZ / "dados" / "tse" / "disputa"
ANOS = [2022, 2024]
VERSAO = 1

csv.field_size_limit(1 << 24)


def linhas(zip_path: Path):
    """Lê o CSV de cada UF (o *_BRASIL.csv repete os dados dos outros e fica de fora)."""
    with zipfile.ZipFile(zip_path) as z:
        for nome in z.namelist():
            if nome.lower().endswith(".csv") and not nome.upper().endswith("_BRASIL.CSV"):
                with z.open(nome) as f:
                    yield from csv.DictReader(io.TextIOWrapper(f, encoding="latin-1", newline=""), delimiter=";")


def inteiro(v: str) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def coletar_ano(ano: int) -> None:
    dados = defaultdict(lambda: {"turnos": {}, "vagas": None})   # (uf, cargo, ue) -> dados
    for l in linhas(BRUTO / "detalhe_votacao_munzona" / f"detalhe_votacao_munzona_{ano}.zip"):
        t = dados[(l["SG_UF"], l["DS_CARGO"].upper(), l["SG_UE"])]["turnos"].setdefault(
            l["NR_TURNO"], dict.fromkeys(("aptos", "comparecimento", "abstencoes", "brancos", "nulos", "validos"), 0))
        t["aptos"] += inteiro(l["QT_APTOS"])
        t["comparecimento"] += inteiro(l["QT_COMPARECIMENTO"])
        t["abstencoes"] += inteiro(l["QT_ABSTENCOES"])
        t["brancos"] += inteiro(l["QT_VOTOS_BRANCOS"])
        t["nulos"] += inteiro(l["QT_TOTAL_VOTOS_NULOS"])
        t["validos"] += inteiro(l["QT_TOTAL_VOTOS_VALIDOS"])
    for l in linhas(BRUTO / "consulta_vagas" / f"consulta_vagas_{ano}.zip"):
        dados[(l["SG_UF"], l["DS_CARGO"].upper(), l["SG_UE"])]["vagas"] = inteiro(l["QT_VAGA"])

    por_uf = defaultdict(dict)
    for (uf, cargo, ue), d in dados.items():
        por_uf[uf][f"{cargo}|{ue}"] = d
    pasta = SAIDA / str(ano)
    pasta.mkdir(parents=True, exist_ok=True)
    for antigo in pasta.glob("*.json"):
        antigo.unlink()
    for uf, mapa in por_uf.items():
        (pasta / f"{uf}.json").write_text(json.dumps(mapa, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (pasta / "_coleta.json").write_text(json.dumps({
        "coletadoEm": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "versao": VERSAO}), encoding="utf-8")
    print(f"TSE disputa {ano}: {len(dados)} cargos/locais em {len(por_uf)} arquivos")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--anos", type=int, nargs="+", default=ANOS)
    for ano in p.parse_args().anos:
        coletar_ano(ano)


if __name__ == "__main__":
    main()
