import gerar_proposicoes
from gerar import TIPOS_PROJETO, destino_projeto


def test_camara_e_senado_ligam_autores_e_votacoes(tmp_path):
    deps = {101: {"nome": "Ana", "partido": "PT", "uf": "SP", "proposicoes": [
        {"id": 5, "tipo": "PEC", "numero": 45, "ano": 2019, "ementa": "Reforma"}, {"id": 6, "tipo": "REQ", "numero": 1, "ano": 2020, "ementa": "x"}]}}
    autorias = {"5": {"idPrincipal": 101, "autores": [[101, "Ana"], [None, "Poder Executivo"]]}}
    nominais = {"5-1": {"id": "5-1", "descricao": "Votação", "placar": {"sim": 3}, "aprovada": 1}}
    sens = [{"id": "7", "nome": "Bia", "partido": "PL", "uf": "RJ"}]
    aut_sen = {"7": [{"id": "88", "tipo": "PL", "numero": "10", "ano": 2024, "ementa": "Algo", "principal": True, "situacao": "Aprovada"}]}
    vot_sen = [{"id": "9", "propId": "88", "data": "2025-01-02", "descricao": "Plenário", "placar": {"sim": 1}, "aprovada": 1}]
    total = gerar_proposicoes.gerar(tmp_path, deps, {}, autorias, {"5": [{"id": "5-1", "data": "2023-01-01", "descricao": "d"}]}, nominais,
                                    sens, aut_sen, vot_sen, TIPOS_PROJETO, destino_projeto,
                                    {("camara", "101"): "pes_ana", ("senado", "7"): "pes_bia"})
    assert total == 2   # o requerimento fica de fora
    import json
    lido = lambda nome: json.loads((tmp_path / nome).read_text(encoding="utf-8"))
    ficha = lido("proposicao/c-2019.json")["5"]
    assert ficha["au"] == [{"id": "101", "p": 1}, {"nome": "Poder Executivo"}]   # nome e partido ficam em deputados.json
    assert ficha["v"] == [{"id": "5-1", "data": "2023-01-01"}]                   # nominal: descrição e placar ficam em votacoes.json
    assert "e" not in ficha and "s" not in ficha                                 # ementa e situação, só no índice
    sen = lido("proposicao/s-2024.json")["88"]
    assert sen["au"] == [{"id": "7", "p": 1}] and sen["v"] == [{"id": "9", "data": "2025-01-02"}]
    assert [i["d"] for i in lido("proposicoes.json") if i["k"] == "s-88"] == ["aprovada"]
    assert lido("senadores.json") == [{"id": "7", "nome": "Bia", "partido": "PL", "uf": "RJ"}]
    # relação proposição -> pessoa: só quem tem id no núcleo; o Executivo entra em semPessoa
    assert lido("nucleo/autorias.json") == {"proposicoes": 2, "semPessoa": 1, "porPessoa": {"pes_ana": [["c-5", 1]], "pes_bia": [["s-88", 1]]}}
