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

import gerar_estaduais
import gerar_prefeituras
import gerar_politicos

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


def juntar_detalhe(p: dict, det: dict | None) -> dict:
    """Acrescenta à proposição a situação atual, quando já foi consultada.
    Nomes curtos para o JSON do site ficar leve."""
    if not det:
        return p
    campos = {"apres": "ap", "sit": "sit", "desp": "desp", "org": "org", "data": "dt",
              "inteiroTeor": "pdf", "detalhada": "det", "palavras": "kw",
              "tram": "tram", "regime": "reg"}
    return {**p, **{curto: det[longo] for longo, curto in campos.items() if det.get(longo)}}


def resumir_despesas(ano: int, itens: list) -> dict:
    """Totais por tipo, mês e fornecedor, no formato que o site usa para deputados e senadores."""
    por_tipo, por_mes, fornecedores = Counter(), Counter(), Counter()
    for i in itens:
        por_tipo[i["tipo"] or "Outros"] += i["valor"]
        por_mes[i["mes"]] += i["valor"]
        fornecedores[i["fornecedor"] or "Não informado"] += i["valor"]
    return {
        "ano": ano, "total": round(sum(por_tipo.values()), 2),
        "porTipo": sorted(([k, round(v, 2)] for k, v in por_tipo.items()), key=lambda x: -x[1]),
        "porMes": sorted(([k, round(v, 2)] for k, v in por_mes.items())),
        "fornecedores": [[k, round(v, 2)] for k, v in fornecedores.most_common(10)],
        "recentes": itens[:30],
    }


def gerar_senadores() -> None:
    """Votos e projetos dos senadores em exercício -> site/dados/senador/<id>.json,
    site/dados/votacoes_senado.json (lista, sem o voto de cada um) e
    site/dados/votacao_senado/<id>.json (uma votação com o voto de cada senador)."""
    senadores = ler(BRUTO / "senado.json", []) or []
    if not senadores:
        return
    votacoes = []
    for arq in sorted((BRUTO / "senado_votacoes").glob("[0-9]*.json")):
        votacoes += ler(arq, {}).values()
    votacoes.sort(key=lambda v: (v["data"], v.get("hora") or ""), reverse=True)
    autorias = ler(BRUTO / "senado_autorias.json", {}) or {}
    ceaps = ler(BRUTO / "senado_ceaps.json", {}) or {}

    por_id = {str(s["id"]): s for s in senadores}
    resumo, votos_por_sen, primeira = [], defaultdict(dict), {}
    for v in votacoes:
        contagem = Counter(x[1] for x in v["votos"])
        placar = {k: n for k, n in contagem.items() if k != "ausente"}
        # placar oficial da API quando ela informa; senão, o que se conta dos votos individuais
        totais = v.get("totais")
        if totais:
            placar.update(totais)
        # votação em que ninguém tem voto com direção só pode ser secreta, mesmo em dados salvos antes do campo existir
        secreta = bool(v.get("secreta")) or (contagem["secreto"] > 0 and not any(contagem[k] for k in ("sim", "nao", "abstencao", "obstrucao")))
        item = {
            "id": v["id"], "data": v["data"], "hora": v.get("hora"), "descricao": v["descricao"],
            "proposicao": v.get("proposicao"), "propId": v.get("propId"), "ementa": v.get("ementa"),
            "aprovada": v.get("aprovada"), "resultadoTexto": v.get("resultadoTexto"),
            "placar": placar, "placarOficial": bool(totais), "ausentes": contagem["ausente"],
            **({"secreta": True} if secreta else {}),
            **({"sessao": v["sessao"]} if v.get("sessao") else {}),
        }
        resumo.append(item)
        por_partido = defaultdict(Counter)
        detalhados = []
        for sid, t, *resto in v["votos"]:
            votos_por_sen[sid][v["id"]] = t
            sen = por_id.get(str(sid))
            partido = (sen or {}).get("partido") or "?"
            por_partido[partido][t] += 1
            # rótulo oficial ("AP|Atividade parlamentar"): a parte depois de "|" explica a ausência
            motivo = resto[0].partition("|")[2] if t == "ausente" and resto and resto[0] else ""
            detalhados.append({
                "id": str(sid), "nome": sen["nome"] if sen else f"Senador {sid}",
                "partido": partido, "uf": (sen or {}).get("uf") or "", "voto": t,
                **({"motivo": motivo} if motivo else {}),
                # fora do exercício hoje: sem ficha no site para ligar
                **({} if sen else {"anterior": True}),
            })
            if sid not in primeira or v["data"] < primeira[sid]:
                primeira[sid] = v["data"]
        salvar(SAIDA / "votacao_senado" / f"{v['id']}.json", {
            **item,
            "porPartido": {p: dict(c) for p, c in sorted(por_partido.items())},
            "votos": sorted(detalhados, key=lambda x: x["nome"]),
        })
    salvar(SAIDA / "votacoes_senado.json", resumo)

    for s in senadores:
        sid = str(s["id"])
        desde = primeira.get(sid)  # antes do primeiro voto o senador pode nem estar em exercício
        propostas = [{k: v for k, v in a.items() if v not in (None, "")} for a in autorias.get(sid, [])]
        salvar(SAIDA / "senador" / f"{sid}.json", {
            "id": sid,
            "votos": [{"id": v["id"], "voto": votos_por_sen[sid].get(v["id"], "ausente")}
                      for v in resumo if desde and v["data"] >= desde],
            "proposicoes": propostas,
            # sem o arquivo (coleta falhou) o site mostra só o link para o Portal da Transparência
            **({"despesas": resumir_despesas(ceaps["ano"], ceaps["itens"].get(sid, []))} if ceaps else {}),
        })
    print(f"Gerado: {len(senadores)} senadores, {len(resumo)} votações nominais do Senado")


def gerar_eleitorado() -> None:
    """Perfil do eleitorado por estado (dados/tse/eleitorado): o ano mais recente que o estado tem."""
    for arq in sorted((BRUTO / "tse" / "eleitorado" / "2022").glob("[A-Z][A-Z].json")):
        for ano in (2024, 2022):
            dados = ler(BRUTO / "tse" / "eleitorado" / str(ano) / arq.name)
            if dados:
                salvar(SAIDA / "eleitorado" / arq.name, {"ano": ano, "d": dados})
                break


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

    detalhes = ler(BRUTO / "proposicoes_detalhe.json", {}) or {}

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
            "propId": v.get("propId"), "ementa": v.get("ementa"),
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
    eleicoes_deps = gerar_politicos.eleicao_deputados(deputados)
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
            "email": d.get("email"), "situacao": d.get("situacao"), "gabinete": d.get("gabinete") or None,
            "nascimento": d.get("nascimento"),
            "naturalidade": ", ".join(x for x in (d.get("municipioNascimento"), d.get("ufNascimento")) if x),
            "escolaridade": d.get("escolaridade"), "redesSociais": d.get("redesSociais", []),
            "proposicoes": [juntar_detalhe(p, detalhes.get(str(p["id"]))) for p in d["proposicoes"]],
            "votos": votos,
            "totalVotacoes": total_nominais, "eleicao": eleicoes_deps.get(did), "condicao": d.get("condicaoEleitoral"),
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
    gerar_senadores()
    gerar_politicos.gerar(deputados, gerar_estaduais.gerar())
    gerar_prefeituras.gerar()
    gerar_eleitorado()
    if (BRUTO / "executivo.json").exists():
        shutil.copy(BRUTO / "executivo.json", SAIDA / "executivo.json")
    shutil.copy(BRUTO / "municipios_ibge.json", SAIDA / "municipios_ibge.json")
    if (BRUTO / "historico").is_dir():   # histórico diário (scripts/historico.py): fica no git e a página historico.html lê daqui
        shutil.copytree(BRUTO / "historico", SAIDA / "historico")
    meta = ler(BRUTO / "meta.json", {}) or {}
    meta["ano"] = next(iter(deputados.values()))["despesas"]["ano"] if deputados else None
    meta["periodoVotacoes"] = [votacoes[-1]["data"], votacoes[0]["data"]] if votacoes else None
    salvar(SAIDA / "meta.json", meta)
    print(f"Gerado: {len(resumo_deps)} deputados, {len(lista_votacoes)} votações nominais -> {SAIDA}")


if __name__ == "__main__":
    main()
