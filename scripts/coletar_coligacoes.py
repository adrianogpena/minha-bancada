"""
Resume as coligações, federações e partidos isolados de cada cargo e local da eleição, com a
situação da legenda, a partir dos ZIPs do TSE baixados por scripts/baixar_tse.py. Guarda
dados/tse/coligacoes/<ano>/<UF>.json (vai para o git), chaveado por "CARGO|código do local".

Só guarda o partido de quem foi eleito (dados/tse/<ano>/<UF>.json, de coletar_tse.py), para o arquivo
não crescer com todos os partidos de todos os municípios.

Cada local: {"coligacoes": [[tipo, nome, composição, situação], ...], "coligacaoDoPartido": {sigla do partido: índice em "coligacoes"}}.
tipo: C coligação, F federação, I partido isolado. Os suplentes de senador ficam de fora.

Uso:
    python scripts/baixar_tse.py consulta_coligacao
    python scripts/coletar_coligacoes.py              # 2022 e 2024
    python scripts/coletar_coligacoes.py --anos 2024

Fonte: https://dadosabertos.tse.jus.br (Consulta de coligações)
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
BRUTO = RAIZ / "dados" / "tse_bruto" / "consulta_coligacao"
SAIDA = RAIZ / "dados" / "tse" / "coligacoes"
ANOS = [2022, 2024]
VERSAO = 1
TIPOS = {"COLIGAÇÃO": "C", "FEDERAÇÃO": "F", "PARTIDO ISOLADO": "I"}

csv.field_size_limit(1 << 24)


def limpo(v: str) -> str:
    return "" if v == "#NULO" else v


def eleitos(ano: int, uf: str) -> set:
    arq = RAIZ / "dados" / "tse" / str(ano) / f"{uf}.json"
    lista = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else []
    return {(e["cargo"], e["unidadeEleitoral"], e.get("partido")) for e in lista}


def coletar_ano(ano: int) -> None:
    pasta = SAIDA / str(ano)
    pasta.mkdir(parents=True, exist_ok=True)
    for antigo in pasta.glob("*.json"):
        antigo.unlink()
    locais = 0
    with zipfile.ZipFile(BRUTO / f"consulta_coligacao_{ano}.zip") as z:
        for nome in sorted(z.namelist()):
            if not nome.lower().endswith(".csv") or nome.upper().endswith("_BRASIL.CSV"):
                continue
            uf = nome.rsplit("_", 1)[1][:2]
            quero = eleitos(ano, uf)
            mapa = defaultdict(lambda: {"coligacoes": [], "coligacaoDoPartido": {}})
            with z.open(nome) as f:
                for l in csv.DictReader(io.TextIOWrapper(f, encoding="latin-1", newline=""), delimiter=";"):
                    cargo = l["DS_CARGO"].upper()
                    if "SUPLENTE" in cargo:
                        continue
                    if (cargo, l["SG_UE"], l["SG_PARTIDO"]) not in quero:
                        continue
                    d = mapa[f"{cargo}|{l['SG_UE']}"]
                    c = [TIPOS.get(l["TP_AGREMIACAO"].upper(), "I"), limpo(l["NM_COLIGACAO"]),
                         limpo(l["DS_COMPOSICAO_COLIGACAO"]), l["DS_SITUACAO"].capitalize()]
                    if c not in d["coligacoes"]:
                        d["coligacoes"].append(c)
                    d["coligacaoDoPartido"][l["SG_PARTIDO"]] = d["coligacoes"].index(c)
            (pasta / f"{uf}.json").write_text(json.dumps(mapa, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            locais += len(mapa)
    (pasta / "_coleta.json").write_text(json.dumps({
        "coletadoEm": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"), "versao": VERSAO}), encoding="utf-8")
    print(f"TSE coligações {ano}: {locais} cargos/locais")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--anos", type=int, nargs="+", default=ANOS)
    for ano in p.parse_args().anos:
        coletar_ano(ano)


if __name__ == "__main__":
    main()
