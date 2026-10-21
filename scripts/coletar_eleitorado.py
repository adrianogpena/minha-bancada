"""
Resume o perfil do eleitorado (quantos eleitores, por faixa etária, gênero e escolaridade) de cada
município e estado, a partir dos ZIPs do TSE baixados por scripts/baixar_tse.py. Guarda
dados/tse/eleitorado/<ano>/<UF>.json (vai para o git), chaveado pelo código TSE do município
("_uf" = total do estado). ZZ é o eleitorado do exterior.

Uso:
    python scripts/baixar_tse.py perfil_eleitorado
    python scripts/coletar_eleitorado.py              # 2022 e 2024
    python scripts/coletar_eleitorado.py --anos 2024

Cada resumo: {"total": total, "porGenero": [masculino, feminino], "porFaixaEtaria": [8 faixas etárias], "porEscolaridade": [8 graus de escolaridade]}.
Faixas e graus: FAIXAS e ESCOLARIDADE, em app.js. "Inválida" (idade) e "não informado" (gênero) só entram no total.

Fonte: https://dadosabertos.tse.jus.br (Eleitorado: perfil do eleitorado)
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
BRUTO = RAIZ / "dados" / "tse_bruto" / "perfil_eleitorado"
SAIDA = RAIZ / "dados" / "tse" / "eleitorado"
ANOS = [2022, 2024]
VERSAO = 1

csv.field_size_limit(1 << 24)

# CD_FAIXA_ETARIA -> índice da faixa (16-17, 18-24, 25-34, 35-44, 45-54, 55-64, 65-74, 75+)
LIMITES = (18, 25, 35, 45, 55, 65, 75)


def faixa(cd: int) -> int | None:
    if cd < 1600:
        return None
    # o código é idade inicial*100 + idade final (ex.: 2529); 9999 = 100 anos ou mais
    return sum(cd // 100 >= lim for lim in LIMITES)


def novo() -> dict:
    return {"total": 0, "porGenero": [0, 0], "porFaixaEtaria": [0] * 8, "porEscolaridade": [0] * 8}


def somar(r: dict, l: dict) -> None:
    n = int(l["QT_ELEITORES"])
    r["total"] += n
    if l["CD_GENERO"] in ("2", "4"):
        r["porGenero"][0 if l["CD_GENERO"] == "2" else 1] += n
    f = faixa(int(l["CD_FAIXA_ETARIA"]))
    if f is not None:
        r["porFaixaEtaria"][f] += n
    e = int(l["CD_GRAU_ESCOLARIDADE"])
    if 1 <= e <= 8:
        r["porEscolaridade"][e - 1] += n


def coletar_ano(ano: int) -> None:
    pasta = SAIDA / str(ano)
    pasta.mkdir(parents=True, exist_ok=True)
    for antigo in pasta.glob("*.json"):
        antigo.unlink()
    total = 0
    with zipfile.ZipFile(BRUTO / f"perfil_eleitorado_{ano}.zip") as z:
        for nome in sorted(z.namelist()):
            if not nome.lower().endswith(".csv") or nome.upper().endswith("_BRASIL.CSV"):
                continue
            uf = nome.rsplit("_", 1)[1][:2]
            mapa = defaultdict(novo)
            with z.open(nome) as f:
                for l in csv.DictReader(io.TextIOWrapper(f, encoding="latin-1", newline=""), delimiter=";"):
                    somar(mapa[l["CD_MUNICIPIO"]], l)
                    somar(mapa["_uf"], l)
            (pasta / f"{uf}.json").write_text(json.dumps(mapa, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            total += len(mapa) - 1
    (pasta / "_coleta.json").write_text(json.dumps({
        "coletadoEm": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "versao": VERSAO}), encoding="utf-8")
    print(f"TSE eleitorado {ano}: {total} municípios")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--anos", type=int, nargs="+", default=ANOS)
    for ano in p.parse_args().anos:
        coletar_ano(ano)


if __name__ == "__main__":
    main()
