"""
Deputados estaduais do Paraná (ALEP), fora do SAPL.

Fontes lidas aqui (abertas, sem login nem captcha):
  - deputados em exercício (nome, partido, foto, ficha): https://www.assembleia.pr.leg.br/deputados/conheca
  - remuneração por deputado (lista com nome civil e lotação "GAB. DEP. <nome>"; detalhe por matrícula):
    https://transparencia.assembleia.pr.leg.br/api/remuneracao (página /pessoal/parlamentares)
  - diárias de viagem (linhas com cargo "DEPUTADO"/"DEPUTADA", ligadas pelo nome civil): /api/diarias
  - presença em plenário por sessão: /api/presenca/ano (página /plenario/presenca-em-plenario)
  - proposições (autoria só por nome, sem id): POST http://webservices.assembleia.pr.leg.br/api/public/proposicao/filtrar
  - normas legais (leis, decretos legislativos, resoluções; autoria só por nome): POST .../norma-legal/filtrar
  - voto nominal por deputado: /api/votacoes/{meses,datas,sessoes} (a sessão vem pelo dia, `data=06`), /api/votacoes (PDF de cada item)
    e /api/votacoes/dados-abertos?sessao=<id> (JSON com a URL do ZIP no storage2; uma planilha por item, uma linha por deputado)

Só 2026 (`PRIMEIRO_ANO`): os arquivos de 2023 a 2025 que já existem ficam como estão e continuam valendo no site, mas não são
relidos nem criados de novo.

Votações, leitura incremental: sessão com ZIP já lido não é baixada de novo; sessão sem ZIP (o arquivo sai com atraso, e há
sessões extraordinárias e audiências sem planilha) é conferida de novo nos últimos RELER_SEM_ZIP_DIAS dias; a cada
RENOVAR_COMPLETA_DIAS a coleta lista todos os meses do ano (a diária só lista os recentes) e confere também as sem ZIP antigas e as
que tinham nome sem deputado ligado. Proposições e normas são lidas inteiras (o ano de 2026 inteiro leva ~2 s: o filtro
`dataInicial` do webservice não segue a data de recebimento, então não vale como incremental).

Não coletado: ressarcimento (cota parlamentar) exige token reCAPTCHA, bloqueado; votação simbólica e item sem planilha (só o PDF);
passagens aéreas e cartões não trazem o deputado.
"""

import html as html_lib
import io
import re
import time
import zipfile
from datetime import date, timedelta
from functools import partial

import requests

import estaduais_comum as comum
import identidades
import ids

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
NORMAS_PAGINA = PROPOSICOES_PAGINA
VOTACOES_API = f"{PORTAL}/api/votacoes"
PRIMEIRO_ANO = 2026   # só 2026; o que já existe de 2023 a 2025 fica como está
FONTE_ID = "alep_pr"
RELER_SEM_ZIP_DIAS = 45   # sessão sem ZIP é conferida de novo até esta idade (o ZIP sai com atraso)
RENOVAR_COMPLETA_DIAS = 14   # de tempos em tempos lista o ano todo, por segurança contra o que a leitura incremental não enxergue
MESES_RECENTES = 2   # meses de diárias relidos todo dia; os anteriores vêm do arquivo
RELER_ULTIMO_MES_DIAS = 7   # o último mês da remuneração (um POST por deputado) é relido uma vez por semana, para pegar correções
PAUSA = 1.2
LIMITE_EMENTA = 400
SIGLAS = {"PROJETO DE LEI": "PRO", "PROJETO DE LEI COMPLEMENTAR": "PLC", "PROJETO DECRETO LEGISLATIVO": "PDL",
          "PROJETO DE RESOLUÇÃO": "RES", "INDICAÇÃO": "IND", "PROPOSTA DE EMENDA À CONSTITUIÇÃO": "PEC", "PROPOSIÇÃO": "PRP",
          "REQUERIMENTO": "REQ", "EMENDA DE PLENÁRIO": "EPL", "VETO": "VET", "EMENDA DE DEPUTADO": "EDEP",
          "PROCESSO DISCIPLINAR": "PDISC", "SUBSTITUTIVO GERAL": "SUBG"}
TOTAIS = {"Total Bruto": "bruto", "Valor Bruto (- Descontos Obrigatórios)": "liquido"}


def get_json(s, url: str, **params):
    r = s.get(url, params=params, headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}, timeout=60)
    r.raise_for_status()
    return r.json()


ligar = partial(identidades.ligar_nomes, uf=UF)


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
                        "partido": comum.sigla_partido(partido.group(1)) if partido else None,
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
            "dataApresentacao": comum.data_iso(p.get("dataRecebimento")), "ementa": ementa, "situacao": status,
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


# ---------------------------------------------------------------- normas legais

def normas_do_ano(sessao, ano: int) -> list[dict]:
    r = sessao.post(f"{API_PROPOSICOES}/norma-legal/filtrar", json={"ano": ano}, timeout=180)
    r.raise_for_status()
    j = r.json()
    if not j.get("sucesso"):
        raise RuntimeError(f"norma-legal/filtrar {ano}: {str(j.get('erro'))[:120]}")
    return j.get("lista") or []


def normas(lista: list[dict], deputados: list[dict]) -> dict:
    """{código da norma: dados}, só as de autoria de deputado (autor vem como texto, ligado pelo nome)."""
    ids_por_nome = ligar({a for n in lista for a in autores_deputados(n.get("autores"))}, deputados)
    achadas = {}
    for n in lista:
        autores = sorted({ids_por_nome[a] for a in autores_deputados(n.get("autores")) if a in ids_por_nome})
        if not autores:
            continue
        ementa = " ".join((n.get("ementa") or "").split())
        if len(ementa) > LIMITE_EMENTA:
            ementa = ementa[:LIMITE_EMENTA].rsplit(" ", 1)[0] + "..."
        achadas[str(n["codigo"])] = {
            "tipo": (n.get("descricaoTipoNormaLegal") or "").strip().title(), "numero": n.get("numero"), "ano": n.get("ano"),
            "data": comum.data_iso(n.get("data")), "ementa": ementa, "situacao": n.get("tipoMovimentacao"),
            "idsDeputados": autores, "fonte": NORMAS_PAGINA}
    return achadas


# ---------------------------------------------------------------- votação nominal

def votacao_da_planilha(linhas: list[dict]) -> dict | None:
    """Uma planilha de item votado (cabeçalho em A/B, depois PARLAMENTAR/PARTIDO/VOTO); None se a votação não for nominal."""
    cab: dict = {}
    votos: list[tuple[str, str]] = []
    em_votos = False
    for i, lin in enumerate(linhas):
        a = lin.get("A", "")
        if em_votos:
            if a and lin.get("C"):
                votos.append((" ".join(a.split()), lin["C"].strip()))
        elif a.upper() == "PARLAMENTAR":
            em_votos = True
        elif i == 0 and a.upper().startswith("ITEM"):
            cab["ITEM"], cab["TITULO"] = a[4:].strip(), lin.get("B", "")
        else:
            cab[a.rstrip(":").strip().upper()] = lin.get("B", "")
    if (cab.get("TIPO VOTAÇÃO") or "").upper() != "NOMINAL" or not votos:
        return None
    return {"item": cab.get("ITEM"), "titulo": cab.get("TITULO", ""), "modelo": cab.get("MODELO"), "ementa": cab.get("EMENTA"),
            "resultado": cab.get("RESULTADO DA VOTAÇÃO"), "votos": votos,
            "apuracao": {"sim": cab.get("VOTOS SIM"), "nao": cab.get("VOTO NÃO"), "abstencao": cab.get("VOTO ABSTER")}}


def voto_normalizado(texto: str) -> str:
    return {"sim": "sim", "nao": "não", "abster": "abstenção", "abstencao": "abstenção"}.get(comum.sem_acento(texto).lower(), texto.lower())


def aprovada(resultado: str | None) -> bool | None:
    r = comum.sem_acento(resultado or "").upper()
    if r.startswith(("NAO APROV", "REJEIT", "REPROV", "PREJUDIC", "DERROT")):
        return False
    if r.startswith("APROV"):
        return True
    return None


def votacoes_do_zip(conteudo: bytes, sessao: str, data: str, pdfs: dict, url_zip: str, deputados: list[dict]) -> tuple[dict, dict, set]:
    """(votações, matérias votadas, nomes sem deputado ligado) de um ZIP de sessão, uma planilha por item.
    Id da votação: `ids.gerar_id("vot", "alep_pr", "<sessão>|<id do item no nome do arquivo>")`; o voto de nome sem par não é gravado."""
    lidas = []
    with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
        for nome in sorted(z.namelist()):
            if not nome.lower().endswith(".xlsx"):
                continue
            v = votacao_da_planilha(comum.xlsx_linhas(z.read(nome)))
            m = re.search(r"ITEM-[^-]+-(\d+)-", nome)
            if v:
                lidas.append((m.group(1) if m else nome, v))
    ligacao = ligar({n for _, v in lidas for n, _ in v["votos"]}, [{**d, "nome": d["nomeCivil"] or d["nome"]} for d in deputados])
    sem_par = {n for _, v in lidas for n, _ in v["votos"] if n not in ligacao}
    votacoes, materias_votadas = {}, {}
    for chave, v in sorted(lidas, key=lambda x: x[0]):
        vid = ids.gerar_id("vot", FONTE_ID, f"{sessao}|{chave}")
        votos = [[ligacao[n], voto_normalizado(x)] for n, x in v["votos"] if n in ligacao]
        numero_item = re.match(r"\d+", v["item"] or "")
        pdf = pdfs.get(numero_item.group(0)) if numero_item else None
        contagem = {k: int(v["apuracao"][k]) if str(v["apuracao"].get(k) or "").isdigit() else sum(1 for _, x in v["votos"] if voto_normalizado(x) == nome)
                    for k, nome in (("sim", "sim"), ("nao", "não"), ("abstencao", "abstenção"))}
        votacoes[vid] = {"data": data, "idMateria": vid, "aprovada": aprovada(v["resultado"]), "resultado": v["resultado"],
                         "sim": contagem["sim"], "nao": contagem["nao"], "abstencoes": contagem["abstencao"], "votos": votos,
                         "fonte": pdf or url_zip, "fonteZip": url_zip, "sessao": sessao}
        t = re.match(r"(.*?)\s+(\d+)/(\d{4})$", " ".join(v["titulo"].split()))
        tipo = (t.group(1) if t else v["titulo"]).strip()
        modelo = f" ({v['modelo'].lower()})" if v.get("modelo") else ""
        materias_votadas[vid] = {"tipo": SIGLAS.get(tipo, tipo[:4].upper()), "tipoDescricao": tipo.capitalize() + modelo,
                                 "numero": int(t.group(2)) if t else None, "ano": int(t.group(3)) if t else None, "ementa": v["ementa"] or None}
    return votacoes, materias_votadas, sem_par


def precisa_ler(estado: dict | None, data: str, hoje: date, completa: bool) -> bool:
    """Sessão nova lê; com ZIP já lido só relê na coleta completa e se ficou nome sem par; sem ZIP, até RELER_SEM_ZIP_DIAS de idade."""
    if estado is None:
        return True
    if estado["zip"]:
        return completa and bool(estado.get("semPar"))
    return completa or (hoje - date.fromisoformat(data)).days <= RELER_SEM_ZIP_DIAS


def sessoes_do_ano(sessao, ano: int, hoje: date, completa: bool) -> list[tuple[str, str, int, str]]:
    """[(id da sessão, data ISO, mês, dia)]: todos os meses na coleta completa; senão só os de RELER_SEM_ZIP_DIAS atrás até agora."""
    meses = sorted(int(m) for m in (get_json(sessao, f"{VOTACOES_API}/meses", ano=ano).get("meses") or {}))
    corte = hoje - timedelta(days=RELER_SEM_ZIP_DIAS)
    achadas = []
    for mes in meses:
        if not completa and (ano, mes) < (corte.year, corte.month):
            continue
        for dia in get_json(sessao, f"{VOTACOES_API}/datas", ano=ano, mes=mes):
            for sid in get_json(sessao, f"{VOTACOES_API}/sessoes", ano=ano, mes=mes, data=dia):
                achadas.append((str(sid), f"{ano:04d}-{mes:02d}-{int(dia):02d}", mes, dia))
    return achadas


def zip_da_sessao(sessao, sid: str) -> str | None:
    r = sessao.get(f"{VOTACOES_API}/dados-abertos", params={"sessao": sid}, headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}, timeout=60)
    if r.status_code >= 500:
        r.raise_for_status()
    try:
        return r.json().get("arquivo") or None
    except ValueError:
        return None


def pdfs_da_sessao(sessao, ano: int, mes: int, dia: str, sid: str) -> dict:
    """{número do item: URL do PDF}, para a fonte de cada votação."""
    itens = get_json(sessao, VOTACOES_API, ano=ano, mes=mes, data=dia, sessao=sid)
    return {m.group(1): i["arquivo"] for i in itens if i.get("arquivo") and (m := re.match(r"ITEM\s+(\d+)", i.get("item") or ""))}


def votacoes_do_ano(sessao, ano: int, deputados: list[dict], arquivo: dict, hoje: date) -> tuple[dict, dict, dict, bool]:
    """Devolve (votações, matérias votadas, estado por sessão, coleta completa?) juntando o novo ao que o arquivo já tinha."""
    completa_em = arquivo.get("completaEm")
    completa = not arquivo.get("sessoes") or not completa_em or (hoje - date.fromisoformat(completa_em)).days >= RENOVAR_COMPLETA_DIAS
    votacoes, estado = dict(arquivo.get("votacoes") or {}), dict(arquivo.get("sessoes") or {})
    materias_votadas = dict(arquivo.get("materiasVotadas") or {})
    sem_par: set = set()
    for sid, data, mes, dia in sessoes_do_ano(sessao, ano, hoje, completa):
        if not precisa_ler(estado.get(sid), data, hoje, completa):
            continue
        url_zip = zip_da_sessao(sessao, sid)
        if not url_zip:
            estado[sid] = {"data": data, "zip": False, "lidoEm": hoje.isoformat()}
            continue
        novas, mats, faltou = votacoes_do_zip(comum.baixar(sessao, url_zip, timeout=120), sid, data, pdfs_da_sessao(sessao, ano, mes, dia, sid), url_zip, deputados)
        votacoes = {k: v for k, v in votacoes.items() if v.get("sessao") != sid} | novas
        materias_votadas = {k: v for k, v in materias_votadas.items() if k in votacoes} | mats
        estado[sid] = {"data": data, "zip": True, "lidoEm": hoje.isoformat(), "semPar": len(faltou)}
        sem_par |= faltou
        time.sleep(PAUSA)
    if sem_par:
        comum.avisar(f"PR: votos de nomes sem deputado ligado (não gravados): {', '.join(sorted(sem_par))}")
    return votacoes, materias_votadas, estado, completa


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
        primeiro = max(PRIMEIRO_ANO, hoje.year - 1)   # anos encerrados e anteriores a PRIMEIRO_ANO não são relidos: vêm do arquivo
        guardados = [i for i in comum.ler(arq, {"itens": []})["itens"] if int(i["periodo"][:4]) < primeiro]
        sessoes = []
        for ano in range(primeiro, hoje.year + 1):
            sessoes += get_json(s, f"{PORTAL}/api/presenca/ano", ano=ano).get("sessoes") or []
        itens = guardados + itens_presenca(contar_presenca(sessoes), deputados)
        comum.salvar(arq, {"coletadoEm": agora, "fonte": PRESENCA_PAGINA, "itens": itens})
        print(f"PR: presença {len(itens)} linhas")

    def normas_legais(ano):
        arq = pasta / f"normas_{ano}.json"
        if comum.ano_encerrado(ano, hoje, arq):
            return
        achadas = normas(normas_do_ano(s, ano), deputados)
        comum.salvar(arq, {"coletadoEm": agora, "fonte": NORMAS_PAGINA, "normas": achadas})
        print(f"PR: {ano} normas {len(achadas)}")

    def votacoes(ano):
        arq = pasta / "votacoes.json"
        anterior = comum.ler(arq, {})
        votos, mats, estado, completa = votacoes_do_ano(s, ano, deputados, {**anterior, "materiasVotadas": comum.ler(pasta / "materias_votadas.json", {})}, hoje)
        comum.salvar(arq, {"coletadoEm": agora, "completaEm": agora if completa else anterior.get("completaEm"), "fonte": f"{PORTAL}/plenario/votacoes",
                           "sessoes": estado, "votacoes": votos})
        comum.salvar(pasta / "materias_votadas.json", mats)
        print(f"PR: {ano} votações {len(votos)} em {sum(1 for e in estado.values() if e['zip'])} sessões com ZIP ({len(estado)} no total)")

    for ano in range(PRIMEIRO_ANO, hoje.year + 1):
        tentar(f"proposições {ano}", partial(proposicoes, ano))
        tentar(f"normas {ano}", partial(normas_legais, ano))
        tentar(f"votações {ano}", partial(votacoes, ano))
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


def _contrato_votacoes(ctx):
    s = comum.sessao()
    hoje = date.today()
    for sid, _, mes, dia in reversed(sessoes_do_ano(s, hoje.year, hoje, False)):
        url_zip = zip_da_sessao(s, sid)
        if not url_zip:
            continue
        with zipfile.ZipFile(io.BytesIO(comum.baixar(s, url_zip, timeout=120))) as z:
            nomes = sorted(n for n in z.namelist() if n.lower().endswith(".xlsx"))
            linhas = comum.xlsx_linhas(z.read(nomes[0]))
        itens = get_json(s, VOTACOES_API, ano=hoje.year, mes=mes, data=dia, sessao=sid)
        return {"zip": url_zip, "arquivo": nomes[0], "linhas": linhas[:32], "itens": itens[:3]}
    raise RuntimeError("nenhuma sessão com ZIP este ano")


def _conferir_votacoes(registro):
    falhas = comum.campos_vazios(registro, ("zip", "arquivo", "itens"), "votação", vazios=(None, "", []))
    if not re.search(r"ITEM-[^-]+-\d+-", registro["arquivo"]):
        falhas.append("nome do arquivo sem o id do item")
    v = votacao_da_planilha(registro["linhas"])
    if not v:
        return falhas + ["planilha sem votação nominal"], []
    falhas += comum.campos_vazios(v, ("item", "titulo", "resultado", "ementa"), "votação", vazios=(None, ""))
    if not re.search(r"\d+/\d{4}$", v["titulo"]):
        falhas.append("título do item sem número/ano")
    novos = {voto_normalizado(x) for _, x in v["votos"]} - {"sim", "não", "abstenção", "não votou"}
    if novos:
        falhas.append(f"voto novo: {sorted(novos)}")
    for i in registro["itens"]:
        falhas += comum.campos_vazios(i, ("item",), "item da sessão", vazios=(None, ""))
    return falhas, []


def _contrato_normas(ctx):
    lista = normas_do_ano(comum.sessao(), date.today().year)
    return {"lista": [n for n in lista if autores_deputados(n.get("autores"))][:3]}


def _conferir_normas(registro):
    falhas = [] if registro["lista"] else ["nenhuma norma de deputado"]
    for n in registro["lista"]:
        falhas += comum.campos_vazios(n, ("codigo", "numero", "ano", "data", "ementa", "autores", "descricaoTipoNormaLegal"), "norma", vazios=(None, ""))
    return falhas, []


CONTRATOS = [
    {"nome": "estadual_pr_deputados", "fonte": DEPUTADOS_URL, "buscar": _contrato_deputados, "html": _conferir_deputados},
    {"nome": "estadual_pr_remuneracao", "fonte": f"{PORTAL}/api/remuneracao", "buscar": _contrato_remuneracao, "html": _conferir_remuneracao},
    {"nome": "estadual_pr_diarias", "fonte": f"{PORTAL}/api/diarias", "buscar": _contrato_diarias, "html": _conferir_diarias},
    {"nome": "estadual_pr_presenca", "fonte": f"{PORTAL}/api/presenca/ano", "buscar": _contrato_presenca, "html": _conferir_presenca},
    {"nome": "estadual_pr_proposicoes", "fonte": f"{API_PROPOSICOES}/proposicao/filtrar", "buscar": _contrato_proposicoes, "html": _conferir_proposicoes},
    {"nome": "estadual_pr_votacoes", "fonte": f"{VOTACOES_API}/dados-abertos", "buscar": _contrato_votacoes, "html": _conferir_votacoes},
    {"nome": "estadual_pr_normas", "fonte": f"{API_PROPOSICOES}/norma-legal/filtrar", "buscar": _contrato_normas, "html": _conferir_normas},
]


if __name__ == "__main__":
    comum.principal(coletar)
