"""
Vereadores em exercício (inclui suplentes que assumiram), a partir da folha de pessoal que o Tribunal de Contas publica.

Fontes abertas e lidas aqui (levantamento em docs/levantamento_vereadores_tce.md):
  - PE: TCE-PE, Dados Abertos (Sagres Pessoal), `ListaServidores` filtrada por cargo VEREADOR
    https://sistemas.tce.pe.gov.br/DadosAbertos/ListaServidores!json?NomeCargo=VEREADOR
    Uma linha por mandato, com ingresso e afastamento (o afastamento falta enquanto o mandato corre). Sem partido.
  - PB: TCE-PB, arquivos de servidores no bucket público https://download.tce.pb.gov.br/dados-abertos/
    `dados-por-municipio/<código>/servidores/servidores-<ano>.zip` (CSV de folha: uma linha por mês e matrícula). Só as linhas
    de cargo eletivo VEREADOR entram; ingresso = menor data de admissão, primeiro e último mês em que aparece na folha.
    Sem partido nem data de afastamento: quem some da folha tem `ultimoMes` anterior ao mês mais recente coletado.

Grava em `dados/municipais/<UF>/`: PE `vereadores.json`; PB `vereadores_<ano>.json` (anos encerrados não são baixados de novo).
O nome e o cargo ficam como a fonte publica (cargo normalizado para VEREADOR); o CPF só entra mascarado (`***.ddd.ddd-**`).
Ligação com a pessoa (TSE) e partido: identidades.py, não aqui.
"""

import csv
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from calendar import monthrange
from datetime import date
from io import BytesIO, StringIO

import estaduais_comum as comum

DADOS = comum.RAIZ / "dados" / "municipais"
PE_URL = "https://sistemas.tce.pe.gov.br/DadosAbertos/ListaServidores!json?NomeCargo=VEREADOR"
PB_BASE = "https://download.tce.pb.gov.br/dados-abertos/"
PB_PORTAL = "https://dados-abertos.tce.pb.gov.br/"
PRIMEIRO_ANO = 2025       # legislatura 2025-2028
INICIO_LEGISLATURA = "2025-01-01"


def cpf_mascarado(valor) -> str | None:
    """`***.ddd.ddd-**` com os 6 dígitos centrais; já mascarado fica como veio; inválido, None."""
    texto = str(valor or "").strip()
    if "*" in texto:
        return texto
    d = re.sub(r"\D", "", texto)
    return f"***.{d[3:6]}.{d[6:9]}-**" if len(d) == 11 else None


def iso(texto) -> str | None:
    """Data AAAA-MM-DD a partir de ISO (com ou sem hora) ou DD/MM/AAAA."""
    t = str(texto or "").strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", t) or None
    if m:
        return f"{m[1]}-{m[2]}-{m[3]}"
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", t)
    return f"{m[3]}-{m[2]}-{m[1]}" if m else None


def municipio_da_camara(nome_uj: str | None) -> str | None:
    """"Câmara Municipal de Afogados da Ingazeira" -> "Afogados da Ingazeira"; também "Vereadores de X" e "Câmara de Vereadores da Cidade do X"."""
    nome = (nome_uj or "").strip()
    m = re.match(r"^(?:c[âa]mara\s+(?:municipal|de\s+vereadores)\s+d[aeo]s?\s+(?:cidade\s+d[aeo]s?\s+)?|vereadores\s+d[aeo]s?\s+)(.+)$", nome, re.I)
    return m[1].strip() if m else (nome or None)


# ------------------------------------------------------------------ PE

def itens_pe(linhas: list[dict]) -> list[dict]:
    """Mandatos de vereador (vínculo eletivo) que tocam a legislatura atual, sem repetir (câmara, pessoa, ingresso)."""
    achados = {}
    for lin in linhas:
        cargo = str(lin.get("NomeCargo") or "").upper()
        if "VEREADOR" not in cargo or "ASSESSOR" in cargo or str(lin.get("NomeTipoVinculo") or "").strip().lower() != "eletivo":
            continue
        ingresso = iso(lin.get("DataIngresso")) or iso(lin.get("DataAdmissao"))
        afastamento = iso(lin.get("DataAfastamento"))
        if not ingresso or (afastamento and afastamento <= INICIO_LEGISLATURA and ingresso < INICIO_LEGISLATURA):
            continue
        item = {"municipio": municipio_da_camara(lin.get("NomeUJ")), "unidade": str(lin.get("UnidadeJurisdicionadaTCE") or "").strip() or None,
                "nome": str(lin.get("NomeServidor") or "").strip(), "cpf": cpf_mascarado(lin.get("CPFServidor")), "cargo": "VEREADOR",
                "matricula": str(lin.get("Matricula") or "").strip() or None, "ingresso": ingresso, "afastamento": afastamento}
        if item["nome"] and item["municipio"]:
            achados[(item["unidade"], item["cpf"], item["nome"], ingresso)] = item
    return sorted(achados.values(), key=lambda i: (i["municipio"], i["ingresso"], i["nome"]))


def coletar_pe() -> None:
    s = comum.sessao()
    r = s.get(PE_URL, timeout=120)
    r.raise_for_status()
    resposta = r.json()["resposta"]
    if int(resposta.get("tamanhoResultado") or 0) >= int(resposta.get("limiteResultado") or 10**9):
        comum.avisar("PE: a resposta bateu no limite da API; podem faltar vereadores")
    itens = itens_pe(resposta["conteudo"])
    comum.salvar(DADOS / "PE" / "vereadores.json", {"coletadoEm": date.today().isoformat(), "fonte": PE_URL, "itens": itens})
    print(f"PE: {len(itens)} mandatos de vereador, {len({i['municipio'] for i in itens})} câmaras")


# ------------------------------------------------------------------ PB

def codigos_pb(xml_texto: str) -> tuple[list[str], str | None]:
    """(códigos de município, token da próxima página) de uma listagem S3 ListObjectsV2 de `dados-por-municipio/`."""
    raiz = ET.fromstring(xml_texto)
    ns = {"s": raiz.tag.split("}")[0][1:]} if raiz.tag.startswith("{") else None
    achar = (lambda tag: raiz.findall(f".//s:{tag}", ns)) if ns else (lambda tag: raiz.findall(f".//{tag}"))
    codigos = [m[1] for p in achar("Prefix") if (m := re.search(r"dados-por-municipio/(\d+)/$", p.text or ""))]
    token = next((t.text for t in achar("NextContinuationToken")), None)
    return codigos, token


def listar_municipios_pb(s) -> list[str]:
    codigos, token = [], None
    while True:
        params = {"list-type": "2", "delimiter": "/", "prefix": "dados-por-municipio/", **({"continuation-token": token} if token else {})}
        r = s.get(PB_BASE, params=params, timeout=60)
        r.raise_for_status()
        novos, token = codigos_pb(r.text)
        codigos += novos
        if not token:
            return sorted(set(codigos))


def linhas_vereador_pb(conteudo_zip: bytes) -> list[dict]:
    """Linhas do CSV de servidores que são vereadores (cargo eletivo)."""
    z = zipfile.ZipFile(BytesIO(conteudo_zip))
    nome = next(n for n in z.namelist() if n.lower().endswith(".csv"))
    texto = z.read(nome).decode("utf-8-sig", errors="replace")
    leitor = csv.DictReader(StringIO(texto), delimiter=";")
    return [lin for lin in leitor
            if (lin.get("tipo_cargo") or "").strip().lower().startswith("eletivo") and "VEREADOR" in (lin.get("descricao_cargo") or "").upper()]


def itens_pb(linhas: list[dict]) -> list[dict]:
    """Uma entrada por (unidade gestora, matrícula, nome) com ingresso e primeiro/último mês na folha."""
    grupos: dict = {}
    for lin in linhas:
        mes = re.sub(r"\D", "", lin.get("ano_mes") or "")
        if len(mes) != 6:
            continue
        nome = (lin.get("nome_servidor") or "").strip()
        chave = (str(lin.get("codigo_unidade_gestora") or "").strip(), (lin.get("matricula") or "").strip(), nome)
        g = grupos.setdefault(chave, {"municipio": (lin.get("nome_municipio") or "").strip() or municipio_da_camara(lin.get("descricao_unidade_gestora")),
                                      "unidade": chave[0] or None, "nome": nome, "cpf": cpf_mascarado(lin.get("cpf_cnpj")), "cargo": "VEREADOR",
                                      "matricula": chave[1] or None, "ingresso": None, "primeiroMes": mes, "ultimoMes": mes})
        adm = iso(lin.get("data_admissao"))
        if adm and (not g["ingresso"] or adm < g["ingresso"]):
            g["ingresso"] = adm
        g["primeiroMes"], g["ultimoMes"] = min(g["primeiroMes"], mes), max(g["ultimoMes"], mes)
    for g in grupos.values():
        g["primeiroMes"], g["ultimoMes"] = f"{g['primeiroMes'][:4]}-{g['primeiroMes'][4:]}", f"{g['ultimoMes'][:4]}-{g['ultimoMes'][4:]}"
    return sorted((g for g in grupos.values() if g["nome"] and g["municipio"]), key=lambda g: (g["municipio"], g["nome"]))


def mandatos_pb(anos: list[list[dict]]) -> list[dict]:
    """Junta os itens de vários anos (mesma unidade, matrícula e nome) e deriva o afastamento: quem não aparece no mês mais recente
    da folha daquela câmara saiu no último dia do `ultimoMes`. Mês mais recente = o maior `ultimoMes` entre todos da mesma unidade."""
    juntos: dict = {}
    for itens in anos:
        for it in itens:
            chave = (it["unidade"], it["matricula"], it["nome"])
            if chave in juntos:
                g = juntos[chave]
                g["primeiroMes"], g["ultimoMes"] = min(g["primeiroMes"], it["primeiroMes"]), max(g["ultimoMes"], it["ultimoMes"])
                g["ingresso"] = min(filter(None, [g["ingresso"], it["ingresso"]]), default=None)
            else:
                juntos[chave] = dict(it)
    mais_recente: dict = {}
    for g in juntos.values():
        mais_recente[g["unidade"]] = max(mais_recente.get(g["unidade"], ""), g["ultimoMes"])
    for g in juntos.values():
        ano, mes = map(int, g["ultimoMes"].split("-"))
        g["afastamento"] = None if g["ultimoMes"] == mais_recente[g["unidade"]] else f"{ano:04d}-{mes:02d}-{monthrange(ano, mes)[1]:02d}"
    return sorted(juntos.values(), key=lambda g: (g["municipio"], g["ingresso"] or "", g["nome"]))


def coletar_pb() -> None:
    hoje = date.today()
    pasta = DADOS / "PB"
    s = comum.sessao()
    municipios = listar_municipios_pb(s)
    for ano in range(PRIMEIRO_ANO, hoje.year + 1):
        arquivo = pasta / f"vereadores_{ano}.json"
        if comum.ano_encerrado(ano, hoje, arquivo):
            continue
        linhas = []
        for cod in municipios:
            comum.checar_prazo()
            r = s.get(f"{PB_BASE}dados-por-municipio/{cod}/servidores/servidores-{ano}.zip", timeout=120)
            if r.status_code == 404:
                continue
            r.raise_for_status()
            linhas += linhas_vereador_pb(r.content)
        itens = itens_pb(linhas)
        comum.salvar(arquivo, {"coletadoEm": hoje.isoformat(), "fonte": PB_PORTAL, "itens": itens})
        print(f"PB {ano}: {len(itens)} vereadores em {len({i['municipio'] for i in itens})} câmaras")


def coletar() -> None:
    comum.rodar_etapas("Vereadores", [("PE", coletar_pe), ("PB", coletar_pb)])


if __name__ == "__main__":
    coletar()
    sys.exit(0)
