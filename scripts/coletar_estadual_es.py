"""
Deputados estaduais do Espírito Santo (ALES), fora do SAPL.

Fontes abertas e lidas aqui:
  - lista de deputados: eleitos de 2022 do TSE (dados/tse/2022/ES.json); `www.al.es.gov.br` não respondeu (timeout) nas tentativas;
  - cota parlamentar e diárias: CSV anual "Despesas-<ano>.csv" do Portal da Transparência do Estado no CKAN
    (https://dados.es.gov.br/dataset/portal-da-transparencia-despesas-execucao-orcamentaria-e-financeira), com a despesa de
    todos os órgãos; aqui só `UnidadeGestora` = Assembleia Legislativa e favorecido que casa com o nome de um deputado.
    Cada linha é um documento (empenho NE, liquidação NL, pagamento OB): só o valor pago (`ValorPago`, das OB) entra, para
    não somar o mesmo gasto três vezes. Estornos vêm como linha negativa e entram no total.
    Cota: `SubelementoDespesa` "Reembolso de Despesas - Cotas Parlamentares..." (ATO 3879/2024); sem categoria nem fornecedor;
    `mes` é o do pagamento e `referencia` o mês citado no histórico ("COTA PARLAMENTAR DO MÊS DE JUNHO").
    Diárias: `ElementoDespesa` "DIÁRIAS - CIVIL"; destino e motivo só no texto do histórico (guardado em `motivo`).

Os arquivos têm 1,2 a 1,5 GB e saem da fonte a ~1 MB/s (um ano levou 23 min daqui): são lidos em streaming, sem guardar o CSV,
do ano mais novo para o mais velho. Um ano só é baixado de novo quando o `last_modified` do recurso no CKAN muda
(`recursoModificadoEm` no arquivo). Se o prazo do job acabar no meio, o que já foi lido fica em `parcial_<ano>.json`
(posição em bytes e linhas úteis) e a coleta seguinte continua dali com `Range`, se o recurso não tiver mudado.
Anos anteriores ao passado com arquivo não são baixados de novo (`comum.ano_encerrado`); o ano passado é lido de novo até
março (pagamentos atrasados) e depois fica.

Não coletado: folha, presença, proposições e votações (não estão no portal do Estado; `www.al.es.gov.br` não responde).
"""

import csv
import re
import sys
from datetime import date

import estaduais_comum as comum

UF = "ES"
TSE_ARQUIVO = comum.RAIZ / "dados" / "tse" / "2022" / "ES.json"
TSE_FICHA = "https://divulgacandcontas.tse.jus.br/divulga/#/candidato/2022/2040602022/ES/{}"
PACOTE = "portal-da-transparencia-despesas-execucao-orcamentaria-e-financeira"
CKAN = f"https://dados.es.gov.br/api/3/action/package_show?id={PACOTE}"
PAGINA = f"https://dados.es.gov.br/dataset/{PACOTE}"
PRIMEIRO_ANO = 2023
MES_FECHA_ANO_ANTERIOR = 3  # a partir deste mês o arquivo do ano passado, se já lido no ano corrente, não é baixado de novo
BLOCO = 1 << 20
_MARCA = b"ASSEMBLEIA LEGISLATIVA"
CAMPOS = ("Data", "ValorPago", "Favorecido", "Documento", "HistoricoDocumento", "UnidadeGestora", "ElementoDespesa", "SubelementoDespesa")


def deputados_do_tse() -> list[dict]:
    lista = []
    for e in comum.ler(TSE_ARQUIVO, []):
        if e.get("cargo") != "DEPUTADO ESTADUAL" or e.get("situacao") != "eleito":
            continue
        lista.append({"id": e["sequencial"], "nome": e.get("urna") or e["nome"], "nomeCivil": e["nome"], "foto": None,
                      "email": e.get("email"), "titular": True, "partido": e.get("partido"), "fonte": TSE_FICHA.format(e["sequencial"])})
    return sorted(lista, key=lambda d: comum.sem_acento(d["nome"]))


def arquivos_por_ano(pacote: dict) -> dict:
    """{ano: {url, modificadoEm}} dos recursos "Despesas-<ano>.csv" do pacote (os semestrais e repetidos ficam de fora)."""
    achados = {}
    for r in pacote["result"]["resources"]:
        m = re.fullmatch(r"despesas-(\d{4})\.csv", (r.get("name") or "").strip(), re.I)
        if m and r.get("url"):
            achados.setdefault(int(m.group(1)), {"url": r["url"], "modificadoEm": r.get("last_modified")})
    return achados


def cabecalho_csv(linha: bytes) -> list[str]:
    return next(csv.reader([linha.decode("utf-8-sig")], delimiter=";"))


def linha_da_assembleia(bruta: bytes, cabecalho: list[str]) -> dict | None:
    """A linha como dict se a unidade gestora é a Assembleia Legislativa; senão None."""
    if _MARCA not in bruta:
        return None
    campos = next(csv.reader([bruta.decode("utf-8", errors="replace")], delimiter=";"), [])
    if len(campos) != len(cabecalho):
        return None
    l = dict(zip(cabecalho, campos))
    return l if (l.get("UnidadeGestora") or "").strip().upper().startswith("ASSEMBLEIA LEGISLATIVA") else None


def linhas_da_assembleia(linhas) -> list[dict]:
    """Linhas (bytes ou str, a primeira é o cabeçalho) cuja unidade gestora é a Assembleia Legislativa."""
    cabecalho, achadas = None, []
    for linha in linhas:
        bruta = linha if isinstance(linha, bytes) else linha.encode("utf-8")
        if cabecalho is None:
            cabecalho = cabecalho_csv(bruta)
        elif (l := linha_da_assembleia(bruta, cabecalho)) is not None:
            achadas.append(l)
    return achadas


def e_cota(l: dict) -> bool:
    return "cotas parlamentares" in comum.sem_acento(l.get("SubelementoDespesa"))


def e_diaria(l: dict) -> bool:
    return comum.sem_acento(l.get("ElementoDespesa")).startswith("diaria")


def data_iso(texto: str) -> str | None:
    m = re.match(r"\s*(\d\d)/(\d\d)/(\d{4})", texto or "")
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None


def referencia(historico: str, pago_em: str | None) -> str | None:
    """"AAAA-MM" do mês citado no histórico; mês depois do pagamento é do ano anterior (cota de dezembro paga em janeiro)."""
    m = re.search(r"\bmes de ([a-z]+)", comum.sem_acento(historico))
    mes = comum.mes_numero(m.group(1)) if m else None
    if not mes or not pago_em:
        return None
    ano = int(pago_em[:4]) - (1 if mes > int(pago_em[5:7]) else 0)
    return f"{ano}-{mes:02d}"


def periodo(historico: str) -> tuple:
    """(início, fim) em AAAA-MM-DD do trecho "PERÍODO DE 02/07/2026 a 03/07/2026" do histórico."""
    m = re.search(r"(\d\d/\d\d/\d{4})\s*(?:a|à|ate|até)\s*(\d\d/\d\d/\d{4})", historico or "", re.I)
    return (data_iso(m.group(1)), data_iso(m.group(2))) if m else (None, None)


def _pagas(linhas: list[dict], deputados: list[dict], filtro) -> list:
    escolhidas = [l for l in linhas if filtro(l) and comum.valor_br(l.get("ValorPago"))]
    limpo = lambda nome: (nome or "").replace("_", " ")  # a fonte traz "COUTINHO_SANTOS"
    ligados = comum.ligar_nomes({limpo(l["Favorecido"]) for l in escolhidas}, deputados)
    return [(ligados[limpo(l["Favorecido"])], l) for l in escolhidas if limpo(l["Favorecido"]) in ligados]


def itens_cota(linhas: list[dict], deputados: list[dict]) -> list[dict]:
    itens = []
    for pid, l in _pagas(linhas, deputados, e_cota):
        pago_em = data_iso(l.get("Data"))
        itens.append({"idDeputado": pid, "mes": int(pago_em[5:7]) if pago_em else None, "data": pago_em,
                      "referencia": referencia(l.get("HistoricoDocumento"), pago_em), "categoria": "Cota parlamentar (reembolso)",
                      "fornecedor": None, "cnpj": None, "documento": (l.get("Documento") or "").strip() or None,
                      "valor": comum.valor_br(l.get("ValorPago")), "fonte": PAGINA})
    itens.sort(key=lambda i: (i["data"] or "", i["idDeputado"], i["documento"] or ""))
    return itens


def itens_diarias(linhas: list[dict], deputados: list[dict]) -> list[dict]:
    itens = []
    for pid, l in _pagas(linhas, deputados, e_diaria):
        pago_em = data_iso(l.get("Data"))
        inicio, fim = periodo(l.get("HistoricoDocumento"))
        itens.append({"idDeputado": pid, "data": inicio or pago_em, "dataFim": fim, "pagoEm": pago_em,
                      "mes": int(pago_em[5:7]) if pago_em else None, "destino": None,
                      "motivo": " ".join((l.get("HistoricoDocumento") or "").split()) or None,
                      "documento": (l.get("Documento") or "").strip() or None, "valor": comum.valor_br(l.get("ValorPago")), "fonte": PAGINA})
    itens.sort(key=lambda i: (i["data"] or "", i["idDeputado"], i["documento"] or ""))
    return itens


def ano_fechado(ano: int, hoje: date, pasta) -> bool:
    """Não baixar de novo: ano encerrado com arquivo, ou o ano passado já lido a partir de março deste ano."""
    arquivo = pasta / f"verbas_{ano}.json"
    if comum.ano_encerrado(ano, hoje, arquivo):
        return True
    if ano == hoje.year - 1 and hoje.month >= MES_FECHA_ANO_ANTERIOR:
        lido = (comum.ler(arquivo, {}) or {}).get("coletadoEm") or ""
        return lido >= f"{hoje.year}-{MES_FECHA_ANO_ANTERIOR:02d}-01"
    return False


def parcial_novo(modificado_em) -> dict:
    return {"recursoModificadoEm": modificado_em, "offset": 0, "cabecalho": None, "linhas": []}


def _guardar(linha: bytes, parcial: dict) -> None:
    if parcial["cabecalho"] is None:
        parcial["cabecalho"] = cabecalho_csv(linha)
        return
    l = linha_da_assembleia(linha, parcial["cabecalho"])
    if l is not None and (e_cota(l) or e_diaria(l)) and comum.valor_br(l.get("ValorPago")):
        parcial["linhas"].append({c: l.get(c) for c in CAMPOS})


def ler_csv(s, url: str, parcial: dict) -> None:
    """Lê o CSV a partir de `parcial["offset"]` e acrescenta a `parcial["linhas"]` as linhas pagas de cota e diárias da Assembleia
    (só `CAMPOS`). Em erro ou prazo esgotado, `parcial` fica certo até a última linha inteira lida, para continuar depois."""
    cabecalhos = {"Range": f"bytes={parcial['offset']}-"} if parcial["offset"] else {}
    with s.get(url, stream=True, timeout=300, headers=cabecalhos) as resp:
        resp.raise_for_status()
        if parcial["offset"] and resp.status_code != 206:  # a fonte ignorou o Range: recomeça do zero
            parcial.update(parcial_novo(parcial["recursoModificadoEm"]))
        resto = b""
        for bloco in resp.iter_content(BLOCO):
            partes = (resto + bloco).split(b"\n")
            resto = partes.pop()
            for linha in partes:
                _guardar(linha.rstrip(b"\r"), parcial)
                parcial["offset"] += len(linha) + 1
            comum.checar_prazo()
        if resto:
            _guardar(resto.rstrip(b"\r"), parcial)
            parcial["offset"] += len(resto)


def coletar() -> None:
    pasta = comum.DADOS / UF
    hoje = date.today()
    deputados = deputados_do_tse()
    if not deputados:
        comum.avisar("ES: sem eleitos de 2022 em dados/tse/2022/ES.json")
        return
    comum.salvar(pasta / "deputados.json", {"fonte": "https://divulgacandcontas.tse.jus.br/divulga/#/home", "host": None, "legislatura": "2023-2027",
                                            "deputados": deputados})
    s = comum.sessao()
    r = s.get(CKAN, timeout=30)
    r.raise_for_status()
    for ano, recurso in sorted(arquivos_por_ano(r.json()).items(), reverse=True):
        if ano < PRIMEIRO_ANO or ano_fechado(ano, hoje, pasta):
            continue
        modificado = recurso["modificadoEm"]
        if modificado and (comum.ler(pasta / f"verbas_{ano}.json", {}) or {}).get("recursoModificadoEm") == modificado:
            print(f"ES: {ano} sem mudança na fonte desde {modificado}")
            continue
        arq_parcial = pasta / f"parcial_{ano}.json"
        parcial = comum.ler(arq_parcial)
        if not parcial or not modificado or parcial.get("recursoModificadoEm") != modificado:
            parcial = parcial_novo(modificado)
        try:
            ler_csv(s, recurso["url"], parcial)
        except Exception as e:  # noqa: BLE001 - guarda o que leu; um ano que falha não derruba os outros
            comum.salvar(arq_parcial, parcial)
            comum.avisar(f"ES: despesas {ano} lidas até o byte {parcial['offset']} ({e}); a próxima coleta continua dali")
            if isinstance(e, comum.PrazoEsgotado):
                break
            continue
        cota, diarias = itens_cota(parcial["linhas"], deputados), itens_diarias(parcial["linhas"], deputados)
        topo = {"coletadoEm": hoje.isoformat(), "fonte": PAGINA, "recursoModificadoEm": modificado}
        comum.salvar(pasta / f"verbas_{ano}.json", {**topo, "itens": cota})
        comum.salvar(pasta / f"diarias_{ano}.json", {**topo, "itens": diarias})
        arq_parcial.unlink(missing_ok=True)
        print(f"ES: {ano} cota {len(cota)}, diárias {len(diarias)} ({parcial['offset'] / 1e6:.0f} MB lidos)")
    print(f"ES: {len(deputados)} deputados")


def _contrato_despesas(ctx):
    """Cabeçalho e algumas linhas pagas da ALES (cota e diárias) do CSV mais recente; para de ler quando já tem a amostra."""
    s = comum.sessao()
    r = s.get(CKAN, timeout=30)
    r.raise_for_status()
    ano, recurso = max(arquivos_por_ano(r.json()).items())
    cabecalho, cota, diarias = None, [], []
    with s.get(recurso["url"], stream=True, timeout=300) as resp:
        resp.raise_for_status()
        for linha in resp.iter_lines(chunk_size=BLOCO):
            if cabecalho is None:
                cabecalho = linha.decode("utf-8-sig")
                colunas = cabecalho_csv(linha)
                continue
            l = linha_da_assembleia(linha, colunas)
            if l is None or not comum.valor_br(l.get("ValorPago")):
                continue
            if e_cota(l) and len(cota) < 4:
                cota.append(linha.decode("utf-8", errors="replace"))
            elif e_diaria(l) and len(diarias) < 4:
                diarias.append(linha.decode("utf-8", errors="replace"))
            if len(cota) >= 4 and len(diarias) >= 4:
                break
    return {"ano": ano, "csv": "\n".join([cabecalho, *cota, *diarias])}


def _conferir_despesas(registro):
    falhas = []
    colunas = next(csv.reader([registro["csv"].split("\n", 1)[0]], delimiter=";"))
    for c in CAMPOS:
        if c not in colunas:
            falhas.append(f"CSV de despesas sem a coluna {c}")
    linhas = linhas_da_assembleia(registro["csv"].split("\n"))
    if not any(e_cota(l) for l in linhas):
        falhas.append("nenhuma linha de cota parlamentar da Assembleia no CSV")
    if not any(e_diaria(l) for l in linhas):
        falhas.append("nenhuma linha de diárias da Assembleia no CSV")
    for l in linhas:
        if not data_iso(l.get("Data")) or comum.valor_br(l.get("ValorPago")) is None:
            falhas.append("linha sem data ou valor pago legível")
    return falhas, []


CONTRATOS = [
    dict(nome="estadual_es_ckan", fonte=CKAN, buscar=lambda ctx: comum.sessao().get(CKAN, timeout=30).json(),
         usados=["result.resources[].name", "result.resources[].url", "result.resources[].last_modified"]),
    dict(nome="estadual_es_despesas", fonte=PAGINA, buscar=_contrato_despesas, html=_conferir_despesas),
]


if __name__ == "__main__":
    coletar()
    sys.exit(0)
