"""
Ministros de Estado para o site, a partir de dados/ministros/ (coletar_ministros.py). Sem internet; chamado por gerar.py.

  site/dados/ministerios.json           [{pasta, nome, ministro: {pessoa, nome, inicio}|None, total, informacao, convocacao, respondidos}]
  site/dados/ministerio/<pasta>.json    {pasta, nome, descricao?: {resumo, areas, site, base: [{rotulo, url}], revisadoEm}, ministros: [{pessoa, nome, cargo, inicio, inicioFonte, nomeadoPor?, inicioUrl?, fim?, atual, requerimentos: [id]}],
                                         requerimentos: [...]}   cada requerimento aparece só na pasta em que a ementa o cita primeiro
  site/dados/ministros_autores.json     {id do deputado: nome} dos autores que não estão em deputados.json (já saíram da Câmara)
  site/dados/ministro/<pessoa>.json     {pessoa, nome, cargos: [{pasta, nome, cargo, inicio, inicioFonte, nomeadoPor?, inicioUrl?, fim?, atual, requerimentos: [id]}],
                                         parlamentar: {casa, id, inicio}|None}   os pedidos em si estão em ministerio/<pasta>.json

Requerimento: {id, fonte: camara|senado, idFonte, tipo, natureza: informacao|convocacao|convite, numero, ano, ementa, data, situacao,
  autores: [id do deputado ou do senador], autoria? (texto do Senado, só quando algum autor não foi ligado), pastas? (outras pastas citadas),
  remessa?, prazoFim?, resposta? (RIC), deliberacao?, dataDeliberacao?, tramitando?, documento? (Senado)}. A pasta de cada pedido vem de
`ministerios.pastas_do_texto` e a ligação com o ministro e com o senador, de `identidades` (registrada em `ligacoes["ministros"]`).
"""

import re
from collections import Counter, defaultdict
from pathlib import Path

import identidades
import ministerios
from estaduais_comum import avisar, sem_acento
from gerar_politicos import ler, salvar

DESCRICAO = Path(__file__).with_name("ministerios_descricao.json")   # escrito à mão, por chave de ministerios.PASTAS
CAMPOS_CAMARA = ("tipo", "numero", "ano", "ementa", "situacao", "remessa", "prazoFim", "resposta")
CAMPOS_SENADO = ("ementa", "deliberacao", "dataDeliberacao", "tramitando", "documento")


def descricoes(caminho: Path = DESCRICAO) -> dict:
    """O que cada pasta faz (texto versionado). Pasta sem descrição vira aviso e a página some com o bloco."""
    d = ler(caminho, {}) or {}
    falta = [k for k in ministerios.PASTAS if k not in d]
    if falta:
        avisar(f"ministérios sem descrição em {caminho.name}: {', '.join(falta)}")
    return {k: v for k, v in d.items() if k in ministerios.PASTAS}


def natureza(tipo: str, ementa: str, conteudo: str | None = None) -> str:
    if tipo == "RIC" or conteudo == "Informações":
        return "informacao"
    t = sem_acento(ementa or "").lower()
    return "convite" if re.search(r"convite|convida", t) and not re.search(r"convoca", t) else "convocacao"


def requerimentos_da_camara(bruto: Path) -> tuple[list[dict], dict]:
    """(requerimentos, {id do deputado: nome como a Câmara publicou})."""
    saida, nomes = [], {}
    for arq in sorted((bruto / "ministros").glob("camara_*.json")):
        for rid, it in (ler(arq, {}) or {}).get("itens", {}).items():
            saida.append({"id": f"camara-{rid}", "fonte": "camara", "idFonte": str(rid),
                          **{k: it[k] for k in CAMPOS_CAMARA if it.get(k) not in (None, "")},
                          "natureza": natureza(it["tipo"], it["ementa"]), "data": it.get("dataApresentacao"),
                          "autores": [str(a[0]) for a in it.get("autores", [])]})
            nomes.update({str(a[0]): a[1] for a in it.get("autores", [])})
    return saida, nomes


def requerimentos_do_senado(bruto: Path) -> list[dict]:
    saida = []
    for arq in sorted((bruto / "ministros").glob("senado_*.json")):
        for rid, it in (ler(arq, {}) or {}).get("itens", {}).items():
            m = re.match(r"^(\S+)\s+(\d+)/(\d{4})$", it.get("identificacao") or "")
            saida.append({"id": f"senado-{rid}", "fonte": "senado", "idFonte": str(rid),
                          "tipo": m.group(1) if m else "RQS", "numero": int(m.group(2)) if m else None, "ano": int(m.group(3)) if m else None,
                          **{k: it[k] for k in CAMPOS_SENADO if it.get(k) not in (None, "")},
                          "natureza": natureza("RQS", it["ementa"], it.get("tipoConteudo")), "data": it.get("dataApresentacao"),
                          "_autoria": it.get("autoria")})
    return saida


def construir(bruto: Path, nucleo: dict, senadores: list[dict], deputados: dict | None = None) -> dict:
    """Liga os requerimentos às pastas, aos ministros e aos senadores e grava a tabela em `nucleo["ligacoes"]["ministros"]`.
    Devolve {ministerios, ministerio: {pasta: {...}}, ministro: {pessoa: {...}}}."""
    ministros = nucleo.get("ministros", [])
    da_camara, nomes = requerimentos_da_camara(bruto)
    pedidos = da_camara + requerimentos_do_senado(bruto)
    for r in pedidos:
        r["pastas"] = ministerios.pastas_do_texto(r["ementa"])
    primaria = {r["id"]: r["pastas"][:1] for r in pedidos}
    ligados = identidades.ligar_requerimentos(
        {r["id"]: {"ementa": r["ementa"], "dataApresentacao": r["data"] or "", "pastas": r["pastas"]} for r in pedidos}, ministros)
    autoria = identidades.ligar_autoria_senado([r["_autoria"] for r in pedidos if r["fonte"] == "senado"], senadores)
    for r in pedidos:
        texto = r.pop("_autoria", None)
        if r["fonte"] == "senado":
            achados = autoria.get(texto, [])
            r["autores"] = [a[0] for a in achados]
            if texto and len(achados) < len(re.findall(r"\([^/()]+/[A-Z]{2}\)", texto)):
                r["autoria"] = texto
        outras = r["pastas"][1:]
        r["pastas"] = outras
        if not outras:
            del r["pastas"]

    sem_pasta = [r["id"] for r in pedidos if not primaria[r["id"]]]
    por_pasta = defaultdict(list)
    for r in pedidos:
        if primaria[r["id"]]:
            por_pasta[primaria[r["id"]][0]].append(r)
    por_ministro = defaultdict(list)
    for rid, (pessoa, _, _) in ligados.items():
        por_ministro[(pessoa, primaria[rid][0])].append(rid)

    cargos = defaultdict(list)
    for m in ministros:
        cargos[m["pasta"]].append({
            "pessoa": m["pessoa"], "nome": m["nome"], "cargo": m["cargo"], "inicio": m["inicio"], "inicioFonte": m["inicioFonte"],
            **{k: m[k] for k in ("nomeadoPor", "inicioUrl") if m.get(k)},
            **({"fim": m["fim"]} if m.get("fim") else {}), "atual": not m.get("fim"),
            "requerimentos": sorted(por_ministro.get((m["pessoa"], m["pasta"]), []))})

    descricao = descricoes()
    pessoas = {p["id"]: p for p in nucleo["pessoas"]}
    saida = {"ministerio": {}, "ministro": {}}
    resumo = []
    for pasta, (nome, _) in sorted(ministerios.PASTAS.items(), key=lambda kv: kv[1][0]):
        lista = sorted(por_pasta.get(pasta, []), key=lambda r: (r["data"] or "", r["id"]), reverse=True)
        if not lista and pasta not in cargos:
            continue
        titulares = sorted(cargos.get(pasta, []), key=lambda c: c["inicio"], reverse=True)
        saida["ministerio"][pasta] = {"pasta": pasta, "nome": nome, **({"descricao": descricao[pasta]} if pasta in descricao else {}),
                                     "ministros": titulares, "requerimentos": lista}
        atual = next((c for c in titulares if c["atual"]), None)
        resumo.append({"pasta": pasta, "nome": nome,
                       "ministro": {k: atual[k] for k in ("pessoa", "nome", "inicio")} if atual else None,
                       "total": len(lista), "informacao": sum(r["natureza"] == "informacao" for r in lista),
                       "convocacao": sum(r["natureza"] != "informacao" for r in lista),
                       "respondidos": sum(1 for r in lista if r.get("resposta"))})
    for pasta, titulares in cargos.items():
        for c in titulares:
            p = saida["ministro"].setdefault(c["pessoa"], {"pessoa": c["pessoa"], "nome": c["nome"], "cargos": [],
                                                           "parlamentar": None})
            p["cargos"].append({**c, "pasta": pasta, "nomePasta": ministerios.PASTAS[pasta][0]})
    for pid, ficha in saida["ministro"].items():
        ficha["cargos"].sort(key=lambda c: c["inicio"], reverse=True)
        fontes = pessoas.get(pid, {}).get("fontes", {})
        for casa in ("camara", "senado"):
            if fontes.get(casa):
                ficha["parlamentar"] = {"casa": casa, "id": str(fontes[casa])}
                break
        ficha["ligacao"] = pessoas.get(pid, {}).get("ligacao", {}).get("planalto")

    nucleo["ligacoes"]["ministros"] = {
        "requerimentos": dict(sorted(ligados.items())),
        "autoriaSenado": {t: a for t, a in autoria.items() if a},
        "resumo": {"requerimentos": len(pedidos), "comPasta": len(pedidos) - len(sem_pasta), "semPasta": len(sem_pasta),
                   "comMinistro": len(ligados), "porMetodo": dict(Counter(f"{v[1]} ({v[2]})" for v in ligados.values())),
                   "autoriaSenadoLigada": sum(1 for a in autoria.values() if a), "autoriaSenadoTextos": len(autoria)},
    }
    usados = {a for r in pedidos if r["fonte"] == "camara" for a in r["autores"]}
    fora = {a: nomes[a] for a in sorted(usados - {str(d) for d in (deputados or {})}) if a in nomes}
    return {"ministerios": resumo, **saida, "total": len(pedidos), "autoresFora": fora}


def salvar_ministros(res: dict, saida: Path) -> None:
    salvar(saida / "ministerios.json", res["ministerios"])
    salvar(saida / "ministros_autores.json", res["autoresFora"])
    for pasta, dados in res["ministerio"].items():
        salvar(saida / "ministerio" / f"{pasta}.json", dados)
    for pessoa, dados in res["ministro"].items():
        salvar(saida / "ministro" / f"{pessoa}.json", dados)
    print(f"Ministros: {len(res['ministro'])} pessoas, {len(res['ministerio'])} pastas, {res['total']} requerimentos")
