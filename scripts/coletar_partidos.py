"""
Resume os votos de cada partido (legenda e nominais) por cargo proporcional e local da eleição,
a partir dos ZIPs do TSE baixados por scripts/baixar_tse.py. Guarda
dados/tse/partidos/<ano>/<UF>.json (vai para o git), chaveado por "CARGO|código do local"
(município para vereador; UF para deputados). Só cargos proporcionais.

Cada local: {"totalVotos": votos válidos dos partidos, "partidos": {sigla: [legenda, nominais, federação]}}.
Legenda = QT_TOTAL_VOTOS_LEG_VALIDOS; nominais = QT_VOTOS_NOMINAIS_VALIDOS.

Uso:
    python scripts/baixar_tse.py votacao_partido_munzona
    python scripts/coletar_partidos.py              # 2022 e 2024
    python scripts/coletar_partidos.py --anos 2024

Fonte: https://dadosabertos.tse.jus.br (Votação por partido por município e zona)
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
BRUTO = RAIZ / "dados" / "tse_bruto" / "votacao_partido_munzona"
SAIDA = RAIZ / "dados" / "tse" / "partidos"
ANOS = [2022, 2024]
VERSAO = 1
PROPORCIONAIS = {"DEPUTADO FEDERAL", "DEPUTADO ESTADUAL", "DEPUTADO DISTRITAL", "VEREADOR"}

csv.field_size_limit(1 << 24)


def inteiro(v: str) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def coletar_ano(ano: int) -> None:
    pasta = SAIDA / str(ano)
    pasta.mkdir(parents=True, exist_ok=True)
    for antigo in pasta.glob("*.json"):
        antigo.unlink()
    locais = 0
    with zipfile.ZipFile(BRUTO / f"votacao_partido_munzona_{ano}.zip") as z:
        for nome in sorted(z.namelist()):
            if not nome.lower().endswith(".csv") or nome.upper().endswith("_BRASIL.CSV"):
                continue
            mapa = defaultdict(lambda: {"totalVotos": 0, "partidos": {}})
            with z.open(nome) as f:
                for l in csv.DictReader(io.TextIOWrapper(f, encoding="latin-1", newline=""), delimiter=";"):
                    cargo = l["DS_CARGO"].upper()
                    if cargo not in PROPORCIONAIS:
                        continue
                    leg, nom = inteiro(l["QT_TOTAL_VOTOS_LEG_VALIDOS"]), inteiro(l["QT_VOTOS_NOMINAIS_VALIDOS"])
                    d = mapa[f"{cargo}|{l['SG_UE']}"]
                    d["totalVotos"] += leg + nom
                    p = d["partidos"].setdefault(l["SG_PARTIDO"], [0, 0, "" if l["SG_FEDERACAO"] == "#NULO" else l["SG_FEDERACAO"]])
                    p[0] += leg
                    p[1] += nom
            if mapa:
                uf = nome.rsplit("_", 1)[1][:2]
                (pasta / f"{uf}.json").write_text(json.dumps(mapa, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
                locais += len(mapa)
    (pasta / "_coleta.json").write_text(json.dumps({
        "coletadoEm": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "versao": VERSAO}), encoding="utf-8")
    print(f"TSE partidos {ano}: {locais} cargos/locais")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--anos", type=int, nargs="+", default=ANOS)
    for ano in p.parse_args().anos:
        coletar_ano(ano)


if __name__ == "__main__":
    main()
