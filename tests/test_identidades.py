import json

import identidades as ident


def gravar(caminho, obj):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def eleito(seq, nome, urna, cargo, uf, nasc, partido="PT", **extra):
    return {"sequencial": seq, "nome": nome, "urna": urna, "cargo": cargo, "uf": uf, "nascimento": nasc,
            "partido": partido, "genero": "FEMININO", "federacao": None, **extra}


def montar(bruto):
    gravar(bruto / "tse" / "2022" / "SP.json", [
        eleito("1", "Ana Maria Souza", "Ana Souza", "DEPUTADO FEDERAL", "SP", "1980-01-02"),
        eleito("2", "Carlos Lima", "Carlão", "DEPUTADO ESTADUAL", "SP", "1970-05-05", "PSL"),
        eleito("3", "João Silva", "João", "DEPUTADO ESTADUAL", "SP", "1960-01-01", federacao="13-PT/65-PC do B/43-PV"),
        eleito("4", "João Silva", "João", "DEPUTADO ESTADUAL", "SP", "1961-02-02"),
    ])
    gravar(bruto / "tse" / "2024" / "SP.json", [
        eleito("9", "ANA MARIA SOUZA", "Ana Vereadora", "VEREADOR", "SP", "1980-01-02", "PC do B"),
    ])
    gravar(bruto / "tse" / "2022" / "RJ.json", [
        eleito("500", "Bia Lima", "Bia", "SENADOR", "RJ", "1975-03-03", "União Brasil"),
        eleito("501", "Dani Alves", "Dani", "DEPUTADO ESTADUAL", "RJ", "1990-01-01"),
    ])
    gravar(bruto / "senado.json", [
        {"id": "7", "nome": "Bia", "nomeCivil": "BIA LIMA", "partido": "UB", "uf": "RJ", "genero": "Feminino"},
        {"id": "8", "nome": "Zé Novo", "nomeCivil": "José Novo", "partido": "PL", "uf": "AC"}])
    gravar(bruto / "estaduais" / "SP" / "deputados.json", {"deputados": [
        {"id": "a", "nome": "Carlão", "nomeCivil": "Carlos Lima (Carlão)", "partido": "PL"},
        {"id": "b", "nome": "João", "nomeCivil": "João Silva", "partido": "PT"},
        {"id": "c", "nome": "Suplente", "nomeCivil": "Fulano Suplente", "partido": "Novo"}]})
    gravar(bruto / "estaduais" / "RJ" / "deputados.json", {"deputados": [{"id": "501", "nome": "Outro Nome"}]})


def pessoa(n, pid):
    return next(p for p in n["pessoas"] if p["id"] == pid)


def test_mesma_pessoa_em_varias_eleicoes_e_na_camara(tmp_path):
    montar(tmp_path)
    camara = {101: {"id": 101, "nome": "Ana Souza", "nomeCivil": "ANA MARIA SOUZA", "nascimento": "1980-01-02", "partido": "PT", "uf": "SP"}}
    n = ident.construir(camara, tmp_path)
    pid = n["chaves"][("camara", "101")]
    assert pid == n["chaves"][("tse", 2022, "1")] == n["chaves"][("tse", 2024, "9")]
    p = pessoa(n, pid)
    assert p["fontes"]["camara"] == 101 and [t[0] for t in p["fontes"]["tse"]] == [2022, 2024]
    assert p["ligacao"]["camara"] == ["nome+nascimento", "alta"]
    assert p["partido"] == "par_pt"          # a fonte atual (Câmara) vale mais que a última eleição (PCdoB em 2024)
    assert "Ana Vereadora" in p["nomes"] and "Ana Souza" in p["nomes"]


def test_id_nao_depende_da_ordem_nem_da_ligacao_com_a_camara(tmp_path):
    montar(tmp_path)
    sem = ident.construir({}, tmp_path)
    com = ident.construir({1: {"id": 1, "nome": "X", "nomeCivil": "Ana Maria Souza", "nascimento": "1980-01-02", "partido": "PT", "uf": "SP"}}, tmp_path)
    assert sem["chaves"][("tse", 2022, "1")] == com["chaves"][("tse", 2022, "1")]
    assert len({p["id"] for p in com["pessoas"]}) == len(com["pessoas"])


def test_camara_sem_tse_ganha_o_id_de_nome_e_nascimento(tmp_path):
    montar(tmp_path)
    n = ident.construir({5: {"id": 5, "nome": "Suplente", "nomeCivil": "Rita Suplente", "nascimento": "1990-09-09", "partido": "PL", "uf": "SP"}}, tmp_path)
    assert pessoa(n, n["chaves"][("camara", "5")])["fontes"] == {"camara": 5}
    assert n["ligacoes"]["semLigacao"]["camara"] == 1


def test_senado_liga_pelo_nome_civil_e_estadual_pelo_cargo_ou_sequencial(tmp_path):
    montar(tmp_path)
    n = ident.construir({}, tmp_path)
    s = pessoa(n, n["chaves"][("senado", "7")])
    assert s["id"] == n["chaves"][("tse", 2022, "500")] and s["ligacao"]["senado"] == ["nome+cargo+uf", "média"]
    assert s["genero"] == "FEMININO" and s["partido"] == "par_uniao"
    assert n["chaves"][("estadual", "SP", "a")] == n["chaves"][("tse", 2022, "2")]      # apelido entre parênteses ignorado
    assert pessoa(n, n["chaves"][("estadual", "SP", "a")])["partido"] == "par_pl"
    assert n["chaves"][("estadual", "RJ", "501")] == n["chaves"][("tse", 2022, "501")]   # id da Assembleia = sequencial do TSE
    assert pessoa(n, n["chaves"][("estadual", "RJ", "501")])["ligacao"]["estadual"] == ["sequencial", "alta"]


def test_homonimo_fica_ambiguo_e_sem_par_vira_pessoa_propria(tmp_path):
    montar(tmp_path)
    n = ident.construir({}, tmp_path)
    amb = n["ligacoes"]["ambiguos"]
    assert [(a["fonte"], a["id"]) for a in amb] == [("estadual", "SP:b")]
    assert sorted(amb[0]["candidatos"]) == sorted([n["chaves"][("tse", 2022, "3")], n["chaves"][("tse", 2022, "4")]])
    for chave in (("estadual", "SP", "b"), ("estadual", "SP", "c"), ("senado", "8")):
        assert n["chaves"][chave] not in {n["chaves"][("tse", 2022, s)] for s in "1234"} | {n["chaves"][("tse", 2022, "500")]}


def test_data_de_nascimento_diferente_impede_a_ligacao(tmp_path):
    montar(tmp_path)
    n = ident.construir({7: {"id": 7, "nome": "Ana", "nomeCivil": "Ana M. Souza", "nascimento": "1999-09-09", "partido": "PT", "uf": "SP"}}, tmp_path)
    assert n["chaves"][("camara", "7")] != n["chaves"][("tse", 2022, "1")]


def test_partido_id_unifica_grafias_e_sucessao():
    d = set()
    assert ident.partido_id("PC do B") == ident.partido_id("PCdoB") == ident.partido_id("PCDOB") == "par_pcdob"
    assert {ident.partido_id(x) for x in ("UNIÃO", "União Brasil", "UB", "União")} == {"par_uniao"}
    assert ident.partido_id("Partido Liberal (PL)") == ident.partido_id("PR") == "par_pl"
    assert ident.partido_id("FE UNIÃO PP") is None and ident.partido_id("  ") is None and ident.partido_id(None) is None
    assert ident.partido_id("XYZ Novo", d) == "par_xyznovo" and d == {"XYZ Novo"}
    assert ident._atual("PRP") == "PRD"      # PRP -> PATRIOTA -> PRD


def test_tabela_de_partidos_e_consistente():
    chaves = set(ident.PARTIDOS)
    numeros_vigentes = [v[2] for v in ident.PARTIDOS.values() if not v[4]]
    assert len(numeros_vigentes) == len(set(numeros_vigentes))
    for k, (_, _, _, _, suc) in ident.PARTIDOS.items():
        assert suc is None or suc in chaves
        assert ident._atual(k) in chaves and not ident.PARTIDOS[ident._atual(k)][4]
    assert len(ident.ALIAS_PARTIDO) >= len(chaves)


def test_partidos_e_federacoes_na_saida(tmp_path):
    montar(tmp_path)
    n = ident.construir({}, tmp_path)
    por_id = {p["id"]: p for p in n["partidos"]["partidos"]}
    assert por_id["par_psl"]["sucessor"] == "par_uniao" and por_id["par_psl"]["atual"] == "par_uniao"
    assert "sucessor" not in por_id["par_pt"]
    assert [f["membros"] for f in n["partidos"]["federacoes"]] == [["par_pcdob", "par_pt", "par_pv"]]
    assert n["partidos"]["federacoes"][0]["id"] == "fed_pcdob_pt_pv"


def test_salvar_nucleo(tmp_path):
    montar(tmp_path)
    n = ident.construir({}, tmp_path)
    ident.salvar_nucleo(n, tmp_path / "saida")
    assert json.loads((tmp_path / "saida" / "pessoas.json").read_text(encoding="utf-8")) == n["pessoas"]
    assert (tmp_path / "saida" / "partidos.json").exists() and (tmp_path / "saida" / "ligacoes.json").exists()


# ---------------------------------------------------------------- nome em registro -> deputado da Assembleia

def test_ligar_nomes_por_nome_e_nome_civil_sem_ambiguidade():
    deps = [{"id": 1, "nome": "Zé Maria", "nomeCivil": "José Maria da Silva"},
            {"id": 2, "nome": "Ana Souza", "nomeCivil": None},
            {"id": 3, "nome": "Ana Souza", "nomeCivil": None},
            {"id": 4, "nome": "João", "nomeCivil": "João Pereira"}]
    r = ident.ligar_nomes(["DEP ZÉ MARIA", "José Maria da Silva", "Ana Souza", "Fulano", "joao pereira"], deps)
    assert r == {"DEP ZÉ MARIA": 1, "José Maria da Silva": 1, "joao pereira": 4}


def test_ligar_nomes_por_palavras_com_titulos_da_uf():
    deputados = [{"id": "1", "nome": "Ana", "nomeCivil": "Ana Paula Souza"}, {"id": "2", "nome": "Beto", "nomeCivil": "Beto Lima"}]
    assert ident.ligar_nomes(["Dep. Souza Ana", "Lima", "Ana", "Zé"], deputados, "RJ") == {"Dep. Souza Ana": "1", "Lima": "2", "Ana": "1"}
    assert ident.ligar_nomes(["Lima"], deputados) == {}   # sem a regra da UF, só o nome inteiro


def test_ligar_nomes_manual_vem_de_arquivo_versionado():
    deputados = [{"id": "1", "nome": "Roberto Hashioka", "nomeCivil": None}]
    assert ident.MANUAIS["MS"]["hashioka"] == "Roberto Hashioka"
    assert ident.ligar_nomes(["DEP. HASHIOKA"], deputados, "MS") == {"DEP. HASHIOKA": "1"}
    assert ident._LOG["MS"]["nomes"]["DEP. HASHIOKA"][1:] == ["manual", "alta"]


def test_gravar_ligacoes_guarda_metodo_ambiguos_e_sem_par_e_junta_com_o_anterior(tmp_path):
    ident._LOG.clear()
    deputados = [{"id": "1", "nome": "Ana Souza", "nomeCivil": None}, {"id": "2", "nome": "Beto Lima", "nomeCivil": None},
                 {"id": "3", "nome": "Beto Lima", "nomeCivil": None}]
    ident.ligar_nomes(["Ana Souza", "Beto Lima", "Fulano"], deputados, "XX")
    ident.gravar_ligacoes(raiz=tmp_path)
    arq = tmp_path / "XX" / "ligacoes.json"
    assert json.loads(arq.read_text(encoding="utf-8")) == {"nomes": {"Ana Souza": ["1", "nome", "média"]},
                                                          "ambiguos": {"Beto Lima": ["2", "3"]}, "semPar": ["Fulano"]}
    assert "XX" not in ident._LOG
    ident.ligar_nomes(["Fulano"], [{"id": "9", "nome": "Fulano", "nomeCivil": None}], "XX")   # agora existe
    ident.gravar_ligacoes("XX", tmp_path)
    tabela = json.loads(arq.read_text(encoding="utf-8"))
    assert tabela["nomes"] == {"Ana Souza": ["1", "nome", "média"], "Fulano": ["9", "nome", "média"]} and tabela["semPar"] == []


def test_construir_junta_a_tabela_de_registros_com_a_pessoa(tmp_path):
    montar(tmp_path)
    gravar(tmp_path / "estaduais" / "RJ" / "ligacoes.json", {"nomes": {"DANI": ["501", "nome", "média"]}, "ambiguos": {}, "semPar": ["Ninguém"]})
    # sem deputados.json da UF a pessoa não existe, mas a linha da tabela continua lá
    registros = ident.construir({}, tmp_path)["ligacoes"]["registros"]
    assert registros["RJ"]["nomes"]["DANI"][:3] == ["501", "nome", "média"] and registros["RJ"]["semPar"] == ["Ninguém"]


def test_eleito_do_tse_por_palavras():
    eleitos = [{"sequencial": "1", "nome": "Ana Paula da Silva", "urna": "Paulinha"}, {"sequencial": "2", "nome": "Dr. João Júnior", "urna": "Dr João"}]
    assert ident.eleito_do_tse("SC", "Ana Paula Silva", eleitos)["sequencial"] == "1"
    assert ident.eleito_do_tse("SE", "Joao Jr", eleitos)["sequencial"] == "2"
    assert ident.eleito_do_tse("SE", "Zé", eleitos) is None


def test_aposentados_do_senado_ligam_so_por_nome_unico_de_candidato_a_senador(tmp_path):
    bruto = tmp_path / "dados"
    montar(bruto)
    gravar(bruto / "senado_aposentados.json", {"itens": [
        {"nome": "BIA LIMA", "tipo": "EX-SENADOR IPC", "inicio": "1990-02-01", "valor": 30000.0},
        {"nome": "ANA MARIA SOUZA", "tipo": "EX-SENADOR PSSC", "inicio": "2016-01-01", "valor": 1.0},
        {"nome": "FULANO DE TAL", "tipo": "EX-SENADOR IPC", "inicio": None, "valor": None}]})
    n = ident.construir({}, bruto)
    assert [(a["nome"], a["tipo"]) for a in n["aposentados"]] == [("BIA LIMA", "EX-SENADOR IPC")]
    bia = next(p for p in n["pessoas"] if p["nome"] == "Bia Lima")
    assert bia["ligacao"]["aposentadoria"] == ["nome+cargo", "média"] and n["aposentados"][0]["pessoa"] == bia["id"]
    assert n["ligacoes"]["semLigacao"]["aposentadoria"] == 2
