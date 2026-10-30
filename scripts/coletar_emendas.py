"""
Emendas parlamentares federais (individuais, de bancada, de comissão e Pix) pela API do Portal da Transparência.

Fonte: https://api.portaldatransparencia.gov.br/api-de-dados/emendas, com chave gratuita (conta gov.br) no cabeçalho
`chave-api-dados`, lida da variável de ambiente PORTAL_TRANSPARENCIA_CHAVE (secret do Actions). Sem a chave, avisa e termina
sem erro. A API pagina de 15 em 15 (`pagina` a partir de 1) e filtra por `ano`; página vazia encerra.

Cada item vem com autor (nome, ou "BANCADA DO CEARÁ" etc.), número, tipo, local do gasto ("MUNICÍPIO (UF)", UF ou
"MÚLTIPLO"), função, subfunção e valores empenhado, liquidado e pago em texto brasileiro. O coletor grava o nome do autor
como veio: a ligação a deputado ou senador é de identidades.py, nunca daqui.

Grava dados/emendas/<ano>.json: {coletadoEm, fonte, itens:[{codigo, ano, tipo, numero, autor, local, municipio, uf, funcao,
subfuncao, empenhado, liquidado, pago}]}. Valores em reais (float).

Anos encerrados (anterior ao passado, com arquivo) não são baixados de novo; o ano passado e o corrente são relidos inteiros
(o pago cresce). O arquivo de cada ano é gravado ao terminar o ano, então o prazo (ESTADUAIS_PRAZO_MIN) só perde o ano em curso.

Uso:
    PORTAL_TRANSPARENCIA_CHAVE=... python scripts/coletar_emendas.py [ano ...]
"""

import datetime as dt
import os
import re
import sys
import time
from pathlib import Path

import estaduais_comum as comum

DADOS = Path(__file__).resolve().parent.parent / "dados" / "emendas"
URL = "https://api.portaldatransparencia.gov.br/api-de-dados/emendas"
FONTE = "https://portaldatransparencia.gov.br/emendas/consulta"
VARIAVEL = "PORTAL_TRANSPARENCIA_CHAVE"
ANO_INICIAL = 2019   # legislatura 2019-2022 em diante
LIMITE_PAGINAS = 5000   # ~75 mil emendas por ano; mais que isso é laço na paginação
PAUSA = 0.7   # s entre páginas: o limite é 90 requisições/min de dia e mais alto na madrugada
LOCAL = re.compile(r"^(?P<municipio>.+?)\s*-?\s*\((?P<uf>[A-Z]{2})\)$")


def compactar(i: dict) -> dict | None:
    codigo = str(i.get("codigoEmenda") or "").strip()
    autor = " ".join((i.get("autor") or i.get("nomeAutor") or "").split())
    if not codigo or not autor:
        return None
    local = " ".join((i.get("localidadeDoGasto") or "").split())
    m = LOCAL.match(local)
    item = {
        "codigo": codigo, "ano": i.get("ano"), "tipo": (i.get("tipoEmenda") or "").strip(), "numero": str(i.get("numeroEmenda") or "").strip(),
        "autor": autor, "local": local, "municipio": m.group("municipio") if m else None, "uf": m.group("uf") if m else None,
        "funcao": (i.get("funcao") or "").strip(), "subfuncao": (i.get("subfuncao") or "").strip(),
        "empenhado": comum.valor_br(i.get("valorEmpenhado")), "liquidado": comum.valor_br(i.get("valorLiquidado")),
        "pago": comum.valor_br(i.get("valorPago")),
    }
    return {k: v for k, v in item.items() if v not in (None, "")}


def chave_item(i: dict) -> tuple:
    return (i["codigo"], i.get("local"), i.get("funcao"), i.get("subfuncao"))


def coletar_ano(ano: int, chave: str, s=None, pausa: float = PAUSA) -> list[dict]:
    """Todas as páginas de um ano; linhas repetidas (mesma emenda, local e função) valem uma vez."""
    s = s or comum.sessao(1)
    itens: dict[tuple, dict] = {}
    for pagina in range(1, LIMITE_PAGINAS + 1):
        lista = comum.get(s, URL, params={"ano": ano, "pagina": pagina}, headers={"chave-api-dados": chave, "Accept": "application/json"}, timeout=60).json()
        if not lista:
            break
        for c in filter(None, map(compactar, lista)):
            itens[chave_item(c)] = c
        time.sleep(pausa)
    else:
        raise RuntimeError(f"paginação das emendas de {ano} não terminou")
    return sorted(itens.values(), key=lambda c: (c["codigo"], c.get("local", ""), c.get("funcao", ""), c.get("subfuncao", "")))


def coletar(chave: str, anos: list[int] | None = None, hoje: dt.date | None = None, s=None, pausa: float = PAUSA) -> None:
    hoje = hoje or dt.date.today()
    for ano in anos or range(ANO_INICIAL, hoje.year + 1):
        arquivo = DADOS / f"{ano}.json"
        if not anos and comum.ano_encerrado(ano, hoje, arquivo):
            continue
        try:
            itens = coletar_ano(ano, chave, s, pausa)
        except Exception as e:  # noqa: BLE001
            comum.avisar(f"emendas {ano}: {e}")
            continue
        if not itens:
            comum.avisar(f"emendas {ano}: a API não devolveu nada; arquivo anterior mantido")
            continue
        comum.salvar(arquivo, {"coletadoEm": hoje.isoformat(), "fonte": f"{FONTE}?ano={ano}", "itens": itens})
        print(f"Emendas {ano}: {len(itens)}")


def main() -> None:
    chave = os.environ.get(VARIAVEL, "").strip()
    if not chave:
        comum.avisar(f"emendas: {VARIAVEL} não definida; coleta pulada")
        return
    coletar(chave, [int(a) for a in sys.argv[1:]] or None)


if __name__ == "__main__":
    main()
