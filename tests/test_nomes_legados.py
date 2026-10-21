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
    assert n.atualizar("dados/outro.json", outro) is outro


def test_tse_antigo_ganha_nomes_atuais():
    eleito = {"sq": "1", "chapaSq": None, "ue": "61018", "votos": [{"turno": 1, "votos": 5, "pct": 40.0}]}
    assert n.atualizar("dados/tse/2024/SP.json", [eleito]) == [{"sequencial": "1", "sequencialChapa": None, "unidadeEleitoral": "61018",
                                                               "votos": [{"turno": 1, "votos": 5, "percentual": 40.0}]}]
    assert n.atualizar("dados/tse/contas/2024/SP.json", {"1": {"r": 1.0, "d": 2.0, "p": 3.0, "o": [], "dn": [], "do": [], "g": []}}) == \
        {"1": {"receitas": 1.0, "despesasContratadas": 2.0, "despesasPagas": 3.0, "origensReceita": [], "principaisDoadores": [],
               "doadoresOriginarios": [], "gastosPorCategoria": []}}
    assert n.atualizar("dados/tse/disputa/2024/SP.json", {"PREFEITO|1": {"t": {"1": {}}, "v": 1}}) == {"PREFEITO|1": {"turnos": {"1": {}}, "vagas": 1}}
    assert n.atualizar("dados/tse/eleitorado/2024/SP.json", {"_uf": {"t": 1, "g": [1, 0], "f": [0], "e": [0]}}) == \
        {"_uf": {"total": 1, "porGenero": [1, 0], "porFaixaEtaria": [0], "porEscolaridade": [0]}}
    assert n.atualizar("dados/tse/secoes/2024/SP.json", {"1": {"n": 1, "t": 9, "l": [], "m": [], "mp": []}}) == \
        {"1": {"turno": 1, "totalVotos": 9, "locaisDeVotacao": [], "municipios": [], "votosPorMunicipio": []}}
    assert n.atualizar("dados/tse/partidos/2024/SP.json", {"VEREADOR|1": {"t": 3, "p": {"X": [1, 2, ""]}}}) == {"VEREADOR|1": {"totalVotos": 3, "partidos": {"X": [1, 2, ""]}}}
    assert n.atualizar("dados/tse/coligacoes/2024/SP.json", {"VEREADOR|1": {"c": [["I"]], "p": {"X": 0}}}) == {"VEREADOR|1": {"coligacoes": [["I"]], "coligacaoDoPartido": {"X": 0}}}


def test_historico_antigo_ganha_nomes_atuais():
    dia = {"data": "2026-01-02", "cobertura": {"BR": {"n": "Brasil", "m": True, "e": 3}},
           "eventos": [{"l": "BR", "k": "nova", "t": "PL 1/2026", "p": [{"c": "dep:1", "n": "Ana", "h": "deputado.html?id=1"}], "x": "e", "m": ["a", "b"],
                        "s": "r", "d": "2026-01-01", "f": [["Fonte", "http://x"]], "r": 2, "n": 5, "i": ["REQ 1/2026"]}]}
    novo = n.atualizar("dados/historico/2026-01-02.json", dia)
    assert novo["cobertura"] == {"BR": {"nome": "Brasil", "mudou": True, "itens": 3}}
    assert novo["eventos"] == [{"local": "BR", "categoria": "nova", "titulo": "PL 1/2026",
                                "politicos": [{"codigo": "dep:1", "nome": "Ana", "pagina": "deputado.html?id=1"}], "texto": "e", "mudanca": ["a", "b"],
                                "resumo": "r", "dataDoAto": "2026-01-01", "fontes": [["Fonte", "http://x"]], "relevancia": 2, "quantidade": 5,
                                "titulos": ["REQ 1/2026"]}]
    assert n.atualizar("dados/historico/indice.json", [{"d": "2026-01-02", "n": 4, "l": {"BR": 4}, "r": {"1": 4}}]) == \
        [{"data": "2026-01-02", "total": 4, "locais": {"BR": 4}, "relevancias": {"1": 4}}]
