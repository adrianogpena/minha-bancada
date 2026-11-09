import json
from datetime import date

import pytest

import coletar_estadual_mg as mg
import estaduais_comum as comum
from conftest import RAIZ

FIX = RAIZ / "tests" / "fixtures" / "contratos"


def amostra(nome):
    return json.loads((FIX / f"{nome}.json").read_text(encoding="utf-8"))["amostra"]


def test_montar_deputados_com_nome_civil_e_email_da_lista_telefonica():
    a = amostra("estadual_mg_deputados")
    deputados = mg.montar_deputados(a["em_exercicio"]["list"], a["lista_telefonica"]["list"])
    d = deputados[0]
    assert d["id"] == "12193" and d["nome"] == "Adalclever Lopes" and d["nomeCivil"] == "ADALCLEVER RIBEIRO LOPES"
    assert d["email"] == "dep.adalclever.lopes@almg.gov.br" and d["partido"] == "PV" and d["titular"] is True
    assert d["fonte"] == "https://dadosabertos.almg.gov.br/api/v2/deputados/12193?formato=json"


def test_montar_deputados_sem_registro_na_lista_telefonica():
    deputados = mg.montar_deputados([{"id": 1, "nome": "Fulano", "partido": "PT"}], [])
    assert deputados[0]["nomeCivil"] is None and deputados[0]["email"] is None


def test_itens_verba_uma_linha_por_nota():
    a = amostra("estadual_mg_verba")
    itens = mg.itens_verba(a["mes"]["list"], "12193", 8)
    primeiro = itens[0]
    assert primeiro["idDeputado"] == "12193" and primeiro["mes"] == 8 and primeiro["categoria"] == "Combustível e lubrificante"
    assert primeiro["fornecedor"] == "Auto Posto Capixaba Ltda." and primeiro["cnpj"] == "02783114000180"
    assert primeiro["valor"] == 200.0 and primeiro["data"] == "2026-08-06" and primeiro["documento"] == "9706"
    assert primeiro["fonte"] == mg.VERBA_PAGINA


def test_itens_verba_sem_notas_usa_o_valor_do_tipo():
    itens = mg.itens_verba([{"descTipoDespesa": "Aluguel", "valor": 1500.5, "listaDetalheVerba": []}], "7", 3)
    assert itens == [{"idDeputado": "7", "mes": 3, "categoria": "Aluguel", "fornecedor": None, "cnpj": None, "valor": 1500.5,
                      "data": None, "documento": None, "fonte": mg.VERBA_PAGINA}]


def test_meses_fechados_ordena_e_ignora_data_invalida():
    resp = {"listaFechamentoVerba": [{"dataReferencia": "2025-03-01"}, {"dataReferencia": "2025-02-01"}, {"dataReferencia": None}]}
    assert mg.meses_fechados(resp) == [(2025, 2), (2025, 3)]
    assert mg.meses_fechados({}) == []


def test_autores_deputados_le_varios_autores_e_ignora_governador():
    autor = "Deputada Beatriz Cerqueira                 PT\nDeputada Bella Gonçalves                   PT\n"
    assert mg.autores_deputados(autor) == ["Beatriz Cerqueira", "Bella Gonçalves"]
    assert mg.autores_deputados("Governador do Estado\n") == []
    assert mg.autores_deputados("Deputado Rodrigo Lopes                     UNIÃO") == ["Rodrigo Lopes"]


def test_materias_liga_autor_e_corta_ementa():
    deputados = [{"id": "1", "nome": "Beatriz Cerqueira", "nomeCivil": None}, {"id": "2", "nome": "Bella Gonçalves", "nomeCivil": None}]
    itens = [
        {"siglaTipoProjeto": "PL", "tipoProjeto": "PROJETO DE LEI", "numero": "5450", "ano": "2026", "dataPublicacao": "2026-04-09",
         "ementa": "palavra " * 100, "situacao": "Aguardando", "dominio": "Tramitação",
         "autor": "Deputada Beatriz Cerqueira                 PT\nDeputada Bella Gonçalves                   PT\n"},
        {"siglaTipoProjeto": "MSG", "numero": "1", "ano": "2026", "autor": "Governador do Estado\n"},
        {"siglaTipoProjeto": "PL", "numero": "2", "ano": "2026", "autor": "Deputado Desconhecido                      PT\n"},
    ]
    achadas = mg.materias(itens, deputados)
    assert list(achadas) == ["PL-5450-2026"]
    m = achadas["PL-5450-2026"]
    assert m["idsDeputados"] == ["1", "2"] and m["numero"] == 5450 and m["dataApresentacao"] == "2026-04-09" and m["emTramitacao"] is True
    assert m["ementa"].endswith("...") and m["fonte"] == "https://www.almg.gov.br/atividade-parlamentar/projetos-de-lei/texto/?tipo=PL&num=5450&ano=2026"


def test_proposicoes_do_contrato():
    r = amostra("estadual_mg_proposicoes")["resultado"]
    assert r["erro"] is False and r["noOcorrencias"] > 0
    for i in r["listaItem"]:
        for campo in ("siglaTipoProjeto", "numero", "ano", "autor", "ementa", "dataPublicacao"):
            assert i.get(campo)
    deputados = [{"id": "x", "nome": n, "nomeCivil": None} for n in {a for i in r["listaItem"] for a in mg.autores_deputados(i["autor"])}]
    assert mg.materias(r["listaItem"], deputados)


def test_janelas_do_ano_cobre_cada_mes_ate_hoje():
    janelas = mg.janelas_do_ano(2024, date(2024, 3, 10))
    assert janelas == [("20240101", "20240131"), ("20240201", "20240229"), ("20240301", "20240331")]
    assert mg.janelas_do_ano(2025, date(2026, 1, 1))[-1] == ("20251201", "20251231")


def test_proposicoes_da_janela_pagina_ate_acabar(monkeypatch):
    paginas = {1: [{"numero": str(n)} for n in range(100)], 2: [{"numero": "100"}]}
    chamadas = []

    def falso_pegar(sessao, caminho, **params):
        chamadas.append(params)
        return {"resultado": {"erro": False, "noOcorrencias": 101, "listaItem": paginas[params["p"]]}}

    monkeypatch.setattr(mg, "pegar", falso_pegar)
    assert len(mg.proposicoes_da_janela(None, "20260101", "20260131")) == 101
    assert chamadas[0]["ini"] == "20260101" and chamadas[0]["fim"] == "20260131"


def test_coletar_grava_deputados_materias_e_verbas(monkeypatch, tmp_path):
    a, v = amostra("estadual_mg_deputados"), amostra("estadual_mg_verba")
    p = amostra("estadual_mg_proposicoes")["resultado"]
    hoje = date.today()

    def falso_pegar(sessao, caminho, **params):
        if caminho == "deputados/em_exercicio":
            return a["em_exercicio"]
        if caminho == "deputados/lista_telefonica":
            return a["lista_telefonica"]
        if caminho.endswith("/datas"):
            return {"listaFechamentoVerba": [{"dataReferencia": f"{hoje.year}-01-01"}]}
        if caminho.startswith("prestacao_contas"):
            return v["mes"]
        return {"resultado": {"erro": False, "noOcorrencias": len(p["listaItem"]), "listaItem": p["listaItem"]}}

    monkeypatch.setattr(mg, "pegar", falso_pegar)
    monkeypatch.setattr(comum, "DADOS", tmp_path)
    monkeypatch.setattr(comum, "sessao", lambda: None)
    mg.coletar()
    pasta = tmp_path / "MG"
    deputados = json.loads((pasta / "deputados.json").read_text(encoding="utf-8"))
    assert deputados["deputados"][0]["nome"] == "Adalclever Lopes"
    verbas = json.loads((pasta / f"verbas_{hoje.year}.json").read_text(encoding="utf-8"))
    assert verbas["itens"] and all(i["fonte"] == mg.VERBA_PAGINA for i in verbas["itens"])
    assert (pasta / f"materias_{hoje.year}.json").exists()


def test_proposicoes_alteradas_para_na_data_da_coleta_anterior(monkeypatch):
    def item(n, ultima):
        return {"numero": str(n), "dataUltimaAcao": ultima}

    paginas = {1: [item(n, "2026-10-21") for n in range(100)], 2: [item(100, "2026-10-20"), item(101, "2026-10-19"), item(102, "2026-10-01")]}
    chamadas = []

    def falso_pegar(sessao, caminho, **params):
        chamadas.append(params)
        return {"resultado": {"erro": False, "noOcorrencias": 9999, "listaItem": paginas[params["p"]]}}

    monkeypatch.setattr(mg, "pegar", falso_pegar)
    itens = mg.proposicoes_alteradas(None, date(2026, 10, 20), date(2026, 10, 22))
    assert [i["numero"] for i in itens][-2:] == ["100", "101"] and len(itens) == 102   # 19/10 ainda entra (folga de 1 dia); 01/10 não
    assert len(chamadas) == 2 and chamadas[0]["ord"] == 3 and chamadas[0]["ini"] == "20230101" and chamadas[0]["fim"] == "20261022"


def test_juntar_alteradas_troca_a_versao_antiga_de_ano():
    por_ano = {2025: {"PL-1-2025": {"situacao": "velha"}}, 2026: {}}
    nova = {"PL-1-2025": {"situacao": "nova", "dataApresentacao": "2026-01-05", "ano": 2025}, "PL-2-2022": {"dataApresentacao": "2022-01-01", "ano": 2022}}
    mg.juntar_alteradas(por_ano, nova)
    assert por_ano[2025] == {} and por_ano[2026]["PL-1-2025"]["situacao"] == "nova" and "PL-2-2022" not in por_ano[2025]


def test_coletar_proposicoes_incremental_so_le_as_alteradas(monkeypatch, tmp_path):
    a = amostra("estadual_mg_deputados")
    p = amostra("estadual_mg_proposicoes")["resultado"]
    hoje = date(2026, 10, 22)
    deputados = mg.montar_deputados(a["em_exercicio"]["list"], a["lista_telefonica"]["list"])
    for ano in range(mg.PRIMEIRO_ANO_PROPOSICOES, hoje.year + 1):
        comum.salvar(tmp_path / f"materias_{ano}.json", {"coletadoEm": "2026-10-20", "completaEm": "2026-10-15", "fonte": "x", "materias": {}})
    chamadas = []

    def falso_pegar(sessao, caminho, **params):
        chamadas.append(params)
        itens = [{**i, "dataUltimaAcao": "2026-10-21"} for i in p["listaItem"]]
        return {"resultado": {"erro": False, "noOcorrencias": len(itens), "listaItem": itens}}

    monkeypatch.setattr(mg, "pegar", falso_pegar)
    mg.coletar_proposicoes(None, deputados, hoje, tmp_path, "2026-10-22")
    assert len(chamadas) == 1 and chamadas[0]["ord"] == 3
    atual = comum.ler(tmp_path / "materias_2026.json")
    assert atual["coletadoEm"] == "2026-10-22" and atual["completaEm"] == "2026-10-15"

    chamadas.clear()
    comum.salvar(tmp_path / "materias_2026.json", {**atual, "completaEm": "2026-10-01"})   # completa velha: refaz por janelas
    mg.coletar_proposicoes(None, deputados, hoje, tmp_path, "2026-10-22")
    assert all("ord" not in c for c in chamadas) and comum.ler(tmp_path / "materias_2026.json")["completaEm"] == "2026-10-22"


class RespostaMG:
    def __init__(self, dados, erro=None):
        self._dados, self._erro = dados, erro

    def raise_for_status(self):
        if self._erro:
            raise self._erro

    def json(self):
        return self._dados


def test_pegar_monta_url_com_formato_json_e_devolve_o_corpo(monkeypatch):
    monkeypatch.setattr(mg, "PAUSA", 0)
    pedidos = []

    class Sessao:
        def get(self, url, params=None, timeout=None):
            pedidos.append((url, params, timeout))
            return RespostaMG({"list": [1]})

    assert mg.pegar(Sessao(), "deputados/em_exercicio", ini="20260101") == {"list": [1]}
    assert pedidos == [(f"{mg.API}/deputados/em_exercicio", {"formato": "json", "ini": "20260101"}, 60)]


def test_pegar_propaga_erro_http(monkeypatch):
    monkeypatch.setattr(mg, "PAUSA", 0)

    class Sessao:
        def get(self, url, params=None, timeout=None):
            return RespostaMG({}, erro=RuntimeError("503"))

    with pytest.raises(RuntimeError, match="503"):
        mg.pegar(Sessao(), "x")


def test_autores_deputados_vazio_ou_ausente():
    assert mg.autores_deputados("") == []
    assert mg.autores_deputados(None) == []


def test_materias_sem_dominio_fica_sem_tramitacao_e_usa_assunto():
    deputados = [{"id": "9", "nome": "Fulano de Tal", "nomeCivil": None}]
    itens = [
        {"siglaTipoProjeto": "RQN", "numero": "1", "ano": "2026", "assunto": "  Assunto   do requerimento ", "autor": "Deputado Fulano de Tal   PT\n"},
        {"siglaTipoProjeto": "PL", "numero": "2", "ano": "2026", "ementa": "e", "dominio": "Arquivada", "autor": "Deputado Fulano de Tal   PT\n"},
    ]
    achadas = mg.materias(itens, deputados)
    assert achadas["RQN-1-2026"]["emTramitacao"] is None and achadas["RQN-1-2026"]["ementa"] == "Assunto do requerimento"
    assert achadas["PL-2-2026"]["emTramitacao"] is False


def test_janelas_do_ano_futuro_nao_tem_janelas():
    assert mg.janelas_do_ano(2027, date(2026, 5, 1)) == []


def test_proposicoes_da_janela_erro_da_api_levanta(monkeypatch):
    monkeypatch.setattr(mg, "pegar", lambda *a, **k: {"resultado": {"erro": True}})
    with pytest.raises(RuntimeError, match="página 1"):
        mg.proposicoes_da_janela(None, "20260101", "20260131")


def test_proposicoes_alteradas_erro_da_api_levanta(monkeypatch):
    monkeypatch.setattr(mg, "pegar", lambda *a, **k: {"resultado": {"erro": True}})
    with pytest.raises(RuntimeError, match="alteradas"):
        mg.proposicoes_alteradas(None, date(2026, 10, 20), date(2026, 10, 22))


def test_proposicoes_do_ano_junta_janelas_e_ano_futuro_nao_consulta(monkeypatch):
    janelas = []

    def falsa(sessao, ini, fim):
        janelas.append((ini, fim))
        return [{"numero": ini}]

    monkeypatch.setattr(mg, "proposicoes_da_janela", falsa)
    assert mg.proposicoes_do_ano(None, 2026, date(2026, 2, 10)) == [{"numero": "20260101"}, {"numero": "20260201"}]
    assert janelas == [("20260101", "20260131"), ("20260201", "20260228")]
    janelas.clear()
    assert mg.proposicoes_do_ano(None, 2027, date(2026, 2, 10)) == [] and janelas == []


def test_coletar_verba_pula_mes_guardado_rele_recentes_e_avisa_falhas(monkeypatch, tmp_path, capsys):
    hoje = date(2026, 3, 10)
    nota = {"data": None, "categoria": "x"}
    comum.salvar(tmp_path / "verbas_2025.json", {"itens": [{"idDeputado": "2", "mes": 5, **nota}]})
    comum.salvar(tmp_path / "verbas_2026.json", {"itens": [{"idDeputado": "2", "mes": 1, **nota}, {"idDeputado": "2", "mes": 2, **nota}]})
    chamadas = []

    def falso_pegar(sessao, caminho, **params):
        if caminho.endswith("/1/datas"):
            raise RuntimeError("fora do ar")
        if caminho.endswith("/2/datas"):
            datas = ["2024-12-01", "2025-05-01", "2025-06-01", "2026-01-01", "2026-02-01"]
            return {"listaFechamentoVerba": [{"dataReferencia": d} for d in datas]}
        chamadas.append(caminho)
        if caminho.endswith("/2025/6"):
            raise RuntimeError("mês quebrado")
        return {"list": [{"descTipoDespesa": "Aluguel", "valor": 10.0, "listaDetalheVerba": []}]}

    monkeypatch.setattr(mg, "pegar", falso_pegar)
    deputados = [{"id": "1", "nome": "Ana"}, {"id": "2", "nome": "Bia"}]
    mg.coletar_verba(None, deputados, hoje, tmp_path, "2026-03-10")
    base = "prestacao_contas/verbas_indenizatorias/deputados/2"
    assert chamadas == [f"{base}/2025/6", f"{base}/2026/2"]
    erros = capsys.readouterr().err
    assert "MG: verba de Ana: RuntimeError: fora do ar" in erros and "MG: verba de Bia 6/2025" in erros
    assert [i["mes"] for i in comum.ler(tmp_path / "verbas_2025.json")["itens"]] == [5]
    itens_2026 = comum.ler(tmp_path / "verbas_2026.json")["itens"]
    assert [i["mes"] for i in itens_2026] == [1, 2] and itens_2026[1]["valor"] == 10.0
    assert comum.ler(tmp_path / "verbas_2026.json")["coletadoEm"] == "2026-03-10"


def item_de_proposicao():
    return {"siglaTipoProjeto": "PL", "tipoProjeto": "PROJETO DE LEI", "numero": "1", "ano": "2026", "dataPublicacao": "2026-01-05",
            "ementa": "e", "autor": "Deputado Fulano de Tal   PT\n"}


DEPUTADOS_MG = [{"id": "9", "nome": "Fulano de Tal", "nomeCivil": None}]


def test_coletar_proposicoes_sem_arquivo_le_o_ano_pula_encerrado_e_avisa_erro(monkeypatch, tmp_path, capsys):
    hoje = date(2026, 2, 10)
    comum.salvar(tmp_path / "materias_2023.json", {"coletadoEm": "antigo", "materias": {}})
    anos = []

    def falsa(sessao, ano, dia):
        anos.append(ano)
        if ano == 2025:
            raise RuntimeError("API fora")
        return [item_de_proposicao()]

    monkeypatch.setattr(mg, "proposicoes_do_ano", falsa)
    mg.coletar_proposicoes(None, DEPUTADOS_MG, hoje, tmp_path, "2026-02-10")
    assert anos == [2024, 2025, 2026]
    assert comum.ler(tmp_path / "materias_2023.json")["coletadoEm"] == "antigo"
    assert not (tmp_path / "materias_2025.json").exists()
    for ano in (2024, 2026):
        arq = comum.ler(tmp_path / f"materias_{ano}.json")
        assert list(arq["materias"]) == ["PL-1-2026"] and arq["completaEm"] == "2026-02-10" and arq["coletadoEm"] == "2026-02-10"
    assert "MG: proposições 2025: RuntimeError: API fora" in capsys.readouterr().err


def guardar_materias(pasta, hoje):
    for ano in range(mg.PRIMEIRO_ANO_PROPOSICOES, hoje.year + 1):
        comum.salvar(pasta / f"materias_{ano}.json", {"coletadoEm": "2026-10-20", "completaEm": "2026-10-15", "fonte": "x", "materias": {}})


def test_coletar_proposicoes_incremental_com_erro_da_api_avisa_e_nao_grava(monkeypatch, tmp_path, capsys):
    hoje = date(2026, 10, 22)
    guardar_materias(tmp_path, hoje)

    def quebra(*a, **k):
        raise RuntimeError("API fora")

    monkeypatch.setattr(mg, "proposicoes_alteradas", quebra)
    monkeypatch.setattr(mg, "proposicoes_do_ano", lambda *a: pytest.fail("leitura completa depois de erro nas alteradas"))
    mg.coletar_proposicoes(None, DEPUTADOS_MG, hoje, tmp_path, "2026-10-22")
    assert "MG: proposições alteradas: RuntimeError: API fora" in capsys.readouterr().err
    assert all(comum.ler(tmp_path / f"materias_{ano}.json")["coletadoEm"] == "2026-10-20" for ano in range(2023, 2027))


def test_coletar_proposicoes_incremental_so_regrava_ano_atual_e_anos_alterados(monkeypatch, tmp_path):
    hoje = date(2026, 10, 22)
    guardar_materias(tmp_path, hoje)
    monkeypatch.setattr(mg, "proposicoes_alteradas", lambda s, desde, dia: [item_de_proposicao()])
    mg.coletar_proposicoes(None, DEPUTADOS_MG, hoje, tmp_path, "2026-10-22")
    assert comum.ler(tmp_path / "materias_2025.json")["coletadoEm"] == "2026-10-20"
    atual = comum.ler(tmp_path / "materias_2026.json")
    assert atual["coletadoEm"] == "2026-10-22" and list(atual["materias"]) == ["PL-1-2026"]

    comum.salvar(tmp_path / "materias_2025.json", {"coletadoEm": "2026-10-20", "completaEm": "2026-10-15", "fonte": "x", "materias": {"PL-1-2026": {"situacao": "velha"}}})
    mg.coletar_proposicoes(None, DEPUTADOS_MG, hoje, tmp_path, "2026-10-22")
    assert comum.ler(tmp_path / "materias_2025.json")["materias"] == {}
    assert comum.ler(tmp_path / "materias_2025.json")["coletadoEm"] == "2026-10-22"


def test_coletar_sem_deputados_em_exercicio_avisa_e_nao_grava(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(mg, "pegar", lambda *a, **k: {"list": []})
    monkeypatch.setattr(comum, "DADOS", tmp_path)
    monkeypatch.setattr(comum, "sessao", lambda: None)
    monkeypatch.setattr(mg, "coletar_proposicoes", lambda *a: pytest.fail("proposições sem deputados"))
    monkeypatch.setattr(mg, "coletar_verba", lambda *a: pytest.fail("verba sem deputados"))
    mg.coletar()
    assert "MG: lista de deputados vazia" in capsys.readouterr().err
    assert not (tmp_path / "MG" / "deputados.json").exists()
