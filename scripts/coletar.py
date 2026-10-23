"""
Coleta dados públicos da API de Dados Abertos da Câmara dos Deputados
e guarda um cache bruto em dados/ (essa pasta é salva no repositório,
assim o histórico de votações vai crescendo a cada execução).

Uso:
    python scripts/coletar.py                 # coleta completa
    python scripts/coletar.py --limite 10     # só 10 deputados (teste rápido)
    python scripts/coletar.py --dias 60       # janela inicial de votações

Documentação da API: https://dadosabertos.camara.leg.br/swagger/api.html
"""

import argparse
import datetime as dt
import csv
import io
import json
import os
import re
import sys
import unicodedata
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API = os.environ.get("CAMARA_API", "https://dadosabertos.camara.leg.br/api/v2")
RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "dados"
INICIO_LEGISLATURA = "2023-02-01"  # 57ª legislatura
LEGISLATURA = 57
ARQUIVOS_CAMARA = "https://dadosabertos.camara.leg.br/arquivos"
TRABALHADORES_SENADO = 2  # o Senado responde 503 quando apertado
TRABALHADORES = int(os.environ.get("CAMARA_TRABALHADORES", 10))  # requisições em paralelo; seja gentil com a API pública (429 e 5xx são repetidos com espera)


def sessao() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "Accept": "application/json",
        "User-Agent": "minha-bancada (projeto de transparencia; github.com)",
    })
    retry = Retry(total=5, backoff_factor=1.5,
                  status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=("GET",))
    s.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=TRABALHADORES * 2))
    s.mount("http://", HTTPAdapter(max_retries=retry, pool_maxsize=TRABALHADORES * 2))
    return s


S = sessao()


def get(caminho: str, **params) -> dict:
    url = caminho if caminho.startswith("http") else f"{API}{caminho}"
    r = S.get(url, params=params or None, timeout=60)
    if not r.ok:
        corpo = r.text[:200].replace("\n", " ")
        raise RuntimeError(f"HTTP {r.status_code} em {r.url}: {corpo}")
    return r.json()


AVISOS: list[str] = []


def avisar(msg: str) -> None:
    """Mostra o problema no log; no GitHub Actions os primeiros viram anotações
    visíveis no resumo da execução."""
    print(f"  ! {msg}", file=sys.stderr)
    AVISOS.append(msg)
    if os.environ.get("GITHUB_ACTIONS") and len(AVISOS) <= 8:
        print(f"::warning::{msg[:900]}")


def get_todos(caminho: str, **params) -> list:
    """Segue a paginação (links rel=next) e junta todos os itens."""
    params.setdefault("itens", 100)
    resp = get(caminho, **params)
    itens = list(resp.get("dados", []))
    while True:
        prox = next((l["href"] for l in resp.get("links", []) if l.get("rel") == "next"), None)
        if not prox:
            break
        resp = get(prox)
        itens.extend(resp.get("dados", []))
    return itens


def salvar(caminho: Path, obj) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(caminho)


def ler(caminho: Path, padrao):
    if caminho.exists():
        return json.loads(caminho.read_text(encoding="utf-8"))
    return padrao


# ---------------------------------------------------------------- deputados

def coletar_proposicoes(dep: dict) -> list:
    """A API aceita no máximo 3 meses por consulta. Guardamos o que já foi
    coletado em dados/proposicoes/ (salvo no git) e, nas execuções seguintes,
    buscamos só o período novo."""
    did = dep["id"]
    arquivo = DADOS / "proposicoes" / f"{did}.json"
    cache = ler(arquivo, {"ate": None, "itens": []})
    hoje = dt.date.today()
    inicio = (dt.date.fromisoformat(cache["ate"]) - dt.timedelta(days=10)) if cache["ate"] \
        else dt.date.fromisoformat(INICIO_LEGISLATURA)
    por_id = {p["id"]: p for p in cache["itens"]}
    completo = True
    atual = inicio
    while atual <= hoje:
        fim = min(atual + dt.timedelta(days=88), hoje)
        try:
            for p in get_todos("/proposicoes", idDeputadoAutor=did,
                               dataApresentacaoInicio=atual.isoformat(),
                               dataApresentacaoFim=fim.isoformat(),
                               ordem="DESC", ordenarPor="id"):
                por_id[p["id"]] = {"id": p["id"], "siglaTipo": p.get("siglaTipo"),
                                   "numero": p.get("numero"), "ano": p.get("ano"),
                                   "ementa": (p.get("ementa") or "").strip()}
        except Exception as e:
            avisar(f"proposições de {dep.get('nome')} de {atual} a {fim}: {e}")
            completo = False
        atual = fim + dt.timedelta(days=1)
    itens = sorted(por_id.values(), key=lambda p: p["id"], reverse=True)
    # só avança a data se tudo deu certo, para tentar de novo o que falhou
    salvar(arquivo, {"ate": hoje.isoformat() if completo else cache["ate"], "itens": itens})
    return itens


def coletar_cota_csv(ano: int) -> dict[int, list]:
    """Cota parlamentar do ano de todos os deputados num arquivo só (~4 MB zipado), com o CNPJ/CPF do fornecedor.
    Devolve {id do deputado: despesas, da mais recente para a mais antiga}; vazio se o arquivo não puder ser lido."""
    r = S.get(f"https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip", timeout=180)
    r.raise_for_status()
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    texto = zf.read(zf.namelist()[0]).decode("utf-8-sig")
    por_dep: dict[int, list] = {}
    for l in csv.DictReader(io.StringIO(texto), delimiter=";"):
        if not l.get("nuDeputadoId", "").isdigit() or l.get("numAno") != str(ano):
            continue
        por_dep.setdefault(int(l["nuDeputadoId"]), []).append({
            "mes": int(l["numMes"]) if l.get("numMes", "").isdigit() else None,
            "tipo": l.get("txtDescricao"), "valor": float(l["vlrLiquido"] or 0),
            "fornecedor": l.get("txtFornecedor"), "cnpj": re.sub(r"\D", "", l.get("txtCNPJCPF") or ""),
            "data": (l.get("datEmissao") or "")[:10] or None, "documento": l.get("urlDocumento") or None,
        })
    for lista in por_dep.values():
        lista.sort(key=lambda i: i["data"] or "", reverse=True)
    print(f"Cota {ano} (CSV): {sum(len(v) for v in por_dep.values())} despesas de {len(por_dep)} deputados")
    return por_dep


def coletar_deputado(dep: dict, ano: int, cota: dict[int, list] | None = None) -> dict:
    did = dep["id"]
    detalhe = get(f"/deputados/{did}").get("dados", {})

    proposicoes = coletar_proposicoes(dep)

    if cota is not None:
        itens_cota = cota.get(did, [])
    else:
        try:
            despesas = get_todos(f"/deputados/{did}/despesas", ano=ano,
                                 ordem="DESC", ordenarPor="dataDocumento")
        except Exception as e:
            avisar(f"despesas de {dep.get('nome')}: {e}")
            despesas = []
        itens_cota = [{"mes": d.get("mes"), "tipo": d.get("tipoDespesa"), "valor": d.get("valorLiquido") or 0,
                       "fornecedor": d.get("nomeFornecedor"), "cnpj": re.sub(r"\D", "", d.get("cnpjCpfFornecedor") or ""),
                       "data": d.get("dataDocumento"), "documento": d.get("urlDocumento")} for d in despesas]

    frentes = None
    try:
        frentes = [{"id": f["id"], "titulo": (f.get("titulo") or "").strip()}
                   for f in get(f"/deputados/{did}/frentes").get("dados", []) if f.get("idLegislatura") == LEGISLATURA]
    except Exception as e:  # a frente é complemento: sem ela o perfil só não mostra o bloco
        avisar(f"frentes de {dep.get('nome')}: {e}")

    status = detalhe.get("ultimoStatus", {}) or {}
    return {
        "id": did,
        "nome": status.get("nomeEleitoral") or dep.get("nome"),
        "nomeCivil": detalhe.get("nomeCivil"),
        "partido": status.get("siglaPartido") or dep.get("siglaPartido"),
        "uf": status.get("siglaUf") or dep.get("siglaUf"),
        "foto": status.get("urlFoto") or dep.get("urlFoto"),
        "email": status.get("email") or dep.get("email"),
        "situacao": status.get("situacao"),
        "condicaoEleitoral": status.get("condicaoEleitoral"),
        "gabinete": {k: v for k, v in (status.get("gabinete") or {}).items()
                     if k in ("predio", "sala", "andar", "telefone", "email") and v},
        "nascimento": detalhe.get("dataNascimento"),
        "municipioNascimento": detalhe.get("municipioNascimento"),
        "ufNascimento": detalhe.get("ufNascimento"),
        "escolaridade": detalhe.get("escolaridade"),
        "redesSociais": detalhe.get("redeSocial") or [],
        "proposicoes": [
            {"id": p["id"], "tipo": p.get("siglaTipo"), "numero": p.get("numero"),
             "ano": p.get("ano"), "ementa": (p.get("ementa") or "").strip()}
            for p in proposicoes
        ],
        "despesas": {"ano": ano, "itens": itens_cota},
        **({"frentes": frentes} if frentes is not None else {}),
        "coletadoEm": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
    }


def coletar_deputados(limite: int | None) -> list:
    lista = get_todos("/deputados", ordem="ASC", ordenarPor="nome")
    if limite:
        lista = lista[:limite]
    print(f"Deputados em exercício: {len(lista)}")
    ano = dt.date.today().year
    try:
        cota = coletar_cota_csv(ano) or None
    except Exception as e:  # sem o CSV, a cota vem da API, deputado a deputado
        avisar(f"cota pelo CSV anual: {e}")
        cota = None
    resumo, falhas = [], 0
    with ThreadPoolExecutor(TRABALHADORES) as ex:
        futuros = {ex.submit(coletar_deputado, d, ano, cota): d for d in lista}
        for i, f in enumerate(as_completed(futuros), 1):
            dep = futuros[f]
            try:
                dados = f.result()
                salvar(DADOS / "deputados" / f"{dep['id']}.json", dados)
                resumo.append(dep["id"])
            except Exception as e:  # um deputado com erro não derruba a coleta
                falhas += 1
                avisar(f"deputado {dep.get('nome')} ({dep['id']}): {e}")
            if i % 50 == 0:
                print(f"  {i}/{len(lista)}")
    salvar(DADOS / "deputados.json", sorted(resumo))
    print(f"Deputados salvos: {len(resumo)}, falhas: {falhas}")
    if lista and falhas > len(lista) * 0.2:
        raise SystemExit("Muitas falhas ao coletar deputados; abortando para não publicar dados incompletos.")
    return resumo

# ---------------------------------------------------------------- detalhes das proposições

# tipos que são projetos de verdade; requerimentos, emendas e pareceres ficam só na lista
TIPOS_PRINCIPAIS = {"PL", "PLP", "PEC", "PDL", "PRC", "PLN", "PFC", "PLV", "MPV", "PLS", "PDC", "PDS"}
ORCAMENTO_DETALHES = int(os.environ.get("DETALHES_POR_EXECUCAO", "4000"))
RENOVAR_APOS_DIAS = 7  # proposição ainda em tramitação é consultada de novo depois disso


def id_da_uri(uri: str | None) -> str | None:
    """Id da proposição no fim de uma URI da API (.../proposicoes/2270800), ou None."""
    m = re.search(r"/proposicoes/(\d+)/?$", uri or "")
    return m.group(1) if m else None


def coletar_detalhes_proposicoes() -> None:
    """Situação atual de cada projeto (aprovado, arquivado, em tramitação...).
    Guardado em dados/proposicoes_detalhe.json (vai para o git). Há muitos
    projetos, então cada execução consulta no máximo ORCAMENTO_DETALHES:
    primeiro os que nunca foram consultados, depois os mais desatualizados
    que ainda tramitam. Com os dias o cache se completa."""
    arquivo = DADOS / "proposicoes_detalhe.json"
    cache = ler(arquivo, {})
    todos = set()
    for arq in (DADOS / "proposicoes").glob("*.json"):
        for p in ler(arq, {"itens": []})["itens"]:
            if p.get("siglaTipo") in TIPOS_PRINCIPAIS:
                todos.add(str(p["id"]))
    hoje = dt.date.today()
    limite_velho = (hoje - dt.timedelta(days=RENOVAR_APOS_DIAS)).isoformat()
    novos = sorted(todos - cache.keys(), reverse=True)
    velhos = sorted((i for i in todos & cache.keys()
                     if not cache[i].get("finalizada") and cache[i].get("consultadoEm", "") < limite_velho),
                    key=lambda i: cache[i].get("consultadoEm", ""))
    fila = (novos + velhos)[:ORCAMENTO_DETALHES]
    print(f"Detalhes de proposições: {len(todos)} projetos, {len(novos)} novos, {len(velhos)} a renovar; consultando {len(fila)}")

    def buscar(pid: str) -> tuple[str, dict]:
        d = get(f"/proposicoes/{pid}").get("dados", {}) or {}
        st = d.get("statusProposicao") or d.get("ultimoStatus") or {}
        situacao = st.get("descricaoSituacao") or ""
        return pid, {
            "dataApresentacao": (d.get("dataApresentacao") or "")[:10] or None,
            "situacao": situacao or None,
            "tramitacao": st.get("descricaoTramitacao"),
            "despacho": (st.get("despacho") or "").strip() or None,
            "orgao": st.get("siglaOrgao"),
            "dataSituacao": (st.get("dataHora") or "")[:10] or None,
            "regime": st.get("regime"),
            "inteiroTeor": d.get("urlInteiroTeor"),
            "ementaDetalhada": (d.get("ementaDetalhada") or "").strip() or None,
            "palavrasChave": (d.get("keywords") or "").strip() or None,
            "apensadoA": id_da_uri(d.get("uriPropPrincipal")),
            "anterior": id_da_uri(d.get("uriPropAnterior")),
            "posterior": id_da_uri(d.get("uriPropPosterior")),
            "consultadoEm": hoje.isoformat(),
            "finalizada": situacao_final(situacao),
        }

    feitos = falhas = 0
    with ThreadPoolExecutor(TRABALHADORES) as ex:
        for f in as_completed([ex.submit(buscar, i) for i in fila]):
            try:
                pid, info = f.result()
                cache[pid] = info
                feitos += 1
            except Exception as e:
                falhas += 1
                if falhas <= 5:
                    avisar(f"detalhe de proposição: {e}")
            if feitos and feitos % 1000 == 0:
                salvar(arquivo, cache)  # não perde o trabalho se a execução for interrompida
    salvar(arquivo, cache)
    print(f"Detalhes salvos: {feitos}, falhas: {falhas}, no cache: {len(cache)}")


# mesmos tipos que o site trata como projeto (TIPOS_PROJETO em site/assets/app.js)
TIPOS_PROJETO = {"PL", "PLP", "PEC", "PDL", "PRC", "PLC", "PLS", "PRS", "PDS", "PLN", "PFC", "PLV", "MPV"}
ORCAMENTO_AUTORES = int(os.environ.get("AUTORES_POR_EXECUCAO", "6000"))


def autores_da_resposta(autores: list) -> dict:
    """De /proposicoes/{id}/autores para {"idPrincipal": idDeputadoPrincipal, "autores": [[idDeputado, nome, tipo], ...]},
    na ordem de assinatura. Quem não é deputado (Executivo, Senado, comissões) entra com id nulo e o
    `tipo` da Câmara ("Órgão do Poder Executivo"...); para deputados o tipo é omitido.
    O principal é quem assinou primeiro (proponente 1, senão ordemAssinatura 1); se não for deputado, idPrincipal fica nulo."""
    lista = sorted((a for a in autores if a.get("nome")), key=lambda a: a.get("ordemAssinatura") or 10**6)
    saida = []
    for a in lista:
        m = re.search(r"/deputados/(\d+)$", a.get("uri") or "")
        if m:
            saida.append([int(m.group(1)), a["nome"].strip()])
        else:
            saida.append([None, a["nome"].strip(), (a.get("tipo") or "").strip() or None])
    if not lista:
        return {"idPrincipal": None, "autores": []}
    i = next((k for k, a in enumerate(lista) if a.get("proponente") == 1), 0)
    return {"idPrincipal": saida[i][0], "autores": saida}


def coletar_autores_proposicoes() -> None:
    """Quem assinou cada projeto e em que ordem, para o site separar autor principal
    de coautor. Guardado em dados/proposicoes_autores.json (vai para o git). A autoria
    não muda, então cada projeto é consultado uma vez só; cada execução consulta no
    máximo ORCAMENTO_AUTORES (os mais novos primeiro) e com os dias o arquivo se completa."""
    arquivo = DADOS / "proposicoes_autores.json"
    cache = ler(arquivo, {})
    todos = set()
    for arq in (DADOS / "proposicoes").glob("*.json"):
        for p in ler(arq, {"itens": []})["itens"]:
            if p.get("siglaTipo") in TIPOS_PROJETO:
                todos.add(str(p["id"]))
    faltam = todos - cache.keys()
    fila = sorted(faltam, key=int, reverse=True)[:ORCAMENTO_AUTORES]
    print(f"Autores de proposições: {len(todos)} projetos, {len(faltam)} sem autoria; consultando {len(fila)}")

    def buscar(pid: str) -> tuple[str, dict]:
        return pid, autores_da_resposta(get(f"/proposicoes/{pid}/autores").get("dados", []) or [])

    feitos = falhas = 0
    with ThreadPoolExecutor(TRABALHADORES) as ex:
        for f in as_completed([ex.submit(buscar, i) for i in fila]):
            try:
                pid, info = f.result()
                cache[pid] = info
                feitos += 1
            except Exception as e:
                falhas += 1
                if falhas <= 5:
                    avisar(f"autores de proposição: {e}")
            if feitos and feitos % 1000 == 0:
                salvar(arquivo, cache)  # não perde o trabalho se a execução for interrompida
    if feitos:  # sem nada novo (ou com a API fora do ar) o arquivo anterior fica como está
        salvar(arquivo, cache)
    print(f"Autores salvos: {feitos}, falhas: {falhas}, no arquivo: {len(cache)}")


def baixar_arquivo_camara(caminho: str) -> list:
    """Arquivo em lote da Câmara (https://dadosabertos.camara.leg.br/arquivos/...): devolve a lista `dados` do JSON."""
    r = S.get(f"{ARQUIVOS_CAMARA}/{caminho}", timeout=300)
    r.raise_for_status()
    return r.json().get("dados", [])


def coletar_temas_proposicoes() -> None:
    """Temas oficiais dos projetos, do arquivo anual proposicoesTemas-{ano}.json (um download por ano da legislatura).
    Guardado em dados/proposicoes_temas.json como {id do projeto: [temas]} (vai para o git). Um ano que falha
    mantém o que já estava guardado."""
    arquivo = DADOS / "proposicoes_temas.json"
    cache = ler(arquivo, {})
    mudou = False
    for ano in range(int(INICIO_LEGISLATURA[:4]), dt.date.today().year + 1):
        try:
            linhas = baixar_arquivo_camara(f"proposicoesTemas/json/proposicoesTemas-{ano}.json")
        except Exception as e:
            avisar(f"temas das proposições de {ano}: {e}")
            continue
        novos: dict[str, list] = {}
        for l in sorted(linhas, key=lambda x: -(x.get("relevancia") or 0)):
            pid = id_da_uri(l.get("uriProposicao"))
            if pid and l.get("siglaTipo") in TIPOS_PROJETO and l.get("tema") and l["tema"] not in novos.setdefault(pid, []):
                novos[pid].append(l["tema"])
        cache.update(novos)
        mudou = True
        print(f"Temas {ano}: {len(novos)} projetos")
    if mudou:
        salvar(arquivo, cache)


def coletar_orgaos_deputados() -> None:
    """Comissões e outros órgãos de cada deputado na legislatura, do arquivo orgaosDeputados-L57.json.
    Guardado em dados/orgaos_deputados.json como {id do deputado: [órgãos]} (vai para o git)."""
    por_dep: dict[str, list] = {}
    for l in baixar_arquivo_camara(f"orgaosDeputados/json/orgaosDeputados-L{LEGISLATURA}.json"):
        m = re.search(r"/deputados/(\d+)$", l.get("uriDeputado") or "")
        if not m or not l.get("siglaOrgao"):
            continue
        por_dep.setdefault(m.group(1), []).append({
            "sigla": l["siglaOrgao"], "nome": (l.get("nomePublicacaoOrgao") or l.get("nomeOrgao") or "").strip(),
            "cargo": l.get("cargo") or None, "inicio": l.get("dataInicio") or None, "fim": l.get("dataFim") or None,
        })
    if por_dep:
        salvar(DADOS / "orgaos_deputados.json", por_dep)
    print(f"Órgãos: {sum(len(v) for v in por_dep.values())} participações de {len(por_dep)} deputados")


def coletar_orientacoes() -> None:
    """Orientação de cada bancada (partido, federação, bloco, Governo...) nas votações nominais já guardadas, do arquivo
    anual votacoesOrientacoes-{ano}.json. Guardado em dados/orientacoes.json como {id da votação: {bancada: orientação}}
    (vai para o git), sem as orientações em branco. Um ano que falha mantém o que já estava guardado."""
    arquivo = DADOS / "orientacoes.json"
    cache = ler(arquivo, {})
    nominais: dict[str, set] = {}
    for arq in (DADOS / "votacoes").glob("*.json"):
        for v in ler(arq, {}).values():
            if v.get("votos"):
                nominais.setdefault(v["data"][:4], set()).add(v["id"])
    mudou = False
    for ano, ids in sorted(nominais.items()):
        try:
            linhas = baixar_arquivo_camara(f"votacoesOrientacoes/json/votacoesOrientacoes-{ano}.json")
        except Exception as e:
            avisar(f"orientações das votações de {ano}: {e}")
            continue
        for l in linhas:
            if l.get("idVotacao") in ids and l.get("siglaBancada") and (l.get("orientacao") or "").strip():
                cache.setdefault(l["idVotacao"], {})[l["siglaBancada"].strip()] = l["orientacao"].strip()
                mudou = True
    if mudou:
        salvar(arquivo, cache)
    print(f"Orientações: {len(cache)} votações")


def coletar_blocos() -> None:
    """Blocos partidários e federações da legislatura com os partidos de cada um (/blocos e /blocos/{id}/partidos).
    Guardado em dados/blocos.json como [{nome, federacao, partidos}] (vai para o git): serve para ligar o nome truncado
    do bloco em votacoesOrientacoes ("Bl UniPpPsd...") aos partidos. Se a API falhar, o arquivo anterior fica."""
    blocos = []
    for b in get_todos("/blocos", idLegislatura=LEGISLATURA):
        partidos = get(f"/blocos/{b['id']}/partidos").get("dados", [])
        blocos.append({"nome": b["nome"], "federacao": bool(b.get("federacao")), "partidos": [p["sigla"] for p in partidos]})
    if blocos:
        salvar(DADOS / "blocos.json", blocos)
    print(f"Blocos: {len(blocos)}")


def coletar_votacoes_proposicoes() -> None:
    """Votações de cada projeto (nominais ou não), do arquivo anual votacoesProposicoes-{ano}.json: um download por ano da
    legislatura no lugar de uma chamada a /proposicoes/{id}/votacoes por projeto. Guardado em dados/proposicoes_votacoes.json
    como {id do projeto: [{id, data, descricao}]} (vai para o git), só dos projetos dos deputados. Um ano que falha mantém
    o que já estava guardado."""
    arquivo = DADOS / "proposicoes_votacoes.json"
    cache = ler(arquivo, {})
    meus = set()
    for arq in (DADOS / "proposicoes").glob("*.json"):
        for p in ler(arq, {"itens": []})["itens"]:
            if p.get("siglaTipo") in TIPOS_PROJETO:
                meus.add(str(p["id"]))
    mudou = False
    for ano in range(int(INICIO_LEGISLATURA[:4]), dt.date.today().year + 1):
        try:
            linhas = baixar_arquivo_camara(f"votacoesProposicoes/json/votacoesProposicoes-{ano}.json")
        except Exception as e:
            avisar(f"votações das proposições de {ano}: {e}")
            continue
        for l in linhas:
            pid = str((l.get("proposicao_") or l.get("proposicao") or {}).get("id") or "")
            if pid not in meus or not l.get("idVotacao"):
                continue
            lista = cache.setdefault(pid, [])
            if not any(x["id"] == l["idVotacao"] for x in lista):
                lista.append({"id": l["idVotacao"], "data": l.get("data"), "descricao": (l.get("descricao") or "").strip()[:300]})
                mudou = True
    if mudou:
        for lista in cache.values():
            lista.sort(key=lambda x: x["data"] or "")
        salvar(arquivo, cache)
    print(f"Votações de projetos: {sum(len(v) for v in cache.values())} votações em {len(cache)} projetos")


def tipo_evento(descricao_tipo: str | None) -> str:
    """Classe do evento da Câmara para a presença: sessoes (Sessão Deliberativa do Plenário), comissoes (reuniões e
    audiências, que são das comissões) ou outros (sessões solenes, seminários, visitas...)."""
    t = (descricao_tipo or "").strip()
    if t == "Sessão Deliberativa":
        return "sessoes"
    if t.startswith(("Reunião", "Audiência")):
        return "comissoes"
    return "outros"


def coletar_presenca_eventos() -> None:
    """Presença dos deputados nos eventos da Câmara, de eventosPresencaDeputados-{ano}.json (~30 MB por ano) e da lista de
    eventos do ano, que dá o tipo de cada um. Guardado em dados/presenca_eventos.json como
    {ano: {sessoesDeliberativas, deputados: {id: {sessoes, comissoes, outros}}}} (vai para o git): `sessoesDeliberativas` é o
    total de sessões deliberativas encerradas do ano. Anos encerrados já guardados não são baixados de novo; um ano que
    falha mantém o que já estava guardado."""
    arquivo = DADOS / "presenca_eventos.json"
    cache = ler(arquivo, {})
    hoje = dt.date.today()
    for ano in range(int(INICIO_LEGISLATURA[:4]), hoje.year + 1):
        if str(ano) in cache and ano < hoje.year:
            continue
        try:
            eventos = {e["id"]: e for e in baixar_arquivo_camara(f"eventos/json/eventos-{ano}.json")}
            presencas = baixar_arquivo_camara(f"eventosPresencaDeputados/json/eventosPresencaDeputados-{ano}.json")
        except Exception as e:
            avisar(f"presença em eventos de {ano}: {e}")
            continue
        vistos: set[tuple] = set()
        deputados: dict[str, dict] = {}
        for l in presencas:
            chave = (l.get("idEvento"), l.get("idDeputado"))
            if None in chave or chave in vistos:
                continue
            vistos.add(chave)
            classe = tipo_evento((eventos.get(l["idEvento"]) or {}).get("descricaoTipo"))
            d = deputados.setdefault(str(l["idDeputado"]), {"sessoes": 0, "comissoes": 0, "outros": 0})
            d[classe] += 1
        sessoes = sum(1 for e in eventos.values() if tipo_evento(e.get("descricaoTipo")) == "sessoes" and (e.get("situacao") or "").startswith("Encerrada"))
        cache[str(ano)] = {"sessoesDeliberativas": sessoes, "deputados": deputados}
        print(f"Presença {ano}: {len(deputados)} deputados, {sessoes} sessões deliberativas")
        salvar(arquivo, cache)


def situacao_final(situacao: str) -> bool:
    """True quando a proposição não vai mais tramitar (não precisa ser reconsultada)."""
    s = (situacao or "").lower()
    return any(k in s for k in ("arquivad", "transformad", "retirad", "perdeu a eficácia", "vetad", "sancionad", "devolvid"))


# ---------------------------------------------------------------- senado

SENADO = os.environ.get("SENADO_API", "https://legis.senado.leg.br/dadosabertos")
SENADO_ADM = os.environ.get("SENADO_ADM_API", "https://adm.senado.gov.br/adm-dadosabertos/api/v1")


def coletar_senado() -> None:
    r = S.get(f"{SENADO}/senador/lista/atual.json", timeout=60)
    r.raise_for_status()
    lista = r.json()["ListaParlamentarEmExercicio"]["Parlamentares"]["Parlamentar"]
    if isinstance(lista, dict):
        lista = [lista]
    senadores = []
    for s in lista:
        ident = s.get("IdentificacaoParlamentar", {})
        mandato = s.get("Mandato", {}) or {}
        fim = max((mandato.get(k, {}) or {}).get("DataFim") or "" for k in
                  ("PrimeiraLegislaturaDoMandato", "SegundaLegislaturaDoMandato")) or None
        exercicios = (mandato.get("Exercicios", {}) or {}).get("Exercicio") or []
        if isinstance(exercicios, dict):
            exercicios = [exercicios]
        abertos = [x.get("DataInicio") for x in exercicios if not x.get("DataFim") and x.get("DataInicio")]
        senadores.append({
            "titular": (mandato.get("Titular", {}) or {}).get("NomeParlamentar"),
            "exercicioDesde": max(abertos) if abertos else None,
            "id": ident.get("CodigoParlamentar"),
            "nome": ident.get("NomeParlamentar"),
            "nomeCivil": ident.get("NomeCompletoParlamentar"),
            "partido": ident.get("SiglaPartidoParlamentar"),
            "uf": ident.get("UfParlamentar") or mandato.get("UfParlamentar"),
            "foto": ident.get("UrlFotoParlamentar"),
            "pagina": ident.get("UrlPaginaParlamentar"),
            "email": ident.get("EmailParlamentar"),
            "genero": ident.get("SexoParlamentar"),
            "participacao": mandato.get("DescricaoParticipacao"),
            "fimMandato": fim,
        })
    salvar(DADOS / "senado.json", senadores)
    print(f"Senadores em exercício: {len(senadores)}")


# ---------------------------------------------------------------- senado: votos e autorias

TIPOS_PROJETO_SENADO = TIPOS_PRINCIPAIS | {"PLC", "PRS", "PDS", "PLS"}


def get_senado(caminho: str, **params):
    r = S.get(f"{SENADO}{caminho}", params=params or None, headers={"Accept": "application/json"}, timeout=180)
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status_code} em {r.url}: {r.text[:200]!r}")
    return r.json()


# siglas de voto do Senado (campo siglaVotoParlamentar) -> chaves que o site usa
VOTOS_SENADO = {"sim": "sim", "não": "nao", "abstenção": "abstencao", "obstrução": "obstrucao",
                "presidente (art. 51 risf)": "art17",
                "votou": "secreto"}  # votação secreta: o Senado informa que votou, mas não como
# quem não registrou voto (licenças, missão, atividade parlamentar, presença sem voto, dispositivo não citado)
SEM_VOTO_SENADO = {"ncom", "ls", "lp", "lap", "mis", "ap", "p-nrv", "na"}


def tipo_voto_senado(sigla: str | None, descricao: str | None) -> str:
    """Normaliza o voto para as chaves que o site usa. Quem não votou fica como 'ausente'."""
    s = (sigla or "").strip().lower()
    if s in SEM_VOTO_SENADO:
        return "ausente"
    if s in VOTOS_SENADO:
        return VOTOS_SENADO[s]
    # sigla nova: tenta pela descrição. "Não compareceu" e "Presente – Não registrou voto" não são voto contra
    t = f"{sigla or ''} {descricao or ''}".lower()
    if any(k in t for k in ("compareceu", "licen", "ausente", "missão", "missao", "representa", "presente", "atividade", "não citado", "nao citado")):
        return "ausente"
    if re.search(r"\bsim\b|favor", t):
        return "sim"
    if re.search(r"\bn[aã]o\b|contr", t):
        return "nao"
    if "absten" in t:
        return "abstencao"
    if "obstru" in t:
        return "obstrucao"
    if "presidente" in t or "art. 51" in t:
        return "art17"
    return "outro"


def resultado_senado(texto: str | None) -> int | None:
    t = (texto or "").strip().lower()
    if t in ("a", "aprovado", "aprovada", "aprovado(a)") or "aprovad" in t:
        return 1
    if t in ("r", "rejeitado", "rejeitada", "p", "prejudicado", "prejudicada") or "rejeitad" in t or "prejudicad" in t:
        return 0
    return None


def normalizar_votacao_senado(v: dict) -> dict | None:
    """Votação do endpoint /votacao. Votações simbólicas ou sem voto individual não entram."""
    votos = []
    for x in v.get("votos") or []:
        cod = x.get("codigoParlamentar")
        if cod is None:
            continue
        sigla, desc = x.get("siglaVotoParlamentar"), x.get("descricaoVotoParlamentar")
        # 3º item: rótulo como o Senado publicou, para poder reclassificar sem consultar de novo
        votos.append([str(cod), tipo_voto_senado(sigla, desc), f"{sigla or ''}|{desc or ''}"])
    data = str(v.get("dataSessao") or "")[:10]
    if not votos or not data:
        return None
    resultado = v.get("resultadoVotacao")
    # placar oficial do Senado; nulo em parte das votações (aí o site conta os votos individuais)
    totais = {k: v[campo] for k, campo in (("sim", "totalVotosSim"), ("nao", "totalVotosNao"), ("abstencao", "totalVotosAbstencao"))
              if v.get(campo) is not None}
    sessao = {k: v[campo] for k, campo in (("numero", "numeroSessao"), ("tipo", "siglaTipoSessao"), ("sequencial", "sequencialSessao"),
                                           ("votacao", "sequencialVotacao")) if v.get(campo) is not None}
    return {
        "id": str(v["codigoSessaoVotacao"]), "data": data, "hora": None,
        "descricao": (v.get("descricaoVotacao") or "").strip(),
        "proposicao": v.get("identificacao") or None, "propId": v.get("codigoMateria"),
        "ementa": (v.get("ementa") or "").strip() or None,
        "aprovada": resultado_senado(resultado), "resultadoTexto": resultado,
        "secreta": str(v.get("votacaoSecreta") or "").upper() == "S",
        "totais": totais or None, "sessao": sessao or None, "processo": v.get("idProcesso"),
        "votos": votos,
    }


def reclassificar_votos_senado(pasta: Path) -> int:
    """Reaplica a classificação aos votos já salvos, a partir do rótulo original (3º item). Devolve quantos mudaram."""
    mudaram = 0
    for arq in sorted(pasta.glob("[0-9]*.json")):
        mapa, alterado = ler(arq, {}), False
        for v in mapa.values():
            for x in v["votos"]:
                if len(x) > 2:
                    sigla, _, desc = x[2].partition("|")
                    tipo = tipo_voto_senado(sigla, desc)
                    if tipo != x[1]:
                        x[1], alterado = tipo, True
                        mudaram += 1
        if alterado:
            salvar(arq, mapa)
    return mudaram


def coletar_votacoes_senado() -> None:
    """Votações nominais do Plenário do Senado, com o voto de cada senador (endpoint /votacao).
    Um arquivo por ano em dados/senado_votacoes/ (vai para o git)."""
    pasta = DADOS / "senado_votacoes"
    pasta.mkdir(parents=True, exist_ok=True)
    hoje = dt.date.today()
    ultimo_ano = max((int(a.stem) for a in pasta.glob("[0-9]*.json")), default=int(INICIO_LEGISLATURA[:4]))
    # arquivos de antes de guardarmos o rótulo original do voto: consulta de novo
    sem_rotulo = [int(a.stem) for a in pasta.glob("[0-9]*.json")
                  if any(len(v["votos"][0]) < 3 for v in ler(a, {}).values() if v.get("votos"))]
    # arquivos de antes de guardarmos voto secreto e placar oficial: consulta de novo
    sem_detalhe = [int(a.stem) for a in pasta.glob("[0-9]*.json") if any("secreta" not in v for v in ler(a, {}).values())]
    if sem_rotulo or sem_detalhe:
        ultimo_ano = min([ultimo_ano, *sem_rotulo, *sem_detalhe])
    reclassificados = reclassificar_votos_senado(pasta)
    if reclassificados:
        print(f"  Votos do Senado reclassificados a partir do rótulo original: {reclassificados}")
    total = 0
    for ano in range(ultimo_ano, hoje.year + 1):
        try:
            dados = get_senado("/votacao", dataInicio=f"{ano}-01-01", dataFim=min(dt.date(ano, 12, 31), hoje).isoformat())
        except Exception as e:
            avisar(f"votações do Senado em {ano}: {str(e)[:200]}")
            continue
        achadas = [n for n in (normalizar_votacao_senado(v) for v in dados if isinstance(v, dict)) if n]
        if not achadas:
            avisar(f"votações do Senado em {ano}: {len(dados)} itens, nenhum com votos individuais")
            continue
        mapa = ler(pasta / f"{ano}.json", {})
        for n in achadas:
            if n["data"][:4] == str(ano):
                mapa[n["id"]] = n
        salvar(pasta / f"{ano}.json", mapa)
        total += len(achadas)
        print(f"  Senado {ano}: {len(achadas)} votações nominais")
    print(f"Votações nominais do Senado coletadas: {total}")
    # resumo dos rótulos de voto por classificação, para conferir se o mapeamento está certo
    rotulos: dict[str, dict[str, int]] = {}
    for arq in pasta.glob("[0-9]*.json"):
        for v in ler(arq, {}).values():
            for x in v["votos"]:
                if len(x) > 2:
                    r = rotulos.setdefault(x[1], {})
                    r[x[2]] = r.get(x[2], 0) + 1
    salvar(pasta / "_rotulos.json", rotulos)
    for tipo, r in rotulos.items():
        print(f"  {tipo}: {sorted(r.items(), key=lambda kv: -kv[1])[:6]}")


def coletar_ceaps_senado() -> None:
    """Gastos da cota (CEAPS) do ano corrente, de todos os senadores, numa chamada só.
    Fica em dados/senado_ceaps.json (não vai para o git: é baixado de novo a cada execução)."""
    ano = dt.date.today().year
    r = S.get(f"{SENADO_ADM}/senadores/despesas_ceaps/{ano}", headers={"Accept": "application/json"}, timeout=180)
    r.raise_for_status()
    itens: dict[str, list] = {}
    for d in r.json():
        if not d.get("codSenador"):
            continue
        itens.setdefault(str(d["codSenador"]), []).append({
            "mes": d.get("mes"), "tipo": d.get("tipoDespesa"), "valor": d.get("valorReembolsado") or 0,
            "fornecedor": d.get("fornecedor"), "data": d.get("data"),
        })
    for lista in itens.values():
        lista.sort(key=lambda i: i["data"] or "", reverse=True)
    salvar(DADOS / "senado_ceaps.json", {"ano": ano, "itens": itens})
    print(f"CEAPS {ano}: {sum(len(v) for v in itens.values())} despesas de {len(itens)} senadores")


def chave_nome(nome: str | None) -> str:
    """Nome sem acento, maiúsculo e sem espaços repetidos, para ligar listas que escrevem o nome de formas diferentes."""
    sem = unicodedata.normalize("NFD", nome or "")
    return " ".join("".join(c for c in sem if not unicodedata.combining(c)).upper().split())


def coletar_recursos_senado() -> None:
    """Recursos e benefícios de cada senador em exercício (gastos fora da cota, auxílio-moradia, imóvel funcional,
    pessoal) e os escritórios de apoio nos estados. Fica em dados/senado_recursos.json (não vai para o git)."""
    senadores = ler(DADOS / "senado.json", [])
    if not senadores:
        raise RuntimeError("lista de senadores vazia; recursos não coletados")
    ano = dt.date.today().year
    cab = {"Accept": "application/json"}

    def buscar(s: dict) -> tuple[str, dict | None]:
        r = S.get(f"{SENADO_ADM}/senadores/{s['id']}/recursos-utilizados", params={"ano": ano}, headers=cab, timeout=60)
        r.raise_for_status()
        dados = r.json().get("data") or []
        if not dados:
            return str(s["id"]), None
        d = dados[0]
        fora = d.get("gastosNaoInclusos") or {}
        return str(s["id"]), {
            "foraCota": [[x["recurso"], x.get("valor") or 0] for x in fora.get("despesas") or [] if x.get("valor")],
            "totalForaCota": fora.get("totalValor") or 0,
            "beneficios": [[x["beneficio"], x.get("utilizacao")] for x in d.get("beneficios") or []],
            "pessoal": [[x["local"], x.get("quantidade") or 0] for x in d.get("pessoal") or []],
        }

    recursos: dict[str, dict] = {}
    falhas = 0
    with ThreadPoolExecutor(TRABALHADORES_SENADO) as ex:
        for f in as_completed([ex.submit(buscar, s) for s in senadores]):
            try:
                sid, item = f.result()
                if item:
                    recursos[sid] = item
            except Exception as e:
                falhas += 1
                if falhas <= 5:
                    avisar(f"recursos de senador: {e}")

    escritorios: dict[str, list] = {}
    try:
        r = S.get(f"{SENADO_ADM}/senadores/escritorios-apoio", headers=cab, timeout=60)
        r.raise_for_status()
        por_nome = {(chave_nome(s.get("nome")), s.get("uf")): str(s["id"]) for s in senadores}
        for e in r.json().get("data") or []:
            sid = por_nome.get((chave_nome((e.get("parlamentar") or {}).get("nome")), (e.get("parlamentar") or {}).get("estado")))
            setor = e.get("setor") or {}
            if sid and (setor.get("endereco") or setor.get("telefone")):
                escritorios.setdefault(sid, []).append({k: setor[k] for k in ("nome", "endereco", "telefone") if setor.get(k)})
    except Exception as e:
        avisar(f"escritórios de apoio: {e}")

    salvar(DADOS / "senado_recursos.json", {"ano": ano, "recursos": recursos, "escritorios": escritorios})
    print(f"Recursos de {len(recursos)} senadores, escritórios de {len(escritorios)}, falhas: {falhas}")


IDENTIFICACAO_SENADO = re.compile(r"^(?P<tipo>\S+)\s+(?P<numero>[\d.]+)/(?P<ano>\d{4})$")


def primeiro_autor_senado(autoria: str | None, nome: str | None) -> bool:
    """True se o senador é o primeiro autor listado (ordem 1), o 'autor principal' do site."""
    m = re.match(r"\s*Senador(?:a)?\s+(.+?)\s*\(", (autoria or "").split(", Senador")[0])
    return bool(m and nome and m.group(1).strip().lower() == nome.strip().lower())


def autoria_senado(p: dict, nome: str | None) -> dict | None:
    """Processo do endpoint /processo -> item de autoria. None para o que o site não mostra (antes de 2019 ou sem número)."""
    m = IDENTIFICACAO_SENADO.match(p.get("identificacao") or "")
    if not m or not p.get("codigoMateria") or int(m["ano"]) < 2019:  # mandato mais antigo em exercício começou em 2019
        return None
    return {"id": str(p["codigoMateria"]), "processo": p["id"], "tipo": m["tipo"], "numero": m["numero"].replace(".", ""), "ano": int(m["ano"]),
            "ementa": (p.get("ementa") or "").strip(), "principal": primeiro_autor_senado(p.get("autoria"), nome),
            "dataApresentacao": (p.get("dataApresentacao") or "")[:10] or None,
            "situacao": p.get("situacaoAtual"), "dataSituacao": (p.get("dataSituacaoAtual") or "")[:10] or None}


def coletar_autorias_senado() -> None:
    """Matérias de que cada senador em exercício é autor ou coautor, com a situação atual (endpoint /processo).
    As autorias não vão para o git; dados/senado_materias.json (situação dos projetos) vai, para o resumo diário."""
    senadores = ler(DADOS / "senado.json", [])
    if not senadores:
        raise RuntimeError("lista de senadores vazia; autorias não coletadas")
    autorias: dict[str, list] = {}

    def buscar(s: dict) -> tuple[str, list]:
        itens = [a for a in (autoria_senado(p, s.get("nome")) for p in get_senado("/processo", codigoParlamentarAutor=s["id"])) if a]
        return str(s["id"]), sorted(itens, key=lambda i: (i["ano"], int(re.sub(r"\D", "", i["numero"]) or 0)), reverse=True)

    falhas = 0
    with ThreadPoolExecutor(TRABALHADORES_SENADO) as ex:
        for f in as_completed([ex.submit(buscar, s) for s in senadores]):
            try:
                sid, itens = f.result()
                autorias[sid] = itens
            except Exception as e:
                falhas += 1
                if falhas <= 5:
                    avisar(f"autorias de senador: {e}")
    salvar(DADOS / "senado_autorias.json", autorias)
    print(f"Autorias de {len(autorias)} senadores, falhas: {falhas}")

    # situação dos projetos, uma vez por matéria (coautorias repetem a mesma)
    arquivo = DADOS / "senado_materias.json"
    materias = {i["id"]: {"situacao": i["situacao"], "dataSituacao": i["dataSituacao"], "dataApresentacao": i["dataApresentacao"], "processo": i["processo"]}
                for itens in autorias.values() for i in itens if i["tipo"] in TIPOS_PROJETO_SENADO}
    if falhas:  # senador que falhou não pode apagar do cache o que já se sabia sobre ele
        materias = {**ler(arquivo, {}), **materias}
    salvar(arquivo, materias)
    print(f"Matérias do Senado: {len(materias)} projetos")


# ---------------------------------------------------------------- votações

def janelas(inicio: dt.date, fim: dt.date):
    """Quebra o período em janelas de até 30 dias, sem atravessar o ano
    (a API recusa intervalos longos)."""
    atual = inicio
    while atual <= fim:
        limite = min(atual + dt.timedelta(days=29), fim, dt.date(atual.year, 12, 31))
        yield atual, limite
        atual = limite + dt.timedelta(days=1)


def coletar_votos(votacao: dict) -> dict:
    votos = get(f"/votacoes/{votacao['id']}/votos").get("dados", [])
    proposicao, ementa, prop_id = votacao.get("proposicaoObjeto"), None, None
    if votos:  # só nas nominais: busca a proposição votada, que a lista nem sempre traz
        try:
            det = get(f"/votacoes/{votacao['id']}").get("dados", {}) or {}
            afetadas = det.get("proposicoesAfetadas") or []
            if afetadas:
                p = afetadas[0]
                prop_id = p.get("id")
                proposicao = proposicao or f"{p.get('siglaTipo')} {p.get('numero')}/{p.get('ano')}"
                ementa = (p.get("ementa") or "").strip() or None
        except Exception as e:
            avisar(f"detalhe da votação {votacao['id']}: {e}")
    return {
        "id": votacao["id"],
        "data": votacao.get("data") or (votacao.get("dataHoraRegistro") or "")[:10],
        "hora": (votacao.get("dataHoraRegistro") or "")[11:16],
        "orgao": votacao.get("siglaOrgao"),
        "descricao": (votacao.get("descricao") or "").strip(),
        "proposicao": proposicao,
        "propId": prop_id,
        "ementa": ementa,
        "aprovada": votacao.get("aprovacao"),
        "votos": [[v["deputado_"]["id"], v.get("tipoVoto")]
                  for v in votos if v.get("deputado_")],
    }


def coletar_votacoes(dias_iniciais: int) -> None:
    pasta = DADOS / "votacoes"
    hoje = dt.date.today()
    arquivos = sorted(pasta.glob("*.json"))
    ultima = None
    for arq in arquivos:
        for v in ler(arq, {}).values():
            d = dt.date.fromisoformat(v["data"])
            ultima = d if ultima is None or d > ultima else ultima
    # recoleta alguns dias para pegar votações registradas com atraso
    inicio = (ultima - dt.timedelta(days=3)) if ultima else hoje - dt.timedelta(days=dias_iniciais)
    print(f"Votações de {inicio} a {hoje}")

    encontradas = []
    for a, b in janelas(inicio, hoje):
        try:
            lote = get_todos("/votacoes", dataInicio=a.isoformat(), dataFim=b.isoformat(),
                             ordem="ASC", ordenarPor="dataHoraRegistro", itens=200)
        except Exception as e:
            avisar(f"votações de {a} a {b}: {e}")
            continue
        # por enquanto só o Plenário, onde todos os deputados votam
        encontradas += [v for v in lote if v.get("siglaOrgao") == "PLEN"]
    print(f"Votações no Plenário encontradas: {len(encontradas)}")
    # votações antigas salvas antes de guardarmos a proposição votada: completa uma vez
    novas = {v["id"] for v in encontradas}
    for arq in arquivos:
        for v in ler(arq, {}).values():
            if v.get("votos") and ("ementa" not in v or "propId" not in v) and v["id"] not in novas:
                encontradas.append({"id": v["id"], "data": v["data"],
                                    "dataHoraRegistro": f"{v['data']}T{v.get('hora') or '00:00'}:00",
                                    "siglaOrgao": v.get("orgao"), "descricao": v.get("descricao"),
                                    "proposicaoObjeto": v.get("proposicao"), "aprovacao": v.get("aprovada")})

    por_ano: dict[str, dict] = {}
    with ThreadPoolExecutor(TRABALHADORES) as ex:
        for f in as_completed([ex.submit(coletar_votos, v) for v in encontradas]):
            try:
                v = f.result()
            except Exception as e:
                avisar(f"votos: {e}")
                continue
            ano = v["data"][:4]
            if ano not in por_ano:
                por_ano[ano] = ler(pasta / f"{ano}.json", {})
            por_ano[ano][v["id"]] = v
    for ano, mapa in por_ano.items():
        salvar(pasta / f"{ano}.json", mapa)
    total = sum(len(ler(a, {})) for a in pasta.glob("*.json"))
    print(f"Votações no histórico: {total}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--limite", type=int, help="coletar só os N primeiros deputados (teste)")
    p.add_argument("--dias", type=int, default=90, help="dias de votações na primeira coleta")
    p.add_argument("--so", choices=["deputados", "votacoes", "proposicoes", "senado"], help="coletar só uma parte")
    a = p.parse_args()
    if a.so in (None, "deputados"):
        coletar_deputados(a.limite)
    if a.so in (None, "votacoes"):
        coletar_votacoes(a.dias)
    if a.so in (None, "proposicoes"):
        try:
            coletar_detalhes_proposicoes()
        except Exception as e:  # os detalhes são um complemento: não derrubam a coleta
            avisar(f"detalhes das proposições: {e}")
        try:
            coletar_autores_proposicoes()
        except Exception as e:
            avisar(f"autores das proposições: {e}")
        for etapa in (coletar_temas_proposicoes, coletar_orgaos_deputados, coletar_orientacoes,
                      coletar_blocos, coletar_votacoes_proposicoes, coletar_presenca_eventos):  # complementos: cada um falha sozinho
            try:
                etapa()
            except Exception as e:
                avisar(f"{etapa.__name__}: {e}")
    if a.so in (None, "senado"):
        try:
            coletar_senado()
        except Exception as e:
            avisar(f"senado: {e}")
        for etapa in (coletar_votacoes_senado, coletar_autorias_senado, coletar_ceaps_senado, coletar_recursos_senado):  # complementos: cada um falha sozinho
            try:
                etapa()
            except Exception as e:
                avisar(f"{etapa.__name__}: {e}")
    salvar(DADOS / "meta.json", {
        "atualizadoEm": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "fonte": "API de Dados Abertos da Câmara dos Deputados",
        "fonteUrl": "https://dadosabertos.camara.leg.br",
    })


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::error::Coleta interrompida: {str(e)[:900]}")
        raise
    if AVISOS:
        print(f"Concluído com {len(AVISOS)} avisos.")
