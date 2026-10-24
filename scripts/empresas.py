"""
Dados cadastrais das empresas fornecedoras que o site mostra (os do ranking de fornecedores e os do cruzamento com doadores).

  site/dados/nucleo/empresas.json   {fonte, tabelas, empresas: {id do fornecedor: dados da Receita + data da primeira nota}}

Fonte: dados/receita/ (CNPJ aberto da Receita Federal, coletado só localmente por scripts/coletar_receita.py). Sem esses arquivos o
arquivo sai com `empresas` vazio (a página não busca nada que não exista) e o site fica sem este bloco. Não acessa a internet; chamado pelo scripts/gerar.py.

Cada empresa guarda os códigos da Receita (CNAE, natureza, qualificação) e `tabelas` a descrição de cada código, uma vez só. Sobre o
tempo: `primeiraNota` é a data da primeira nota do ano em `fornecedores.json` (não do primeiro pagamento da história) e `diasAteNota`
são os dias entre a abertura da empresa e essa nota. É um fato cadastral, não indício de irregularidade.
"""

import datetime as dt
import json
from pathlib import Path

from gerar_politicos import ler, salvar

RECENTE_DIAS = 365   # a página destaca empresa aberta até este prazo antes da primeira nota do ano
VOCABULARIO = {   # vocabulário fechado da Receita (Metadados do CNPJ)
    "situacao": {"01": "Nula", "02": "Ativa", "03": "Suspensa", "04": "Inapta", "08": "Baixada"},
    "porte": {"00": "Não informado", "01": "Microempresa", "03": "Empresa de pequeno porte", "05": "Demais"},
    "tipoSocio": {"1": "Pessoa jurídica", "2": "Pessoa física", "3": "Estrangeiro"},
}
FONTE = {"nome": "Receita Federal, CNPJ (dados abertos)", "url": "https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj"}


def _dias(abertura: str | None, nota: str | None) -> int | None:
    try:
        return (dt.date.fromisoformat(nota) - dt.date.fromisoformat(abertura)).days if abertura and nota else None
    except ValueError:
        return None


def construir(bruto: Path, ids, datas: dict) -> dict:
    """`ids`: ids de fornecedor a mostrar; `datas`: {id: (primeira nota, última)} de fornecedores.construir()."""
    coleta = ler(bruto / "receita" / "_coleta.json", None)
    if not coleta:
        return {"fonte": None, "tabelas": {}, "recenteDias": RECENTE_DIAS, "empresas": {}}
    por_parte = {}
    empresas, usados = {}, {"cnae": set(), "natureza": set(), "qualificacao": set(), "municipio": set()}
    for id_ in sorted(ids):
        if not id_.startswith("for_") or not id_[4:].isdigit():
            continue
        raiz = id_[4:]
        mapa = por_parte.get(raiz[:2])
        if mapa is None:
            mapa = por_parte[raiz[:2]] = ler(bruto / "receita" / "cnpj" / f"{raiz[:2]}.json", {}) or {}
        e = mapa.get(raiz)
        if not e:
            continue
        primeira = (datas.get(id_) or (None, None))[0]
        e = {**e, "primeiraNota": primeira, "diasAteNota": _dias(e.get("abertura"), primeira)}
        empresas[id_] = {k: v for k, v in e.items() if v is not None}
        usados["cnae"].update(c for c in [e.get("cnaePrincipal"), *e.get("cnaesSecundarios", ())] if c)
        usados["natureza"].update([e["natureza"]] if e.get("natureza") else [])
        usados["qualificacao"].update(s[1] for s in e.get("socios", ()) if s[1])
        usados["municipio"].update([e["municipio"]] if e.get("municipio") else [])
    tabelas = ler(bruto / "receita" / "tabelas.json", {}) or {}
    return {"fonte": {**FONTE, "competencia": coleta.get("competencia"), "coletadoEm": coleta.get("coletadoEm")},
            "tabelas": {**{k: {c: tabelas.get(k, {}).get(c) for c in sorted(v) if c in tabelas.get(k, {})} for k, v in usados.items()}, **VOCABULARIO},
            "recenteDias": RECENTE_DIAS, "empresas": empresas}


def salvar_empresas(res: dict, saida: Path) -> None:
    salvar(saida / "nucleo" / "empresas.json", res)
    if not res["fonte"]:
        print("Empresas: sem dados/receita/ (rode scripts/coletar_receita.py na sua máquina); bloco da Receita fica de fora")
        return
    recentes = sum(1 for e in res["empresas"].values() if e.get("diasAteNota") is not None and 0 <= e["diasAteNota"] <= res["recenteDias"])
    print(f"Empresas: {len(res['empresas'])} com dados da Receita ({res['fonte']['competencia']}); {recentes} abertas até "
          f"{res['recenteDias']} dias antes da primeira nota do ano")
