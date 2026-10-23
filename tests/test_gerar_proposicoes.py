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
                                    sens, aut_sen, vot_sen, TIPOS_PROJETO, destino_projeto)
    assert total == 2   # o requerimento fica de fora
    import json
    ficha = json.loads((tmp_path / "proposicao" / "c-5.json").read_text(encoding="utf-8"))
    assert [(a["nome"], a.get("id"), a.get("principal")) for a in ficha["autores"]] == [("Ana", "101", True), ("Poder Executivo", None, None)]
    assert ficha["votacoes"][0]["nominal"] and ficha["votacoes"][0]["placar"] == {"sim": 3}
    sen = json.loads((tmp_path / "proposicao" / "s-88.json").read_text(encoding="utf-8"))
    assert sen["autores"][0]["id"] == "7" and sen["votacoes"][0]["id"] == "9" and sen["d"] == "aprovada"
