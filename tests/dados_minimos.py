"""Um dados/ mínimo (1 deputado, 1 senador, 1 votação de cada) e a geração do site sobre ele.
Usado por test_gerar_integracao.py e por tests/e2e/preparar_site.py (teste de fumaça no navegador)."""
import json
from unittest import mock

import gerar
import gerar_estaduais
import gerar_politicos
import gerar_prefeituras


def gravar(caminho, obj):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def montar_bruto(bruto):
    gravar(bruto / "deputados.json", [101])
    gravar(bruto / "deputados" / "101.json", {
        "id": 101, "nome": "Ana Souza", "nomeCivil": "Ana Maria Souza", "partido": "PT", "uf": "SP",
        "foto": "https://exemplo/101.jpg", "email": "dep.ana@camara.leg.br", "situacao": "Exercício",
        "condicaoEleitoral": "Titular", "gabinete": {"sala": "10"}, "nascimento": "1980-01-02",
        "municipioNascimento": "Santos", "ufNascimento": "SP", "escolaridade": "Superior", "redesSociais": [],
        "proposicoes": [{"id": 900, "tipo": "PL", "numero": 1, "ano": 2026, "ementa": "Dispõe sobre algo."}],
        "despesas": {"ano": 2026, "itens": [
            {"mes": 1, "tipo": "Passagens", "valor": 120.5, "fornecedor": "Cia Aérea", "cnpj": "12345678000195", "data": "2026-01-10", "documento": None}]},
        "frentes": [{"id": 1, "titulo": "Frente X"}],
        "profissoes": [{"titulo": "Advogada", "desde": "2019-02-06"}], "mandatosExternos": [], "historico": [{"data": "2023-02-01", "partido": "PT"}],
        "discursos": [{"data": "2026-09-02", "tipo": "PELA ORDEM", "link": None}], "coletadoEm": "2026-10-01T00:00:00+00:00"})
    gravar(bruto / "votacoes" / "2026.json", {"1-1": {
        "id": "1-1", "data": "2026-08-12", "hora": "17:58", "orgao": "PLEN", "descricao": "Aprovado.", "proposicao": "PL 1/2026",
        "propId": 900, "ementa": "Dispõe sobre algo.", "aprovada": 1, "votos": [[101, "Sim"], [102, "Não"]]}})
    gravar(bruto / "senado.json", [{"id": "7", "nome": "Bia Lima", "partido": "PL", "uf": "RJ"}])
    gravar(bruto / "senado_ficha.json", {"7": {"comissoes": [{"sigla": "CAE", "nome": "Assuntos Econômicos", "inicio": "2023-02-02", "fim": None}],
                                               "mandatos": [{"uf": "RJ", "inicio": "2023-02-01", "fim": "2031-01-31", "partidos": []}]}})
    gravar(bruto / "senado_atividade.json", {"7": {
        "relatorias": {"total": 2, "tramitando": 1, "porAno": [[2025, 2]], "porColegiado": [["CAE", 2]], "recentes": [
            {"id": "55", "materia": "PL 5/2025", "ementa": "Dispõe sobre algo.", "colegiado": "CAE", "tipo": "Relator", "desde": "2025-03-01", "ate": None, "tramitando": True}]},
        "discursos": {"total": 4, "apartes": 1, "porAno": [[2026, 4]], "assuntos": [["saúde", 3]], "recentes": [
            {"id": "9", "data": "2026-05-01", "tipo": "Pela ordem", "resumo": "Fala sobre saúde.", "url": "https://www25.senado.leg.br/web/atividade/pronunciamentos/-/p/texto/9"}]},
        "cargos": [{"sigla": "CAE", "nome": "Assuntos Econômicos", "cargo": "PRESIDENTE", "inicio": "2025-03-01", "fim": None}],
        "licencas": [{"inicio": "2025-05-20", "fim": "2025-05-21", "tipo": "Missão política"}],
        "liderancas": [{"unidade": "Liderança de Partido", "cargo": "Líder", "casa": "SF", "partido": "PL", "desde": "2025-02-01"}]}})
    gravar(bruto / "senado_votacoes" / "2026.json", {"9": {
        "id": "9", "data": "2026-02-24", "descricao": "Votação X", "aprovada": 1, "votos": [["7", "sim", "Sim|"]]}})
    gravar(bruto / "tse" / "2024" / "SP.json", [
        {"sequencial": "500", "nome": "Vera Eadora", "urna": "Vera", "cargo": "VEREADOR", "situacao": "eleito", "partido": "PT", "federacao": "PT/PC do B/PV",
         "numero": "13123", "uf": "SP", "unidadeEleitoral": "71072", "municipio": "São Paulo", "nascimento": "1980-05-05", "genero": "FEMININO",
         "resultado": "Eleito por qp", "votos": [{"turno": 1, "data": "2024-10-06", "votos": 900, "percentual": 0.5}], "bens": [], "totalBens": 0.0},
        {"sequencial": "501", "nome": "Outro Eador", "urna": "Outro", "cargo": "VEREADOR", "situacao": "eleito", "partido": "PL", "federacao": None,
         "numero": "22456", "uf": "SP", "unidadeEleitoral": "71072", "municipio": "São Paulo", "nascimento": "1975-05-05", "genero": "MASCULINO",
         "resultado": "Eleito por média", "votos": [{"turno": 1, "data": "2024-10-06", "votos": 800, "percentual": 0.4}], "bens": [], "totalBens": 0.0}])
    gravar(bruto / "tse" / "disputa" / "2024" / "SP.json", {"VEREADOR|71072": {"turnos": {"1": {"aptos": 1000, "comparecimento": 800, "abstencoes": 200,
                                                                                                "brancos": 10, "nulos": 20, "validos": 770}}, "vagas": 55}})
    gravar(bruto / "tse" / "partidos" / "2024" / "SP.json", {"VEREADOR|71072": {"totalVotos": 770, "partidos": {
        "PT": [100, 300, "PT/PC do B/PV"], "PC do B": [10, 20, "PT/PC do B/PV"], "PL": [50, 290, ""]}}})
    gravar(bruto / "tse" / "coligacoes" / "2024" / "SP.json", {"VEREADOR|71072": {
        "coligacoes": [["F", "", "Federação BRASIL DA ESPERANÇA (13-PT / 65-PC do B / 43-PV)", "Deferido"], ["I", "", "PL", "Deferido"]],
        "coligacaoDoPartido": {"PT": 0, "PC do B": 0, "PL": 1}}})
    gravar(bruto / "municipios_ibge.json", {})
    gravar(bruto / "meta.json", {"coletadoEm": "2026-10-01"})


def gerar_site(bruto, saida):
    """Roda o gerar.py com BRUTO/SAIDA trocados em todos os módulos que os têm."""
    with mock.patch.multiple(gerar, BRUTO=bruto, SAIDA=saida), mock.patch.multiple(gerar_politicos, BRUTO=bruto, SAIDA=saida), \
            mock.patch.multiple(gerar_estaduais, BRUTO=bruto / "estaduais", SAIDA=saida), \
            mock.patch.multiple(gerar_prefeituras, BRUTO=bruto / "municipais", SAIDA=saida):
        gerar.main()


def gerar_tudo(raiz):
    """Monta dados/ em raiz/dados e gera raiz/site/dados; devolve esta última."""
    bruto, saida = raiz / "dados", raiz / "site" / "dados"
    montar_bruto(bruto)
    gerar_site(bruto, saida)
    return saida
