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

Os arquivos têm 1,2 a 1,5 GB e saem da fonte a ~0,65 MB/s por conexão: são lidos em streaming, sem guardar o CSV, do ano mais
novo para o mais velho, em CONEXOES fatias paralelas com `Range` (cada fatia lê as linhas que começam nela). Um ano só é
baixado de novo quando o `last_modified` do recurso no CKAN muda (`recursoModificadoEm` no arquivo). Mudou: se o ano já foi lido
por completo há menos de RENOVAR_COMPLETA_DIAS, lê só o trecho novo depois do `tamanho` anterior e junta com os itens
guardados; senão (ou se o arquivo encolheu) lê tudo, pois estorno pode alterar linha antiga. Se o prazo do job acabar no meio,
o que já foi lido fica em `parcial_<ano>.json` (uma posição e as linhas úteis por fatia) e a coleta seguinte continua dali.
Anos anteriores ao passado com arquivo não são baixados de novo (`comum.ano_encerrado`); o ano passado é lido de novo até
março (pagamentos atrasados) e depois fica.

Não coletado: folha, presença, proposições e votações (não estão no portal do Estado; `www.al.es.gov.br` não responde).
"""

import csv
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import estaduais_comum as comum
import identidades

UF = "ES"
TSE_ARQUIVO = comum.arquivo_tse(UF)
TSE_FICHA = comum.ficha_tse(UF)
PACOTE = "portal-da-transparencia-despesas-execucao-orcamentaria-e-financeira"
CKAN = f"https://dados.es.gov.br/api/3/action/package_show?id={PACOTE}"
PAGINA = f"https://dados.es.gov.br/dataset/{PACOTE}"
PRIMEIRO_ANO = 2026  # anos anteriores ficam de fora: cada CSV tem 1,2 a 1,5 GB e a carga deles levaria dias de job
MES_FECHA_ANO_ANTERIOR = 3  # a partir deste mês o arquivo do ano passado, se já lido no ano corrente, não é baixado de novo
BLOCO = 1 << 20
CONEXOES = 3  # leituras simultâneas do mesmo CSV (host S3: medido ~0,65 MB/s numa conexão e ~1,8 MB/s em três)
FATIA_MIN = 8 << 20  # trecho menor que isto não vale outra conexão
TAMANHO_CABECALHO = 1 << 16
RENOVAR_COMPLETA_DIAS = 14  # entre duas leituras completas, só o trecho novo do fim do CSV é lido
_MARCA = b"ASSEMBLEIA LEGISLATIVA"
CAMPOS = ("Data", "ValorPago", "Favorecido", "Documento", "HistoricoDocumento", "UnidadeGestora", "ElementoDespesa", "SubelementoDespesa")


def deputados_do_tse() -> list[dict]:
    return comum.deputados_do_tse(TSE_ARQUIVO, TSE_FICHA)


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
    lin = dict(zip(cabecalho, campos, strict=False))
    return lin if (lin.get("UnidadeGestora") or "").strip().upper().startswith("ASSEMBLEIA LEGISLATIVA") else None


def linhas_da_assembleia(linhas) -> list[dict]:
    """Linhas (bytes ou str, a primeira é o cabeçalho) cuja unidade gestora é a Assembleia Legislativa."""
    cabecalho, achadas = None, []
    for linha in linhas:
        bruta = linha if isinstance(linha, bytes) else linha.encode("utf-8")
        if cabecalho is None:
            cabecalho = cabecalho_csv(bruta)
        elif (lin := linha_da_assembleia(bruta, cabecalho)) is not None:
            achadas.append(lin)
    return achadas


def e_cota(lin: dict) -> bool:
    return "cotas parlamentares" in comum.sem_acento(lin.get("SubelementoDespesa"))


def e_diaria(lin: dict) -> bool:
    return comum.sem_acento(lin.get("ElementoDespesa")).startswith("diaria")


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
    return (comum.data_br_iso(m.group(1)), comum.data_br_iso(m.group(2))) if m else (None, None)


def _pagas(linhas: list[dict], deputados: list[dict], filtro) -> list:
    escolhidas = [lin for lin in linhas if filtro(lin) and comum.valor_br(lin.get("ValorPago"))]
    def limpo(nome):  # a fonte traz "COUTINHO_SANTOS"
        return (nome or "").replace("_", " ")

    ligados = identidades.ligar_nomes({limpo(lin["Favorecido"]) for lin in escolhidas}, deputados, UF)
    return [(ligados[limpo(lin["Favorecido"])], lin) for lin in escolhidas if limpo(lin["Favorecido"]) in ligados]


def itens_cota(linhas: list[dict], deputados: list[dict]) -> list[dict]:
    itens = []
    for pid, lin in _pagas(linhas, deputados, e_cota):
        pago_em = comum.data_br_iso(lin.get("Data"))
        itens.append({"idDeputado": pid, "mes": int(pago_em[5:7]) if pago_em else None, "data": pago_em,
                      "referencia": referencia(lin.get("HistoricoDocumento"), pago_em), "categoria": "Cota parlamentar (reembolso)",
                      "fornecedor": None, "cnpj": None, "documento": (lin.get("Documento") or "").strip() or None,
                      "valor": comum.valor_br(lin.get("ValorPago")), "fonte": PAGINA})
    itens.sort(key=lambda i: (i["data"] or "", i["idDeputado"], i["documento"] or ""))
    return itens


def itens_diarias(linhas: list[dict], deputados: list[dict]) -> list[dict]:
    itens = []
    for pid, lin in _pagas(linhas, deputados, e_diaria):
        pago_em = comum.data_br_iso(lin.get("Data"))
        inicio, fim = periodo(lin.get("HistoricoDocumento"))
        itens.append({"idDeputado": pid, "data": inicio or pago_em, "dataFim": fim, "pagoEm": pago_em,
                      "mes": int(pago_em[5:7]) if pago_em else None, "destino": None,
                      "motivo": " ".join((lin.get("HistoricoDocumento") or "").split()) or None,
                      "documento": (lin.get("Documento") or "").strip() or None, "valor": comum.valor_br(lin.get("ValorPago")), "fonte": PAGINA})
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


def _guardar(linha: bytes, cabecalho: list[str], linhas: list) -> None:
    lin = linha_da_assembleia(linha, cabecalho)
    if lin is not None and (e_cota(lin) or e_diaria(lin)) and comum.valor_br(lin.get("ValorPago")):
        linhas.append({c: lin.get(c) for c in CAMPOS})


def cabecalho_e_tamanho(s, url: str) -> tuple:
    """(colunas, bytes do cabeçalho com a quebra de linha, tamanho total do arquivo) por uma leitura curta com Range."""
    with s.get(url, stream=True, timeout=60, headers={"Range": f"bytes=0-{TAMANHO_CABECALHO - 1}"}) as resp:
        resp.raise_for_status()
        if resp.status_code != 206:
            raise RuntimeError("a fonte não aceita Range")
        total = int(resp.headers["Content-Range"].rsplit("/", 1)[1])
        inicio = b""
        for bloco in resp.iter_content(BLOCO):
            inicio += bloco
            if b"\n" in inicio:
                break
    fim = inicio.index(b"\n") + 1
    return cabecalho_csv(inicio[:fim].rstrip(b"\r\n")), fim, total


def planejar_fatias(inicio: int, total: int, conexoes: int = CONEXOES) -> list[dict]:
    """Divide [inicio, total) em até `conexoes` fatias de pelo menos FATIA_MIN bytes. `offset` é onde a leitura continua; só a
    primeira fatia começa numa linha inteira (`alinhada`), as outras descartam o trecho até a primeira quebra de linha."""
    n = max(1, min(conexoes, (total - inicio) // FATIA_MIN))
    passo = -(-(total - inicio) // n)
    return [{"inicio": a, "fim": min(a + passo, total), "offset": a, "alinhada": i == 0, "linhas": []}
            for i, a in enumerate(range(inicio, total, passo))]


def ler_fatia(s, url: str, f: dict, cabecalho: list[str]) -> None:
    """Lê as linhas que COMEÇAM em [f.inicio, f.fim) (a que cruza o fim é desta fatia; a que cruza o início é da anterior) e as
    acrescenta a `f["linhas"]`. Em erro ou prazo esgotado, `f["offset"]` fica no começo da próxima linha a ler."""
    if f["alinhada"] and f["offset"] >= f["fim"]:
        return
    pos = f["offset"] if f["alinhada"] else f["offset"] - 1
    with s.get(url, stream=True, timeout=300, headers={"Range": f"bytes={pos}-"}) as resp:
        resp.raise_for_status()
        if resp.status_code != 206:
            raise RuntimeError("a fonte ignorou o Range")
        pular, resto = not f["alinhada"], b""
        for bloco in resp.iter_content(BLOCO):
            partes = (resto + bloco).split(b"\n")
            resto = partes.pop()
            for linha in partes:
                if pular:
                    pular, f["alinhada"] = False, True
                elif pos >= f["fim"]:
                    return
                else:
                    _guardar(linha.rstrip(b"\r"), cabecalho, f["linhas"])
                pos += len(linha) + 1
                f["offset"] = pos
            comum.checar_prazo()
        if resto and not pular and pos < f["fim"]:
            _guardar(resto.rstrip(b"\r"), cabecalho, f["linhas"])
            f["offset"] = pos + len(resto)
    if f["offset"] < f["fim"]:
        raise RuntimeError(f"leitura incompleta da fatia {f['inicio']}-{f['fim']}")


def ler_fatias(s, url: str, parcial: dict) -> None:
    """Lê as fatias do `parcial` em paralelo. Todas terminam (ou param no prazo) antes do erro de alguma ser levantado, para o
    `parcial` guardar o avanço de cada uma; prazo esgotado tem prioridade sobre os outros erros."""
    pendentes = [f for f in parcial["fatias"] if not (f["alinhada"] and f["offset"] >= f["fim"])]
    if not pendentes:
        return
    erros = []
    with ThreadPoolExecutor(max_workers=len(pendentes)) as pool:
        futuros = [pool.submit(ler_fatia, s, url, f, parcial["cabecalho"]) for f in pendentes]
    for fut in futuros:
        if fut.exception() is not None:
            erros.append(fut.exception())
    if erros:
        raise next((e for e in erros if isinstance(e, comum.PrazoEsgotado)), erros[0])


def parcial_novo(s, url: str, modificado_em, antigo: dict, hoje: date) -> dict:
    """Plano de leitura de um ano. `antigo` é o `verbas_<ano>.json` anterior: se tem `tamanho` e foi lido por completo há menos
    de RENOVAR_COMPLETA_DIAS, só o trecho novo do fim do CSV é lido (`incremental`); estorno de linha antiga só entra na completa."""
    cabecalho, fim_cab, total = cabecalho_e_tamanho(s, url)
    completaEm = antigo.get("completaEm")
    incremental = bool(antigo.get("tamanho") and completaEm and antigo["tamanho"] <= total
                       and (hoje - date.fromisoformat(completaEm)).days < RENOVAR_COMPLETA_DIAS)
    inicio = antigo["tamanho"] if incremental else fim_cab
    return {"recursoModificadoEm": modificado_em, "tamanho": total, "cabecalho": cabecalho, "incremental": incremental,
            "completaEm": completaEm if incremental else hoje.isoformat(), "inicio": inicio, "fatias": planejar_fatias(inicio, total)}


def juntar(antigos: list[dict], novos: list[dict]) -> list[dict]:
    return sorted(antigos + novos, key=lambda i: (i["data"] or "", i["idDeputado"], i["documento"] or ""))


def coletar() -> None:
    pasta = comum.DADOS / UF
    hoje = date.today()
    deputados = deputados_do_tse()
    if not deputados:
        comum.avisar("ES: sem eleitos de 2022 em dados/tse/2022/ES.json")
        return
    comum.salvar(pasta / "deputados.json", {"fonte": "https://divulgacandcontas.tse.jus.br/divulga/#/home", "host": None, "legislatura": "2023-2027",
                                            "deputados": deputados})
    s = comum.sessao(CONEXOES)
    r = s.get(CKAN, timeout=30)
    r.raise_for_status()
    for ano, recurso in sorted(arquivos_por_ano(r.json()).items(), reverse=True):
        if ano < PRIMEIRO_ANO or ano_fechado(ano, hoje, pasta):
            continue
        modificado = recurso["modificadoEm"]
        antigo = comum.ler(pasta / f"verbas_{ano}.json", {}) or {}
        if modificado and antigo.get("recursoModificadoEm") == modificado:
            print(f"ES: {ano} sem mudança na fonte desde {modificado}")
            continue
        arq_parcial = pasta / f"parcial_{ano}.json"
        parcial = comum.ler(arq_parcial)
        try:
            if not parcial or not modificado or parcial.get("recursoModificadoEm") != modificado:
                parcial = None
                parcial = parcial_novo(s, recurso["url"], modificado, antigo, hoje)
            ler_fatias(s, recurso["url"], parcial)
        except Exception as e:  # noqa: BLE001 - guarda o que leu; um ano que falha não derruba os outros
            if parcial:
                comum.salvar(arq_parcial, parcial)
            comum.avisar(f"ES: despesas {ano} não lidas por inteiro ({e}); a próxima coleta continua do que já foi lido")
            if isinstance(e, comum.PrazoEsgotado):
                break
            continue
        linhas = [lin for f in parcial["fatias"] for lin in f["linhas"]]
        cota, diarias = itens_cota(linhas, deputados), itens_diarias(linhas, deputados)
        if parcial["incremental"]:
            cota = juntar(antigo.get("itens", []), cota)
            diarias = juntar((comum.ler(pasta / f"diarias_{ano}.json", {}) or {}).get("itens", []), diarias)
        topo = {"coletadoEm": hoje.isoformat(), "fonte": PAGINA, "recursoModificadoEm": modificado, "tamanho": parcial["tamanho"],
                "completaEm": parcial["completaEm"]}
        comum.salvar(pasta / f"verbas_{ano}.json", {**topo, "itens": cota})
        comum.salvar(pasta / f"diarias_{ano}.json", {**topo, "itens": diarias})
        arq_parcial.unlink(missing_ok=True)
        modo = "incremental" if parcial["incremental"] else "completa"
        print(f"ES: {ano} cota {len(cota)}, diárias {len(diarias)} (leitura {modo}, {(parcial['tamanho'] - parcial['inicio']) / 1e6:.0f} MB)")
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
            lin = linha_da_assembleia(linha, colunas)
            if lin is None or not comum.valor_br(lin.get("ValorPago")):
                continue
            if e_cota(lin) and len(cota) < 4:
                cota.append(linha.decode("utf-8", errors="replace"))
            elif e_diaria(lin) and len(diarias) < 4:
                diarias.append(linha.decode("utf-8", errors="replace"))
            if len(cota) >= 4 and len(diarias) >= 4:
                break
    return {"ano": ano, "csv": "\n".join([cabecalho, *cota, *diarias])}


def _conferir_despesas(registro):
    falhas = []
    colunas = next(csv.reader([registro["csv"].split("\n", 1)[0]], delimiter=";"))
    falhas += comum.faltando(colunas, CAMPOS, "CSV de despesas")
    linhas = linhas_da_assembleia(registro["csv"].split("\n"))
    if not any(e_cota(lin) for lin in linhas):
        falhas.append("nenhuma linha de cota parlamentar da Assembleia no CSV")
    if not any(e_diaria(lin) for lin in linhas):
        falhas.append("nenhuma linha de diárias da Assembleia no CSV")
    for lin in linhas:
        if not comum.data_br_iso(lin.get("Data")) or comum.valor_br(lin.get("ValorPago")) is None:
            falhas.append("linha sem data ou valor pago legível")
    return falhas, []


CONTRATOS = [
    {"nome": "estadual_es_ckan", "fonte": CKAN, "buscar": lambda ctx: comum.contrato_json(CKAN),
         "usados": ["result.resources[].name", "result.resources[].url", "result.resources[].last_modified"]},
    {"nome": "estadual_es_despesas", "fonte": PAGINA, "buscar": _contrato_despesas, "html": _conferir_despesas},
]


if __name__ == "__main__":
    comum.principal(coletar)
