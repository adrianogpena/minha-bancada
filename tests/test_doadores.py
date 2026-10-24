import json

import doadores
import fornecedores as forn
import identidades
from test_fornecedores import TIM, VIVO, gravar, montar

TIM_SEM_ZERO = "2421421000111"


def preparar(tmp_path):
    montar(tmp_path)   # eleito 10 (Carlos Lima, SP 2022), deputado estadual "a" ligado a ele, pagando TIM (150) e Vivo (50) em 2026
    gravar(tmp_path / "tse" / "2022" / "SP.json", [
        {"sequencial": "10", "nome": "Carlos Lima", "urna": "Carlão", "cargo": "DEPUTADO ESTADUAL", "uf": "SP", "nascimento": "1970-05-05", "partido": "PL",
         "federacao": None},
        {"sequencial": "11", "nome": "Outro Eleito", "urna": "Outro", "cargo": "DEPUTADO ESTADUAL", "uf": "SP", "nascimento": "1971-06-06", "partido": "PT",
         "federacao": None}])
    gravar(tmp_path / "tse" / "contas" / "2022" / "SP.json", {
        "10": {"receitas": 1.0, "principaisDoadores": [], "doadoresOriginarios": [],
               "doadoresPJ": [[TIM, "TIM S A", "Recursos de origens não identificadas", 3000.0], ["11144477000100", "Empresa Qualquer", "Outra", 5.0]],
               "originariosPJ": [[VIVO, "Telefonica Brasil", 700.0]]},
        # coleta antiga (sem CNPJ): só vale o nome exato de fornecedor com CNPJ; partido e pessoa física ficam de fora
        "11": {"receitas": 1.0, "doadoresOriginarios": [["Vivo", 90.0]],
               "principaisDoadores": [["Partido Liberal", "Recursos de partido político", 100.0], ["Mercadinho", "Recursos de pessoas físicas", 10.0],
                                      ["Vivo Participações", "Recursos de pessoas jurídicas", 20.0]]}})
    camara = {}
    nucleo = identidades.construir(camara, tmp_path)
    return nucleo, forn.construir(camara, tmp_path, nucleo)


def test_cnpj_liga_com_confianca_alta_e_mostra_o_que_o_mesmo_politico_recebeu(tmp_path):
    nucleo, f = preparar(tmp_path)
    r = doadores.construir(tmp_path, nucleo, f)
    reg = r["ligacoes"]["registros"]
    assert reg["2022|10|direto|" + TIM] == ["for_02421421", "cnpj", "alta"]
    assert reg["2022|10|repasse|" + VIVO] == ["for_02558157", "cnpj", "alta"]
    assert not any(k.endswith("11144477000100") for k in reg)                      # empresa que não é fornecedora
    tim = next(c for c in r["cruzamentos"] if c["fornecedor"] == "for_02421421")
    d = tim["doacoes"][0]
    assert d["valor"] == 3000.0 and d["eleicao"] == 2022 and d["via"] == "direto" and d["ligacao"] == ["cnpj", "alta"]
    assert d["pagoPeloMesmoPolitico"] == [{"casa": "estadual", "uf": "SP", "id": "a", "valor": 150.0}]
    assert d["pessoa"] == nucleo["chaves"][("tse", 2022, "10")] and d["sequencial"] == "10" and d["uf"] == "SP"
    assert r["anoPagamentos"] == 2026
    assert "nome" not in d and "documento" not in d                                   # nome e documento ficam em nucleo/fornecedores.json


def test_coleta_antiga_liga_so_pelo_nome_exato_de_empresa(tmp_path):
    nucleo, f = preparar(tmp_path)
    reg = doadores.construir(tmp_path, nucleo, f)["ligacoes"]["registros"]
    assert reg["2022|11|repasse|Vivo"] == ["for_02558157", "nome", "média"]
    assert "2022|11|direto|Vivo Participações" not in reg and "2022|11|direto|Mercadinho" not in reg and "2022|11|direto|Partido Liberal" not in reg


def test_ordena_pagos_pelo_mesmo_politico_primeiro_e_resume(tmp_path):
    nucleo, f = preparar(tmp_path)
    r = doadores.construir(tmp_path, nucleo, f)
    assert [c["fornecedor"] for c in r["cruzamentos"]][0] == "for_02421421"
    assert r["resumo"]["ligados"] == {"cnpj": 2, "nome": 1} and r["resumo"]["comPagamentoAoMesmoPolitico"] == 2
    vivo11 = [d for c in r["cruzamentos"] if c["fornecedor"] == "for_02558157" for d in c["doacoes"] if d["sequencial"] == "11"][0]
    assert "pagoPeloMesmoPolitico" not in vivo11                                      # quem recebeu a doação não foi quem pagou a Vivo


def test_salvar_inclui_fontes(tmp_path):
    nucleo, f = preparar(tmp_path)
    doadores.salvar_doadores(doadores.construir(tmp_path, nucleo, f), tmp_path / "saida")
    j = json.loads((tmp_path / "saida" / "doadores_fornecedores.json").read_text(encoding="utf-8"))
    assert j["fontes"]["doacoes"]["url"].startswith("https://") and set(j["fontes"]["pagamentos"]) == {"camara", "senado", "estadual"}


def test_ligar_doadores_nome_ambiguo_nao_liga_e_pessoa_fisica_fica_de_fora():
    fornecedores = [{"id": "for_00000001", "tipo": "PJ", "nome": "Casa Azul Ltda"}, {"id": "for_00000002", "tipo": "PJ", "nome": "CASA AZUL SA"},
                    {"id": "for_pf_x", "tipo": "PF", "nome": "Maria Souza"}, {"id": "for_n_y", "tipo": None, "nome": "Padaria Sol"},
                    {"id": "for_00000003", "tipo": "PJ", "nome": "Sol Nascente", "nomes": ["SOL NASCENTE COMERCIO"]}]
    ligados, ambiguos = identidades.ligar_doadores(
        [("a", "Casa Azul", None), ("b", "Maria Souza", None), ("c", "Padaria Sol", None), ("d", "sol nascente comercio ltda", None),
         ("e", "Qualquer", "00000003000100")], fornecedores)
    assert ambiguos == {"a": ["for_00000001", "for_00000002"]}
    assert ligados == {"d": ["for_00000003", "nome", "média"], "e": ["for_00000003", "cnpj", "alta"]}
