import json

import identidades as ident


def gravar(caminho, obj):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def eleito(seq, nome, urna, cargo, uf, nasc, partido="PT", **extra):
    return {"sequencial": seq, "nome": nome, "urna": urna, "cargo": cargo, "uf": uf, "nascimento": nasc,
            "partido": partido, "genero": "FEMININO", "federacao": None, **extra}


def test_candidato_do_tse_sem_nascimento_ganha_id_de_ano_e_sequencial(tmp_path):
    gravar(tmp_path / "tse" / "2022" / "SP.json", [
        eleito("77", "Sem Data", "Sem", "VEREADOR", "SP", None),
        eleito("78", None, "Sem Nome", "VEREADOR", "SP", "1980-01-01")])
    n = ident.construir({}, tmp_path)
    esperado = ident._Registro().obter("tse", "2022|77")["id"]
    assert n["chaves"][("tse", 2022, "77")] == esperado
    p = next(p for p in n["pessoas"] if p["id"] == esperado)
    assert p["nome"] == "Sem Data" and "nascimento" not in p and p["fontes"]["tse"] == [[2022, "77", "VEREADOR", "par_pt"]]
    assert n["chaves"][("tse", 2022, "78")] != esperado
    assert ident.construir({}, tmp_path)["chaves"][("tse", 2022, "77")] == esperado


def test_partido_desconhecido_vira_linha_sem_cadastro_e_e_listado(tmp_path):
    gravar(tmp_path / "tse" / "2022" / "SP.json", [eleito("1", "Ana Souza", "Ana", "VEREADOR", "SP", "1980-01-01", "XYZ Novo")])
    n = ident.construir({}, tmp_path)
    linha = next(x for x in n["partidos"]["partidos"] if x["id"] == "par_xyznovo")
    assert linha == {"id": "par_xyznovo", "sigla": "XYZNOVO", "conhecido": False}
    assert n["ligacoes"]["partidosDesconhecidos"] == ["XYZ Novo"]
    assert n["pessoas"][0]["partido"] == "par_xyznovo"


def test_construir_liga_ministros_e_tribunais_e_deixa_vazio_sem_arquivos(tmp_path):
    gravar(tmp_path / "tse" / "2022" / "SP.json", [eleito("1", "Ana Maria Souza", "Ana", "DEPUTADO FEDERAL", "SP", "1980-01-02")])
    gravar(tmp_path / "senado.json", [{"id": "7", "nome": "Bia", "nomeCivil": "Bia Lima", "partido": "PL", "uf": "RJ"}])
    gravar(tmp_path / "ministros" / "planalto.json", {
        "atuais": [{"cargo": "Ministro da Saúde", "nome": "Ana Maria Souza", "vistoDesde": "2026-01-01"},
                   {"cargo": "Ministro da Pesca", "nome": "Desconhecido Total", "vistoDesde": "2026-02-02"}],
        "anteriores": []})
    gravar(tmp_path / "tribunais" / "tribunais.json", {"tribunais": {"TCU": {"atuais": [{"nome": "Bia Lima", "wiki": "Bia_Lima"}]}}})
    n = ident.construir({}, tmp_path)
    ana = next(p for p in n["pessoas"] if p["nome"] == "Ana Maria Souza")
    bia = next(p for p in n["pessoas"] if p["nome"] == "Bia Lima")
    assert [(m["pasta"], m["nome"], m["pessoa"], m["inicio"], m["inicioFonte"]) for m in n["ministros"]][0] == \
        (ident.ministerios.pasta_do_cargo("Ministro da Saúde"), "Ana Maria Souza", ana["id"], "2026-01-01", "planalto")
    assert len(n["ministros"]) == 2 and ana["ligacao"]["planalto"] == ["nome", "média"] and ana["fontes"]["planalto"]
    assert n["chaves"][("planalto", n["ministros"][0]["pasta"], "ana maria souza")] == ana["id"]
    assert n["ligacoes"]["semLigacao"]["planalto"] == 1
    assert n["tribunais"] == {ident.id_ministro_tribunal("TCU", {"nome": "Bia Lima", "wiki": "Bia_Lima"}): bia["id"]}
    assert bia["ligacao"]["tribunal"] == ["nome", "média"]

    vazio = ident.construir({}, tmp_path / "vazio")
    assert vazio["ministros"] == [] and vazio["tribunais"] == {} and vazio["aposentados"] == []
    assert vazio["inabilitados"] == [] and vazio["emendas"] == [] and vazio["pessoas"] == []
    assert vazio["ligacoes"]["ambiguos"] == [] and vazio["ligacoes"]["registros"] == {} and vazio["partidos"]["federacoes"] == []
