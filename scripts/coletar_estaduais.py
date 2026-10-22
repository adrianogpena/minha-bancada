"""
Coleta votos nominais e projetos dos deputados estaduais das Assembleias que
usam o SAPL (sistema do Interlegis), cuja API REST em JSON é aberta e igual
em todas. Guarda o cache bruto em dados/estaduais/<UF>/ (vai para o git, o
histórico cresce aos poucos).

Uso:
    python scripts/coletar_estaduais.py              # todas as Assembleias configuradas
    python scripts/coletar_estaduais.py PB AM        # só algumas
"""

import datetime as dt
import json
import re
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "dados" / "estaduais"

# UF -> host do SAPL. Assembleias com votos nominais ou autoria abertos, verificadas em 2026-10.
ASSEMBLEIAS = {
    "PB": "sapl.al.pb.leg.br",
    "AM": "sapl.al.am.leg.br",
    "AL": "sapl.al.al.leg.br",   # confirmado: documentos públicos servidos por esse host
    "RO": "sapl.al.ro.leg.br",   # a Assembleia usa SAPL, mas o host é o padrão dos outros: se falhar, só avisa
    "AC": "sapl.al.ac.leg.br",
    "PI": "sapl.al.pi.leg.br",
    "TO": "sapl.al.to.leg.br",
}
TRABALHADORES = 4
UFS_EM_PARALELO = 4  # Assembleias e Câmaras são servidores diferentes, então dá para coletar várias ao mesmo tempo
RENOVAR_ANO_ANTIGO_DIAS = 7   # projetos de anos anteriores são consultados de novo só de vez em quando
# só projetos de verdade; requerimentos e indicações são milhares por ano e pesariam no repositório
TIPO_PROJETO = re.compile(r"^(projeto|proposta de emenda|medida provis)", re.I)


def sessao() -> requests.Session:
    s = requests.Session()
    s.headers.update({"Accept": "application/json",
                      "User-Agent": "Mozilla/5.0 (compatible; minha-bancada; projeto de transparencia)"})
    retry = Retry(total=5, backoff_factor=2, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=("GET",))
    s.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=TRABALHADORES * 2))
    return s


S = sessao()


def avisar(msg: str) -> None:
    print(f"AVISO: {msg}", file=sys.stderr)


def ler(caminho: Path, padrao=None):
    if caminho.exists():
        return json.loads(caminho.read_text(encoding="utf-8"))
    return padrao


def salvar(caminho: Path, obj) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True), encoding="utf-8")


def get(host: str, caminho: str, **params) -> dict:
    r = S.get(f"https://{host}/api/{caminho.strip('/')}/", params=params or None, timeout=90)
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status_code} em {r.url}")
    return r.json()


def paginar(host: str, caminho: str, **params):
    """Percorre todas as páginas de uma listagem do SAPL."""
    pagina = 1
    while pagina:
        d = get(host, caminho, page=pagina, page_size=100, **params)
        yield from d["results"]
        pagina = d["pagination"]["next_page"]


def https(url: str | None) -> str | None:
    return url.replace("http://", "https://", 1) if url else None


def data_curta(texto: str | None) -> str | None:
    return texto[:10] if texto else None


def sem_acento(s: str) -> str:
    n = unicodedata.normalize("NFD", (s or "").lower())
    return " ".join("".join(c for c in n if unicodedata.category(c) != "Mn").split())


# ---------------------------------------------------------------- por Assembleia
def legislatura_atual(host: str) -> dict:
    hoje = dt.date.today().isoformat()
    for l in get(host, "parlamentares/legislatura", page_size=10)["results"]:
        if l["data_inicio"] <= hoje <= l["data_fim"]:
            return l
    raise RuntimeError("legislatura atual não encontrada")


def coletar_deputados(host: str, leg: dict) -> list[dict]:
    """Deputados com mandato em vigor hoje (titulares e suplentes em exercício)."""
    hoje = dt.date.today().isoformat()
    ids = {}
    for m in paginar(host, "parlamentares/mandato", legislatura=leg["id"]):
        ini, fim = m.get("data_inicio_mandato") or "0000", m.get("data_fim_mandato") or "9999"
        if ini <= hoje <= fim:
            ids[m["parlamentar"]] = m
    deputados = []
    for pid in sorted(ids):
        try:
            p = get(host, f"parlamentares/parlamentar/{pid}")
        except Exception as e:
            avisar(f"{host}: parlamentar {pid}: {e}")
            continue
        deputados.append({"id": pid, "nome": p.get("nome_parlamentar"), "nomeCivil": p.get("nome_completo"),
                          "foto": https(p.get("fotografia")), "email": p.get("email") or None,
                          "titular": ids[pid].get("titular")})
    return deputados


def mapa_autores(host: str, deputados: dict) -> dict:
    """id de autor -> id do deputado (só autores que são parlamentares em exercício)."""
    tipo_parlamentar = {t["id"] for t in paginar(host, "base/tipoautor") if t["descricao"].strip().lower() == "parlamentar"}
    mapa = {}
    for a in paginar(host, "base/autor"):
        if a["tipo"] in tipo_parlamentar and a.get("object_id") in deputados:
            mapa[a["id"]] = a["object_id"]
    return mapa


def tipos_materia(host: str) -> dict:
    return {t["id"]: {"sigla": t["sigla"], "descricao": t["descricao"]} for t in paginar(host, "materia/tipomaterialegislativa")}


def situacao(m: dict) -> str:
    if m.get("em_tramitacao"):
        return "Em tramitação"
    return (m.get("resultado") or "").strip() or "Tramitação encerrada"


def compactar_materia(m: dict, tipos: dict) -> dict:
    t = tipos.get(m["tipo"], {"sigla": "?", "descricao": "?"})
    return {"tipo": t["sigla"], "tipoDescricao": t["descricao"], "numero": m["numero"], "ano": m["ano"],
            "dataApresentacao": m.get("data_apresentacao"), "ementa": (m.get("ementa") or "").strip(),
            "situacao": situacao(m), "emTramitacao": bool(m.get("em_tramitacao")),
            "linkTexto": https(m.get("texto_original")) or None, "idsAutores": m.get("autores") or []}


def coletar_materias(host: str, uf: str, leg: dict, autores: dict, tipos: dict) -> None:
    """Projetos da legislatura atual de que algum deputado em exercício é autor."""
    pasta = DADOS / uf
    hoje = dt.date.today()
    for ano in range(int(leg["data_inicio"][:4]), hoje.year + 1):
        arq = pasta / f"materias_{ano}.json"
        antigo = ler(arq)
        if antigo and ano < hoje.year and (hoje - dt.date.fromisoformat(antigo["coletadoEm"])).days < RENOVAR_ANO_ANTIGO_DIAS:
            continue
        itens = {}
        for tid, t in tipos.items():
            if not TIPO_PROJETO.match(t["descricao"]):
                continue
            for m in paginar(host, "materia/materialegislativa", ano=ano, tipo=tid):
                deps = sorted({autores[a] for a in (m.get("autores") or []) if a in autores})
                if deps:
                    itens[str(m["id"])] = {**compactar_materia(m, tipos), "idsDeputados": deps}
        salvar(arq, {"coletadoEm": hoje.isoformat(), "materias": itens})
        print(f"  {uf} projetos {ano}: {len(itens)}")


def resultado_aprovado(nome: str, natureza: str) -> int | None:
    if re.search(r"n[ãa]o votad|retirad", sem_acento(nome)):
        return None
    return 1 if natureza == "A" else 0 if natureza == "R" else None


def coletar_votacoes(host: str, uf: str, leg: dict, deputados: dict) -> None:
    """Votações com voto nominal desde o início da legislatura. A cada execução
    refaz só as últimas semanas; o resto vem do cache."""
    pasta = DADOS / uf
    resultados = {r["id"]: (r["nome"], r["natureza"]) for r in paginar(host, "sessao/tiporesultadovotacao")}
    cache = ler(pasta / "votacoes.json", {"votacoes": {}})["votacoes"]
    desde = leg["data_inicio"]
    if cache:
        ultima = max(v["data"] for v in cache.values())
        desde = max(desde, (dt.date.fromisoformat(ultima) - dt.timedelta(days=14)).isoformat())

    votos = {}
    for v in paginar(host, "sessao/votoparlamentar", data_hora__gte=desde):
        if v["parlamentar"] in deputados and v.get("voto"):
            votos.setdefault(v["votacao"], []).append([v["parlamentar"], v["voto"]])
    novas = {}
    for vid, lista in votos.items():
        try:
            r = get(host, f"sessao/registrovotacao/{vid}")
        except Exception as e:
            avisar(f"{uf}: votação {vid}: {e}")
            continue
        nome, nat = resultados.get(r["tipo_resultado_votacao"], ("", ""))
        novas[str(vid)] = {"data": data_curta(r["data_hora"]), "idMateria": r["materia"], "aprovada": resultado_aprovado(nome, nat),
                           "resultado": nome, "sim": r["numero_votos_sim"], "nao": r["numero_votos_nao"],
                           "abstencoes": r["numero_abstencoes"], "votos": lista}
    cache.update({k: v for k, v in novas.items() if v["data"]})
    salvar(pasta / "votacoes.json", {"votacoes": cache})
    print(f"  {uf} votações nominais: {len(cache)} ({len(novas)} atualizadas)")


def coletar_materias_votadas(host: str, uf: str, tipos: dict) -> None:
    """Descrição das matérias votadas (nem todas são de autoria de deputados)."""
    pasta = DADOS / uf
    votacoes = ler(pasta / "votacoes.json", {"votacoes": {}})["votacoes"]
    cache = ler(pasta / "materias_votadas.json", {})
    faltam = sorted({str(v["idMateria"]) for v in votacoes.values() if v["idMateria"]} - set(cache))

    def buscar(mid):
        return mid, compactar_materia(get(host, f"materia/materialegislativa/{mid}"), tipos)

    with ThreadPoolExecutor(TRABALHADORES) as ex:
        for f in as_completed([ex.submit(buscar, m) for m in faltam]):
            try:
                mid, m = f.result()
                cache[mid] = {k: m[k] for k in ("tipo", "tipoDescricao", "numero", "ano", "ementa")}
            except Exception as e:
                avisar(f"{uf}: matéria votada: {e}")
    salvar(pasta / "materias_votadas.json", cache)
    print(f"  {uf} matérias votadas: {len(cache)} ({len(faltam)} novas)")


def coletar_assembleia(uf: str, host: str) -> None:
    print(f"{uf} ({host})")
    leg = legislatura_atual(host)
    deputados = coletar_deputados(host, leg)
    if not deputados:
        raise RuntimeError("nenhum deputado em exercício")
    por_id = {d["id"]: d for d in deputados}
    tipos = tipos_materia(host)
    salvar(DADOS / uf / "deputados.json", {"host": host, "legislatura": leg["numero"], "deputados": deputados})
    print(f"  {uf} deputados em exercício: {len(deputados)}")
    autores = mapa_autores(host, por_id)
    for etapa in (lambda: coletar_materias(host, uf, leg, autores, tipos),
                  lambda: coletar_votacoes(host, uf, leg, por_id),
                  lambda: coletar_materias_votadas(host, uf, tipos)):
        try:
            etapa()
        except Exception as e:  # cada parte falha sozinha, sem derrubar as outras
            avisar(f"{uf}: {e}")


def em_paralelo(ufs: list[str], coletar, rotulo: str = "") -> None:
    """Roda `coletar(uf)` para cada UF, várias ao mesmo tempo; a falha de uma UF vira aviso e não derruba as outras."""
    def uma(uf):
        try:
            coletar(uf)
        except Exception as e:
            avisar(f"{uf}: {rotulo + ': ' if rotulo else ''}{e}")

    with ThreadPoolExecutor(UFS_EM_PARALELO) as ex:
        list(ex.map(uma, ufs))


def main() -> None:
    alvo = [a.upper() for a in sys.argv[1:]] or list(ASSEMBLEIAS)
    em_paralelo(alvo, lambda uf: coletar_assembleia(uf, ASSEMBLEIAS[uf]))


if __name__ == "__main__":
    main()
