"""
Despesa da Câmara Municipal de cada município a partir da DCA do SICONFI (Tesouro Nacional).

Fonte: Declaração de Contas Anuais, Anexo I-E (despesa por função), da prefeitura (id_ente = código IBGE do município),
sem chave: https://apidatalake.tesouro.gov.br/ords/siconfi/tt/dca. A subfunção 01.031 (Ação Legislativa) é a Câmara
Municipal. Uma consulta por município (~5.570, cerca de 2,5 s cada), então o coletor guarda o que já leu, trabalha
só no último ano com DCA publicada e respeita o prazo do job (ESTADUAIS_PRAZO_MIN): as consultas que faltam ficam para o
dia seguinte. Município sem DCA no ano é consultado de novo só depois de RETENTAR_DIAS.

Grava dados/siconfi_municipios/<UF>.json:
  {coletadoEm, uf, ano, municipios:{<IBGE 7 dígitos>: {empenhada, liquidada, paga, populacao, fonte} | {semDca: "AAAA-MM-DD"}}}

Uso:
    python scripts/coletar_siconfi_municipios.py          # todas as UFs
    python scripts/coletar_siconfi_municipios.py SP DF
"""

import datetime as dt
import json
import sys
from concurrent.futures import ThreadPoolExecutor

import coletar_siconfi as sic
import estaduais_comum as comum

DADOS = comum.RAIZ / "dados" / "siconfi_municipios"
MUNICIPIOS_IBGE = comum.RAIZ / "dados" / "municipios_ibge.json"
SAO_PAULO = 3550308   # município usado para descobrir o último ano com DCA publicada
ANOS_TENTADOS = 3
RETENTAR_DIAS = 30
SIMULTANEAS = 4


def despesa_camara(s, ibge: int | str, ano: int) -> dict:
    """Ação Legislativa do município no ano, ou vazio se a prefeitura não entregou a DCA."""
    comum.checar_prazo()
    fonte = sic.url_dca_ente(ibge, ano)
    itens = sic.paginar(s, lambda limit, offset: sic.url_dca_ente(ibge, ano, limit=limit, offset=offset))
    acao = sic.resumir_legislativa(itens, fonte).get("acaoLegislativa")
    if not acao:
        return {}
    populacao = next((i["populacao"] for i in itens if i.get("populacao")), None)
    return {**acao, **({"populacao": populacao} if populacao else {}), "fonte": fonte}


def ultimo_ano(s, hoje: dt.date) -> int | None:
    for ano in range(hoje.year - 1, hoje.year - 1 - ANOS_TENTADOS, -1):
        if despesa_camara(s, SAO_PAULO, ano):
            return ano
    return None


def a_consultar(codigos: list[str], guardados: dict, hoje: dt.date) -> list[str]:
    def velho(reg: dict) -> bool:
        return "semDca" in reg and (hoje - dt.date.fromisoformat(reg["semDca"])).days >= RETENTAR_DIAS
    return [c for c in codigos if c not in guardados or velho(guardados[c])]


def coletar_uf(s, uf: str, codigos: list[str], ano: int, hoje: dt.date) -> None:
    arq = DADOS / f"{uf}.json"
    antes = comum.ler(arq, {})
    guardados = antes.get("municipios", {}) if antes.get("ano") == ano else {}
    faltam = a_consultar(codigos, guardados, hoje)

    def ler_um(cod: str):
        try:
            return cod, despesa_camara(s, cod, ano) or {"semDca": hoje.isoformat()}
        except comum.PrazoEsgotado:
            return cod, None

    try:
        with ThreadPoolExecutor(SIMULTANEAS) as pool:
            for cod, reg in pool.map(ler_um, faltam):
                if reg is not None:
                    guardados[cod] = reg
    finally:
        comum.salvar(arq, {"coletadoEm": hoje.isoformat(), "uf": uf, "ano": ano, "municipios": dict(sorted(guardados.items()))})
    print(f"{uf}: {len(guardados)}/{len(codigos)} municípios ({len(faltam)} consultados)")


def main() -> None:
    ufs = [u.upper() for u in sys.argv[1:]] or list(sic.UFS)
    s = comum.sessao(SIMULTANEAS)
    hoje = dt.date.today()
    por_uf: dict[str, list[str]] = {}
    for ibge in sorted(set(json.loads(MUNICIPIOS_IBGE.read_text(encoding="utf-8")).values())):
        por_uf.setdefault(next((u for u, c in sic.UFS.items() if str(c) == ibge[:2]), ""), []).append(ibge)
    try:
        ano = ultimo_ano(s, hoje)
    except Exception as e:
        comum.avisar(f"SICONFI municípios: {e}")
        return
    if ano is None:
        comum.avisar("SICONFI municípios: nenhuma DCA recente encontrada")
        return
    for uf in ufs:
        try:
            coletar_uf(s, uf, por_uf.get(uf, []), ano, hoje)
        except Exception as e:
            comum.avisar(f"SICONFI municípios {uf}: {e}")
            if isinstance(e, comum.PrazoEsgotado):
                return


if __name__ == "__main__":
    main()
