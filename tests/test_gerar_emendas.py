import json

import gerar_emendas as ge


def item(codigo, ano, municipio, uf, empenhado, pago):
    return {"pessoa": "pes_a", "codigo": codigo, "ano": ano, "autor": "A", "tipo": "Individual", "local": f"{municipio} ({uf})", "municipio": municipio,
            "uf": uf, "empenhado": empenhado, "pago": pago}


def test_resume_por_ano_e_municipio_e_ordena_itens():
    r = ge.construir([item("1", 2023, "CAMPINAS", "SP", 100.0, 40.0), item("2", 2024, "CAMPINAS", "SP", 50.0, 50.0),
                      item("3", 2024, "SANTOS", "SP", 200.0, 0.0), {"pessoa": "pes_a", "codigo": "4", "ano": 2024, "autor": "A", "local": "CEARÁ", "empenhado": 1.0}])["pes_a"]
    assert [(a["ano"], a["n"], a["empenhado"], a["pago"]) for a in r["anos"]] == [(2024, 3, 251.0, 50.0), (2023, 1, 100.0, 40.0)]
    assert [(m["nome"], m["empenhado"], m["pago"], m["n"]) for m in r["municipios"]] == [("SANTOS", 200.0, 0.0, 1), ("CAMPINAS", 150.0, 90.0, 2)]
    assert [i["codigo"] for i in r["itens"]] == ["3", "2", "4", "1"]
    assert "pessoa" not in r["itens"][0] and "autor" not in r["itens"][0]


def test_totais_por_funcao_ordenam_pelo_empenhado_e_agrupam_sem_area():
    com = lambda c, f, emp, pago: {**item(c, 2024, "SANTOS", "SP", emp, pago), **({"funcao": f} if f else {})}
    r = ge.construir([com("1", "Saúde", 10.0, 5.0), com("2", "Educação", 30.0, 0.0), com("3", "Saúde", 25.0, 25.0), com("4", None, 1.0, 0.0)])["pes_a"]
    assert r["funcoes"] == [{"nome": "Saúde", "n": 2, "empenhado": 35.0, "pago": 30.0}, {"nome": "Educação", "n": 1, "empenhado": 30.0, "pago": 0.0},
                            {"nome": "Sem área informada", "n": 1, "empenhado": 1.0, "pago": 0.0}]


def test_salva_um_arquivo_por_pessoa(tmp_path):
    assert ge.salvar([item("1", 2024, "SANTOS", "SP", 1.0, 1.0)], tmp_path, planos={}) == 1
    assert json.loads((tmp_path / "emendas" / "pes_a.json").read_text(encoding="utf-8"))["anos"][0]["ano"] == 2024


def test_municipio_ganha_codigo_ibge_e_soma_das_emendas_pix():
    nomes = {"3509502": ["SP", "CAMPINAS"], "3548500": ["SP", "SANTOS"], "5101605": ["MT", "SANTO ANTONIO DO LEVERGER"]}
    pix = {**item("1", 2024, "CAMPINAS", "SP", 100.0, 30.0), "tipo": "Emenda Individual - Transferências Especiais"}
    r = ge.construir([pix, item("2", 2024, "CAMPINAS", "SP", 50.0, 50.0), item("3", 2024, "SANTOS", "SP", 10.0, 0.0),
                      item("4", 2024, "SANTO ANTÔNIO DE LEVERGER", "MT", 5.0, 5.0), item("5", 2024, "OUTRA", "SP", 1.0, 1.0)], nomes)["pes_a"]
    por_nome = {m["nome"]: m for m in r["municipios"]}
    assert por_nome["CAMPINAS"]["ibge"] == "3509502"
    assert (por_nome["CAMPINAS"]["pixEmpenhado"], por_nome["CAMPINAS"]["pixPago"], por_nome["CAMPINAS"]["pixN"]) == (100.0, 30.0, 1)
    assert "pixN" not in por_nome["SANTOS"]
    assert por_nome["SANTO ANTÔNIO DE LEVERGER"]["ibge"] == "5101605"
    assert "ibge" not in por_nome["OUTRA"]


def test_totais_somam_todos_os_anos_por_pessoa():
    t = ge.totais([item("1", 2023, "A", "SP", 100.5, 40.0), item("2", 2024, "B", "SP", 50.0, 10.0), {"pessoa": "pes_b", "codigo": "3", "ano": 2024, "empenhado": 7.0}])
    assert t == {"pes_a": {"n": 2, "empenhado": 150.5, "pago": 50.0}, "pes_b": {"n": 1, "empenhado": 7.0, "pago": 0.0}}


def test_municipio_sai_do_local_mesmo_em_arquivo_antigo_e_estado_inteiro_nao_vira_municipio():
    base = {"pessoa": "pes_a", "ano": 2024, "autor": "A", "tipo": "Individual", "empenhado": 10.0, "pago": 0.0}
    r = ge.construir([{**base, "codigo": "1", "local": "EMBU - SP"}, {**base, "codigo": "2", "local": "SÃO PAULO (UF)", "municipio": "SÃO PAULO", "uf": "UF"}],
                     {"3515004": ["SP", "EMBU DAS ARTES"]})["pes_a"]
    assert [(m["nome"], m["uf"], m.get("ibge")) for m in r["municipios"]] == [("EMBU", "SP", "3515004")]


PLANO = {"id": 38527, "codigo": "08.000001-X", "emenda": "202027070006", "ano": 2020, "situacao": "Concluído", "objeto": "Estradas vicinais",
         "custeio": 0.0, "investimento": 4350000.0, "beneficiario": 7052,
         "executores": [{"id": 1, "cnpj": "01613028000167", "nome": "MUNICIPIO DE IRACEMA", "objeto": "Estradas", "investimento": 4350000.0}]}


def test_plano_do_transferegov_liga_pelo_codigo_da_emenda_e_fica_uma_vez_na_pessoa():
    pix = {**item("202027070006", 2020, "IRACEMA", "RR", 10.0, 5.0), "tipo": "Emenda Individual - Transferências Especiais"}
    r = ge.construir([pix, item("999", 2020, "IRACEMA", "RR", 1.0, 0.0)], planos={"202027070006": [PLANO]})["pes_a"]
    assert [i.get("planos") for i in r["itens"]] == [[38527], None]
    assert list(r["planos"]) == ["38527"]
    plano = r["planos"]["38527"]
    assert plano["situacao"] == "Concluído" and plano["executores"][0]["cnpj"] == "01613028000167"
    assert "emenda" not in plano and "beneficiario" not in plano and "id" not in plano


def test_sem_plano_o_arquivo_da_pessoa_nao_ganha_campo():
    r = ge.construir([item("1", 2024, "SANTOS", "SP", 1.0, 1.0)], planos={"outra": [PLANO]})["pes_a"]
    assert "planos" not in r and "planos" not in r["itens"][0]


def test_carrega_planos_dos_arquivos_por_ano_e_confere_os_que_nao_casam(tmp_path):
    ge.comum.salvar(tmp_path / "especiais" / "2020.json", {"planos": [PLANO, {**PLANO, "id": 2, "emenda": "000000000000"}, {"id": 3, "codigo": "x"}]})
    planos = ge.carregar_planos(tmp_path)
    assert sorted(planos) == ["000000000000", "202027070006"]
    assert ge.carregar_planos(tmp_path / "nada") == {}
    pix = {**item("202027070006", 2020, "IRACEMA", "RR", 10.0, 5.0), "tipo": "Emenda Individual - Transferências Especiais"}
    pix2 = {**item("202027070007", 2020, "IRACEMA", "RR", 10.0, 5.0), "tipo": "Emenda Individual - Transferências Especiais"}
    assert ge.conferir_planos([pix, pix2], planos) == {"planos": 2, "semEmenda": 1, "emendasPix": 2, "pixSemPlano": 1, "planosDeOutroTipo": 0}


def test_plano_so_entra_em_emenda_pix_e_o_resto_e_contado():
    fin = {**item("202027070006", 2020, "IRACEMA", "RR", 10.0, 5.0), "tipo": "Emenda Individual - Transferências com Finalidade Definida"}
    planos = {"202027070006": [PLANO]}
    assert "planos" not in ge.construir([fin], planos=planos)["pes_a"]
    assert ge.conferir_planos([fin], planos)["planosDeOutroTipo"] == 1
