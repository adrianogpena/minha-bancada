import json
import subprocess
import sys

import pytest

from conftest import RAIZ

SCRIPT = RAIZ / "scripts" / "simplificar_df.py"


def carregar_funcoes():
    """O script executa main() ao ser importado; carrega só as definições."""
    fonte = SCRIPT.read_text(encoding="utf-8")
    fonte = fonte.rsplit("\nmain(sys.argv", 1)[0]
    ns = {"__file__": str(SCRIPT), "__name__": "simplificar_df"}
    exec(compile(fonte, str(SCRIPT), "exec"), ns)
    return ns


F = carregar_funcoes()


@pytest.mark.parametrize("r,n", [("I", 1), ("IV", 4), ("IX", 9), ("XIV", 14), ("XXXIII", 33), ("XL", 40)])
def test_romano(r, n):
    assert F["romano"](r) == n


def test_nomes_das_ras_cobrem_todos_os_numeros():
    assert len(F["NOMES"]) == 35
    assert F["NOMES"][F["romano"]("I") - 1] == "Plano Piloto"


def test_dist2_ponto_no_segmento_e_fora():
    assert F["dist2"]((1, 1), (0, 0), (2, 0)) == 1
    assert F["dist2"]((5, 0), (0, 0), (2, 0)) == 9      # além da ponta: distância ao extremo
    assert F["dist2"]((3, 4), (0, 0), (0, 0)) == 25     # segmento degenerado


def test_douglas_remove_pontos_colineares_e_mantem_desvios():
    reta = [(0, 0), (1, 0), (2, 0), (3, 0)]
    assert F["douglas"](reta, 0.01) == [(0, 0), (3, 0)]
    pico = [(0, 0), (1, 5), (2, 0)]
    assert F["douglas"](pico, 0.01) == pico
    assert F["douglas"]([(0, 0), (1, 1)], 1) == [(0, 0), (1, 1)]


def test_anel_descarta_aneis_degenerados_e_arredonda():
    assert F["anel"]([[0, 0], [0.00001, 0.00001], [0.00002, 0]]) is None
    quadrado = [[0, 0, 9], [0, 1, 9], [1, 1, 9], [1, 0, 9], [0, 0, 9]]
    assert F["anel"](quadrado) == [[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]
    assert F["anel"]([[0.123456, 0], [0.123456, 1], [1, 1], [0.123456, 0]])[0][0] == 0.1235


def test_geojson_versionado_e_valido():
    dados = json.loads((RAIZ / "site" / "geo" / "df_ras.json").read_text(encoding="utf-8"))
    assert dados["type"] == "FeatureCollection" and len(dados["features"]) == 35
    for f in dados["features"]:
        assert f["geometry"]["type"] == "MultiPolygon"
        for poli in f["geometry"]["coordinates"]:
            for aro in poli:
                assert len(aro) >= 4 and aro[0] == aro[-1], f["properties"]["nome"]


def test_script_de_ponta_a_ponta_com_arquivo_local(tmp_path):
    entrada = tmp_path / "ras.json"
    entrada.write_text(json.dumps({"features": [{
        "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]]},
        "properties": {"ra_codigo": "RA-II"}}]}), encoding="utf-8")
    destino = RAIZ / "site" / "geo" / "df_ras.json"
    antes = destino.read_bytes()
    try:
        r = subprocess.run([sys.executable, "-I", str(SCRIPT), str(entrada)], capture_output=True, text=True, check=True)
        assert "1 RAs" in r.stdout
        saida = json.loads(destino.read_text(encoding="utf-8"))
        assert saida["features"][0]["properties"] == {"nome": "Gama", "codigo": "RA-II"}
    finally:
        destino.write_bytes(antes)
