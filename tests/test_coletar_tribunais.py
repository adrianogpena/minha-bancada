"""Coletor e gerador dos ministros dos tribunais superiores (scripts/coletar_tribunais.py, gerar_tribunais.py)."""
import json

import coletar_tribunais as c
import gerar_tribunais as g

TABELA_STF = """<table class="wikitable"><tbody>
<tr><th>Ordem</th><th>Ministro</th><th>Nascimento</th><th>Indicação presidencial</th><th>Data da posse</th></tr>
<tr><td>1</td><td><a href="/wiki/Gilmar_Mendes" title="Gilmar Mendes">Gilmar Ferreira Mendes</a><sup>[1]</sup></td><td>30 de dezembro de 1955</td>
<td>Fernando Henrique Cardoso</td><td><span style="display:none">20020620</span>20 de junho de 2002 (24 anos)</td></tr>
<tr><td>2</td><td><a href="/wiki/C%C3%A1rmen_L%C3%BAcia">Cármen Lúcia Antunes Rocha</a></td><td>19 de abril de 1954</td>
<td>Luiz Inácio Lula da Silva</td><td>21 de junho de 2006</td></tr></tbody></table>"""

TABELA_TSE = """<table class="wikitable"><tbody>
<tr><th>Nome</th><th>Origem</th><th>Início</th></tr>
<tr><th colspan="3">Ministros titulares</th></tr>
<tr><td><a href="/wiki/Nunes_Marques">Kassio Nunes Marques</a> (Presidente)</td><td>STF</td><td>25 de maio de 2023</td></tr>
<tr><th colspan="3">Ministros substitutos</th></tr>
<tr><td>Nauê Bernardo Pinheiro de Azevedo</td><td>Jurista</td><td>março de 2026</td></tr></tbody></table>"""


def test_ler_tabela_stf():
    lista = c.ler_tabelas(TABELA_STF)
    assert [m["nome"] for m in lista] == ["Gilmar Ferreira Mendes", "Cármen Lúcia Antunes Rocha"]
    assert lista[0]["posse"] == "2002-06-20" and lista[0]["nomeadoPor"] == "Fernando Henrique Cardoso"
    assert lista[0]["wiki"] == "Gilmar_Mendes" and lista[1]["wiki"] == "Cármen_Lúcia"
    assert lista[1]["nascimento"] == "1954-04-19"


def test_ler_tabela_tse_com_grupos_e_data_incompleta():
    lista = c.ler_tabelas(TABELA_TSE)
    assert [(m["nome"], m["categoria"]) for m in lista] == [("Kassio Nunes Marques", "Ministros titulares"),
                                                            ("Nauê Bernardo Pinheiro de Azevedo", "Ministros substitutos")]
    assert lista[0]["vaga"] == "STF"
    assert lista[1]["posse"] is None and lista[1]["posseTexto"] == "março de 2026"


def test_data_extenso():
    assert c.data_extenso("4 de abril 2018") == "2018-04-04"
    assert c.data_extenso("1º de agosto de 2025") == "2025-08-01"
    assert c.data_extenso("22/12/2014") == "2014-12-22"
    assert c.data_extenso("2007") is None


def test_atualizar_mantem_entrada_e_fecha_saida():
    anterior = {"atuais": [{"nome": "A Silva", "vistoDesde": "2026-01-01"}, {"nome": "B Souza", "vistoDesde": "2026-01-01"}], "anteriores": []}
    r = c.atualizar(anterior, [{"nome": "A Silva"}, {"nome": "C Lima"}], "2026-10-30")
    assert r["atuais"] == [{"nome": "A Silva", "vistoDesde": "2026-01-01"}, {"nome": "C Lima", "vistoDesde": "2026-10-30"}]
    assert r["anteriores"] == [{"nome": "B Souza", "vistoDesde": "2026-01-01", "vistoAte": "2026-10-30"}]


def test_gerar_ids_estaveis_e_posse_sem_texto(tmp_path):
    (tmp_path / "tribunais").mkdir()
    atuais = [{"nome": "Gilmar Ferreira Mendes", "wiki": "Gilmar_Mendes", "posse": "2002-06-20", "posseTexto": "20 de junho de 2002", "vistoDesde": "2026-10-30"},
              {"nome": "Sem Link Nenhum", "wiki": None, "posse": None, "posseTexto": "março de 2026", "vistoDesde": "2026-10-30"}]
    (tmp_path / "tribunais" / "tribunais.json").write_text(json.dumps(
        {"coletadoEm": "2026-10-30", "tribunais": {"STF": {"nome": "Supremo Tribunal Federal", "fonte": "https://x", "wikipedia": "https://y",
                                                          "atuais": atuais, "anteriores": []}}}), encoding="utf-8")
    um, dois = g.construir(tmp_path), g.construir(tmp_path)
    assert um == dois
    m = um[0]["ministros"]
    assert m[0]["id"].startswith("mtr_") and "posseTexto" not in m[0]
    assert m[1]["posseTexto"] == "março de 2026" and m[1]["id"] != m[0]["id"]
