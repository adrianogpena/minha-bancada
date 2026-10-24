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

import estaduais_comum as comum
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


SANCAO = re.compile(r"\bà sanção\b", re.I)
RAZOES = re.compile(r"Razões do veto:?\s*(DOU[^.]*?COL\s*\d+)", re.I)
MSC_VETO = re.compile(r"MSC-PE\s*(\d+/\d+)", re.I)


def desfecho(id_: int) -> dict:
    """O que aconteceu depois que o Congresso votou, lido na tramitação.

    norma/dataNorma/veto: ex. 'Transformado na Lei Ordinária 15421/2026. ... Vetado parcialmente.'
    remessa: data em que a matéria foi enviada à sanção do presidente.
    razoesVeto/mensagemVeto: onde estão publicadas as razões do veto (DOU) e a mensagem do veto.
    dataEdicao: data de publicação da medida provisória (vale desde então).
    """
    tram = get(f"/proposicoes/{id_}/tramitacoes")["dados"]
    saida = {"tramitacaoLida": True}
    for t in tram:
        desp = t.get("despacho") or ""
        if "Publicação da Medida Provisória" in desp and "dataEdicao" not in saida:
            saida["dataEdicao"] = comum.data_iso(t.get("dataHora"))
        m = NORMA.search(desp)
        sit = t.get("descricaoSituacao") or ""
        if m or "veto" in (t.get("descricaoSituacao") or "").lower():
            texto = desp + sit
            saida.update({"norma": m.group(1) if m else None, "dataNorma": comum.data_iso(t.get("dataHora")),
                          "veto": "total" if re.search(r"vetad[oa] total", texto, re.I)
                          else "parcial" if re.search(r"veto parcial|vetad[oa] parcial", texto, re.I) else None})
            r, c = RAZOES.search(desp), MSC_VETO.search(desp)
            if r:
                saida["razoesVeto"] = re.sub(r"\s+", " ", r.group(1)).strip()
            if c:
                saida["mensagemVeto"] = c.group(1)
            break
    fim = saida.get("dataNorma") or "9999"
    for t in tram:
        dia = comum.data_iso(t.get("dataHora"))
        if SANCAO.search(t.get("despacho") or "") and dia and dia <= fim:
            saida["remessa"] = dia
            break
    return saida


def tramitacao_lida(p: dict) -> bool:
    """Itens que viraram lei ou foram vetados só estão completos depois de lida a tramitação."""
    return not (p.get("situacao") or "").lower().startswith(("transformad", "vetad")) or p.get("tramitacaoLida")


def detalhar(prop: dict) -> dict:
    d = get(f"/proposicoes/{prop['id']}")["dados"]
    st = d.get("statusProposicao") or {}
    sit = (st.get("descricaoSituacao") or "").lower()
    extra = desfecho(prop["id"]) if sit.startswith(("transformad", "vetad", "aguardando sanção")) else {}
    return {**extra,
        "id": prop["id"], "tipo": d["siglaTipo"], "numero": d["numero"], "ano": d["ano"],
        "ementa": (d.get("ementa") or "").strip(),
        "dataApresentacao": comum.data_iso(d.get("dataApresentacao")),
        "situacao": st.get("descricaoSituacao"),
        "dataSituacao": comum.data_iso(st.get("dataHora")),
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
        if p["id"] in antigo and final(antigo[p["id"]].get("situacao")) and tramitacao_lida(antigo[p["id"]]):
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
    lista = sorted(novos.values(), key=lambda p: (p["dataApresentacao"], p["id"]), reverse=True)
    ARQUIVO.write_text(json.dumps(lista, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"Salvo: {len(lista)} proposições ({len(pendentes)} consultadas) -> {ARQUIVO}")


if __name__ == "__main__":
    main()
