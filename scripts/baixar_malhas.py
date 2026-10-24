"""
Baixa do IBGE as malhas do mapa (Brasil por estado e cada estado por município)
para site/geo/, para o mapa não depender da API do IBGE no navegador.

Uso:
    python scripts/baixar_malhas.py

Fonte: https://servicodados.ibge.gov.br/api/v3/malhas
"""

import json
import sys
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "site" / "geo"
BASE = "https://servicodados.ibge.gov.br/api/v3/malhas"
PARAMS = {"formato": "application/vnd.geo+json", "qualidade": "minima"}
# DF fica de fora: o site usa geo/df_ras.json (não tem municípios).
CODIGOS_UF = [11, 12, 13, 14, 15, 16, 17, 21, 22, 23, 24, 25, 26, 27, 28, 29, 31, 32, 33, 35, 41, 42, 43, 50, 51, 52]


def baixar(url, intrarregiao, arquivo):
    r = requests.get(url, params={**PARAMS, "intrarregiao": intrarregiao}, timeout=60)
    r.raise_for_status()
    dados = r.json()
    if not dados.get("features"):
        raise ValueError(f"{url}: malha sem features")
    DESTINO.mkdir(parents=True, exist_ok=True)
    (DESTINO / arquivo).write_text(json.dumps(dados, separators=(",", ":")), encoding="utf-8")
    print(f"{arquivo}: {len(dados['features'])} áreas")


def main():
    baixar(f"{BASE}/paises/BR", "UF", "br.json")
    falhas = []
    for cod in CODIGOS_UF:
        try:
            baixar(f"{BASE}/estados/{cod}", "municipio", f"uf_{cod}.json")
        except (requests.RequestException, ValueError) as e:
            falhas.append(cod)
            print(f"uf_{cod}.json: falhou ({e})", file=sys.stderr)
    if falhas:
        sys.exit(f"Falharam os estados {falhas}; rode de novo.")


if __name__ == "__main__":
    main()
