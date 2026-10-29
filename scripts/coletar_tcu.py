"""
Pessoas inabilitadas pelo TCU para exercer cargo ou função pública (sanção do art. 60 da Lei Orgânica do TCU).

Fonte: API aberta do TCU, sem chave (https://contas.tcu.gov.br/ords/condenacao/consulta/inabilitados), paginada por
`limit` (máx. 500) e `offset`. Cada item traz nome, CPF, processo, deliberação, datas do acórdão, do trânsito em julgado e
do fim da sanção, e a UF e o município do caso. O CPF não é guardado (regra do projeto); o nome e a UF ligam à pessoa em
identidades.py. Grava dados/tcu/inabilitados.json (fora do git): {coletadoEm, itens: [...]}.

Também coleta os inidôneos (proibidos de licitar com a administração federal, art. 46), em .../consulta/inidoneos, mesmo formato com
`cpf_cnpj`. Só o CNPJ válido é guardado (empresa); CPF de pessoa física é descartado. Liga a fornecedor por CNPJ em fornecedores.py.
Grava dados/tcu/inidoneos.json.

Uso:
    python scripts/coletar_tcu.py
"""

import datetime as dt
import re
from pathlib import Path

import estaduais_comum as comum
import fornecedores

DADOS = Path(__file__).resolve().parent.parent / "dados" / "tcu"
URL = "https://contas.tcu.gov.br/ords/condenacao/consulta/inabilitados"
URL_INIDONEOS = "https://contas.tcu.gov.br/ords/condenacao/consulta/inidoneos"
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


def compactar_inidoneo(i: dict) -> dict | None:
    doc = fornecedores.documento(i.get("cpf_cnpj"))
    base = compactar({**i, "nome": i.get("nome")})
    if not base or not doc or doc[0] != "cnpj":
        return None
    return {**base, "cnpj": doc[1]}


def paginar(url: str, compacta, s=None) -> list[dict]:
    s = s or comum.sessao(1)
    itens, offset = [], 0
    for _ in range(LIMITE_PAGINAS):
        d = comum.get(s, url, params={"limit": POR_PAGINA, "offset": offset}, timeout=60).json()
        itens += [c for c in map(compacta, d.get("items", [])) if c]
        if not d.get("hasMore"):
            break
        offset += POR_PAGINA
    else:
        raise RuntimeError("paginação do TCU não terminou")
    return itens


def coletar(s=None) -> list[dict]:
    itens = paginar(URL, compactar, s)
    if not itens:
        raise RuntimeError("lista de inabilitados do TCU vazia")
    return itens


def coletar_inidoneos(s=None) -> list[dict]:
    itens = paginar(URL_INIDONEOS, compactar_inidoneo, s)
    if not itens:
        raise RuntimeError("lista de inidôneos do TCU vazia")
    return itens


def main() -> None:
    itens = coletar()
    comum.salvar(DADOS / "inabilitados.json", {"coletadoEm": dt.date.today().isoformat(), "itens": itens})
    print(f"Inabilitados pelo TCU: {len(itens)}")
    try:
        inidoneos = coletar_inidoneos()
    except Exception as e:
        comum.avisar(f"inidôneos do TCU: {e}")
        return
    comum.salvar(DADOS / "inidoneos.json", {"coletadoEm": dt.date.today().isoformat(), "itens": inidoneos})
    print(f"Inidôneos pelo TCU (empresas): {len(inidoneos)}")


if __name__ == "__main__":
    main()
