import json

import candidaturas as C
import identidades
import ids


def gravar(caminho, obj):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def eleito(seq, nome, cargo, uf, partido, ue=None, votos=1000, **extra):
    return {"sequencial": seq, "nome": nome, "urna": nome, "cargo": cargo, "uf": uf, "nascimento": "1980-01-0" + seq[-1], "partido": partido,
            "federacao": None, "numero": "13", "resultado": "Eleito", "situacao": "eleito", "unidadeEleitoral": ue or uf, "totalBens": 5000.0,
            "votos": [{"turno": 1, "data": "2022-10-02", "votos": votos, "percentual": 12.5}], **extra}


def montar(bruto):
    gravar(bruto / "tse" / "2022" / "SP.json", [
        eleito("1", "Ana Gov", "GOVERNADOR", "SP", "PT", votos=2000, federacao="13-PT/65-PC do B/43-PV"),
        eleito("2", "Vice Ana", "VICE-GOVERNADOR", "SP", "PCdoB", sequencialChapa="1", titular="Ana"),
        eleito("3", "Dep Federal", "DEPUTADO FEDERAL", "SP", "PL", votos=500),
        eleito("4", "Sem Contas", "DEPUTADO ESTADUAL", "SP", "UNIÃO"),
    ])
    gravar(bruto / "tse" / "contas" / "2022" / "SP.json", {
        "1": {"receitas": 1000.0, "despesasContratadas": 900.0, "despesasPagas": 800.0,
              "origensReceita": [["Recursos de partido político", 700.0], ["Rótulo Novo Qualquer", 300.0]], "principaisDoadores": [], "doadoresOriginarios": [], "gastosPorCategoria": []},
        "3": {"receitas": 250.0, "despesasContratadas": 0, "despesasPagas": 0, "origensReceita": [["Recursos próprios", 250.0]]},
    })
    gravar(bruto / "tse" / "contas" / "2022" / "_coleta.json", {"ok": True})
    gravar(bruto / "tse" / "disputa" / "2022" / "SP.json", {
        "GOVERNADOR|SP": {"turnos": {"1": {"aptos": 10, "validos": 8}}, "vagas": 1},
        "VICE-GOVERNADOR|SP": {"turnos": {"1": {"aptos": 10, "validos": 8}}, "vagas": 1},
        "DEPUTADO FEDERAL|SP": {"turnos": {"1": {"aptos": 10}}, "vagas": 70}})
    gravar(bruto / "tse" / "partidos" / "2022" / "SP.json", {"DEPUTADO FEDERAL|SP": {"totalVotos": 900, "partidos": {
        "PL": [100, 400, ""], "PT": [10, 50, "PT/PC do B/PV"], "PC do B": [5, 1, "PT/PC do B/PV"]}}})
    gravar(bruto / "tse" / "coligacoes" / "2022" / "SP.json", {"DEPUTADO FEDERAL|SP": {
        "coligacoes": [["I", "", "PL", "Deferido"], ["F", "", "Federação BRASIL DA ESPERANÇA (13-PT / 65-PC do B / 43-PV)", "Deferido"]],
        "coligacaoDoPartido": {"PL": 0, "PT": 1, "PC do B": 1}}})


def rodar(tmp_path):
    montar(tmp_path)
    nucleo = identidades.construir({}, tmp_path)
    return C.construir(tmp_path, nucleo), nucleo


def cand(res, id_):
    return next(c for c in res["candidaturas"] if c["id"] == id_)


def test_candidatura_liga_pessoa_partido_federacao_e_resumo_da_campanha(tmp_path):
    res, n = rodar(tmp_path)
    c = cand(res, C.id_candidatura(2022, 1))
    assert c["pessoa"] == n["chaves"][("tse", 2022, "1")] and c["partido"] == "par_pt" and c["federacao"] == "fed_pcdob_pt_pv"
    assert c["cargo"] == "GOVERNADOR" and c["uf"] == "SP" and c["votos"] == 2000 and c["percentual"] == 12.5 and c["bens"] == 5000.0
    assert (c["receitas"], c["despesas"], c["custoVoto"]) == (1000.0, 800.0, 0.5)
    assert c["origens"] == {"partido": 700.0, "rotulo_novo_qualquer": 300.0}
    assert "local" not in c and "situacao" not in c and "disputa" not in c and "ano" not in c      # se deduzem
    assert cand(res, C.id_candidatura(2022, 4)).get("receitas") is None and res["resumo"]["semContas"] == 1


def test_vice_aponta_para_a_chapa_e_nao_repete_as_contas(tmp_path):
    res, _ = rodar(tmp_path)
    v = cand(res, C.id_candidatura(2022, 2))
    assert v["chapa"] == C.id_candidatura(2022, 1) and "receitas" not in v and v["partido"] == "par_pcdob"


def test_disputa_junta_comparecimento_votos_por_partido_e_coligacoes_uma_vez(tmp_path):
    res, _ = rodar(tmp_path)
    d = res["disputas"][2022]
    assert set(d) == {C.id_disputa(2022, "DEPUTADO FEDERAL", "SP"), C.id_disputa(2022, "GOVERNADOR", "SP")}       # o vice usa a disputa do titular
    assert d[C.id_disputa(2022, "GOVERNADOR", "SP")]["cargo"] == "GOVERNADOR" and d[C.id_disputa(2022, "GOVERNADOR", "SP")]["vagas"] == 1
    f = d[C.id_disputa(2022, "DEPUTADO FEDERAL", "SP")]
    assert f["vagas"] == 70 and f["totalVotosPartidos"] == 900
    assert f["partidos"] == {"par_pl": [100, 400], "par_pt": [10, 50, "fed_pcdob_pt_pv"], "par_pcdob": [5, 1, "fed_pcdob_pt_pv"]}
    assert f["coligacoes"][1] == {"tipo": "F", "nome": None, "composicao": "Federação BRASIL DA ESPERANÇA (13-PT / 65-PC do B / 43-PV)",
                                  "situacao": "Deferido", "comEleitos": ["par_pcdob", "par_pt"]}
    assert C.id_disputa(2022, "VICE-GOVERNADOR", "SP") == C.id_disputa(2022, "GOVERNADOR", "SP")
    assert C.id_disputa(2024, "DEPUTADO FEDERAL", "01538") == ids.gerar_id("dsp", "tse:2024", "deputado_federal|01538")
    assert C.id_candidatura(2022, 1) == ids.gerar_id("can", "tse:2022", "1") != C.id_candidatura(2024, 1)
    assert res["resumo"]["semDisputa"] == 1       # o deputado estadual não tem disputa coletada


def test_salvar_candidaturas_por_ano(tmp_path):
    res, _ = rodar(tmp_path)
    C.salvar_candidaturas(res, tmp_path / "saida")
    lido = json.loads((tmp_path / "saida" / "nucleo" / "candidaturas" / "2022.json").read_text(encoding="utf-8"))
    assert [c["id"] for c in lido] == sorted(C.id_candidatura(2022, n) for n in (1, 2, 3, 4))
    assert {(c["eleicao"], c["sequencial"]) for c in lido} == {(2022, str(n)) for n in (1, 2, 3, 4)}
    assert C.id_disputa(2022, "GOVERNADOR", "SP") in json.loads((tmp_path / "saida" / "nucleo" / "disputas" / "2022.json").read_text(encoding="utf-8"))
