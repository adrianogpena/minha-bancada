"""
Refaz dados/municipios_ibge.json (código TSE do município -> código IBGE de 7 dígitos), que o
mapa do site usa para ligar a eleição à malha do IBGE.

Os nomes e códigos TSE vêm do arquivo de detalhe da votação por município e zona (já baixado por
scripts/baixar_tse.py detalhe_votacao_munzona); os códigos IBGE vêm da API de localidades do IBGE.
A ligação é por UF + nome sem acento; o que não casa pelo nome fica em AJUSTES ou é listado.

Uso:
    python scripts/baixar_tse.py detalhe_votacao_munzona
    python scripts/gerar_municipios_ibge.py

Fontes:
    https://cdn.tse.jus.br/estatistica/sead/odsele/detalhe_votacao_munzona/detalhe_votacao_munzona_<ano>.zip
    https://servicodados.ibge.gov.br/api/v1/localidades/municipios
"""

import csv
import gzip
import io
import json
import re
import sys
import unicodedata
import urllib.request
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ZIPS = RAIZ / "dados" / "tse_bruto" / "detalhe_votacao_munzona"
DESTINO = RAIZ / "dados" / "municipios_ibge.json"
IBGE = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
ANOS = [2024, 2022]   # 2022 cobre o DF, que não tem eleição municipal

# (UF, nome no TSE sem acento) -> nome no IBGE sem acento, para grafias que diferem
AJUSTES = {
    ("BA", "camaca"): "camacan",
    ("MG", "barao de monte alto"): "barao do monte alto",
    ("MG", "dona eusebia"): "dona euzebia",
    ("MG", "sao thome das letras"): "sao tome das letras",
    ("MT", "santo antonio do leverger"): "santo antonio de leverger",
    ("PA", "eldorado dos carajas"): "eldorado do carajas",
    ("PA", "santa isabel do para"): "santa izabel do para",
    ("PR", "munhoz de mello"): "munhoz de melo",
    ("RN", "boa saude"): "januario cicco",
    ("RO", "alvorada do oeste"): "alvorada d oeste",
    ("RO", "espigao do oeste"): "espigao d oeste",
    ("RR", "sao luiz"): "sao luiz do anaua",
    ("SE", "amparo de sao francisco"): "amparo do sao francisco",
    ("SP", "sao luis do paraitinga"): "sao luiz do paraitinga",
}

csv.field_size_limit(1 << 24)


def chave(nome: str) -> str:
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def municipios_tse() -> dict:
    """(UF, nome) -> código TSE, com os nomes como estão no TSE."""
    achados = {}
    for ano in ANOS:
        caminho = ZIPS / f"detalhe_votacao_munzona_{ano}.zip"
        if not caminho.exists():
            sys.exit(f"falta {caminho}; rode: python scripts/baixar_tse.py detalhe_votacao_munzona")
        with zipfile.ZipFile(caminho) as z:
            for nome in z.namelist():
                if not nome.lower().endswith(".csv") or nome.upper().endswith(("BRASIL.CSV", "_ZZ.CSV")):
                    continue
                with z.open(nome) as f:
                    bruto = f.read()
                try:
                    texto = bruto.decode("utf-8")
                except UnicodeDecodeError:
                    texto = bruto.decode("latin-1")
                if True:
                    for l in csv.DictReader(io.StringIO(texto, newline=""), delimiter=";"):
                        if l["SG_UF"] == "ZZ":
                            continue
                        achados.setdefault((l["SG_UF"], l["NM_MUNICIPIO"].strip()), l["CD_MUNICIPIO"].zfill(5))
    return achados


def main() -> None:
    req = urllib.request.Request(IBGE, headers={"Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=60) as r:
        corpo = r.read()
    ibge = json.loads(gzip.decompress(corpo) if corpo[:2] == bytes([0x1F, 0x8B]) else corpo)
    por_nome = {}
    for m in ibge:
        uf = m["microrregiao"]["mesorregiao"]["UF"]["sigla"] if m.get("microrregiao") else m["regiao-imediata"]["regiao-intermediaria"]["UF"]["sigla"]
        por_nome[(uf, chave(m["nome"]))] = str(m["id"])

    mapa, sem_par = {}, []
    for (uf, nome), cod in sorted(municipios_tse().items()):
        k = (uf, AJUSTES.get((uf, chave(nome)), chave(nome)))
        if k in por_nome:
            mapa[cod] = por_nome[k]
        else:
            sem_par.append((uf, nome, cod))
    for uf, nome, cod in sem_par:
        print(f"sem par no IBGE: {uf} {nome} (TSE {cod})")

    antigo = json.loads(DESTINO.read_text(encoding="utf-8")) if DESTINO.exists() else {}
    diferentes = {c: (antigo[c], mapa[c]) for c in mapa if c in antigo and antigo[c] != mapa[c]}
    print(f"{len(mapa)} municípios; no arquivo antigo: {len(antigo)}; "
          f"só no antigo: {len(set(antigo) - set(mapa))}; só no novo: {len(set(mapa) - set(antigo))}; códigos diferentes: {len(diferentes)}")
    for c in sorted(set(antigo) - set(mapa)):
        print(f"  só no antigo: {c} -> {antigo[c]}")
    for c in sorted(set(mapa) - set(antigo)):
        print(f"  só no novo: {c} -> {mapa[c]}")
    for c, (a, n) in list(diferentes.items())[:10]:
        print(f"  {c}: antigo {a}, novo {n}")
    if "--gravar" in sys.argv:
        DESTINO.write_text(json.dumps(dict(sorted(mapa.items())), separators=(",", ":")), encoding="utf-8")
        print("gravado em", DESTINO)


if __name__ == "__main__":
    main()
