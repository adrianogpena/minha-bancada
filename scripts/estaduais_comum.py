"""
Base comum dos coletores de deputados estaduais (um módulo `coletar_estadual_<uf>.py` por UF fora do SAPL).

Cada módulo de UF expõe:
    UF = "GO"
    def coletar() -> None            # grava em dados/estaduais/<UF>/
    CONTRATOS = [dict(nome="estadual_go_x", fonte="https://...", buscar=fn(ctx), usados=["a.b"], html=None)]
        (opcional; sem importar `contrato_apis`; os endpoints são independentes entre si, sem usar o `ctx`
        de outros; `--gravar estadual_go_x` grava tests/fixtures/contratos/estadual_go_x.json)

`coletar_estaduais.py` descobre esses módulos por glob; `python scripts/coletar_estaduais.py GO` roda só GO.

CONTRATO DOS ARQUIVOS em dados/estaduais/<UF>/ (JSON compacto; campo desconhecido vira null;
todo `fonte` é a URL que a pessoa abre para conferir o dado):

  deputados.json  {fonte, host, legislatura, deputados:[{id, nome, nomeCivil, foto, email, titular, partido?, fonte?}]}
      `host` é null fora do SAPL; `fonte` é a URL da lista; `partido` e `fonte` por deputado são opcionais.
  materias_<ano>.json  {coletadoEm, fonte, materias:{id:{tipo, tipoDescricao, numero, ano, dataApresentacao, ementa,
      situacao, emTramitacao, linkTexto, idsAutores, idsDeputados, fonte}}}
  votacoes.json  {fonte, votacoes:{id:{data, idMateria, aprovada, resultado, sim, nao, abstencoes,
      votos:[[idDeputado, voto]], fonte}}}
  materias_votadas.json  {idMateria:{tipo, tipoDescricao, numero, ano, ementa}}

  Opcionais, todos com `coletadoEm` e `fonte` no topo e `fonte` por item:
  verbas_<ano>.json  {coletadoEm, fonte, itens:[{idDeputado, mes, categoria, fornecedor, cnpj, valor, fonte}]}
      verba indenizatória / cota parlamentar; mes de 1 a 12; valor em reais (float).
  remuneracao_<ano>.json  {coletadoEm, fonte, itens:[{idDeputado, mes, bruto, liquido, componentes:{nome:valor}, fonte}]}
  presenca.json  {coletadoEm, fonte, itens:[{idDeputado, periodo ("2026" ou "2026-10"), presente, ausente, licenca,
      totalSessoes, fonte}]}
  diarias_<ano>.json  {coletadoEm, fonte, itens:[{idDeputado, data (AAAA-MM-DD), destino, motivo, valor, fonte}]}
  emendas_<ano>.json  {coletadoEm, fonte, itens:[{idDeputado, ano, objeto, orgao, empenhado, pago, fonte}]}

Helpers: `sessao`, `ler`, `salvar`, `avisar`, `sem_acento`, `nome_limpo`, `valor_br`, `mes_numero`, `ligar_nomes`,
`meses_recentes`, `ano_encerrado`.
"""

import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "dados" / "estaduais"
CONEXOES_POR_HOST = 2
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

TIMEOUT_PADRAO = 30   # segundos por requisição quando o coletor não define o seu
TIMEOUT_CONEXAO = 15  # teto para abrir a conexão; o timeout do coletor vale para a leitura
# Tempo total de coleta do processo, em minutos (variável ESTADUAIS_PRAZO_MIN; vazio = sem prazo). Esgotado, toda nova
# requisição levanta PrazoEsgotado: cada etapa vira aviso, o que já foi gravado fica e o job termina no prazo, sem ser morto.
PRAZO_FIM = time.monotonic() + float(os.environ["ESTADUAIS_PRAZO_MIN"]) * 60 if os.environ.get("ESTADUAIS_PRAZO_MIN") else None

MESES = {"janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
         "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}
_PREFIXO_DEP = re.compile(r"^\s*(deputad[oa]\s*\(a\)|deputad[oa]|dep\.?)\s+", re.I)


class PrazoEsgotado(RuntimeError):
    pass


def checar_prazo() -> None:
    if PRAZO_FIM is not None and time.monotonic() > PRAZO_FIM:
        raise PrazoEsgotado("prazo de coleta esgotado")


class _Sessao(requests.Session):
    # Host que não aceitou conexão (ConnectTimeout depois das tentativas) fica fora do ar até o fim da coleta: as
    # requisições seguintes a ele falham na hora, em vez de esperar timeout e tentativas de novo (PE: 21 min perdidos).
    def __init__(self):
        super().__init__()
        self.fora_do_ar = set()

    def request(self, method, url, *args, **kwargs):
        checar_prazo()
        host = urlsplit(url).hostname
        if host in self.fora_do_ar:
            raise requests.ConnectTimeout(f"{host} não aceitou conexão antes nesta coleta")
        t = kwargs.get("timeout", TIMEOUT_PADRAO)
        kwargs["timeout"] = (min(TIMEOUT_CONEXAO, t), t) if isinstance(t, (int, float)) else t
        try:
            return super().request(method, url, *args, **kwargs)
        except requests.ConnectTimeout:
            self.fora_do_ar.add(host)
            raise


def sessao() -> requests.Session:
    s = _Sessao()
    s.headers.update({"User-Agent": USER_AGENT, "Accept": "*/*"})
    retry = Retry(total=3, backoff_factor=2, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=("GET",))
    adaptador = HTTPAdapter(max_retries=retry, pool_connections=CONEXOES_POR_HOST, pool_maxsize=CONEXOES_POR_HOST, pool_block=True)
    s.mount("https://", adaptador)
    s.mount("http://", adaptador)
    return s


def avisar(msg: str) -> None:
    print(f"AVISO: {msg}", file=sys.stderr)


def ler(caminho: Path, padrao=None):
    if caminho.exists():
        return json.loads(caminho.read_text(encoding="utf-8"))
    return padrao


def salvar(caminho: Path, obj) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True), encoding="utf-8")


def sem_acento(s: str) -> str:
    n = unicodedata.normalize("NFD", (s or "").lower())
    return " ".join("".join(c for c in n if unicodedata.category(c) != "Mn").split())


def nome_limpo(nome: str) -> str:
    """Tira o prefixo "DEP ", "DEP. " ou "DEPUTADO(A) " do nome."""
    return " ".join(_PREFIXO_DEP.sub("", nome or "").split())


def valor_br(texto) -> float | None:
    """"4.000,00", "R$ 99,90" e "31310.41" viram float; vazio ou ilegível vira None."""
    if texto is None:
        return None
    if isinstance(texto, (int, float)):
        return float(texto)
    t = re.sub(r"[^\d,.\-]", "", str(texto))
    if not re.search(r"\d", t):
        return None
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    elif t.count(".") > 1:
        t = t.replace(".", "")
    try:
        return float(t)
    except ValueError:
        return None


def mes_numero(nome) -> int | None:
    """"janeiro" (ou "Março", "mar") -> 1; já numérico devolve o número."""
    t = sem_acento(str(nome)).strip(" ./")
    if t.isdigit():
        n = int(t)
        return n if 1 <= n <= 12 else None
    if len(t) < 3:
        return None
    for m, n in MESES.items():
        if m == t or (len(t) == 3 and m.startswith(t)):
            return n
    return None


def meses_recentes(hoje, quantos: int) -> set:
    """{(ano, mes)} dos `quantos` meses até o de `hoje`, inclusive: os que a coleta diária relê (o resto vem do arquivo anterior)."""
    achados, ano, mes = set(), hoje.year, hoje.month
    for _ in range(quantos):
        achados.add((ano, mes))
        ano, mes = (ano - 1, 12) if mes == 1 else (ano, mes - 1)
    return achados


def ano_encerrado(ano: int, hoje, arquivo: Path) -> bool:
    """Ano anterior ao passado com arquivo já gravado: não muda mais e não é baixado de novo."""
    return ano < hoje.year - 1 and arquivo.exists()


def ligar_nomes(nomes_fonte, deputados: list[dict]) -> dict:
    """{nome como veio da fonte: id do deputado}, comparando sem acento, maiúsculas e prefixo "DEP".
    Tenta `nome` e depois `nomeCivil`; nome ambíguo ou sem par fica de fora."""
    por_nome: dict[str, set] = {}
    for campo in ("nome", "nomeCivil"):
        for d in deputados:
            if d.get(campo):
                por_nome.setdefault(sem_acento(d[campo]), set()).add(d["id"])
    ligados = {}
    for n in nomes_fonte:
        ids = por_nome.get(sem_acento(nome_limpo(n)), set())
        if len(ids) == 1:
            ligados[n] = next(iter(ids))
    return ligados
