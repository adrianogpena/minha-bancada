import json

import identidades
import mandatos as M


def gravar(caminho, obj):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def vereador(seq, nome, urna, ue, municipio, nasc):
    return {"sequencial": seq, "nome": nome, "urna": urna, "cargo": "VEREADOR", "uf": "PE", "nascimento": nasc, "partido": "PT", "genero": "MASCULINO",
            "federacao": None, "situacao": "eleito", "unidadeEleitoral": ue, "municipio": municipio}


def item(nome, cpf, matricula, ingresso, afastamento=None, municipio="Afogados da Ingazeira", unidade="100"):
    return {"municipio": municipio, "unidade": unidade, "nome": nome, "cpf": cpf, "cargo": "VEREADOR", "matricula": matricula,
            "ingresso": ingresso, "afastamento": afastamento}


def montar(bruto, itens):
    gravar(bruto / "tse" / "2024" / "PE.json", [
        vereador("1", "José Lima da Silva", "Zé Lima", "20001", "Afogados da Ingazeira", "1970-01-01"),
        vereador("2", "Maria Souza", "Maria", "20001", "Afogados da Ingazeira", "1980-02-02"),
        vereador("3", "Pedro Alves", "Pedro", "20001", "Afogados da Ingazeira", "1975-03-03"),
        vereador("4", "Pedro Alves", "Pedrão", "20001", "Afogados da Ingazeira", "1985-04-04"),
        vereador("5", "Carlos Rocha", "Carlão", "20002", "São Caitano", "1968-05-05"),
        vereador("6", "Ana Lins", "Ana", "20003", "Recife", "1990-06-06"),
    ])
    gravar(bruto / "municipais" / "PE" / "vereadores.json", {"itens": itens})


def rodar(tmp_path, itens, hoje="2026-10-23"):
    montar(tmp_path, itens)
    nucleo = identidades.construir({}, tmp_path)
    return M.construir({}, tmp_path, nucleo, hoje), nucleo


def mandato(res, nucleo, seq, **filtro):
    pessoa = nucleo["chaves"][("tse", 2024, seq)]
    achados = [m for m in res["mandatos"] if m["pessoa"] == pessoa and m["cargo"] == "VEREADOR" and all(m.get(k) == v for k, v in filtro.items())]
    assert len(achados) == 1, achados
    return achados[0]


ITENS = [item("JOSE LIMA DA SILVA", "***.111.222-**", "1", "2025-01-01"),
         item("MARIA SOUZA", "***.333.444-**", "2", "2025-01-01", afastamento="2025-08-31"),
         item("PEDRO ALVES", "***.555.666-**", "3", "2025-01-01"),
         item("CARLOS ROCHA", "***.777.888-**", "1", "2025-01-01", municipio="São Caetano", unidade="200")]


def test_nome_igual_liga_confirma_o_mandato_do_tse_e_registra_metodo(tmp_path):
    res, n = rodar(tmp_path, ITENS)
    pessoa = next(p for p in n["pessoas"] if p["id"] == n["chaves"][("tse", 2024, "1")])
    assert pessoa["ligacao"]["vereador_pe"] == ["nome+municipio", "alta"]
    m = mandato(res, n, "1")
    assert m["status"] == "atual" and m["confirmado"] is True and m["fontes"]["vereador_pe"] == "100|1|2025-01-01" and "condicao" not in m
    assert mandato(res, n, "5")["fontes"]["vereador_pe"] == "200|1|2025-01-01"     # grafia "São Caetano" do TCE casa com "São Caitano" do TSE


def test_urna_liga_com_confianca_menor(tmp_path):
    res, n = rodar(tmp_path, [item("ZE LIMA", "***.111.222-**", "1", "2025-01-01")])
    pessoa = next(p for p in n["pessoas"] if p["id"] == n["chaves"][("tse", 2024, "1")])
    assert pessoa["ligacao"]["vereador_pe"] == ["urna+municipio", "média"]


def test_nome_ambiguo_nao_liga_nem_cria_mandato(tmp_path):
    res, n = rodar(tmp_path, ITENS)
    ambiguo = [a for a in n["ligacoes"]["ambiguos"] if a["fonte"] == "vereador_pe"]
    assert len(ambiguo) == 1 and ambiguo[0]["nome"] == "PEDRO ALVES" and len(ambiguo[0]["candidatos"]) == 2
    assert "vereador_pe" not in next(p for p in n["pessoas"] if p["id"] == n["chaves"][("tse", 2024, "3")]).get("ligacao", {})
    assert "confirmado" not in mandato(res, n, "3")


def test_suplente_que_assumiu_no_meio_do_mandato_ganha_mandato_proprio(tmp_path):
    itens = ITENS + [item("JOAO SUPLENTE", "***.999.000-**", "9", "2025-08-15")]
    res, n = rodar(tmp_path, itens)
    pessoa = n["chaves"][("vereador_pe", "100|9|2025-08-15")]
    m = next(x for x in res["mandatos"] if x["pessoa"] == pessoa)
    assert (m["cargo"], m["condicao"], m["inicio"], m["fim"], m["status"], m["confirmado"]) == ("VEREADOR", "suplente", "2025-08-15", "2028-12-31", "atual", True)
    assert m["municipio"] == "20001" and "inicioAproximado" not in m and m["fontes"] == {"vereador_pe": "100|9|2025-08-15"}
    assert m["id"] == M.gerar_id("man", "vereador_pe", "100|9|2025-08-15")
    assert n["ligacoes"]["semLigacao"]["vereador_pe"] >= 1


def test_suplente_sem_data_de_ingresso_tem_inicio_aproximado(tmp_path):
    res, n = rodar(tmp_path, ITENS + [item("JOAO SUPLENTE", "***.999.000-**", "9", None)])
    m = next(x for x in res["mandatos"] if x["pessoa"] == n["chaves"][("vereador_pe", "100|9|")])
    assert m["inicio"] == "2025-01-01" and m["inicioAproximado"] is True


def test_eleito_afastado_ou_que_o_tce_nao_lista_vira_fora_de_exercicio(tmp_path):
    res, n = rodar(tmp_path, ITENS)
    assert mandato(res, n, "2")["status"] == "fora_de_exercicio"       # saiu em 2025-08-31
    montar(tmp_path, [i for i in ITENS if i["nome"] != "JOSE LIMA DA SILVA"])
    n = identidades.construir({}, tmp_path)
    assert mandato(M.construir({}, tmp_path, n, "2026-10-23"), n, "1")["status"] == "fora_de_exercicio"


def test_municipio_sem_lista_do_tce_nao_muda(tmp_path):
    res, n = rodar(tmp_path, ITENS)
    assert mandato(res, n, "6")["status"] == "atual" and "confirmado" not in mandato(res, n, "6")     # Recife não está na folha
    assert n["ligacoes"]["municipiosSemCodigo"] == {}


def test_municipio_do_tce_sem_codigo_do_tse_e_registrado_e_nao_liga(tmp_path):
    res, n = rodar(tmp_path, ITENS + [item("FULANO", "***.000.111-**", "1", "2025-01-01", municipio="Cidade Inexistente", unidade="300")])
    assert n["ligacoes"]["municipiosSemCodigo"] == {"PE": ["Cidade Inexistente"]}
    assert ("vereador_pe", "300|1|2025-01-01") not in n["chaves"]


def test_uf_sem_lista_nada_muda(tmp_path):
    gravar(tmp_path / "tse" / "2024" / "PE.json", [vereador("1", "José Lima da Silva", "Zé", "20001", "Afogados da Ingazeira", "1970-01-01")])
    n = identidades.construir({}, tmp_path)
    res = M.construir({}, tmp_path, n, "2026-10-23")
    assert n["vereadores"]["itens"] == [] and res["mandatos"][0]["status"] == "atual" and "confirmado" not in res["mandatos"][0]


def test_homonimos_com_cpf_diferente_nao_ligam(tmp_path):
    itens = [item("MARIA SOUZA", "***.333.444-**", "2", "2025-01-01"), item("MARIA SOUZA", "***.000.000-**", "7", "2025-03-01")]
    res, n = rodar(tmp_path, itens)
    assert [a["nome"] for a in n["ligacoes"]["ambiguos"] if a["fonte"] == "vereador_pe"] == ["MARIA SOUZA"]
