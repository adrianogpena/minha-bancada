"""
Deputados estaduais de Minas Gerais (ALMG), fora do SAPL.

Fonte: API pública de dados abertos https://dadosabertos.almg.gov.br/api/v2 (JSON, sem login). O portal pede no máximo
2 requisições simultâneas e 1 s entre elas, com bloqueio sem aviso: aqui as chamadas são sequenciais com pausa de 1 s.
  - deputados em exercício: deputados/em_exercicio (id, nome, partido) e deputados/lista_telefonica (nome civil, e-mail)
  - verba indenizatória: prestacao_contas/verbas_indenizatorias/deputados/{id}/datas (meses fechados) e .../{id}/{ano}/{mes}
    (por tipo de despesa, com cada nota em `listaDetalheVerba`). O CSV `verbas-indenizatorias` dos arquivos abertos vem sem
    valores nem emitentes (só código, tipo e mês), por isso não é usado.
  - proposições: proposicoes/pesquisa/direcionada?ini=&fim=&tp=100&p= (uma janela por mês: a API só pagina até 10 mil resultados; autores no campo `autor`: "Deputado Fulano   PARTIDO"; texto em `ementa`, ou em `assunto` nos tipos sem ementa).
    Com `ord=3` a lista vem da última ação mais recente para a mais antiga (`dataUltimaAcao`): a coleta diária lê só as primeiras
    páginas, até chegar na data da coleta anterior, e a coleta completa por janelas mensais só se repete a cada RENOVAR_COMPLETA_DIAS.

Não existe na API (Swagger conferido): remuneração, presença e votações nominais. A ALMG não publica salários nominais.
Não coletado: foto (a API não traz URL), comissões, pronunciamentos, reuniões do plenário.
"""

import re
import time
from datetime import date, timedelta

import estaduais_comum as comum
import identidades

UF = "MG"
API = "https://dadosabertos.almg.gov.br/api/v2"
EM_EXERCICIO_URL = f"{API}/deputados/em_exercicio?formato=json"
VERBA_PAGINA = "https://www.almg.gov.br/transparencia/prestacao-de-contas/deputados/verba-indenizatoria/"
PROPOSICOES_PAGINA = "https://www.almg.gov.br/atividade-parlamentar/projetos-de-lei/texto/"
PAUSA = 1.0
TAMANHO_PAGINA = 100
PRIMEIRO_ANO_VERBA = 2025
PRIMEIRO_ANO_PROPOSICOES = 2023
MESES_RECENTES = 2
LIMITE_EMENTA = 400
RENOVAR_COMPLETA_DIAS = 14   # de tempos em tempos refaz tudo, por segurança contra o que a leitura incremental não enxergue
ORDEM_ULTIMA_ACAO = 3


def pegar(sessao, caminho: str, **params) -> dict:
    r = sessao.get(f"{API}/{caminho}", params={"formato": "json", **params}, timeout=60)
    time.sleep(PAUSA)
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------- deputados

def ficha_url(id_deputado) -> str:
    return f"{API}/deputados/{id_deputado}?formato=json"


def montar_deputados(em_exercicio: list[dict], telefonica: list[dict]) -> list[dict]:
    por_id = {t["id"]: t for t in telefonica}
    deputados = []
    for d in em_exercicio:
        t = por_id.get(d["id"], {})
        deputados.append({"id": str(d["id"]), "nome": comum.nome_limpo(d["nome"]), "nomeCivil": t.get("nomeServidor") or None, "foto": None,
                          "email": t.get("email") or None, "titular": True, "partido": d.get("partido") or None, "fonte": ficha_url(d["id"])})
    return deputados


# ---------------------------------------------------------------- verba indenizatória

def data_iso(valor) -> str | None:
    return comum.data_iso(valor)


def itens_verba(registros: list[dict], id_deputado: str, mes: int) -> list[dict]:
    itens = []
    for r in registros:
        categoria = r.get("descTipoDespesa") or f"Tipo {r.get('codTipoDespesa')}"
        notas = r.get("listaDetalheVerba") or []
        itens.extend({"idDeputado": id_deputado, "mes": mes, "categoria": n.get("descTipoDespesa") or categoria,
                      **comum.fornecedor(n.get("nomeEmitente"), n.get("cpfCnpj")),
                      "valor": comum.valor_br(n.get("valorReembolsado")), "data": data_iso(n.get("dataEmissao")),
                      "documento": n.get("descDocumento") or None, "fonte": VERBA_PAGINA} for n in notas)
        if not notas:
            itens.append({"idDeputado": id_deputado, "mes": mes, "categoria": categoria, "fornecedor": None, "cnpj": None,
                          "valor": comum.valor_br(r.get("valor")), "data": None, "documento": None, "fonte": VERBA_PAGINA})
    return itens


def meses_fechados(resp: dict) -> list[tuple[int, int]]:
    achados = []
    for f in resp.get("listaFechamentoVerba") or []:
        m = re.match(r"(\d{4})-(\d{2})", f.get("dataReferencia") or "")
        if m:
            achados.append((int(m.group(1)), int(m.group(2))))
    return sorted(achados)


def coletar_verba(sessao, deputados: list[dict], hoje: date, pasta, agora: str) -> None:
    anteriores = {ano: comum.ler(pasta / f"verbas_{ano}.json", {"itens": []})["itens"] for ano in range(PRIMEIRO_ANO_VERBA, hoje.year + 1)}
    novos = comum.meses_recentes(hoje, MESES_RECENTES)
    por_ano = {ano: [i for i in itens if (ano, i["mes"]) not in novos] for ano, itens in anteriores.items()}
    guardados = {(ano, i["idDeputado"], i["mes"]) for ano, itens in por_ano.items() for i in itens}
    for d in deputados:
        try:
            meses = meses_fechados(pegar(sessao, f"prestacao_contas/verbas_indenizatorias/deputados/{d['id']}/datas", atual="true"))
        except Exception as e:
            comum.avisar(f"MG: verba de {d['nome']}: {type(e).__name__}: {str(e)[:120]}")
            continue
        for ano, mes in meses:
            if ano < PRIMEIRO_ANO_VERBA or (ano, d["id"], mes) in guardados:
                continue
            try:
                resp = pegar(sessao, f"prestacao_contas/verbas_indenizatorias/deputados/{d['id']}/{ano}/{mes}")
            except Exception as e:
                comum.avisar(f"MG: verba de {d['nome']} {mes}/{ano}: {type(e).__name__}: {str(e)[:120]}")
                continue
            por_ano[ano] += itens_verba(resp.get("list") or [], d["id"], mes)
    for ano, itens in por_ano.items():
        itens.sort(key=lambda i: (i["mes"], i["idDeputado"], i["data"] or "", i["categoria"]))
        comum.salvar(pasta / f"verbas_{ano}.json", {"coletadoEm": agora, "fonte": VERBA_PAGINA, "itens": itens})
        print(f"MG: {ano} verba {len(itens)} notas")


# ---------------------------------------------------------------- proposições

def autores_deputados(autor: str) -> list[str]:
    nomes = []
    for linha in (autor or "").splitlines():
        m = re.match(r"\s*Deputad[oa]\s+(.+)", linha)
        if m:
            nomes.append(re.split(r"\s{2,}", m.group(1).strip())[0].strip())
    return nomes


def proposicao_url(item: dict) -> str:
    return f"{PROPOSICOES_PAGINA}?tipo={item.get('siglaTipoProjeto')}&num={item.get('numero')}&ano={item.get('ano')}"


def materias(itens: list[dict], deputados: list[dict]) -> dict:
    ids = identidades.ligar_nomes({a for i in itens for a in autores_deputados(i.get("autor"))}, deputados, UF)
    achadas = {}
    for i in itens:
        autores = sorted({ids[a] for a in autores_deputados(i.get("autor")) if a in ids})
        if not autores:
            continue
        ementa = " ".join((i.get("ementa") or i.get("assunto") or "").split())
        if len(ementa) > LIMITE_EMENTA:
            ementa = ementa[:LIMITE_EMENTA].rsplit(" ", 1)[0] + "..."
        url = proposicao_url(i)
        numero, ano = str(i.get("numero") or ""), str(i.get("ano") or "")
        achadas[f"{i['siglaTipoProjeto']}-{numero}-{ano}"] = {
            "tipo": i["siglaTipoProjeto"], "tipoDescricao": i.get("tipoProjeto"), "numero": int(numero) if numero.isdigit() else None,
            "ano": int(ano) if ano.isdigit() else None, "dataApresentacao": data_iso(i.get("dataPublicacao")), "ementa": ementa,
            "situacao": i.get("situacao"), "emTramitacao": (i.get("dominio") == "Tramitação") if i.get("dominio") else None,
            "linkTexto": url, "idsAutores": autores, "idsDeputados": autores, "fonte": url}
    return achadas


def janelas_do_ano(ano: int, hoje: date) -> list[tuple[str, str]]:
    """Uma janela de publicação por mês (AAAAMMDD): a API corta a paginação em 10 mil resultados por consulta."""
    janelas = []
    for mes in range(1, 13):
        inicio = date(ano, mes, 1)
        if inicio > hoje:
            break
        fim = date(ano + (mes == 12), mes % 12 + 1, 1).toordinal() - 1
        janelas.append((inicio.strftime("%Y%m%d"), date.fromordinal(fim).strftime("%Y%m%d")))
    return janelas


def proposicoes_da_janela(sessao, ini: str, fim: str) -> list[dict]:
    itens, pagina = [], 1
    while True:
        r = pegar(sessao, "proposicoes/pesquisa/direcionada", ini=ini, fim=fim, tp=TAMANHO_PAGINA, p=pagina)["resultado"]
        if r.get("erro"):
            raise RuntimeError(f"erro na página {pagina} de {ini}-{fim}")
        itens += r.get("listaItem") or []
        if len(r.get("listaItem") or []) < TAMANHO_PAGINA or len(itens) >= r.get("noOcorrencias", 0):
            return itens
        pagina += 1


def proposicoes_do_ano(sessao, ano: int, hoje: date) -> list[dict]:
    itens = []
    for ini, fim in janelas_do_ano(ano, hoje):
        itens += proposicoes_da_janela(sessao, ini, fim)
    return itens


# ---------------------------------------------------------------- coleta

def proposicoes_alteradas(sessao, desde: date, hoje: date) -> list[dict]:
    """Proposições com última ação a partir de `desde` (menos 1 dia de folga): a lista vem ordenada por `dataUltimaAcao`, da mais recente para a mais antiga."""
    limite = (desde - timedelta(days=1)).isoformat()
    itens, pagina = [], 1
    while True:
        r = pegar(sessao, "proposicoes/pesquisa/direcionada", ini=f"{PRIMEIRO_ANO_PROPOSICOES}0101", fim=hoje.strftime("%Y%m%d"),
                  tp=TAMANHO_PAGINA, p=pagina, ord=ORDEM_ULTIMA_ACAO)["resultado"]
        if r.get("erro"):
            raise RuntimeError(f"erro na página {pagina} das alteradas")
        lista = r.get("listaItem") or []
        for i in lista:
            if (data_iso(i.get("dataUltimaAcao")) or limite) < limite:
                return itens
            itens.append(i)
        if len(lista) < TAMANHO_PAGINA or len(itens) >= r.get("noOcorrencias", 0):
            return itens
        pagina += 1


def juntar_alteradas(por_ano: dict, novas: dict) -> None:
    """Põe cada matéria nova ou alterada no arquivo do ano de publicação, tirando a versão antiga de onde estiver."""
    for chave, m in novas.items():
        ano = int((m["dataApresentacao"] or "")[:4] or m["ano"] or 0)
        if ano not in por_ano:
            continue
        for materias_ano in por_ano.values():
            materias_ano.pop(chave, None)
        por_ano[ano][chave] = m


def coletar_proposicoes(s, deputados: list[dict], hoje: date, pasta, agora: str) -> None:
    arquivos = {ano: pasta / f"materias_{ano}.json" for ano in range(PRIMEIRO_ANO_PROPOSICOES, hoje.year + 1)}
    atuais = {ano: comum.ler(arq) for ano, arq in arquivos.items()}
    ultimo = atuais[hoje.year] or {}
    completa_em = ultimo.get("completaEm")
    if all(atuais.values()) and completa_em and ultimo.get("coletadoEm") and (hoje - date.fromisoformat(completa_em)).days < RENOVAR_COMPLETA_DIAS:
        try:
            itens = proposicoes_alteradas(s, date.fromisoformat(ultimo["coletadoEm"]), hoje)
            por_ano = {ano: dict(a["materias"]) for ano, a in atuais.items()}
            juntar_alteradas(por_ano, materias(itens, deputados))
        except Exception as e:
            comum.avisar(f"MG: proposições alteradas: {type(e).__name__}: {str(e)[:120]}")
            return
        for ano, achadas in por_ano.items():
            if ano == hoje.year or achadas != atuais[ano]["materias"]:
                comum.salvar(arquivos[ano], {**atuais[ano], "coletadoEm": agora, "materias": achadas})
        print(f"MG: proposições alteradas lidas {len(itens)}")
        return
    for ano, arq in arquivos.items():
        if arq.exists() and ano < hoje.year - 1:
            continue
        try:
            achadas = materias(proposicoes_do_ano(s, ano, hoje), deputados)
        except Exception as e:
            comum.avisar(f"MG: proposições {ano}: {type(e).__name__}: {str(e)[:120]}")
            continue
        comum.salvar(arq, {"coletadoEm": agora, "completaEm": agora, "fonte": PROPOSICOES_PAGINA, "materias": achadas})
        print(f"MG: {ano} proposições {len(achadas)}")


def coletar() -> None:
    pasta = comum.DADOS / UF
    hoje = date.today()
    agora = hoje.isoformat()
    s = comum.sessao()
    em_exercicio = pegar(s, "deputados/em_exercicio").get("list") or []
    telefonica = pegar(s, "deputados/lista_telefonica").get("list") or []
    if not em_exercicio:
        comum.avisar("MG: lista de deputados vazia")
        return
    deputados = montar_deputados(em_exercicio, telefonica)
    comum.salvar(pasta / "deputados.json", {"fonte": EM_EXERCICIO_URL, "host": None, "legislatura": "2023-2027", "deputados": deputados})
    print(f"MG: {len(deputados)} deputados")

    coletar_proposicoes(s, deputados, hoje, pasta, agora)

    coletar_verba(s, deputados, hoje, pasta, agora)


# ---------------------------------------------------------------- contratos

def _contrato_deputados(ctx):
    s = comum.sessao()
    return {"em_exercicio": pegar(s, "deputados/em_exercicio"), "lista_telefonica": pegar(s, "deputados/lista_telefonica")}


def _contrato_verba(ctx):
    s = comum.sessao()
    ident = 12193
    datas = pegar(s, f"prestacao_contas/verbas_indenizatorias/deputados/{ident}/datas", atual="true")
    ano, mes = meses_fechados(datas)[-2]
    return {"datas": datas, "mes": pegar(s, f"prestacao_contas/verbas_indenizatorias/deputados/{ident}/{ano}/{mes}")}


def _contrato_proposicoes(ctx):
    return pegar(comum.sessao(), "proposicoes/pesquisa/direcionada", ano=date.today().year, tipo="PL", tp=3, p=1)


CONTRATOS = [
    {"nome": "estadual_mg_deputados", "fonte": EM_EXERCICIO_URL, "buscar": _contrato_deputados,
         "usados": ["em_exercicio.list[].id", "em_exercicio.list[].nome", "em_exercicio.list[].partido",
                 "lista_telefonica.list[].id", "lista_telefonica.list[].nomeServidor", "lista_telefonica.list[].email"]},
    {"nome": "estadual_mg_verba", "fonte": VERBA_PAGINA, "buscar": _contrato_verba,
         "usados": ["datas.listaFechamentoVerba[].dataReferencia", "mes.list[].descTipoDespesa", "mes.list[].valor",
                 "mes.list[].listaDetalheVerba[].valorReembolsado", "mes.list[].listaDetalheVerba[].nomeEmitente",
                 "mes.list[].listaDetalheVerba[].cpfCnpj", "mes.list[].listaDetalheVerba[].dataEmissao"]},
    {"nome": "estadual_mg_proposicoes", "fonte": f"{API}/proposicoes/pesquisa/direcionada", "buscar": _contrato_proposicoes,
         "usados": ["resultado.noOcorrencias", "resultado.erro", "resultado.listaItem[].siglaTipoProjeto", "resultado.listaItem[].numero",
                 "resultado.listaItem[].ano", "resultado.listaItem[].autor", "resultado.listaItem[].ementa",
                 "resultado.listaItem[].dataPublicacao", "resultado.listaItem[].situacao", "resultado.listaItem[].dominio",
                 "resultado.listaItem[].tipoProjeto"]},
]


if __name__ == "__main__":
    comum.principal(coletar)
