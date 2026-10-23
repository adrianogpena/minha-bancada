"""
Deputados estaduais de Mato Grosso (ALMT), fora do SAPL.

Fonte aberta e lida aqui: a API JSON do Portal da Transparência da ALMT (Elotech), https://almt.eloweb.net/portaltransparencia/1/ ,
que o próprio portal consome em https://almt.eloweb.net/portaltransparencia-api/api/ (sem login; cabeçalhos `entidade: 1` e
`exercicio: <ano>`, aprendidos na aba Rede do Firefox):
  - deputados em exercício: /servidores?cargo=DEPUTADO, cargo "DEPUTADO ESTADUAL" e situação ATIVO (nome civil e matrícula);
    nome parlamentar, partido e e-mail vêm do TSE (eleitos de 2022, dados/tse/2022/MT.json) quando o nome civil casa, senão do nome do gabinete;
  - remuneração mensal: /servidores/{matrícula} (`dadosFinanceiros`: salário-base, vencimentos, descontos, outros proventos);
  - diárias: /diarias?dataInicial&dataFinal, só as linhas cujo nome é o de um deputado (as de assessores "solicitado: gab deputado" ficam de fora).

Sem dado: verbas (/servidores/verbas/{evento}/{mês}) e emendas parlamentares (/emendas-parlamentares) respondem lista vazia; a tela
/cotas-parlamentares não chama nenhuma API de dados.
Não acessado: https://www.al.mt.gov.br (projetos, votações, presença, ficha) não respondeu (timeout) em duas tentativas.
"""

import re
from datetime import date

import estaduais_comum as comum

UF = "MT"
PORTAL = "https://almt.eloweb.net/portaltransparencia/1/"
API = "https://almt.eloweb.net/portaltransparencia-api/api"
TSE_ARQUIVO = comum.arquivo_tse(UF)
TSE_FICHA = comum.ficha_tse(UF)
PRIMEIRO_ANO = 2023
PAGINA = 500
PEQUENAS = {"de", "da", "do", "das", "dos", "e"}


def cabecalhos(ano: int) -> dict:
    return {"Accept": "application/json", "entidade": "1", "exercicio": str(ano)}


def titulo(nome: str) -> str:
    palavras = (nome or "").lower().split()
    return " ".join(p if (i and p in PEQUENAS) else p.capitalize() for i, p in enumerate(palavras))


def nome_do_gabinete(lotacao: str) -> str | None:
    """"GAB DEP FABIO TARDIN "FABINHO"" -> "Fabio Tardin Fabinho"; lotação sem nome de gabinete (ex.: "WILSON SANTOS") vale como está."""
    n = re.sub(r"^(GAB(INETE)?\s+)?(DEP(UTAD[OA])?\.?\s+)?", "", (lotacao or "").upper().replace('"', "")).strip()
    return titulo(n) if n else None


def deputados_ativos(servidores: list[dict]) -> list[dict]:
    """Servidores com cargo "DEPUTADO ESTADUAL" e situação ATIVO, um por matrícula."""
    achados = {}
    for s in servidores:
        if (s.get("descricaoCargo") or "").upper() == "DEPUTADO ESTADUAL" and (s.get("situacao") or "").upper() == "ATIVO":
            achados[s["matricula"]] = s
    return list(achados.values())


def deputados_do_tse() -> list[dict]:
    return comum.eleitos_tse(TSE_ARQUIVO)


def montar_deputados(servidores: list[dict], eleitos: list[dict]) -> list[dict]:
    tse = [{"id": e["sequencial"], "nome": e.get("urna") or e["nome"], "nomeCivil": e["nome"], "e": e} for e in eleitos]
    ligados = comum.ligar_nomes([s["nome"] for s in servidores], tse)
    por_id = {t["id"]: t["e"] for t in tse}
    lista = []
    for s in servidores:
        e = por_id.get(ligados.get(s["nome"]))
        nome = (e.get("urna") or e["nome"]) if e else (nome_do_gabinete(s.get("descricaoLotacao")) or titulo(s["nome"]))
        lista.append({"id": str(s["matricula"]), "nome": nome, "nomeCivil": titulo(s["nome"]), "foto": None, "email": e.get("email") if e else None,
                      "titular": True, "partido": e.get("partido") if e else None,
                      "fonte": TSE_FICHA.format(e["sequencial"]) if e else f"{PORTAL}servidores"})
    return sorted(lista, key=lambda d: comum.sem_acento(d["nome"]))


def itens_remuneracao(detalhe: dict, id_deputado: str, ano: int) -> list[dict]:
    itens = []
    for f in detalhe.get("dadosFinanceiros") or []:
        if f.get("anoCompetencia") != ano:
            continue
        bruto, descontos = f.get("vencimentos"), f.get("descontos")
        itens.append({"idDeputado": id_deputado, "mes": f["mesCompetencia"], "bruto": bruto,
                      "liquido": round(bruto - descontos, 2) if bruto is not None and descontos is not None else None,
                      "componentes": {"salarioBase": f.get("salarioBase"), "outrosProventos": f.get("outrosProventos"), "descontos": descontos},
                      "folha": f.get("descricaoTipoFolha"), "fonte": f"{PORTAL}servidores"})
    return sorted(itens, key=lambda i: (i["mes"], i["folha"] or ""))


def itens_diarias(registros: list[dict], deputados: list[dict]) -> list[dict]:
    ligados = comum.ligar_nomes({r["nome"] for r in registros if r.get("nome")}, deputados)
    itens = []
    for r in registros:
        if r.get("nome") not in ligados:
            continue
        itens.append({"idDeputado": ligados[r["nome"]], "data": r.get("dataSaida"), "dataFim": r.get("dataRetorno"), "destino": r.get("destino"),
                      "motivo": " ".join((r.get("motivo") or "").split()) or None, "valor": r.get("valorDiarias"), "passagem": r.get("valorPassagem"),
                      "quantidade": r.get("quantidadeDiarias"), "anulado": r.get("valorAnulado"), "situacao": r.get("situacaoCancelamento"),
                      "empenho": r.get("displayEmpenho"), "fonte": f"{PORTAL}diarias"})
    return sorted(itens, key=lambda i: (i["data"] or "", i["idDeputado"]))


def _json(s, caminho: str, ano: int, ignorar_404: bool = False, **params):
    r = s.get(f"{API}{caminho}", params=params or None, headers=cabecalhos(ano), timeout=60)
    if ignorar_404 and r.status_code == 404:
        return {}
    r.raise_for_status()
    return r.json()


def buscar_servidores(s, ano: int) -> list[dict]:
    pagina, tudo = 0, []
    while True:
        r = _json(s, "/servidores", ano, entidade=1, exercicio=ano, cargo="DEPUTADO", page=pagina, size=PAGINA)
        tudo += r["content"]
        if r.get("last", True) or not r["content"]:
            return tudo
        pagina += 1


def buscar_diarias(s, ano: int) -> list[dict]:
    pagina, tudo = 0, []
    while True:
        r = _json(s, "/diarias", ano, entidade=1, exercicio=ano, dataInicial=f"{ano}-01-01", dataFinal=f"{ano}-12-31", page=pagina, size=PAGINA)
        tudo += r["content"]
        if r.get("last", True) or not r["content"]:
            return tudo
        pagina += 1


def coletar() -> None:
    pasta = comum.DADOS / UF
    hoje = date.today()
    s = comum.sessao()
    servidores = deputados_ativos(buscar_servidores(s, hoje.year))
    if not servidores:
        comum.avisar("MT: nenhum deputado ativo na API do portal")
        return
    deputados = montar_deputados(servidores, deputados_do_tse())
    comum.salvar(pasta / "deputados.json", {"fonte": f"{PORTAL}servidores", "host": None, "legislatura": "2023-2027", "deputados": deputados})
    print(f"MT: {len(deputados)} deputados")
    for ano in range(PRIMEIRO_ANO, hoje.year + 1):
        if all(comum.ano_encerrado(ano, hoje, pasta / f"{nome}_{ano}.json") for nome in ("remuneracao", "diarias")):
            continue
        remuneracao = []
        for sv in servidores:
            remuneracao += itens_remuneracao(_json(s, f"/servidores/{sv['matricula']}", ano, ignorar_404=True), str(sv["matricula"]), ano)
        comum.salvar(pasta / f"remuneracao_{ano}.json", {"coletadoEm": hoje.isoformat(), "fonte": f"{PORTAL}servidores", "itens": remuneracao})
        diarias = itens_diarias(buscar_diarias(s, ano), deputados)
        comum.salvar(pasta / f"diarias_{ano}.json", {"coletadoEm": hoje.isoformat(), "fonte": f"{PORTAL}diarias", "itens": diarias})
        print(f"MT: {ano}: remuneração {len(remuneracao)} folhas, diárias {len(diarias)} registros")


def _contrato_servidores(ctx):
    ano = date.today().year
    r = _json(comum.sessao(), "/servidores", ano, entidade=1, exercicio=ano, cargo="DEPUTADO", size=PAGINA)
    ativos = deputados_ativos(r["content"])
    return {"content": ativos[:2], "totalElements": r["totalElements"]}


def _conferir_servidores(registro):
    falhas = []
    if not registro["content"]:
        falhas.append("nenhum deputado ativo em /servidores?cargo=DEPUTADO")
    for s in registro["content"]:
        falhas += comum.campos_vazios(s, ("matricula", "nome", "descricaoCargo", "descricaoLotacao", "situacao"), "servidor")
    return falhas, []


def _contrato_remuneracao(ctx):
    ano = date.today().year
    s = comum.sessao()
    mat = deputados_ativos(_json(s, "/servidores", ano, entidade=1, exercicio=ano, cargo="DEPUTADO", size=PAGINA)["content"])[0]["matricula"]
    d = _json(s, f"/servidores/{mat}", ano)
    return {"matricula": mat, "ano": ano, "dadosFinanceiros": (d.get("dadosFinanceiros") or [])[:3]}


def _conferir_remuneracao(registro):
    falhas = []
    itens = itens_remuneracao({"dadosFinanceiros": registro["dadosFinanceiros"]}, str(registro["matricula"]), registro["ano"])
    if not itens:
        falhas.append("/servidores/{matrícula} sem dadosFinanceiros do ano")
    falhas += ["folha sem vencimentos ou descontos" for i in itens if i["bruto"] is None or i["liquido"] is None]
    return falhas, []


def _contrato_diarias(ctx):
    ano = date.today().year
    r = _json(comum.sessao(), "/diarias", ano, entidade=1, exercicio=ano, dataInicial=f"{ano}-01-01", dataFinal=f"{ano}-12-31", size=3)
    return {"content": r["content"], "totalElements": r["totalElements"]}


def _conferir_diarias(registro):
    falhas = []
    if not registro["content"]:
        falhas.append("/diarias sem registros no ano")
    for r in registro["content"]:
        falhas += comum.campos_vazios(r, ("nome", "dataSaida", "dataRetorno", "destino", "valorDiarias", "motivo"), "diária", vazios=(None, ""))
    return falhas, []


CONTRATOS = [
    {"nome": "estadual_mt_servidores", "fonte": f"{PORTAL}servidores", "buscar": _contrato_servidores, "html": _conferir_servidores},
    {"nome": "estadual_mt_remuneracao", "fonte": f"{PORTAL}servidores", "buscar": _contrato_remuneracao, "html": _conferir_remuneracao},
    {"nome": "estadual_mt_diarias", "fonte": f"{PORTAL}diarias", "buscar": _contrato_diarias, "html": _conferir_diarias},
]


if __name__ == "__main__":
    comum.principal(coletar)
