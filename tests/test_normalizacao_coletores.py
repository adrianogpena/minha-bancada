"""Trava a regra "normalizar na entrada" (CLAUDE.md): os coletores não montam data, CNPJ nem e-mail à mão.
Use `estaduais_comum` (`data_iso`, `data_br_iso`, `fornecedor`, `email`). Exceção justificada: acrescente a linha em EXCECOES."""
import re
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
COLETORES = sorted(SCRIPTS.glob("coletar*.py"))

PROIBIDOS = [
    (re.compile(r"(?i)\bdata\w*\W[^\n]*\[:10\]"), "data cortada com [:10]: use comum.data_iso"),
    (re.compile(r"(?i)\[:10\][^\n]*\bdata\b"), "data cortada com [:10]: use comum.data_iso"),
    (re.compile(r"(?i)(cnpj|cpf|documento|fornec)[^\n]*re\.sub\(r?[\"']\\D|re\.sub\(r?[\"']\\D[^\n]*(cnpj|cpf|documento|fornec)"), "documento só com dígitos à mão: use comum.fornecedor / fornecedores.documento"),
    (re.compile(r"strptime\([^)]*%d/%m/%Y"), "data dd/mm/aaaa à mão: use comum.data_br_iso"),
]
# (arquivo, trecho da linha) liberados
EXCECOES: set = set()


def _violacoes(arq: Path):
    for n, linha in enumerate(arq.read_text(encoding="utf-8").splitlines(), 1):
        if linha.lstrip().startswith("#"):
            continue
        for padrao, motivo in PROIBIDOS:
            if padrao.search(linha) and not any(arq.name == a and t in linha for a, t in EXCECOES):
                yield f"{arq.name}:{n}: {motivo}\n    {linha.strip()}"


@pytest.mark.parametrize("arq", COLETORES, ids=lambda a: a.name)
def test_coletor_nao_normaliza_na_mao(arq):
    achados = list(_violacoes(arq))
    assert not achados, "\n".join(achados)


def test_ha_coletores_para_varrer():
    assert len(COLETORES) > 20
