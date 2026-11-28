import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
TABELA = json.loads((RAIZ / "scripts" / "comissoes_temas.json").read_text(encoding="utf-8"))


def test_todo_tema_da_tabela_e_um_tema_que_a_camara_usa():
    usados = {t for temas in json.loads((RAIZ / "dados" / "proposicoes_temas.json").read_text(encoding="utf-8")).values() for t in temas}
    erradas = {(sigla, x["tema"]) for sigla, c in TABELA["comissoes"].items() for x in c["temas"] if x["tema"] not in usados}
    assert not erradas


def test_cada_comissao_tem_base_legal_e_cada_tema_a_alinea():
    for sigla, c in TABELA["comissoes"].items():
        assert c["base"] and c["nome"], sigla
        assert all(x["alineas"] for x in c["temas"]), sigla
        assert len({x["tema"] for x in c["temas"]}) == len(c["temas"]), sigla


def test_area_das_comissoes_conta_projetos_so_das_comissoes_atuais():
    import sys
    sys.path.insert(0, str(RAIZ / "scripts"))
    import gerar
    orgaos = [{"sigla": "CAPADR", "nome": "x", "fim": None},
              {"sigla": "SUBLEITE", "nome": "Subcomissão (CAPADR/SUBLEITE)", "fim": None},
              {"sigla": "CSAUDE", "nome": "x", "fim": "2025-01-01"},
              {"sigla": "PEC1", "nome": "Comissão Especial (PEC 1/23)", "fim": None}]
    props = [{"temas": ["Estrutura Fundiária"]}, {"temas": ["Saúde"]}, {"temas": ["Estrutura Fundiária", "Agricultura, Pecuária, Pesca e Extrativismo"]}]
    r = gerar.resumir_area_das_comissoes(props, orgaos)
    assert [(a["sigla"], a["projetos"]) for a in r] == [("CAPADR", 2)]
