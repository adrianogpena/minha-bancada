"""Sanidade dos arquivos coletados e versionados em dados/: o que o gerar.py e o site esperam encontrar."""
import json

import pytest

from conftest import RAIZ

DADOS = RAIZ / "dados"
ARQUIVOS = sorted(DADOS.rglob("*.json"))


def test_ha_dados_versionados():
    assert ARQUIVOS


@pytest.mark.parametrize("arq", ARQUIVOS, ids=lambda p: str(p.relative_to(DADOS)))
def test_json_valido(arq):
    json.loads(arq.read_text(encoding="utf-8"))


def carregar(padrao):
    return [pytest.param(json.loads(a.read_text(encoding="utf-8")), id=f"{a.parent.name}/{a.name}")
            for a in sorted(DADOS.glob(padrao))]


@pytest.mark.parametrize("dados", carregar("estaduais/*/materias_20*.json"))
def test_materias_estaduais(dados):
    assert isinstance(dados["materias"], dict)
    assert "coletadoEm" in dados


@pytest.mark.parametrize("dados", carregar("estaduais/*/votacoes.json"))
def test_votacoes_estaduais(dados):
    assert isinstance(dados["votacoes"], dict)


def test_executivo_tem_campos_essenciais():
    for i in json.loads((DADOS / "executivo.json").read_text(encoding="utf-8")):
        assert {"id", "tipo", "numero", "ano"} <= i.keys()


def test_mandatos_cobrem_anos_coletados_do_tse():
    pastas = {p.name for p in (DADOS / "tse").iterdir() if p.name.isdigit()}
    assert pastas <= {str(a) for a in __import__("gerar_politicos").MANDATOS}


def test_proposicoes_dos_deputados_tem_cadastro_quando_no_formato_novo():
    """`ids` (formato novo) só vale com a ementa no cadastro; `itens` (formato antigo) carrega os objetos."""
    import cadastro_proposicoes as cp
    arquivos = sorted((DADOS / "proposicoes").glob("*.json"))
    cadastro = cp.Cadastro(DADOS / "proposicoes_cadastro")
    for arq in arquivos:
        conteudo = json.loads(arq.read_text(encoding="utf-8"))
        ids = cp.ids_de(conteudo)
        assert all(isinstance(i, int) for i in ids), arq.name
        if "ids" in conteudo:
            assert all(cadastro.get(i) for i in ids), arq.name
        else:
            assert len(cp.itens_legados(conteudo)) == len(ids), arq.name
