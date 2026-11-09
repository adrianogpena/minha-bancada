import json
from datetime import date

import pytest

import coletar_estadual_sc as sc
import estaduais_comum as comum
from conftest import RAIZ

FIX = RAIZ / "tests" / "fixtures" / "contratos"

DEPUTADOS = [
    {"id": "10", "nome": "Alex Brasil", "nomeCivil": "Alexander Brasil Alves Pereira", "nomeFonte": "Alexander Brasil Alves Pereira"},
    {"id": "11", "nome": "Altair Silva", "nomeCivil": "Altair da Silva", "nomeFonte": "Altair Silva"},
    {"id": "12", "nome": "Paulinha", "nomeCivil": "Ana Paula da Silva", "nomeFonte": "Paulinha"},
    {"id": "13", "nome": "Silvio Cardoso Junior", "nomeCivil": "Silvio Cardoso Junior", "nomeFonte": "Silvio Cardoso Junior"},
    {"id": "14", "nome": "Napoleao Bernardes", "nomeCivil": "Napoleão Bernardes Neto", "nomeFonte": "Napoleao Bernardes Neto"},
]


def amostra(nome):
    return json.loads((FIX / f"{nome}.json").read_text(encoding="utf-8"))["amostra"]


def test_ligar_casa_apelidos_prefixos_e_parenteses():
    ligados = sc.ligar(["Alex Brasil", "ALTAIR DA SILVA", "Ana Paula da Silva (Paulinha)", "Emerson Stein"], DEPUTADOS)
    assert ligados == {"Alex Brasil": "10", "ALTAIR DA SILVA": "11", "Ana Paula da Silva (Paulinha)": "12"}


def test_parse_deputados_do_contrato():
    a = amostra("estadual_sc_deputados")
    lista = sc.parse_deputados(a["html"])
    assert lista[0] == {"nomeCivil": "ALEXANDER BRASIL ALVES PEREIRA", "idContracheque": "10230"}
    assert sc._conferir_deputados(a) == ([], [])


def test_deputados_com_tse_usa_urna_e_partido(tmp_path, monkeypatch):
    tse = tmp_path / "SC.json"
    tse.write_text(json.dumps([{"cargo": "DEPUTADO ESTADUAL", "situacao": "eleito", "sequencial": "1", "nome": "Altair da Silva", "urna": "Altair Silva", "partido": "PP", "email": None},
                               {"cargo": "DEPUTADO ESTADUAL", "situacao": "eleito", "sequencial": "2", "nome": "Ana Paula da Silva", "urna": "Paulinha", "partido": "PODE", "email": None}]), encoding="utf-8")
    monkeypatch.setattr(sc, "TSE_ARQUIVO", tse)
    lista = [{"nomeCivil": "ALTAIR SILVA", "idContracheque": "11"}, {"nomeCivil": "PAULINHA", "idContracheque": "12"}, {"nomeCivil": "FULANO DE TAL", "idContracheque": "99"}]
    deputados = {d["id"]: d for d in sc.deputados_com_tse(lista)}
    assert deputados["11"]["nome"] == "Altair Silva" and deputados["11"]["nomeCivil"] == "Altair da Silva" and deputados["11"]["partido"] == "PP"
    assert deputados["12"]["nome"] == "Paulinha" and deputados["12"]["partido"] == "PODE"
    assert deputados["99"]["nome"] == "Fulano De Tal" and deputados["99"]["partido"] is None


def test_parse_contracheque_do_contrato():
    a = amostra("estadual_sc_contracheque")
    cc = sc.parse_contracheque(a["html"])
    assert cc["bruto"] == 34774.64 and cc["liquido"] == 23387.07
    assert cc["componentes"]["Subsídio"] == 34774.64 and cc["componentes"]["Previdência"] == -988.07
    assert sc._conferir_contracheque(a) == ([], [])


def test_itens_remuneracao():
    itens = sc.itens_remuneracao({"10": {"bruto": 1.0, "liquido": 0.5, "componentes": {"Subsídio": 1.0}}}, 9, 2026)
    assert itens == [{"idDeputado": "10", "mes": 9, "bruto": 1.0, "liquido": 0.5, "componentes": {"Subsídio": 1.0},
                      "fonte": "https://transparencia.alesc.sc.gov.br/deputados?ano=2026&mes=9"}]


def test_itens_gabinetes_do_contrato():
    a = amostra("estadual_sc_gabinetes")
    linhas = sc.ler_csv(a["csv"])
    itens = sc.itens_gabinetes(linhas, DEPUTADOS)
    assert len(itens) == 2 and {i["idDeputado"] for i in itens} == {"12"}
    assert itens[0]["mes"] == 6 and itens[0]["categoria"] == "ALMOXARIFADO / Jornais e Revistas" and itens[0]["valor"] == 733.0
    assert itens[0]["data"] == "2026-06-26" and itens[0]["fonte"] == sc.GABINETES_PAGINA and itens[0]["fornecedor"] is None
    assert sc._conferir_gabinetes(a) == ([], [])


def test_itens_diarias_so_deputados_e_com_relatorio_como_fonte():
    a = amostra("estadual_sc_diarias")
    itens = sc.itens_diarias(sc.ler_csv(a["csv"]), DEPUTADOS)
    assert [(i["idDeputado"], i["data"], i["valor"], i["quantidade"]) for i in itens] == [("13", "2026-10-19", 1078.0, 1.0), ("14", "2026-10-19", 1078.0, 1.0)]
    assert itens[0]["fonte"].startswith("https://diarias.alesc.sc.gov.br/prestacao-contas/")
    assert sc._conferir_diarias(a) == ([], [])
    servidor = "Nome;Conta;Vínculo;Data;Quantidade;Valor;Relatório\nFULANO;1;Servidor;01/01/2026;1,0;10,00;http://x"
    assert sc.itens_diarias(sc.ler_csv(servidor), DEPUTADOS) == []


def test_parse_sessoes_e_presenca_do_contrato():
    a = amostra("estadual_sc_sessoes")
    sessoes = sc.parse_sessoes(a["lista"])
    assert len(sessoes) == 2 and all(s["codigo"] and s["data"] and "Sessão" in s["titulo"] for s in sessoes)
    assert {s["situacao"] for s in sessoes} <= {"Realizada", "Horário regimental"}
    assert a["total"] >= 2
    assert sc.parse_presenca(a["presenca"])["Altair Silva"] == "Presente"
    assert sc._conferir_sessoes(a) == ([], [])


def test_tipo_presenca():
    assert [sc.tipo_presenca(x) for x in ("Presente", "Ausência justificada", "Ausente", "Licença")] == ["presente", "licenca", "ausente", "licenca"]


def test_itens_presenca_soma_por_mes_e_ignora_sessao_vazia():
    sessoes = {
        "a": {"data": "2026-09-01", "presencas": {"Alex Brasil": "Presente", "Altair Silva": "Ausência justificada", "Desconhecido": "Presente"}},
        "b": {"data": "2026-09-02", "presencas": {"Alex Brasil": "Ausente", "Altair Silva": "Presente"}},
        "c": {"data": "2026-09-03", "presencas": {}},
        "d": {"data": "2026-10-01", "presencas": {"Alex Brasil": "Presente"}},
    }
    itens = {(i["idDeputado"], i["periodo"]): i for i in sc.itens_presenca(sessoes, DEPUTADOS)}
    assert itens[("10", "2026-09")] == {"idDeputado": "10", "periodo": "2026-09", "presente": 1, "ausente": 1, "licenca": 0, "totalSessoes": 2, "fonte": sc.SESSOES_URL}
    assert itens[("11", "2026-09")]["licenca"] == 1 and itens[("11", "2026-09")]["presente"] == 1
    assert itens[("10", "2026-10")]["totalSessoes"] == 1
    assert len(itens) == 3


class Resposta:
    def __init__(self, texto="", conteudo=None):
        self.text = texto
        self.content = conteudo if conteudo is not None else texto.encode("utf-8")

    def raise_for_status(self):
        pass


class Sessao:
    def __init__(self, respostas):
        self.respostas = respostas

    def get(self, url, params=None, timeout=None, headers=None):
        if url.startswith(f"{sc.DEPUTADOS_URL}/contracheque/"):
            return Resposta(self.respostas["contracheque"])
        return Resposta(self.respostas[url])


def test_coletar_grava_arquivos(tmp_path, monkeypatch):
    hoje = date.today()
    ano = hoje.year
    tabela = amostra("estadual_sc_deputados")["html"]
    lista = amostra("estadual_sc_sessoes")["lista"]
    respostas = {
        sc.DEPUTADOS_URL: tabela,
        "contracheque": amostra("estadual_sc_contracheque")["html"],
        sc.SESSOES_URL: lista,
    }
    for a in range(sc.PRIMEIRO_ANO, ano + 1):
        respostas[f"{sc.GABINETES_PAGINA}/csv/{a}"] = amostra("estadual_sc_gabinetes")["csv"]
        respostas[f"{sc.DIARIAS_PAGINA}/csv/{a}"] = amostra("estadual_sc_diarias")["csv"]
    for s in sc.parse_sessoes(lista):
        respostas[f"{sc.SESSOES_URL}/{s['codigo']}/presenca"] = amostra("estadual_sc_sessoes")["presenca"]
    tse = tmp_path / "SC.json"
    tse.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(sc, "TSE_ARQUIVO", tse)
    monkeypatch.setattr(comum, "DADOS", tmp_path / "estaduais")
    monkeypatch.setattr(comum, "sessao", lambda: Sessao(respostas))
    monkeypatch.setattr(sc, "ANOS_REMUNERACAO", 1)
    sc.coletar()
    pasta = tmp_path / "estaduais" / "SC"
    deputados = json.loads((pasta / "deputados.json").read_text(encoding="utf-8"))
    assert deputados["host"] is None and len(deputados["deputados"]) == 2
    assert (pasta / f"verbas_{ano}.json").exists() and (pasta / f"diarias_{ano}.json").exists()
    presenca = json.loads((pasta / "presenca.json").read_text(encoding="utf-8"))
    assert presenca["itens"] and presenca["sessoes"]
    remuneracao = json.loads((pasta / f"remuneracao_{ano}.json").read_text(encoding="utf-8"))["itens"]
    assert {i["bruto"] for i in remuneracao} == {34774.64}


def fingir_baixar(monkeypatch, resposta):
    chamadas = []

    def baixar(s, url, params=None, headers=None):
        chamadas.append((url, dict(params or {})))
        return Resposta(resposta(url, params or {}))

    monkeypatch.setattr(sc, "baixar", baixar)
    return chamadas


def cartao_sessao(codigo, data, situacao):
    return (f'<div class="card card-alesc mb-4"><a href="/sessoes-plenarias/{codigo}/presenca">ver</a><h4 class="mb-1">Sessão {codigo}</h4>'
            f'<p>{data} · Ordinária</p><span><i class="bi"></i> {situacao}</span></div></div></div>')


def pagina_presenca(*linhas):
    return "<table>" + "".join(f"<tr><td>{n}</td><td>{s}</td></tr>" for n, s in linhas) + "</table>"


def tabela_deputados(*pares):
    return "<table>" + "".join(f'<tr><td class="fw-semibold">{n}</td><td><a href="/deputados/contracheque/{i}?ano=2026">x</a></td></tr>' for i, n in pares) + "</table>"


def cartao_proposicao(codigo, rotulo, autores, entrada="10/02/2026", situacao="Em tramitação", ementa="Dispõe sobre algo"):
    lis = "".join(f"<li>{a}</li>" for a in autores)
    return (f'<div class="card card-alesc mb-3"><a href="/proposicoes/{codigo}">{rotulo}</a><p class="mb-1 fst-italic" id="e">{ementa}</p>'
            f'<div class="fw-bold col-lg-2">Autoria</div><div class="col-lg-10"><ul>{lis}</ul></div>'
            f'<div class="fw-bold col-lg-2">Entrada</div><div class="col-lg-10">{entrada}</div>'
            f'<div class="fw-bold col-lg-2">Situação atual</div><div class="col-lg-10">{situacao}</div></div>')


def lida(codigo, numero, autores, ano=2026):
    return {"codigo": codigo, "tipo": "PL", "numero": numero, "ano": ano, "dataApresentacao": f"{ano}-02-10", "ementa": "e",
            "situacao": "Em tramitação", "autores": autores}


def opcao(ident, rotulo):
    return f'<option value="{ident}">{rotulo}</option>'


def linha_servidor(nome, vinculo, lotacao, matricula):
    return (f'<tr><td class="fw-semibold">{nome}</td><td>{vinculo}</td><td class="small">{lotacao}</td>'
            f'<td><a href="/servidores/contracheque/{matricula}?ano=2026">x</a></td></tr>')


def cartao_contrato(ident, numero, especie, nome, doc, objeto, valor, modalidade, vigencia, situacao, download=True):
    arquivo = f'<a href="/contratos/download/{ident}">pdf</a>' if download else ""
    return (f'<article class="card card-alesc h-100"><a href="/contratos/{ident}" class="t">Nº {numero}</a>'
            f'<span class="text-uppercase small fw-semibold">{especie}</span>'
            f'<div class="fw-bold">{nome}</div><div class="text-muted small">CNPJ: {doc}</div>'
            f'<span>Objeto</span></div><p class="o">{objeto}</p>'
            f'<div>Valor Original</div><div class="v">{valor}</div>'
            f'<div>Modalidade</div><div>{modalidade}</div>'
            f'<div>Vigência</div><div>{vigencia}</div>'
            f'<span class="badge bg-success">{situacao}</span>{arquivo}</article>')


REGRAS_HTML = ('<section id="gabinetes-parlamentares"><h2>Gabinetes</h2>'
               '<a href="/ato-normativo/legislativo/1">Ato da Mesa 12/2019</a><p class="x fst-italic mb-2">Dispõe sobre as cotas de custeio</p>'
               '<a href="/ato-normativo/legislativo/2">Ato da Mesa 5/2023</a><p class="fst-italic mb-2">Regulamenta a cota do gabinete</p>'
               '<a href="/ato-normativo/legislativo/3">Ato sem relação 8/2024</a><p class="fst-italic mb-2">Dispõe sobre férias</p>'
               '<h5 class="card-title h5" id="outra">Outra</h5>'
               '<a href="/ato-normativo/legislativo/4">Ato 1/2025</a><p class="fst-italic mb-2">cotas de outro grupo</p></section>')


def test_mes_anterior_na_virada_do_ano():
    assert sc.mes_anterior(2026, 1) == (2025, 12)
    assert sc.mes_anterior(2026, 5) == (2026, 4)


def test_parsers_com_html_vazio():
    assert sc.parse_deputados("") == []
    assert sc.parse_contracheque("<html></html>") == {"bruto": None, "liquido": None, "componentes": {}}
    assert sc.parse_sessoes("") == []
    assert sc.parse_presenca("") == {}


def test_total_paginas_com_e_sem_paginacao():
    assert sc.total_paginas('<a href="/sessoes-plenarias?page=2">2</a><a href="/sessoes-plenarias?page=7">7</a>') == 7
    assert sc.total_paginas("<html></html>") == 1


def test_conferir_com_falhas():
    assert sc._conferir_deputados({"html": ""}) == (["tabela de deputados sem linhas"], [])
    assert sc._conferir_contracheque({"html": ""}) == (["contracheque sem bruto", "contracheque sem liquido", "contracheque sem componentes"], [])
    for conferir, rotulo in ((sc._conferir_gabinetes, "gabinetes"), (sc._conferir_diarias, "diárias")):
        falhas, _ = conferir({"csv": ""})
        assert len(falhas) == 8 and falhas[-1] == f"CSV de {rotulo} sem linhas"
    sem_situacao = '<div class="card card-alesc mb-4"><a href="/sessoes-plenarias/x1/presenca">v</a><h4 class="mb-1">T</h4>01/02/2026 ·</div>'
    assert sc._conferir_sessoes({"lista": sem_situacao, "presenca": ""}) == (["sessão sem data ou situação", "página de presença sem linhas"], [])
    assert sc._conferir_sessoes({"lista": "", "presenca": pagina_presenca(("A", "Presente"))}) == (["lista de sessões plenárias vazia"], [])


def test_remuneracao_pula_meses_fechados_rele_recentes_e_ignora_contracheque_vazio(tmp_path, monkeypatch):
    pasta = tmp_path
    comum.salvar(pasta / "remuneracao_2025.json", {"itens": [{"idDeputado": "v", "mes": m} for m in range(1, 13)]})
    comum.salvar(pasta / "remuneracao_2026.json", {"itens": [{"idDeputado": "velho1", "mes": 1}, {"idDeputado": "velho2", "mes": 2}]})
    contracheque = amostra("estadual_sc_contracheque")["html"]

    def resposta(url, params):
        if url == sc.DEPUTADOS_URL:
            return tabela_deputados(("1", "A"), ("2", "B"))
        return contracheque if url.endswith("/1") else "<html></html>"

    chamadas = fingir_baixar(monkeypatch, resposta)
    sc.coletar_remuneracao(None, pasta, date(2026, 3, 15), "2026-03-15")
    assert [(p["ano"], p["mes"]) for u, p in chamadas if u == sc.DEPUTADOS_URL] == [(2026, 2), (2026, 3)]
    itens = comum.ler(pasta / "remuneracao_2026.json")["itens"]
    assert [(i["idDeputado"], i["mes"]) for i in itens] == [("velho1", 1), ("1", 2), ("1", 3)]
    assert len(comum.ler(pasta / "remuneracao_2025.json")["itens"]) == 12


def test_presenca_incremental_pula_sessao_lida_e_para_na_data_antiga(tmp_path, monkeypatch):
    comum.salvar(tmp_path / "presenca.json", {"sessoes": {"s1": {"data": "2026-03-10", "titulo": "Sessão s1", "presencas": {"Alex Brasil": "Ausente"}}}})
    lista = (cartao_sessao("s1", "10/03/2026", "Realizada") + cartao_sessao("s4", "11/03/2026", "Realizada")
             + cartao_sessao("s2", "12/03/2026", "Horário regimental") + cartao_sessao("s3", "15/01/2023", "Realizada")
             + '<a href="/sessoes-plenarias?page=2">2</a>')

    def resposta(url, params):
        if url == sc.SESSOES_URL:
            return lista
        assert url == f"{sc.SESSOES_URL}/s4/presenca"
        return pagina_presenca(("Alex Brasil", "Presente"))

    chamadas = fingir_baixar(monkeypatch, resposta)
    sc.coletar_presenca(None, tmp_path, DEPUTADOS, date(2026, 11, 3), "2026-11-03")
    assert [p["page"] for u, p in chamadas if u == sc.SESSOES_URL] == [1]
    env = comum.ler(tmp_path / "presenca.json")
    assert set(env["sessoes"]) == {"s1", "s4"}
    assert env["itens"] == [{"idDeputado": "10", "periodo": "2026-03", "presente": 1, "ausente": 1, "licenca": 0, "totalSessoes": 2, "fonte": sc.SESSOES_URL}]


def test_presenca_le_todas_as_paginas_da_lista(tmp_path, monkeypatch):
    paginas = {1: cartao_sessao("s1", "10/03/2026", "Realizada") + '<a href="/sessoes-plenarias?page=2">2</a>',
               2: cartao_sessao("s2", "11/03/2026", "Realizada") + '<a href="/sessoes-plenarias?page=2">2</a>'}

    def resposta(url, params):
        return paginas[params["page"]] if url == sc.SESSOES_URL else pagina_presenca(("Altair Silva", "Presente"))

    chamadas = fingir_baixar(monkeypatch, resposta)
    sc.coletar_presenca(None, tmp_path, DEPUTADOS, date(2026, 11, 3), "2026-11-03")
    assert [p["page"] for u, p in chamadas if u == sc.SESSOES_URL] == [1, 2]
    assert set(comum.ler(tmp_path / "presenca.json")["sessoes"]) == {"s1", "s2"}


def test_presenca_sem_sessoes_grava_arquivo_vazio(tmp_path, monkeypatch):
    fingir_baixar(monkeypatch, lambda url, params: "")
    sc.coletar_presenca(None, tmp_path, DEPUTADOS, date(2026, 11, 3), "2026-11-03")
    env = comum.ler(tmp_path / "presenca.json")
    assert env["itens"] == [] and env["sessoes"] == {}


def test_coletar_sem_deputados_avisa_e_nao_grava(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(comum, "DADOS", tmp_path)
    monkeypatch.setattr(comum, "sessao", lambda: None)
    fingir_baixar(monkeypatch, lambda url, params: "<html></html>")
    sc.coletar()
    assert "nenhum deputado" in capsys.readouterr().err
    assert not (tmp_path / "SC").exists()


def test_coletar_pula_ano_encerrado_e_avisa_etapa_que_falha(tmp_path, monkeypatch, capsys):
    pasta = tmp_path / "estaduais" / "SC"
    pasta.mkdir(parents=True)
    for nome in ("verbas_2023.json", "diarias_2023.json"):
        (pasta / nome).write_text("{}", encoding="utf-8")
    tse = tmp_path / "SC.json"
    tse.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(sc, "TSE_ARQUIVO", tse)
    monkeypatch.setattr(sc, "PRIMEIRO_ANO", 2023)
    monkeypatch.setattr(comum, "DADOS", tmp_path / "estaduais")
    monkeypatch.setattr(comum, "sessao", lambda: None)
    for nome in ("coletar_presenca", "coletar_remuneracao", "coletar_gabinete", "coletar_orgao"):
        monkeypatch.setattr(sc, nome, lambda *a, **k: None)

    def falha(*a, **k):
        raise RuntimeError("fora do ar")

    monkeypatch.setattr(sc, "coletar_proposicoes", falha)
    monkeypatch.setattr(sc, "coletar_regras", falha)
    tabela = amostra("estadual_sc_deputados")["html"]
    chamadas = fingir_baixar(monkeypatch, lambda url, params: tabela if url == sc.DEPUTADOS_URL else "Conta;Nome\n")
    sc.coletar()
    urls = [u for u, _ in chamadas]
    assert f"{sc.GABINETES_PAGINA}/csv/2023" not in urls and f"{sc.GABINETES_PAGINA}/csv/2024" in urls
    assert f"{sc.DIARIAS_PAGINA}/csv/2023" not in urls
    err = capsys.readouterr().err
    assert "SC: proposições: fora do ar" in err and "SC: regras da cota: fora do ar" in err
    assert (pasta / "verbas_2023.json").read_text(encoding="utf-8") == "{}"


def test_proposicoes_da_pagina_le_cartao_completo_e_minimo():
    html = (cartao_proposicao("AB123", "PL./0667/2026", ["Deputado Alex Brasil", "Comissão de Finanças"])
            + '<div class="card card-alesc">sem link</div>'
            + '<div class="card card-alesc"><a href="/proposicoes/ZZ9">REQ/1/2026</a></div>')
    completo, minimo = sc.proposicoes_da_pagina(html)
    assert completo == {"codigo": "AB123", "tipo": "PL", "numero": 667, "ano": 2026, "ementa": "Dispõe sobre algo", "dataApresentacao": "2026-02-10",
                        "autores": ["Deputado Alex Brasil", "Comissão de Finanças"], "situacao": "Em tramitação"}
    assert minimo == {"codigo": "ZZ9", "tipo": "REQ", "numero": 1, "ano": 2026, "ementa": "", "dataApresentacao": None, "autores": [], "situacao": None}


def test_total_proposicoes():
    assert sc.total_proposicoes("Exibindo 1 - 10 de 1.234 registros") == 1234
    assert sc.total_proposicoes("<html></html>") == 0


def test_ler_proposicoes_pagina_a_pagina_ate_o_total(monkeypatch):
    p1 = (cartao_proposicao("A1", "PL/1/2026", ["Deputado Alex Brasil"]) + cartao_proposicao("A2", "PL/2/2026", ["Deputado Alex Brasil"])
          + "Exibindo 1 - 2 de 3")
    p2 = cartao_proposicao("A3", "PL/3/2026", ["Deputado Alex Brasil"]) + "Exibindo 3 - 3 de 3"
    chamadas = fingir_baixar(monkeypatch, lambda url, params: p1 if params["page"] == 1 else p2)
    assert [p["codigo"] for p in sc.ler_proposicoes(None, 2026)] == ["A1", "A2", "A3"]
    assert chamadas[0][1] == {"arquivados": 1, "inicio": "2026-01-01", "fim": "2026-12-31", "page": 1}
    sc.ler_proposicoes(None, 2026, "2026-05-01")
    assert chamadas[-1][1]["inicio"] == "2026-05-01"


def test_ler_proposicoes_pagina_vazia_encerra(monkeypatch):
    chamadas = fingir_baixar(monkeypatch, lambda url, params: "")
    assert sc.ler_proposicoes(None, 2026) == [] and len(chamadas) == 1


def test_autor_deputado_e_do_governador():
    assert sc.autor_deputado("Deputado Jerry Comper") == "Jerry Comper"
    assert sc.autor_deputado(" Deputada Ana Paula ") == "Ana Paula"
    assert sc.autor_deputado("Governador do Estado") is None
    assert sc.autor_deputado(None) is None
    assert sc.do_governador({"autores": ["Comissão", "Governador do Estado"]}) is True
    assert sc.do_governador({"autores": ["Comissão"]}) is False


def test_separar_proposicoes_deputado_governador_e_demais():
    lidas = [lida("A1", 1, ["Deputado Alex Brasil", "Comissão"]), lida("G1", 2, ["Governador do Estado"]), lida("C1", 3, ["Comissão de Finanças"])]
    materias, governo = sc.separar_proposicoes(lidas, DEPUTADOS)
    assert list(materias) == ["PL-1-2026"] and list(governo) == ["PL-2-2026"]
    assert materias["PL-1-2026"]["idsDeputados"] == ["10"] and materias["PL-1-2026"]["idsAutores"] == ["10"]
    assert materias["PL-1-2026"]["fonte"] == f"{sc.ELEGIS}/proposicoes/A1" and materias["PL-1-2026"]["idFonte"] == "A1"
    assert governo["PL-2-2026"]["tipoDescricao"] == "PL"


def test_proposicoes_sem_arquivo_leitura_completa_e_separa_governo(tmp_path, monkeypatch):
    monkeypatch.setattr(sc, "PRIMEIRO_ANO", 2026)
    chamadas = []
    lidas = [lida("A1", 1, ["Deputado Alex Brasil"]), lida("G1", 2, ["Governador do Estado"]), lida("C1", 3, ["Comissão"])]
    monkeypatch.setattr(sc, "ler_proposicoes", lambda s, ano, inicio=None: chamadas.append((ano, inicio)) or lidas)
    sc.coletar_proposicoes(None, tmp_path, DEPUTADOS, date(2026, 11, 3), "2026-11-03")
    assert chamadas == [(2026, None)]
    env = comum.ler(tmp_path / "materias_2026.json")
    assert list(env["materias"]) == ["PL-1-2026"] and env["completaEm"] == "2026-11-03"
    assert list(comum.ler(tmp_path / "governo_2026.json")["materias"]) == ["PL-2-2026"]


def test_proposicoes_incremental_junta_com_o_guardado(tmp_path, monkeypatch):
    monkeypatch.setattr(sc, "PRIMEIRO_ANO", 2026)
    comum.salvar(tmp_path / "materias_2026.json", {"coletadoEm": "2026-11-01", "completaEm": "2026-11-01", "materias": {"PL-9-2026": {"x": 1}}})
    comum.salvar(tmp_path / "governo_2026.json", {"materias": {"MSG-8-2026": {"y": 1}}})
    chamadas = []
    novas = [lida("A1", 1, ["Deputado Alex Brasil"]), lida("G1", 2, ["Governador do Estado"])]
    monkeypatch.setattr(sc, "ler_proposicoes", lambda s, ano, inicio=None: chamadas.append((ano, inicio)) or novas)
    sc.coletar_proposicoes(None, tmp_path, DEPUTADOS, date(2026, 11, 3), "2026-11-03")
    assert chamadas == [(2026, "2026-10-31")]
    env = comum.ler(tmp_path / "materias_2026.json")
    assert set(env["materias"]) == {"PL-9-2026", "PL-1-2026"} and env["completaEm"] == "2026-11-01" and env["coletadoEm"] == "2026-11-03"
    assert set(comum.ler(tmp_path / "governo_2026.json")["materias"]) == {"MSG-8-2026", "PL-2-2026"}


def test_proposicoes_completa_velha_rele_tudo_e_substitui(tmp_path, monkeypatch):
    monkeypatch.setattr(sc, "PRIMEIRO_ANO", 2026)
    comum.salvar(tmp_path / "materias_2026.json", {"coletadoEm": "2026-10-01", "completaEm": "2026-10-01", "materias": {"PL-9-2026": {"x": 1}}})
    chamadas = []
    monkeypatch.setattr(sc, "ler_proposicoes", lambda s, ano, inicio=None: chamadas.append((ano, inicio)) or [lida("A1", 1, ["Deputado Alex Brasil"])])
    sc.coletar_proposicoes(None, tmp_path, DEPUTADOS, date(2026, 11, 3), "2026-11-03")
    assert chamadas == [(2026, None)]
    env = comum.ler(tmp_path / "materias_2026.json")
    assert list(env["materias"]) == ["PL-1-2026"] and env["completaEm"] == "2026-11-03"


def test_proposicoes_completa_com_lista_vazia_mantem_o_arquivo(tmp_path, monkeypatch):
    monkeypatch.setattr(sc, "PRIMEIRO_ANO", 2026)
    original = {"coletadoEm": "2026-10-01", "completaEm": "2026-10-01", "materias": {"PL-9-2026": {"x": 1}}}
    comum.salvar(tmp_path / "materias_2026.json", original)
    monkeypatch.setattr(sc, "ler_proposicoes", lambda s, ano, inicio=None: [])
    with pytest.raises(RuntimeError, match="lista vazia"):
        sc.coletar_proposicoes(None, tmp_path, DEPUTADOS, date(2026, 11, 3), "2026-11-03")
    assert comum.ler(tmp_path / "materias_2026.json") == original


def test_proposicoes_ano_encerrado_nao_e_lido(tmp_path, monkeypatch):
    monkeypatch.setattr(sc, "PRIMEIRO_ANO", 2023)
    comum.salvar(tmp_path / "materias_2023.json", {"coletadoEm": "2026-10-01", "completaEm": "2026-11-01", "materias": {"x": {}}})
    anos = []
    monkeypatch.setattr(sc, "ler_proposicoes", lambda s, ano, inicio=None: anos.append(ano) or [])
    sc.coletar_proposicoes(None, tmp_path, DEPUTADOS, date(2026, 11, 3), "2026-11-03")
    assert anos == [2024, 2025, 2026]


def test_setores_de_gabinete_e_servidores_da_pagina():
    html = '<option value="">Todos</option>' + opcao(5, "GAB DEP Alex Brasil") + opcao(6, "DIRETORIA") + opcao(7, "GAB. DEP. Fulano Inexistente")
    assert sc.setores_de_gabinete(html) == {"5": "Alex Brasil", "7": "Fulano Inexistente"}
    linhas = sc.servidores_da_pagina(linha_servidor("Maria", "CC-1", "GAB DEP Alex Brasil", "900") + linha_servidor("João", "", "DIRETORIA", "901"))
    assert linhas == [{"nome": "Maria", "vinculo": "CC-1", "lotacao": "GAB DEP Alex Brasil", "matricula": "900"},
                      {"nome": "João", "vinculo": "", "lotacao": "DIRETORIA", "matricula": "901"}]


def test_coletar_gabinete_grava_servidores_sem_o_proprio_deputado(tmp_path, monkeypatch):
    lista = opcao(5, "GAB DEP Alex Brasil") + opcao(7, "GAB DEP Fulano Inexistente")
    pagina = linha_servidor("Maria", "CC-1", "GAB DEP Alex Brasil", "900") + linha_servidor("Alex Brasil", "Deputado", "GAB DEP Alex Brasil", "901")
    chamadas = fingir_baixar(monkeypatch, lambda url, params: pagina if "setor_id" in params else lista)
    sc.coletar_gabinete(None, tmp_path, DEPUTADOS, date(2026, 11, 3), "2026-11-03")
    env = comum.ler(tmp_path / "gabinete.json")
    assert env["itens"] == [{"idDeputado": "10", "matricula": "900", "nome": "Maria", "simbolo": "CC-1"}]
    assert [p["setor_id"] for u, p in chamadas if "setor_id" in p] == ["5", "5"]


def test_coletar_gabinete_recente_nao_baixa(tmp_path, monkeypatch):
    comum.salvar(tmp_path / "gabinete.json", {"coletadoEm": "2026-11-01", "itens": []})
    chamadas = fingir_baixar(monkeypatch, lambda url, params: "")
    sc.coletar_gabinete(None, tmp_path, DEPUTADOS, date(2026, 11, 3), "2026-11-03")
    assert chamadas == []


def test_coletar_gabinete_sem_servidor_ligado_levanta(tmp_path, monkeypatch):
    lista = opcao(7, "GAB DEP Fulano Inexistente")
    fingir_baixar(monkeypatch, lambda url, params: lista if "setor_id" not in params else linha_servidor("Maria", "CC-1", "x", "900"))
    with pytest.raises(RuntimeError, match="nenhum servidor"):
        sc.coletar_gabinete(None, tmp_path, DEPUTADOS, date(2026, 11, 3), "2026-11-03")
    assert not (tmp_path / "gabinete.json").exists()


def test_contratos_da_pagina_ata_e_contrato():
    html = (cartao_contrato("77", "12/2026", "Ata de Registro de Preço", "EMPRESA ALFA LTDA", "11.222.333/0001-81", "Material de expediente",
                            "R$ 1.000,00", "- Pregão", "01/01/2026 - 31/12/2026", "Vigente")
            + cartao_contrato("78", "13/2026", "Contrato", "BETA SERVICOS", "", "Limpeza", "R$ 50,00", "- ", "05/02/2026 -", "Vigente", download=False)
            + '<article class="card card-alesc">sem link</article>')
    itens = {i["idFonte"]: i for i in sc.contratos_da_pagina(html).values()}
    assert set(itens) == {"77", "78"}
    ata, contrato = itens["77"], itens["78"]
    assert ata["tipo"] == "ata_registro" and ata["numero"] == "12/2026" and ata["fornecedor"] == "EMPRESA ALFA LTDA" and ata["cnpj"] == "11222333000181"
    assert ata["valor"] == 1000.0 and ata["objeto"] == "Material de expediente" and ata["inicio"] == "2026-01-01" and ata["fim"] == "2026-12-31"
    assert ata["modalidade"] == "Pregão" and ata["situacao"] == "Vigente" and ata["fonte"] == f"{sc.CONTRATOS_URL}/77"
    assert ata["arquivos"] == [{"nome": "Contrato (PDF)", "url": f"{sc.TRANSPARENCIA}/contratos/download/77"}]
    assert contrato["tipo"] == "contrato" and contrato["cnpj"] is None and contrato["fim"] is None and contrato["modalidade"] is None
    assert contrato["inicio"] == "2026-02-05" and contrato["arquivos"] == []


def cartao_unico():
    return cartao_contrato("77", "12/2026", "Contrato", "EMPRESA ALFA LTDA", "11.222.333/0001-81", "Objeto", "R$ 1,00", "- Pregão", "01/01/2026 - 31/12/2026", "Vigente")


def test_coletar_orgao_grava_e_para_na_pagina_repetida(tmp_path, monkeypatch):
    monkeypatch.setattr(sc, "PRIMEIRO_ANO", 2026)
    chamadas = fingir_baixar(monkeypatch, lambda url, params: cartao_unico())
    sc.coletar_orgao(None, tmp_path, date(2026, 11, 3), "2026-11-03")
    assert [p["page"] for u, p in chamadas] == [1, 2]
    env = comum.ler(tmp_path / "orgao_2026.json")
    assert len(env["itens"]) == 1 and env["fonte"] == f"{sc.CONTRATOS_URL}?ano_vigencia=2026"


def test_coletar_orgao_lista_vazia_mantem_o_arquivo_anterior(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sc, "PRIMEIRO_ANO", 2026)
    original = {"itens": {"x": {"idFonte": "1"}}}
    comum.salvar(tmp_path / "orgao_2026.json", original)
    fingir_baixar(monkeypatch, lambda url, params: "")
    sc.coletar_orgao(None, tmp_path, date(2026, 11, 3), "2026-11-03")
    assert "contratos 2026: lista vazia" in capsys.readouterr().err
    assert comum.ler(tmp_path / "orgao_2026.json") == original


def test_coletar_orgao_ano_encerrado_nao_e_baixado(tmp_path, monkeypatch):
    monkeypatch.setattr(sc, "PRIMEIRO_ANO", 2023)
    (tmp_path / "orgao_2023.json").write_text("{}", encoding="utf-8")
    chamadas = fingir_baixar(monkeypatch, lambda url, params: "")
    sc.coletar_orgao(None, tmp_path, date(2026, 11, 3), "2026-11-03")
    assert 2023 not in {p["ano_vigencia"] for u, p in chamadas}
    assert (tmp_path / "orgao_2023.json").read_text(encoding="utf-8") == "{}"


def test_regras_da_cota_escolhe_o_ato_mais_novo_sobre_cotas():
    regra = sc.regras_da_cota(REGRAS_HTML)
    assert regra["url"] == f"{sc.LEIS}/ato-normativo/legislativo/2" and regra["ano"] == 2023 and regra["titulo"] == "Ato da Mesa 5/2023"
    assert regra["fonte"] == f"{sc.REGRAS_URL}#gabinetes-parlamentares"
    assert [d["ano"] for d in regra["documentos"]] == [2019, 2023, 2024]


def test_regras_da_cota_sem_secao_ou_sem_ato_de_cota():
    assert sc.regras_da_cota("<html></html>") is None
    sem_cota = '<section id="gabinetes-parlamentares"><a href="/ato-normativo/legislativo/3">Ato 8/2024</a><p class="fst-italic mb-2">Dispõe sobre férias</p></section>'
    assert sc.regras_da_cota(sem_cota) is None


def test_coletar_regras_grava_e_levanta_sem_ato(tmp_path, monkeypatch):
    fingir_baixar(monkeypatch, lambda url, params: REGRAS_HTML)
    sc.coletar_regras(None, tmp_path)
    assert comum.ler(tmp_path / "regras_ressarcimento.json")["ano"] == 2023
    fingir_baixar(monkeypatch, lambda url, params: "<html></html>")
    with pytest.raises(RuntimeError, match="sem ato sobre as cotas"):
        sc.coletar_regras(None, tmp_path / "outra")
    assert not (tmp_path / "outra").exists()
