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
    return {
        "id": votacao["id"],
        "data": votacao.get("data") or (votacao.get("dataHoraRegistro") or "")[:10],
        "hora": (votacao.get("dataHoraRegistro") or "")[11:16],
        "orgao": votacao.get("siglaOrgao"),
        "descricao": (votacao.get("descricao") or "").strip(),
        "proposicao": votacao.get("proposicaoObjeto"),
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
    p.add_argument("--so", choices=["deputados", "votacoes"], help="coletar só uma parte")
    a = p.parse_args()
    if a.so in (None, "deputados"):
        coletar_deputados(a.limite)
    if a.so in (None, "votacoes"):
        coletar_votacoes(a.dias)
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
