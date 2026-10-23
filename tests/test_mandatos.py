import json

import identidades
import mandatos as M


def gravar(caminho, obj):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def eleito(seq, nome, cargo, uf, nasc, partido="PT", situacao="eleito", ue="71072", **extra):
    return {"sequencial": seq, "nome": nome, "urna": nome, "cargo": cargo, "uf": uf, "nascimento": nasc, "partido": partido,
            "genero": "FEMININO", "federacao": None, "situacao": situacao, "unidadeEleitoral": ue, **extra}


def montar(bruto):
    gravar(bruto / "tse" / "2022" / "SP.json", [
        eleito("1", "Ana Maria Souza", "DEPUTADO FEDERAL", "SP", "1980-01-02", "PSL"),
        eleito("2", "Carlos Lima", "DEPUTADO FEDERAL", "SP", "1970-05-05", "PL"),            # titular que saiu: o suplente assume
        eleito("3", "Dani Alves", "DEPUTADO ESTADUAL", "SP", "1990-01-01", "PT"),
        eleito("4", "Edu Rocha", "DEPUTADO ESTADUAL", "SP", "1985-01-01", "PT"),             # fora da lista da Assembleia
        eleito("5", "Tarcísio Gomes", "GOVERNADOR", "SP", "1975-01-01", "REPUBLICANOS", ue="SP"),
        eleito("6", "Vice Silva", "VICE-GOVERNADOR", "SP", "1976-01-01", "PL", ue="SP", titular="Tarcísio"),
        eleito("7", "Não Eleito", "DEPUTADO FEDERAL", "SP", "1960-01-01", situacao="nao_eleito"),
    ])
    gravar(bruto / "tse" / "2022" / "AP.json", [eleito("30", "Gil Amapá", "DEPUTADO ESTADUAL", "AP", "1966-06-06")])    # AP não tem lista coletada
    gravar(bruto / "tse" / "2018" / "RJ.json", [eleito("500", "Bia Lima", "SENADOR", "RJ", "1975-03-03", "UNIÃO")])
    gravar(bruto / "tse" / "2024" / "SP.json", [eleito("9", "Ver Eador", "VEREADOR", "SP", "1980-02-02", "PSD", ue="71072"),
                                                eleito("10", "Ver Eador", "VEREADOR", "SP", "1980-02-02", "PSD", ue="71072")])    # linha repetida
    gravar(bruto / "tse" / "2026" / "SP.json", [eleito("90", "Ana Maria Souza", "DEPUTADO FEDERAL", "SP", "1980-01-02", "PSL"),
                                                eleito("91", "Segundo Turno", "GOVERNADOR", "SP", "1950-01-01", situacao="2turno", ue="SP")])
    gravar(bruto / "senado.json", [
        {"id": "7", "nome": "Bia", "nomeCivil": "BIA LIMA", "partido": "UB", "uf": "RJ", "participacao": "Titular", "fimMandato": "2027-01-31"},
        {"id": "8", "nome": "Zé Novo", "nomeCivil": "José Novo", "partido": "PL", "uf": "AC", "participacao": "1º Suplente",
         "titular": "Fulano Titular", "exercicioDesde": "2025-04-01", "fimMandato": "2031-01-31"}])
    gravar(bruto / "estaduais" / "SP" / "deputados.json", {"deputados": [
        {"id": "a", "nome": "Dani Alves", "nomeCivil": "Dani Alves", "partido": "PL"},
        {"id": "c", "nome": "Suplente", "nomeCivil": "Fulano Suplente", "partido": "Novo", "titular": False}]})


CAMARA = {1: {"id": 1, "nome": "Ana", "nomeCivil": "ANA MARIA SOUZA", "nascimento": "1980-01-02", "partido": "UNIÃO", "uf": "SP", "condicaoEleitoral": "Titular"},
          2: {"id": 2, "nome": "Rita", "nomeCivil": "Rita Suplente", "nascimento": "1990-09-09", "partido": "PL", "uf": "SP", "condicaoEleitoral": "Suplente"}}


def rodar(tmp_path, deputados=None, hoje="2026-10-23"):
    montar(tmp_path)
    nucleo = identidades.construir(CAMARA if deputados is None else deputados, tmp_path)
    return M.construir(CAMARA if deputados is None else deputados, tmp_path, nucleo, hoje), nucleo


def do(res, nucleo, chave, cargo=None, **filtro):
    pessoa = nucleo["chaves"][chave]
    achados = [m for m in res["mandatos"] if m["pessoa"] == pessoa and (cargo is None or m["cargo"] == cargo)
               and all(m.get(k) == v for k, v in filtro.items())]
    assert len(achados) == 1, (chave, cargo, filtro, achados)
    return achados[0]


def test_eleito_em_exercicio_ganha_periodo_partido_e_fusao_nao_conta_como_troca(tmp_path):
    res, n = rodar(tmp_path)
    m = do(res, n, ("tse", 2022, "1"), eleicao=2022)
    assert (m["inicio"], m["fim"], m["status"], m["confirmado"]) == ("2023-02-01", "2027-01-31", "atual", True)
    assert m["partidoEleicao"] == "par_psl" and m["partido"] == "par_uniao" and "mudouPartido" not in m      # PSL -> UNIÃO é fusão
    assert m["fontes"] == {"tse": "1", "camara": 1} and "condicao" not in m
    futuro = do(res, n, ("tse", 2026, "90"), eleicao=2026)
    assert futuro["status"] == "futuro" and futuro["inicio"] == "2027-02-01" and futuro["eleicao"] == 2026


def test_troca_de_partido_e_ausente_da_lista_da_casa(tmp_path):
    res, n = rodar(tmp_path)
    dani = do(res, n, ("tse", 2022, "3"))
    assert dani["partidoEleicao"] == "par_pt" and dani["partido"] == "par_pl" and dani["mudouPartido"] is True
    carlos = do(res, n, ("tse", 2022, "2"))
    assert carlos["status"] == "fora_de_exercicio" and "confirmado" not in carlos     # a Câmara não o lista: assumiu o suplente
    assert do(res, n, ("tse", 2022, "4"))["status"] == "fora_de_exercicio"            # idem na Assembleia de SP
    assert do(res, n, ("tse", 2022, "30"))["status"] == "atual"                       # AP sem lista: segue no período


def test_suplente_sem_registro_no_tse_ganha_mandato_proprio(tmp_path):
    res, n = rodar(tmp_path)
    rita = do(res, n, ("camara", "2"))
    assert rita["condicao"] == "suplente" and rita["inicioAproximado"] is True and rita["eleicao"] is None
    assert rita["inicio"] == "2023-02-01" and rita["status"] == "atual" and "partidoEleicao" not in rita
    ze = do(res, n, ("senado", "8"))
    assert (ze["condicao"], ze["inicio"], ze["fim"], ze["titularDe"]) == ("suplente", "2025-04-01", "2031-01-31", "Fulano Titular")
    assert "inicioAproximado" not in ze
    assert do(res, n, ("estadual", "SP", "c"))["condicao"] == "suplente"
    bia = do(res, n, ("senado", "7"), eleicao=2018)
    assert bia["fim"] == "2027-01-31" and bia["partido"] == "par_uniao" and bia["confirmado"] is True


def test_executivo_municipal_vice_e_segundo_turno(tmp_path):
    res, n = rodar(tmp_path)
    assert do(res, n, ("tse", 2022, "6"))["titularDe"] == "Tarcísio"
    assert do(res, n, ("tse", 2022, "5"))["fim"] == "2027-01-05"
    v = do(res, n, ("tse", 2024, "9"))
    assert v["municipio"] == "71072" and v["inicio"] == "2025-01-01" and v["status"] == "atual"
    assert res["resumo"]["repetido"] == 1 and res["resumo"]["tseSemMandato"] == 2          # a repetição não duplica; 2º turno e não eleito não têm mandato
    assert not [m for m in res["mandatos"] if m["pessoa"] == n["chaves"][("tse", 2026, "91")]]


def test_status_encerrado_depois_do_fim_e_sem_listas_nada_fica_fora_de_exercicio(tmp_path):
    res, n = rodar(tmp_path, hoje="2027-06-01")
    assert do(res, n, ("tse", 2022, "5"))["status"] == "encerrado"
    assert do(res, n, ("tse", 2026, "90"), eleicao=2026)["status"] == "atual"
    res, n = rodar(tmp_path / "outro", deputados={})
    assert do(res, n, ("tse", 2022, "2"))["status"] == "atual"                            # sem lista da Câmara, não dá para saber


def test_ids_unicos_e_estaveis_e_salvar(tmp_path):
    res, n = rodar(tmp_path)
    ids = [m["id"] for m in res["mandatos"]]
    assert len(ids) == len(set(ids)) and all(i.startswith("man_") for i in ids)
    outra, _ = rodar(tmp_path)
    assert ids == [m["id"] for m in outra["mandatos"]]
    M.salvar_mandatos(res, tmp_path / "saida")
    assert json.loads((tmp_path / "saida" / "nucleo" / "mandatos.json").read_text(encoding="utf-8")) == res["mandatos"]


def test_vigente_segue_fusoes():
    assert M.vigente("par_prp") == "par_prd" and M.vigente("par_pt") == "par_pt" and M.vigente("par_desconhecido") == "par_desconhecido"
    assert M.vigente(None) is None
