"""
Deputados estaduais do Rio Grande do Sul (ALRS), fora do SAPL.

Fontes abertas e lidas aqui:
  - lista de deputados: eleitos de 2022 do TSE (dados/tse/2022/RS.json); `www.al.rs.gov.br` não respondeu (timeout) nas tentativas;
  - diárias: CSV (ZIP) por ano do pacote "Diárias do Estado" do portal de dados abertos do Estado (CAGE),
    https://dados.rs.gov.br/dataset/diarias-do-estado ; o arquivo traz todos os órgãos, aqui só `Orgao` = Assembleia e
    favorecido que casa com o nome de um deputado (as diárias de assessores "a serviço de deputado" ficam de fora).
    O `Exercicio` do arquivo é o ano do pagamento: `diarias_<ano>.json` agrupa por esse ano.

Não coletado: a tela "Diárias Assembleia" (https://www.transparencia.rs.gov.br/relatorios/externo/diarias-assembleia/dados/) é um
painel Power BI embutido, sem dado na página; os CSV acima são os mesmos dados.
"""

import csv
import re
import sys
import zipfile
from datetime import date
from io import BytesIO, StringIO

import estaduais_comum as comum

UF = "RS"
TSE_ARQUIVO = comum.RAIZ / "dados" / "tse" / "2022" / "RS.json"
TSE_FICHA = "https://divulgacandcontas.tse.jus.br/divulga/#/candidato/2022/2040602022/RS/{}"
CKAN = "https://dados.rs.gov.br/api/3/action/package_show?id=diarias-do-estado"
PAGINA_DIARIAS = "https://dados.rs.gov.br/dataset/diarias-do-estado"
PRIMEIRO_ANO = 2023


def deputados_do_tse() -> list[dict]:
    lista = []
    for e in comum.ler(TSE_ARQUIVO, []):
        if e.get("cargo") != "DEPUTADO ESTADUAL" or e.get("situacao") != "eleito":
            continue
        lista.append({"id": e["sequencial"], "nome": e.get("urna") or e["nome"], "nomeCivil": e["nome"], "foto": None,
                      "email": e.get("email"), "titular": True, "partido": e.get("partido"), "fonte": TSE_FICHA.format(e["sequencial"])})
    return sorted(lista, key=lambda d: comum.sem_acento(d["nome"]))


def arquivos_por_ano(pacote: dict) -> dict:
    """{ano: url do ZIP} dos recursos "Diárias <ano>" do pacote CKAN."""
    achados = {}
    for r in pacote["result"]["resources"]:
        m = re.search(r"di.rias\s+(\d{4})", r.get("name") or "", re.I)
        if m and (r.get("url") or "").lower().endswith(".zip"):
            achados[int(m.group(1))] = r["url"]
    return achados


def linhas_da_assembleia(texto_csv: str) -> list[dict]:
    """Linhas do CSV cujo órgão é a Assembleia Legislativa."""
    leitor = csv.DictReader(StringIO(texto_csv), delimiter=";")
    return [l for l in leitor if (l.get("Orgao") or "").upper().startswith("ASSEMBLEIA")]


def data_iso(texto_data: str) -> str | None:
    m = re.fullmatch(r"\s*(\d\d)/(\d\d)/(\d{4})\s*", texto_data or "")
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None


def itens_diarias(linhas: list[dict], deputados: list[dict]) -> list[dict]:
    ligados = comum.ligar_nomes({l["Favorecido"] for l in linhas}, deputados)
    itens = []
    for l in linhas:
        if l["Favorecido"] not in ligados:
            continue
        itens.append({"idDeputado": ligados[l["Favorecido"]], "data": data_iso(l.get("DataInicio")), "dataFim": data_iso(l.get("DataFim")),
                      "destino": (l.get("Destino") or "").strip() or None, "motivo": (l.get("Motivo") or "").strip() or None,
                      "tipo": (l.get("Tipo") or "").strip() or None, "origem": (l.get("Origem") or "").strip() or None,
                      "empenho": (l.get("Empenho") or "").strip() or None, "valor": comum.valor_br(l.get("Valor")), "fonte": PAGINA_DIARIAS})
    itens.sort(key=lambda i: (i["data"] or "", i["idDeputado"]))
    return itens


def ler_zip_csv(conteudo: bytes) -> str:
    z = zipfile.ZipFile(BytesIO(conteudo))
    nome = next(n for n in z.namelist() if n.lower().endswith(".csv"))
    return z.read(nome).decode("cp1252", errors="replace")


def coletar() -> None:
    pasta = comum.DADOS / UF
    hoje = date.today().isoformat()
    deputados = deputados_do_tse()
    if not deputados:
        comum.avisar("RS: sem eleitos de 2022 em dados/tse/2022/RS.json")
        return
    comum.salvar(pasta / "deputados.json", {"fonte": "https://divulgacandcontas.tse.jus.br/divulga/#/home", "host": None, "legislatura": "2023-2027",
                                            "deputados": deputados})
    s = comum.sessao()
    r = s.get(CKAN, timeout=30)
    r.raise_for_status()
    for ano, url in sorted(arquivos_por_ano(r.json()).items()):
        if ano < PRIMEIRO_ANO or comum.ano_encerrado(ano, date.today(), pasta / f"diarias_{ano}.json"):
            continue
        resp = s.get(url, timeout=300)
        resp.raise_for_status()
        itens = itens_diarias(linhas_da_assembleia(ler_zip_csv(resp.content)), deputados)
        comum.salvar(pasta / f"diarias_{ano}.json", {"coletadoEm": hoje, "fonte": PAGINA_DIARIAS, "itens": itens})
        print(f"RS: diárias {ano} {len(itens)} registros")
    print(f"RS: {len(deputados)} deputados")


def _contrato_diarias(ctx):
    s = comum.sessao()
    r = s.get(CKAN, timeout=30)
    r.raise_for_status()
    ano = max(arquivos_por_ano(r.json()))
    resp = s.get(arquivos_por_ano(r.json())[ano], timeout=300)
    resp.raise_for_status()
    texto_csv = ler_zip_csv(resp.content)
    linhas = linhas_da_assembleia(texto_csv)
    cabecalho = texto_csv.split("\n", 1)[0].strip()
    amostra = [";".join(l.values()) for l in linhas[:6]]
    return {"ano": ano, "csv": "\n".join([cabecalho, *amostra])}


def _conferir_diarias(registro):
    falhas = []
    colunas = registro["csv"].split("\n", 1)[0].split(";")
    for c in ("Exercicio", "Orgao", "Favorecido", "DataInicio", "DataFim", "Destino", "Tipo", "Motivo", "Valor"):
        if c not in colunas:
            falhas.append(f"CSV de diárias sem a coluna {c}")
    linhas = linhas_da_assembleia(registro["csv"])
    if not linhas:
        falhas.append("nenhuma linha da Assembleia no CSV de diárias")
    for l in linhas:
        if not data_iso(l.get("DataInicio")) or comum.valor_br(l.get("Valor")) is None:
            falhas.append("diária sem data ou valor legível")
    return falhas, []


CONTRATOS = [
    dict(nome="estadual_rs_ckan", fonte=CKAN, buscar=lambda ctx: comum.sessao().get(CKAN, timeout=30).json(),
         usados=["result.resources[].name", "result.resources[].url"]),
    dict(nome="estadual_rs_diarias", fonte=PAGINA_DIARIAS, buscar=_contrato_diarias, html=_conferir_diarias),
]


if __name__ == "__main__":
    coletar()
    sys.exit(0)
