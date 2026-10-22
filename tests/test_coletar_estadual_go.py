import json

import pytest

import coletar_estadual_go as go
from conftest import RAIZ

FIX = RAIZ / "tests" / "fixtures" / "contratos"

DEPUTADOS = [
    {"id": "117", "nome": "Charles Bento", "nomeCivil": "Charles Bento Evangelista"},
    {"id": "808", "nome": "Alessandro Moreira", "nomeCivil": "Alessandro Moreira dos Santos"},
    {"id": "6", "nome": "Cristóvão Tormin", "nomeCivil": "Cristóvão Tormin"},
]


@pytest.fixture(autouse=True)
def sem_espera(monkeypatch):
    monkeypatch.setattr(go, "INTERVALO", 0)


def amostra(nome):
    return json.loads((FIX / f"{nome}.json").read_text(encoding="utf-8"))["amostra"]


class Resposta:
    def __init__(self, dados, total=None, status=200):
        self.dados, self.status_code = dados, status
        self.headers = {"TotalLinhas": str(total)} if total is not None else {}
        self.encoding = None
        self.text = ""

    def json(self):
        return self.dados

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class Sessao:
    def __init__(self, respostas):
        self.respostas, self.chamadas = list(respostas), []

    def get(self, url, params=None, timeout=None):
        self.chamadas.append(params)
        return self.respostas.pop(0)


def test_contratos_registrados():
    nomes = [c["nome"] for c in go.CONTRATOS]
    assert nomes == ["estadual_go_lista", "estadual_go_perfil", "estadual_go_verbas", "estadual_go_remuneracao",
                     "estadual_go_diarias", "estadual_go_requerimentos", "estadual_go_votacoes"]
    for c in go.CONTRATOS:
        falhas, _ = c["html"](amostra(c["nome"]))
        assert falhas == [], c["nome"]


def test_parse_lista_e_perfil():
    lista = go.parse_lista(amostra("estadual_go_lista")["html"])
    assert lista[0]["id"].isdigit() and lista[0]["nome"] and lista[0]["partido"] and len(lista[0]["partido"]) <= 12
    perfil = go.parse_perfil(amostra("estadual_go_perfil")["html"])
    assert perfil["nomeCivil"] and perfil["foto"].startswith("https://") and "@" in perfil["email"]


def test_parse_lista_partido_em_sigla():
    html = ('<table><tr data-target="search.filterable" data-filter-key="x"><td data-title="Nome">'
            '<a class="link" href=/deputados/perfil/117>Charles Bento</a></td>'
            '<td data-title="Partido"> MOVIMENTO DEMOCRÁTICO BRASILEIRO (MDB)</td>'
            '<td><a href="mailto:charlesbento@al.go.leg.br" target="_blank">x</a></td></tr></table>')
    assert go.parse_lista(html) == [{"id": "117", "nome": "Charles Bento", "partido": "MDB", "email": "charlesbento@al.go.leg.br"}]


def test_montar_deputados_usa_perfil_e_ordena():
    lista = [{"id": "808", "nome": "Alessandro Moreira", "partido": "PRD", "email": "a@x"}, {"id": "117", "nome": "Charles Bento", "partido": "MDB", "email": "c@x"}]
    perfis = {"117": {"nomeCivil": "Charles Bento Evangelista", "foto": "http://f", "email": None}}
    deputados = go.montar_deputados(lista, perfis)
    assert [d["id"] for d in deputados] == ["808", "117"]
    assert deputados[0]["nomeCivil"] is None and deputados[0]["email"] == "a@x"
    assert deputados[1]["nomeCivil"] == "Charles Bento Evangelista" and deputados[1]["email"] == "c@x"
    assert deputados[1]["fonte"] == "https://portal.al.go.leg.br/deputados/perfil/117"


def test_paginar_para_no_total_de_linhas():
    s = Sessao([Resposta([{"id": 1}, {"id": 2}], total=3), Resposta([{"id": 3}], total=3)])
    assert go.paginar(s, "x", ano=2026) == [{"id": 1}, {"id": 2}, {"id": 3}]
    assert [c["pagina"] for c in s.chamadas] == [1, 2]


def test_paginar_para_em_pagina_vazia_ou_repetida():
    assert go.paginar(Sessao([Resposta([{"id": 1}]), Resposta([])]), "x") == [{"id": 1}]
    assert go.paginar(Sessao([Resposta([{"id": 1}]), Resposta([{"id": 1}])]), "x") == [{"id": 1}]


def test_pegar_repete_depois_de_403(monkeypatch):
    monkeypatch.setattr(go.time, "sleep", lambda *_: None)
    s = Sessao([Resposta(None, status=403), Resposta([{"id": 1}])])
    assert go.pegar_json(s, "x") == [{"id": 1}]


def test_itens_verba_so_deputados_em_exercicio():
    registros = amostra("estadual_go_verbas")
    ids = {str(registros[0]["deputado"]["id"])}
    itens = go.itens_verba(registros, ids, 2026, 8)
    assert len(itens) == 1 and itens[0]["idDeputado"] in ids and itens[0]["mes"] == 8
    assert itens[0]["valor"] == float(registros[0]["valor_indenizado"])
    assert itens[0]["fonte"] == f"https://transparencia.al.go.leg.br/gestao-parlamentar/verba-indenizatoria/exibir/{itens[0]['idDeputado']}/2026/8"


def test_item_remuneracao_soma_componentes():
    r = {"matricula": 101025100, "nome": "ALESSANDRO MOREIRA DOS SANTOS", "vencimento": "22435.25", "indenizacoes": "7478.41", "auxilios": "4370.02",
         "ferias": "0.0", "remuneracao_bruta": "0.0", "remuneracao_liquida": "25403.99", "desconto_obrigatorios": "5977.31", "status": "-"}
    item = go.item_remuneracao(r, "808", 2026, 8)
    assert item["bruto"] == 34283.68 and item["liquido"] == 25403.99 and item["status"] is None
    assert item["componentes"] == {"Vencimento": 22435.25, "Indenizações": 7478.41, "Auxílios": 4370.02}
    assert item["descontos"] == {"Descontos obrigatórios": 5977.31}
    assert item["fonte"].endswith("?ano=2026&mes=8&matricula=101025100")
    assert go.item_remuneracao({**r, "status": "LICENÇA SAÚDE"}, "808", 2026, 8)["status"] == "LICENÇA SAÚDE"


def test_ligacao_da_remuneracao_pelo_nome_civil():
    ligados = go.comum.ligar_nomes({"ALESSANDRO MOREIRA DOS SANTOS", "CHARLES BENTO EVANGELISTA", "FULANO"}, DEPUTADOS)
    assert ligados == {"ALESSANDRO MOREIRA DOS SANTOS": "808", "CHARLES BENTO EVANGELISTA": "117"}


def test_itens_diarias_filtra_deputado_e_assessor():
    base = {"id": 1, "data_inicio": "2026-08-10", "data_fim": "2026-08-15", "trecho": "Goiânia/GO - Anápolis/GO", "motivo": "Missão\n institucional",
            "total": "2035.0"}
    registros = [{**base, "beneficiario": "CHARLES BENTO EVANGELISTA", "cargo": "DEPUTADO ESTADUAL"},
                 {**base, "id": 2, "beneficiario": "CHARLES BENTO EVANGELISTA", "cargo": "ASSESSOR NIVEL VIII"},
                 {**base, "id": 3, "beneficiario": "OUTRO NOME", "cargo": "DEPUTADO ESTADUAL"}]
    itens = go.itens_diarias(registros, "117", "Charles Bento Evangelista")
    assert itens == [{"idDeputado": "117", "data": "2026-08-10", "dataFim": "2026-08-15", "destino": "Goiânia/GO - Anápolis/GO",
                      "motivo": "Missão institucional", "valor": 2035.0,
                      "fonte": "https://transparencia.al.go.leg.br/prestacao-de-contas/diarias-e-ajudas-de-custo/1"}]


def test_montar_votacoes_agrupa_por_pauta_e_ignora_secreto():
    def linha(pauta, parlamentar, voto, tipo="NOMINAL", resultado="APROVADO EM 1ª DISCUSSÃO"):
        return {"pauta_id": pauta, "parlamentar": parlamentar, "tipo_voto": voto, "tipo_votacao": tipo, "mes": 5.0,
                "data_sessao": "2025-05-29", "resultado_votacao": resultado, "ementa_projeto": "AUTOR - X\nASSUNTO - Y"}
    linhas = [linha(1, "Charles Bento", "SIM"), linha(1, "CRISTÓVÃO TORMIN", "NAO"), linha(1, "Fulano", "SIM"),
              linha(1, "Alessandro Moreira", "ABSTENCAO"), linha(2, "Charles Bento", "SECRETO", tipo="SECRETA"),
              linha(3, "Charles Bento", "SIM", resultado="REJEITADO")]
    ligacao = go.comum.ligar_nomes({l["parlamentar"] for l in linhas}, DEPUTADOS)
    votacoes, materias = go.montar_votacoes(linhas, ligacao, 2025)
    assert set(votacoes) == {"1", "3"}
    v = votacoes["1"]
    assert (v["sim"], v["nao"], v["abstencoes"], v["aprovada"]) == (2, 1, 1, True)
    assert v["votos"] == [["117", "Sim"], ["6", "Não"], ["808", "Abstenção"]]
    assert v["fonte"].endswith("votacoes?tipo=detalhes&ano=2025&mes=5") and votacoes["3"]["aprovada"] is False
    assert materias["1"]["ementa"] == "AUTOR - X ASSUNTO - Y" and materias["1"]["ano"] == 2025


def test_itens_requerimentos_so_de_deputado_ligado():
    registros = [{"id": 34455, "numero": 1815, "deputado": {"nome": "Charles Bento Evangelista"}, "tipo_requerimento": {"descricao": "Conhecimento e Providência"},
                  "etapa": {"descricao": "Aprovado"}, "url_download": "https://saba.al.go.leg.br/x"},
                 {"id": 2, "numero": 1, "deputado": {"nome": "Ex Deputado"}, "tipo_requerimento": None, "etapa": None, "url_download": None}]
    ligacao = go.comum.ligar_nomes({r["deputado"]["nome"] for r in registros}, DEPUTADOS)
    materias = go.itens_requerimentos(registros, ligacao, 2023)
    assert list(materias) == ["34455"]
    m = materias["34455"]
    assert m["idsDeputados"] == ["117"] and m["situacao"] == "Aprovado" and m["linkTexto"] == "https://saba.al.go.leg.br/x"
    assert m["ementa"] == "Requerimento nº 1815: Conhecimento e Providência" and m["ano"] == 2023
