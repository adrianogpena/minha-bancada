"""
Deputados estaduais de Goiás (Alego). Grava em dados/estaduais/GO/ (contrato em estaduais_comum.py).

Fontes lidas aqui:
  - lista (nome parlamentar, partido, e-mail) e ficha (nome civil, foto, e-mail): https://portal.al.go.leg.br/deputados/em-exercicio
    e /deputados/perfil/<id> (HTML renderizado no servidor; o id é o mesmo da API de verbas);
  - API JSON pública da Transparência Alego, sem autenticação: https://transparencia.al.go.leg.br/api/transparencia/
      verbas_indenizatorias?ano=&mes=&pagina=   verba indenizatória por deputado e mês (10 por página)
      remuneracoes?ano=&mes=&categoria=7&pagina=   remuneração por nome civil (categoria 7 = Deputados)
      diarias?ano=&favorecido=<nome civil>&pagina=   diárias (a API traz também assessores: filtra-se pelo beneficiário)
      requerimentos?ano=&pagina=   requerimentos com autor (a API só lista até 2023)
      votacoes.json?tipo=detalhes&ano=   um registro por voto nominal (ano inteiro numa resposta)
  - desde 2023 (início da legislatura).

Não coletado: presença (a API só dá datas e pauta das sessões), emendas (não existem na fonte), projetos de lei e outras
proposições (processos/busca-avancada devolve vazio sem os parâmetros certos; busca-simples dá erro 500).
"""

import re
import time
from datetime import date
from html import unescape

import estaduais_comum as comum
import identidades

UF = "GO"
PASTA = comum.DADOS / UF
PORTAL = "https://portal.al.go.leg.br"
LISTA_URL = f"{PORTAL}/deputados/em-exercicio"
PERFIL_URL = f"{PORTAL}/deputados/perfil/{{id}}"
TRANSP = "https://transparencia.al.go.leg.br"
API = f"{TRANSP}/api/transparencia"
VERBA_PAGINA = f"{TRANSP}/gestao-parlamentar/verba-indenizatoria"
VERBA_FONTE = f"{VERBA_PAGINA}/exibir/{{id}}/{{ano}}/{{mes}}"
REMUNERACAO_PAGINA = f"{TRANSP}/prestacao-de-contas/gestao-de-pessoas/quadro-de-remuneracao"
REMUNERACAO_FONTE = f"{REMUNERACAO_PAGINA}?ano={{ano}}&mes={{mes}}&matricula={{matricula}}"
DIARIAS_PAGINA = f"{TRANSP}/prestacao-de-contas/diarias-e-ajudas-de-custo"
DIARIA_FONTE = f"{DIARIAS_PAGINA}/{{id}}"
REQUERIMENTOS_PAGINA = f"{TRANSP}/gestao-parlamentar/assuntos-legislativos/requerimentos"
VOTACOES_PAGINA = f"{TRANSP}/gestao-parlamentar/painel-votacao-parlamentar/votacoes"
ANO_INICIAL = 2023
ANO_REQUERIMENTOS_FINAL = 2023
ANO_INICIAL_REMUNERACAO = 2026   # a API devolve vazio para 2023 a 2025 (conferido em 2026-10-22)
MESES_RECENTES = 2   # meses relidos todo dia; os anteriores já gravados vêm do arquivo
MAX_PAGINAS = 400
TIMEOUT = 90
INTERVALO = 0.8
PAUSA_403 = 20

COMPONENTES_REMUNERACAO = {"vencimento": "Vencimento", "indenizacoes": "Indenizações", "auxilios": "Auxílios",
                           "vantagens_pessoais": "Vantagens pessoais", "vantagens_eventuais": "Vantagens eventuais",
                           "abono_permanencia": "Abono de permanência", "diferencas": "Diferenças", "ferias": "Férias",
                           "decimo_terceiro": "13º salário"}
DESCONTOS_REMUNERACAO = {"desconto_obrigatorios": "Descontos obrigatórios", "desconto_diversos": "Descontos diversos"}
VOTOS = {"SIM": "Sim", "NAO": "Não", "ABSTENCAO": "Abstenção", "OBSTRUCAO": "Obstrução"}


_ULTIMA = [0.0]


def pegar(s, url: str, **params):
    """GET com intervalo mínimo entre pedidos: a API responde 403 a rajadas; nesse caso espera e tenta de novo."""
    for tentativa in range(4):
        espera = INTERVALO - (time.monotonic() - _ULTIMA[0])
        if espera > 0:
            time.sleep(espera)
        r = s.get(url, params=params, timeout=TIMEOUT)
        _ULTIMA[0] = time.monotonic()
        if r.status_code != 403:
            break
        time.sleep(PAUSA_403 * (tentativa + 1))
    r.raise_for_status()
    return r


def pegar_json(s, caminho: str, **params):
    return pegar(s, f"{API}/{caminho}", **params).json()


def paginar(s, caminho: str, **params) -> list:
    """Junta as páginas (`pagina=1, 2, ...`, 10 itens cada) até somar `TotalLinhas` ou vir uma vazia ou repetida."""
    itens, vistos = [], set()
    for pagina in range(1, MAX_PAGINAS + 1):
        r = pegar(s, f"{API}/{caminho}", pagina=pagina, **params)
        dados = r.json()
        if not dados:
            break
        chave = dados[0].get("id")
        if chave is not None and chave in vistos:
            break
        vistos.add(chave)
        itens.extend(dados)
        total = r.headers.get("TotalLinhas")
        if total and total.isdigit() and len(itens) >= int(total):
            break
    return itens


def pegar_html(s, url: str) -> str:
    return pegar(s, url).text


def texto_html(trecho: str) -> str:
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", trecho or "")).split())


def sigla_partido(texto: str) -> str | None:
    t = texto_html(texto)
    m = re.search(r"\(([^()]+)\)\s*$", t)
    return (m.group(1) if m else t) or None


def parse_lista(html: str) -> list[dict]:
    """Linhas da tabela de deputados em exercício: id, nome parlamentar, partido (sigla) e e-mail."""
    lista = []
    for trecho in html.split('<tr data-target="search.filterable"')[1:]:
        linha = trecho.split("</tr>", 1)[0]
        m = re.search(r'href="?/deputados/perfil/(\d+)"?>(.*?)</a>', linha, re.S)
        if not m:
            continue
        partido = re.search(r'data-title="Partido">(.*?)</td>', linha, re.S)
        email = re.search(r'href="mailto:([^"]+)"', linha)
        lista.append({"id": m.group(1), "nome": texto_html(m.group(2)), "partido": sigla_partido(partido.group(1)) if partido else None,
                      "email": email.group(1).strip() if email else None})
    return lista


def parse_perfil(html: str) -> dict:
    """Nome civil, foto e e-mail da ficha de um deputado."""
    civil = re.search(r"<b>Nome Civil:</b>\s*<span>(.*?)</span>", html, re.S)
    foto = re.search(r'<img class="foto" src="([^"]+)"', html)
    email = re.search(r"<b>E-mail:</b>\s*<span>(.*?)</span>", html, re.S)
    return {"nomeCivil": texto_html(civil.group(1)) if civil else None, "foto": foto.group(1) if foto else None,
            "email": texto_html(email.group(1)) if email else None}


def montar_deputados(lista: list[dict], perfis: dict) -> list[dict]:
    deputados = []
    for d in lista:
        p = perfis.get(d["id"], {})
        deputados.append({"id": d["id"], "nome": d["nome"], "nomeCivil": p.get("nomeCivil"), "foto": p.get("foto"),
                          "email": p.get("email") or d.get("email"), "titular": True, "partido": d.get("partido"),
                          "fonte": PERFIL_URL.format(id=d["id"])})
    return sorted(deputados, key=lambda d: comum.sem_acento(d["nome"]))


def coletar_deputados(s) -> list[dict]:
    """A ficha (nome civil, foto) só é lida para quem não tem nome civil no `deputados.json` anterior."""
    lista = parse_lista(pegar_html(s, LISTA_URL))
    anteriores = {d["id"]: d for d in (comum.ler(PASTA / "deputados.json") or {}).get("deputados") or [] if d.get("nomeCivil")}
    perfis = {}
    for d in lista:
        if d["id"] in anteriores:
            perfis[d["id"]] = {k: anteriores[d["id"]].get(k) for k in ("nomeCivil", "foto", "email")}
            continue
        try:
            perfis[d["id"]] = parse_perfil(pegar_html(s, PERFIL_URL.format(id=d["id"])))
        except Exception as e:
            comum.avisar(f"GO: ficha de {d['nome']}: {e}")
    return montar_deputados(lista, perfis)


def meses_do_ano(ano: int) -> list[int]:
    hoje = date.today()
    return list(range(1, (hoje.month if ano == hoje.year else 12) + 1))


def anos() -> list[int]:
    return list(range(ANO_INICIAL, date.today().year + 1))


def meses_a_ler(ano: int, existentes: list[dict], hoje: date) -> list[int]:
    """Meses do ano que faltam no arquivo ou estão entre os MESES_RECENTES; os outros ficam como estavam."""
    novos = comum.meses_recentes(hoje, MESES_RECENTES)
    feitos = {i["mes"] for i in existentes if (ano, i["mes"]) not in novos}
    return [m for m in meses_do_ano(ano) if m not in feitos]


def float_ou_zero(v) -> float:
    return comum.valor_br(v) or 0.0


def itens_verba(registros: list[dict], ids: set, ano: int, mes: int) -> list[dict]:
    itens = []
    for r in registros:
        dep = str((r.get("deputado") or {}).get("id"))
        if dep not in ids:
            continue
        itens.append({"idDeputado": dep, "mes": mes, "categoria": "Verba indenizatória", "fornecedor": None, "cnpj": None,
                      "valor": comum.valor_br(r.get("valor_indenizado")), "apresentado": comum.valor_br(r.get("valor_apresentado")),
                      "fonte": VERBA_FONTE.format(id=dep, ano=ano, mes=mes)})
    return itens


def coletar_verbas(s, deputados: list[dict]) -> None:
    ids = {d["id"] for d in deputados}
    hoje = date.today()
    for ano in anos():
        destino = PASTA / f"verbas_{ano}.json"
        if comum.ano_encerrado(ano, hoje, destino):
            continue
        existentes = comum.ler(destino, {"itens": []})["itens"]
        ler = meses_a_ler(ano, existentes, hoje)
        itens = [i for i in existentes if i["mes"] not in ler]
        for m in ler:
            itens += itens_verba(paginar(s, "verbas_indenizatorias", ano=ano, mes=m), ids, ano, m)
        itens.sort(key=lambda i: (i["mes"], i["idDeputado"]))
        if itens:
            comum.salvar(destino, {"coletadoEm": hoje.isoformat(), "fonte": VERBA_PAGINA, "itens": itens})
        print(f"GO: verbas {ano}: {len(itens)} lançamentos ({len(ler)} meses lidos)")


def item_remuneracao(r: dict, dep: str, ano: int, mes: int) -> dict:
    componentes = {rotulo: float_ou_zero(r.get(k)) for k, rotulo in COMPONENTES_REMUNERACAO.items() if float_ou_zero(r.get(k))}
    descontos = {rotulo: float_ou_zero(r.get(k)) for k, rotulo in DESCONTOS_REMUNERACAO.items() if float_ou_zero(r.get(k))}
    bruto = round(sum(componentes.values()), 2)
    status = (r.get("status") or "").strip()
    return {"idDeputado": dep, "mes": mes, "bruto": bruto or None, "liquido": comum.valor_br(r.get("remuneracao_liquida")),
            "componentes": componentes, "descontos": descontos, "status": None if status in ("", "-") else status,
            "fonte": REMUNERACAO_FONTE.format(ano=ano, mes=mes, matricula=r.get("matricula"))}


def coletar_remuneracao(s, deputados: list[dict]) -> None:
    hoje = date.today()
    sem_par = set()
    for ano in range(ANO_INICIAL_REMUNERACAO, hoje.year + 1):
        destino = PASTA / f"remuneracao_{ano}.json"
        if comum.ano_encerrado(ano, hoje, destino):
            continue
        existentes = comum.ler(destino, {"itens": []})["itens"]
        ler = meses_a_ler(ano, existentes, hoje)
        itens = [i for i in existentes if i["mes"] not in ler]
        for mes in ler:
            regs = paginar(s, "remuneracoes", ano=ano, mes=mes, categoria=7)
            ligacao = identidades.ligar_nomes({r["nome"] for r in regs}, deputados, UF)
            for r in regs:
                if r["nome"] in ligacao:
                    itens.append(item_remuneracao(r, ligacao[r["nome"]], ano, mes))
                else:
                    sem_par.add(r["nome"])
        itens.sort(key=lambda i: (i["mes"], i["idDeputado"]))
        if itens:
            comum.salvar(destino, {"coletadoEm": hoje.isoformat(), "fonte": REMUNERACAO_PAGINA, "itens": itens})
        print(f"GO: remuneração {ano}: {len(itens)} lançamentos ({len(ler)} meses lidos)")
    if sem_par:
        comum.avisar(f"GO: remuneração sem deputado em exercício ({len(sem_par)}): {sorted(sem_par)[:12]}")


def itens_diarias(registros: list[dict], dep: str, nome_civil: str) -> list[dict]:
    itens = []
    for r in registros:
        if comum.sem_acento(r.get("beneficiario")) != comum.sem_acento(nome_civil) or "DEPUTADO" not in (r.get("cargo") or "").upper():
            continue
        itens.append({"idDeputado": dep, "data": r.get("data_inicio"), "dataFim": r.get("data_fim"), "destino": r.get("trecho"),
                      "motivo": " ".join((r.get("motivo") or "").split()) or None, "valor": comum.valor_br(r.get("total")),
                      "fonte": DIARIA_FONTE.format(id=r.get("id"))})
    return itens


def coletar_diarias(s, deputados: list[dict]) -> None:
    hoje = date.today().isoformat()
    com_nome = [d for d in deputados if d.get("nomeCivil")]
    for ano in anos():
        destino = PASTA / f"diarias_{ano}.json"
        # a consulta é por deputado e ano inteiro (uma volta por todos): só o ano corrente é relido
        if ano < date.today().year and destino.exists():
            continue
        itens = []
        for d in com_nome:
            itens += itens_diarias(paginar(s, "diarias", ano=ano, favorecido=d["nomeCivil"].upper()), d["id"], d["nomeCivil"])
        comum.salvar(destino, {"coletadoEm": hoje, "fonte": DIARIAS_PAGINA, "itens": sorted(itens, key=lambda i: (i["data"] or "", i["idDeputado"]))})
        print(f"GO: diárias {ano}: {len(itens)} lançamentos")


def montar_votacoes(linhas: list[dict], ligacao: dict, ano: int) -> tuple[dict, dict]:
    """Agrupa os votos nominais por pauta (`pauta_id`); voto secreto fica de fora."""
    votacoes, materias = {}, {}
    for lin in linhas:
        if lin.get("tipo_votacao") != "NOMINAL":
            continue
        pauta = str(lin["pauta_id"])
        mes = int(lin.get("mes") or 0)
        v = votacoes.setdefault(pauta, {"data": lin.get("data_sessao"), "idMateria": pauta, "aprovada": (lin.get("resultado_votacao") or "").strip().upper().startswith("APROVADO"),
                                        "resultado": " ".join((lin.get("resultado_votacao") or "").split()) or None, "sim": 0, "nao": 0,
                                        "abstencoes": 0, "votos": [], "fonte": f"{VOTACOES_PAGINA}?tipo=detalhes&ano={ano}&mes={mes}"})
        materias.setdefault(pauta, {"tipo": None, "tipoDescricao": None, "numero": None, "ano": ano,
                                    "ementa": " ".join((lin.get("ementa_projeto") or "").split()) or None})
        voto = VOTOS.get(comum.sem_acento(lin.get("tipo_voto")).upper().replace(" ", ""))
        if voto == "Sim":
            v["sim"] += 1
        elif voto == "Não":
            v["nao"] += 1
        elif voto:
            v["abstencoes"] += 1
        dep = ligacao.get(lin.get("parlamentar"))
        if dep and voto:
            v["votos"].append([dep, voto])
    return votacoes, materias


def ano_da_votacao(v: dict) -> int:
    a = str(v.get("data") or "")[:4]
    return int(a) if a.isdigit() else 0


def coletar_votacoes(s, deputados: list[dict]) -> None:
    """Votações de anos encerrados vêm do arquivo anterior; só o ano passado e o corrente são lidos de novo."""
    hoje = date.today()
    anteriores = (comum.ler(PASTA / "votacoes.json") or {}).get("votacoes") or {}
    votacoes = {k: v for k, v in anteriores.items() if 0 < ano_da_votacao(v) < hoje.year - 1}
    materias_anteriores = comum.ler(PASTA / "materias_votadas.json", {})
    materias = {k: materias_anteriores[k] for k in votacoes if k in materias_anteriores}
    sem_par = set()
    for ano in range(hoje.year - 1 if votacoes else ANO_INICIAL, hoje.year + 1):
        linhas = pegar_json(s, "votacoes.json", tipo="detalhes", ano=ano)
        ligacao = identidades.ligar_nomes({lin["parlamentar"] for lin in linhas}, deputados, UF)
        sem_par |= {lin["parlamentar"] for lin in linhas if lin["parlamentar"] not in ligacao}
        v, m = montar_votacoes(linhas, ligacao, ano)
        votacoes.update(v)
        materias.update(m)
    comum.salvar(PASTA / "votacoes.json", {"fonte": f"{VOTACOES_PAGINA}?tipo=detalhes", "votacoes": votacoes})
    comum.salvar(PASTA / "materias_votadas.json", materias)
    print(f"GO: {len(votacoes)} votações nominais")
    if sem_par:
        comum.avisar(f"GO: votos sem deputado em exercício ({len(sem_par)}): {sorted(sem_par)[:12]}")


def itens_requerimentos(registros: list[dict], ligacao: dict, ano: int) -> dict:
    materias = {}
    for r in registros:
        dep = ligacao.get((r.get("deputado") or {}).get("nome"))
        if not dep:
            continue
        tipo = (r.get("tipo_requerimento") or {}).get("descricao")
        materias[str(r["id"])] = {"tipo": "REQ", "tipoDescricao": "Requerimento", "numero": r.get("numero"), "ano": ano,
                                  "dataApresentacao": None, "ementa": f"Requerimento nº {r.get('numero')}: {tipo}" if tipo else None,
                                  "situacao": (r.get("etapa") or {}).get("descricao"), "emTramitacao": None,
                                  "linkTexto": r.get("url_download"), "idsAutores": [], "idsDeputados": [dep],
                                  "fonte": f"{REQUERIMENTOS_PAGINA}?ano={ano}&numero={r.get('numero')}"}
    return materias


def coletar_requerimentos(s, deputados: list[dict]) -> None:
    hoje = date.today().isoformat()
    for ano in range(ANO_INICIAL, ANO_REQUERIMENTOS_FINAL + 1):
        destino = PASTA / f"materias_{ano}.json"
        if destino.exists():
            continue
        registros = paginar(s, "requerimentos", ano=ano)
        ligacao = identidades.ligar_nomes({(r.get("deputado") or {}).get("nome") for r in registros}, deputados, UF)
        materias = itens_requerimentos(registros, ligacao, ano)
        comum.salvar(destino, {"coletadoEm": hoje, "fonte": f"{REQUERIMENTOS_PAGINA}?ano={ano}", "materias": materias})
        print(f"GO: requerimentos {ano}: {len(materias)} de {len(registros)}")


def coletar() -> None:
    s = comum.sessao()
    deputados = coletar_deputados(s)
    if not deputados:
        comum.avisar("GO: portal.al.go.leg.br sem deputados em exercício")
        return
    comum.salvar(PASTA / "deputados.json", {"fonte": LISTA_URL, "host": None, "legislatura": "2023-2027", "deputados": deputados})
    print(f"GO: {len(deputados)} deputados")
    comum.rodar_etapas(UF, [("verbas", lambda: coletar_verbas(s, deputados)), ("remuneração", lambda: coletar_remuneracao(s, deputados)),
                            ("votações", lambda: coletar_votacoes(s, deputados)), ("requerimentos", lambda: coletar_requerimentos(s, deputados)),
                            ("diárias", lambda: coletar_diarias(s, deputados))])


def _contrato_lista(ctx):
    html = pegar_html(comum.sessao(), LISTA_URL)
    linhas = html.split('<tr data-target="search.filterable"')[1:3]
    return {"html": '<table><tr data-target="search.filterable"' + '<tr data-target="search.filterable"'.join(linhas)}


def _conferir_lista(registro):
    lista = parse_lista(registro["html"])
    if not lista:
        return ["lista de deputados sem linhas com /deputados/perfil/<id>"], []
    falhas = []
    falhas += comum.campos_vazios(lista[0], ("id", "nome", "partido"), "linha da lista")
    return falhas, []


def _contrato_perfil(ctx):
    html = pegar_html(comum.sessao(), PERFIL_URL.format(id=117))
    i = html.find('<section class="perfil">')
    return {"html": html[i:i + 1800]}


def _conferir_perfil(registro):
    p = parse_perfil(registro["html"])
    return [f"ficha sem {k}" for k in ("nomeCivil", "foto", "email") if not p[k]], []


def _conferir_campos(*campos):
    def conferir(registro):
        if not registro:
            return ["resposta sem itens"], []
        return [f"item sem {c}" for c in campos if c not in registro[0]], []
    return conferir


def _contrato_votacoes(ctx):
    dados = pegar_json(comum.sessao(), "votacoes.json", tipo="detalhes", ano=date.today().year - 1)
    nominais = [lin for lin in dados if lin.get("tipo_votacao") == "NOMINAL"]
    return nominais[:3]


def _ultimo_mes_publicado(caminho: str, **params) -> list:
    s = comum.sessao()
    hoje = date.today()
    ano, mes = hoje.year, hoje.month - 1
    for _ in range(12):
        if mes < 1:
            ano, mes = ano - 1, 12
        registros = pegar_json(s, caminho, ano=ano, mes=mes, **params)
        if registros:
            return registros[:2]
        mes -= 1
    return []


CONTRATOS = [
    {"nome": "estadual_go_lista", "fonte": LISTA_URL, "buscar": _contrato_lista, "html": _conferir_lista},
    {"nome": "estadual_go_perfil", "fonte": PERFIL_URL.format(id=117), "buscar": _contrato_perfil, "html": _conferir_perfil},
    {"nome": "estadual_go_verbas", "fonte": f"{API}/verbas_indenizatorias", "html": _conferir_campos("ano", "mes", "valor_indenizado", "valor_apresentado", "deputado"),
         "buscar": lambda ctx: _ultimo_mes_publicado("verbas_indenizatorias")},
    {"nome": "estadual_go_remuneracao", "fonte": f"{API}/remuneracoes", "html": _conferir_campos("nome", "matricula", "vencimento", "remuneracao_liquida", "status"),
         "buscar": lambda ctx: _ultimo_mes_publicado("remuneracoes", categoria=7)},
    {"nome": "estadual_go_diarias", "fonte": f"{API}/diarias", "html": _conferir_campos("id", "beneficiario", "cargo", "trecho", "data_inicio", "total"),
         "buscar": lambda ctx: _ultimo_mes_publicado("diarias")},
    {"nome": "estadual_go_requerimentos", "fonte": f"{API}/requerimentos", "html": _conferir_campos("id", "numero", "deputado", "tipo_requerimento", "etapa", "url_download"),
         "buscar": lambda ctx: pegar_json(comum.sessao(), "requerimentos", ano=ANO_REQUERIMENTOS_FINAL)[:2]},
    {"nome": "estadual_go_votacoes", "fonte": f"{API}/votacoes.json", "html": _conferir_campos("data_sessao", "pauta_id", "parlamentar", "tipo_voto", "resultado_votacao", "tipo_votacao", "ementa_projeto"),
         "buscar": _contrato_votacoes},
]


if __name__ == "__main__":
    comum.principal(coletar)
