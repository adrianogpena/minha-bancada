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
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API = os.environ.get("CAMARA_API", "https://dadosabertos.camara.leg.br/api/v2")
RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "dados"
INICIO_LEGISLATURA = "2023-02-01"  # 57ª legislatura
TRABALHADORES_SENADO = 2  # o Senado responde 503 quando apertado
TRABALHADORES = 6  # requisições em paralelo; seja gentil com a API pública


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


def coletar_deputado(dep: dict, ano: int) -> dict:
    did = dep["id"]
    detalhe = get(f"/deputados/{did}").get("dados", {})

    proposicoes = coletar_proposicoes(dep)

    try:
        despesas = get_todos(f"/deputados/{did}/despesas", ano=ano,
                             ordem="DESC", ordenarPor="dataDocumento")
    except Exception as e:
        avisar(f"despesas de {dep.get('nome')}: {e}")
        despesas = []

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
        "despesas": {
            "ano": ano,
            "itens": [
                {"mes": d.get("mes"), "tipo": d.get("tipoDespesa"),
                 "valor": d.get("valorLiquido") or 0,
                 "fornecedor": d.get("nomeFornecedor"),
                 "data": d.get("dataDocumento"),
                 "documento": d.get("urlDocumento")}
                for d in despesas
            ],
        },
        "coletadoEm": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }


def coletar_deputados(limite: int | None) -> list:
    lista = get_todos("/deputados", ordem="ASC", ordenarPor="nome")
    if limite:
        lista = lista[:limite]
    print(f"Deputados em exercício: {len(lista)}")
    ano = dt.date.today().year
    resumo, falhas = [], 0
    with ThreadPoolExecutor(TRABALHADORES) as ex:
        futuros = {ex.submit(coletar_deputado, d, ano): d for d in lista}
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
                     if not cache[i].get("fim") and cache[i].get("em", "") < limite_velho),
                    key=lambda i: cache[i].get("em", ""))
    fila = (novos + velhos)[:ORCAMENTO_DETALHES]
    print(f"Detalhes de proposições: {len(todos)} projetos, {len(novos)} novos, {len(velhos)} a renovar; consultando {len(fila)}")

    def buscar(pid: str) -> tuple[str, dict]:
        d = get(f"/proposicoes/{pid}").get("dados", {}) or {}
        st = d.get("statusProposicao") or d.get("ultimoStatus") or {}
        situacao = st.get("descricaoSituacao") or ""
        return pid, {
            "apres": (d.get("dataApresentacao") or "")[:10] or None,
            "sit": situacao or None,
            "tram": st.get("descricaoTramitacao"),
            "desp": (st.get("despacho") or "").strip() or None,
            "org": st.get("siglaOrgao"),
            "data": (st.get("dataHora") or "")[:10] or None,
            "regime": st.get("regime"),
            "inteiroTeor": d.get("urlInteiroTeor"),
            "detalhada": (d.get("ementaDetalhada") or "").strip() or None,
            "palavras": (d.get("keywords") or "").strip() or None,
            "em": hoje.isoformat(),
            "fim": situacao_final(situacao),
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
ORCAMENTO_MATERIAS = int(os.environ.get("MATERIAS_POR_EXECUCAO", "1500"))


def get_senado(caminho: str, **params):
    r = S.get(f"{SENADO}{caminho}", params=params or None, headers={"Accept": "application/json"}, timeout=90)
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status_code} em {r.url}: {r.text[:200]!r}")
    return r.json()


def achar(obj, chave: str):
    """Primeiro valor da chave em qualquer nível. A API do Senado converte XML em JSON e
    ora devolve objeto, ora lista, ora muda o aninhamento; assim não dependemos disso."""
    if isinstance(obj, dict):
        if chave in obj:
            return obj[chave]
        for v in obj.values():
            r = achar(v, chave)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = achar(v, chave)
            if r is not None:
                return r
    return None


def como_lista(x) -> list:
    return x if isinstance(x, list) else ([] if x is None else [x])


def tipo_voto_senado(sigla: str | None, descricao: str | None) -> str:
    """Normaliza o voto para as chaves que o site usa. Quem não votou fica como 'ausente'."""
    t = f"{sigla or ''} {descricao or ''}".lower()
    if any(k in t for k in ("compareceu", "ncom", "licen", "ausente", "missão", "missao", "representa")):
        return "ausente"  # antes do "não": "Não compareceu" não é voto contra
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


def resultado_senado(texto: str | None, sim: int, nao: int) -> int | None:
    t = (texto or "").strip().lower()
    if t in ("a", "aprovado", "aprovada", "aprovado(a)") or "aprovad" in t:
        return 1
    if t in ("r", "rejeitado", "rejeitada", "p", "prejudicado", "prejudicada") or "rejeitad" in t or "prejudicad" in t:
        return 0
    return None


def pegar(d, *nomes):
    """Valor da primeira chave existente, sem diferenciar maiúsculas: a API do Senado
    mistura camelCase e PascalCase conforme o endpoint."""
    if not isinstance(d, dict):
        return None
    baixo = {k.lower(): v for k, v in d.items()}
    for n in nomes:
        v = baixo.get(n.lower())
        if v not in (None, ""):
            return v
    return None


def normalizar_votacao_senado(v: dict) -> dict | None:
    votos_brutos = pegar(v, "votos")
    if isinstance(votos_brutos, dict):  # {"VotoParlamentar": [...]}
        votos_brutos = next(iter(votos_brutos.values()), [])
    votos = []
    for x in como_lista(votos_brutos):
        cod = pegar(x, "codigoParlamentar")
        if cod is None and isinstance(pegar(x, "parlamentar"), dict):
            cod = pegar(pegar(x, "parlamentar"), "codigoParlamentar")
        if cod is None:
            continue
        sigla = pegar(x, "siglaVotoParlamentar", "siglaVoto", "voto")
        desc = pegar(x, "descricaoVotoParlamentar", "descricaoVoto", "voto")
        # 3º item: rótulo como o Senado publicou, para poder reclassificar sem consultar de novo
        votos.append([str(cod), tipo_voto_senado(sigla, desc), f"{sigla or ''}|{desc or ''}"])
    if not votos:  # votação simbólica ou secreta: não há voto individual
        return None
    sessao = pegar(v, "sessaoPlenaria") or {}
    data = str(pegar(v, "dataSessao", "data") or pegar(sessao, "dataSessao") or "")[:10]
    if not data:
        return None
    if re.fullmatch(r"\d{8}", data):
        data = f"{data[:4]}-{data[4:6]}-{data[6:]}"
    sim = sum(1 for _, t, _r in votos if t == "sim")
    nao = sum(1 for _, t, _r in votos if t == "nao")
    sigla, numero, ano = pegar(v, "siglaMateria"), pegar(v, "numeroMateria"), pegar(v, "anoMateria")
    ident = " ".join(x for x in (str(sigla or ""), f"{numero}/{ano}" if numero else "") if x) or pegar(v, "identificacao")
    resultado = pegar(v, "resultadoVotacao", "resultado")
    vid = str(pegar(v, "codigoSessaoVotacao", "codigoVotacao") or f"{pegar(v, 'codigoSessao')}-{pegar(v, 'sequencialSessao')}")
    return {
        "id": vid, "data": data, "hora": str(pegar(v, "horaInicio", "hora") or "")[:5] or None,
        "descricao": str(pegar(v, "descricaoVotacao", "descricao") or "").strip(),
        "proposicao": ident or None, "propId": pegar(v, "codigoMateria"),
        "ementa": str(pegar(v, "ementa", "ementaMateria") or "").strip() or None,
        "aprovada": resultado_senado(resultado, sim, nao), "resultadoTexto": resultado,
        "votos": votos,
    }


def coletar_votacoes_senado() -> None:
    """Votações nominais do Plenário do Senado, com o voto de cada senador.
    Um arquivo por ano em dados/senado_votacoes/ (vai para o git).
    Não achei a documentação oficial para consultar daqui, então tenta mais de um
    endpoint e deixa no log o formato da resposta para facilitar o ajuste."""
    pasta = DADOS / "senado_votacoes"
    pasta.mkdir(parents=True, exist_ok=True)
    hoje = dt.date.today()
    ultimo_ano = max((int(a.stem) for a in pasta.glob("*.json")), default=int(INICIO_LEGISLATURA[:4]))
    # arquivos de antes de guardarmos o rótulo original do voto: consulta de novo
    sem_rotulo = [int(a.stem) for a in pasta.glob("[0-9]*.json")
                  if any(len(v["votos"][0]) < 3 for v in ler(a, {}).values() if v.get("votos"))]
    if sem_rotulo:
        ultimo_ano = min(ultimo_ano, min(sem_rotulo))
    total = 0
    for ano in range(ultimo_ano, hoje.year + 1):
        tentativas = [
            ("nominais do ano", lambda ano=ano: get_senado(f"/plenario/votacao/nominal/{ano}")),
            ("busca por datas", lambda ano=ano: get_senado("/votacao", dataInicio=f"{ano}-01-01",
                                                          dataFim=min(dt.date(ano, 12, 31), hoje).isoformat())),
        ]
        achadas, erros = [], []
        for nome, buscar in tentativas:
            try:
                dados = buscar()
            except Exception as e:
                erros.append(f"{nome}: {str(e)[:160]}")
                continue
            lista = dados
            if isinstance(dados, dict):  # algumas versões embrulham a lista
                lista = achar(dados, "Votacao") or achar(dados, "votacoes") or []
            lista = como_lista(lista)
            achadas = [n for n in (normalizar_votacao_senado(v) for v in lista if isinstance(v, dict)) if n]
            if achadas:
                break
            amostra = lista[0] if lista else dados
            erros.append(f"{nome}: {len(lista)} itens, nenhum com votos individuais; chaves: {sorted(amostra)[:25] if isinstance(amostra, dict) else type(amostra).__name__}")
        if not achadas:
            avisar(f"votações do Senado em {ano}: " + " | ".join(erros))
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


def coletar_autorias_senado() -> None:
    """Matérias de que cada senador em exercício é autor, e a situação atual delas."""
    senadores = ler(DADOS / "senado.json", [])
    autorias: dict[str, list] = {}

    def buscar(sid: str) -> tuple[str, list]:
        dados = get_senado(f"/senador/{sid}/autorias")
        itens = []
        for a in como_lista(achar(dados, "Autoria")):
            m = a.get("Materia") or a
            codigo = m.get("Codigo") or achar(a, "CodigoMateria")
            ano = int(m.get("Ano") or 0)
            if not codigo or ano < 2019:  # mandato mais antigo em exercício começou em 2019
                continue
            itens.append({"id": str(codigo), "tipo": m.get("Sigla") or m.get("SiglaSubtipoMateria"),
                          "numero": m.get("Numero"), "ano": ano,
                          "ementa": (m.get("Ementa") or "").strip(),
                          "principal": a.get("IndicadorAutorPrincipal") == "Sim",
                          "ap": str(m.get("Data") or m.get("DataApresentacao") or "")[:10] or None})
        return sid, sorted(itens, key=lambda i: (i["ano"], int(re.sub(r"\D", "", str(i["numero"] or "")) or 0)), reverse=True)

    falhas = 0
    with ThreadPoolExecutor(TRABALHADORES_SENADO) as ex:
        for f in as_completed([ex.submit(buscar, str(s["id"])) for s in senadores]):
            try:
                sid, itens = f.result()
                autorias[sid] = itens
            except Exception as e:
                falhas += 1
                if falhas <= 5:
                    avisar(f"autorias de senador: {e}")
    salvar(DADOS / "senado_autorias.json", autorias)
    print(f"Autorias de {len(autorias)} senadores, falhas: {falhas}")

    # situação atual das matérias que são projetos
    arquivo = DADOS / "senado_materias.json"
    cache = ler(arquivo, {})
    todos = {i["id"] for itens in autorias.values() for i in itens if i["tipo"] in TIPOS_PROJETO_SENADO}
    hoje = dt.date.today()
    limite_velho = (hoje - dt.timedelta(days=RENOVAR_APOS_DIAS)).isoformat()
    novos = sorted(todos - cache.keys(), reverse=True)
    velhos = sorted((i for i in todos & cache.keys() if not cache[i].get("fim") and cache[i].get("em", "") < limite_velho),
                    key=lambda i: cache[i].get("em", ""))
    fila = (novos + velhos)[:ORCAMENTO_MATERIAS]
    print(f"Matérias do Senado: {len(todos)} projetos, {len(novos)} novos, {len(velhos)} a renovar; consultando {len(fila)}")

    def detalhe(cod: str) -> tuple[str, dict]:
        d = get_senado(f"/materia/{cod}")
        sit = achar(d, "DescricaoSituacao")
        return cod, {
            "sit": sit, "org": achar(d, "SiglaLocal") or achar(d, "NomeLocal"),
            "data": str(achar(d, "DataSituacao") or achar(d, "DataLocal") or "")[:10] or None,
            "ap": str(achar(d, "DataApresentacao") or "")[:10] or None,
            "det": (achar(d, "ExplicacaoEmentaMateria") or "").strip() or None,
            "kw": (achar(d, "IndexacaoMateria") or "").strip() or None,
            "em": hoje.isoformat(), "fim": situacao_final(sit or ""),
        }

    feitos = falhas = 0
    with ThreadPoolExecutor(TRABALHADORES_SENADO) as ex:
        for f in as_completed([ex.submit(detalhe, i) for i in fila]):
            try:
                cod, info = f.result()
                cache[cod] = info
                feitos += 1
            except Exception as e:
                falhas += 1
                if falhas <= 5:
                    avisar(f"detalhe de matéria do Senado: {e}")
            if feitos and feitos % 500 == 0:
                salvar(arquivo, cache)
    salvar(arquivo, cache)
    print(f"Matérias do Senado salvas: {feitos}, falhas: {falhas}, no cache: {len(cache)}")


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
    if a.so in (None, "senado"):
        try:
            coletar_senado()
        except Exception as e:
            avisar(f"senado: {e}")
        for etapa in (coletar_votacoes_senado, coletar_autorias_senado, coletar_ceaps_senado):  # complementos: cada um falha sozinho
            try:
                etapa()
            except Exception as e:
                avisar(f"{etapa.__name__}: {e}")
    salvar(DADOS / "meta.json", {
        "atualizadoEm": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
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
