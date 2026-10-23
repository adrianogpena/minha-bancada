"""
Núcleo de mandatos: cada mandato (pessoa, cargo, Casa, local, período, partido, condição) como um registro próprio.

  site/dados/nucleo/mandatos.json   [{id, pessoa, cargo, uf, municipio, eleicao, inicio, fim, condicao, status,
                                      partidoEleicao, partido, mudouPartido, ...}]

Fontes: os eleitos do TSE (2018 para senadores, 2022, 2024 e 2026), que dão cargo, local, partido na eleição e o período
do mandato (`gerar_politicos.MANDATOS`), e as listas de quem está em exercício: Câmara, Senado e Assembleias. Quem exerce
sem ter sido eleito (suplente) ganha um mandato próprio. Não acessa a internet; chamado pelo scripts/gerar.py.

Campos:
  cargo     o do TSE; `CASAS[cargo]` dá a Casa: presidencia, governo_estadual, senado, camara, assembleia, prefeitura ou camara_municipal
  condicao  só aparece quando é "suplente" (o que a Casa informa; o TSE só lista eleitos); sem o campo, é titular
  status    atual (no período e, onde há lista da Casa, em exercício), fora_de_exercicio (no período, mas fora da lista da Casa:
            quem assumiu o lugar é o suplente), futuro (eleito, ainda sem posse) ou encerrado
  confirmado   true quando uma lista da Casa (Câmara, Senado, Assembleia da UF) confirmou o exercício
  inicioAproximado   o início de quem exerce sem registro no TSE é o do período legal, não a data da posse
  partidoEleicao / partido   partido na eleição e o de hoje (o das fontes de exercício); `mudouPartido` só quando são partidos
            diferentes depois de considerar fusões e renomeações (PSL -> UNIÃO não conta). O dia da troca não é publicado
            pelas fontes, então não há período por partido.
"""

import datetime as dt
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

import identidades
from gerar_politicos import ler, periodo, salvar

CASAS = {
    "PRESIDENTE": "presidencia", "VICE-PRESIDENTE": "presidencia", "GOVERNADOR": "governo_estadual", "VICE-GOVERNADOR": "governo_estadual",
    "SENADOR": "senado", "DEPUTADO FEDERAL": "camara", "DEPUTADO ESTADUAL": "assembleia", "DEPUTADO DISTRITAL": "assembleia",
    "PREFEITO": "prefeitura", "VICE-PREFEITO": "prefeitura", "VEREADOR": "camara_municipal",
}
MUNICIPAIS = {"PREFEITO", "VICE-PREFEITO", "VEREADOR"}
INICIO_LEGISLATURA = "2023-02-01"
FIM_LEGISLATURA = "2027-01-31"


def vigente(par: str | None) -> str | None:
    """Partido de hoje de um id "par_…" (segue fusões); None para vazio."""
    if not par:
        return None
    chave = par[4:].upper()
    return "par_" + identidades._atual(chave).lower() if chave in identidades.PARTIDOS else par


def _id(pessoa: str, cargo: str, inicio: str, uf: str | None, municipio: str | None) -> str:
    return "man_" + hashlib.sha1(f"{pessoa}|{cargo}|{inicio}|{uf}|{municipio}".encode("utf-8")).hexdigest()[:12]


def _status(m: dict, hoje: str) -> str:
    if m["inicio"] > hoje:
        return "futuro"
    if m["fim"] < hoje:
        return "encerrado"
    return "atual"


def construir(deputados: dict, bruto: Path, nucleo: dict, hoje: str | None = None) -> dict:
    """Devolve {mandatos, resumo}. `nucleo` é o resultado de identidades.construir()."""
    hoje = hoje or dt.date.today().isoformat()
    chaves = nucleo["chaves"]
    mandatos: list[dict] = []
    por_pessoa_cargo = defaultdict(list)       # (pessoa, cargo) -> mandatos
    stats = Counter()
    por_id: dict = {}

    def novo(pessoa, cargo, ini, fim, uf, municipio=None, **extra) -> dict:
        if _id(pessoa, cargo, ini, uf, municipio) in por_id:    # a mesma pessoa duas vezes no mesmo cargo e local (registro repetido no TSE)
            stats["repetido"] += 1
            return por_id[_id(pessoa, cargo, ini, uf, municipio)]
        m = {"id": _id(pessoa, cargo, ini, uf, municipio), "pessoa": pessoa, "cargo": cargo, "uf": uf,
             **({"municipio": municipio} if municipio else {}), "inicio": ini, "fim": fim, "condicao": "titular", **extra}
        mandatos.append(m)
        por_id[m["id"]] = m
        por_pessoa_cargo[(pessoa, cargo)].append(m)
        return m

    # --- TSE: um mandato por eleito, no período legal do cargo
    for pasta in sorted(p for p in (bruto / "tse").glob("*") if p.is_dir() and p.name.isdigit()):
        ano = int(pasta.name)
        for arq in sorted(pasta.glob("[A-Z][A-Z].json")):
            for e in ler(arq, []):
                ini, fim = periodo(ano, e["cargo"])
                pessoa = chaves.get(("tse", ano, e["sequencial"]))
                if e.get("situacao") != "eleito" or not ini or not pessoa:
                    stats["tseSemMandato"] += 1
                    continue
                uf = "BR" if e["uf"] in ("BR", "BRASIL") else e["uf"]
                par = identidades.partido_id(e.get("partido"))
                m = novo(pessoa, e["cargo"], ini, fim, uf, e["unidadeEleitoral"] if e["cargo"] in MUNICIPAIS else None,
                         eleicao=ano, partidoEleicao=par, partido=par, fontes={"tse": e["sequencial"]},
                         **({"titularDe": e["titular"]} if e["cargo"].startswith("VICE-") and e.get("titular") else {}))
                m.setdefault("status", _status(m, hoje))

    def achar(pessoa: str, cargo: str) -> dict | None:
        """O mandato do TSE da pessoa que cobre hoje (ou o mais recente)."""
        ms = por_pessoa_cargo.get((pessoa, cargo), [])
        return next((m for m in ms if m["inicio"] <= hoje <= m["fim"]), None) or (max(ms, key=lambda m: m["inicio"]) if ms else None)

    def exercicio(fonte, chave_fonte, pessoa, cargo, casa_uf, par_atual, condicao, inicio_extra=None, fim_extra=None, **extra):
        """Liga quem exerce ao mandato do TSE ou, sem ele, cria o mandato (suplente). Devolve o mandato."""
        m = achar(pessoa, cargo)
        if m is None or not m["inicio"] <= hoje <= m["fim"]:
            ini = inicio_extra or INICIO_LEGISLATURA
            m = novo(pessoa, cargo, ini, fim_extra or FIM_LEGISLATURA, casa_uf, condicao="suplente" if condicao == "suplente" else "titular",
                     eleicao=None, partidoEleicao=None, inicioAproximado=True if not inicio_extra else None, fontes={}, **extra)
            m["status"] = _status(m, hoje)
            stats["mandatoSemTse"] += 1
        else:
            m["condicao"] = condicao
        m["fontes"][fonte] = chave_fonte
        m["confirmado"] = True
        if par_atual:
            m["partido"] = par_atual
        return m

    confirmadas = set()    # (pessoa, cargo) que uma lista da Casa confirmou, para achar quem ficou de fora

    # --- Câmara
    for did, d in deputados.items():
        pessoa = chaves.get(("camara", str(did)))
        if not pessoa:
            continue
        cond = "suplente" if "suplente" in (d.get("condicaoEleitoral") or "").lower() else "titular"
        m = exercicio("camara", d["id"], pessoa, "DEPUTADO FEDERAL", d["uf"], identidades.partido_id(d.get("partido")), cond)
        confirmadas.add(m["id"])

    # --- Senado
    for s in ler(bruto / "senado.json", []) or []:
        pessoa = chaves.get(("senado", str(s["id"])))
        if not pessoa:
            continue
        part = (s.get("participacao") or "").lower()
        cond = "suplente" if "suplente" in part else "titular"
        m = exercicio("senado", str(s["id"]), pessoa, "SENADOR", s["uf"], identidades.partido_id(s.get("partido")), cond,
                      inicio_extra=s.get("exercicioDesde") if cond == "suplente" else None, fim_extra=s.get("fimMandato") if cond == "suplente" else None,
                      **({"titularDe": s["titular"]} if cond == "suplente" and s.get("titular") else {}))
        confirmadas.add(m["id"])

    # --- Assembleias com lista coletada
    ufs_com_lista = set()
    for pasta in sorted(x for x in (bruto / "estaduais").glob("*") if x.is_dir()):
        uf = pasta.name
        deps = (ler(pasta / "deputados.json", {}) or {}).get("deputados", [])
        if not deps:
            continue
        ufs_com_lista.add(uf)
        for d in deps:
            pessoa = chaves.get(("estadual", uf, str(d["id"])))
            if not pessoa:
                continue
            cargo = next((c for c in ("DEPUTADO ESTADUAL", "DEPUTADO DISTRITAL") if por_pessoa_cargo.get((pessoa, c))),
                         "DEPUTADO DISTRITAL" if uf == "DF" else "DEPUTADO ESTADUAL")
            m = exercicio("estadual", f"{uf}:{d['id']}", pessoa, cargo, uf, identidades.partido_id(d.get("partido")),
                          "suplente" if d.get("titular") is False else "titular")
            confirmadas.add(m["id"])

    # --- quem foi eleito, está no período e a Casa não lista: o lugar é de um suplente
    tem_lista = {"camara": bool(deputados), "senado": bool(ler(bruto / "senado.json", []))}
    for m in mandatos:
        if m["status"] != "atual" or m["id"] in confirmadas:
            continue
        casa = CASAS[m["cargo"]]
        lista = tem_lista.get(casa) if casa in tem_lista else (casa == "assembleia" and m["uf"] in ufs_com_lista)
        if lista:
            m["status"] = "fora_de_exercicio"
            stats["foraDeExercicio"] += 1

    for m in mandatos:
        m["mudouPartido"] = bool(m.get("partidoEleicao") and m.get("partido") and vigente(m["partidoEleicao"]) != vigente(m["partido"]))
        for k in ("partidoEleicao", "partido", "confirmado", "inicioAproximado"):
            if m.get(k) is None:
                m.pop(k, None)
        if not m["mudouPartido"]:
            del m["mudouPartido"]
        if m["condicao"] == "titular":     # o padrão não se repete 72 mil vezes
            del m["condicao"]
        if not m.get("fontes"):
            m.pop("fontes", None)
    mandatos.sort(key=lambda m: (m["pessoa"], m["inicio"], m["cargo"], m["id"]))
    ids = [m["id"] for m in mandatos]
    if len(ids) != len(set(ids)):
        raise RuntimeError("colisão de id de mandato")
    resumo = {"total": len(mandatos), "porStatus": dict(Counter(m["status"] for m in mandatos)),
              "porCasa": dict(Counter(CASAS[m["cargo"]] for m in mandatos if m["status"] == "atual")),
              "mudaramDePartido": sum(1 for m in mandatos if m.get("mudouPartido") and m["status"] == "atual"), **dict(stats)}
    return {"mandatos": mandatos, "resumo": resumo}


def salvar_mandatos(res: dict, saida: Path) -> None:
    salvar(saida / "nucleo" / "mandatos.json", res["mandatos"])
    r = res["resumo"]
    print(f"Mandatos: {r['total']} ({r['porStatus']}); trocaram de partido: {r['mudaramDePartido']}")
