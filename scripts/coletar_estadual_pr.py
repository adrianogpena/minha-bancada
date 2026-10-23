"""
Deputados estaduais do Paraná (ALEP), fora do SAPL.

Fontes lidas aqui (abertas, sem login nem captcha):
  - deputados em exercício (nome, partido, foto, ficha): https://www.assembleia.pr.leg.br/deputados/conheca
  - remuneração por deputado (lista com nome civil e lotação "GAB. DEP. <nome>"; detalhe por matrícula):
    https://transparencia.assembleia.pr.leg.br/api/remuneracao (página /pessoal/parlamentares)
  - diárias de viagem (linhas com cargo "DEPUTADO"/"DEPUTADA", ligadas pelo nome civil): /api/diarias
  - presença em plenário por sessão: /api/presenca/ano (página /plenario/presenca-em-plenario)
  - proposições (autoria só por nome, sem id): POST http://webservices.assembleia.pr.leg.br/api/public/proposicao/filtrar

Não coletado: ressarcimento (cota parlamentar) exige token reCAPTCHA, bloqueado; votações nominais só em PDF por item
(/api/votacoes devolve o PDF da sessão); passagens aéreas e cartões não trazem o deputado.
"""

import difflib
import html as html_lib
import re
import time
from datetime import date
from functools import partial

import requests

import estaduais_comum as comum

UF = "PR"
PORTAL = "https://transparencia.assembleia.pr.leg.br"
SITE = "https://www.assembleia.pr.leg.br"
API_PROPOSICOES = "http://webservices.assembleia.pr.leg.br/api/public"
DEPUTADOS_URL = f"{SITE}/deputados/conheca"
REMUNERACAO_PAGINA = f"{PORTAL}/pessoal/parlamentares"
DIARIAS_PAGINA = f"{PORTAL}/receitas-e-despesas/diarias-de-viagem"
PRESENCA_PAGINA = f"{PORTAL}/plenario/presenca-em-plenario"
PROPOSICOES_PAGINA = "https://consultas.assembleia.pr.leg.br/#/pesquisa-legislativa"
TIPO_REMUNERACAO = "deputado estadual"
PRIMEIRO_ANO = 2023
MESES_RECENTES = 2   # meses de diárias relidos todo dia; os anteriores vêm do arquivo
RELER_ULTIMO_MES_DIAS = 7   # o último mês da remuneração (um POST por deputado) é relido uma vez por semana, para pegar correções
PAUSA = 1.2
LIMITE_EMENTA = 400
SIGLAS = {"PROJETO DE LEI": "PRO", "PROJETO DE LEI COMPLEMENTAR": "PLC", "PROJETO DECRETO LEGISLATIVO": "PDL",
          "PROJETO DE RESOLUÇÃO": "RES", "INDICAÇÃO": "IND", "PROPOSTA DE EMENDA À CONSTITUIÇÃO": "PEC", "PROPOSIÇÃO": "PRP",
          "REQUERIMENTO": "REQ", "EMENDA DE PLENÁRIO": "EPL", "VETO": "VET", "EMENDA DE DEPUTADO": "EDEP",
          "PROCESSO DISCIPLINAR": "PDISC", "SUBSTITUTIVO GERAL": "SUBG"}
EXPANSAO = {"del": "delegado", "delegada": "delegado", "prof": "professor"}
TITULOS = {"dr", "dra", "doutor", "doutora", "secretaria"}
TOTAIS = {"Total Bruto": "bruto", "Valor Bruto (- Descontos Obrigatórios)": "liquido"}


def get_json(sessao, url: str, **params):
    r = sessao.get(url, params=params, headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}, timeout=60)
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------- nomes

def tokens(nome: str) -> list[str]:
    t = re.sub(r"\(.*?\)", " ", nome or "")
    t = comum.sem_acento(comum.nome_limpo(t)).replace(".", " ")
    return [EXPANSAO.get(p, p) for p in t.split() if p not in TITULOS]


def aliases(d: dict) -> list[list[str]]:
    achados = [tokens(d["nome"]), tokens(d.get("nomeCivil") or ""), d["id"].split("-")]
    return [a for a in achados if a]


def ligar(nomes, deputados: list[dict]) -> dict:
    """{nome da fonte: id}. Tenta o nome inteiro (nome, nome civil, ficha); depois "ANA JÚLIA DO PT" sem o partido e, por fim,
    o nome contido em um único deputado ("BAZANA" em "PEDRO PAULO BAZANA"). Ambíguo fica de fora."""
    partidos = {comum.sem_acento(d["partido"]) for d in deputados if d.get("partido")}
    por_alias = [(a, d["id"]) for d in deputados for a in aliases(d)]
    ligados = {}
    for n in nomes:
        t = tokens(n)
        if len(t) > 2 and t[-2] in ("do", "da") and t[-1] in partidos:
            t = t[:-2]
        if not t:
            continue
        ids = {i for a, i in por_alias if a == t}
        if not ids:
            ids = {i for a, i in por_alias if set(t) <= set(a) or set(a) <= set(t)}
        if not ids:
            ids = {i for a, i in por_alias if difflib.SequenceMatcher(None, " ".join(a), " ".join(t)).ratio() >= 0.9}
        if len(ids) == 1:
            ligados[n] = next(iter(ids))
    return ligados


# ---------------------------------------------------------------- deputados

def parse_deputados(texto: str) -> list[dict]:
    achados = []
    for c in re.split(r'<div class="deputado-card', texto)[1:]:
        href = re.search(r'href="[^"]*/deputados/perfil/([^"/]+)"', c)
        nome = re.search(r"<h3[^>]*>\s*(.*?)\s*</h3>", c, re.S)
        if not href or not nome:
            continue
        partido = re.search(r'italic">\s*(.*?)\s*</p>', c, re.S)
        foto = re.search(r'<img src="([^"]+)"', c)
        achados.append({"id": href.group(1), "nome": " ".join(html_lib.unescape(nome.group(1)).split()),
                        "nomeCivil": None, "foto": foto.group(1) if foto else None, "email": None, "titular": True,
                        "partido": " ".join(partido.group(1).split()) if partido else None,
                        "fonte": f"{SITE}/deputados/perfil/{href.group(1)}"})
    return achados


def deputados_com_nome_civil(deputados: list[dict], remuneracoes: list[dict]) -> list[dict]:
    """O nome civil vem da lista de remuneração, cuja lotação é "GAB. DEP. <nome parlamentar>"."""
    gabinete = {r["nome"]: re.sub(r"^\s*GAB\.?\s*(DEP\.?)?\s*", "", r.get("lotacao") or "", flags=re.I) for r in remuneracoes}
    ligados = ligar(set(gabinete.values()), deputados)
    for r in remuneracoes:
        achado = next((d for d in deputados if d["id"] == ligados.get(gabinete[r["nome"]])), None)
        if achado and not achado["nomeCivil"]:
            achado["nomeCivil"] = " ".join(r["nome"].split())
    return deputados


# ---------------------------------------------------------------- remuneração

def componentes(detalhe: dict) -> tuple[dict, float | None, float | None]:
    valores = {}
    for bloco in ("valores", "valores_eventuais"):
        tabela = detalhe.get(bloco) or []
        if len(tabela) == 2:
            for rotulo, v in zip(*tabela, strict=False):
                valores[re.sub(r"\s*\(\d+\)\s*$", "", rotulo)] = comum.valor_br(v)
    bruto = valores.get("Total Bruto")
    liquido = valores.get("Valor Bruto (- Descontos Obrigatórios)")
    itens = {k: v for k, v in valores.items() if k not in TOTAIS and v}
    return itens, bruto, liquido


def detalhe_remuneracao(sessao, r: dict, mes: int, ano: int, cabecalho: dict) -> dict:
    """POST do detalhe; o nginx do portal aceita cerca de 1 requisição por segundo (429), então pausa e tenta de novo."""
    for tentativa in range(6):
        resp = sessao.post(f"{PORTAL}/api/remuneracao/{r['matricula']}", data={"t": TIPO_REMUNERACAO, "mes": mes, "ano": ano, "id": r["id"]},
                           headers=cabecalho, timeout=60)
        if resp.status_code != 429:
            resp.raise_for_status()
            time.sleep(PAUSA)
            return resp.json()
        time.sleep(5 * (tentativa + 1))
    resp.raise_for_status()
    return None


def remuneracao_do_mes(sessao, ano: int, mes: int, deputados: list[dict]) -> list[dict]:
    pagina = sessao.get(REMUNERACAO_PAGINA, timeout=60).text
    token = re.search(r'name="csrf-token" content="([^"]+)"', pagina)
    cabecalho = {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest", "X-CSRF-TOKEN": token.group(1) if token else ""}
    lista, p = [], 1
    while True:
        r = sessao.get(f"{PORTAL}/api/remuneracao", params={"t": TIPO_REMUNERACAO, "mes": mes, "ano": ano, "page": p, "search": "", "searchType": "nome"},
                       headers=cabecalho, timeout=60)
        r.raise_for_status()
        j = r.json()
        lista += j.get("remuneracoes") or []
        if p >= (j.get("last_page") or 0):
            break
        p += 1
    gabinete = {r["id"]: re.sub(r"^\s*GAB\.?\s*(DEP\.?)?\s*", "", r.get("lotacao") or "", flags=re.I) for r in lista}
    ligados = ligar(set(gabinete.values()) | {r["nome"] for r in lista}, deputados)

    def um(r):
        id_dep = ligados.get(gabinete[r["id"]]) or ligados.get(r["nome"])
        if not id_dep:
            return None
        resp = detalhe_remuneracao(sessao, r, mes, ano, cabecalho)
        itens, bruto, liquido = componentes(resp)
        return {"idDeputado": id_dep, "mes": mes, "bruto": bruto, "liquido": liquido, "componentes": itens, "fonte": REMUNERACAO_PAGINA}

    return [i for i in map(um, lista) if i]


def remuneracao_do_ano(sessao, ano: int, deputados: list[dict], anterior: dict, hoje: date) -> tuple[list[dict], dict]:
    """Lê os meses que faltam no arquivo; o último publicado é relido se faz RELER_ULTIMO_MES_DIAS que foi lido.
    Devolve os itens e a marca {mes, dia} da última leitura do último mês."""
    meses = sorted(int(m) for m in (get_json(sessao, f"{PORTAL}/api/remuneracao/meses", ano=ano).get("meses") or {}))
    lido = anterior.get("ultimoMesLidoEm") or {}
    velho = meses and (lido.get("mes") != meses[-1] or (hoje - date.fromisoformat(lido["dia"])).days >= RELER_ULTIMO_MES_DIAS)
    refazer = {meses[-1]} if velho else set()
    itens = [i for i in anterior.get("itens", []) if i["mes"] not in refazer]
    feitos = {i["mes"] for i in itens}
    lidos = [m for m in meses if m not in feitos]
    for mes in lidos:
        itens += remuneracao_do_mes(sessao, ano, mes, deputados)
    marca = {"mes": meses[-1], "dia": hoje.isoformat()} if meses and meses[-1] in lidos else lido
    return sorted(itens, key=lambda i: (i["mes"], i["idDeputado"])), marca


# ---------------------------------------------------------------- diárias

def data_br(texto) -> str | None:
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})$", texto or "")
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None


def itens_diarias(linhas: list[dict], deputados: list[dict]) -> list[dict]:
    do_cargo = [lin for lin in linhas if "DEPUTAD" in (lin.get("cargo_funcao") or "").upper()]
    ligados = ligar({lin["emitido"] for lin in do_cargo}, [{**d, "nome": d["nomeCivil"] or d["nome"]} for d in deputados])
    itens = []
    for lin in do_cargo:
        if lin["emitido"] not in ligados:
            continue
        itens.append({"idDeputado": ligados[lin["emitido"]], "data": data_br(lin.get("data_saida")), "dataRetorno": data_br(lin.get("data_retorno")),
                      "destino": lin.get("destino"), "motivo": lin.get("motivo"), "valor": comum.valor_br(lin.get("valor")),
                      "quantidade": lin.get("quantidade_autorizada"), "protocolo": lin.get("protocolo"), "fonte": DIARIAS_PAGINA})
    return itens


def diarias_do_ano(sessao, ano: int, deputados: list[dict], existentes: list[dict], hoje: date) -> list[dict]:
    """Lê só os meses que faltam no arquivo e os MESES_RECENTES; o resto fica como estava."""
    meses = sorted(int(m) for m in (get_json(sessao, f"{PORTAL}/api/diarias/meses", ano=ano).get("meses") or {}))
    novos = comum.meses_recentes(hoje, MESES_RECENTES)
    itens = [i for i in existentes if i.get("mes") and (ano, i["mes"]) not in novos]
    feitos = {i["mes"] for i in itens}
    for mes in meses:
        if mes not in feitos:
            itens += [{**i, "mes": mes} for i in itens_diarias(get_json(sessao, f"{PORTAL}/api/diarias", ano=ano, mes=mes), deputados)]
    return sorted(itens, key=lambda i: (i["data"] or "", i["idDeputado"], i["protocolo"] or ""))


# ---------------------------------------------------------------- presença

def contar_presenca(sessoes: list[dict]) -> dict:
    """{nome como veio da fonte: {periodo: [presente, licenca, ausente]}}; colunas PRESENTES, JUSTIFICADOS, AUSENTES."""
    contagem: dict = {}
    for s in sessoes:
        m = re.match(r"\d{2}/(\d{2})/(\d{4})$", s.get("data") or "")
        if not m:
            continue
        periodos = (m.group(2), f"{m.group(2)}-{m.group(1)}")
        for linha in (s.get("linhas") or [])[1:]:
            for coluna in range(3):
                nome = " ".join(str(linha[coluna] if len(linha) > coluna else "").split())
                if not nome:
                    continue
                for p in periodos:
                    contagem.setdefault(nome, {}).setdefault(p, [0, 0, 0])[coluna] += 1
    return contagem


def itens_presenca(contagem: dict, deputados: list[dict]) -> list[dict]:
    ligados = ligar(contagem, deputados)
    somas: dict = {}
    for nome, periodos in contagem.items():
        if nome not in ligados:
            continue
        for p, (presente, licenca, ausente) in periodos.items():
            soma = somas.setdefault((ligados[nome], p), [0, 0, 0])
            for i, v in enumerate((presente, licenca, ausente)):
                soma[i] += v
    return [{"idDeputado": i, "periodo": p, "presente": s[0], "ausente": s[2], "licenca": s[1], "totalSessoes": sum(s), "fonte": PRESENCA_PAGINA}
            for (i, p), s in sorted(somas.items())]


# ---------------------------------------------------------------- proposições

def autores_deputados(autor: str) -> list[str]:
    return [a.strip() for a in (autor or "").split(",") if re.match(r"\s*DEPUTAD[OA]\b", a, re.I)]


def materias(lista: list[dict], deputados: list[dict]) -> dict:
    nomes = {a for p in lista for a in autores_deputados(p.get("autor"))}
    ids = ligar(nomes, deputados)
    achadas = {}
    for p in lista:
        autores = sorted({ids[a] for a in autores_deputados(p.get("autor")) if a in ids})
        if not autores:
            continue
        ementa = " ".join((p.get("ementa") or "").split())
        if len(ementa) > LIMITE_EMENTA:
            ementa = ementa[:LIMITE_EMENTA].rsplit(" ", 1)[0] + "..."
        tipo = (p.get("tipoProposicao") or "").strip()
        status = p.get("status")
        achadas[str(p["codigo"])] = {
            "tipo": SIGLAS.get(tipo, tipo[:4].upper()), "tipoDescricao": tipo.title(), "numero": p.get("numero"), "ano": p.get("ano"),
            "dataApresentacao": (p.get("dataRecebimento") or "")[:10] or None, "ementa": ementa, "situacao": status,
            "emTramitacao": status == "TRAMITANDO" if status else None, "linkTexto": None, "idsAutores": autores, "idsDeputados": autores,
            "fonte": PROPOSICOES_PAGINA}
    return achadas


def proposicoes_do_ano(sessao, ano: int) -> list[dict]:
    for tentativa in range(3):
        try:
            r = sessao.post(f"{API_PROPOSICOES}/proposicao/filtrar", json={"ano": ano}, timeout=180)
            r.raise_for_status()
            j = r.json()
            break
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError):
            if tentativa == 2:
                raise
            time.sleep(15)
    if not j.get("sucesso"):
        raise RuntimeError(f"proposicao/filtrar {ano}: {str(j.get('erro'))[:120]}")
    return j.get("lista") or []


# ---------------------------------------------------------------- coleta

def coletar() -> None:
    pasta = comum.DADOS / UF
    hoje = date.today()
    agora = hoje.isoformat()
    s = comum.sessao()
    r = s.get(DEPUTADOS_URL, timeout=60)
    r.raise_for_status()
    deputados = parse_deputados(r.content.decode("utf-8"))
    if not deputados:
        comum.avisar("PR: lista de deputados vazia")
        return
    meses = get_json(s, f"{PORTAL}/api/remuneracao/meses", ano=hoje.year).get("meses") or {}
    if meses:
        ultimo = max(int(m) for m in meses)
        lista_mes = get_json(s, f"{PORTAL}/api/remuneracao", t=TIPO_REMUNERACAO, mes=ultimo, ano=hoje.year, page=1, search="", searchType="nome")
        deputados = deputados_com_nome_civil(deputados, lista_mes.get("remuneracoes") or [])
    sem_civil = [d["nome"] for d in deputados if not d["nomeCivil"]]
    if sem_civil:
        comum.avisar(f"PR: sem nome civil (sem diárias): {', '.join(sem_civil)}")
    comum.salvar(pasta / "deputados.json", {"fonte": DEPUTADOS_URL, "host": None, "legislatura": "2023-2027", "deputados": deputados})
    print(f"PR: {len(deputados)} deputados")

    tentar = partial(comum.tentar, UF)

    def proposicoes(ano):
        if comum.ano_encerrado(ano, hoje, pasta / f"materias_{ano}.json"):
            return
        achadas = materias(proposicoes_do_ano(s, ano), deputados)
        comum.salvar(pasta / f"materias_{ano}.json", {"coletadoEm": agora, "fonte": PROPOSICOES_PAGINA, "materias": achadas})
        print(f"PR: {ano} proposições {len(achadas)}")

    def diarias(ano):
        arq = pasta / f"diarias_{ano}.json"
        if comum.ano_encerrado(ano, hoje, arq):
            return
        itens = diarias_do_ano(s, ano, deputados, comum.ler(arq, {"itens": []})["itens"], hoje)
        comum.salvar(arq, {"coletadoEm": agora, "fonte": DIARIAS_PAGINA, "itens": itens})
        print(f"PR: {ano} diárias {len(itens)}")

    def remuneracao(ano):
        arq = pasta / f"remuneracao_{ano}.json"
        itens, marca = remuneracao_do_ano(s, ano, deputados, comum.ler(arq, {"itens": []}), hoje)
        comum.salvar(arq, {"coletadoEm": agora, "fonte": REMUNERACAO_PAGINA, "ultimoMesLidoEm": marca, "itens": itens})
        print(f"PR: {ano} remuneração {len(itens)} linhas")

    def presenca():
        arq = pasta / "presenca.json"
        guardados = [i for i in comum.ler(arq, {"itens": []})["itens"] if int(i["periodo"][:4]) < hoje.year - 1]
        primeiro = hoje.year - 1 if guardados else PRIMEIRO_ANO   # anos encerrados não mudam: vêm do arquivo
        sessoes = []
        for ano in range(primeiro, hoje.year + 1):
            sessoes += get_json(s, f"{PORTAL}/api/presenca/ano", ano=ano).get("sessoes") or []
        itens = guardados + itens_presenca(contar_presenca(sessoes), deputados)
        comum.salvar(arq, {"coletadoEm": agora, "fonte": PRESENCA_PAGINA, "itens": itens})
        print(f"PR: presença {len(itens)} linhas")

    for ano in range(PRIMEIRO_ANO, hoje.year + 1):
        tentar(f"proposições {ano}", partial(proposicoes, ano))
        tentar(f"diárias {ano}", partial(diarias, ano))
        if ano == hoje.year:
            tentar(f"remuneração {ano}", partial(remuneracao, ano))
    tentar("presença", presenca)


# ---------------------------------------------------------------- contratos

def _contrato_deputados(ctx):
    r = comum.sessao().get(DEPUTADOS_URL, timeout=60)
    r.raise_for_status()
    cartoes = re.split(r'(?=<div class="deputado-card)', r.content.decode("utf-8"))[1:3]
    return {"html": "".join(cartoes)}


def _conferir_deputados(registro):
    achados = parse_deputados(registro["html"])
    falhas = [] if achados else ["nenhum deputado na página"]
    for d in achados:
        falhas += comum.campos_vazios(d, ("id", "nome", "partido", "foto"), "deputado")
    return falhas, []


def _contrato_remuneracao(ctx):
    s = comum.sessao()
    ano = date.today().year
    meses = get_json(s, f"{PORTAL}/api/remuneracao/meses", ano=ano)
    mes = max(int(m) for m in meses["meses"])
    lista = get_json(s, f"{PORTAL}/api/remuneracao", t=TIPO_REMUNERACAO, mes=mes, ano=ano, page=1, search="", searchType="nome")
    pagina = s.get(REMUNERACAO_PAGINA, timeout=60).text
    token = re.search(r'name="csrf-token" content="([^"]+)"', pagina).group(1)
    primeiro = lista["remuneracoes"][0]
    detalhe = s.post(f"{PORTAL}/api/remuneracao/{primeiro['matricula']}", data={"t": TIPO_REMUNERACAO, "mes": mes, "ano": ano, "id": primeiro["id"]},
                     headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest", "X-CSRF-TOKEN": token}, timeout=60)
    detalhe.raise_for_status()
    return {"meses": meses, "remuneracoes": lista["remuneracoes"][:2], "detalhe": detalhe.json()}


def _conferir_remuneracao(registro):
    falhas = []
    for r in registro["remuneracoes"]:
        falhas += comum.campos_vazios(r, ("id", "matricula", "nome", "lotacao", "valor"), "remuneração", vazios=(None, ""))
    itens, bruto, liquido = componentes(registro["detalhe"])
    if bruto is None or liquido is None:
        falhas.append("detalhe sem Total Bruto ou Valor Bruto (- Descontos)")
    return falhas or ([] if registro["remuneracoes"] else ["lista vazia"]), []


def _contrato_diarias(ctx):
    s = comum.sessao()
    ano = date.today().year
    meses = get_json(s, f"{PORTAL}/api/diarias/meses", ano=ano)
    achados = []
    for mes in sorted((int(m) for m in meses["meses"]), reverse=True):
        linhas = get_json(s, f"{PORTAL}/api/diarias", ano=ano, mes=mes)
        achados += [lin for lin in linhas if "DEPUTAD" in (lin.get("cargo_funcao") or "").upper()]
        if len(achados) >= 2:
            break
    return {"meses": meses, "linhas": achados[:2]}


def _conferir_diarias(registro):
    falhas = [] if registro["linhas"] else ["nenhuma diária de deputado"]
    for lin in registro["linhas"]:
        falhas += comum.campos_vazios(lin, ("emitido", "data_saida", "valor", "destino", "motivo", "cargo_funcao"), "diária", vazios=(None, ""))
    return falhas, []


def _contrato_presenca(ctx):
    s = comum.sessao()
    ano = date.today().year
    sessoes = get_json(s, f"{PORTAL}/api/presenca/ano", ano=ano).get("sessoes") or []
    return {"sessoes": [{"data": x["data"], "linhas": x["linhas"][:4]} for x in sessoes[:2]]}


def _conferir_presenca(registro):
    falhas = [] if registro["sessoes"] else ["nenhuma sessão"]
    for s in registro["sessoes"]:
        if not re.match(r"\d{2}/\d{2}/\d{4}$", s.get("data") or ""):
            falhas.append("sessão sem data")
        if [c.strip().upper() for c in s["linhas"][0][:3]] != ["PRESENTES", "JUSTIFICADOS", "AUSENTES"]:
            falhas.append("colunas da presença mudaram")
    return falhas, []


def _contrato_proposicoes(ctx):
    s = comum.sessao()
    lista = proposicoes_do_ano(s, date.today().year - 1)
    com_deputado = [p for p in lista if autores_deputados(p.get("autor"))]
    return {"lista": com_deputado[:3]}


def _conferir_proposicoes(registro):
    falhas = [] if registro["lista"] else ["nenhuma proposição"]
    for p in registro["lista"]:
        falhas += comum.campos_vazios(p, ("codigo", "numero", "ano", "autor", "dataRecebimento", "tipoProposicao", "ementa", "status"), "proposição", vazios=(None, ""))
        if (p.get("tipoProposicao") or "").strip() not in SIGLAS:
            falhas.append(f"tipo de proposição novo: {p.get('tipoProposicao')}")
    return falhas, []


CONTRATOS = [
    {"nome": "estadual_pr_deputados", "fonte": DEPUTADOS_URL, "buscar": _contrato_deputados, "html": _conferir_deputados},
    {"nome": "estadual_pr_remuneracao", "fonte": f"{PORTAL}/api/remuneracao", "buscar": _contrato_remuneracao, "html": _conferir_remuneracao},
    {"nome": "estadual_pr_diarias", "fonte": f"{PORTAL}/api/diarias", "buscar": _contrato_diarias, "html": _conferir_diarias},
    {"nome": "estadual_pr_presenca", "fonte": f"{PORTAL}/api/presenca/ano", "buscar": _contrato_presenca, "html": _conferir_presenca},
    {"nome": "estadual_pr_proposicoes", "fonte": f"{API_PROPOSICOES}/proposicao/filtrar", "buscar": _contrato_proposicoes, "html": _conferir_proposicoes},
]


if __name__ == "__main__":
    comum.principal(coletar)
