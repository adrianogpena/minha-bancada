"""
Base comum dos coletores de deputados estaduais (um módulo `coletar_estadual_<uf>.py` por UF fora do SAPL).

Cada módulo de UF expõe:
    UF = "GO"
    def coletar() -> None            # grava em dados/estaduais/<UF>/
    CONTRATOS = [{"nome": "estadual_go_x", "fonte": "https://...", "buscar": fn(ctx), "usados": ["a.b"], "html": None}]
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

  ligacoes.json  {nomes:{nome da fonte:[id, método, confiança]}, ambiguos:{nome:[ids]}, semPar:[nomes]}
      gravado por `identidades.gravar_ligacoes` depois da coleta; o coletor só chama `identidades.ligar_nomes(nomes, deputados, UF)`.

  Opcionais, todos com `coletadoEm` e `fonte` no topo e `fonte` por item:
  verbas_<ano>.json  {coletadoEm, fonte, itens:[{idDeputado, mes, categoria, fornecedor, cnpj, valor, fonte}]}
      verba indenizatória / cota parlamentar; mes de 1 a 12; valor em reais (float).
  remuneracao_<ano>.json  {coletadoEm, fonte, itens:[{idDeputado, mes, bruto, liquido, componentes:{nome:valor}, fonte}]}
  presenca.json  {coletadoEm, fonte, itens:[{idDeputado, periodo ("2026" ou "2026-10"), presente, ausente, licenca,
      totalSessoes, fonte}]}
  diarias_<ano>.json  {coletadoEm, fonte, itens:[{idDeputado, data (AAAA-MM-DD), destino, motivo, valor, fonte}]}
  emendas_<ano>.json  {coletadoEm, fonte, itens:[{idDeputado, ano, objeto, orgao, empenhado, pago, fonte}]}

Helpers: `sessao`, `get`, `baixar`, `ler`, `salvar`, `avisar`, `sem_acento`, `nome_limpo`, `limpar`, `compactar`, `valor_br`,
`mes_numero`, `data_br_iso`, `palavras`, `meses_recentes`, `ano_encerrado`,
`arquivo_tse`, `ficha_tse`, `eleitos_tse`, `deputados_do_tse` (eleitos de 2022 do TSE como lista de deputados),
`xlsx_linhas` e `xlsx_abas` (XLSX só com biblioteca padrão), `contrato_json`, `campos_vazios`, `faltando`, `tentar`, `rodar_etapas`, `principal`.
"""

import io
import json
import os
import re
import sys
import time
import unicodedata
import zipfile
from html import unescape
from pathlib import Path
from urllib.parse import urlsplit

import requests
from defusedxml import ElementTree
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
NS_XLSX = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
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


def get(s, url: str, timeout: int = TIMEOUT_PADRAO, **kw):
    """GET que levanta em erro HTTP; `kw` vai para `requests` (params, headers)."""
    r = s.get(url, timeout=timeout, **kw)
    r.raise_for_status()
    return r


def baixar(s, url: str, params: dict | None = None, timeout: int = TIMEOUT_PADRAO) -> bytes:
    return get(s, url, timeout, **({"params": params} if params else {})).content


def contrato_json(url: str, timeout: int = 30):
    """`buscar` de contrato para uma API JSON simples."""
    return sessao().get(url, timeout=timeout).json()


def tentar(uf: str, rotulo: str, fn) -> None:
    """Roda uma etapa da coleta; se falhar, só avisa, para não derrubar as outras."""
    try:
        fn()
    except Exception as e:  # noqa: BLE001
        avisar(f"{uf}: {rotulo}: {e}")


def rodar_etapas(uf: str, etapas) -> None:
    """`etapas`: [(rótulo, função sem argumentos)], cada uma isolada por `tentar`."""
    for rotulo, fn in etapas:
        tentar(uf, rotulo, fn)


def principal(coletar) -> None:
    """Rodapé dos módulos de UF: `if __name__ == "__main__": comum.principal(coletar)`."""
    import identidades   # aqui dentro: identidades importa este módulo

    coletar()
    identidades.gravar_ligacoes()
    sys.exit(0)


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


def limpar(html: str | None) -> str:
    """Texto de um trecho de HTML: sem tags, entidades resolvidas e espaços compactados."""
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", html or "")).split())


def compactar(texto) -> str | None:
    """Espaços compactados; vazio vira None."""
    return " ".join((texto or "").split()) or None


def data_br_iso(texto: str | None, inteiro: bool = False) -> str | None:
    """"31/12/2024" (com espaços nas pontas) -> "2024-12-31". `inteiro`: recusa texto depois da data (hora)."""
    padrao = r"\s*(\d\d)/(\d\d)/(\d{4})" + (r"\s*" if inteiro else "")
    m = (re.fullmatch if inteiro else re.match)(padrao, texto or "")
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None


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


def palavras(nome: str, ignorar=()) -> list[str]:
    """Palavras do nome sem acento, só letras, na ordem e sem as de `ignorar`."""
    return [t for t in re.sub(r"[^a-z ]", " ", sem_acento(nome)).split() if t not in ignorar]


def campos_vazios(obj, campos, rotulo: str, vazios=None) -> list[str]:
    """Falhas de contrato "<rotulo> sem <campo>" para cada campo de `obj` vazio; `vazios` lista os valores que contam como
    vazio (padrão: qualquer valor falso)."""
    return [f"{rotulo} sem {c}" for c in campos if (not obj.get(c) if vazios is None else obj.get(c) in vazios)]


def faltando(presentes, esperadas, rotulo: str) -> list[str]:
    """Falhas de contrato "<rotulo> sem a coluna X" para cada coluna esperada que não está em `presentes`."""
    return [f"{rotulo} sem a coluna {c}" for c in esperadas if c not in presentes]


def arquivo_tse(uf: str) -> Path:
    return RAIZ / "dados" / "tse" / "2022" / f"{uf}.json"


def ficha_tse(uf: str) -> str:
    return f"https://divulgacandcontas.tse.jus.br/divulga/#/candidato/2022/2040602022/{uf}/{{}}"


def eleitos_tse(arquivo: Path) -> list[dict]:
    """Candidatos eleitos a deputado estadual em 2022 (dados/tse/2022/<UF>.json)."""
    return [e for e in ler(arquivo, []) if e.get("cargo") == "DEPUTADO ESTADUAL" and e.get("situacao") == "eleito"]


def deputados_do_tse(arquivo: Path, ficha: str) -> list[dict]:
    """Eleitos de 2022 no formato de deputados.json, em ordem alfabética; `ficha` é a URL com `{}` para o sequencial."""
    lista = [{"id": e["sequencial"], "nome": e.get("urna") or e["nome"], "nomeCivil": e["nome"], "foto": None, "email": e.get("email"),
              "titular": True, "partido": e.get("partido"), "fonte": ficha.format(e["sequencial"])} for e in eleitos_tse(arquivo)]
    return sorted(lista, key=lambda d: sem_acento(d["nome"]))


def _celulas_xlsx(z: zipfile.ZipFile, caminho: str, textos: list[str]) -> list[dict]:
    linhas = []
    for row in ElementTree.fromstring(z.read(caminho)).iter(f"{{{NS_XLSX['m']}}}row"):
        celulas = {}
        for c in row.findall("m:c", NS_XLSX):
            v = c.find("m:v", NS_XLSX)
            if v is None or v.text is None:
                continue
            celulas[re.match(r"[A-Z]+", c.get("r")).group(0)] = textos[int(v.text)] if c.get("t") == "s" else v.text
        if celulas:
            linhas.append(celulas)
    return linhas


def _textos_xlsx(z: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    raiz = ElementTree.fromstring(z.read("xl/sharedStrings.xml"))
    return ["".join(t.text or "" for t in si.iter(f"{{{NS_XLSX['m']}}}t")) for si in raiz.findall("m:si", NS_XLSX)]


def xlsx_linhas(conteudo: bytes, aparar: bool = True) -> list[dict]:
    """Primeira planilha como lista de linhas {coluna (A, B...): texto}. `aparar`: tira espaços e descarta células vazias."""
    z = zipfile.ZipFile(io.BytesIO(conteudo))
    linhas = _celulas_xlsx(z, "xl/worksheets/sheet1.xml", _textos_xlsx(z))
    if not aparar:
        return linhas
    aparadas = ({c: v.strip() for c, v in linha.items() if v.strip()} for linha in linhas)
    return [linha for linha in aparadas if linha]


def xlsx_abas(conteudo: bytes) -> dict[str, list[dict]]:
    """{nome da aba: linhas {coluna: texto}}."""
    z = zipfile.ZipFile(io.BytesIO(conteudo))
    textos = _textos_xlsx(z)
    rels = {r.get("Id"): r.get("Target") for r in ElementTree.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
    abas = {}
    for aba in ElementTree.fromstring(z.read("xl/workbook.xml")).find("m:sheets", NS_XLSX):
        alvo = rels[aba.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")].lstrip("/")
        abas[aba.get("name")] = _celulas_xlsx(z, alvo if alvo.startswith("xl/") else f"xl/{alvo}", textos)
    return abas
