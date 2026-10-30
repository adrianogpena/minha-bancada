"""
Histórico diário: tudo o que mudou nos dados em cada dia, com fonte, separado por local e, quando dá, por político.

A execução diária faz um commit "Dados atualizados em AAAA-MM-DD". Este script compara os dados antes e depois do dia
(como o resumo por e-mail e os feeds RSS) e grava dados/historico/AAAA-MM-DD.json, que fica no git: o histórico só cresce.
Depois espelha tudo em site/dados/historico/ (com indice.json), que a página historico.html lê.

O dia é o da descoberta: o de 27/10 pode trazer um ato de 26/10 encontrado só nessa coleta, com a data real em dataDoAto. Só entra o que
tem data do ato até JANELA_ATO_DIAS (3) dias antes da coleta, ou nenhuma data; o resto continua no site, fora do histórico. Os arquivos
dos dias são a memória: cada evento guarda a data do ato como a fonte a deu na descoberta, e uma mudança posterior vira evento novo.

Cada evento do dia:
    local         "BR", "UF:SP" ou "MUN:SP" (capital)                 uf          estado de quem aparece (filtro por estado)
    categoria     nova, situacao, votacao, eleicao, ministro, ministerio       titulo      título curto (ex.: "PL 123/2026")
    politicos     [{codigo: código do "Fique informado" ou null, nome, pagina: página no site ou null}]
    texto         ementa, despacho                                    mudanca     [antes, depois] de uma mudança
    resumo        placar, resultado                                   dataDoAto   data do ato (AAAA-MM-DD); dataDoAtoAproximada: é só a de apresentação
    fontes        [[rótulo, URL], ...]
    relevancia    3 marco (votação, projeto aprovado/sancionado/vetado, eleito), 2 projeto de verdade, 1 o resto (requerimento, parecer, carga antiga)
    quantidade    só no evento "lote": quantos registros de baixa relevância ele resume (acima de LIMITE_LOTE por local)
    titulos       só no evento "lote": os títulos resumidos (ex.: "REQ 12/2026"), em ordem
O dia também traz "cobertura": para cada local (todos os estados, com ou sem fonte), o nome, quantos itens saíram (itens) e o status:
novidade, irrelevante (dados mudaram sem virar item; "mudancas" lista o quê; "foraDaJanela" conta os itens barrados pela janela), parado (ultimaMudanca quando conhecida), falha (coleta não gravou nada
no dia; ultimaColeta) ou sem_cobertura. O campo coletadoEm, que muda todo dia, não conta como mudança.
O dia do histórico é o dia (Brasília) em que a coleta rodou; "coletaEm" e "coletaAnterior" (ISO com fuso) dizem entre que execuções saíram as novidades.
Os códigos de local e de político são os mesmos do feeds.py.

Uso:
    python scripts/historico.py [ANTES [DEPOIS]] [--dias N] [--saida PASTA] [--so-espelhar]
    (--so-espelhar só copia dados/historico para site/dados/historico, sem git nem dia novo: serve ao republicar.yml)
    (sem argumentos: o último dia com commit de dados; --dias N refaz os N últimos dias, para reconstruir o passado)
"""

import argparse
import contextlib
import json
import os
import re
import shutil
import subprocess
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

import feeds
import fuso
import identidades
import ministerios
import nomes_legados
import cadastro_proposicoes
import resumo_email as r

PASTA = r.RAIZ / "dados" / "historico"
SITE_PASTA = r.RAIZ / "site" / "dados" / "historico"
SITE_DADOS = r.RAIZ / "site" / "dados"
CAMARA_API = "https://dadosabertos.camara.leg.br/api/v2"
SENADO_MATERIA = "https://www25.senado.leg.br/web/atividade/materias/-/materia/"
TSE_DADOS = "https://dadosabertos.tse.jus.br"
SENADO_DADOS = "https://legis.senado.leg.br/dadosabertos"
PLANALTO_MINISTROS = "https://www.gov.br/planalto/pt-br/conheca-a-presidencia/ministros-e-ministras"
TSE_CDN = "https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_{ano}.zip"
# a situação só vira evento para projetos de verdade; requerimentos, emendas e pareceres entram só quando são apresentados
PROJETOS = {"PL", "PLP", "PEC", "PDL", "MPV", "PRC", "PLN", "PLV", "PFC", "PLC", "PLS", "PRS", "PDS"}
LIMITE_TEXTO = 1200
# "projeto de verdade": sigla acima ou, nas Assembleias e prefeituras, o nome do tipo por extenso
DESCRICAO_PROJETO = ("projeto de", "proposta de emenda", "medida provisória")
MARCO_SITUACAO = re.compile(r"aprovad|sancionad|vetad|promulgad|arquivad|rejeitad|retirad|transformad|prejudicad", re.I)
JANELA_ATO_DIAS = r.JANELA_ATO_DIAS   # só entra no histórico o que tem data do ato até esse tanto de dias antes da coleta (ou nenhuma data)
LIMITE_LOTE = 40          # por local: acima disso, os eventos de baixa relevância viram um evento só
PREFIXOS_BR = ("dados/proposicoes", "dados/proposicoes_cadastro", "dados/proposicoes_detalhe.json", "dados/votacoes", "dados/senado_materias.json",
               "dados/senado_votacoes", "dados/executivo.json", "dados/ministros")
LIMITE_ELEICAO = 200   # por arquivo do TSE; acima disso é carga em lote (eleição nova, recoleta), resumida em um evento só


# ---------------------------------------------------------------- leitura do git

def ler_lote(rev: str, caminhos: list[str]) -> dict:
    """{caminho: JSON} dos arquivos que existem em `rev`, com um único processo git."""
    if not caminhos:
        return {}
    p = subprocess.run([r.GIT, "cat-file", "--batch"], cwd=r.RAIZ, check=True, capture_output=True,
                       input="".join(f"{rev}:{c}\n" for c in caminhos).encode())
    saida, buf, pos = {}, p.stdout, 0
    for c in caminhos:
        fim = buf.index(b"\n", pos)
        cab = buf[pos:fim].split()
        pos = fim + 1
        if cab[-1] == b"missing":
            continue
        n = int(cab[2])
        with contextlib.suppress(ValueError):
            saida[c] = nomes_legados.atualizar(c, json.loads(buf[pos:pos + n]))
        pos += n + 1
    return saida


def listar(rev: str, prefixo: str) -> list[str]:
    try:
        return r.git("ls-tree", "-r", "--name-only", rev, "--", prefixo).split()
    except subprocess.CalledProcessError:
        return []


def dia_da_coleta(timestamp: int) -> str:
    """Dia (AAAA-MM-DD, Brasília) em que a coleta rodou: é o dia do histórico, e as novidades vão da coleta anterior a ela."""
    return datetime.fromtimestamp(timestamp, fuso.BRASILIA).date().isoformat()


def dia_do_commit(rev: str, *caminhos: str) -> str | None:
    ts = r.git("log", "-1", "--format=%ct", rev, *(["--", *caminhos] if caminhos else [])).strip()
    return dia_da_coleta(int(ts)) if ts else None


def momento_do_commit(rev: str) -> str | None:
    """Instante (ISO, Brasília) do último commit de dados alcançável a partir de `rev`; None se não houver."""
    ts = r.git("log", "-1", "--grep=^Dados atualizados em", "--format=%ct", rev).strip()
    return datetime.fromtimestamp(int(ts), fuso.BRASILIA).isoformat(timespec="seconds") if ts else None


def coleta_anterior(data: str, antes: str, pasta: Path) -> str | None:
    """Instante da coleta anterior: o `coletaEm` do dia gravado logo antes, ou o commit de dados anterior a `antes`."""
    for arq in sorted(pasta.glob("????-??-??.json"), reverse=True):
        if arq.stem < data:
            with contextlib.suppress(OSError, ValueError):
                if (x := json.loads(arq.read_text(encoding="utf-8")).get("coletaEm")):
                    return x
            break
    return momento_do_commit(antes)


def dias_git(n: int | None) -> list[tuple[str, str, str]]:
    """[(data, antes, depois)] dos n últimos dias com commit de dados, do mais novo ao mais antigo.
    Vários commits no mesmo dia viram um dia só: do pai do primeiro ao último."""
    por_dia = defaultdict(list)
    for linha in r.git("log", "--grep=^Dados atualizados em", "--format=%H %ct").splitlines():
        commit, ts = linha.split()
        data = dia_da_coleta(int(ts))
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
        self.lista_senadores = []   # dados/senado.json, para ligar o texto de autoria (identidades.ligar_autoria_senado)
        for arq in sorted((SITE_DADOS / "indice").glob("*.json")) if (SITE_DADOS / "indice").is_dir() else []:
            if not arq.stem.isalpha():
                continue
            for x in json.loads(arq.read_text(encoding="utf-8")):
                if x.get("codigoFeed"):
                    self.codigos.setdefault(x["codigoFeed"], (x["nome"], x.get("pagina")))
        with contextlib.suppress(OSError, ValueError, KeyError):
            self.capitais = json.loads((SITE_DADOS / "cobertura.json").read_text(encoding="utf-8"))["capitais"]
        try:
            for d in json.loads((SITE_DADOS / "deputados.json").read_text(encoding="utf-8")):
                self.deputados[int(d["id"])] = (d["nome"], d["uf"])
        except (OSError, ValueError, KeyError):
            pass
        try:
            self.lista_senadores = json.loads((r.RAIZ / "dados" / "senado.json").read_text(encoding="utf-8"))
            for s in self.lista_senadores:
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
        return {"codigo": codigo, "nome": nome, **({"pagina": pagina} if pagina else {})}

    def deputado(self, did: int) -> dict:
        nome, uf = self.deputados.get(did, (None, None))
        if not nome:
            ficha = r.RAIZ / "dados" / "deputados" / f"{did}.json"
            try:
                f = json.loads(ficha.read_text(encoding="utf-8"))
                nome, uf = f["nome"], f.get("uf")
            except (OSError, ValueError, KeyError):
                pass
        return {"codigo": f"dep:{did}", "nome": nome or f"Deputado(a) {did}", "pagina": f"deputado.html?id={did}", "uf": uf}

    def senadores_por_nome(self, autoria: str) -> list:
        """[(id, nome)] dos senadores citados no texto de autoria de um requerimento do Senado."""
        achados = identidades.ligar_autoria_senado([autoria], self.lista_senadores).get(autoria, [])
        return [(a[0], self.senadores.get(a[0])) for a in achados]

    def nome_local(self, codigo: str) -> str:
        if codigo == "BR":
            return "Federal: Câmara, Senado e Presidência"
        tipo, uf = codigo.split(":")
        if tipo == "UF":
            return f"Estado: {feeds.UFS.get(uf, uf)}"
        return f"Capital: {self.capitais.get(uf, uf)} ({uf})"


def cortar(texto, n: int = LIMITE_TEXTO) -> str:
    texto = " ".join(str(texto or "").split())
    return texto if len(texto) <= n else texto[: n - 1] + "…"


def evento(local: str, categoria: str, titulo: str, *, uf=None, politicos=None, texto=None, mudanca=None, resumo=None,
           data_do_ato=None, aproximada=False, fontes=None, relevancia=None, quantidade=None, titulos=None) -> dict:
    e = {"local": local, "categoria": categoria, "titulo": titulo, "uf": uf, "politicos": politicos or None, "texto": cortar(texto) or None,
         "mudanca": mudanca, "resumo": resumo, "dataDoAto": data_do_ato, "dataDoAtoAproximada": aproximada or None,
         "fontes": [list(a) for a in (fontes or []) if a and a[1]], "relevancia": relevancia, "quantidade": quantidade, "titulos": titulos}
    return {k: v for k, v in e.items() if v not in (None, [], "")}


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
    novas = defaultdict(list)    # id -> deputados que passaram a constar como autores
    for f in arquivos_:
        ids = set(cadastro_proposicoes.ids_de(a.get(f)))
        for pid in cadastro_proposicoes.ids_de(b.get(f)):
            if pid not in ids:
                novas[pid].append(int(Path(f).stem))
    det_a = ler_lote(antes, ["dados/proposicoes_detalhe.json"]).get("dados/proposicoes_detalhe.json") or {}
    det_b = ler_lote(depois, ["dados/proposicoes_detalhe.json"]).get("dados/proposicoes_detalhe.json") or {}
    saida = []

    def autores(deps):
        ps = [ctx.deputado(d) for d in sorted(deps)]
        return ps, next((p["uf"] for p in ps if p.get("uf")), None)

    meta_depois = r.objetos_em(depois, b) if novas else {}
    for pid, deps in novas.items():
        if pid not in meta_depois:
            continue
        i = {**meta_depois[pid], "idsDeputados": deps}
        ps, uf = autores(i["idsDeputados"])
        det = det_b.get(str(i["id"])) or {}
        saida.append(evento("BR", "nova", f"{i['siglaTipo']} {i['numero']}/{i['ano']}", uf=uf, politicos=ps, texto=i.get("ementa"),
                            data_do_ato=det.get("dataApresentacao"), fontes=fontes_camara(i["id"], det.get("inteiroTeor"))))
    mudancas = [pid for pid, y in det_b.items() if pid in det_a and (mudou(det_a[pid].get("situacao"), y.get("situacao")) or mudou(det_a[pid].get("tramitacao"), y.get("tramitacao")))]
    if mudancas:
        todos = ler_lote(depois, listar(depois, "dados/proposicoes"))
        meta = {str(pid): {**i, "idsDeputados": []} for pid, i in r.objetos_em(depois, todos).items()}
        for f, d in todos.items():
            for pid in cadastro_proposicoes.ids_de(d):
                if str(pid) in meta:
                    meta[str(pid)]["idsDeputados"].append(int(Path(f).stem))
        for pid in mudancas:
            i, y, x = meta.get(pid), det_b[pid], det_a[pid]
            if not i or i["siglaTipo"] not in PROJETOS:
                continue
            ps, uf = autores(i["idsDeputados"])
            sit = mudou(x.get("situacao"), y.get("situacao"))
            antes_, depois_ = (x.get("situacao"), y.get("situacao")) if sit else (x.get("tramitacao"), y.get("tramitacao"))
            saida.append(evento("BR", "situacao", f"{i['siglaTipo']} {i['numero']}/{i['ano']}", uf=uf, politicos=ps, texto=y.get("despacho") or i.get("ementa"),
                                mudanca=[antes_ or "—", depois_ or "—"], resumo=None if sit else "Nova tramitação", data_do_ato=y.get("dataSituacao"),
                                fontes=fontes_camara(pid, y.get("inteiroTeor"))))
    return saida


def _pasta_do_pedido(ementa) -> str | None:
    achadas = ministerios.pastas_do_texto(ementa)
    return ministerios.PASTAS[achadas[0]][0] if achadas else None


def _politico_senador(ctx: Contexto, sid: str, nome: str | None) -> dict:
    return {"codigo": None, "nome": nome or ctx.senadores.get(sid) or f"Senador(a) {sid}", "pagina": f"politico.html?f=senado&i={sid}"}


def ministros_planalto(antes: str, depois: str) -> list:
    """Troca de ministro: quem entrou ou saiu da lista do Planalto, por cargo. O Planalto não dá data: vale o dia da coleta."""
    a = ler_lote(antes, ["dados/ministros/planalto.json"]).get("dados/ministros/planalto.json")
    b = ler_lote(depois, ["dados/ministros/planalto.json"]).get("dados/ministros/planalto.json")
    if not a or not b:
        return []
    fontes_ = [("Ministros e Ministras (Planalto)", PLANALTO_MINISTROS)]
    por_cargo = lambda d: defaultdict(set, {c: {x["nome"] for x in d["atuais"] if x["cargo"] == c} for c in {x["cargo"] for x in d["atuais"]}})  # noqa: E731
    ant, atual = por_cargo(a), por_cargo(b)
    saida = []
    for cargo in sorted(set(ant) | set(atual)):
        saiu, entrou = sorted(ant[cargo] - atual[cargo]), sorted(atual[cargo] - ant[cargo])
        if not saiu and not entrou:
            continue
        saida.append(evento("BR", "ministro", cargo, mudanca=[", ".join(saiu) or "—", ", ".join(entrou) or "—"],
                            resumo="Troca de ministro" if saiu and entrou else "Novo ministro" if entrou else "Cargo sem ministro na lista",
                            fontes=fontes_, relevancia=3))
    return saida


def ministros_camara(ctx: Contexto, antes: str, depois: str, hoje: str, ontem: str) -> list:
    """Requerimentos a ministros na Câmara: novos, resposta recebida, prazo que acabou de vencer sem resposta e convocação ou convite aprovado."""
    arquivos_ = [f for f in r.arquivos(antes, depois, "dados/ministros") if re.fullmatch(r"dados/ministros/camara_\d{4}\.json", f)]
    a, b = ler_lote(antes, arquivos_), ler_lote(depois, arquivos_)
    saida = []
    for f in arquivos_:
        ant, atual = (a.get(f) or {}).get("itens", {}), (b.get(f) or {}).get("itens", {})
        for pid, y in atual.items():
            x = ant.get(pid)
            titulo, autores = f"{y['tipo']} {y['numero']}/{y['ano']}", [ctx.deputado(int(i)) for i, _ in y.get("autores", [])]
            uf = next((p["uf"] for p in autores if p.get("uf")), None)
            pasta = _pasta_do_pedido(y["ementa"])
            comum_ = dict(uf=uf, politicos=autores, texto=y["ementa"], fontes=fontes_camara(pid, y.get("inteiroTeor")))
            if x is None:
                saida.append(evento("BR", "ministerio", titulo, **comum_, resumo=f"Pedido ao ministério: {pasta}" if pasta else "Pedido a ministro",
                                    data_do_ato=y.get("dataApresentacao"), relevancia=1))
                continue
            if y["tipo"] == "RIC":
                if y.get("resposta") and not x.get("resposta"):
                    no_prazo = not y.get("prazoFim") or y["resposta"] <= y["prazoFim"]
                    saida.append(evento("BR", "ministerio", titulo, **comum_, mudanca=["Sem resposta", "Respondido" + (" no prazo" if no_prazo else " fora do prazo")],
                                        resumo=f"Resposta recebida ({pasta})" if pasta else "Resposta recebida", data_do_ato=y["resposta"], relevancia=2))
                elif not y.get("resposta") and y.get("prazoFim") and ontem <= y["prazoFim"] < hoje:
                    saida.append(evento("BR", "ministerio", titulo, **comum_, mudanca=["Aguardando resposta", "Prazo vencido sem resposta"],
                                        resumo=f"Prazo até {y['prazoFim']}" + (f", {pasta}" if pasta else ""), data_do_ato=y["prazoFim"], relevancia=2))
            elif mudou(x.get("situacao"), y.get("situacao")) and re.search(r"aprovad", y.get("situacao") or "", re.I):
                saida.append(evento("BR", "ministerio", titulo, **comum_, mudanca=[x.get("situacao") or "—", y.get("situacao")],
                                    resumo="Convocação ou convite a ministro aprovado", data_do_ato=y.get("dataStatus"), relevancia=3))
    return saida


def ministros_senado(ctx: Contexto, antes: str, depois: str) -> list:
    """Requerimentos do Senado a ministros: novos e convocação ou convite aprovado."""
    arquivos_ = [f for f in r.arquivos(antes, depois, "dados/ministros") if re.fullmatch(r"dados/ministros/senado_\d{4}\.json", f)]
    a, b = ler_lote(antes, arquivos_), ler_lote(depois, arquivos_)
    saida = []
    for f in arquivos_:
        ant, atual = (a.get(f) or {}).get("itens", {}), (b.get(f) or {}).get("itens", {})
        for pid, y in atual.items():
            x = ant.get(pid)
            texto_autoria = y.get("autoria") or ""
            autores = [_politico_senador(ctx, sid, nome) for sid, nome in ctx.senadores_por_nome(texto_autoria)]
            comum_ = dict(politicos=autores, texto=y["ementa"], fontes=[("Documento (Senado)", y.get("documento"))])
            pasta = _pasta_do_pedido(y["ementa"])
            if x is None:
                saida.append(evento("BR", "ministerio", y["identificacao"], **comum_, resumo=f"Pedido ao ministério: {pasta}" if pasta else "Pedido a ministro",
                                    data_do_ato=y.get("dataApresentacao"), relevancia=1))
            elif y.get("tipoConteudo") != "Informações" and mudou(x.get("deliberacao"), y.get("deliberacao")) and re.search(r"aprovad", y.get("deliberacao") or "", re.I):
                saida.append(evento("BR", "ministerio", y["identificacao"], **comum_, mudanca=[x.get("deliberacao") or "—", y["deliberacao"]],
                                    resumo="Convocação de ministro aprovada", data_do_ato=y.get("dataDeliberacao"), relevancia=3))
    return saida


def ministros_licencas(ctx: Contexto, antes: str, depois: str) -> list:
    """Parlamentar que se licenciou para ser ministro ou voltou ao mandato (novos registros no histórico da Câmara ou afastamentos do Senado)."""
    a = ler_lote(antes, ["dados/ministros/licencas.json"]).get("dados/ministros/licencas.json")
    b = ler_lote(depois, ["dados/ministros/licencas.json"]).get("dados/ministros/licencas.json")
    if not a or not b:
        return []
    saida = []
    for did, y in b.get("camara", {}).items():
        antigos = {(h["data"], h.get("descricao")) for h in a.get("camara", {}).get(did, {}).get("historico", [])}
        for h in y["historico"]:
            if (h["data"], h.get("descricao")) in antigos or h.get("situacao") not in ("Licença", "Exercício") or h["data"] < "2023-02-02":
                continue
            licenca = h["situacao"] == "Licença"
            saida.append(evento("BR", "ministro", y["nome"], politicos=[ctx.deputado(int(did))], resumo="Licenciou-se para ser ministro" if licenca else "Voltou ao mandato",
                                texto=h.get("descricao"), data_do_ato=h["data"], relevancia=3,
                                fontes=[("Histórico do deputado (API da Câmara)", f"{CAMARA_API}/deputados/{did}/historico")]))
    for sid, y in b.get("senado", {}).items():
        antigos = {(x.get("inicio"), x.get("cargo")) for x in a.get("senado", {}).get(sid, {}).get("afastamentos", [])}
        for x in y["afastamentos"]:
            if (x.get("inicio"), x.get("cargo")) in antigos or "inistro" not in (x.get("cargo") or ""):
                continue
            saida.append(evento("BR", "ministro", y["nome"], politicos=[_politico_senador(ctx, sid, y["nome"])], resumo="Afastou-se do mandato para ser ministro",
                                texto=x.get("cargo"), data_do_ato=x.get("inicio"), relevancia=3,
                                fontes=[("Senadores afastados (Dados Abertos do Senado)", f"{SENADO_DADOS}/senador/lista/afastados.json")]))
    return saida


def ministros(ctx: Contexto, antes: str, depois: str) -> list:
    """Ministros de Estado (dados/ministros/, scripts/coletar_ministros.py): troca na lista do Planalto, requerimentos e seu andamento, licenças."""
    if not listar(antes, "dados/ministros"):
        return []   # primeira coleta: tudo seria "novo"
    hoje, ontem = dia_do_commit(depois) or "", dia_do_commit(antes) or ""
    return (ministros_planalto(antes, depois) + ministros_camara(ctx, antes, depois, hoje, ontem) + ministros_senado(ctx, antes, depois)
            + ministros_licencas(ctx, antes, depois))


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
            saida.append(evento("BR", "votacao", v.get("proposicao") or "Votação no Plenário da Câmara", texto=v.get("ementa") or v.get("descricao"),
                                resumo=f"{res}{', ' + placar if placar else ''}", data_do_ato=v.get("data"),
                                fontes=[("Votação no site", f"votacao.html?id={vid}"), ("API da Câmara", f"{CAMARA_API}/votacoes/{vid}"),
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
        if mid in a and (not a[mid].get("situacao") or not mudou(a[mid].get("situacao"), m.get("situacao"))):
            continue   # sem situação anterior é a coleta preenchendo o campo, não uma mudança
        sid, i = autoria.get(mid, (None, None))
        nome = ctx.senadores.get(sid)
        ps = [{"codigo": None, "nome": nome, "pagina": f"politico.html?f=senado&i={sid}"}] if nome else None
        titulo = f"{i['tipo']} {i['numero']}/{i['ano']}" if i else f"Matéria {mid} do Senado"
        fontes_ = [("Matéria no Senado", SENADO_MATERIA + mid), ("Dados abertos do Senado", "https://legis.senado.leg.br/dadosabertos/processo/" + str(m["processo"]) if m.get("processo") else None)]
        if mid in a:
            saida.append(evento("BR", "situacao", titulo, politicos=ps, texto=i and i["ementa"], mudanca=[a[mid].get("situacao") or "—", m.get("situacao") or "—"], data_do_ato=m.get("dataSituacao"), fontes=fontes_))
        else:
            saida.append(evento("BR", "nova", titulo, politicos=ps, texto=i and i["ementa"], resumo=m.get("situacao"), data_do_ato=m.get("dataApresentacao") or m.get("dataSituacao"), fontes=fontes_))
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
            saida.append(evento("BR", "votacao", f"{v['proposicao']} (Senado)" if v.get("proposicao") else "Votação no Plenário do Senado", texto=v.get("ementa") or v.get("descricao"),
                                resumo=f"{res}{', ' + placar if placar else ''}", data_do_ato=v.get("data"),
                                fontes=[("Votação no site", f"votacao.html?casa=senado&id={vid}"),
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
        if x and not mudou(x.get("situacao"), i.get("situacao")):
            continue
        saida.append(evento("BR", "situacao" if x else "nova", f"{i['tipo']} {i['numero']}/{i['ano']}", politicos=pres, texto=i.get("ementa"),
                            mudanca=[x.get("situacao") or "—", i.get("situacao") or "—"] if x else None, resumo=None if x else i.get("situacao"), data_do_ato=i.get("dataSituacao") or i.get("dataApresentacao"),
                            fontes=fontes_camara(i["id"], i.get("inteiroTeor"))))
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
            if not novo and not mudou(ant[mid].get("situacao"), m.get("situacao")):
                continue
            host = host_de(b.get(f))
            titulo = f"{m.get('tipoDescricao') or m.get('tipo', '')} {m.get('numero', '')}/{m.get('ano', '')}".strip()
            saida.append(evento(local, "nova" if novo else "situacao", titulo, uf=uf, politicos=politicos(m), texto=m.get("ementa"),
                                mudanca=None if novo else [ant[mid].get("situacao") or "—", m.get("situacao") or "—"], resumo=m.get("situacao") if novo else None, data_do_ato=m.get("dataApresentacao"), aproximada=not novo,
                                fontes=[("Matéria no sistema legislativo", f"https://{host}/materia/{mid}" if host and str(mid).isdigit() else None), ("Texto", m.get("linkTexto"))]))
    return saida


def estados(ctx: Contexto, antes: str, depois: str) -> list:
    saida = []
    ufs = sorted({f.split("/")[2] for f in r.arquivos(antes, depois, "dados/estaduais")})
    for uf in ufs:
        if not listar(antes, f"dados/estaduais/{uf}/deputados.json"):
            continue
        ass = ctx.assembleia(uf)
        saida += sapl(ctx, antes, depois, uf, "estaduais", f"UF:{uf}",
                      lambda m, uf=uf, ass=ass: [ctx.politico(f"est:{uf}:{d}", ass["nomes"].get(d) or f"Deputado(a) estadual {d}") for d in m.get("idsDeputados", [])] or None,
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
    for d in lotes.values():
        materias.update(d.get("materias", d) if isinstance(d, dict) else {})
    saida = []
    for v in novas.values():
        m = materias.get(str(v.get("idMateria"))) or {}
        titulo = f"{m.get('tipo', '')} {m.get('numero', '')}/{m.get('ano', '')}".strip() if m else f"Matéria {v.get('idMateria')}"
        placar = f"{v.get('sim', 0)} sim, {v.get('nao', 0)} não, {v.get('abstencoes', 0)} abstenções"
        saida.append(evento(f"UF:{uf}", "votacao", f"{titulo} (votação nominal)", uf=uf, texto=m.get("ementa"), resumo=f"{v.get('resultado') or 'Sem resultado informado'}, {placar}", data_do_ato=v.get("data"),
                            fontes=[("Matéria no sistema legislativo", f"https://{ass['host']}/materia/{v['idMateria']}" if ass.get("host") and v.get("idMateria") else None)]))
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
        ant = {c["sequencial"]: c for c in a[f]}
        atual = {c["sequencial"]: c for c in b.get(f, [])}
        fontes_ = [("Candidatos e eleitos (TSE, dados abertos)", TSE_DADOS), ("Arquivo usado", TSE_CDN.format(ano=ano))]
        antes_n = len(saida)
        for sq in sorted(set(ant) | set(atual)):
            x, y = ant.get(sq), atual.get(sq)
            c = y or x
            titulo = f"{c.get('urna') or c['nome']}, {c['cargo'].title()} ({c['partido']}), eleição de {ano}"
            local = "BR" if uf == "BR" else f"UF:{c['uf']}"
            if not x:
                saida.append(evento(local, "eleicao", titulo, uf=None if uf == "BR" else c["uf"], resumo=f"Passou a constar como {c.get('situacao')}", fontes=fontes_))
            elif not y:
                saida.append(evento(local, "eleicao", titulo, uf=None if uf == "BR" else c["uf"], resumo="Deixou de constar entre os eleitos", fontes=fontes_))
            else:
                for campo, rotulo in (("situacao", "Situação"), ("resultado", "Resultado"), ("partido", "Partido")):
                    if mudou(x.get(campo), y.get(campo)):
                        saida.append(evento(local, "eleicao", titulo, uf=None if uf == "BR" else c["uf"], mudanca=[x.get(campo) or "—", y.get(campo) or "—"], resumo=rotulo, fontes=fontes_))
        if len(saida) - antes_n > LIMITE_ELEICAO:
            n = len(saida) - antes_n
            del saida[antes_n:]
            saida.append(evento("BR" if uf == "BR" else f"UF:{uf}", "eleicao", f"Eleitos de {ano}: {n} registros novos ou alterados", uf=None if uf == "BR" else uf,
                                resumo="Carga em lote; a lista completa está nos dados abertos do TSE", fontes=fontes_, relevancia=2))
    return saida


# ---------------------------------------------------------------- relevância, lotes e cobertura

def projeto_de_verdade(titulo: str) -> bool:
    sigla = titulo.split(" ", 1)[0]
    return sigla in PROJETOS or titulo.lower().startswith(DESCRICAO_PROJETO)


def relevancia(e: dict, data: str) -> int:
    """3 marco, 2 projeto de verdade, 1 o resto. Só ordena e filtra na página: nada deixa de ser registrado (exceto o excesso de lote)."""
    if e.get("relevancia"):
        return e["relevancia"]
    if e["categoria"] in ("votacao", "eleicao"):
        return 3
    desconhecido = e["titulo"].startswith("Matéria ")   # matéria do Senado sem o tipo: na dúvida, não esconde
    if not (projeto_de_verdade(e["titulo"]) or desconhecido):
        return 1
    if e["categoria"] == "situacao":
        if e.get("resumo") == "Nova tramitação":   # só andou de lugar; a situação é a mesma
            return 1
        return 3 if MARCO_SITUACAO.search((e.get("mudanca") or ["", ""])[1]) else 2
    return 2


def tipo_do_titulo(titulo: str) -> str:
    m = re.match(r"(.+?)\s+\d+(?:/\d+)?\b", titulo)
    return m.group(1) if m else titulo


def agrupar_lotes(eventos: list) -> list:
    """Por local, o que passa de LIMITE_LOTE entre novidades de baixa relevância (requerimentos, pareceres e afins) vira um evento só,
    com a conta por tipo; o mesmo vale para as mudanças de situação sem data do ato (data aproximada) que não são marco, caso a fonte
    reescreva situações antigas de uma vez. Projetos de verdade novos e marcos nunca entram no lote."""
    saida = eventos
    for chave, titulo, resumo in (
            (lambda e: e["relevancia"] == 1 and e["categoria"] in ("nova", "situacao", "ministerio"), "{n} registros de baixa relevância (requerimentos, pareceres e afins)",
             "Novos ou com nova situação: {conta}. Títulos na lista abaixo."),
            (lambda e: e["relevancia"] == 2 and e.get("dataDoAtoAproximada"), "{n} mudanças de situação sem data do ato conhecida",
             "Com nova situação, de uma vez: {conta}. Títulos na lista abaixo.")):
        grupos = defaultdict(list)
        for e in saida:
            if chave(e):
                grupos[e["local"]].append(e)
        for local, lista in grupos.items():
            if len(lista) <= LIMITE_LOTE:
                continue
            ids = {id(e) for e in lista}
            saida = [e for e in saida if id(e) not in ids]
            tipos = Counter(tipo_do_titulo(e["titulo"]) for e in lista).most_common(8)
            resto = len(lista) - sum(n for _, n in tipos)
            conta = ", ".join(f"{n} {t}" for t, n in tipos) + (f" e mais {resto} de outros tipos" if resto else "")
            ufs = {e.get("uf") for e in lista if e.get("uf")}
            saida.append(evento(local, "lote", titulo.format(n=len(lista)), uf=ufs.pop() if len(ufs) == 1 else None,
                                resumo=resumo.format(conta=conta), relevancia=1, quantidade=len(lista), titulos=sorted(e["titulo"] for e in lista)))
    return saida


ADMINISTRATIVOS = ("coletadoEm", "vistas", "completaEm")   # campos de controle da coleta: mudam todo dia sem trazer dado
ROTULOS_ARQUIVO = {"materias": "matérias", "materias_votadas": "matérias votadas", "governo": "projetos do governo", "votacoes": "votações",
                   "deputados": "deputados", "verbas": "verbas", "remuneracao": "remuneração", "presenca": "presença", "diarias": "diárias",
                   "emendas": "emendas", "proposicoes": "proposições", "ligacoes": "ligação de nomes a deputados",
                   "parcial": "leitura em andamento (parcial)", "presenca_sessoes": "presença em sessões",
                   "planalto": "lista de ministros", "licencas": "licenças de ministros"}


def rotulo_arquivo(caminho: str) -> str:
    nome = re.sub(r"(_\d{4})?\.json$", "", caminho.rsplit("/", 1)[-1])
    if nome.isdigit():
        nome = caminho.split("/")[-2]
    return ROTULOS_ARQUIVO.get(nome, nome.replace("_", " "))


def sem_controle(obj):
    return {k: v for k, v in obj.items() if k not in ADMINISTRATIVOS} if isinstance(obj, dict) else obj


def mudancas_reais(antes: str, depois: str, arquivos: list[str]) -> list[str]:
    """Rótulos dos arquivos cujo conteúdo mudou de verdade (ignora coletadoEm e afins), sem repetição, em ordem."""
    a, b = ler_lote(antes, arquivos), ler_lote(depois, arquivos)
    return sorted({rotulo_arquivo(f) for f in arquivos if sem_controle(a.get(f)) != sem_controle(b.get(f))})


def ultima_coleta(depois: str, prefixo: str) -> str | None:
    """Data (AAAA-MM-DD) mais recente de coletadoEm entre os arquivos sem ano e os do último ano do local."""
    arquivos = [f for f in listar(depois, prefixo) if f.endswith(".json")]
    anos = {m.group(1) for f in arquivos if (m := re.search(r"_(\d{4})\.json$", f))}
    recentes = [f for f in arquivos if not re.search(r"_\d{4}\.json$", f) or f.endswith(f"_{max(anos)}.json")]
    datas = [fuso.dia(x["coletadoEm"]) or str(x["coletadoEm"])[:10] for x in ler_lote(depois, recentes).values() if isinstance(x, dict) and x.get("coletadoEm")]
    return max(datas) if datas else None


def ultima_mudanca_registrada(data: str, local: str) -> str | None:
    """Último dia anterior a `data` em que o histórico já gravado marcou mudança real (novidade ou mudança sem relevância) no local."""
    for arq in sorted(PASTA.glob("????-??-??.json"), reverse=True):
        if arq.stem >= data:
            continue
        try:
            item = json.loads(arq.read_text(encoding="utf-8")).get("cobertura", {}).get(local)
        except (OSError, ValueError):
            return None
        if not item or "status" not in item:
            return None   # dia gravado antes dos status: a data de mudança não é confiável
        if item["status"] in ("novidade", "irrelevante"):
            return arq.stem
    return None


def ultima_mudanca_real(antes: str, prefixos: list[str], limite: int = 10) -> str | None:
    """Dia da última mudança real do local entre os `limite` commits de dados anteriores a `antes`, comparando um commit com o seguinte."""
    commits = r.git("log", f"-{limite + 1}", "--grep=^Dados atualizados em", "--format=%H", antes).split()
    for novo, velho in zip(commits, commits[1:]):
        arquivos = [f for p in prefixos for f in r.arquivos(velho, novo, p)]
        if arquivos and mudancas_reais(velho, novo, arquivos):
            return dia_do_commit(novo)
    return None


def cobertura(ctx: Contexto, antes: str, depois: str, contagem: dict, data: str | None = None, fora: dict | None = None) -> dict:
    """Todo local monitorado no dia, com ou sem novidade: {código: {nome, mudou, itens, status, mudancas, foraDaJanela, ultimaMudanca, ultimaColeta}}.
    foraDaJanela: quantos itens do local ficaram fora do histórico por terem data do ato anterior à janela (só no site).
    status: "novidade" (saiu item), "irrelevante" (os dados mudaram mas nada vira item; `mudancas` diz o que), "parado" (nenhum dado novo),
    "falha" (a coleta não gravou nada nesse dia; `ultimaColeta`) e "sem_cobertura" (estado ainda sem fonte coletada).
    Assim "nada aconteceu" se distingue de "o local não foi acompanhado" e uma coleta parada há dias aparece."""
    data = data or dia_do_commit(depois)
    prefixos = {"BR": list(PREFIXOS_BR)}
    for tipo, pasta in (("UF", "estaduais"), ("MUN", "municipais")):
        for uf in sorted({f.split("/")[2] for f in listar(depois, f"dados/{pasta}")}):
            if re.fullmatch(r"[A-Z]{2}", uf):
                prefixos[f"{tipo}:{uf}"] = [f"dados/{pasta}/{uf}"]
    saida = {}
    for local in sorted(prefixos, key=ordem_local):
        itens = sum(contagem.get(local, {}).values())
        alterados = [f for p in prefixos[local] for f in r.arquivos(antes, depois, p)]   # o TSE tem arquivos próprios, fora dos prefixos
        item = {"nome": ctx.nome_local(local), "itens": itens}
        if itens:
            item.update(mudou=True, status="novidade")
        else:
            mudancas = mudancas_reais(antes, depois, alterados)
            item["mudou"] = bool(mudancas)
            if mudancas:
                item.update(status="irrelevante", mudancas=mudancas)
            else:
                coleta = ultima_coleta(depois, prefixos[local][0]) if local != "BR" else None
                if coleta and coleta < data:   # `data` é o dia da coleta: uma última coleta anterior a ele é coleta que não rodou
                    item.update(status="falha", ultimaColeta=coleta)
                else:
                    item["status"] = "parado"
                item["ultimaMudanca"] = ultima_mudanca_registrada(data, local)
                if not item["ultimaMudanca"]:
                    with contextlib.suppress(subprocess.CalledProcessError):
                        item["ultimaMudanca"] = ultima_mudanca_real(antes, prefixos[local])
                if not item["ultimaMudanca"] and not alterados:
                    with contextlib.suppress(subprocess.CalledProcessError):
                        item["ultimaMudanca"] = dia_do_commit(depois, *prefixos[local])
        if fora and fora.get(local):
            item["foraDaJanela"] = fora[local]
        saida[local] = {k: v for k, v in item.items() if v is not None}
    for uf in sorted(feeds.UFS):
        if f"UF:{uf}" not in saida:
            saida[f"UF:{uf}"] = {"nome": ctx.nome_local(f"UF:{uf}"), "mudou": False, "itens": 0, "status": "sem_cobertura"}
    return dict(sorted(saida.items(), key=lambda kv: ordem_local(kv[0])))


COLETORES = (camara, votacoes_camara, senado, votacoes_senado, executivo, ministros, estados, capitais, eleitos)


# ---------------------------------------------------------------- montagem do dia

def ordem_local(c):
    return (c != "BR", c.startswith("MUN"), c)


def na_janela(e: dict, data: str) -> bool:
    """Novidade, mudança ou votação cuja data do ato é antiga (carga de backlog, publicação atrasada) fica só no site, fora do histórico.
    Data aproximada (mudança de situação de Assembleia ou capital, que mostra só a data de apresentação) não conta: entra no dia da descoberta."""
    return e.get("dataDoAtoAproximada") or r.na_janela(e.get("dataDoAto"), data)


def dia(data: str, antes: str, depois: str, coleta_em: str | None = None, coleta_ant: str | None = None) -> dict:
    ctx = Contexto(depois)
    eventos = []
    for coletor in COLETORES:
        eventos += coletor(ctx, antes, depois)
    fora = Counter()
    for e in eventos:
        if not na_janela(e, data):
            fora[e["local"]] += e.get("quantidade", 1)
    eventos = [e for e in eventos if na_janela(e, data)]
    for e in eventos:
        e["relevancia"] = relevancia(e, data)
    eventos = agrupar_lotes(eventos)
    eventos.sort(key=lambda e: (ordem_local(e["local"]), -e["relevancia"]))   # a ordem do arquivo já põe o que importa primeiro
    locais = sorted({e["local"] for e in eventos}, key=ordem_local)
    contagem = {c: {} for c in locais}
    for e in eventos:
        contagem[e["local"]][e["categoria"]] = contagem[e["local"]].get(e["categoria"], 0) + e.get("quantidade", 1)
    quando = {"coletaAnterior": coleta_ant, "coletaEm": coleta_em or momento_do_commit(depois)}
    return {"data": data, "antes": r.git("rev-parse", antes).strip(), "depois": r.git("rev-parse", depois).strip(),
            **{k: v for k, v in quando.items() if v},
            "locais": {c: ctx.nome_local(c) for c in locais}, "contagem": contagem, "cobertura": cobertura(ctx, antes, depois, contagem, data, fora),
            "eventos": eventos}


def resumo_indice(d: dict) -> dict:
    r_ = Counter()
    for e in d["eventos"]:
        r_[str(e["relevancia"])] += e.get("quantidade", 1)
    return {"data": d["data"], "total": sum(sum(v.values()) for v in d["contagem"].values()),
            "locais": {c: sum(v.values()) for c, v in d["contagem"].items()}, "relevancias": dict(r_)}


def gravar(d: dict, pasta: Path) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / f"{d['data']}.json").write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    caminho = pasta / "indice.json"
    try:
        indice = {x["data"]: x for x in json.loads(caminho.read_text(encoding="utf-8"))}
    except (OSError, ValueError):
        indice = {}
    indice[d["data"]] = resumo_indice(d)
    caminho.write_text(json.dumps(sorted(indice.values(), key=lambda x: x["data"], reverse=True), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


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
    p.add_argument("--so-espelhar", action="store_true")
    a = p.parse_args()
    saida = Path(a.saida)
    if a.so_espelhar:
        espelhar(saida, SITE_PASTA)
        return
    if a.antes:
        lista = [(dia_do_commit(a.depois or "HEAD"), a.antes, a.depois or "HEAD")]
    else:
        lista = dias_git(a.dias)
    inicio = os.environ.get("COLETA_INICIO")   # início da execução agendada (o workflow informa); sem ele vale a hora do commit de dados
    for i, (data, antes, depois) in enumerate(lista):
        d = dia(data, antes, depois, inicio if i == 0 else None, coleta_anterior(data, antes, saida))
        gravar(d, saida)
        print(f"Histórico de {data}: {len(d['eventos'])} eventos em {len(d['locais'])} locais")
    if not lista:
        print("Nenhum dia com commit de dados e commit anterior disponível; nada a registrar (falta git fetch --deepen?).")
    espelhar(saida, SITE_PASTA)


if __name__ == "__main__":
    main()
