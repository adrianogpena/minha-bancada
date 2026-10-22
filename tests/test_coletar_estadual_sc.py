import json
from datetime import date

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
