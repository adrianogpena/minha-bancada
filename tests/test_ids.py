import hashlib
import re
from pathlib import Path

import pytest

import identidades
import mandatos
from ids import gerar_id

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def sha(texto, n=12):
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()[:n]


def test_gerar_id_e_o_hash_de_fonte_e_id_original():
    assert gerar_id("pes", "camara", 204554) == "pes_" + sha("camara|204554")
    assert gerar_id("pes", "camara", " 204554 ") == gerar_id("pes", "camara", "204554") == gerar_id("pes", "camara", 204554)
    assert gerar_id("man", "tse:2022", "1") != gerar_id("man", "tse:2024", "1") != gerar_id("can", "tse:2022", "1")


@pytest.mark.parametrize("fonte, original", [("", "1"), ("camara", None), ("camara", ""), ("camara", "None"), ("camara", "  ")])
def test_gerar_id_recusa_fonte_ou_id_vazio(fonte, original):
    with pytest.raises(ValueError):
        gerar_id("pes", fonte, original)


def test_id_de_pessoa_segue_o_formato_de_antes_da_regra():
    """Os ids de pessoa já eram sha1 de "fonte|id"; passar por gerar_id não os muda."""
    reg = identidades._Registro()
    assert reg.obter("nn", "ana souza|1980-01-02")["id"] == "pes_" + sha("nn|ana souza|1980-01-02")
    assert reg.obter("tse", "2022|7")["id"] == "pes_" + sha("tse|2022|7")
    assert reg.obter("estadual", "SP|12")["id"] == "pes_" + sha("estadual|SP|12")
    assert reg.obter("camara", 5) is reg.obter("camara", "5")


def test_mandato_do_tse_repetido_fica_com_o_id_do_menor_sequencial_em_qualquer_ordem(tmp_path):
    import json

    def montar(ordem):
        eleitos = [{"sequencial": s, "nome": "Ana Maria Souza", "urna": "Ana", "cargo": "DEPUTADO FEDERAL", "uf": "SP", "nascimento": "1980-01-02",
                    "partido": "PT", "situacao": "eleito", "unidadeEleitoral": "SP"} for s in ordem]
        arq = tmp_path / ("a" + "".join(ordem)) / "tse" / "2022" / "SP.json"
        arq.parent.mkdir(parents=True)
        arq.write_text(json.dumps(eleitos), encoding="utf-8")
        bruto = arq.parent.parent.parent
        nucleo = identidades.construir({}, bruto)
        return mandatos.construir({}, bruto, nucleo, hoje="2026-01-01")["mandatos"]

    um, outro = montar(["20", "10"]), montar(["10", "20"])
    assert len(um) == len(outro) == 1
    assert um[0]["id"] == outro[0]["id"] == gerar_id("man", "tse:2022", "10") and um[0]["fontes"] == {"tse": "10"}


def test_nenhum_id_do_projeto_nasce_de_sha1_fora_de_ids_py():
    """Ids novos passam por ids.gerar_id: sha1 só em ids.py (sha256 de arquivo e de token não são ids)."""
    fora = [f.name for f in SCRIPTS.glob("*.py") if f.name != "ids.py" and re.search(r"\bsha1\b", f.read_text(encoding="utf-8"))]
    assert fora == []
