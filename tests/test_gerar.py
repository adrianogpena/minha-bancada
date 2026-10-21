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
    assert r["porTipo"][0][0] == "Passagens"
    assert ["Outros", 10] in [[k, v] for k, v in r["porTipo"]]
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
