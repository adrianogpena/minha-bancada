"""
Pessoas inabilitadas pelo TCU para exercer cargo ou função pública (sanção do art. 60 da Lei Orgânica do TCU).

Fonte: API aberta do TCU, sem chave (https://contas.tcu.gov.br/ords/condenacao/consulta/inabilitados), paginada por
`limit` (máx. 500) e `offset`. Cada item traz nome, CPF, processo, deliberação, datas do acórdão, do trânsito em julgado e
do fim da sanção, e a UF e o município do caso. O CPF não é guardado (regra do projeto); o nome e a UF ligam à pessoa em
identidades.py. Grava dados/tcu/inabilitados.json (fora do git): {coletadoEm, itens: [...]}.

Uso:
    python scripts/coletar_tcu.py
"""

import datetime as dt
import re
from pathlib import Path

import estaduais_comum as comum

DADOS = Path(__file__).resolve().parent.parent / "dados" / "tcu"
URL = "https://contas.tcu.gov.br/ords/condenacao/consulta/inabilitados"
POR_PAGINA = 500
LIMITE_PAGINAS = 50   # a lista tem centenas de itens; mais que isso é laço na paginação


def dia(texto: str | None) -> str | None:
    """'2022-07-16T03:00:00Z' -> '2022-07-16' (o TCU manda a meia-noite de Brasília em UTC)."""
    m = re.match(r"\d{4}-\d{2}-\d{2}", texto or "")
    return m.group(0) if m else None


def compactar(i: dict) -> dict | None:
    nome = " ".join((i.get("nome") or "").split())
    if not nome or not i.get("processo"):
        return None
    return {k: v for k, v in {
        "nome": nome, "processo": i["processo"].strip(), "deliberacao": (i.get("deliberacao") or "").strip() or None,
        "acordao": dia(i.get("data_acordao")), "transito": dia(i.get("data_transito_julgado")), "fim": dia(i.get("data_final")),
        "uf": (i.get("uf") or "").strip().upper() or None, "municipio": (i.get("municipio") or "").strip() or None,
    }.items() if v}


def coletar(s=None) -> list[dict]:
    s = s or comum.sessao(1)
    itens, offset = [], 0
    for _ in range(LIMITE_PAGINAS):
        d = comum.get(s, URL, params={"limit": POR_PAGINA, "offset": offset}, timeout=60).json()
        itens += [c for c in map(compactar, d.get("items", [])) if c]
        if not d.get("hasMore"):
            break
        offset += POR_PAGINA
    else:
        raise RuntimeError("paginação do TCU não terminou")
    if not itens:
        raise RuntimeError("lista de inabilitados do TCU vazia")
    return itens


def main() -> None:
    itens = coletar()
    comum.salvar(DADOS / "inabilitados.json", {"coletadoEm": dt.date.today().isoformat(), "itens": itens})
    print(f"Inabilitados pelo TCU: {len(itens)}")


if __name__ == "__main__":
    main()
