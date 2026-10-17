"""
Transforma o cache bruto (dados/) nos arquivos JSON enxutos que o site lê
(site/dados/). Não acessa a internet.

Uso:
    python scripts/gerar.py
"""

import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BRUTO = RAIZ / "dados"
SAIDA = RAIZ / "site" / "dados"

VOTOS_NORMAIS = {"Sim": "sim", "Não": "nao", "Abstenção": "abstencao",
                 "Obstrução": "obstrucao", "Artigo 17": "art17"}


def ler(caminho: Path, padrao=None):
    if caminho.exists():
        return json.loads(caminho.read_text(encoding="utf-8"))
    return padrao


def salvar(caminho: Path, obj) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def tipo_voto(v: str | None) -> str:
    return VOTOS_NORMAIS.get(v or "", "outro")


def main():
    ids = ler(BRUTO / "deputados.json", [])
    if not ids:
        raise SystemExit("Nada em dados/. Rode antes: python scripts/coletar.py")

    deputados = {}
    for did in ids:
        d = ler(BRUTO / "deputados" / f"{did}.json")
        if d:
            deputados[did] = d

    # todas as votações do histórico, só as nominais (com votos registrados)
    votacoes = []
    for arq in sorted((BRUTO / "votacoes").glob("*.json")):
        votacoes += [v for v in ler(arq, {}).values() if v.get("votos")]
    votacoes.sort(key=lambda v: (v["data"], v.get("hora") or ""), reverse=True)

    if SAIDA.exists():
        shutil.rmtree(SAIDA)

    votos_por_dep = defaultdict(list)
    lista_votacoes = []
    for v in votacoes:
        placar = Counter(tipo_voto(t) for _, t in v["votos"])
        por_partido = defaultdict(Counter)
        detalhados = []
        for did, t in v["votos"]:
            dep = deputados.get(did)
            votos_por_dep[did].append({
                "id": v["id"], "data": v["data"], "descricao": v["descricao"],
                "proposicao": v.get("proposicao"), "aprovada": v.get("aprovada"),
                "voto": tipo_voto(t),
            })
            partido = dep["partido"] if dep else "?"
            por_partido[partido][tipo_voto(t)] += 1
            detalhados.append({
                "id": did, "nome": dep["nome"] if dep else f"Deputado {did}",
                "partido": partido, "uf": dep["uf"] if dep else "",
                "voto": tipo_voto(t),
            })
        resumo = {
            "id": v["id"], "data": v["data"], "hora": v.get("hora"),
            "descricao": v["descricao"], "proposicao": v.get("proposicao"),
            "aprovada": v.get("aprovada"), "placar": dict(placar),
        }
        lista_votacoes.append(resumo)
        salvar(SAIDA / "votacao" / f"{v['id']}.json", {
            **resumo,
            "porPartido": {p: dict(c) for p, c in sorted(por_partido.items())},
            "votos": sorted(detalhados, key=lambda x: x["nome"]),
        })
    salvar(SAIDA / "votacoes.json", lista_votacoes)

    total_nominais = len(votacoes)
    resumo_deps = []
    for did, d in deputados.items():
        itens = d["despesas"]["itens"]
        por_tipo = Counter()
        por_mes = Counter()
        fornecedores = Counter()
        for i in itens:
            por_tipo[i["tipo"] or "Outros"] += i["valor"]
            por_mes[i["mes"]] += i["valor"]
            fornecedores[i["fornecedor"] or "Não informado"] += i["valor"]
        total_gasto = round(sum(por_tipo.values()), 2)
        votos = votos_por_dep.get(did, [])
        votou = sum(1 for x in votos if x["voto"] in ("sim", "nao", "abstencao", "art17"))

        salvar(SAIDA / "deputado" / f"{did}.json", {
            "id": did, "nome": d["nome"], "nomeCivil": d.get("nomeCivil"),
            "partido": d["partido"], "uf": d["uf"], "foto": d.get("foto"),
            "email": d.get("email"), "situacao": d.get("situacao"),
            "nascimento": d.get("nascimento"),
            "naturalidade": ", ".join(x for x in (d.get("municipioNascimento"), d.get("ufNascimento")) if x),
            "escolaridade": d.get("escolaridade"), "redesSociais": d.get("redesSociais", []),
            "proposicoes": d["proposicoes"],
            "votos": votos,
            "totalVotacoes": total_nominais,
            "despesas": {
                "ano": d["despesas"]["ano"], "total": total_gasto,
                "porTipo": sorted(([k, round(v, 2)] for k, v in por_tipo.items()), key=lambda x: -x[1]),
                "porMes": sorted(([k, round(v, 2)] for k, v in por_mes.items())),
                "fornecedores": [[k, round(v, 2)] for k, v in fornecedores.most_common(10)],
                "recentes": itens[:30],
            },
            "coletadoEm": d.get("coletadoEm"),
        })
        resumo_deps.append({
            "id": did, "nome": d["nome"], "partido": d["partido"], "uf": d["uf"],
            "foto": d.get("foto"), "proposicoes": len(d["proposicoes"]),
            "gasto": total_gasto, "votou": votou, "votacoes": total_nominais,
        })

    resumo_deps.sort(key=lambda x: x["nome"])
    salvar(SAIDA / "deputados.json", resumo_deps)
    meta = ler(BRUTO / "meta.json", {}) or {}
    meta["ano"] = next(iter(deputados.values()))["despesas"]["ano"] if deputados else None
    meta["periodoVotacoes"] = [votacoes[-1]["data"], votacoes[0]["data"]] if votacoes else None
    salvar(SAIDA / "meta.json", meta)
    print(f"Gerado: {len(resumo_deps)} deputados, {len(lista_votacoes)} votações nominais -> {SAIDA}")


if __name__ == "__main__":
    main()
