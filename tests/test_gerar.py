import json

import gerar


def test_tipo_voto():
    assert gerar.tipo_voto("Sim") == "sim"
    assert gerar.tipo_voto("Não") == "nao"
    assert gerar.tipo_voto("Artigo 17") == "art17"
    assert gerar.tipo_voto("Qualquer") == "outro"
    assert gerar.tipo_voto(None) == "outro"


def test_juntar_detalhe_sem_detalhe_devolve_igual():
    p = {"id": 1}
    assert gerar.juntar_detalhe(p, None) is p


def test_juntar_detalhe_copia_campos_e_ignora_vazios():
    r = gerar.juntar_detalhe({"id": 1}, {"situacao": "Arquivada", "dataApresentacao": "2024-01-01", "orgao": "", "regime": None, "tramitacao": [1],
                                                "inteiroTeor": "http://pdf"})
    assert r == {"id": 1, "situacao": "Arquivada", "dataApresentacao": "2024-01-01", "tramitacao": [1], "linkTexto": "http://pdf"}


def test_resumir_despesas():
    itens = [
        {"tipo": "Passagens", "mes": 1, "fornecedor": "A", "valor": 100.25},
        {"tipo": "Passagens", "mes": 2, "fornecedor": "A", "valor": 50},
        {"tipo": None, "mes": 1, "fornecedor": None, "valor": 10},
    ]
    r = gerar.resumir_despesas(2024, itens)
    assert r["ano"] == 2024
    assert r["total"] == 160.25
    assert r["porCategoria"][0] == {"id": "locomocao", "categoria": "Passagens, locomoção, hospedagem e alimentação", "total": 150.25,
                                    "originais": [["Passagens", 150.25]]}
    assert {"id": "sem_detalhe", "categoria": "Reembolso ou verba sem detalhamento da fonte", "total": 10.0, "originais": [["Sem categoria", 10.0]]} in r["porCategoria"]
    assert r["porMes"] == [[1, 110.25], [2, 50.0]]
    assert r["fornecedores"][0][0] == "A"
    assert any(f[0] == "Não informado" for f in r["fornecedores"])
    assert r["recentes"] == itens


def test_resumir_despesas_limita_recentes_e_fornecedores():
    itens = [{"tipo": "T", "mes": 1, "fornecedor": f"F{i}", "valor": 1} for i in range(40)]
    r = gerar.resumir_despesas(2024, itens)
    assert len(r["recentes"]) == 30
    assert len(r["fornecedores"]) == 10


def test_salvar_e_ler(tmp_path):
    destino = tmp_path / "x" / "y.json"
    gerar.salvar(destino, {"a": "ç"})
    assert gerar.ler(destino) == {"a": "ç"}
    assert json.loads(destino.read_text(encoding="utf-8")) == {"a": "ç"}
    assert gerar.ler(tmp_path / "nada.json", 5) == 5


def test_gerar_senadores_cria_detalhe_de_cada_votacao(tmp_path, monkeypatch):
    bruto, saida = tmp_path / "dados", tmp_path / "site"
    gerar.salvar(bruto / "senado.json", [{"id": "1", "nome": "Ana", "partido": "AAA", "uf": "SP"}])
    gerar.salvar(bruto / "senado_votacoes" / "2026.json", {"9": {
        "id": "9", "data": "2026-02-24", "descricao": "Votação X", "aprovada": 1,
        "votos": [["1", "sim", "Sim|"], ["2", "ausente", "AP|Atividade parlamentar"], ["3", "nao", "Não|"]]}})
    monkeypatch.setattr(gerar, "BRUTO", bruto)
    monkeypatch.setattr(gerar, "SAIDA", saida)
    gerar.gerar_senadores()
    d = json.loads((saida / "votacao_senado" / "9.json").read_text())
    assert d["placar"] == {"sim": 1, "nao": 1} and d["ausentes"] == 1
    assert d["porPartido"] == {"AAA": {"sim": 1}, "?": {"ausente": 1, "nao": 1}}
    por_id = {x["id"]: x for x in d["votos"]}
    assert por_id["1"]["nome"] == "Ana" and por_id["1"]["uf"] == "SP" and "anterior" not in por_id["1"]
    assert por_id["2"]["motivo"] == "Atividade parlamentar" and por_id["2"]["anterior"] is True
    assert por_id["3"]["nome"] == "Senador 3"


def test_juntar_autoria_principal_coautores_partido_e_contagens():
    import gerar
    aut = {"idPrincipal": 10, "autores": [[10, "Ana"], [20, "Bia"], [None, "Comissão X", "Comissão"]]}
    partidos = {"10": "PT", "20": "PL"}
    assert gerar.juntar_autoria({"id": 1}, aut, "10", partidos) == {
        "id": 1, "principal": True, "coautores": ["Bia (PL)", "Comissão X"], "totalAutores": 3, "partidosDistintos": 2}
    r = gerar.juntar_autoria({"id": 1}, aut, "20", partidos)
    assert r["principal"] is False and r["coautores"] == ["Ana (PT)", "Comissão X"]
    assert gerar.juntar_autoria({"id": 1}, aut, "10") == {"id": 1, "principal": True, "coautores": ["Bia", "Comissão X"], "totalAutores": 3}  # sem partidos conhecidos
    assert gerar.juntar_autoria({"id": 1}, None, "10", partidos) == {"id": 1}  # ainda não coletada


def test_juntar_autoria_usa_partido_da_data_de_apresentacao():
    import gerar
    aut = {"idPrincipal": 10, "autores": [[10, "Ana"], [20, "Bia"]]}
    historicos = {"20": [{"data": "2023-02-01", "partido": "PL"}, {"data": "2024-06-01", "partido": "PP"}, {"data": "2025-01-01", "partido": None}]}
    partidos = {"10": "PT", "20": "PP"}
    antes = gerar.juntar_autoria({"id": 1, "dataApresentacao": "2024-03-10T09:00"}, aut, "10", partidos, historicos)
    assert antes["coautores"] == ["Bia (PL)"] and antes["partidosDistintos"] == 2
    depois = gerar.juntar_autoria({"id": 1, "dataApresentacao": "2025-03-10"}, aut, "10", partidos, historicos)
    assert depois["coautores"] == ["Bia (PP)"]
    sem_data = gerar.juntar_autoria({"id": 1}, aut, "10", partidos, historicos)
    assert sem_data["coautores"] == ["Bia (PP)"]
    anterior = gerar.juntar_autoria({"id": 1, "dataApresentacao": "2022-01-01"}, aut, "10", partidos, historicos)
    assert anterior["coautores"] == ["Bia (PP)"]


def test_juntar_autoria_iniciativa_nao_deputado():
    import gerar
    aut = {"idPrincipal": None, "autores": [[None, "Poder Executivo", "Órgão do Poder Executivo"], [20, "Bia"]]}
    r = gerar.juntar_autoria({}, aut, "20", {"20": "PL"})
    assert r["iniciativa"] == "Órgão do Poder Executivo" and r["principal"] is False and r["totalAutores"] == 2 and "partidosDistintos" not in r


def test_juntar_autoria_limita_coautores():
    import gerar
    aut = {"idPrincipal": 1, "autores": [[1, "A"]] + [[100 + i, f"N{i}"] for i in range(20)]}
    co = gerar.juntar_autoria({}, aut, "1")["coautores"]
    assert len(co) == 16 and co[-1] == "e mais 5"


def test_destino_projeto_segue_o_desfecho_do_site():
    import gerar
    casos = {"Transformado em Norma Jurídica": "aprovada", "Aprovada pela CCJC": "aprovada", "Arquivada": "rejeitada",
             "Rejeitada": "rejeitada", "Tramitação encerrada": "sem", None: "sem", "Aguardando Parecer": "tramitando",
             "Aguardando Sanção": "aprovada", "Retirado pelo Autor": "rejeitada"}
    for situacao, esperado in casos.items():
        assert gerar.destino_projeto(situacao) == esperado, situacao


def test_resumir_autoria_conta_so_projetos():
    import gerar
    props = [
        {"tipo": "PL", "principal": True, "situacao": "Transformado em Norma Jurídica", "partidosDistintos": 3},
        {"tipo": "PL", "principal": True, "situacao": "Arquivada"},
        {"tipo": "PEC", "principal": False, "partidosDistintos": 2},
        {"tipo": "PL"},
        {"tipo": "REQ", "principal": True},
    ]
    assert gerar.resumir_autoria(props) == {"projetos": 4, "autoriaColetada": 3, "proprias": 2, "aprovadasProprias": 1, "suprapartidarios": 2}


def test_limite_cota_e_maiores_notas():
    import gerar
    itens = [{"mes": 1, "valor": 10, "documento": "a"}, {"mes": 3, "valor": 50, "documento": "b", "fornecedor": "X"}, {"mes": 2, "valor": 99, "documento": None}]
    assert gerar.limite_cota("SP", itens) == {"mensal": gerar.LIMITE_COTA_UF["SP"], "meses": 3}
    assert gerar.limite_cota("SP", []) is None
    assert [n["documento"] for n in gerar.maiores_notas(itens)] == ["b", "a"]
    assert len(gerar.LIMITE_COTA_UF) == 27


def test_presenca_do_senador():
    import gerar
    from collections import Counter
    assert gerar.categoria_presenca("sim", "S|Sim") == "compareceu"
    assert gerar.categoria_presenca("ausente", "P-NRV|Presente (não registrou voto)") == "compareceu"
    assert gerar.categoria_presenca("ausente", "NCOM|Não compareceu") == "naoCompareceu"
    assert gerar.categoria_presenca("ausente", "LS|Licença saúde") == "licenca"
    assert gerar.categoria_presenca("ausente", "MIS|Missão") == "missao"
    assert gerar.categoria_presenca("ausente", "NA|Dispositivo não citado") == "ignorar"
    c = Counter(compareceu=8, naoCompareceu=1, licenca=1, ignorar=5)
    assert gerar.resumir_presenca(c) == {"votacoes": 10, "compareceu": 8, "naoCompareceu": 1, "licenca": 1}


def test_resumir_temas_conta_por_tema_com_aprovados_e_autoria():
    ps = [
        {"temas": ["Saúde", "Educação"], "situacao": "Transformado em Norma Jurídica", "principal": True},
        {"temas": ["Saúde"], "situacao": "Aguardando Designação", "principal": False},
        {"situacao": "Arquivada"},
    ]
    assert gerar.resumir_temas(ps) == [["Saúde", 2, 1, 1], ["Educação", 1, 1, 1]]


def test_ordenar_orgaos_atuais_primeiro_e_mais_recentes_antes():
    orgaos = [{"sigla": "A", "inicio": "2023-02-01", "fim": "2024-01-01"}, {"sigla": "B", "inicio": "2023-03-01", "fim": None},
              {"sigla": "C", "inicio": "2025-03-01", "fim": None}]
    assert [o["sigla"] for o in gerar.ordenar_orgaos(orgaos)] == ["C", "B", "A"]


def test_bancada_do_partido_acha_sigla_ou_federacao():
    assert gerar.bancada_do_partido("pl", ["Governo", "PL"]) == "PL"
    assert gerar.bancada_do_partido("PCdoB", ["Fdr PT-PCdoB-PV"]) == "Fdr PT-PCdoB-PV"
    assert gerar.bancada_do_partido("MDB", ["Bl UniPpPsd...", "PL"]) is None


def test_resumir_comportamento_conta_partido_governo_e_divergencias():
    votos = [
        {"id": "a", "data": "2026-01-01", "descricao": "d", "proposicao": "PL 1/2026", "voto": "sim"},
        {"id": "b", "data": "2026-01-02", "descricao": "d", "proposicao": "PL 2/2026", "voto": "nao"},
        {"id": "c", "data": "2026-01-03", "descricao": "d", "voto": "ausente"},
        {"id": "d", "data": "2026-01-04", "descricao": "d", "voto": "sim"},
    ]
    orient = {"a": {"PL": "Sim", "Governo": "Não"}, "b": {"PL": "Não", "Governo": "Liberado"},
              "c": {"PL": "Sim"}, "d": {"PL": "Liberado"}}
    r = gerar.resumir_comportamento(votos, orient, "PL")
    assert r["partido"] == {"total": 2, "seguiu": 2} and r["governo"] == {"total": 1, "seguiu": 0}
    assert [(x["id"], x["contra"], x["orientacao"]) for x in r["divergencias"]] == [("a", "governo", "Não")]
    assert gerar.resumir_comportamento(votos, {}, "PL") is None


BLOCOS = [{"nome": "AVANTE, SOLIDARIEDADE, PRD", "federacao": False, "partidos": []},
          {"nome": "UNIÃO", "federacao": False, "partidos": []},
          {"nome": "UNIÃO, PP, PSD", "federacao": False, "partidos": ["UNIÃO", "PP", "PSD"]},
          {"nome": "Federação PSOL REDE", "federacao": True, "partidos": ["PSOL", "REDE"]}]


def test_partidos_do_bloco_liga_o_nome_truncado_ao_bloco():
    assert gerar.partidos_do_bloco("Bl UniPpPsd...", BLOCOS) == {"UNIÃO", "PP", "PSD"}
    assert gerar.partidos_do_bloco("Bl AvanSolidPrd...", BLOCOS) == {"AVANTE", "SOLIDARIEDADE", "PRD"}
    assert gerar.partidos_do_bloco("Bl Uni...", BLOCOS) == set()
    assert gerar.partidos_do_bloco("Bl PlFdrPtUniPp...", BLOCOS) == set()


def test_bancada_do_partido_acha_bloco_e_federacao_truncada():
    blocos = {"Bl UniPpPsd...": {"UNIÃO", "PP", "PSD"}}
    assert gerar.bancada_do_partido("pp", ["Bl UniPpPsd...", "PL"], blocos) == "Bl UniPpPsd..."
    assert gerar.bancada_do_partido("MDB", ["Bl UniPpPsd..."], blocos) is None
    assert gerar.bancada_do_partido("CIDADANIA", ["Fdr PSDB-CIDADAN"]) == "Fdr PSDB-CIDADAN"
    assert gerar.bancada_do_partido("PT", ["Fdr PSDB-CIDADAN"]) is None


def test_resumir_comportamento_usa_a_orientacao_do_bloco():
    votos = [{"id": "a", "data": "2026-01-01", "descricao": "d", "voto": "sim"}]
    r = gerar.resumir_comportamento(votos, {"a": {"Bl UniPpPsd...": "Sim"}}, "PP", {"Bl UniPpPsd...": {"PP"}})
    assert r["partido"] == {"total": 1, "seguiu": 1}


def test_juntar_votacoes_traz_placar_e_orientacoes_so_das_nominais():
    p = {"id": 10}
    vots = [{"id": "1-1", "data": "2026-01-01", "descricao": "a"}, {"id": "2-2", "data": "2026-02-01", "descricao": "b"}]
    nominais = {"2-2": {"placar": {"sim": 3}, "aprovada": True}}
    r = gerar.juntar_votacoes(p, vots, nominais, {"2-2": {"PL": "Sim"}})
    assert [v["id"] for v in r["votacoes"]] == ["2-2", "1-1"] and r["totalVotacoes"] == 2
    assert r["votacoes"][0] == {"id": "2-2", "data": "2026-02-01", "descricao": "b", "nominal": True, "placar": {"sim": 3},
                                "aprovada": True, "orientacoes": {"PL": "Sim"}}
    assert "nominal" not in r["votacoes"][1]
    assert gerar.juntar_votacoes(p, None, nominais, {}) == p


def test_presenca_do_deputado_por_ano_com_mediana():
    presenca = {"2025": {"sessoesDeliberativas": 10, "deputados": {"1": {"sessoes": 8, "comissoes": 2, "outros": 0}, "2": {"sessoes": 4, "comissoes": 0, "outros": 1}, "3": {"sessoes": 6, "comissoes": 0, "outros": 0}}},
                "2026": {"sessoesDeliberativas": 5, "deputados": {"2": {"sessoes": 5, "comissoes": 1, "outros": 0}}}}
    medianas = gerar.medianas_sessoes(presenca)
    assert medianas == {"2025": 6, "2026": 5}
    assert gerar.presenca_do_deputado("1", presenca, medianas) == [
        {"ano": 2025, "sessoes": 8, "comissoes": 2, "outros": 0, "sessoesDeliberativas": 10, "medianaSessoes": 6}]
