"""Relatorias do TCU e do STJ (scripts/coletar_relatorias.py) e o que o gerar_tribunais.py faz com elas."""
import coletar_relatorias as r
import gerar_tribunais as g
import identidades


def test_agregar_tcu_por_dia_e_relator():
    itens = [{"dataSessao": "28/10/2026", "relator": "RODRIGO PACHECO", "tipo": "ACÓRDÃO", "numeroAcordao": "1", "anoAcordao": "2026", "colegiado": "Plenário"},
             {"dataSessao": "28/10/2026", "relator": "RODRIGO PACHECO", "tipo": "ACÓRDÃO DE RELAÇÃO", "numeroAcordao": "2", "anoAcordao": "2026"},
             {"dataSessao": "27/10/2026", "relator": "ODAIR CUNHA", "tipo": "ACÓRDÃO", "numeroAcordao": "3", "anoAcordao": "2026"},
             {"dataSessao": None, "relator": "SEM DATA", "tipo": "ACÓRDÃO"}]
    dias, recentes = r.agregar_tcu(itens)
    assert dias == {"2026-10-28": {"RODRIGO PACHECO": {"ACÓRDÃO": 1, "ACÓRDÃO DE RELAÇÃO": 1}}, "2026-10-27": {"ODAIR CUNHA": {"ACÓRDÃO": 1}}}
    assert [x["numero"] for x in recentes["RODRIGO PACHECO"]] == ["2", "1"]


def test_contar_stj_por_ano():
    itens = [{"ministroRelator": "HERMAN BENJAMIN", "dataDecisao": "20240110"}, {"ministroRelator": "HERMAN BENJAMIN", "dataDecisao": "20250102"},
             {"ministroRelator": "HERMAN BENJAMIN", "dataDecisao": "20250103"}, {"ministroRelator": "", "dataDecisao": "20250103"},
             {"ministroRelator": "X", "dataDecisao": "None"}]
    assert r.contar_stj(itens) == {"HERMAN BENJAMIN": {"2024": 1, "2025": 2}}


def test_recursos_stj_so_json_mensal_a_partir_de_2023():
    pacote = {"result": {"resources": [
        {"id": "a", "format": "JSON", "name": "20220531.json"}, {"id": "b", "format": "JSON", "name": "20230531.json"},
        {"id": "c", "format": "CSV", "name": "dicionario.csv"}, {"id": "d", "format": "ZIP", "name": "20240531.zip"},
        {"id": "e", "format": "JSON", "name": "20240630.json"}]}}
    assert [x["id"] for x in r.recursos_stj(pacote)] == ["b", "e"]


def test_casar_relator_pelas_palavras_do_nome():
    ministros = [{"nome": "Antonio Herman de Vasconcellos e Benjamin"}, {"nome": "Marco Aurélio Gastaldi Buzzi"}, {"nome": "Marco Aurélio Bellizze Oliveira"}]
    assert g.casar_relator("HERMAN BENJAMIN", ministros) is ministros[0]
    assert g.casar_relator("MARCO BUZZI", ministros) is ministros[1]
    assert g.casar_relator("MARCO AURÉLIO", ministros) is None
    assert g.casar_relator("FULANO", ministros) is None


def test_juntar_relatorias_confirma_e_separa_outros():
    ministros = [{"nome": "Vital do Rêgo Filho"}, {"nome": "Walton Alencar Rodrigues"}]
    por_relator = {"VITAL DO RÊGO": {"2026": 2, "2025": 5}, "WEDER DE OLIVEIRA": {"2026": 57}, "ANTIGO RELATOR": {"2023": 4}}
    fora = g.juntar_relatorias("TCU", ministros, por_relator, {}, 2026)
    assert ministros[0]["relatorias"] == {"2026": 2, "2025": 5} and ministros[0]["confirmado"] is True
    assert ministros[1]["confirmado"] is False
    assert [o["nome"] for o in fora] == ["Weder De Oliveira", "Antigo Relator"]


def test_id_do_ministro_estavel_e_sem_wikipedia():
    com = identidades.id_ministro_tribunal("STF", {"nome": "Gilmar Mendes", "wiki": "Gilmar_Mendes"})
    sem = identidades.id_ministro_tribunal("TST", {"nome": "Lélio Bentes Corrêa", "wiki": None})
    assert com.startswith("mtr_") and sem.startswith("mtr_") and com != sem
    assert sem == identidades.id_ministro_tribunal("TST", {"nome": "Lelio Bentes Correa", "wiki": None})
