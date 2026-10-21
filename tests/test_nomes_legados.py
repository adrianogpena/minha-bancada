import nomes_legados as n


def test_materia_estadual_antiga_ganha_nomes_atuais():
    antigo = {"coletadoEm": "x", "materias": {"1": {"t": "PL", "td": "Projeto", "n": 2, "a": 2026, "ap": "2026-01-01", "e": "e",
                                                      "sit": "Em tramitação", "tr": True, "pdf": "p", "au": [3], "dep": [4]}}}
    novo = n.atualizar("dados/estaduais/AC/materias_2026.json", antigo)
    assert novo["materias"]["1"] == {"tipo": "PL", "tipoDescricao": "Projeto", "numero": 2, "ano": 2026, "dataApresentacao": "2026-01-01",
                                     "ementa": "e", "situacao": "Em tramitação", "emTramitacao": True, "linkTexto": "p",
                                     "idsAutores": [3], "idsDeputados": [4]}


def test_votacao_detalhe_executivo_e_senado_antigos():
    assert n.atualizar("dados/estaduais/AC/votacoes.json", {"votacoes": {"1": {"d": "x", "m": 2, "ok": 1, "res": "A", "abs": 0, "v": []}}}) == \
        {"votacoes": {"1": {"data": "x", "idMateria": 2, "aprovada": 1, "resultado": "A", "abstencoes": 0, "votos": []}}}
    assert n.atualizar("dados/proposicoes_detalhe.json", {"1": {"apres": "a", "sit": "s", "fim": True}}) == {"1": {"dataApresentacao": "a", "situacao": "s", "finalizada": True}}
    assert n.atualizar("dados/executivo.json", [{"id": 1, "sit": "s", "data": "d"}]) == [{"id": 1, "situacao": "s", "dataSituacao": "d"}]
    assert n.atualizar("dados/senado_materias.json", {"1": {"sit": "s", "proc": 9}}) == {"1": {"situacao": "s", "processo": 9}}


def test_dados_ja_atuais_e_outros_arquivos_ficam_como_estao():
    atual = {"materias": {"1": {"tipo": "PL", "situacao": "x"}}}
    assert n.atualizar("dados/estaduais/AC/materias_2026.json", atual) == atual
    outro = [{"sit": "fica"}]
    assert n.atualizar("dados/tse/2024/SP.json", outro) is outro
