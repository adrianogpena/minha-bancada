"""
Resume a prestação de contas de campanha de cada eleito (receitas, despesas, principais
doadores) a partir do ZIP do TSE baixado por scripts/baixar_tse.py, e guarda um JSON por
UF em dados/tse/contas/<ano>/<UF>.json (vai para o git; o ZIP em dados/tse_bruto/ não).

Só roda na sua máquina: o ZIP tem 0,5 a 1,3 GB e anos encerrados não mudam. O Actions
só lê os JSONs resumidos. Não guarda CPF de doadores, só o nome que consta na prestação. Os doadores originários
(arquivo receitas_candidatos_doador_originario) mostram quem está por trás dos repasses de
partido e de outros candidatos.

Uso:
    python scripts/baixar_tse.py prestacao_contas
    python scripts/coletar_contas.py                # 2022 e 2024
    python scripts/coletar_contas.py --anos 2024

Fonte: https://dadosabertos.tse.jus.br (Prestação de contas eleitorais)
"""

import argparse
import csv
import datetime as dt
import io
import json
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TSE = RAIZ / "dados" / "tse"
ZIPS = RAIZ / "dados" / "tse_bruto" / "prestacao_contas"
ANOS = [2022, 2024]
TOP_DOADORES = 5
TOP_GASTOS = 6
TOP_ORIGINARIOS = 5
REPASSES = ("partido", "outros candidatos")
VERSAO = 3

csv.field_size_limit(1 << 24)


def valor(v: str) -> float:
    try:
        return float((v or "0").replace(".", "").replace(",", "."))
    except ValueError:
        return 0.0


def nulo(v: str | None) -> str | None:
    v = (v or "").strip()
    return None if not v or v.startswith("#NULO") or v in ("-1", "-4") else v


def linhas(zip_path: Path, nome: str):
    with zipfile.ZipFile(zip_path) as z, z.open(nome) as f:
        yield from csv.DictReader(io.TextIOWrapper(f, encoding="latin-1", newline=""), delimiter=";")


def eleitos_do_ano(ano: int) -> dict:
    """sq da prestação de contas -> UF. Vice usa a prestação do titular (chapa)."""
    alvo = {}
    for arq in sorted((TSE / str(ano)).glob("[A-Z][A-Z].json")):
        for e in json.loads(arq.read_text(encoding="utf-8")):
            alvo[e.get("sequencialChapa") or e["sequencial"]] = e["uf"]
    return alvo


def coletar_ano(ano: int) -> None:
    zip_path = ZIPS / f"prestacao_de_contas_eleitorais_candidatos_{ano}.zip"
    if not zip_path.exists():
        sys.exit(f"falta {zip_path}; rode: python scripts/baixar_tse.py prestacao_contas --anos {ano}")
    alvo = eleitos_do_ano(ano)
    print(f"TSE contas {ano}: {len(alvo)} prestações de eleitos")

    receita = defaultdict(float)
    repasse = {}  # SQ_RECEITA de repasse de partido/outro candidato -> SQ_CANDIDATO
    por_origem = defaultdict(lambda: defaultdict(float))
    doadores = defaultdict(dict)  # sq -> chave do doador -> [nome, origem, valor]
    for l in linhas(zip_path, f"receitas_candidatos_{ano}_BRASIL.csv"):
        sq = l["SQ_CANDIDATO"]
        if sq not in alvo:
            continue
        v = valor(l["VR_RECEITA"])
        origem = nulo(l["DS_ORIGEM_RECEITA"]) or "Não informada"
        receita[sq] += v
        por_origem[sq][origem] += v
        if any(r in origem.lower() for r in REPASSES):
            repasse[l["SQ_RECEITA"]] = sq
        if origem == "Recursos próprios" or "próprios" in origem:
            continue
        nome = nulo(l["NM_DOADOR_RFB"]) or nulo(l["NM_DOADOR"])
        if nome:
            d = doadores[sq].setdefault(nulo(l["NR_CPF_CNPJ_DOADOR"]) or nome, [nome, origem, 0.0])
            d[2] += v

    originarios = defaultdict(dict)  # sq -> chave do doador -> [nome, valor]
    for l in linhas(zip_path, f"receitas_candidatos_doador_originario_{ano}_BRASIL.csv"):
        sq = repasse.get(l["SQ_RECEITA"])
        nome = sq and (nulo(l["NM_DOADOR_ORIGINARIO_RFB"]) or nulo(l["NM_DOADOR_ORIGINARIO"]))
        if nome:
            d = originarios[sq].setdefault(nulo(l["NR_CPF_CNPJ_DOADOR_ORIGINARIO"]) or nome, [nome, 0.0])
            d[1] += valor(l["VR_RECEITA"])

    despesa = defaultdict(float)
    por_gasto = defaultdict(lambda: defaultdict(float))
    for l in linhas(zip_path, f"despesas_contratadas_candidatos_{ano}_BRASIL.csv"):
        sq = l["SQ_CANDIDATO"]
        if sq not in alvo:
            continue
        v = valor(l["VR_DESPESA_CONTRATADA"])
        despesa[sq] += v
        por_gasto[sq][nulo(l["DS_ORIGEM_DESPESA"]) or "Não informada"] += v

    pago = defaultdict(float)
    dono = {}  # SQ_DESPESA -> SQ_CANDIDATO (o arquivo de pagamentos não traz o candidato)
    for l in linhas(zip_path, f"despesas_contratadas_candidatos_{ano}_BRASIL.csv"):
        if l["SQ_CANDIDATO"] in alvo:
            dono[l["SQ_DESPESA"]] = l["SQ_CANDIDATO"]
    for l in linhas(zip_path, f"despesas_pagas_candidatos_{ano}_BRASIL.csv"):
        sq = dono.get(l["SQ_DESPESA"])
        if sq:
            pago[sq] += valor(l["VR_PAGTO_DESPESA"])

    por_uf = defaultdict(dict)
    for sq, uf in alvo.items():
        if sq not in receita and sq not in despesa:
            continue
        top = sorted(doadores[sq].values(), key=lambda d: -d[2])[:TOP_DOADORES]
        orig = sorted(originarios[sq].values(), key=lambda d: -d[1])[:TOP_ORIGINARIOS]
        gastos = sorted(por_gasto[sq].items(), key=lambda g: -g[1])[:TOP_GASTOS]
        por_uf[uf][sq] = {
            "receitas": round(receita[sq], 2), "despesasContratadas": round(despesa[sq], 2), "despesasPagas": round(pago[sq], 2),
            "origensReceita": sorted(([k, round(v, 2)] for k, v in por_origem[sq].items() if v), key=lambda x: -x[1]),
            "principaisDoadores": [[n, o, round(v, 2)] for n, o, v in top if v > 0],
            "doadoresOriginarios": [[n, round(v, 2)] for n, v in orig if v > 0],
            "gastosPorCategoria": [[k, round(v, 2)] for k, v in gastos if v > 0],
        }
    pasta = TSE / "contas" / str(ano)
    pasta.mkdir(parents=True, exist_ok=True)
    for antigo in pasta.glob("*.json"):
        antigo.unlink()
    for uf, mapa in por_uf.items():
        (pasta / f"{uf}.json").write_text(json.dumps(mapa, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (pasta / "_coleta.json").write_text(json.dumps({
        "coletadoEm": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "prestacoes": sum(len(m) for m in por_uf.values()), "versao": VERSAO,
    }), encoding="utf-8")
    print(f"  salvo em {pasta} ({sum(len(m) for m in por_uf.values())} prestações)")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--anos", type=int, nargs="+", default=ANOS)
    for ano in p.parse_args().anos:
        coletar_ano(ano)


if __name__ == "__main__":
    main()
