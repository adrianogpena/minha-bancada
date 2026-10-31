import json

import gerar_estaduais as ge


def escrever(pasta, nome, obj):
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / nome).write_text(json.dumps(obj), encoding="utf-8")


def base(pasta, host="sapl.exemplo.leg.br", fonte_dep=None):
    dep = {"id": 1, "nome": "Ana", "nomeCivil": "Ana Silva", "foto": None, "email": None, "titular": True}
    if fonte_dep:
        dep["fonte"] = fonte_dep
    escrever(pasta, "deputados.json", {"host": host, "deputados": [dep]})
    escrever(pasta, "votacoes.json", {"votacoes": {}})
    escrever(pasta, "materias_2024.json", {"materias": {"9": {
        "idsDeputados": [1], "tipo": "PL", "tipoDescricao": "Projeto", "numero": 1, "ano": 2024,
        "dataApresentacao": "2024-02-01", "ementa": "x", "situacao": "Em tramitação"}}})


def preparar(tmp_path, monkeypatch):
    monkeypatch.setattr(ge, "BRUTO", tmp_path / "bruto")
    monkeypatch.setattr(ge, "SAIDA", tmp_path / "saida")
    return tmp_path / "bruto"


def test_uf_sapl_sem_arquivos_novos(tmp_path, monkeypatch):
    bruto = preparar(tmp_path, monkeypatch)
    pasta = bruto / "AC"
    base(pasta)
    ge.gerar_assembleia("AC", pasta)
    saida = json.loads((tmp_path / "saida" / "estadual" / "AC" / "1.json").read_text(encoding="utf-8"))
    assert set(saida) == {"id", "host", "foto", "email", "titular", "votos", "proposicoes"}
    assert saida["host"] == "sapl.exemplo.leg.br"
    assert "fonte" not in saida["proposicoes"][0]


def test_uf_com_todos_os_arquivos_novos(tmp_path, monkeypatch):
    bruto = preparar(tmp_path, monkeypatch)
    pasta = bruto / "GO"
    base(pasta, host=None, fonte_dep="https://dep/1")
    escrever(pasta, "verbas_2024.json", {"fonte": "https://verba", "itens": (
        [{"idDeputado": 1, "mes": 1, "categoria": "Combustível", "fornecedor": f"F{i}", "cnpj": f"{i}", "valor": 10 + i, "fonte": "u"} for i in range(12)]
        + [{"idDeputado": 1, "mes": 2, "categoria": "Aluguel", "fornecedor": "F0", "cnpj": "0", "valor": 5, "fonte": "u"}])})
    escrever(pasta, "verbas_2020.json", {"fonte": "https://verba", "itens": [{"idDeputado": 1, "mes": 1, "categoria": "Velho", "valor": 999}]})
    escrever(pasta, "remuneracao_2024.json", {"fonte": "https://rem", "itens": [
        {"idDeputado": 1, "mes": 1, "bruto": 100, "liquido": 80, "componentes": [], "fonte": "a"},
        {"idDeputado": 1, "mes": 3, "bruto": 120, "liquido": 90, "componentes": [], "fonte": "b"}]})
    escrever(pasta, "presenca.json", {"fonte": "https://pres", "itens": [
        {"idDeputado": 1, "periodo": "2024", "presente": 10, "ausente": 2, "licenca": 0, "totalSessoes": 12}]})
    escrever(pasta, "diarias_2024.json", {"fonte": "https://dia", "itens": [
        {"idDeputado": 1, "data": "2024-05-01", "valor": 100}, {"idDeputado": 1, "data": "2024-06-01", "valor": 50}]})
    escrever(pasta, "emendas_2024.json", {"fonte": "https://em", "itens": [
        {"idDeputado": 1, "ano": 2024, "empenhado": 1000, "pago": 400}, {"idDeputado": 1, "ano": 2024, "empenhado": 500, "pago": 100}]})
    ge.gerar_assembleia("GO", pasta)
    s = json.loads((tmp_path / "saida" / "estadual" / "GO" / "1.json").read_text(encoding="utf-8"))
    assert s["host"] is None and s["fonte"] == "https://dep/1"
    verba = s["verba"]
    assert verba["fonte"] == "https://verba"
    assert [a["ano"] for a in verba["anos"]] == [2024]
    a = verba["anos"][0]
    assert len(a["fornecedores"]) == 10 and a["fornecedores"][0]["fornecedor"] == "F11"
    assert a["categorias"][0]["id"] == "combustivel" and a["categorias"][0]["categoria"] == "Combustíveis e lubrificantes"
    assert a["categorias"][0]["originais"][0][0] == "Combustível" and a["categorias"][1]["id"] == "imovel"
    assert [m["mes"] for m in a["meses"]] == [1, 2]
    assert s["remuneracao"]["mes"] == 3 and s["remuneracao"]["bruto"] == 120
    assert s["presenca"]["periodos"][0]["presente"] == 10
    assert s["diarias"]["anos"] == [{"ano": 2024, "total": 150.0, "quantidade": 2}]
    assert s["emendas"]["anos"] == [{"ano": 2024, "empenhado": 1500.0, "pago": 500.0, "quantidade": 2}]


def test_emendas_trazem_pagamentos_ligados_pelo_numero(tmp_path, monkeypatch):
    bruto = preparar(tmp_path, monkeypatch)
    pasta = bruto / "BA"
    base(pasta, host=None)
    escrever(pasta, "emendas_2025.json", {"fonte": "https://em", "itens": [
        {"idDeputado": 1, "ano": 2025, "numero": "N1", "empenhado": 1000, "pago": 400}]})
    escrever(pasta, "pagamentos_2026.json", {"fonte": "https://em", "itens": [
        {"numero": "N1", "data": "2026-01-20", "credor": "A", "objeto": "o1", "valor": 10.5, "empenho": "E1", "efetivado": False},
        {"numero": "N1", "data": "2026-02-23", "credor": "B", "objeto": "o2", "valor": 20, "empenho": "E1", "efetivado": True},
        {"numero": "N9", "data": "2026-03-01", "credor": "C", "objeto": "o3", "valor": 1, "empenho": "E2", "efetivado": True}]})
    ge.gerar_assembleia("BA", pasta)
    s = json.loads((tmp_path / "saida" / "estadual" / "BA" / "1.json").read_text(encoding="utf-8"))
    assert [p["credor"] for p in s["emendas"]["pagamentos"]] == ["B", "A"]
    assert s["emendas"]["pagamentos"][0] == {"data": "2026-02-23", "credor": "B", "objeto": "o2", "valor": 20, "empenho": "E1", "efetivado": True}


def test_verba_de_ce_e_ms_traz_lancamentos_so_do_ano_atual(tmp_path, monkeypatch):
    bruto = preparar(tmp_path, monkeypatch)
    item = {"idDeputado": 1, "mes": 2, "categoria": "Combustível", "fornecedor": "F", "cnpj": "1", "valor": 10, "documento": "NF-1",
            "emissao": "2026-02-03", "fonte": "https://comprovante"}
    for uf in ("MS", "GO"):
        pasta = bruto / uf
        base(pasta, host=None)
        escrever(pasta, "verbas_2026.json", {"fonte": "https://verba", "itens": [item, {**item, "mes": 3, "documento": None, "emissao": None, "empenho": "2026NE1", "descricao": "d"}]})
        escrever(pasta, "verbas_2025.json", {"fonte": "https://verba", "itens": [item]})
        ge.gerar_assembleia(uf, pasta)
    ms = json.loads((tmp_path / "saida" / "estadual" / "MS" / "1.json").read_text(encoding="utf-8"))["verba"]["anos"]
    assert "lancamentos" not in ms[0] and len(ms[1]["lancamentos"]) == 2
    assert ms[1]["lancamentos"][0]["documento"] == "NF-1" and ms[1]["lancamentos"][0]["emissao"] == "2026-02-03"
    assert ms[1]["lancamentos"][1] == {"mes": 3, "categoria": "Combustível", "fornecedor": "F", "cnpj": "1", "valor": 10, "empenho": "2026NE1", "descricao": "d", "fonte": "https://comprovante"}
    go = json.loads((tmp_path / "saida" / "estadual" / "GO" / "1.json").read_text(encoding="utf-8"))["verba"]["anos"]
    assert all("lancamentos" not in a for a in go)


def test_total_de_autores_conta_quem_nao_e_deputado(tmp_path, monkeypatch):
    bruto = preparar(tmp_path, monkeypatch)
    pasta = bruto / "AC"
    escrever(pasta, "deputados.json", {"host": "h", "deputados": [
        {"id": 1, "nome": "Ana", "titular": True}, {"id": 2, "nome": "Bia", "titular": True}]})
    escrever(pasta, "votacoes.json", {"votacoes": {}})
    escrever(pasta, "materias_2024.json", {"materias": {"9": {
        "idsDeputados": [1, 2], "idsAutores": [5, 6, 7], "tipo": "PL", "tipoDescricao": "Projeto", "numero": 1, "ano": 2024,
        "dataApresentacao": "2024-02-01", "ementa": "x", "situacao": "Em tramitação"}}})
    ge.gerar_assembleia("AC", pasta)
    p = json.loads((tmp_path / "saida" / "estadual" / "AC" / "1.json").read_text(encoding="utf-8"))["proposicoes"][0]
    assert p["coautores"] == ["Bia"] and p["totalAutores"] == 3


def test_normas_na_ficha_do_deputado(tmp_path, monkeypatch):
    bruto = preparar(tmp_path, monkeypatch)
    pasta = bruto / "AC"
    base(pasta)
    escrever(pasta, "normas_2026.json", {"normas": {
        "10": {"tipo": "Lei Ordinária", "numero": 5, "ano": 2026, "data": "2026-03-01", "ementa": "A", "situacao": "Publicada", "idsDeputados": [1], "fonte": "https://n/10"},
        "11": {"tipo": "Resolução", "numero": 2, "ano": 2026, "data": "2026-05-01", "ementa": "B", "situacao": None, "idsDeputados": [1], "fonte": "https://n/11"}}})
    ge.gerar_assembleia("AC", pasta)
    saida = json.loads((tmp_path / "saida" / "estadual" / "AC" / "1.json").read_text(encoding="utf-8"))
    assert [n["id"] for n in saida["normas"]] == ["11", "10"]
    assert saida["normas"][0]["fonte"] == "https://n/11"


def test_votacao_recebe_pauta_e_ata_do_dia(tmp_path, monkeypatch):
    bruto = preparar(tmp_path, monkeypatch)
    pasta = bruto / "AC"
    base(pasta)
    escrever(pasta, "votacoes.json", {"votacoes": {"v1": {
        "idMateria": 1, "data": "2026-10-21", "votos": [], "sim": 1, "nao": 0, "abstencoes": 0, "aprovada": True}}})
    escrever(pasta, "pautas_2026.json", {"itens": {
        "a": {"tipo": "atas", "data": "2026-10-21", "arquivos": [{"nome": "Ata 88", "url": "https://x/ata.pdf"}]},
        "b": {"tipo": "ccj", "data": "2026-10-21", "arquivos": [{"nome": "CCJ", "url": "https://x/ccj.pdf"}]},
        "c": {"tipo": "ordem-do-dia", "data": "2026-10-22", "arquivos": [{"nome": "Outra", "url": "https://x/o.pdf"}]}}})
    ge.gerar_assembleia("AC", pasta)
    v = json.loads((tmp_path / "saida" / "votacoes_estadual_AC.json").read_text(encoding="utf-8"))[0]
    assert v["documentos"] == [["Ata da sessão: Ata 88", "https://x/ata.pdf"]]


def test_gabinete_na_ficha_do_deputado(tmp_path, monkeypatch):
    bruto = preparar(tmp_path, monkeypatch)
    pasta = bruto / "AC"
    base(pasta)
    escrever(pasta, "gabinete.json", {"coletadoEm": "2026-10-31", "fonte": "https://g/pessoal", "itens": [
        {"idDeputado": 1, "matricula": "2", "nome": "B", "simbolo": "G-7"},
        {"idDeputado": 1, "matricula": "1", "nome": "A", "simbolo": "G-7"},
        {"idDeputado": 1, "matricula": "3", "nome": "C", "simbolo": "G-3"}]})
    ge.gerar_assembleia("AC", pasta)
    g = json.loads((tmp_path / "saida" / "estadual" / "AC" / "1.json").read_text(encoding="utf-8"))["gabinete"]
    assert g["total"] == 3 and g["coletadoEm"] == "2026-10-31" and g["fonte"] == "https://g/pessoal"
    assert g["simbolos"] == [{"simbolo": "G-3", "quantidade": 1}, {"simbolo": "G-7", "quantidade": 2}]
    assert [s["nome"] for s in g["servidores"]] == ["C", "A", "B"] and "matricula" not in g["servidores"][0]


def test_orgao_agrupa_fornecedor_e_separa_valor_registrado(tmp_path, monkeypatch):
    bruto = preparar(tmp_path, monkeypatch)
    pasta = bruto / "PR"
    base(pasta)
    escrever(tmp_path / "saida" / "nucleo", "fornecedores.json", [{"id": "for_23324543"}])

    def item(tipo, nome, cnpj, valor, inicio):
        return {"tipo": tipo, "fornecedor": nome, "nomeChave": nome, "cnpj": cnpj, "valor": valor, "inicio": inicio, "arquivos": []}

    escrever(pasta, "orgao_2026.json", {"itens": {
        "ctr_a": item("contrato", "CS", "23324543000160", 100.0, "2026-01-01"),
        "ctr_b": item("ata_adesao", "CS", "23324543000160", 50.0, "2026-02-01"),
        "ctr_c": item("ata_registro", "CS", "23324543000160", 900.0, "2026-03-01"),
        "ctr_d": item("contrato", "SEM CNPJ", None, 10.0, "2026-04-01")}})
    escrever(pasta, "regras_ressarcimento.json", {"url": "https://r.pdf", "ano": 2025})
    ge.gerar_assembleia("PR", pasta)
    o = json.loads((tmp_path / "saida" / "orgao" / "PR.json").read_text(encoding="utf-8"))
    cs, sem = o["fornecedores"]
    assert cs["contratos"] == 2 and cs["valorContratado"] == 150.0 and cs["atas"] == 1 and cs["valorRegistrado"] == 900.0 and cs["idFornecedor"] == "for_23324543"
    assert sem["nome"] == "SEM CNPJ" and "idFornecedor" not in sem
    assert [i["id"] for i in o["itens"]] == ["ctr_d", "ctr_c", "ctr_b", "ctr_a"] and o["regrasRessarcimento"]["ano"] == 2025
