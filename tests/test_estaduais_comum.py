"""Helpers comuns dos coletores estaduais (scripts/estaduais_comum.py)."""
import io
import zipfile

import pytest

import estaduais_comum as ec


@pytest.mark.parametrize("texto,esperado", [
    ("4.000,00", 4000.0), ("R$ 99,90", 99.9), ("31310.41", 31310.41), ("1.234.567", 1234567.0),
    ("-12,5", -12.5), (7, 7.0), ("", None), ("-", None), (None, None),
])
def test_valor_br(texto, esperado):
    assert ec.valor_br(texto) == esperado


@pytest.mark.parametrize("nome,esperado", [
    ("janeiro", 1), ("Março", 3), ("DEZEMBRO", 12), ("mar", 3), ("07", 7), ("13", None), ("xyz", None), ("", None),
])
def test_mes_numero(nome, esperado):
    assert ec.mes_numero(nome) == esperado


@pytest.mark.parametrize("nome,esperado", [
    ("DEP ANA SILVA", "ANA SILVA"), ("Dep. Ana Silva", "Ana Silva"), ("DEPUTADO(A)  Ana  Silva", "Ana Silva"),
    ("Deputada Ana", "Ana"), ("Depoimento Souza", "Depoimento Souza"),
])
def test_nome_limpo(nome, esperado):
    assert ec.nome_limpo(nome) == esperado


def test_sem_acento():
    assert ec.sem_acento("  JOSÉ  da Conceição ") == "jose da conceicao"


def test_salvar_e_ler_ida_e_volta(tmp_path):
    arq = tmp_path / "a" / "x.json"
    ec.salvar(arq, {"b": "ç", "a": 1})
    assert arq.read_text(encoding="utf-8") == '{"a":1,"b":"ç"}'
    assert ec.ler(arq) == {"a": 1, "b": "ç"} and ec.ler(tmp_path / "nada.json", []) == []


def test_sessao_limita_conexoes_por_host():
    s = ec.sessao()
    a = s.get_adapter("https://exemplo.gov.br")
    assert a._pool_maxsize == 2 and "Mozilla" in s.headers["User-Agent"]


def test_prazo_esgotado_interrompe_novas_requisicoes(monkeypatch):
    monkeypatch.setattr(ec, "PRAZO_FIM", None)
    ec.checar_prazo()  # sem prazo, nunca levanta
    monkeypatch.setattr(ec, "PRAZO_FIM", ec.time.monotonic() - 1)
    with pytest.raises(ec.PrazoEsgotado):
        ec.checar_prazo()
    with pytest.raises(ec.PrazoEsgotado):
        ec.sessao().get("https://exemplo.invalid/")


def test_sessao_tem_timeout_padrao(monkeypatch):
    monkeypatch.setattr(ec, "PRAZO_FIM", None)
    vistos = {}
    monkeypatch.setattr(ec.requests.Session, "request", lambda self, *a, **kw: vistos.update(kw))
    ec.sessao().get("https://exemplo.invalid/")
    assert vistos["timeout"] == (ec.TIMEOUT_CONEXAO, ec.TIMEOUT_PADRAO)
    ec.sessao().get("https://exemplo.invalid/", timeout=5)
    assert vistos["timeout"] == (5, 5)
    ec.sessao().get("https://exemplo.invalid/", timeout=(3, 90))
    assert vistos["timeout"] == (3, 90)


def test_host_sem_conexao_falha_na_hora_no_resto_da_coleta(monkeypatch):
    monkeypatch.setattr(ec, "PRAZO_FIM", None)
    chamadas = []

    def request(self, method, url, **kw):
        chamadas.append(url)
        if "fora" in url:
            raise ec.requests.ConnectTimeout("sem conexão")
        return "ok"
    monkeypatch.setattr(ec.requests.Session, "request", request)
    s = ec.sessao()
    for _ in range(2):
        with pytest.raises(ec.requests.ConnectTimeout):
            s.get("https://fora.gov.br/a")
    assert s.get("https://outro.gov.br/b") == "ok"
    assert chamadas == ["https://fora.gov.br/a", "https://outro.gov.br/b"]


def test_matriz_do_workflow_cobre_todas_as_ufs():
    """Cada UF nova (SAPL ou módulo coletar_estadual_<uf>.py) precisa entrar na matriz do job `estaduais` em atualizar.yml."""
    import re
    from conftest import RAIZ
    import coletar_estaduais
    texto = (RAIZ / ".github" / "workflows" / "atualizar.yml").read_text(encoding="utf-8")
    no_workflow = {u for ufs in re.findall(r'\{ id: \w+, ufs: "([A-Z ]+)"', texto) for u in ufs.split()}
    esperadas = set(coletar_estaduais.ASSEMBLEIAS) | set(coletar_estaduais.modulos_uf())
    assert no_workflow == esperadas


def test_meses_recentes_atravessa_o_ano():
    from datetime import date
    assert ec.meses_recentes(date(2026, 1, 10), 2) == {(2026, 1), (2025, 12)}
    assert ec.meses_recentes(date(2026, 5, 1), 3) == {(2026, 5), (2026, 4), (2026, 3)}


def test_ano_encerrado_so_com_arquivo_e_antes_do_ano_passado(tmp_path):
    from datetime import date
    hoje = date(2026, 10, 22)
    arq = tmp_path / "x.json"
    assert not ec.ano_encerrado(2024, hoje, arq)
    arq.write_text("{}")
    assert ec.ano_encerrado(2024, hoje, arq)
    assert not ec.ano_encerrado(2025, hoje, arq)


def test_data_br_iso():
    assert ec.data_br_iso("04/12/2025") == "2025-12-04"
    assert ec.data_br_iso(" 04/12/2025 10:00") == "2025-12-04"
    assert ec.data_br_iso("04/12/2025 10:00", inteiro=True) is None
    assert ec.data_br_iso(" 04/12/2025 ", inteiro=True) == "2025-12-04"
    assert ec.data_br_iso("") is None and ec.data_br_iso(None) is None


def test_limpar_e_compactar():
    assert ec.limpar("<p>A&amp;B  <b>c</b></p>") == "A&B c"
    assert ec.limpar(None) == ""
    assert ec.compactar("  a   b ") == "a b" and ec.compactar("  ") is None


def test_palavras():
    assert ec.palavras("Dr. João Paulo", {"dr"}) == ["joao", "paulo"]



def test_deputados_do_tse(tmp_path):
    arquivo = tmp_path / "XX.json"
    ec.salvar(arquivo, [
        {"cargo": "DEPUTADO ESTADUAL", "situacao": "eleito", "sequencial": "9", "nome": "Zeca Silva", "urna": "Zeca", "partido": "PT", "email": None},
        {"cargo": "DEPUTADO ESTADUAL", "situacao": "eleito", "sequencial": "8", "nome": "Ana Lima", "urna": None, "partido": "PL", "email": "a@x"},
        {"cargo": "DEPUTADO ESTADUAL", "situacao": "suplente", "sequencial": "7", "nome": "Fulano"},
        {"cargo": "DEPUTADO FEDERAL", "situacao": "eleito", "sequencial": "6", "nome": "Beltrano"},
    ])
    deputados = ec.deputados_do_tse(arquivo, ec.ficha_tse("XX"))
    assert [d["id"] for d in deputados] == ["8", "9"]
    assert deputados[1]["nome"] == "Zeca" and deputados[1]["nomeCivil"] == "Zeca Silva"
    assert deputados[0]["fonte"].endswith("/XX/8") and deputados[0]["email"] == "a@x"
    assert len(ec.eleitos_tse(arquivo)) == 2 and ec.eleitos_tse(tmp_path / "nao.json") == []


def test_xlsx_linhas_e_abas():
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    mini = io.BytesIO()
    with zipfile.ZipFile(mini, "w") as z:
        z.writestr("xl/sharedStrings.xml", f'<sst {ns}><si><t>Olá </t></si><si><t> </t></si></sst>')
        z.writestr("xl/worksheets/sheet1.xml", f'<worksheet {ns}><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c>'
                                                f'<c r="C1"><v>7</v></c></row><row r="2"><c r="B2"/></row></sheetData></worksheet>')
        z.writestr("xl/workbook.xml", f'<workbook {ns} xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                                      '<sheets><sheet name="Aba1" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                                                 '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
    assert ec.xlsx_linhas(mini.getvalue()) == [{"A": "Olá", "C": "7"}]
    assert ec.xlsx_linhas(mini.getvalue(), aparar=False) == [{"A": "Olá ", "B": " ", "C": "7"}]
    assert ec.xlsx_abas(mini.getvalue()) == {"Aba1": [{"A": "Olá ", "B": " ", "C": "7"}]}


def test_faltando():
    assert ec.faltando({"A", "B"}, ["A", "C"], "CSV") == ["CSV sem a coluna C"]


@pytest.mark.parametrize("nome,doc,esperado", [
    ("  ACME   Ltda ", "11.222.333/0001-81", {"fornecedor": "ACME Ltda", "cnpj": "11222333000181"}),
    ("Padaria", "1222333000181", {"fornecedor": "Padaria", "cnpj": "01222333000181"}),   # zero à esquerda perdido
    ("Fulano", "***.123.456-**", {"fornecedor": "Fulano", "cnpj": None}),                  # mascarado
    ("Fulano", "11222333000182", {"fornecedor": "Fulano", "cnpj": None}),                  # dígito verificador errado
    ("", None, {"fornecedor": None, "cnpj": None}),
])
def test_fornecedor(nome, doc, esperado):
    assert ec.fornecedor(nome, doc) == esperado
