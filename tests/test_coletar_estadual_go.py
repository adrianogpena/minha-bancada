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
    ligados = go.identidades.ligar_nomes({"ALESSANDRO MOREIRA DOS SANTOS", "CHARLES BENTO EVANGELISTA", "FULANO"}, DEPUTADOS)
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
    ligacao = go.identidades.ligar_nomes({lin["parlamentar"] for lin in linhas}, DEPUTADOS)
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
    ligacao = go.identidades.ligar_nomes({r["deputado"]["nome"] for r in registros}, DEPUTADOS)
    materias = go.itens_requerimentos(registros, ligacao, 2023)
    assert list(materias) == ["34455"]
    m = materias["34455"]
    assert m["idsDeputados"] == ["117"] and m["situacao"] == "Aprovado" and m["linkTexto"] == "https://saba.al.go.leg.br/x"
    assert m["ementa"] == "Requerimento nº 1815: Conhecimento e Providência" and m["ano"] == 2023


class Hoje(go.date):
    @classmethod
    def today(cls):
        return cls(2026, 10, 22)


def test_verbas_le_so_meses_que_faltam_e_os_recentes(monkeypatch, tmp_path):
    monkeypatch.setattr(go, "date", Hoje)
    monkeypatch.setattr(go, "PASTA", tmp_path)
    lidos = []

    def paginar(s, caminho, ano, mes):
        lidos.append((ano, mes))
        return [{"deputado": {"id": 117}, "valor_indenizado": "10,00", "valor_apresentado": "10,00"}]

    monkeypatch.setattr(go, "paginar", paginar)

    def guardado(ano, meses):
        return {"itens": [{"idDeputado": "117", "mes": m, "valor": 1.0} for m in meses]}

    go.comum.salvar(tmp_path / "verbas_2024.json", guardado(2024, [1]))
    go.comum.salvar(tmp_path / "verbas_2025.json", guardado(2025, range(1, 13)))
    go.comum.salvar(tmp_path / "verbas_2026.json", guardado(2026, range(1, 11)))
    go.coletar_verbas(None, DEPUTADOS)
    assert sorted(lidos) == [(2023, m) for m in range(1, 13)] + [(2026, 9), (2026, 10)]
    itens = go.comum.ler(tmp_path / "verbas_2026.json")["itens"]
    assert [i["mes"] for i in itens] == list(range(1, 11))
    assert [i["valor"] for i in itens if i["mes"] >= 9] == [10.0, 10.0]


def test_votacoes_de_anos_encerrados_vem_do_arquivo(monkeypatch, tmp_path):
    monkeypatch.setattr(go, "date", Hoje)
    monkeypatch.setattr(go, "PASTA", tmp_path)
    go.comum.salvar(tmp_path / "votacoes.json", {"votacoes": {"1": {"data": "2023-05-02", "votos": []}, "2": {"data": "2025-05-02", "votos": []}}})
    go.comum.salvar(tmp_path / "materias_votadas.json", {"1": {"ano": 2023}, "2": {"ano": 2025}})
    lidos = []
    monkeypatch.setattr(go, "pegar_json", lambda s, caminho, tipo, ano: lidos.append(ano) or [])
    go.coletar_votacoes(None, DEPUTADOS)
    assert lidos == [2025, 2026]
    assert list(go.comum.ler(tmp_path / "votacoes.json")["votacoes"]) == ["1"]
    assert go.comum.ler(tmp_path / "materias_votadas.json") == {"1": {"ano": 2023}}


def test_ficha_so_e_lida_para_quem_nao_tem_nome_civil_guardado(monkeypatch, tmp_path):
    monkeypatch.setattr(go, "PASTA", tmp_path)
    go.comum.salvar(tmp_path / "deputados.json", {"deputados": [{"id": "117", "nomeCivil": "Charles Bento Evangelista", "foto": "f.jpg", "email": None}]})
    monkeypatch.setattr(go, "parse_lista", lambda html: [{"id": "117", "nome": "Charles Bento"}, {"id": "808", "nome": "Alessandro Moreira"}])
    lidas = []
    monkeypatch.setattr(go, "pegar_html", lambda s, url: lidas.append(url) or "")
    deputados = {d["id"]: d for d in go.coletar_deputados(None)}
    assert lidas == [go.LISTA_URL, go.PERFIL_URL.format(id="808")]
    assert deputados["117"]["nomeCivil"] == "Charles Bento Evangelista" and deputados["117"]["foto"] == "f.jpg"


def linha_votacao(pauta, parlamentar, voto="SIM", ano="2025"):
    return {"pauta_id": pauta, "parlamentar": parlamentar, "tipo_voto": voto, "tipo_votacao": "NOMINAL", "mes": 5.0,
            "data_sessao": f"{ano}-05-29", "resultado_votacao": "APROVADO", "ementa_projeto": "X"}


REGISTRO_REMUNERACAO = {"nome": "CHARLES BENTO EVANGELISTA", "matricula": 101, "vencimento": "1000.00", "remuneracao_liquida": "900.00", "status": "-"}


def test_pegar_erro_que_nao_e_403_nao_repete():
    s = Sessao([Resposta(None, status=500), Resposta([{"id": 1}])])
    with pytest.raises(RuntimeError, match="500"):
        go.pegar(s, f"{go.API}/x")
    assert len(s.chamadas) == 1


def test_pegar_esgota_as_tentativas_no_403(monkeypatch):
    monkeypatch.setattr(go.time, "sleep", lambda *_: None)
    s = Sessao([Resposta(None, status=403) for _ in range(4)])
    with pytest.raises(RuntimeError, match="403"):
        go.pegar(s, f"{go.API}/x")
    assert len(s.chamadas) == 4


def test_pegar_html_devolve_o_texto():
    r = Resposta(None)
    r.text = "<p>oi</p>"
    assert go.pegar_html(Sessao([r]), "http://x") == "<p>oi</p>"


def test_paginar_propaga_erro_de_pagina():
    s = Sessao([Resposta([{"id": 1}], total=5), Resposta(None, status=500)])
    with pytest.raises(RuntimeError, match="500"):
        go.paginar(s, "x")


def test_parsers_e_conversoes_com_entrada_vazia():
    assert go.sigla_partido("") is None
    assert go.parse_lista("") == []
    assert go.parse_perfil("") == {"nomeCivil": None, "foto": None, "email": None}
    assert go.float_ou_zero("abc") == 0.0 and go.float_ou_zero(None) == 0.0 and go.float_ou_zero("1,5") == 1.5


def test_coletar_deputados_com_lista_vazia(monkeypatch, tmp_path):
    monkeypatch.setattr(go, "PASTA", tmp_path)
    monkeypatch.setattr(go, "parse_lista", lambda html: [])
    monkeypatch.setattr(go, "pegar_html", lambda s, url: "")
    assert go.coletar_deputados(None) == []


def test_coletar_deputados_avisa_ficha_que_falha(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(go, "PASTA", tmp_path)
    monkeypatch.setattr(go, "parse_lista", lambda html: [{"id": "808", "nome": "Alessandro Moreira", "partido": "PRD", "email": None}])

    def pegar_html(s, url):
        if url == go.LISTA_URL:
            return ""
        raise RuntimeError("ficha fora do ar")

    monkeypatch.setattr(go, "pegar_html", pegar_html)
    deputados = go.coletar_deputados(None)
    assert [d["id"] for d in deputados] == ["808"] and deputados[0]["nomeCivil"] is None
    assert "ficha de Alessandro Moreira: ficha fora do ar" in capsys.readouterr().err


def test_verbas_erro_de_mes_propaga_e_nao_grava(monkeypatch, tmp_path):
    monkeypatch.setattr(go, "date", Hoje)
    monkeypatch.setattr(go, "PASTA", tmp_path)

    def paginar(s, caminho, **params):
        raise RuntimeError("API fora do ar")

    monkeypatch.setattr(go, "paginar", paginar)
    with pytest.raises(RuntimeError, match="fora do ar"):
        go.coletar_verbas(None, DEPUTADOS)
    assert list(tmp_path.iterdir()) == []


def test_remuneracao_le_so_meses_que_faltam_e_avisa_nome_sem_par(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(go, "date", Hoje)
    monkeypatch.setattr(go, "PASTA", tmp_path)
    go.comum.salvar(tmp_path / "remuneracao_2026.json", {"itens": [{"idDeputado": "117", "mes": m, "bruto": 1.0} for m in range(1, 9)]})
    lidos = []

    def paginar(s, caminho, **params):
        lidos.append((params["ano"], params["mes"], params["categoria"]))
        return [REGISTRO_REMUNERACAO, {"nome": "FULANO SEM PAR", "matricula": 102, "vencimento": "5.00"}]

    monkeypatch.setattr(go, "paginar", paginar)
    go.coletar_remuneracao(None, DEPUTADOS)
    assert lidos == [(2026, 9, 7), (2026, 10, 7)]
    itens = go.comum.ler(tmp_path / "remuneracao_2026.json")["itens"]
    assert [i["mes"] for i in itens] == list(range(1, 11)) and {i["idDeputado"] for i in itens} == {"117"}
    assert itens[-1]["bruto"] == 1000.0 and itens[-1]["liquido"] == 900.0
    assert "sem deputado em exercício (1)" in capsys.readouterr().err


def test_remuneracao_sem_itens_nao_grava_arquivo(monkeypatch, tmp_path):
    monkeypatch.setattr(go, "date", Hoje)
    monkeypatch.setattr(go, "PASTA", tmp_path)
    monkeypatch.setattr(go, "paginar", lambda s, caminho, **params: [])
    go.coletar_remuneracao(None, DEPUTADOS)
    assert not (tmp_path / "remuneracao_2026.json").exists()


def test_remuneracao_ano_encerrado_nao_e_lido(monkeypatch, tmp_path):
    monkeypatch.setattr(go, "date", Hoje)
    monkeypatch.setattr(go, "PASTA", tmp_path)
    monkeypatch.setattr(go, "ANO_INICIAL_REMUNERACAO", 2023)
    (tmp_path / "remuneracao_2023.json").write_text("{}", encoding="utf-8")
    anos = set()
    monkeypatch.setattr(go, "paginar", lambda s, caminho, **params: anos.add(params["ano"]) or [])
    go.coletar_remuneracao(None, DEPUTADOS)
    assert anos == {2024, 2025, 2026}


def test_diarias_le_por_deputado_e_pula_ano_encerrado(monkeypatch, tmp_path):
    monkeypatch.setattr(go, "date", Hoje)
    monkeypatch.setattr(go, "PASTA", tmp_path)
    (tmp_path / "diarias_2023.json").write_text("{}", encoding="utf-8")
    chamadas = []
    registro = {"id": 1, "beneficiario": "Charles Bento Evangelista", "cargo": "DEPUTADO ESTADUAL", "data_inicio": "2026-08-10", "data_fim": "2026-08-15",
                "trecho": "X", "motivo": "M", "total": "100.0"}

    def paginar(s, caminho, **params):
        chamadas.append((params["ano"], params["favorecido"]))
        return [registro] if params["favorecido"] == "CHARLES BENTO EVANGELISTA" else []

    monkeypatch.setattr(go, "paginar", paginar)
    go.coletar_diarias(None, DEPUTADOS + [{"id": "9", "nome": "Sem Civil", "nomeCivil": None}])
    assert {a for a, _ in chamadas} == {2024, 2025, 2026} and len(chamadas) == 9
    assert ("2026", "SEM CIVIL") not in {(str(a), f) for a, f in chamadas}
    env = go.comum.ler(tmp_path / "diarias_2026.json")
    assert env["coletadoEm"] == "2026-10-22" and [i["idDeputado"] for i in env["itens"]] == ["117"]
    assert (tmp_path / "diarias_2023.json").read_text(encoding="utf-8") == "{}"


def test_ano_da_votacao():
    assert go.ano_da_votacao({"data": "2025-05-02"}) == 2025
    assert go.ano_da_votacao({}) == 0
    assert go.ano_da_votacao({"data": "sem data"}) == 0


def test_montar_votacoes_pauta_sem_voto_ligado():
    votacoes, materias = go.montar_votacoes([linha_votacao(1, "Fulano Qualquer")], {}, 2025)
    assert votacoes["1"]["sim"] == 1 and votacoes["1"]["votos"] == [] and materias["1"]["ano"] == 2025


def test_votacoes_erro_da_fonte_propaga_e_nao_grava(monkeypatch, tmp_path):
    monkeypatch.setattr(go, "date", Hoje)
    monkeypatch.setattr(go, "PASTA", tmp_path)

    def pegar_json(s, caminho, **params):
        raise RuntimeError("API fora do ar")

    monkeypatch.setattr(go, "pegar_json", pegar_json)
    with pytest.raises(RuntimeError, match="fora do ar"):
        go.coletar_votacoes(None, DEPUTADOS)
    assert not (tmp_path / "votacoes.json").exists()


def test_votacoes_avisa_voto_sem_deputado_em_exercicio(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(go, "date", Hoje)
    monkeypatch.setattr(go, "PASTA", tmp_path)
    linhas = [linha_votacao(1, "Charles Bento"), linha_votacao(1, "Fulano Qualquer")]
    monkeypatch.setattr(go, "pegar_json", lambda s, caminho, **params: linhas)
    go.coletar_votacoes(None, DEPUTADOS)
    env = go.comum.ler(tmp_path / "votacoes.json")
    assert list(env["votacoes"]) == ["1"] and env["votacoes"]["1"]["votos"] == [["117", "Sim"]]
    assert "votos sem deputado em exercício (1)" in capsys.readouterr().err


def test_requerimentos_grava_o_ano_e_nao_le_arquivo_existente(monkeypatch, tmp_path):
    monkeypatch.setattr(go, "PASTA", tmp_path)
    lidas = []
    registros = [{"id": 34455, "numero": 1815, "deputado": {"nome": "Charles Bento Evangelista"}, "tipo_requerimento": {"descricao": "Conhecimento"},
                  "etapa": {"descricao": "Aprovado"}, "url_download": "https://saba.al.go.leg.br/x"}]
    monkeypatch.setattr(go, "paginar", lambda s, caminho, **params: lidas.append(params["ano"]) or registros)
    go.coletar_requerimentos(None, DEPUTADOS)
    env = go.comum.ler(tmp_path / "materias_2023.json")
    assert lidas == [2023] and list(env["materias"]) == ["34455"] and env["materias"]["34455"]["idsDeputados"] == ["117"]
    go.coletar_requerimentos(None, DEPUTADOS)
    assert lidas == [2023]


def test_vigencia_troca_datas_invertidas():
    assert go.vigencia("2027-01-01", "2026-05-01") == ("2026-05-01", "2027-01-01")
    assert go.vigencia("2026-01-01", None) == ("2026-01-01", "2026-01-01")
    assert go.vigencia(None, "") == (None, None)


CONTRATO_API = {"id": 5, "numero": " 12/2026 ", "nome_favorecido": "EMPRESA ALFA LTDA", "cpf_cnpj": "11222333000181", "valor_empenhado": 1000.0,
                "valor_pago": 500.0, "descricao": "Serviço", "data_inicio": "2027-01-01", "data_fim": "2026-01-01", "url": "http://c.pdf",
                "aditivo": [{"url_aditivo": "http://a.pdf"}], "licitacao": {"identificador": "PE 1"}, "tipo_contrato": "Serviço", "numero_processo": "P1"}


def test_itens_contratos_ordena_vigencia_e_junta_aditivos():
    itens = go.itens_contratos([CONTRATO_API, {"id": None, "numero": "x"}])
    (item,) = itens.values()
    assert next(iter(itens)).startswith("ctr_") and item["tipo"] == "contrato" and item["idFonte"] == 5 and item["numero"] == "12/2026"
    assert item["inicio"] == "2026-01-01" and item["fim"] == "2027-01-01" and item["cnpj"] == "11222333000181" and item["valor"] == 1000.0
    assert item["valorPago"] == 500.0 and item["licitacao"] == "PE 1" and item["processo"] == "P1" and item["fonte"] == go.ORGAO_PAGINA
    assert [a["url"] for a in item["arquivos"]] == ["http://c.pdf", "http://a.pdf"]


def test_itens_atas_data_de_inicio_pelo_ano_e_mes():
    atas = [{"id": 9, "ano": 2025, "mes": 3, "numero": "1", "fornecedor": {"nome": "FORNECEDOR"}, "objeto": "o", "carona": 1, "url_ata": "http://ata.pdf",
             "licitacao": None},
            {"id": 10, "ano": 2025, "mes": 13, "fornecedor": None},
            {"id": None}]
    itens = {i["idFonte"]: i for i in go.itens_atas(atas).values()}
    assert set(itens) == {9, 10}
    assert itens[9]["tipo"] == "ata_registro" and itens[9]["inicio"] == "2025-03-01" and itens[9]["carona"] is True and itens[9]["cnpj"] is None
    assert itens[9]["arquivos"] == [{"nome": "Ata (PDF)", "url": "http://ata.pdf"}] and itens[9]["fonte"] == go.ATAS_PAGINA
    assert itens[10]["inicio"] is None and itens[10]["fornecedor"] is None


def test_coletar_orgao_grava_por_ano_de_inicio(monkeypatch, tmp_path):
    monkeypatch.setattr(go, "PASTA", tmp_path)
    antigo = {**CONTRATO_API, "id": 6, "data_inicio": "2020-01-01", "data_fim": "2020-12-31"}
    ata = {"id": 9, "ano": 2025, "mes": 3, "fornecedor": {"nome": "F"}}

    def paginar(s, caminho, **params):
        assert params == {"por_pagina": go.POR_PAGINA_ORGAO}
        return [CONTRATO_API, antigo] if caminho.endswith("/contratos") else [ata]

    monkeypatch.setattr(go, "paginar", paginar)
    go.coletar_orgao(None)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["orgao_2025.json", "orgao_2026.json"]
    assert len(go.comum.ler(tmp_path / "orgao_2026.json")["itens"]) == 1


def test_coletar_orgao_vazio_levanta(monkeypatch, tmp_path):
    monkeypatch.setattr(go, "PASTA", tmp_path)
    monkeypatch.setattr(go, "paginar", lambda s, caminho, **params: [])
    with pytest.raises(RuntimeError, match="vazios"):
        go.coletar_orgao(None)
    assert list(tmp_path.iterdir()) == []


LEGISLACOES = {"legislacoes": [
    {"tipo": "Atos Normativos Consolidados", "leis": [{"id": 1, "descricao": "Resolução 1.531/2015 - Cota para o Exercício da Atividade Parlamentar",
                                                       "get_arquivo_view_url": "http://r1", "ultima_atualizacao": "2020-01-01"}]},
    {"tipo": "Decretos", "leis": [{"id": 2, "descricao": "Decreto 9.999/2022 - diárias de viagem", "get_arquivo_view_url": "http://d"},
                                  {"id": 3, "descricao": "Sem link Cota para o Exercício da Atividade Parlamentar", "get_arquivo_view_url": None},
                                  {"id": 4, "descricao": "Lei aleatória", "get_arquivo_view_url": "http://x"}]}]}


def test_regras_da_ceap_consolidada_primeiro_e_documentos_ordenados():
    regra = go.regras_da_ceap(LEGISLACOES)
    assert regra["url"] == "http://r1" and regra["ano"] == 2015 and regra["fonte"] == go.LEGISLACOES_API
    assert [(d["ano"], d["consolidado"]) for d in regra["documentos"]] == [(2015, True), (2022, False)]


def test_regras_da_ceap_sem_resolucao():
    assert go.regras_da_ceap({}) is None
    assert go.regras_da_ceap({"legislacoes": [{"tipo": "Decretos", "leis": [LEGISLACOES["legislacoes"][1]["leis"][0]]}]}) is None


def test_coletar_regras_grava_e_levanta_sem_resolucao(monkeypatch, tmp_path):
    monkeypatch.setattr(go, "PASTA", tmp_path)
    monkeypatch.setattr(go, "pegar_json", lambda s, caminho, **params: LEGISLACOES)
    go.coletar_regras(None)
    assert go.comum.ler(tmp_path / "regras_ressarcimento.json")["ano"] == 2015
    monkeypatch.setattr(go, "pegar_json", lambda s, caminho, **params: {})
    with pytest.raises(RuntimeError, match="não achada"):
        go.coletar_regras(None)


ETAPAS = ("coletar_remuneracao", "coletar_votacoes", "coletar_requerimentos", "coletar_diarias", "coletar_orgao", "coletar_regras")


def test_coletar_roda_todas_as_etapas_e_avisa_a_que_falha(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(go, "PASTA", tmp_path)
    monkeypatch.setattr(go.comum, "sessao", lambda: "sessao")
    monkeypatch.setattr(go, "coletar_deputados", lambda s: [{"id": "117", "nome": "Charles Bento", "nomeCivil": "x"}])
    chamadas = []
    for nome in ETAPAS:
        monkeypatch.setattr(go, nome, lambda *a, _n=nome, **k: chamadas.append(_n))

    def verbas(s, deputados):
        raise RuntimeError("fora do ar")

    monkeypatch.setattr(go, "coletar_verbas", verbas)
    go.coletar()
    assert chamadas == list(ETAPAS)
    assert go.comum.ler(tmp_path / "deputados.json")["host"] is None
    assert "GO: verbas: fora do ar" in capsys.readouterr().err


def test_coletar_sem_deputados_avisa_e_nao_roda_etapas(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(go, "PASTA", tmp_path)
    monkeypatch.setattr(go.comum, "sessao", lambda: "sessao")
    monkeypatch.setattr(go, "coletar_deputados", lambda s: [])
    chamadas = []
    for nome in ("coletar_verbas", *ETAPAS):
        monkeypatch.setattr(go, nome, lambda *a, _n=nome, **k: chamadas.append(_n))
    go.coletar()
    assert chamadas == [] and not (tmp_path / "deputados.json").exists()
    assert "sem deputados em exercício" in capsys.readouterr().err


def test_conferir_com_falhas():
    assert go._conferir_lista({"html": ""}) == (["lista de deputados sem linhas com /deputados/perfil/<id>"], [])
    sem_partido = '<tr data-target="search.filterable"><td><a href=/deputados/perfil/1>Fulano</a></td></tr>'
    assert go._conferir_lista({"html": sem_partido}) == (["linha da lista sem partido"], [])
    assert go._conferir_perfil({"html": ""}) == (["ficha sem nomeCivil", "ficha sem foto", "ficha sem email"], [])
    conferir = go._conferir_campos("id", "numero")
    assert conferir([]) == (["resposta sem itens"], [])
    assert conferir([{"id": 1}]) == (["item sem numero"], [])
