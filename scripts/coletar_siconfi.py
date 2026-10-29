"""
Despesa com pessoal e limites da LRF de cada estado e do DF, por Poder, a partir do SICONFI (Tesouro Nacional).

Fonte: Relatório de Gestão Fiscal (RGF), Anexo 01, da API de dados abertos do Tesouro
(https://apidatalake.tesouro.gov.br/ords/siconfi/tt/rgf), sem chave. Para cada UF e ano:
  - Poder Legislativo (`co_poder=L`): uma linha por instituição (Assembleia ou Câmara Legislativa e, quando entrega
    o próprio RGF, o Tribunal de Contas);
  - Poder Executivo (`co_poder=E`): o Governo do Estado.
Vale o último período publicado do ano (3.º quadrimestre; se ainda não saiu, o 2.º ou o 1.º). Valores em reais;
`pct*` é % da receita corrente líquida ajustada. É dado da instituição, não de cada deputado.

Despesa total da função Legislativa: Declaração de Contas Anuais (DCA), Anexo I-E (despesa por função), do Governo do
Estado. Publicada depois do fim do ano, então o ano corrente não tem. A subfunção 01.031 (Ação Legislativa) é a
Assembleia; 01.032 (Controle Externo) é o Tribunal de Contas. Dividida pelas cadeiras dá o custo por parlamentar.

Grava dados/siconfi/<UF>.json:
  {coletadoEm, uf, anos:{"2025":{poderes:[{poder, instituicao, periodicidade ("Q"|"S"), periodo, despesaBruta, despesaLiquida, rcl, rclAjustada,
      dtp, pctDtp, limiteMaximo, pctLimiteMaximo, limitePrudencial, limiteAlerta, fonte}],
    legislativa:{fonte, legislativa|acaoLegislativa|controleExterno: {empenhada, liquidada, paga}}}}}

Uso:
    python scripts/coletar_siconfi.py          # todas as UFs
    python scripts/coletar_siconfi.py SP DF
"""

import datetime as dt
import sys
from urllib.parse import urlencode

import estaduais_comum as comum

BASE = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/rgf"
BASE_DCA = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/dca"
DADOS = comum.RAIZ / "dados" / "siconfi"
ANO_INICIAL = 2023
PAGINA = 5000
# id_ente do SICONFI para estado e DF é o código IBGE da UF
UFS = {"RO": 11, "AC": 12, "AM": 13, "RR": 14, "PA": 15, "AP": 16, "TO": 17, "MA": 21, "PI": 22, "CE": 23, "RN": 24,
       "PB": 25, "PE": 26, "AL": 27, "SE": 28, "BA": 29, "MG": 31, "ES": 32, "RJ": 33, "SP": 35, "PR": 41, "SC": 42,
       "RS": 43, "MS": 50, "MT": 51, "GO": 52, "DF": 53}
# conta da DCA (começo do rótulo) -> campo; coluna -> campo
FUNCOES = {"01 -": "legislativa", "01.031 -": "acaoLegislativa", "01.032 -": "controleExterno"}
COLUNAS_DCA = {"Despesas Empenhadas": "empenhada", "Despesas Liquidadas": "liquidada", "Despesas Pagas": "paga"}
PODERES = ("L", "E")
# (periodicidade, períodos do mais novo ao mais antigo); o RGF é quadrimestral, semestral só para quem optou
PERIODOS = (("Q", (3, 2, 1)), ("S", (2, 1)))
# conta do SICONFI -> (coluna, campo). A coluna "TOTAL (ÚLTIMOS 12 MESES)" começa assim em todos os anos.
TOTAL = "TOTAL (ÚLTIMOS 12 MESES)"
CAMPOS = {
    ("DespesaComPessoalBruta", TOTAL): "despesaBruta",
    ("DespesaComPessoalLiquida", TOTAL): "despesaLiquida",
    ("ReceitaCorrenteLiquidaLimiteLegal", "Valor"): "rcl",
    ("ReceitaCorrenteLiquidaAjustada", "Valor"): "rclAjustada",
    ("DespesaComPessoalTotal", "Valor"): "dtp",
    ("DespesaComPessoalTotal", "% sobre a RCL Ajustada"): "pctDtp",
    ("LimiteMaximoDespesaComPessoalTotal", "Valor"): "limiteMaximo",
    ("LimiteMaximoDespesaComPessoalTotal", "% sobre a RCL Ajustada"): "pctLimiteMaximo",
    ("LimitePrudencialDespesaComPessoalTotal", "Valor"): "limitePrudencial",
    ("LimiteDeAlertaDespesaComPessoalTotal", "Valor"): "limiteAlerta",
}


def url(uf: str, ano: int, periodicidade: str, periodo: int, poder: str, **extra) -> str:
    """Endereço da consulta (também é o `fonte` que a pessoa abre para conferir)."""
    params = dict(an_exercicio=ano, in_periodicidade=periodicidade, nr_periodo=periodo, co_tipo_demonstrativo="RGF",
                  no_anexo="RGF-Anexo 01", co_esfera="E", co_poder=poder, id_ente=UFS[uf], **extra)
    return f"{BASE}?{urlencode(params)}"


def url_dca(uf: str, ano: int, **extra) -> str:
    params = dict(an_exercicio=ano, no_anexo="DCA-Anexo I-E", id_ente=UFS[uf], **extra)
    return f"{BASE_DCA}?{urlencode(params)}"


def paginar(s, endereco) -> list[dict]:
    """Junta as páginas; `endereco(limit, offset)` monta a consulta de cada uma."""
    itens, offset = [], 0
    while True:
        r = s.get(endereco(PAGINA, offset), timeout=60)
        r.raise_for_status()
        corpo = r.json()
        itens += corpo.get("items") or []
        if not corpo.get("hasMore"):
            return itens
        offset += PAGINA


def baixar(s, uf: str, ano: int, periodicidade: str, periodo: int, poder: str) -> list[dict]:
    return paginar(s, lambda limit, offset: url(uf, ano, periodicidade, periodo, poder, limit=limit, offset=offset))


def resumir_legislativa(itens: list[dict], fonte: str) -> dict:
    """Despesa da função Legislativa e das subfunções 031 e 032; vazio se a DCA do ano não trouxe a função."""
    saida: dict = {}
    for i in itens:
        if i.get("cod_conta") != "TotalDespesas" or i.get("valor") is None:
            continue
        coluna = COLUNAS_DCA.get((i.get("coluna") or "").strip())
        funcao = next((c for p, c in FUNCOES.items() if (i.get("conta") or "").startswith(p)), None)
        if coluna and funcao:
            saida.setdefault(funcao, {})[coluna] = float(i["valor"])
    return {"fonte": fonte, **saida} if saida else {}


def resumir(itens: list[dict], fonte: str) -> list[dict]:
    """Uma linha por instituição, com só as contas de CAMPOS (coluna que não é o total dos 12 meses é ignorada)."""
    por_instituicao: dict[str, dict] = {}
    for i in itens:
        coluna = (i.get("coluna") or "").strip()
        coluna = TOTAL if coluna.startswith(TOTAL) else coluna
        campo = CAMPOS.get((i.get("cod_conta"), coluna))
        if campo is None or i.get("valor") is None:
            continue
        linha = por_instituicao.setdefault(i["instituicao"], {"poder": i["co_poder"], "instituicao": i["instituicao"], "fonte": fonte})
        linha[campo] = float(i["valor"])
    return [lin for lin in sorted(por_instituicao.values(), key=lambda lin: lin["instituicao"]) if "dtp" in lin or "despesaBruta" in lin]


def ano_do_poder(s, uf: str, ano: int, poder: str) -> list[dict]:
    """Linhas do último período publicado do ano para o Poder (cada uma leva `periodicidade` e `periodo`)."""
    for periodicidade, periodos in PERIODOS:
        for periodo in periodos:
            linhas = resumir(baixar(s, uf, ano, periodicidade, periodo, poder), url(uf, ano, periodicidade, periodo, poder))
            if linhas:
                return [{**lin, "periodicidade": periodicidade, "periodo": periodo} for lin in linhas]
    return []


def coletar_uf(s, uf: str, hoje: dt.date) -> None:
    arq = DADOS / f"{uf}.json"
    anteriores = comum.ler(arq, {}).get("anos", {})
    anos = {}
    for ano in range(ANO_INICIAL, hoje.year + 1):
        if comum.ano_encerrado(ano, hoje, arq) and "legislativa" in anteriores.get(str(ano), {}):
            anos[str(ano)] = anteriores[str(ano)]
            continue
        poderes = [lin for poder in PODERES for lin in ano_do_poder(s, uf, ano, poder)]
        legislativa = resumir_legislativa(paginar(s, lambda limit, offset: url_dca(uf, ano, limit=limit, offset=offset)), url_dca(uf, ano))
        if poderes or legislativa:
            anos[str(ano)] = {"poderes": poderes, **({"legislativa": legislativa} if legislativa else {})}
        elif str(ano) in anteriores:
            anos[str(ano)] = anteriores[str(ano)]
    if anos:
        comum.salvar(arq, {"coletadoEm": hoje.isoformat(), "uf": uf, "anos": anos})
    print(f"{uf}: {', '.join(f'{a} ({len(v['poderes'])})' for a, v in anos.items()) or 'nada'}")


def main() -> None:
    ufs = [u.upper() for u in sys.argv[1:]] or list(UFS)
    s = comum.sessao()
    hoje = dt.date.today()
    for uf in ufs:
        try:
            coletar_uf(s, uf, hoje)
        except Exception as e:
            comum.avisar(f"SICONFI {uf}: {e}")


if __name__ == "__main__":
    main()
