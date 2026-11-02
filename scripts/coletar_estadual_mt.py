"""
Deputados estaduais de Mato Grosso (ALMT), fora do SAPL.

Fonte aberta e lida aqui: a API JSON do Portal da Transparência da ALMT (Elotech), https://almt.eloweb.net/portaltransparencia/1/ ,
que o próprio portal consome em https://almt.eloweb.net/portaltransparencia-api/api/ (sem login; cabeçalhos `entidade: 1` e
`exercicio: <ano>`, aprendidos na aba Rede do Firefox):
  - deputados em exercício: /servidores?cargo=DEPUTADO, cargo "DEPUTADO ESTADUAL" e situação ATIVO (nome civil e matrícula);
    nome parlamentar, partido e e-mail vêm do TSE (eleitos de 2022, dados/tse/2022/MT.json) quando o nome civil casa, senão do nome do gabinete;
  - remuneração mensal: /servidores/{matrícula} (`dadosFinanceiros`: salário-base, vencimentos, descontos, outros proventos);
  - diárias: /diarias?dataInicial&dataFinal, só as linhas cujo nome é o de um deputado (as de assessores "solicitado: gab deputado" ficam de fora).

  - gabinete: /servidores?lotacao=GAB (servidores ativos lotados em "GAB DEP <nome>", ligados ao deputado pelo texto da lotação; id `srv_` da matrícula);
  - contratos e atas de registro de preço do órgão: /contratos (tipoAto 2 = ata), PDFs em /contratos/arquivos e /files/arquivo/{id} (só o link);
    /contratos/ultimas-atualizacoes diz se o ano corrente mudou;
  - regras das diárias: /publicacoes, grupo "Legislações de Diárias" (resolução e tabela, só links).

Sem dado: verbas (/servidores/verbas/{evento}/{mês}) e emendas parlamentares (/emendas-parlamentares) respondem lista vazia; a tela
/cotas-parlamentares não chama nenhuma API de dados.
Não acessado: https://www.al.mt.gov.br (projetos, votações, presença, ficha) não respondeu (timeout) em duas tentativas.
"""

import re
from datetime import date
from functools import partial

import estaduais_comum as comum
import identidades
import ids

UF = "MT"
PORTAL = "https://almt.eloweb.net/portaltransparencia/1/"
API = "https://almt.eloweb.net/portaltransparencia-api/api"
TSE_ARQUIVO = comum.arquivo_tse(UF)
TSE_FICHA = comum.ficha_tse(UF)
PRIMEIRO_ANO = 2023
PAGINA = 500
PEQUENAS = {"de", "da", "do", "das", "dos", "e"}
FONTE_ID = "almt_mt"
CONTRATOS_PAGINA = f"{PORTAL}contratos"
PUBLICACOES_PAGINA = f"{PORTAL}publicacoes"
CONTRATOS_POR_PAGINA = 200
RENOVAR_COMPLETA_DIAS = 14
LOTACAO_DEPUTADO = re.compile(r"^\s*GAB(INETE)?\.?\s+DEP", re.I)
TIPO_ATO = {"contrato": 1, "ata_registro": 2}
ligar = partial(identidades.ligar_nomes, uf=UF)


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
    ligados = identidades.ligar_nomes([s["nome"] for s in servidores], tse, UF)
    por_id = {t["id"]: t["e"] for t in tse}
    lista = []
    for s in servidores:
        e = por_id.get(ligados.get(s["nome"]))
        nome = (e.get("urna") or e["nome"]) if e else (nome_do_gabinete(s.get("descricaoLotacao")) or titulo(s["nome"]))
        lista.append({"id": str(s["matricula"]), "nome": nome, "nomeCivil": titulo(s["nome"]), "foto": None, "email": comum.email(e.get("email")) if e else None,
                      "titular": True, "partido": comum.sigla_partido(e.get("partido")) if e else None,
                      "fonte": TSE_FICHA.format(e["sequencial"]) if e else f"{PORTAL}servidores"})
    return sorted(lista, key=lambda d: comum.sem_acento(d["nome"]))


def itens_remuneracao(detalhe: dict, id_deputado: str, ano: int) -> list[dict]:
    itens = []
    for f in detalhe.get("dadosFinanceiros") or []:
        if f.get("anoCompetencia") != ano:
            continue
        bruto, descontos = f.get("vencimentos"), f.get("descontos")
        itens.append({"idDeputado": id_deputado, "mes": comum.mes_numero(f["mesCompetencia"]), "bruto": bruto,
                      "liquido": round(bruto - descontos, 2) if bruto is not None and descontos is not None else None,
                      "componentes": {"salarioBase": f.get("salarioBase"), "outrosProventos": f.get("outrosProventos"), "descontos": descontos},
                      "folha": f.get("descricaoTipoFolha"), "fonte": f"{PORTAL}servidores"})
    return sorted(itens, key=lambda i: (i["mes"], i["folha"] or ""))


def itens_diarias(registros: list[dict], deputados: list[dict]) -> list[dict]:
    ligados = identidades.ligar_nomes({r["nome"] for r in registros if r.get("nome")}, deputados, UF)
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


# ---------------------------------------------------------------- gabinete

def buscar_gabinete(s, ano: int) -> list[dict]:
    pagina, tudo = 0, []
    while True:
        r = _json(s, "/servidores", ano, entidade=1, exercicio=ano, lotacao="GAB", page=pagina, size=PAGINA)
        tudo += r["content"]
        if r.get("last", True) or not r["content"]:
            return tudo
        pagina += 1


def servidores_do_gabinete(registros: list[dict], deputados: list[dict]) -> list[dict]:
    """Servidores ativos lotados em "GAB DEP <nome>". O filtro `lotacao=GAB` do portal casa por trecho (traz gabinete de presidência e
    unidades) e `situacao` não filtra: ficam só os ativos cuja lotação liga a um único deputado (`ligar`). Sem valores nem datas; o id sai
    da matrícula que a fonte publica."""
    gabinete = {}
    for r in registros:
        lotacao = r.get("descricaoLotacao") or ""
        if LOTACAO_DEPUTADO.match(lotacao) and nome_do_gabinete(lotacao):
            gabinete[lotacao] = nome_do_gabinete(lotacao)
    ligados = ligar(set(gabinete.values()), deputados)
    itens = {}
    for r in registros:
        id_dep = ligados.get(gabinete.get(r.get("descricaoLotacao") or ""))
        if not id_dep or not r.get("matricula") or not r.get("nome") or (r.get("situacao") or "").upper() != "ATIVO":
            continue
        iid = ids.gerar_id("srv", FONTE_ID, r["matricula"])
        itens[iid] = {"id": iid, "idDeputado": id_dep, "matricula": r["matricula"], "nome": titulo(r["nome"]),
                      "cargo": comum.compactar(r.get("descricaoCargo")), "simbolo": comum.compactar(r.get("faixa"))}
    return sorted(itens.values(), key=lambda i: (i["idDeputado"], i["simbolo"] or "", i["nome"], str(i["matricula"])))


def coletar_gabinete(s, pasta, deputados: list[dict], hoje: date) -> None:
    itens = servidores_do_gabinete(buscar_gabinete(s, hoje.year), deputados)
    if not itens:
        raise RuntimeError("nenhum servidor ligado a gabinete de deputado; mantém o arquivo anterior")
    comum.salvar(pasta / "gabinete.json", {"coletadoEm": hoje.isoformat(), "fonte": f"{PORTAL}servidores", "itens": itens})
    print(f"MT: gabinetes {len(itens)} servidores de {len({i['idDeputado'] for i in itens})} deputados")


# ---------------------------------------------------------------- contratos e atas de registro de preço do órgão

def buscar_contratos(s, ano: int) -> list[dict]:
    pagina, tudo = 0, []
    while True:
        r = _json(s, "/contratos", ano, entidade=1, exercicio=ano, page=pagina, size=CONTRATOS_POR_PAGINA)
        tudo += r["content"]
        if r.get("last", True) or not r["content"]:
            return tudo
        pagina += 1


def tipo_do_ato(registro: dict) -> str:
    return "ata_registro" if registro.get("tipoAto") == 2 or "registro" in comum.sem_acento(registro.get("descricaoTipoAto") or "").lower() else "contrato"


def id_fonte_contrato(registro: dict, ano: int) -> str:
    return f"{ano}|{registro['contrato']}"


def link_arquivo(id_arquivo, ano: int) -> str:
    return f"{API}/files/arquivo/{id_arquivo}?entidade=1&exercicio={ano}"


def arquivos_do_contrato(lista: list[dict], ano: int) -> list[dict]:
    return [{"url": link_arquivo(a["idArquivo"], ano), "nome": comum.compactar(a.get("nomeArquivo")), "data": comum.data_iso(a.get("dataPublicacao"))}
            for a in lista or [] if a.get("idArquivo") is not None]


def itens_contratos(registros: list[dict], ano: int, arquivos: dict | None = None) -> dict:
    """{id: item} de contratos e atas de registro do ano (`descricaoTipoAto`; `tipoAto=2` são as atas), no formato de `comum.item_orgao`.
    `arquivos`: {idFonte: [links]} já lidos. Valor contratado como a fonte publica; CPF de contratado não é gravado."""
    itens = {}
    for r in sorted(registros, key=lambda x: str(x.get("contrato"))):
        if r.get("contrato") in (None, "") or not comum.compactar(r.get("nome")):
            continue
        tipo, idf = tipo_do_ato(r), id_fonte_contrato(r, ano)
        iid, item = comum.item_orgao(FONTE_ID, tipo, idf, fornecedor_nome=r["nome"], documento=r.get("cnpjCpf"), valor=r.get("valorContratado"),
                                     inicio=comum.data_iso(r.get("inicioVigencia")), fim=comum.data_iso(r.get("terminoVigencia")),
                                     objeto=r.get("objeto"), numero=comum.compactar(r.get("displayContrato")), arquivos=(arquivos or {}).get(idf, ()),
                                     fonte=CONTRATOS_PAGINA, modalidade=comum.compactar(r.get("descricaoTipoLicitacao")),
                                     numeroModalidade=comum.compactar(r.get("displayLicitacao")), situacao=comum.compactar(r.get("situacao")),
                                     valorAditivo=r.get("valorAditivo"), protocolo=None, diretoria=None)
        itens[iid] = item
    return itens


def buscar_arquivos(s, ano: int, registro: dict) -> list[dict]:
    r = _json(s, "/contratos/arquivos", ano, entidade=1, exercicio=ano, contrato=registro["contrato"], tipoAto=TIPO_ATO[tipo_do_ato(registro)])
    return arquivos_do_contrato(r if isinstance(r, list) else [], ano)


def ultima_atualizacao(s, ano: int) -> str | None:
    """`ultimoAcesso` do módulo de contratos (10); muda quando algo do portal de contratos foi alterado."""
    r = _json(s, "/contratos/ultimas-atualizacoes", ano)
    return next((m.get("ultimoAcesso") for m in r if str(m.get("modulo")) == "10"), None) if isinstance(r, list) else None


def contratos_do_ano(s, pasta, ano: int, hoje: date, atualizacao: str | None) -> None:
    arq = pasta / f"orgao_{ano}.json"
    if comum.ano_encerrado(ano, hoje, arq):
        return
    anterior = comum.ler(arq, {})
    completa_em = anterior.get("completaEm")
    completa_velha = not completa_em or (hoje - date.fromisoformat(completa_em)).days >= RENOVAR_COMPLETA_DIAS
    if anterior.get("itens") and not completa_velha and atualizacao and anterior.get("atualizacao") == atualizacao:
        return
    registros = buscar_contratos(s, ano)
    if not registros and anterior.get("itens"):
        raise RuntimeError(f"/contratos devolveu lista vazia para {ano}; mantém o arquivo anterior")
    antigos = {i["idFonte"]: i["arquivos"] for i in (anterior.get("itens") or {}).values() if i.get("arquivos")}
    arquivos = dict(antigos)
    falhas = 0
    for r in registros:
        idf = id_fonte_contrato(r, ano)
        if idf in antigos or r.get("contrato") in (None, ""):
            continue
        try:
            achados = buscar_arquivos(s, ano, r)
        except comum.PrazoEsgotado:
            raise
        except Exception as e:  # noqa: BLE001
            falhas += 1
            comum.avisar(f"MT: arquivos do contrato {idf}: {e}")
            continue
        if achados:
            arquivos[idf] = achados
    itens = itens_contratos(registros, ano, arquivos)
    comum.salvar(arq, {"coletadoEm": hoje.isoformat(), "completaEm": hoje.isoformat() if completa_velha else completa_em,
                       "atualizacao": atualizacao, "fonte": CONTRATOS_PAGINA, "itens": itens})
    n_atas = sum(i["tipo"] == "ata_registro" for i in itens.values())
    print(f"MT: {ano} contratos {len(itens) - n_atas} e atas de registro {n_atas} do órgão ({falhas} sem link de arquivo)")


def coletar_contratos(s, pasta, hoje: date) -> None:
    atualizacao = ultima_atualizacao(s, hoje.year)
    for ano in range(PRIMEIRO_ANO, hoje.year + 1):
        comum.tentar(UF, f"contratos {ano}", partial(contratos_do_ano, s, pasta, ano, hoje, atualizacao if ano == hoje.year else None))


# ---------------------------------------------------------------- regras das diárias (publicações)

def grupos_por_nome(no, padrao: str) -> list[dict]:
    """Grupos da árvore de /publicacoes (dict com `valor`) cujo nome, sem acento e em minúsculas, casa com `padrao`. Procura pelo nome, não pelo id."""
    achados = []
    if isinstance(no, dict):
        if isinstance(no.get("valor"), str) and re.search(padrao, comum.sem_acento(no["valor"]).lower()):
            achados.append(no)
        for v in no.values():
            achados += grupos_por_nome(v, padrao)
    elif isinstance(no, list):
        for v in no:
            achados += grupos_por_nome(v, padrao)
    return achados


def arquivos_do_grupo(no) -> list[dict]:
    """Arquivos (dict com `idArquivo`) em qualquer nível abaixo do grupo."""
    if isinstance(no, dict):
        achados = [no] if no.get("idArquivo") is not None else []
        for v in no.values():
            achados += arquivos_do_grupo(v)
        return achados
    return [a for v in no for a in arquivos_do_grupo(v)] if isinstance(no, list) else []


GRUPO_DIARIAS = r"legislac\w* de diarias"


def regras_das_diarias(publicacoes, ano: int) -> dict | None:
    """Resolução e tabela das diárias (grupo "Legislações de Diárias") como links; a resolução vem primeiro. None se o grupo sumir."""
    docs = {}
    for g in grupos_por_nome(publicacoes, GRUPO_DIARIAS):
        for a in arquivos_do_grupo(g):
            docs[a["idArquivo"]] = {"titulo": comum.compactar(a.get("nomeArquivo")), "url": link_arquivo(a["idArquivo"], ano),
                                    "ano": int(str(a.get("dataArquivo") or "0000")[:4]) or None, "atualizadoEm": comum.data_iso(a.get("dataArquivo"))}
    if not docs:
        return None
    lista = sorted(docs.values(), key=lambda d: (not re.search(r"resolu", comum.sem_acento(d["titulo"] or "").lower()), -(d["ano"] or 0), d["titulo"] or ""))
    return {"url": lista[0]["url"], "ano": lista[0]["ano"], "titulo": lista[0]["titulo"], "fonte": PUBLICACOES_PAGINA, "documentos": lista}


def coletar_regras(s, pasta, hoje: date) -> None:
    regra = regras_das_diarias(_json(s, "/publicacoes", hoje.year, entidade=1, exercicio=hoje.year), hoje.year)
    if not regra:
        raise RuntimeError('grupo "Legislações de Diárias" não achado em /publicacoes; mantém o arquivo anterior')
    comum.salvar(pasta / "regras_ressarcimento.json", regra)
    print(f"MT: regras das diárias {len(regra['documentos'])} documentos")


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
    comum.rodar_etapas(UF, [("gabinete", lambda: coletar_gabinete(s, pasta, deputados, hoje)),
                            ("contratos e atas de registro do órgão", lambda: coletar_contratos(s, pasta, hoje)),
                            ("regras das diárias", lambda: coletar_regras(s, pasta, hoje))])


def _contrato_gabinete(ctx):
    ano = date.today().year
    r = _json(comum.sessao(), "/servidores", ano, entidade=1, exercicio=ano, lotacao="GAB", size=PAGINA)
    return {"content": [x for x in r["content"] if LOTACAO_DEPUTADO.match(x.get("descricaoLotacao") or "")][:3], "totalElements": r["totalElements"]}


def _conferir_gabinete(registro):
    falhas = []
    if not registro["content"]:
        falhas.append("/servidores?lotacao=GAB sem lotação de deputado")
    for r in registro["content"]:
        falhas += comum.campos_vazios(r, ("matricula", "nome", "descricaoCargo", "descricaoLotacao", "situacao", "faixa"), "servidor de gabinete")
    return falhas, []


def _contrato_contratos(ctx):
    ano = date.today().year
    s = comum.sessao()
    r = _json(s, "/contratos", ano, entidade=1, exercicio=ano, size=CONTRATOS_POR_PAGINA)
    atas = [x for x in r["content"] if tipo_do_ato(x) == "ata_registro"][:1]
    contratos = [x for x in r["content"] if tipo_do_ato(x) == "contrato"][:2]
    arquivos = _json(s, "/contratos/arquivos", ano, entidade=1, exercicio=ano, contrato=atas[0]["contrato"], tipoAto=2) if atas else []
    return {"ano": ano, "content": contratos + atas, "totalElements": r["totalElements"], "arquivos": arquivos,
            "atualizacoes": _json(s, "/contratos/ultimas-atualizacoes", ano)}


def _conferir_contratos(registro):
    falhas = []
    itens = itens_contratos(registro["content"], registro["ano"])
    if not itens:
        falhas.append("/contratos sem contrato nem ata no ano")
    if not any(i["tipo"] == "ata_registro" for i in itens.values()):
        falhas.append("/contratos sem ata de registro de preço (descricaoTipoAto)")
    for r in registro["content"]:
        falhas += comum.campos_vazios(r, ("contrato", "nome", "inicioVigencia", "terminoVigencia", "valorContratado", "objeto", "descricaoTipoAto"), "contrato", vazios=(None, ""))
    if not arquivos_do_contrato(registro["arquivos"], registro["ano"]):
        falhas.append("/contratos/arquivos sem idArquivo")
    if not any(str(m.get("modulo")) == "10" for m in registro["atualizacoes"]):
        falhas.append("/contratos/ultimas-atualizacoes sem o módulo 10")
    return falhas, []


def _contrato_publicacoes(ctx):
    ano = date.today().year
    p = _json(comum.sessao(), "/publicacoes", ano, entidade=1, exercicio=ano)
    return {"ano": ano, "grupos": grupos_por_nome(p, GRUPO_DIARIAS)[:1]}


def _conferir_publicacoes(registro):
    if not regras_das_diarias(registro["grupos"], registro["ano"]):
        return ['/publicacoes sem o grupo "Legislações de Diárias" com arquivos'], []
    return [], []


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
    {"nome": "estadual_mt_gabinete", "fonte": f"{PORTAL}servidores", "buscar": _contrato_gabinete, "html": _conferir_gabinete},
    {"nome": "estadual_mt_contratos", "fonte": CONTRATOS_PAGINA, "buscar": _contrato_contratos, "html": _conferir_contratos},
    {"nome": "estadual_mt_publicacoes", "fonte": PUBLICACOES_PAGINA, "buscar": _contrato_publicacoes, "html": _conferir_publicacoes},
    {"nome": "estadual_mt_remuneracao", "fonte": f"{PORTAL}servidores", "buscar": _contrato_remuneracao, "html": _conferir_remuneracao},
    {"nome": "estadual_mt_diarias", "fonte": f"{PORTAL}diarias", "buscar": _contrato_diarias, "html": _conferir_diarias},
]


if __name__ == "__main__":
    comum.principal(coletar)
