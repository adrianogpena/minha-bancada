import json
from datetime import date

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


def test_recentes():
    assert mg.recentes(date(2026, 1, 10)) == {(2026, 1), (2025, 12)}


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
