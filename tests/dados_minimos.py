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
        "frentes": [{"id": 1, "titulo": "Frente X"}], "coletadoEm": "2026-10-01T00:00:00+00:00"})
    gravar(bruto / "votacoes" / "2026.json", {"1-1": {
        "id": "1-1", "data": "2026-08-12", "hora": "17:58", "orgao": "PLEN", "descricao": "Aprovado.", "proposicao": "PL 1/2026",
        "propId": 900, "ementa": "Dispõe sobre algo.", "aprovada": 1, "votos": [[101, "Sim"], [102, "Não"]]}})
    gravar(bruto / "senado.json", [{"id": "7", "nome": "Bia Lima", "partido": "PL", "uf": "RJ"}])
    gravar(bruto / "senado_votacoes" / "2026.json", {"9": {
        "id": "9", "data": "2026-02-24", "descricao": "Votação X", "aprovada": 1, "votos": [["7", "sim", "Sim|"]]}})
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
