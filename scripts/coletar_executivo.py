"""
Coleta o que o Presidente da República enviou ao Congresso (projetos de lei,
leis complementares, emendas à Constituição e medidas provisórias) na API de
Dados Abertos da Câmara, e como cada um terminou: sancionado, vetado, em
tramitação, arquivado ou sem eficácia. Guarda em dados/executivo.json (vai
para o git, o histórico cresce aos poucos).

Uso:
    python scripts/coletar_executivo.py
"""

import datetime as dt
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from coletar import avisar, get, get_todos

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO = RAIZ / "dados" / "executivo.json"
ANO_INICIAL = 2023  # mandato atual começa em 1º de janeiro de 2023
TIPOS = ("PL", "PLP", "PEC", "MPV")
TRABALHADORES = 6
# situações em que a proposição não muda mais; não vale consultar de novo
FINAIS = ("transformad", "vetad", "perdeu a eficácia", "retirad", "arquivad", "rejeitad", "prejudicad")


def final(sit: str | None) -> bool:
    s = (sit or "").lower()
    return any(s.startswith(f) for f in FINAIS)


NORMA = re.compile(r"Transformad[oa] n[ao] (Lei [\w ]*?\d[\d.]*/\d{4}|Emenda Constitucional[\w ]*?\d[\d.]*/\d{4})", re.I)


def desfecho(id_: int) -> dict:
    """Número da lei e se houve veto, lidos na tramitação (ex.: 'Transformado na Lei Ordinária 15421/2026. ... Vetado parcialmente.')."""
    for t in get(f"/proposicoes/{id_}/tramitacoes")["dados"]:
        desp = t.get("despacho") or ""
        m = NORMA.search(desp)
        if m or "veto" in (t.get("descricaoSituacao") or "").lower():
            return {"norma": m.group(1) if m else None, "dataNorma": (t.get("dataHora") or "")[:10],
                    "veto": "total" if re.search(r"vetad[oa] total", desp + (t.get("descricaoSituacao") or ""), re.I)
                    else "parcial" if re.search(r"veto parcial|vetad[oa] parcial", desp + (t.get("descricaoSituacao") or ""), re.I) else None}
    return {}


def detalhar(prop: dict) -> dict:
    d = get(f"/proposicoes/{prop['id']}")["dados"]
    st = d.get("statusProposicao") or {}
    extra = desfecho(prop["id"]) if (st.get("descricaoSituacao") or "").lower().startswith(("transformad", "vetad")) else {}
    return {**extra,
        "id": prop["id"], "tipo": d["siglaTipo"], "numero": d["numero"], "ano": d["ano"],
        "ementa": (d.get("ementa") or "").strip(),
        "apres": (d.get("dataApresentacao") or "")[:10],
        "sit": st.get("descricaoSituacao"),
        "data": (st.get("dataHora") or "")[:10],
        "inteiroTeor": d.get("urlInteiroTeor"),
    }


def main() -> None:
    antigo = {}
    if ARQUIVO.exists():
        antigo = {p["id"]: p for p in json.loads(ARQUIVO.read_text(encoding="utf-8"))}

    achados = []
    for ano in range(ANO_INICIAL, dt.date.today().year + 1):
        for tipo in TIPOS:
            try:
                achados += get_todos("/proposicoes", autor="Poder Executivo", siglaTipo=tipo, ano=ano)
            except Exception as e:
                avisar(f"Executivo: {tipo} de {ano}: {e}")
    print(f"Proposições do Poder Executivo na Câmara: {len(achados)}")

    novos = {}
    pendentes = []
    for p in achados:
        if p["id"] in antigo and final(antigo[p["id"]].get("sit")):
            novos[p["id"]] = antigo[p["id"]]
        else:
            pendentes.append(p)
    with ThreadPoolExecutor(TRABALHADORES) as ex:
        futuros = {ex.submit(detalhar, p): p for p in pendentes}
        for f in as_completed(futuros):
            p = futuros[f]
            try:
                novos[p["id"]] = f.result()
            except Exception as e:
                avisar(f"Executivo: proposição {p['id']}: {e}")
                if p["id"] in antigo:
                    novos[p["id"]] = antigo[p["id"]]
    if not novos:
        print("Nada coletado; mantendo o arquivo anterior.", file=sys.stderr)
        return
    lista = sorted(novos.values(), key=lambda p: (p["apres"], p["id"]), reverse=True)
    ARQUIVO.write_text(json.dumps(lista, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"Salvo: {len(lista)} proposições ({len(pendentes)} consultadas) -> {ARQUIVO}")


if __name__ == "__main__":
    main()
