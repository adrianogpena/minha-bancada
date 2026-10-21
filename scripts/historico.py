"""
Histórico diário: tudo o que mudou nos dados em cada dia, com fonte, separado por local e, quando dá, por político.

A execução diária faz um commit "Dados atualizados em AAAA-MM-DD". Este script compara os dados antes e depois do dia
(como o resumo por e-mail e os feeds RSS) e grava dados/historico/AAAA-MM-DD.json, que fica no git: o histórico só cresce.
Depois espelha tudo em site/dados/historico/ (com indice.json), que a página historico.html lê.

Cada evento do dia:
    l     local: "BR", "UF:SP" ou "MUN:SP" (capital)         uf   estado de quem aparece (filtro por estado)
    k     categoria: nova, situacao, votacao, eleicao         t    título curto (ex.: "PL 123/2026")
    p     políticos: [{c: código do "Fique informado" ou null, n: nome, h: página no site ou null}]
    x     texto (ementa, despacho)     m  [antes, depois] de uma mudança     s  resumo (placar, resultado)
    d     data do ato (AAAA-MM-DD)     f  fontes: [[rótulo, URL], ...]
Os códigos de local e de político são os mesmos do feeds.py.

Uso:
    python scripts/historico.py [ANTES [DEPOIS]] [--dias N] [--saida PASTA]
    (sem argumentos: o último dia com commit de dados; --dias N refaz os N últimos dias, para reconstruir o passado)
"""

import argparse
import json
import re
import shutil
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import feeds
import resumo_email as r

PASTA = r.RAIZ / "dados" / "historico"
SITE_PASTA = r.RAIZ / "site" / "dados" / "historico"
SITE_DADOS = r.RAIZ / "site" / "dados"
CAMARA_API = "https://dadosabertos.camara.leg.br/api/v2"
SENADO_MATERIA = "https://www25.senado.leg.br/web/atividade/materias/-/materia/"
TSE_DADOS = "https://dadosabertos.tse.jus.br"
TSE_CDN = "https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_{ano}.zip"
# a situação só vira evento para projetos de verdade; requerimentos, emendas e pareceres entram só quando são apresentados
PROJETOS = {"PL", "PLP", "PEC", "PDL", "MPV", "PRC", "PLN", "PLV", "PFC", "PLC", "PLS", "PRS", "PDS"}
LIMITE_TEXTO = 1200
LIMITE_ELEICAO = 200   # por arquivo do TSE; acima disso é carga em lote (eleição nova, recoleta), resumida em um evento só


# ---------------------------------------------------------------- leitura do git

def ler_lote(rev: str, caminhos: list[str]) -> dict:
    """{caminho: JSON} dos arquivos que existem em `rev`, com um único processo git."""
    if not caminhos:
        return {}
    p = subprocess.run(["git", "cat-file", "--batch"], cwd=r.RAIZ, check=True, capture_output=True,
                       input="".join(f"{rev}:{c}\n" for c in caminhos).encode())
    saida, buf, pos = {}, p.stdout, 0
    for c in caminhos:
        fim = buf.index(b"\n", pos)
        cab = buf[pos:fim].split()
        pos = fim + 1
        if cab[-1] == b"missing":
            continue
        n = int(cab[2])
        try:
            saida[c] = json.loads(buf[pos:pos + n])
        except ValueError:
            pass
        pos += n + 1
    return saida


def listar(rev: str, prefixo: str) -> list[str]:
    try:
        return r.git("ls-tree", "-r", "--name-only", rev, "--", prefixo).split()
    except subprocess.CalledProcessError:
        return []


def dias_git(n: int | None) -> list[tuple[str, str, str]]:
    """[(data, antes, depois)] dos n últimos dias com commit de dados, do mais novo ao mais antigo.
    Vários commits no mesmo dia viram um dia só: do pai do primeiro ao último."""
    por_dia = defaultdict(list)
    for linha in r.git("log", "--grep=^Dados atualizados em", "--format=%H %cs").splitlines():
        commit, data = linha.split()
        por_dia[data].append(commit)   # do mais novo ao mais antigo
    saida = []
    for data in sorted(por_dia, reverse=True):
        commits = por_dia[data]
        try:
            r.git("rev-parse", "--verify", "-q", f"{commits[-1]}~1")
        except subprocess.CalledProcessError:
            continue   # histórico raso ou primeiro commit: nada para comparar
        saida.append((data, f"{commits[-1]}~1", commits[0]))
        if n and len(saida) >= n:
            break
    return saida


# ---------------------------------------------------------------- nomes e links

class Contexto:
    """Nomes e páginas dos políticos, do que o gerar.py já montou em site/dados (com alternativas quando falta)."""

    def __init__(self, depois: str):
        self.depois = depois
        self.codigos = {}    # código do "Fique informado" -> (nome, página)
        self.deputados = {}  # id da Câmara -> (nome, UF)
        self.capitais = {}
        self.senadores = {}  # id do Senado -> nome
        for arq in sorted((SITE_DADOS / "indice").glob("*.json")) if (SITE_DADOS / "indice").is_dir() else []:
            if not arq.stem.isalpha():
                continue
            for x in json.loads(arq.read_text(encoding="utf-8")):
                if x.get("a"):
                    self.codigos.setdefault(x["a"], (x["n"], x.get("h")))
        try:
            self.capitais = json.loads((SITE_DADOS / "cobertura.json").read_text(encoding="utf-8"))["capitais"]
        except (OSError, ValueError, KeyError):
            pass
        try:
            for d in json.loads((SITE_DADOS / "deputados.json").read_text(encoding="utf-8")):
                self.deputados[int(d["id"])] = (d["nome"], d["uf"])
        except (OSError, ValueError, KeyError):
            pass
        try:
            for s in json.loads((r.RAIZ / "dados" / "senado.json").read_text(encoding="utf-8")):
                self.senadores[str(s["id"])] = s.get("nome")
        except (OSError, ValueError, KeyError, TypeError):
            pass
        self._assembleias = {}

    def assembleia(self, uf: str) -> dict:
        """{host, nomes: {id SAPL: nome}} da Assembleia, no commit `depois`."""
        if uf not in self._assembleias:
            d = ler_lote(self.depois, [f"dados/estaduais/{uf}/deputados.json"]).get(f"dados/estaduais/{uf}/deputados.json") or {}
            self._assembleias[uf] = {"host": d.get("host"), "nomes": {x["id"]: x.get("nome") for x in d.get("deputados", [])}}
        return self._assembleias[uf]

    def politico(self, codigo: str, padrao: str) -> dict:
        nome, pagina = self.codigos.get(codigo, (padrao, None))
        return {"c": codigo, "n": nome, **({"h": pagina} if pagina else {})}

    def deputado(self, did: int) -> dict:
        nome, uf = self.deputados.get(did, (None, None))
        if not nome:
            ficha = r.RAIZ / "dados" / "deputados" / f"{did}.json"
            try:
                f = json.loads(ficha.read_text(encoding="utf-8"))
                nome, uf = f["nome"], f.get("uf")
            except (OSError, ValueError, KeyError):
                pass
        return {"c": f"dep:{did}", "n": nome or f"Deputado(a) {did}", "h": f"deputado.html?id={did}", "uf": uf}

    def nome_local(self, codigo: str) -> str:
        if codigo == "BR":
            return "Brasil: Câmara, Senado e Presidência"
        tipo, uf = codigo.split(":")
        if tipo == "UF":
            return f"Estado: {feeds.UFS.get(uf, uf)}"
        return f"Capital: {self.capitais.get(uf, uf)} ({uf})"


def cortar(texto, n: int = LIMITE_TEXTO) -> str:
    texto = " ".join(str(texto or "").split())
    return texto if len(texto) <= n else texto[: n - 1] + "…"


def evento(local: str, k: str, t: str, *, uf=None, p=None, x=None, m=None, s=None, d=None, f=None) -> dict:
    e = {"l": local, "k": k, "t": t, "uf": uf, "p": p or None, "x": cortar(x) or None, "m": m, "s": s, "d": d,
         "f": [list(a) for a in (f or []) if a and a[1]]}
    return {k_: v for k_, v in e.items() if v not in (None, [], "")}


def mudou(a, b) -> bool:
    return (a or "") != (b or "")


# ---------------------------------------------------------------- coletores, um por fonte

def fontes_camara(pid, teor=None) -> list:
    return [("Ficha de tramitação (Câmara)", f"https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao={pid}"),
            ("API da Câmara", f"{CAMARA_API}/proposicoes/{pid}"), ("Inteiro teor", teor)]


def camara(ctx: Contexto, antes: str, depois: str) -> list:
    """Proposições novas por deputado e mudanças de situação dos projetos."""
    if not listar(antes, "dados/proposicoes"):
        return []   # primeira coleta: tudo seria "novo"
    arquivos_ = r.arquivos(antes, depois, "dados/proposicoes")
    a, b = ler_lote(antes, arquivos_), ler_lote(depois, arquivos_)
    novas = {}
    for f in arquivos_:
        ids = {i["id"] for i in (a.get(f) or {}).get("itens", [])}
        for i in (b.get(f) or {}).get("itens", []):
            if i["id"] not in ids:
                novas.setdefault(i["id"], {**i, "deps": []})["deps"].append(int(Path(f).stem))
    det_a = ler_lote(antes, ["dados/proposicoes_detalhe.json"]).get("dados/proposicoes_detalhe.json") or {}
    det_b = ler_lote(depois, ["dados/proposicoes_detalhe.json"]).get("dados/proposicoes_detalhe.json") or {}
    saida = []

    def autores(deps):
        ps = [ctx.deputado(d) for d in sorted(deps)]
        return ps, next((p["uf"] for p in ps if p.get("uf")), None)

    for i in novas.values():
        ps, uf = autores(i["deps"])
        det = det_b.get(str(i["id"])) or {}
        saida.append(evento("BR", "nova", f"{i['siglaTipo']} {i['numero']}/{i['ano']}", uf=uf, p=ps, x=i.get("ementa"),
                            d=det.get("apres"), f=fontes_camara(i["id"], det.get("inteiroTeor"))))
    mudancas = [pid for pid, y in det_b.items() if pid in det_a and (mudou(det_a[pid].get("sit"), y.get("sit")) or mudou(det_a[pid].get("tram"), y.get("tram")))]
    if mudancas:
        meta = {}
        todos = ler_lote(depois, listar(depois, "dados/proposicoes"))
        for f, d in todos.items():
            for i in d.get("itens", []):
                m = meta.setdefault(str(i["id"]), {**i, "deps": []})
                m["deps"].append(int(Path(f).stem))
        for pid in mudancas:
            i, y, x = meta.get(pid), det_b[pid], det_a[pid]
            if not i or i["siglaTipo"] not in PROJETOS:
                continue
            ps, uf = autores(i["deps"])
            sit = mudou(x.get("sit"), y.get("sit"))
            antes_, depois_ = (x.get("sit"), y.get("sit")) if sit else (x.get("tram"), y.get("tram"))
            saida.append(evento("BR", "situacao", f"{i['siglaTipo']} {i['numero']}/{i['ano']}", uf=uf, p=ps, x=y.get("desp") or i.get("ementa"),
                                m=[antes_ or "—", depois_ or "—"], s=None if sit else "Nova tramitação", d=y.get("data"),
                                f=fontes_camara(pid, y.get("inteiroTeor"))))
    return saida


def votos_camara(votos: list) -> str:
    c = Counter(v[1] for v in votos)
    return ", ".join(f"{c[k]} {k.lower()}" for k in ("Sim", "Não", "Abstenção") if c[k])


def votacoes_camara(ctx: Contexto, antes: str, depois: str) -> list:
    if not listar(antes, "dados/votacoes"):
        return []
    arquivos_ = r.arquivos(antes, depois, "dados/votacoes")
    a, b = ler_lote(antes, arquivos_), ler_lote(depois, arquivos_)
    saida = []
    for f in arquivos_:
        for vid, v in (b.get(f) or {}).items():
            if vid in (a.get(f) or {}):
                continue
            res = {1: "Aprovada", 0: "Rejeitada"}.get(v.get("aprovada"), "Sem resultado informado")
            placar = votos_camara(v.get("votos") or [])
            saida.append(evento("BR", "votacao", v.get("proposicao") or "Votação no Plenário da Câmara", x=v.get("ementa") or v.get("descricao"),
                                s=f"{res}{', ' + placar if placar else ''}", d=v.get("data"),
                                f=[("Votação no site", f"votacao.html?id={vid}"), ("API da Câmara", f"{CAMARA_API}/votacoes/{vid}"),
                                   ("Ficha de tramitação (Câmara)", f"https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao={v['propId']}") if v.get("propId") else None]))
    return saida


def senado(ctx: Contexto, antes: str, depois: str) -> list:
    """Matérias novas e mudanças de situação (o título e o autor vêm de dados/senado_autorias.json, quando o arquivo existe)."""
    a = ler_lote(antes, ["dados/senado_materias.json"]).get("dados/senado_materias.json")
    b = ler_lote(depois, ["dados/senado_materias.json"]).get("dados/senado_materias.json") or {}
    if not a:
        return []
    autoria = {}
    try:
        for sid, itens in json.loads((r.RAIZ / "dados" / "senado_autorias.json").read_text(encoding="utf-8")).items():
            for i in itens:
                autoria.setdefault(i["id"], (sid, i))
    except (OSError, ValueError):
        pass
    saida = []
    for mid, m in b.items():
        if mid in a and (not a[mid].get("sit") or not mudou(a[mid].get("sit"), m.get("sit"))):
            continue   # sem situação anterior é a coleta preenchendo o campo, não uma mudança
        sid, i = autoria.get(mid, (None, None))
        nome = ctx.senadores.get(sid)
        ps = [{"c": None, "n": nome, "h": f"politico.html?f=senado&i={sid}"}] if nome else None
        titulo = f"{i['tipo']} {i['numero']}/{i['ano']}" if i else f"Matéria {mid} do Senado"
        fontes_ = [("Matéria no Senado", SENADO_MATERIA + mid), ("Dados abertos do Senado", "https://legis.senado.leg.br/dadosabertos/processo/" + str(m["proc"]) if m.get("proc") else None)]
        if mid in a:
            saida.append(evento("BR", "situacao", titulo, p=ps, x=i and i["ementa"], m=[a[mid].get("sit") or "—", m.get("sit") or "—"], d=m.get("data"), f=fontes_))
        else:
            saida.append(evento("BR", "nova", titulo, p=ps, x=i and i["ementa"], s=m.get("sit"), d=m.get("ap") or m.get("data"), f=fontes_))
    return saida


def votacoes_senado(ctx: Contexto, antes: str, depois: str) -> list:
    if not listar(antes, "dados/senado_votacoes"):
        return []
    arquivos_ = r.arquivos(antes, depois, "dados/senado_votacoes")
    a, b = ler_lote(antes, arquivos_), ler_lote(depois, arquivos_)
    saida = []
    for f in arquivos_:
        for vid, v in (b.get(f) or {}).items():
            if vid in (a.get(f) or {}):
                continue
            tot = v.get("totais") or {}
            placar = ", ".join(f"{tot[k]} {n}" for k, n in (("totalVotosSim", "sim"), ("totalVotosNao", "não"), ("totalVotosAbstencao", "abstenções")) if tot.get(k) is not None)
            res = "Votação secreta" if v.get("secreta") else {1: "Aprovada", 0: "Rejeitada"}.get(v.get("aprovada"), v.get("resultadoTexto") or "Sem resultado informado")
            saida.append(evento("BR", "votacao", f"{v['proposicao']} (Senado)" if v.get("proposicao") else "Votação no Plenário do Senado", x=v.get("ementa") or v.get("descricao"),
                                s=f"{res}{', ' + placar if placar else ''}", d=v.get("data"),
                                f=[("Votação no site", f"votacao.html?casa=senado&id={vid}"),
                                   ("Matéria no Senado", SENADO_MATERIA + str(v["propId"])) if v.get("propId") else None,
                                   ("Dados abertos do Senado", "https://legis.senado.leg.br/dadosabertos/votacao")]))
    return saida


def executivo(ctx: Contexto, antes: str, depois: str) -> list:
    a = ler_lote(antes, ["dados/executivo.json"]).get("dados/executivo.json")
    b = ler_lote(depois, ["dados/executivo.json"]).get("dados/executivo.json") or []
    if a is None:
        return []
    ant = {i["id"]: i for i in a}
    pres = [ctx.politico("pres", "Presidência da República")]
    saida = []
    for i in b:
        x = ant.get(i["id"])
        if x and not mudou(x.get("sit"), i.get("sit")):
            continue
        saida.append(evento("BR", "situacao" if x else "nova", f"{i['tipo']} {i['numero']}/{i['ano']}", p=pres, x=i.get("ementa"),
                            m=[x.get("sit") or "—", i.get("sit") or "—"] if x else None, s=None if x else i.get("sit"), d=i.get("data") or i.get("apres"),
                            f=fontes_camara(i["id"], i.get("inteiroTeor"))))
    return saida


def sapl(ctx: Contexto, antes: str, depois: str, uf: str, arquivo: str, local: str, politicos, host_de, sufixo=r"materias_\d{4}") -> list:
    """Matérias novas e com nova situação num arquivo materias_/governo_/prefeitura_<ano>.json de um estado ou capital."""
    todos = [f for f in r.arquivos(antes, depois, f"dados/{arquivo}/{uf}") if re.search(sufixo + r"\.json$", f)]
    a, b = ler_lote(antes, todos), ler_lote(depois, todos)
    saida = []
    for f in todos:
        if f not in a and not listar(antes, f"dados/{arquivo}/{uf}"):
            continue   # primeira coleta do estado ou da capital
        ant = (a.get(f) or {}).get("materias", {})
        for mid, m in ((b.get(f) or {}).get("materias") or {}).items():
            novo = mid not in ant
            if not novo and not mudou(ant[mid].get("sit"), m.get("sit")):
                continue
            host = host_de(b.get(f))
            titulo = f"{m.get('td') or m.get('t', '')} {m.get('n', '')}/{m.get('a', '')}".strip()
            saida.append(evento(local, "nova" if novo else "situacao", titulo, uf=uf, p=politicos(m), x=m.get("e"),
                                m=None if novo else [ant[mid].get("sit") or "—", m.get("sit") or "—"], s=m.get("sit") if novo else None, d=m.get("ap"),
                                f=[("Matéria no sistema legislativo", f"https://{host}/materia/{mid}" if host and str(mid).isdigit() else None), ("Texto", m.get("pdf"))]))
    return saida


def estados(ctx: Contexto, antes: str, depois: str) -> list:
    saida = []
    ufs = sorted({f.split("/")[2] for f in r.arquivos(antes, depois, "dados/estaduais")})
    for uf in ufs:
        if not listar(antes, f"dados/estaduais/{uf}/deputados.json"):
            continue
        ass = ctx.assembleia(uf)
        saida += sapl(ctx, antes, depois, uf, "estaduais", f"UF:{uf}",
                      lambda m, uf=uf, ass=ass: [ctx.politico(f"est:{uf}:{d}", ass["nomes"].get(d) or f"Deputado(a) estadual {d}") for d in m.get("dep", [])] or None,
                      lambda _, ass=ass: ass["host"])
        gov = [ctx.politico(f"gov:{uf}", f"Governo estadual ({uf})")]
        saida += sapl(ctx, antes, depois, uf, "estaduais", f"UF:{uf}", lambda m, gov=gov: gov, lambda _, ass=ass: ass["host"], r"governo_\d{4}")
        saida += votacoes_estaduais(ctx, antes, depois, uf, ass)
    return saida


def votacoes_estaduais(ctx: Contexto, antes: str, depois: str, uf: str, ass: dict) -> list:
    caminho = f"dados/estaduais/{uf}/votacoes.json"
    a = ler_lote(antes, [caminho]).get(caminho)
    if a is None:
        return []
    b = ler_lote(depois, [caminho]).get(caminho) or {}
    novas = {k: v for k, v in b.get("votacoes", {}).items() if k not in a.get("votacoes", {})}
    if not novas:
        return []
    arqs = listar(depois, f"dados/estaduais/{uf}/materias_")
    lotes = ler_lote(depois, [f"dados/estaduais/{uf}/materias_votadas.json"] + [x for x in arqs if re.search(r"materias_\d{4}\.json$", x)])
    materias = {}
    for caminho_, d in lotes.items():
        materias.update(d.get("materias", d) if isinstance(d, dict) else {})
    saida = []
    for vid, v in novas.items():
        m = materias.get(str(v.get("m"))) or {}
        titulo = f"{m.get('t', '')} {m.get('n', '')}/{m.get('a', '')}".strip() if m else f"Matéria {v.get('m')}"
        placar = f"{v.get('sim', 0)} sim, {v.get('nao', 0)} não, {v.get('abs', 0)} abstenções"
        saida.append(evento(f"UF:{uf}", "votacao", f"{titulo} (votação nominal)", uf=uf, x=m.get("e"), s=f"{v.get('res') or 'Sem resultado informado'}, {placar}", d=v.get("d"),
                            f=[("Matéria no sistema legislativo", f"https://{ass['host']}/materia/{v['m']}" if ass.get("host") and v.get("m") else None)]))
    return saida


def capitais(ctx: Contexto, antes: str, depois: str) -> list:
    saida = []
    for uf in sorted({f.split("/")[2] for f in r.arquivos(antes, depois, "dados/municipais")}):
        if not listar(antes, f"dados/municipais/{uf}"):
            continue
        pref = [ctx.politico(f"pref:{uf}", f"Prefeitura de {ctx.capitais[uf]}" if uf in ctx.capitais else f"Prefeitura da capital ({uf})")]
        saida += sapl(ctx, antes, depois, uf, "municipais", f"MUN:{uf}", lambda m, pref=pref: pref, lambda arq: (arq or {}).get("host"), r"prefeitura_\d{4}")
    return saida


def eleitos(ctx: Contexto, antes: str, depois: str) -> list:
    """Eleitos que entraram, saíram ou mudaram de situação ou partido nos arquivos do TSE (votos e redes sociais ficam de fora: mudam sem novidade)."""
    arquivos_ = [f for f in r.arquivos(antes, depois, "dados/tse") if re.fullmatch(r"dados/tse/\d{4}/[A-Z]{2}\.json", f)]
    a, b = ler_lote(antes, arquivos_), ler_lote(depois, arquivos_)
    saida = []
    for f in arquivos_:
        if f not in a:
            continue
        ano, uf = f.split("/")[2], f.split("/")[3][:2]
        ant = {c["sq"]: c for c in a[f]}
        atual = {c["sq"]: c for c in b.get(f, [])}
        fontes_ = [("Candidatos e eleitos (TSE, dados abertos)", TSE_DADOS), ("Arquivo usado", TSE_CDN.format(ano=ano))]
        antes_n = len(saida)
        for sq in sorted(set(ant) | set(atual)):
            x, y = ant.get(sq), atual.get(sq)
            c = y or x
            titulo = f"{c.get('urna') or c['nome']}, {c['cargo'].title()} ({c['partido']}), eleição de {ano}"
            local = "BR" if uf == "BR" else f"UF:{c['uf']}"
            if not x:
                saida.append(evento(local, "eleicao", titulo, uf=None if uf == "BR" else c["uf"], s=f"Passou a constar como {c.get('situacao')}", f=fontes_))
            elif not y:
                saida.append(evento(local, "eleicao", titulo, uf=None if uf == "BR" else c["uf"], s="Deixou de constar entre os eleitos", f=fontes_))
            else:
                for campo, rotulo in (("situacao", "Situação"), ("resultado", "Resultado"), ("partido", "Partido")):
                    if mudou(x.get(campo), y.get(campo)):
                        saida.append(evento(local, "eleicao", titulo, uf=None if uf == "BR" else c["uf"], m=[x.get(campo) or "—", y.get(campo) or "—"], s=rotulo, f=fontes_))
        if len(saida) - antes_n > LIMITE_ELEICAO:
            n = len(saida) - antes_n
            del saida[antes_n:]
            saida.append(evento("BR" if uf == "BR" else f"UF:{uf}", "eleicao", f"Eleitos de {ano}: {n} registros novos ou alterados", uf=None if uf == "BR" else uf,
                                s="Carga em lote; a lista completa está nos dados abertos do TSE", f=fontes_))
    return saida


COLETORES = (camara, votacoes_camara, senado, votacoes_senado, executivo, estados, capitais, eleitos)


# ---------------------------------------------------------------- montagem do dia

ORDEM_LOCAL = lambda c: (c != "BR", c.startswith("MUN"), c)


def dia(data: str, antes: str, depois: str) -> dict:
    ctx = Contexto(depois)
    eventos = []
    for coletor in COLETORES:
        eventos += coletor(ctx, antes, depois)
    locais = sorted({e["l"] for e in eventos}, key=ORDEM_LOCAL)
    contagem = {c: dict(Counter(e["k"] for e in eventos if e["l"] == c)) for c in locais}
    return {"data": data, "antes": r.git("rev-parse", antes).strip(), "depois": r.git("rev-parse", depois).strip(),
            "locais": {c: ctx.nome_local(c) for c in locais}, "contagem": contagem, "eventos": eventos}


def resumo_indice(d: dict) -> dict:
    return {"d": d["data"], "n": len(d["eventos"]), "l": {c: sum(v.values()) for c, v in d["contagem"].items()}}


def gravar(d: dict, pasta: Path) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / f"{d['data']}.json").write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    caminho = pasta / "indice.json"
    try:
        indice = {x["d"]: x for x in json.loads(caminho.read_text(encoding="utf-8"))}
    except (OSError, ValueError):
        indice = {}
    indice[d["data"]] = resumo_indice(d)
    caminho.write_text(json.dumps(sorted(indice.values(), key=lambda x: x["d"], reverse=True), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def espelhar(origem: Path, destino: Path) -> None:
    """Copia o histórico do git para a pasta que o site publica."""
    if not origem.is_dir():
        return
    shutil.rmtree(destino, ignore_errors=True)
    shutil.copytree(origem, destino)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("antes", nargs="?")
    p.add_argument("depois", nargs="?")
    p.add_argument("--dias", type=int, default=1)
    p.add_argument("--saida", default=str(PASTA))
    a = p.parse_args()
    saida = Path(a.saida)
    if a.antes:
        lista = [(r.git("log", "-1", "--format=%cs", a.depois or "HEAD").strip(), a.antes, a.depois or "HEAD")]
    else:
        lista = dias_git(a.dias)
    for data, antes, depois in lista:
        d = dia(data, antes, depois)
        gravar(d, saida)
        print(f"Histórico de {data}: {len(d['eventos'])} eventos em {len(d['locais'])} locais")
    if not lista:
        print("Nenhum dia com commit de dados e commit anterior disponível; nada a registrar (falta git fetch --deepen?).")
    espelhar(saida, SITE_PASTA)


if __name__ == "__main__":
    main()
